import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from slugify import slugify
from sqlalchemy import Select, func, or_, select, text
from sqlalchemy.orm import Session, object_session

from appfit.config import RESERVED_SLUGS, SLUG_MAX_LEN
from appfit.models import (
    App,
    AppCapability,
    AppMaintainer,
    Interface,
    LicenseType,
    LifecycleStatus,
    Maintainer,
    MaintainerRole,
    Tag,
    TagCategory,
    app_tags,
)
from appfit.schemas.app import (
    AppListItem,
    AppMaintainerOut,
    AppOut,
    CapabilityIn,
    CapabilityOut,
    LinkItem,
    MaintainerRef,
)
from appfit.services.errors import ConflictError, ServiceError
from appfit.services.interface_docs import refresh_interface_hash, to_summary, touching_interfaces
from appfit.text import content_hash, normalize_ws

EMBED_CHANNEL = "appfit_embed"
_SLUG_SUFFIX_ROOM = 4  # room for "-NN" when de-duplicating slugs

SCALAR_FIELDS = (
    "name",
    "short_description",
    "description",
    "lifecycle_status",
    "license",
    "license_type",
    "vendor",
    "version",
    "homepage_url",
    "repo_url",
    "docs_url",
    "extra",
)
# Non-nullable columns: an explicit null (import "clear") resets them to their default.
SCALAR_DEFAULTS: dict[str, Any] = {
    "short_description": "",
    "description": "",
    "lifecycle_status": LifecycleStatus.active,
    "extra": {},
}
TAG_FIELDS = {"tags": TagCategory.general, "tech_stack": TagCategory.tech, "domains": TagCategory.domain}

# Interface texts (name, data objects, description, both endpoint names) join weight C, deprecated ones excluded.
REFRESH_TSV_SQL = text(
    """
    UPDATE apps a SET search_tsv =
        setweight(to_tsvector('german', coalesce(a.name, '')), 'A')
        || setweight(to_tsvector('english', coalesce(a.name, '')), 'A')
        || setweight(to_tsvector('german', coalesce(a.short_description, '') || ' ' || coalesce(t.tags, '')), 'B')
        || setweight(to_tsvector('english', coalesce(a.short_description, '') || ' ' || coalesce(t.tags, '')), 'B')
        || setweight(to_tsvector('german', coalesce(a.description, '') || ' ' || coalesce(c.caps, '')
                                 || ' ' || coalesce(a.vendor, '') || ' ' || coalesce(f.ifaces, '')), 'C')
        || setweight(to_tsvector('english', coalesce(a.description, '') || ' ' || coalesce(c.caps, '')
                                 || ' ' || coalesce(a.vendor, '') || ' ' || coalesce(f.ifaces, '')), 'C')
    FROM (SELECT string_agg(tg.name, ' ') AS tags
            FROM app_tags at JOIN tags tg ON tg.id = at.tag_id WHERE at.app_id = :app_id) t,
         (SELECT string_agg(ac.text || ' ' || coalesce(ac.details, ''), ' ') AS caps
            FROM app_capabilities ac WHERE ac.app_id = :app_id) c,
         (SELECT string_agg(i.name || ' ' || array_to_string(i.data_objects, ' ') || ' ' || i.description
                            || ' ' || coalesce(fa.name, fs.name, '') || ' ' || coalesce(ta.name, ts.name, ''), ' ')
                 AS ifaces
            FROM interfaces i
            LEFT JOIN apps fa ON fa.id = i.from_app_id
            LEFT JOIN external_systems fs ON fs.id = i.from_system_id
            LEFT JOIN apps ta ON ta.id = i.to_app_id
            LEFT JOIN external_systems ts ON ts.id = i.to_system_id
           WHERE (i.from_app_id = :app_id OR i.to_app_id = :app_id) AND i.status <> 'deprecated') f
    WHERE a.id = :app_id
    """
)


def refresh_search_tsv(db: Session, app_id: uuid.UUID) -> None:
    db.execute(REFRESH_TSV_SQL, {"app_id": app_id})


