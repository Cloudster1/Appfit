import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import cast

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session

from appfit.models import (
    App,
    ExternalSystem,
    Interface,
    InterfaceStatus,
    InterfaceType,
    LifecycleStatus,
    TagCategory,
)
from appfit.schemas.interface import (
    EndpointRef,
    ExternalSystemIn,
    ExternalSystemOut,
    InterfaceIn,
    InterfaceOut,
    Landscape,
    LandscapeEdge,
    LandscapeNode,
)
from appfit.services.apps import get_app, in_any_domain, notify_embedder, refresh_search_tsv
from appfit.services.errors import ConflictError, NotFoundError, ServiceError
from appfit.services.interface_docs import endpoint_out, refresh_interface_hash

# Fields copied from InterfaceIn onto the row; endpoints are resolved separately.
CONTENT_FIELDS = ("name", "interface_type", "data_objects", "frequency", "status", "bidirectional", "description")


@dataclass
class Endpoint:
    app: App | None = None
    system: ExternalSystem | None = None

    @property
    def key(self) -> uuid.UUID:
        target = self.app if self.app is not None else self.system
        assert target is not None
        return target.id


def find_system(db: Session, name: str) -> ExternalSystem | None:
    return db.scalar(select(ExternalSystem).where(func.lower(ExternalSystem.name) == name.strip().lower()))


def get_or_create_system(db: Session, name: str) -> ExternalSystem:
    system = find_system(db, name)
    if system is None:
        system = ExternalSystem(id=uuid.uuid4(), name=name, description="")
        db.add(system)
        db.flush()
    return system


def resolve_endpoint(db: Session, ref: EndpointRef, *, create_systems: bool = True) -> Endpoint:
    if ref.app is not None:
        app = get_app(db, ref.app)
        if app is None:
            raise ServiceError(f"Unknown app {ref.app!r}")
        return Endpoint(app=app)
    assert ref.system is not None
    system = get_or_create_system(db, ref.system) if create_systems else find_system(db, ref.system)
    if system is None:
        raise ServiceError(f"Unknown external system {ref.system!r}")
    return Endpoint(system=system)


def _endpoint_filter(side: str, ep: Endpoint) -> ColumnElement[bool]:
    column = getattr(Interface, f"{side}_app_id" if ep.app is not None else f"{side}_system_id")
    return cast(ColumnElement[bool], column == ep.key)


def find_interface(db: Session, source: Endpoint, target: Endpoint, name: str) -> Interface | None:
    """The upsert key: both endpoints and the name, case-insensitive."""
    return db.scalar(
        select(Interface).where(
            _endpoint_filter("from", source),
            _endpoint_filter("to", target),
            func.lower(Interface.name) == name.lower(),
        )
    )


def get_interface(db: Session, interface_id: uuid.UUID) -> Interface:
    iface = db.get(Interface, interface_id)
    if iface is None:
        raise NotFoundError("Interface not found")
    return iface


def _app_ids(iface: Interface) -> set[uuid.UUID]:
    return {a for a in (iface.from_app_id, iface.to_app_id) if a is not None}


def _after_write(db: Session, iface: Interface | None, app_ids: set[uuid.UUID]) -> None:
    db.flush()
    if iface is not None:
        db.refresh(iface)
        refresh_interface_hash(iface)
        db.flush()
    for app_id in app_ids:
        refresh_search_tsv(db, app_id)
    notify_embedder(db)


def _assign(iface: Interface, source: Endpoint, target: Endpoint, data: InterfaceIn) -> bool:
    """Copy endpoints and content onto the row; True if anything changed."""
    changed = False
    values = {
        "from_app_id": source.app.id if source.app else None,
        "from_system_id": source.system.id if source.system else None,
        "to_app_id": target.app.id if target.app else None,
        "to_system_id": target.system.id if target.system else None,
        **{f: getattr(data, f) for f in CONTENT_FIELDS},
    }
    for key, value in values.items():
        current = getattr(iface, key)
        if key == "data_objects":
            current = list(current or [])
        if current != value:
            setattr(iface, key, value)
            changed = True
    return changed


