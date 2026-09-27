import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from appfit.config import (
    INTERFACE_DESCRIPTION_MAX_LEN,
    INTERFACE_MAX_DATA_OBJECTS,
    NAME_MAX_LEN,
    SHORT_TEXT_MAX_LEN,
)
from appfit.models import InterfaceFrequency, InterfaceStatus, InterfaceType, LifecycleStatus
from appfit.schemas.types import Slug, Url
from appfit.text import normalize_ws

SystemName = Annotated[str, Field(min_length=1, max_length=NAME_MAX_LEN)]
EndpointKind = Literal["app", "system"]
Direction = Literal["outgoing", "incoming", "both"]


class EndpointRef(BaseModel):
    """One end of an interface: a catalog app by slug or an external system by name."""

    app: Slug | None = None
    system: SystemName | None = None

    @field_validator("system")
    @classmethod
    def _clean_system(cls, v: str | None) -> str | None:
        return normalize_ws(v) or None if v else None

    @model_validator(mode="after")
    def _exactly_one(self) -> "EndpointRef":
        if (self.app is None) == (self.system is None):
            raise ValueError("give either an app slug or a system name")
        return self


class InterfaceIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    source: EndpointRef = Field(alias="from")
    target: EndpointRef = Field(alias="to")
    name: str = Field(min_length=1, max_length=NAME_MAX_LEN)
    interface_type: InterfaceType = Field(default=InterfaceType.other, alias="type")
    data_objects: list[Annotated[str, Field(max_length=SHORT_TEXT_MAX_LEN)]] = Field(
        default=[], max_length=INTERFACE_MAX_DATA_OBJECTS
    )
    frequency: InterfaceFrequency | None = None
    status: InterfaceStatus = InterfaceStatus.active
    bidirectional: bool = False
    description: str = Field(default="", max_length=INTERFACE_DESCRIPTION_MAX_LEN)

    @field_validator("name")
    @classmethod
    def _clean_name(cls, v: str) -> str:
        v = normalize_ws(v)
        if not v:
            raise ValueError("must not be blank")
        return v

    @field_validator("data_objects")
    @classmethod
    def _clean_objects(cls, values: list[str]) -> list[str]:
        seen: dict[str, None] = {}
        for v in values:
            v = normalize_ws(v)
            if v and v.lower() not in {s.lower() for s in seen}:
                seen[v] = None
        return list(seen)

    @field_validator("description")
    @classmethod
    def _clean_description(cls, v: str) -> str:
        return v.strip()

    @model_validator(mode="after")
    def _valid_endpoints(self) -> "InterfaceIn":
        if self.source.app is None and self.target.app is None:
            raise ValueError("at least one side must be a catalog app")
        if self.source.app is not None and self.source.app == self.target.app:
            raise ValueError("an app cannot have an interface to itself")
        if self.source.system is not None and self.source.system.lower() == (self.target.system or "").lower():
            raise ValueError("both sides are the same system")
        return self


class EndpointOut(BaseModel):
    kind: EndpointKind
    id: uuid.UUID
    name: str
    slug: str | None = None
    lifecycle_status: LifecycleStatus | None = None


class InterfaceOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    id: uuid.UUID
    source: EndpointOut = Field(alias="from")
    target: EndpointOut = Field(alias="to")
    name: str
    interface_type: InterfaceType = Field(alias="type")
    data_objects: list[str]
    frequency: InterfaceFrequency | None
    status: InterfaceStatus
    bidirectional: bool
    description: str
    indexed: bool
    updated_at: datetime


class InterfaceSummary(BaseModel):
    """An interface as seen from one app: the other side and the direction of the data flow."""

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    id: uuid.UUID
    name: str
    direction: Direction
    counterpart: EndpointOut
    interface_type: InterfaceType = Field(alias="type")
    data_objects: list[str]
    frequency: InterfaceFrequency | None
    status: InterfaceStatus


class ExternalSystemIn(BaseModel):
    name: SystemName
    description: str = Field(default="", max_length=INTERFACE_DESCRIPTION_MAX_LEN)
    vendor: str | None = Field(default=None, max_length=NAME_MAX_LEN)
    url: Url | None = None

    @field_validator("name")
    @classmethod
    def _clean_name(cls, v: str) -> str:
        v = normalize_ws(v)
        if not v:
            raise ValueError("must not be blank")
        return v


class ExternalSystemOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    vendor: str | None
    url: str | None
    interface_count: int


class LandscapeNode(BaseModel):
    id: str
    kind: EndpointKind
    name: str
    slug: str | None = None
    lifecycle_status: LifecycleStatus | None = None
    domains: list[str] = []
    degree: int


class LandscapeEdge(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    id: uuid.UUID
    source: str
    target: str
    name: str
    interface_type: InterfaceType = Field(alias="type")
    status: InterfaceStatus
    bidirectional: bool
    data_objects: list[str]
    frequency: InterfaceFrequency | None


class Landscape(BaseModel):
    nodes: list[LandscapeNode]
    edges: list[LandscapeEdge]