def notify_embedder(db: Session) -> None:
    db.execute(text("SELECT pg_notify(:ch, '')"), {"ch": EMBED_CHANNEL})


@dataclass
class ApplyResult:
    changed_fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def summary_document(app: App) -> str:
    """Text embedded as the app-level vector: identity, description, tags and tech, not capabilities."""
    parts = [normalize_ws(f"{app.name}. {app.short_description or ''}")]
    if app.description:
        parts.append(normalize_ws(app.description))
    tags = [t.name for t in app.tags if t.category != TagCategory.tech]
    tech = [t.name for t in app.tags if t.category == TagCategory.tech]
    if tags:
        parts.append("Tags: " + ", ".join(tags))
    if tech:
        parts.append("Tech: " + ", ".join(tech))
    return "\n".join(parts)


def get_app(db: Session, slug: str) -> App | None:
    return db.scalar(select(App).where(App.slug == slug))


def unique_slug(db: Session, base: str, exclude_id: uuid.UUID | None = None) -> str:
    root = slugify(base, max_length=SLUG_MAX_LEN - _SLUG_SUFFIX_ROOM) or "app"
    candidate, n = root, 2
    while True:
        stmt = select(App.id).where(App.slug == candidate)
        if exclude_id is not None:
            stmt = stmt.where(App.id != exclude_id)
        if candidate not in RESERVED_SLUGS and db.scalar(stmt) is None:
            return candidate
        candidate, n = f"{root}-{n}", n + 1


def get_or_create_tag(db: Session, name: str, category: TagCategory) -> Tag:
    tag = db.scalar(select(Tag).where(Tag.category == category, Tag.name == name))
    if tag is None:
        tag = Tag(id=uuid.uuid4(), name=name, category=category)
        db.add(tag)
    return tag


def resolve_maintainer(db: Session, ref: MaintainerRef) -> Maintainer:
    m: Maintainer | None = None
    if ref.id is not None:
        m = db.get(Maintainer, ref.id)
        if m is None:
            raise ServiceError(f"Unknown maintainer id {ref.id}")
        return m
    if ref.email:
        m = db.scalar(select(Maintainer).where(Maintainer.email == ref.email))
    if m is None and ref.name:
        m = db.scalar(
            select(Maintainer).where(func.lower(Maintainer.name) == ref.name.lower()).order_by(Maintainer.name)
        )
        if m is not None and ref.email and m.email and m.email != ref.email:
            m = None  # same name, different person
    if m is None:
        if not ref.name:
            raise ServiceError("A new maintainer needs a name")
        m = Maintainer(id=uuid.uuid4(), name=ref.name, email=ref.email, kind=ref.kind, org_unit=ref.org_unit)
        db.add(m)
        db.flush()
    else:
        if ref.email and not m.email:
            m.email = ref.email
        if ref.org_unit and not m.org_unit:
            m.org_unit = ref.org_unit
    return m


def _apply_capabilities(app: App, incoming: Sequence[CapabilityIn], result: ApplyResult) -> bool:
    """Diff capabilities, text match first so unchanged statements keep id and embedding."""
    existing = list(app.capabilities)
    by_text = {c.text.lower(): c for c in existing}
    by_id = {c.id: c for c in existing}
    used: set[uuid.UUID] = set()
    new_list: list[AppCapability] = []
    changed = False
    seen_texts: set[str] = set()
    incoming_texts = {ci.text.lower() for ci in incoming}

    for ci in incoming:
        key = ci.text.lower()
        if key in seen_texts:
            result.warnings.append(f"Duplicate capability removed: {ci.text!r}")
            changed = True
            continue
        seen_texts.add(key)
        cap = by_text.get(key)
        if cap is not None and cap.id in used:
            cap = None
        if cap is None and ci.id is not None:
            candidate = by_id.get(ci.id)
            # Only reuse by id when no incoming item will claim this row by its current text.
            if candidate is not None and candidate.id not in used and candidate.text.lower() not in incoming_texts:
                cap = candidate
        if cap is None:
            cap = AppCapability(
                id=uuid.uuid4(), kind=ci.kind, text=ci.text, details=ci.details, content_hash=content_hash(ci.text)
            )
            changed = True
        else:
            if cap.text != ci.text:
                cap.text = ci.text
                cap.content_hash = content_hash(ci.text)
                cap.embedding = None
                cap.embedded_at = None
                changed = True
            if cap.kind != ci.kind or (cap.details or None) != (ci.details or None):
                cap.kind, cap.details = ci.kind, ci.details
                changed = True
        used.add(cap.id)
        new_list.append(cap)

    if len(new_list) != len(existing) or any(c.id not in used for c in existing):
        changed = True
    for pos, cap in enumerate(new_list):
        if cap.position != pos:
            cap.position = pos
            changed = True
    if changed:
        app.capabilities = new_list
    return changed


