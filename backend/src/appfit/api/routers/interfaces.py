import uuid
from http import HTTPStatus

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from appfit.api.deps import active_model_id
from appfit.api.openapi import errors
from appfit.auth.deps import require_admin, require_editor, require_viewer
from appfit.db.engine import get_db
from appfit.models import InterfaceStatus, InterfaceType, LifecycleStatus, User
from appfit.schemas.interface import ExternalSystemIn, ExternalSystemOut, InterfaceIn, InterfaceOut, Landscape
from appfit.services import interfaces as svc

router = APIRouter(tags=["interfaces"])


@router.get("/interfaces", response_model=list[InterfaceOut])
def list_interfaces(
    app: str | None = Query(default=None, description="Slug of an app at either end"),
    system: str | None = Query(default=None, description="Name of an external system at either end"),
    type_: list[InterfaceType] = Query(default=[], alias="type"),
    status_: list[InterfaceStatus] = Query(default=[], alias="status"),
    db: Session = Depends(get_db),
    model_id: str = Depends(active_model_id),
    _: User = Depends(require_viewer),
) -> list[InterfaceOut]:
    """Interfaces, optionally only those touching one app or external system."""
    found = svc.list_interfaces(db, app_slug=app, system=system, types=type_, statuses=status_)
    return [svc.to_interface_out(i, model_id) for i in found]


@router.get("/interfaces/{interface_id}", response_model=InterfaceOut)
def get_interface(
    interface_id: uuid.UUID,
    db: Session = Depends(get_db),
    model_id: str = Depends(active_model_id),
    _: User = Depends(require_viewer),
) -> InterfaceOut:
    """One interface with both endpoints."""
    return svc.to_interface_out(svc.get_interface(db, interface_id), model_id)


@router.post(
    "/interfaces",
    response_model=InterfaceOut,
    status_code=status.HTTP_201_CREATED,
    responses=errors(HTTPStatus.CONFLICT),
)
def create_interface(
    body: InterfaceIn,
    db: Session = Depends(get_db),
    model_id: str = Depends(active_model_id),
    user: User = Depends(require_editor),
) -> InterfaceOut:
    """Document an interface; an external system named as an endpoint is created when new."""
    iface = svc.create_interface(db, body, user.id)
    db.commit()
    return svc.to_interface_out(iface, model_id)


@router.put("/interfaces/{interface_id}", response_model=InterfaceOut, responses=errors(HTTPStatus.CONFLICT))
def update_interface(
    interface_id: uuid.UUID,
    body: InterfaceIn,
    db: Session = Depends(get_db),
    model_id: str = Depends(active_model_id),
    user: User = Depends(require_editor),
) -> InterfaceOut:
    """Replace all fields of an interface."""
    iface = svc.get_interface(db, interface_id)
    svc.update_interface(db, iface, body, user.id)
    db.commit()
    db.refresh(iface)
    return svc.to_interface_out(iface, model_id)


@router.delete("/interfaces/{interface_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_interface(interface_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_editor)) -> None:
    """Delete an interface."""
    svc.delete_interface(db, svc.get_interface(db, interface_id))
    db.commit()


@router.get("/external-systems", response_model=list[ExternalSystemOut])
def list_external_systems(db: Session = Depends(get_db), _: User = Depends(require_viewer)) -> list[ExternalSystemOut]:
    """External systems with the number of interfaces using each."""
    return svc.list_systems(db)


@router.post(
    "/external-systems",
    response_model=ExternalSystemOut,
    status_code=status.HTTP_201_CREATED,
    responses=errors(HTTPStatus.CONFLICT),
)
def create_external_system(
    body: ExternalSystemIn, db: Session = Depends(get_db), _: User = Depends(require_editor)
) -> ExternalSystemOut:
    """Register an external system (outside the catalog)."""
    system = svc.save_system(db, body)
    db.commit()
    return svc.to_system_out(system, 0)


@router.put("/external-systems/{system_id}", response_model=ExternalSystemOut, responses=errors(HTTPStatus.CONFLICT))
def update_external_system(
    system_id: uuid.UUID, body: ExternalSystemIn, db: Session = Depends(get_db), _: User = Depends(require_editor)
) -> ExternalSystemOut:
    """Rename or describe an external system; interface texts are re-indexed."""
    system = svc.save_system(db, body, svc.get_system(db, system_id))
    db.commit()
    return svc.to_system_out(system, svc.system_interface_count(db, system.id))


@router.delete(
    "/external-systems/{system_id}", status_code=status.HTTP_204_NO_CONTENT, responses=errors(HTTPStatus.CONFLICT)
)
def delete_external_system(
    system_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> None:
    """Delete an external system that no interface uses."""
    svc.delete_system(db, svc.get_system(db, system_id))
    db.commit()


@router.get("/landscape", response_model=Landscape)
def get_landscape(
    domain: list[str] = Query(default=[]),
    lifecycle: list[LifecycleStatus] = Query(default=[], description="Default: every state except retired"),
    type_: list[InterfaceType] = Query(default=[], alias="type"),
    status_: list[InterfaceStatus] = Query(default=[], alias="status"),
    include_systems: bool = True,
    include_unconnected: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
) -> Landscape:
    """Nodes (apps, external systems) and edges (interfaces) for the landscape graph."""
    filters = svc.LandscapeFilters(
        domains=domain,
        lifecycle=lifecycle,
        types=type_,
        statuses=status_,
        include_systems=include_systems,
        include_unconnected=include_unconnected,
    )
    return svc.landscape(db, filters)
