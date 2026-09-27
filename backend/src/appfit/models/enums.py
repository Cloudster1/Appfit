from enum import StrEnum


class Role(StrEnum):
    viewer = "viewer"
    editor = "editor"
    admin = "admin"

    @property
    def rank(self) -> int:
        return {Role.viewer: 1, Role.editor: 2, Role.admin: 3}[self]


class LifecycleStatus(StrEnum):
    idea = "idea"
    pilot = "pilot"
    active = "active"
    deprecated = "deprecated"
    retired = "retired"


class LicenseType(StrEnum):
    oss = "oss"
    commercial = "commercial"
    internal = "internal"
    other = "other"


class CapabilityKind(StrEnum):
    capability = "capability"
    requirement = "requirement"
    feature = "feature"


class TagCategory(StrEnum):
    general = "general"
    tech = "tech"
    domain = "domain"


class MaintainerKind(StrEnum):
    person = "person"
    team = "team"


class MaintainerRole(StrEnum):
    owner = "owner"
    maintainer = "maintainer"
    contact = "contact"


class InterfaceType(StrEnum):
    rest_api = "rest_api"
    soap = "soap"
    file_transfer = "file_transfer"
    database = "database"
    messaging = "messaging"
    sso = "sso"
    ui_embedding = "ui_embedding"
    other = "other"


class InterfaceFrequency(StrEnum):
    realtime = "realtime"
    batch = "batch"
    on_demand = "on_demand"


class InterfaceStatus(StrEnum):
    planned = "planned"
    active = "active"
    deprecated = "deprecated"
