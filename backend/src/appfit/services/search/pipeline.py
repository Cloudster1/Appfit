import time
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass

import numpy as np
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from appfit.config import (
    CAPABILITY_TOP_K_PER_REQ,
    FTS_TOP_K,
    MAX_COMBINATIONS,
    MIN_RELATIVE_SCORE,
    NO_MATCH_CLOSEST,
    RETRIEVAL_LISTS,
    RRF_DECIMALS,
    SCORE_DECIMALS,
    SUMMARY_TOP_K,
    Settings,
)
from appfit.ml.embedder import Embedder
from appfit.models import App, Interface, InterfaceStatus, SearchLog, TagCategory
from appfit.schemas.interface import Landscape, LandscapeEdge, LandscapeNode
from appfit.schemas.search import (
    Combination,
    Evidence,
    MatchedCapability,
    ParsedRequirement,
    ResultApp,
    SearchRequest,
    SearchResponse,
    SearchResult,
    Signals,
    ThresholdsOut,
)
from appfit.services.apps import owners_first
from appfit.services.interfaces import app_node_id, node_id, system_node_id
from appfit.services.search.combine import Link, find_combinations
from appfit.services.search.fusion import max_rrf, reciprocal_rank_fusion
from appfit.services.search.retrieval import (
    FilterSpec,
    capability_ranking,
    configure_vector_search,
    filter_conditions,
    fts_ranking,
    load_candidates,
    summary_ranking,
)
from appfit.services.search.scoring import (
    AppScore,
    Candidate,
    Req,
    catalog_gaps,
    has_evidence,
    is_no_match,
    rank_scores,
    score_candidate,
)
from appfit.services.search.splitter import SplitRequirement, split_requirements
from appfit.services.search.thresholds import Thresholds, thresholds_for
from appfit.text import normalize_ws, stem_map

_MS = 1000


def parse_requirements(text: str) -> list[ParsedRequirement]:
    split = split_requirements(text)
    if not split and text.strip():
        split = [SplitRequirement(normalize_ws(text), None)]
    return [ParsedRequirement(idx=i, text=r.text, priority=r.priority, weight=r.weight) for i, r in enumerate(split)]


def _requirements(req: SearchRequest) -> list[ParsedRequirement]:
    if req.requirements:
        items = [SplitRequirement(normalize_ws(r.text), r.priority) for r in req.requirements if r.text.strip()]
        return [
            ParsedRequirement(idx=i, text=r.text, priority=r.priority, weight=r.weight) for i, r in enumerate(items)
        ]
    return parse_requirements(req.text or "")


def _result_app(app: App) -> ResultApp:
    return ResultApp(
        id=app.id,
        slug=app.slug,
        name=app.name,
        short_description=app.short_description,
        lifecycle_status=app.lifecycle_status,
        vendor=app.vendor,
        # General tags and domains can share a name; list each once.
        tags=list(dict.fromkeys(t.name for t in app.tags if t.category != TagCategory.tech)),
        tech_stack=[t.name for t in app.tags if t.category == TagCategory.tech],
        domains=[t.name for t in app.tags if t.category == TagCategory.domain],
        maintainers=list(dict.fromkeys(link.maintainer.name for link in owners_first(app.maintainer_links))),
    )


def _to_result(score: AppScore, app: App, recommended: bool) -> SearchResult:
    ranks = score.candidate.ranks
    return SearchResult(
        app=_result_app(app),
        final=round(score.final, SCORE_DECIMALS),
        coverage=round(score.coverage, SCORE_DECIMALS),
        soft=round(score.soft, SCORE_DECIMALS),
        label=score.label,
        flags=score.flags,
        signals=Signals(
            rrf=round(score.candidate.rrf, RRF_DECIMALS),
            summary_rank=ranks.get("summary"),
            capability_rank=ranks.get("capability"),
            fts_rank=ranks.get("fts"),
        ),
        evidence=[
            Evidence(
                req_idx=e.req_idx,
                status=e.status,
                score=round(e.score, SCORE_DECIMALS),
                similarity=round(e.similarity, SCORE_DECIMALS),
                via=e.via,
                capability=(
                    MatchedCapability(id=e.capability.id, kind=e.capability.kind, text=e.capability.text)
                    if e.capability and e.capability.interface is None
                    else None
                ),
                interface=e.capability.interface if e.capability else None,
                keyword_hits=e.keyword_hits,
            )
            for e in score.evidence
        ],
        recommended=recommended,
    )