def _apply_tags(db: Session, app: App, category: TagCategory, names: Sequence[str]) -> bool:
    current = {t.name for t in app.tags if t.category == category}
    if current == set(names) and len(current) == len(names):
        return False
    keep = [t for t in app.tags if t.category != category]
    app.tags = keep + [get_or_create_tag(db, n, category) for n in names]
    return True


def _apply_maintainers(db: Session, app: App, refs: Sequence[MaintainerRef]) -> bool:
    desired: list[tuple[Maintainer, Any]] = []
    seen: set[tuple[uuid.UUID, str]] = set()
    for ref in refs:
        m = resolve_maintainer(db, ref)
        key = (m.id, ref.role.value)
        if key not in seen:
            seen.add(key)
            desired.append((m, ref.role))
    current = {(link.maintainer_id, link.role.value) for link in app.maintainer_links}
    if current == seen:
        return False
    existing = {(link.maintainer_id, link.role.value): link for link in app.maintainer_links}
    app.maintainer_links = [
        existing.get((m.id, role.value)) or AppMaintainer(maintainer_id=m.id, maintainer=m, role=role)
        for m, role in desired
    ]
    return True


def apply_app_data(db: Session, app: App, data: dict[str, Any], user_id: uuid.UUID | None) -> ApplyResult:
    """Apply the given fields; absent keys stay untouched, collections present replace the current set."""
    result = ApplyResult()
    for name in SCALAR_FIELDS:
        if name not in data:
            continue
        value = data[name]
        if value is None and name in SCALAR_DEFAULTS:
            value = SCALAR_DEFAULTS[name]
        if name == "name" and not value:
            raise ServiceError("name is required")
        if getattr(app, name) != value:
            setattr(app, name, value)
            result.changed_fields.append(name)

    if "slug" in data and data["slug"] and data["slug"] != app.slug:
        clash = db.scalar(select(App.id).where(App.slug == data["slug"], App.id != app.id))
        if clash is not None:
            raise ConflictError(f"Slug {data['slug']!r} is already used")
        app.slug = data["slug"]
        result.changed_fields.append("slug")

    if "links" in data:
        links = [
            (link.model_dump() if isinstance(link, LinkItem) else LinkItem.model_validate(link).model_dump())
            for link in data["links"] or []
        ]
        if (app.links or []) != links:
            app.links = links
            result.changed_fields.append("links")

    for fname, category in TAG_FIELDS.items():
        if fname in data and _apply_tags(db, app, category, data[fname] or []):
            result.changed_fields.append(fname)

    if "maintainers" in data and _apply_maintainers(db, app, data["maintainers"] or []):
        result.changed_fields.append("maintainers")

    if "capabilities" in data and _apply_capabilities(app, data["capabilities"] or [], result):
        result.changed_fields.append("capabilities")

    if result.changed_fields:
        app.updated_by = user_id
    return result


def _neighbour_ids(interfaces: Sequence[Interface], app_id: uuid.UUID) -> set[uuid.UUID]:
    return {
        other
        for iface in interfaces
        for other in (iface.from_app_id, iface.to_app_id)
        if other is not None and other != app_id
    }


