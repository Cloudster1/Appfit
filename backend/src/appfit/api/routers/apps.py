from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from appfit.api.deps import active_model_id
from appfit.auth.deps import require_admin, require_editor, require_viewer
from appfit.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, SCORE_DECIMALS, SIMILAR_APPS_LIMIT
from appfit.db.engine import get_db
from appfit.models import App, LicenseType, LifecycleStatus, User
from appfit.schemas.app import AppFacets, AppIn, AppListItem, AppOut, FacetValue, SimilarApp
from appfit.schemas.common import Page
from appfit.services import apps as svc
from appfit.services.errors import NotFoundError
from appfit.services.search.retrieval import similar_apps

router = APIRouter(prefix="/apps", tags=["apps"])


def _get_or_404(db: Session, slug: str) -> App:
    app = svc.get_app(db, slug)
    if app is None:
        raise NotFoundError(f"App {slug!r} not found")
    return app


def app_filters(
    q: str | None = None,
    tags: list[str] = Query(default=[]),
    status_: list[LifecycleStatus] = Query(default=[], alias="status"),
    license_type: list[LicenseType] = Query(default=[]),
    domain: list[str] = Query(default=[], description="Any of these domains"),
    maintainer: str | None = None,
    sort: Literal["name", "updated", "relevance"] = "name",
) -> svc.AppFilters:
    return svc.AppFilters(
        q=q,
        tags=tags,
        statuses=status_,
        license_types=license_type,
        domains=domain,
        maintainer=maintainer,
        sort=sort,
    )


@router.get("", response_model=Page[AppListItem])
def list_apps(
    filters: svc.AppFilters = Depends(app_filters),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    model_id: str = Depends(active_model_id),
    _: User = Depends(require_viewer),
) -> Page[AppListItem]:
    items, total = svc.list_apps(db, filters, offset=(page - 1) * size, limit=size)
    return Page(items=[svc.to_list_item(a, model_id) for a in items], total=total, page=page, size=size)


@router.get("/facets", response_model=AppFacets)
def app_facets(
    filters: svc.AppFilters = Depends(app_filters),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
) -> AppFacets:
    counts = svc.facet_counts(db, filters)

    def values(rows: list[tuple[str, int]]) -> list[FacetValue]:
        return [FacetValue(value=v, count=n) for v, n in rows]

    return AppFacets(
        lifecycle=values(counts.lifecycle),
        license_type=values(counts.license_type),
        domain=values(counts.domain),
    )


@router.get("/{slug}", response_model=AppOut)
def get_app(
    slug: str,
    db: Session = Depends(get_db),
    model_id: str = Depends(active_model_id),
    _: User = Depends(require_viewer),
) -> AppOut:
    return svc.to_app_out(_get_or_404(db, slug), model_id)


@router.post("", response_model=AppOut, status_code=status.HTTP_201_CREATED)
def create_app(
    body: AppIn,
    db: Session = Depends(get_db),
    model_id: str = Depends(active_model_id),
    user: User = Depends(require_editor),
) -> AppOut:
    app, _ = svc.create_app(db, body.as_full_update(), user.id)
    db.commit()
    return svc.to_app_out(app, model_id)


@router.put("/{slug}", response_model=AppOut)
def replace_app(
    slug: str,
    body: AppIn,
    db: Session = Depends(get_db),
    model_id: str = Depends(active_model_id),
    user: User = Depends(require_editor),
) -> AppOut:
    app = _get_or_404(db, slug)
    svc.update_app(db, app, body.as_full_update(), user.id)
    db.commit()
    db.refresh(app)
    return svc.to_app_out(app, model_id)


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
def delete_app(slug: str, db: Session = Depends(get_db), _: User = Depends(require_admin)) -> None:
    svc.delete_app(db, _get_or_404(db, slug))
    db.commit()


@router.get("/{slug}/similar", response_model=list[SimilarApp])
def get_similar(
    slug: str,
    limit: int = Query(default=SIMILAR_APPS_LIMIT, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    model_id: str = Depends(active_model_id),
    _: User = Depends(require_viewer),
) -> list[SimilarApp]:
    app = _get_or_404(db, slug)
    return [
        SimilarApp(
            slug=a.slug, name=a.name, short_description=a.short_description, similarity=round(sim, SCORE_DECIMALS)
        )
        for a, sim in similar_apps(db, app.id, model_id, limit)
    ]
