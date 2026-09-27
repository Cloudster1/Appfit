from typing import Any

LIFECYCLE_ALIASES = {
    "aktiv": "active",
    "in betrieb": "active",
    "produktiv": "active",
    "live": "active",
    "production": "active",
    "idee": "idea",
    "geplant": "idea",
    "planned": "idea",
    "pilotphase": "pilot",
    "test": "pilot",
    "beta": "pilot",
    "abgekündigt": "deprecated",
    "veraltet": "deprecated",
    "auslaufend": "deprecated",
    "sunset": "deprecated",
    "stillgelegt": "retired",
    "abgeschaltet": "retired",
    "eingestellt": "retired",
    "decommissioned": "retired",
}
LICENSE_TYPE_ALIASES = {
    "open source": "oss",
    "opensource": "oss",
    "open-source": "oss",
    "foss": "oss",
    "kommerziell": "commercial",
    "proprietär": "commercial",
    "proprietary": "commercial",
    "lizenz": "commercial",
    "intern": "internal",
    "eigenentwicklung": "internal",
    "inhouse": "internal",
    "in-house": "internal",
    "sonstige": "other",
    "andere": "other",
}
MAINTAINER_ROLE_ALIASES = {
    "eigentümer": "owner",
    "verantwortlich": "owner",
    "product owner": "owner",
    "po": "owner",
    "betreuer": "maintainer",
    "entwickler": "maintainer",
    "developer": "maintainer",
    "kontakt": "contact",
    "ansprechpartner": "contact",
    "support": "contact",
}
CAPABILITY_KIND_ALIASES = {
    "fähigkeit": "capability",
    "funktion": "feature",
    "anforderung": "requirement",
    "merkmal": "feature",
}


def _norm(value: Any, aliases: dict[str, str]) -> Any:
    if isinstance(value, str):
        key = value.strip().lower()
        return aliases.get(key, key)
    return value


def normalize_aliases(data: dict[str, Any]) -> dict[str, Any]:
    """Case-insensitive enum values plus German aliases, applied before validation."""
    if "lifecycle_status" in data:
        data["lifecycle_status"] = _norm(data["lifecycle_status"], LIFECYCLE_ALIASES)
    if "license_type" in data:
        data["license_type"] = _norm(data["license_type"], LICENSE_TYPE_ALIASES)
    for m in data.get("maintainers") or []:
        if isinstance(m, dict) and "role" in m:
            m["role"] = _norm(m["role"], MAINTAINER_ROLE_ALIASES)
        if isinstance(m, dict) and isinstance(m.get("kind"), str):
            m["kind"] = m["kind"].strip().lower()
    for c in data.get("capabilities") or []:
        if isinstance(c, dict) and "kind" in c:
            c["kind"] = _norm(c["kind"], CAPABILITY_KIND_ALIASES)
    return data