def sync_derived(db: Session, app: App) -> None:
    """Refresh FTS vector and summary staleness after a write, and wake the embedding worker."""
    db.flush()
    new_hash = content_hash(summary_document(app))
    if app.summary_hash != new_hash:
        app.summary_hash = new_hash
        app.summary_embedding = None
        app.embedded_at = None
        db.flush()
    # Interface texts and the neighbours' search texts contain the app name, so a rename makes them stale.
    interfaces = touching_interfaces(db, app.id)
    for iface in interfaces:
        refresh_interface_hash(iface)
    db.flush()
    for app_id in (app.id, *_neighbour_ids(interfaces, app.id)):
        refresh_search_tsv(db, app_id)
    notify_embedder(db)


def create_app(db: Session, data: dict[str, Any], user_id: uuid.UUID | None) -> tuple[App, ApplyResult]:
    slug = data.get("slug")
    if slug:
        if db.scalar(select(App.id).where(App.slug == slug)) is not None:
            raise ConflictError(f"Slug {slug!r} is already used")
    else:
        slug = unique_slug(db, data["name"])
    app = App(id=uuid.uuid4(), slug=slug, name=data["name"], created_by=user_id, links=[], extra={})
    db.add(app)
    result = apply_app_data(db, app, {**data, "slug": slug}, user_id)
    sync_derived(db, app)
    return app, result


def update_app(db: Session, app: App, data: dict[str, Any], user_id: uuid.UUID | None) -> ApplyResult:
    result = apply_app_data(db, app, data, user_id)
    if result.changed_fields:
        sync_derived(db, app)
    return result


def delete_app(db: Session, app: App) -> None:
    """Delete the app; its interfaces go with it, so its neighbours' search texts are rebuilt."""
    neighbours = _neighbour_ids(touching_interfaces(db, app.id), app.id)
    db.delete(app)
    db.flush()
    for app_id in neighbours:
        refresh_search_tsv(db, app_id)


@dataclass
class AppFilters:
    q: str | None = None
    tags: list[str] = field(default_factory=list)
    statuses: list[LifecycleStatus] = field(default_factory=list)
    license_types: list[LicenseType] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    maintainer: str | None = None
    sort: str = "name"


def _tsquery(q: str) -> Any:
    return func.websearch_to_tsquery("german", q).op("||")(func.websearch_to_tsquery("english", q))


def in_any_domain(domains: list[str]) -> Any:
    names = [d.strip().lower() for d in domains]
    return App.tags.any((Tag.category == TagCategory.domain) & Tag.name.in_(names))


def apply_app_filters(stmt: Select[Any], f: AppFilters) -> Select[Any]:
    if f.q:
        like = f"%{f.q.strip()}%"
        stmt = stmt.where(or_(App.search_tsv.op("@@")(_tsquery(f.q)), App.name.ilike(like), App.slug.ilike(like)))
    for tag in f.tags:
        stmt = stmt.where(App.tags.any(Tag.name == tag.strip().lower()))
    if f.statuses:
        stmt = stmt.where(App.lifecycle_status.in_(f.statuses))
    if f.license_types:
        stmt = stmt.where(App.license_type.in_(f.license_types))
    if f.domains:
        stmt = stmt.where(in_any_domain(f.domains))
    if f.maintainer:
        like = f"%{f.maintainer.strip()}%"
        stmt = stmt.where(
            App.maintainer_links.any(
                AppMaintainer.maintainer.has(or_(Maintainer.name.ilike(like), Maintainer.email.ilike(like)))
            )
        )
    return stmt


def list_apps(db: Session, f: AppFilters, offset: int, limit: int) -> tuple[list[App], int]:
    stmt = apply_app_filters(select(App), f)
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    if f.sort == "updated":
        stmt = stmt.order_by(App.updated_at.desc(), App.name)
    elif f.sort == "relevance" and f.q:
        stmt = stmt.order_by(func.ts_rank_cd(App.search_tsv, _tsquery(f.q)).desc(), App.name)
    else:
        stmt = stmt.order_by(func.lower(App.name))
    return list(db.scalars(stmt.offset(offset).limit(limit)).all()), total


@dataclass
class FacetCounts:
    lifecycle: list[tuple[str, int]]
    license_type: list[tuple[str, int]]
    domain: list[tuple[str, int]]