@dataclass
class PreparedQuery:
    """Retrieval output that does not depend on thresholds; scoring can be re-run cheaply on it."""

    parsed: list[ParsedRequirement]
    reqs: list[Req]
    req_vecs: np.ndarray
    candidates: list[Candidate]


@dataclass
class ScoredQuery:
    scores: list[AppScore]
    ranked: list[AppScore]
    no_match: bool
    shown: list[tuple[AppScore, bool]]


def prepare_query(db: Session, embedder: Embedder, settings: Settings, req: SearchRequest) -> PreparedQuery:
    parsed = _requirements(req)
    query_text = normalize_ws(req.text) if req.text and req.text.strip() else " ".join(r.text for r in parsed)
    model_id = embedder.model_id

    vecs = embedder.embed_queries([query_text] + [r.text for r in parsed])
    query_vec, req_vecs = vecs[0], vecs[1:]

    spec = FilterSpec(
        lifecycle=req.filters.lifecycle,
        tags=req.filters.tags,
        license_types=req.filters.license_types,
        domains=req.filters.domains,
        maintainer=req.filters.maintainer,
    )
    conds = filter_conditions(spec)
    configure_vector_search(db)
    lists = {
        "summary": summary_ranking(db, query_vec, conds, model_id, SUMMARY_TOP_K),
        "capability": capability_ranking(
            db, req_vecs, [r.weight for r in parsed], conds, model_id, CAPABILITY_TOP_K_PER_REQ
        ),
        "fts": fts_ranking(db, query_text, conds, FTS_TOP_K),
    }
    rrf = reciprocal_rank_fusion(list(lists.values()), settings.rrf_k)
    ranks: dict[uuid.UUID, dict[str, int | None]] = {}
    for name, ranked in lists.items():
        for pos, app_id in enumerate(ranked, start=1):
            ranks.setdefault(app_id, {"summary": None, "capability": None, "fts": None})[name] = pos
    candidate_ids = sorted(rrf, key=lambda a: -rrf[a])[: settings.match_candidates]
    reqs = [
        Req(idx=r.idx, text=r.text, weight=r.weight, must=r.priority == "must", stems=stem_map(r.text)) for r in parsed
    ]
    return PreparedQuery(parsed, reqs, req_vecs, load_candidates(db, candidate_ids, model_id, rrf, ranks))


def score_prepared(prep: PreparedQuery, th: Thresholds, settings: Settings, limit: int) -> ScoredQuery:
    rrf_ceiling = max_rrf(RETRIEVAL_LISTS, settings.rrf_k)
    scores = [
        score_candidate(prep.req_vecs, prep.reqs, c, th, settings.lexical_bonus, rrf_ceiling) for c in prep.candidates
    ]
    ranked = rank_scores(scores)
    no_match = is_no_match(ranked, th)
    if no_match:
        shown = [(s, False) for s in ranked[:NO_MATCH_CLOSEST]]
    else:
        cutoff = ranked[0].final * MIN_RELATIVE_SCORE
        shown = [(s, True) for s in ranked if has_evidence(s) and s.final >= cutoff][:limit]
    return ScoredQuery(scores, ranked, no_match, shown)


