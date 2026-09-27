from typing import Any

from fastapi.testclient import TestClient

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_NO_CONTENT = 204


def app_payload(name: str, capabilities: list[str] | None = None, **extra: Any) -> dict[str, Any]:
    return {
        "name": name,
        "short_description": extra.pop("short_description", f"{name} short description"),
        "capabilities": [{"text": t} for t in capabilities or []],
        **extra,
    }


def create_app(client: TestClient, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    resp = client.post("/api/apps", json=payload, headers=headers)
    assert resp.status_code == HTTP_CREATED, resp.text
    data: dict[str, Any] = resp.json()
    return data


def iface_payload(source: str, target: str, name: str, **extra: Any) -> dict[str, Any]:
    """Interface body; an endpoint written as "system:Name" is an external system, else an app slug."""

    def ref(value: str) -> dict[str, str]:
        return {"system": value.removeprefix("system:")} if value.startswith("system:") else {"app": value}

    return {"from": ref(source), "to": ref(target), "name": name, **extra}


def create_iface(client: TestClient, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    resp = client.post("/api/interfaces", json=payload, headers=headers)
    assert resp.status_code == HTTP_CREATED, resp.text
    data: dict[str, Any] = resp.json()
    return data


SAMPLE_CATALOG = [
    app_payload(
        "Invoice Hub",
        [
            "OCR extraction of invoice data from PDF",
            "Multi-level approval workflow for invoices",
            "Export of booked invoices to SAP FI",
            "E-invoicing with XRechnung and ZUGFeRD",
        ],
        description="Processes incoming supplier invoices end to end.",
        tags=["finance"],
        tech_stack=["java"],
        domains=["accounting"],
    ),
    app_payload(
        "Travel Desk",
        [
            "Booking of flights and hotels",
            "Travel expense reports with receipt upload",
            "Approval of travel requests by managers",
        ],
        tags=["hr"],
        domains=["travel"],
    ),
    app_payload(
        "Doc Vault",
        [
            "Document archive with full text search",
            "Retention policies for GDPR compliant deletion",
            "Versioning of documents",
        ],
        tags=["documents"],
        tech_stack=["python"],
    ),
    app_payload(
        "Old Mailer",
        ["Sending newsletters by email"],
        lifecycle_status="retired",
    ),
]