def _matching_ids(f: AppFilters) -> Any:
    return apply_app_filters(select(App.id), f).scalar_subquery()


def facet_counts(db: Session, f: AppFilters) -> FacetCounts:
    """Counts per facet value; each facet ignores its own selection so other values stay visible."""

    def grouped(value: Any, app_id: Any, ids: Any, stmt: Select[Any]) -> list[tuple[str, int]]:
        count = func.count(func.distinct(app_id))
        stmt = stmt.add_columns(value, count).where(app_id.in_(ids), value.is_not(None))
        rows = db.execute(stmt.group_by(value).order_by(count.desc(), value)).all()
        return [(str(getattr(v, "value", v)), n) for v, n in rows]

    by_domain = select().select_from(Tag).join(app_tags, app_tags.c.tag_id == Tag.id)
    return FacetCounts(
        lifecycle=grouped(App.lifecycle_status, App.id, _matching_ids(replace(f, statuses=[])), select()),
        license_type=grouped(App.license_type, App.id, _matching_ids(replace(f, license_types=[])), select()),
        domain=grouped(
            Tag.name,
            app_tags.c.app_id,
            _matching_ids(replace(f, domains=[])),
            by_domain.where(Tag.category == TagCategory.domain),
        ),
    )


def _is_indexed(embedded_at: Any, model: str | None, active_model: str) -> bool:
    return embedded_at is not None and model == active_model


def embedding_status(app: App, active_model: str) -> str:
    ok = _is_indexed(app.embedded_at, app.embedding_model, active_model) and all(
        _is_indexed(c.embedded_at, c.embedding_model, active_model) for c in app.capabilities
    )
    return "indexed" if ok else "pending"


def _tags_by_category(app: App) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {"tags": [], "tech_stack": [], "domains": []}
    reverse = {v: k for k, v in TAG_FIELDS.items()}
    for t in app.tags:
        out[reverse[t.category]].append(t.name)
    return out


def owners_first(links: Sequence[AppMaintainer]) -> list[AppMaintainer]:
    return sorted(links, key=lambda x: (x.role != MaintainerRole.owner, x.maintainer.name))


def to_app_out(app: App, active_model: str) -> AppOut:
    session = object_session(app)
    return AppOut(
        id=app.id,
        slug=app.slug,
        name=app.name,
        short_description=app.short_description,
        description=app.description,
        lifecycle_status=app.lifecycle_status,
        license=app.license,
        license_type=app.license_type,
        vendor=app.vendor,
        version=app.version,
        homepage_url=app.homepage_url,
        repo_url=app.repo_url,
        docs_url=app.docs_url,
        links=[LinkItem.model_validate(link) for link in app.links or []],
        extra=app.extra or {},
        **_tags_by_category(app),
        maintainers=[
            AppMaintainerOut(
                id=link.maintainer.id,
                name=link.maintainer.name,
                email=link.maintainer.email,
                kind=link.maintainer.kind,
                org_unit=link.maintainer.org_unit,
                url=link.maintainer.url,
                role=link.role,
            )
            for link in owners_first(app.maintainer_links)
        ],
        capabilities=[
            CapabilityOut(
                id=c.id,
                kind=c.kind,
                text=c.text,
                details=c.details,
                position=c.position,
                indexed=_is_indexed(c.embedded_at, c.embedding_model, active_model),
            )
            for c in app.capabilities
        ],
        embedding_status=embedding_status(app, active_model),
        interfaces=[to_summary(i, app.id) for i in touching_interfaces(session, app.id)] if session else [],
        created_at=app.created_at,
        updated_at=app.updated_at,
    )


def to_list_item(app: App, active_model: str) -> AppListItem:
    return AppListItem(
        id=app.id,
        slug=app.slug,
        name=app.name,
        short_description=app.short_description,
        lifecycle_status=app.lifecycle_status,
        license_type=app.license_type,
        vendor=app.vendor,
        **_tags_by_category(app),
        maintainers=sorted({link.maintainer.name for link in app.maintainer_links}),
        capability_count=len(app.capabilities),
        embedding_status=embedding_status(app, active_model),
        updated_at=app.updated_at,
    )