def create_interface(db: Session, data: InterfaceIn, user_id: uuid.UUID | None) -> Interface:
    source, target = resolve_endpoint(db, data.source), resolve_endpoint(db, data.target)
    if find_interface(db, source, target, data.name) is not None:
        raise ConflictError(f"An interface named {data.name!r} already exists between these endpoints")
    iface = Interface(id=uuid.uuid4(), created_by=user_id, updated_by=user_id)
    _assign(iface, source, target, data)
    db.add(iface)
    _after_write(db, iface, _app_ids(iface))
    return iface


def update_interface(db: Session, iface: Interface, data: InterfaceIn, user_id: uuid.UUID | None) -> bool:
    source, target = resolve_endpoint(db, data.source), resolve_endpoint(db, data.target)
    clash = find_interface(db, source, target, data.name)
    if clash is not None and clash.id != iface.id:
        raise ConflictError(f"An interface named {data.name!r} already exists between these endpoints")
    before = _app_ids(iface)
    changed = _assign(iface, source, target, data)
    if changed:
        iface.updated_by = user_id
        _after_write(db, iface, before | _app_ids(iface))
    return changed


def delete_interface(db: Session, iface: Interface) -> None:
    app_ids = _app_ids(iface)
    db.delete(iface)
    _after_write(db, None, app_ids)


def list_interfaces(
    db: Session,
    app_slug: str | None = None,
    system: str | None = None,
    types: list[InterfaceType] | None = None,
    statuses: list[InterfaceStatus] | None = None,
) -> list[Interface]:
    stmt = select(Interface)
    if app_slug:
        app = get_app(db, app_slug)
        if app is None:
            return []
        stmt = stmt.where(or_(Interface.from_app_id == app.id, Interface.to_app_id == app.id))
    if system:
        found = find_system(db, system)
        if found is None:
            return []
        stmt = stmt.where(or_(Interface.from_system_id == found.id, Interface.to_system_id == found.id))
    if types:
        stmt = stmt.where(Interface.interface_type.in_(types))
    if statuses:
        stmt = stmt.where(Interface.status.in_(statuses))
    return list(db.scalars(stmt.order_by(func.lower(Interface.name))).unique().all())


def to_interface_out(iface: Interface, active_model: str) -> InterfaceOut:
    return InterfaceOut(
        id=iface.id,
        source=endpoint_out(iface.from_app, iface.from_system),
        target=endpoint_out(iface.to_app, iface.to_system),
        name=iface.name,
        interface_type=iface.interface_type,
        data_objects=list(iface.data_objects),
        frequency=iface.frequency,
        status=iface.status,
        bidirectional=iface.bidirectional,
        description=iface.description,
        indexed=iface.embedded_at is not None and iface.embedding_model == active_model,
        updated_at=iface.updated_at,
    )


# External systems


def _system_usage(db: Session) -> Counter[uuid.UUID]:
    usage: Counter[uuid.UUID] = Counter()
    for from_id, to_id in db.execute(select(Interface.from_system_id, Interface.to_system_id)).all():
        usage.update(i for i in (from_id, to_id) if i is not None)
    return usage


def list_systems(db: Session) -> list[ExternalSystemOut]:
    usage = _system_usage(db)
    systems = db.scalars(select(ExternalSystem).order_by(func.lower(ExternalSystem.name))).all()
    return [to_system_out(s, usage[s.id]) for s in systems]


def to_system_out(system: ExternalSystem, interface_count: int) -> ExternalSystemOut:
    return ExternalSystemOut(
        id=system.id,
        name=system.name,
        description=system.description,
        vendor=system.vendor,
        url=system.url,
        interface_count=interface_count,
    )


def system_interface_count(db: Session, system_id: uuid.UUID) -> int:
    return _system_usage(db)[system_id]


def get_system(db: Session, system_id: uuid.UUID) -> ExternalSystem:
    system = db.get(ExternalSystem, system_id)
    if system is None:
        raise NotFoundError("External system not found")
    return system


