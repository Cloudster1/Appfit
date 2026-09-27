from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from appfit.api.deps import active_model_id
from appfit.auth.deps import require_viewer
from appfit.config import (
    CAPABILITY_ATOMIC_WARN_LEN,
    MAX_REQUIREMENTS,
    PRIORITY_WEIGHTS,
)
from appfit.ml.embedder import expected_model_name
from appfit.models import (
    CapabilityKind,
    InterfaceFrequency,
    InterfaceStatus,
    InterfaceType,
    LicenseType,
    LifecycleStatus,
    MaintainerKind,
    MaintainerRole,
    Role,
    TagCategory,
    User,
)
from appfit.schemas.search import ThresholdsOut
from appfit.services.search.thresholds import thresholds_for

router = APIRouter(prefix="/meta", tags=["meta"])


class SearchConfigOut(BaseModel):
    model_id: str
    thresholds: ThresholdsOut
    priority_weights: dict[str, float]
    max_requirements: int
    capability_atomic_warn_len: int


@router.get("/enums")
def list_enums(_: User = Depends(require_viewer)) -> dict[str, list[str]]:
    """Allowed values of every enum in the API."""
    return {
        "lifecycle_status": [e.value for e in LifecycleStatus],
        "license_type": [e.value for e in LicenseType],
        "capability_kind": [e.value for e in CapabilityKind],
        "tag_category": [e.value for e in TagCategory],
        "maintainer_kind": [e.value for e in MaintainerKind],
        "maintainer_role": [e.value for e in MaintainerRole],
        "role": [e.value for e in Role],
        "interface_type": [e.value for e in InterfaceType],
        "interface_frequency": [e.value for e in InterfaceFrequency],
        "interface_status": [e.value for e in InterfaceStatus],
    }


@router.get("/search-config", response_model=SearchConfigOut)
def get_search_config(
    request: Request,
    model_id: str = Depends(active_model_id),
    _: User = Depends(require_viewer),
) -> SearchConfigOut:
    """Active model, score thresholds and requirement limits for clients."""
    settings = request.app.state.settings
    embedder = request.app.state.embedder
    model_name = embedder.model_name if embedder is not None else expected_model_name(settings)
    th = thresholds_for(model_name, settings)
    return SearchConfigOut(
        model_id=model_id,
        thresholds=ThresholdsOut(
            model=th.model,
            covered=th.covered,
            partial=th.partial,
            nomatch=th.nomatch,
            min_top_coverage=th.min_top_coverage,
        ),
        priority_weights=PRIORITY_WEIGHTS,
        max_requirements=MAX_REQUIREMENTS,
        capability_atomic_warn_len=CAPABILITY_ATOMIC_WARN_LEN,
    )
