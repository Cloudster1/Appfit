import uuid
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from appfit.config import MAX_REQUIREMENTS, MAX_SEARCH_LIMIT, MAX_SEARCH_TEXT_LEN, SEARCH_DEFAULT_LIMIT
from appfit.models import CapabilityKind, InterfaceStatus, LicenseType, LifecycleStatus
from appfit.schemas.interface import InterfaceSummary, Landscape
from appfit.schemas.types import NOT_BLANK_PATTERN

Priority = Literal["must", "should", "could"]
ReqStatus = Literal["covered", "partial", "gap"]
AppLabel = Literal["strong", "partial", "weak"]


class RequirementIn(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_SEARCH_TEXT_LEN, pattern=NOT_BLANK_PATTERN)
    priority: Priority | None = None


class ParsedRequirement(BaseModel):
    idx: int
    text: str
    priority: Priority | None
    weight: float


class ParseRequest(BaseModel):
    text: str = Field(max_length=MAX_SEARCH_TEXT_LEN)


class ParseResponse(BaseModel):
    requirements: list[ParsedRequirement]


class SearchFilters(BaseModel):
    lifecycle: list[LifecycleStatus] | None = Field(
        default=None, description="Allowed lifecycle states; default excludes 'retired'."
    )
    tags: list[str] = []
    license_types: list[LicenseType] = []
    domains: list[str] = Field(default=[], description="Any of these domains")
    maintainer: str | None = None


class SearchRequest(BaseModel):
    """Give `text` (split into requirements) or a `requirements` list with at least one non-blank item."""

    text: str | None = Field(default=None, max_length=MAX_SEARCH_TEXT_LEN)
    requirements: list[RequirementIn] | None = Field(default=None, max_length=MAX_REQUIREMENTS)
    filters: SearchFilters = SearchFilters()
    limit: int = Field(default=SEARCH_DEFAULT_LIMIT, ge=1, le=MAX_SEARCH_LIMIT)

    @model_validator(mode="after")
    def _need_input(self) -> "SearchRequest":
        has_text = bool(self.text and self.text.strip())
        has_reqs = bool(self.requirements and any(r.text.strip() for r in self.requirements))
        if not (has_text or has_reqs):
            raise ValueError("Provide 'text' or at least one requirement")
        return self


class MatchedCapability(BaseModel):
    id: uuid.UUID
    kind: CapabilityKind
    text: str


class Evidence(BaseModel):
    req_idx: int
    status: ReqStatus
    score: float
    similarity: float
    via: Literal["capability", "interface", "summary", "none"]
    capability: MatchedCapability | None = None
    interface: InterfaceSummary | None = None
    keyword_hits: list[str] = []


class Signals(BaseModel):
    rrf: float
    summary_rank: int | None
    capability_rank: int | None
    fts_rank: int | None


class ResultApp(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    short_description: str
    lifecycle_status: LifecycleStatus
    vendor: str | None
    tags: list[str]
    tech_stack: list[str]
    domains: list[str] = []
    maintainers: list[str] = Field(default=[], description="Names, owners first")


class SearchResult(BaseModel):
    app: ResultApp
    final: float
    coverage: float
    soft: float
    label: AppLabel
    flags: list[str]
    signals: Signals
    evidence: list[Evidence]
    recommended: bool = True


class ThresholdsOut(BaseModel):
    model: str
    covered: float
    partial: float
    nomatch: float
    min_top_coverage: float


class Combination(BaseModel):
    """Two connected result apps that together cover more requirements than either alone."""

    apps: list[str] = Field(description="Slugs of the two apps")
    covered: list[int] = Field(description="Requirement indexes covered by at least one of them")
    interface_id: uuid.UUID
    interface_name: str
    interface_status: InterfaceStatus


class SearchResponse(BaseModel):
    status: Literal["ok", "no_match"]
    requirements: list[ParsedRequirement]
    results: list[SearchResult]
    catalog_gaps: list[int]
    connections: Landscape = Field(
        default=Landscape(nodes=[], edges=[]),
        description="Interfaces between the result apps, and external systems two or more of them share",
    )
    combinations: list[Combination] = []
    thresholds: ThresholdsOut
    candidates_considered: int
    duration_ms: int
    search_log_id: uuid.UUID | None


class FeedbackIn(BaseModel):
    rating: Literal["up", "down"]
    expected_app_slug: str | None = None
    comment: str | None = Field(default=None, max_length=MAX_SEARCH_TEXT_LEN)
