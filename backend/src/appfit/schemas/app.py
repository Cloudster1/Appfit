import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, field_validator

from appfit.config import (
    CAPABILITY_DETAILS_MAX_LEN,
    CAPABILITY_TEXT_MAX_LEN,
    NAME_MAX_LEN,
    SHORT_DESCRIPTION_MAX_LEN,
    SHORT_TEXT_MAX_LEN,
)
from appfit.models import (
    CapabilityKind,
    LicenseType,
    LifecycleStatus,
    MaintainerKind,
    MaintainerRole,
    TagCategory,
)
from appfit.schemas.common import ORMModel
from appfit.schemas.interface import InterfaceSummary
from appfit.schemas.types import NOT_BLANK_PATTERN, AppSlug, Email, Url
from appfit.text import normalize_ws

Name = Annotated[str, Field(min_length=1, max_length=NAME_MAX_LEN, pattern=NOT_BLANK_PATTERN)]
ShortText = Annotated[str, Field(max_length=SHORT_TEXT_MAX_LEN)]
TagName = Annotated[str, Field(min_length=1, max_length=SHORT_TEXT_MAX_LEN, pattern=NOT_BLANK_PATTERN)]
EmbeddingStatus = Literal["indexed", "pending"]


class LinkItem(BaseModel):
    label: ShortText
    url: Url


class CapabilityIn(BaseModel):
    id: uuid.UUID | None = None
    kind: CapabilityKind = CapabilityKind.capability
    text: str = Field(min_length=1, max_length=CAPABILITY_TEXT_MAX_LEN, pattern=NOT_BLANK_PATTERN)
    details: str | None = Field(default=None, max_length=CAPABILITY_DETAILS_MAX_LEN)

    @field_validator("text")
    @classmethod
    def _clean_text(cls, v: str) -> str:
        v = normalize_ws(v)
        if not v:
            raise ValueError("must not be blank")
        return v


class MaintainerRef(BaseModel):
    """Reference to a maintainer: by id, else matched by email, else by name (created when missing)."""

    id: uuid.UUID | None = None
    name: Name | None = None
    email: Email | None = None
    kind: MaintainerKind = MaintainerKind.person
    org_unit: ShortText | None = None
    role: MaintainerRole = MaintainerRole.maintainer

    @field_validator("name")
    @classmethod
    def _clean_name(cls, v: str | None) -> str | None:
        return normalize_ws(v) if v else v


def _clean_tags(values: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for v in values:
        v = normalize_ws(v).lower()
        if v:
            seen.setdefault(v, None)
    return list(seen)


class AppFields(BaseModel):
    """All editable app fields; `None` means "not given" in partial updates."""

    slug: AppSlug | None = None
    name: Name | None = None
    short_description: str | None = Field(default=None, max_length=SHORT_DESCRIPTION_MAX_LEN)
    description: str | None = None
    lifecycle_status: LifecycleStatus | None = None
    license: ShortText | None = None
    license_type: LicenseType | None = None
    vendor: Name | None = None
    version: ShortText | None = None
    homepage_url: Url | None = None
    repo_url: Url | None = None
    docs_url: Url | None = None
    links: list[LinkItem] | None = None
    extra: dict[str, Any] | None = None
    tags: list[TagName] | None = None
    tech_stack: list[TagName] | None = None
    domains: list[TagName] | None = None
    maintainers: list[MaintainerRef] | None = None
    capabilities: list[CapabilityIn] | None = None

    @field_validator("tags", "tech_stack", "domains")
    @classmethod
    def _tags(cls, v: list[str] | None) -> list[str] | None:
        return _clean_tags(v) if v is not None else None


class AppIn(AppFields):
    """Create/replace payload: omitted fields fall back to defaults (full replace semantics)."""

    name: Name
    short_description: str = Field(default="", max_length=SHORT_DESCRIPTION_MAX_LEN)
    description: str = ""
    lifecycle_status: LifecycleStatus = LifecycleStatus.active
    links: list[LinkItem] = []
    extra: dict[str, Any] = {}
    tags: list[TagName] = []
    tech_stack: list[TagName] = []
    domains: list[TagName] = []
    maintainers: list[MaintainerRef] = []
    capabilities: list[CapabilityIn] = []

    def as_full_update(self) -> dict[str, Any]:
        data = {name: getattr(self, name) for name in AppFields.model_fields}
        if data["slug"] is None:
            del data["slug"]
        return data


class CapabilityOut(ORMModel):
    id: uuid.UUID
    kind: CapabilityKind
    text: str
    details: str | None
    position: int
    indexed: bool = False


class MaintainerOut(ORMModel):
    id: uuid.UUID
    name: str
    email: str | None
    kind: MaintainerKind
    org_unit: str | None
    url: str | None


class MaintainerIn(BaseModel):
    name: Name
    email: Email | None = None
    kind: MaintainerKind = MaintainerKind.person
    org_unit: ShortText | None = None
    url: Url | None = None


class AppMaintainerOut(MaintainerOut):
    role: MaintainerRole


class AppListItem(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    short_description: str
    lifecycle_status: LifecycleStatus
    license_type: LicenseType | None
    vendor: str | None
    tags: list[str]
    tech_stack: list[str]
    domains: list[str]
    maintainers: list[str]
    capability_count: int
    embedding_status: EmbeddingStatus
    updated_at: datetime


class FacetValue(BaseModel):
    value: str
    count: int


class AppFacets(BaseModel):
    lifecycle: list[FacetValue]
    license_type: list[FacetValue]
    domain: list[FacetValue]


class AppOut(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    short_description: str
    description: str
    lifecycle_status: LifecycleStatus
    license: str | None
    license_type: LicenseType | None
    vendor: str | None
    version: str | None
    homepage_url: str | None
    repo_url: str | None
    docs_url: str | None
    links: list[LinkItem]
    extra: dict[str, Any]
    tags: list[str]
    tech_stack: list[str]
    domains: list[str]
    maintainers: list[AppMaintainerOut]
    capabilities: list[CapabilityOut]
    embedding_status: EmbeddingStatus
    interfaces: list[InterfaceSummary] = []
    created_at: datetime
    updated_at: datetime


class SimilarApp(BaseModel):
    slug: str
    name: str
    short_description: str
    similarity: float


class TagOut(BaseModel):
    id: uuid.UUID
    name: str
    category: TagCategory
    app_count: int


class TagUpdate(BaseModel):
    name: TagName | None = None
    merge_into: uuid.UUID | None = None


class TagCreate(BaseModel):
    name: TagName
    category: TagCategory = TagCategory.general