def _connections(db: Session, results: list[SearchResult]) -> tuple[Landscape, list[Link]]:
    """Interfaces among the result apps, plus external systems that two or more of them use."""
    by_id = {r.app.id: r.app for r in results}
    ifaces = db.scalars(
        select(Interface).where(
            or_(Interface.from_app_id.in_(list(by_id)), Interface.to_app_id.in_(list(by_id))),
            Interface.status != InterfaceStatus.deprecated,
        )
    ).unique()
    direct: list[Interface] = []
    via_system: dict[uuid.UUID, list[Interface]] = defaultdict(list)
    for iface in ifaces:
        ends = [iface.from_app_id, iface.to_app_id]
        if all(e in by_id for e in ends):
            direct.append(iface)
        elif any(e in by_id for e in ends):
            system_id = iface.from_system_id or iface.to_system_id
            if system_id is not None:
                via_system[system_id].append(iface)
    shared = {sid: items for sid, items in via_system.items() if len({i.from_app_id or i.to_app_id for i in items}) > 1}
    edges = [
        LandscapeEdge(
            id=i.id,
            source=node_id(i.from_app_id, i.from_system_id),
            target=node_id(i.to_app_id, i.to_system_id),
            name=i.name,
            interface_type=i.interface_type,
            status=i.status,
            bidirectional=i.bidirectional,
            data_objects=list(i.data_objects),
            frequency=i.frequency,
        )
        for i in direct + [i for items in shared.values() for i in items]
    ]
    degree = Counter(n for e in edges for n in (e.source, e.target))
    nodes = [
        LandscapeNode(
            id=app_node_id(a.id),
            kind="app",
            name=a.name,
            slug=a.slug,
            lifecycle_status=a.lifecycle_status,
            domains=a.domains,
            degree=degree[app_node_id(a.id)],
        )
        for a in by_id.values()
    ]
    for items in shared.values():
        system = items[0].from_system or items[0].to_system
        assert system is not None
        nodes.append(LandscapeNode(id=system_node_id(system.id), kind="system", name=system.name, degree=len(items)))
    links = [
        Link(by_id[i.from_app_id].slug, by_id[i.to_app_id].slug, i.id, i.name, i.status.value)
        for i in direct
        if i.from_app_id is not None and i.to_app_id is not None
    ]
    return Landscape(nodes=nodes, edges=edges), links


def _combinations(results: list[SearchResult], parsed: list[ParsedRequirement], links: list[Link]) -> list[Combination]:
    covered = {r.app.slug: {e.req_idx for e in r.evidence if e.status == "covered"} for r in results}
    finals = {r.app.slug: r.final for r in results}
    pairs = find_combinations(covered, finals, links, {r.idx: r.weight for r in parsed}, MAX_COMBINATIONS)
    return [
        Combination(
            apps=list(p.apps),
            covered=sorted(p.covered),
            interface_id=p.link.interface_id,
            interface_name=p.link.interface_name,
            interface_status=InterfaceStatus(p.link.interface_status),
        )
        for p in pairs
    ]


def run_search(
    db: Session,
    embedder: Embedder,
    settings: Settings,
    req: SearchRequest,
    user_id: uuid.UUID | None,
) -> SearchResponse:
    started = time.perf_counter()
    th = thresholds_for(embedder.model_name, settings)
    prep = prepare_query(db, embedder, settings, req)
    parsed = prep.parsed
    scored = score_prepared(prep, th, settings, req.limit)
    no_match, shown = scored.no_match, scored.shown

    apps = {a.id: a for a in db.scalars(select(App).where(App.id.in_([s.candidate.app_id for s, _ in shown]))).all()}
    results = [_to_result(s, apps[s.candidate.app_id], rec) for s, rec in shown if s.candidate.app_id in apps]
    connections, links = _connections(db, results)
    duration_ms = int((time.perf_counter() - started) * _MS)

    log_id: uuid.UUID | None = None
    if settings.search_log_enabled:
        log = SearchLog(
            id=uuid.uuid4(),
            user_id=user_id,
            query_text=req.text or "\n".join(r.text for r in parsed),
            requirements=[r.model_dump() for r in parsed],
            filters=req.filters.model_dump(mode="json"),
            results=[{"slug": r.app.slug, "final": r.final, "coverage": r.coverage, "label": r.label} for r in results],
            no_match=no_match,
            embedding_model=embedder.model_id,
            duration_ms=duration_ms,
        )
        db.add(log)
        log_id = log.id

    return SearchResponse(
        status="no_match" if no_match else "ok",
        requirements=parsed,
        results=results,
        catalog_gaps=catalog_gaps(scored.scores, prep.reqs),
        connections=connections,
        combinations=_combinations(results, parsed, links),
        thresholds=ThresholdsOut(
            model=th.model,
            covered=th.covered,
            partial=th.partial,
            nomatch=th.nomatch,
            min_top_coverage=th.min_top_coverage,
        ),
        candidates_considered=len(prep.candidates),
        duration_ms=duration_ms,
        search_log_id=log_id,
    )
