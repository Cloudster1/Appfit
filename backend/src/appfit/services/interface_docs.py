"""Interface texts and views shared by the app service, the interface service and search.

Kept free of imports from services.apps so both can use it without a cycle."""

import uuid
from typing import Literal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from appfit.models import App, ExternalSystem, Interface, InterfaceFrequency, InterfaceStatus, InterfaceType
from appfit.schemas.interface import Direction, EndpointOut, InterfaceSummary
from appfit.text import content_hash, normalize_ws

Side = Literal["from", "to"]

TYPE_LABELS: dict[InterfaceType, str] = {
    InterfaceType.rest_api: "REST API",
    InterfaceType.soap: "SOAP web service",
    InterfaceType.file_transfer: "file transfer",
    InterfaceType.database: "database access",
    InterfaceType.messaging: "messaging and events",
    InterfaceType.sso: "single sign-on and identity",
    InterfaceType.ui_embedding: "UI embedding",
    InterfaceType.other: "other integration",
}
FREQUENCY_LABELS: dict[InterfaceFrequency, str] = {
    InterfaceFrequency.realtime: "real-time",
    InterfaceFrequency.batch: "batch",
    InterfaceFrequency.on_demand: "on demand",
}


def endpoint_name(app: App | None, system: ExternalSystem | None) -> str:
    if app is not None:
        return app.name
    return system.name if system is not None else ""


def interface_document(iface: Interface) -> str:
    """Neutral sentence shown as evidence text; its words also give the keyword bonus in scoring."""
    source = endpoint_name(iface.from_app, iface.from_system)
    target = endpoint_name(iface.to_app, iface.to_system)
    link = "and" if iface.bidirectional else "to"
    parts = [f"Interface {source} {link} {target}: {iface.name}."]
    if iface.data_objects:
        parts.append("Data: " + ", ".join(iface.data_objects) + ".")
    how = TYPE_LABELS[iface.interface_type]
    if iface.frequency is not None:
        how += ", " + FREQUENCY_LABELS[iface.frequency]
    parts.append(how + ".")
    return normalize_ws(" ".join(parts))


def side_text(iface: Interface, side: Side) -> str | None:
    """What is embedded for the app on one side: short, and naming the other side.

    Measured on eval/pair_labels.yaml, this matches requirements such as "Integration mit SAP S/4HANA"
    clearly better than the full neutral sentence. None when that side is an external system."""
    if side == "from":
        own, other = iface.from_app, endpoint_name(iface.to_app, iface.to_system)
    else:
        own, other = iface.to_app, endpoint_name(iface.from_app, iface.from_system)
    return f"{iface.name} - Integration mit {other}" if own is not None else None


def embedded_texts(iface: Interface) -> str:
    return "\n".join(t or "" for t in (side_text(iface, "from"), side_text(iface, "to")))


def refresh_interface_hash(iface: Interface) -> bool:
    """Reset the embeddings when the embedded texts changed; True if they did."""
    new_hash = content_hash(embedded_texts(iface))
    if iface.content_hash == new_hash:
        return False
    iface.content_hash = new_hash
    iface.from_embedding = None
    iface.to_embedding = None
    iface.embedded_at = None
    return True


def touching_interfaces(db: Session, app_id: uuid.UUID) -> list[Interface]:
    stmt = select(Interface).where(or_(Interface.from_app_id == app_id, Interface.to_app_id == app_id))
    return list(db.scalars(stmt.order_by(Interface.name)).unique().all())


def endpoint_out(app: App | None, system: ExternalSystem | None) -> EndpointOut:
    if app is not None:
        return EndpointOut(kind="app", id=app.id, name=app.name, slug=app.slug, lifecycle_status=app.lifecycle_status)
    assert system is not None
    return EndpointOut(kind="system", id=system.id, name=system.name)


def direction_for(iface: Interface, app_id: uuid.UUID) -> Direction:
    if iface.bidirectional:
        return "both"
    return "outgoing" if iface.from_app_id == app_id else "incoming"


def counterpart(iface: Interface, app_id: uuid.UUID) -> EndpointOut:
    if iface.from_app_id == app_id:
        return endpoint_out(iface.to_app, iface.to_system)
    return endpoint_out(iface.from_app, iface.from_system)


def to_summary(iface: Interface, app_id: uuid.UUID) -> InterfaceSummary:
    return InterfaceSummary(
        id=iface.id,
        name=iface.name,
        direction=direction_for(iface, app_id),
        counterpart=counterpart(iface, app_id),
        interface_type=iface.interface_type,
        data_objects=list(iface.data_objects),
        frequency=iface.frequency,
        status=iface.status,
    )


def counts_as_evidence(status: InterfaceStatus) -> bool:
    return status != InterfaceStatus.deprecated