def save_system(db: Session, data: ExternalSystemIn, system: ExternalSystem | None = None) -> ExternalSystem:
    clash = find_system(db, data.name)
    if clash is not None and (system is None or clash.id != system.id):
        raise ConflictError(f"An external system named {data.name!r} already exists")
    renamed = system is not None and system.name != data.name
    if system is None:
        system = ExternalSystem(id=uuid.uuid4())
        db.add(system)
    system.name, system.description, system.vendor, system.url = data.name, data.description, data.vendor, data.url
    db.flush()
    if renamed:
        # Interface texts and app search vectors contain the system name.
        touching = db.scalars(
            select(Interface).where(or_(Interface.from_system_id == system.id, Interface.to_system_id == system.id))
        ).unique()
        app_ids: set[uuid.UUID] = set()
        for iface in touching:
            db.refresh(iface)
            refresh_interface_hash(iface)
            app_ids |= _app_ids(iface)
        _after_write(db, None, app_ids)
    return system


def delete_system(db: Session, system: ExternalSystem) -> None:
    used = system_interface_count(db, system.id)
    if used:
        raise ConflictError(f"{system.name} is used by {used} interface(s); delete or change those first")
    db.delete(system)
    db.flush()


# Landscape


@dataclass
class LandscapeFilters:
    domains: list[str] = field(default_factory=list)
    lifecycle: list[LifecycleStatus] = field(default_factory=list)
    types: list[InterfaceType] = field(default_factory=list)
    statuses: list[InterfaceStatus] = field(default_factory=list)
    include_systems: bool = True
    include_unconnected: bool = False


def app_node_id(app_id: uuid.UUID) -> str:
    return f"app:{app_id}"


def system_node_id(system_id: uuid.UUID) -> str:
    return f"system:{system_id}"


def node_id(app_id: uuid.UUID | None, system_id: uuid.UUID | None) -> str:
    return app_node_id(app_id) if app_id is not None else system_node_id(system_id)  # type: ignore[arg-type]


def landscape(db: Session, f: LandscapeFilters) -> Landscape:
    """Apps passing the filters, the interfaces between them and (optionally) the external systems they use."""
    lifecycle = f.lifecycle or [s for s in LifecycleStatus if s != LifecycleStatus.retired]
    app_stmt = select(App).where(App.lifecycle_status.in_(lifecycle))
    if f.domains:
        app_stmt = app_stmt.where(in_any_domain(f.domains))
    apps = {a.id: a for a in db.scalars(app_stmt)}

    iface_stmt = select(Interface)
    if f.types:
        iface_stmt = iface_stmt.where(Interface.interface_type.in_(f.types))
    if f.statuses:
        iface_stmt = iface_stmt.where(Interface.status.in_(f.statuses))

    edges: list[LandscapeEdge] = []
    systems: dict[uuid.UUID, ExternalSystem] = {}
    degree: Counter[str] = Counter()
    for iface in db.scalars(iface_stmt.order_by(func.lower(Interface.name))).unique():
        ends = [(iface.from_app_id, iface.from_system), (iface.to_app_id, iface.to_system)]
        if any(app_id is not None and app_id not in apps for app_id, _ in ends):
            continue
        if not f.include_systems and any(system is not None for _, system in ends):
            continue
        for _, system in ends:
            if system is not None:
                systems[system.id] = system
        source = node_id(iface.from_app_id, iface.from_system_id)
        target = node_id(iface.to_app_id, iface.to_system_id)
        degree.update([source, target])
        edges.append(
            LandscapeEdge(
                id=iface.id,
                source=source,
                target=target,
                name=iface.name,
                interface_type=iface.interface_type,
                status=iface.status,
                bidirectional=iface.bidirectional,
                data_objects=list(iface.data_objects),
                frequency=iface.frequency,
            )
        )

    nodes = [
        LandscapeNode(
            id=app_node_id(a.id),
            kind="app",
            name=a.name,
            slug=a.slug,
            lifecycle_status=a.lifecycle_status,
            domains=[t.name for t in a.tags if t.category == TagCategory.domain],
            degree=degree[app_node_id(a.id)],
        )
        for a in sorted(apps.values(), key=lambda a: a.name.lower())
        if f.include_unconnected or degree[app_node_id(a.id)] > 0
    ]
    nodes += [
        LandscapeNode(id=system_node_id(s.id), kind="system", name=s.name, degree=degree[system_node_id(s.id)])
        for s in sorted(systems.values(), key=lambda s: s.name.lower())
    ]
    return Landscape(nodes=nodes, edges=edges)
