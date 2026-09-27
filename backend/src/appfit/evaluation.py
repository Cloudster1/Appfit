import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from appfit.config import (
    EVAL_COVERED_MIN_PRECISION,
    EVAL_NOMATCH_GRID,
    EVAL_SIMILARITY_GRID,
    EVAL_TOP_COVERAGE_GRID,
    RETRIEVAL_LISTS,
    SCORE_DECIMALS,
    SEARCH_DEFAULT_LIMIT,
    get_settings,
)
from appfit.db.engine import make_engine, make_session_factory
from appfit.ml.embedder import Embedder, build_embedder
from appfit.models import App
from appfit.schemas.search import SearchRequest
from appfit.services.search.fusion import max_rrf
from appfit.services.search.pipeline import PreparedQuery, prepare_query, score_prepared
from appfit.services.search.retrieval import load_candidates
from appfit.services.search.scoring import Req, score_candidate
from appfit.services.search.thresholds import Thresholds, thresholds_for
from appfit.text import stem_map
from appfit.worker import EmbeddingWorker

RECALL_KS = (1, 3, 5, 10)
NDCG_K = 10
COVERED, PARTIAL = "covered", "partial"


@dataclass
class LabelledQuery:
    id: str
    text: str
    relevant: dict[str, int]
    expect_no_match: bool
    prepared: PreparedQuery
    slugs: dict[Any, str]


def _dcg(gains: list[float]) -> float:
    return sum(g / math.log2(i + 2) for i, g in enumerate(gains))


def ranking_metrics(queries: list[LabelledQuery], th: Thresholds, settings: Any) -> dict[str, Any]:
    """Recall@k, MRR and nDCG@10 on queries with relevant apps; balanced accuracy of the no-match decision."""
    per_query = []
    recalls = {k: [] for k in RECALL_KS}  # type: dict[int, list[float]]
    mrr, ndcg = [], []
    tp = tn = fp = fn = 0
    for q in queries:
        scored = score_prepared(q.prepared, th, settings, SEARCH_DEFAULT_LIMIT)
        ranking = [q.slugs[s.candidate.app_id] for s in scored.ranked]
        if q.expect_no_match:
            tn, fp = tn + scored.no_match, fp + (not scored.no_match)
        else:
            tp, fn = tp + (not scored.no_match), fn + scored.no_match
            relevant = set(q.relevant)
            for k in RECALL_KS:
                recalls[k].append(len(relevant & set(ranking[:k])) / len(relevant))
            first = next((i for i, slug in enumerate(ranking) if slug in relevant), None)
            mrr.append(1.0 / (first + 1) if first is not None else 0.0)
            gains = [float(q.relevant.get(slug, 0)) for slug in ranking[:NDCG_K]]
            ideal = sorted(q.relevant.values(), reverse=True)[:NDCG_K]
            ndcg.append(_dcg(gains) / _dcg([float(g) for g in ideal]))
        per_query.append(
            {
                "id": q.id,
                "expect_no_match": q.expect_no_match,
                "predicted_no_match": scored.no_match,
                "top3": [f"{q.slugs[s.candidate.app_id]}:{round(s.final, SCORE_DECIMALS)}" for s in scored.ranked[:3]],
                "relevant": q.relevant,
            }
        )
    tpr = tp / (tp + fn) if tp + fn else 0.0
    tnr = tn / (tn + fp) if tn + fp else 0.0
    return {
        **{f"recall@{k}": round(float(np.mean(v)), SCORE_DECIMALS) for k, v in recalls.items() if v},
        "mrr": round(float(np.mean(mrr)), SCORE_DECIMALS) if mrr else None,
        f"ndcg@{NDCG_K}": round(float(np.mean(ndcg)), SCORE_DECIMALS) if ndcg else None,
        "no_match_balanced_accuracy": round((tpr + tnr) / 2, SCORE_DECIMALS),
        "no_match_confusion": {"match_ok": tp, "false_no_match": fn, "no_match_ok": tn, "false_match": fp},
        "queries": per_query,
    }


def pair_scores(
    db: Session, embedder: Embedder, pairs: list[dict[str, Any]], th: Thresholds, lexical_bonus: float
) -> list[tuple[float, str]]:
    """Adjusted evidence score of each labelled (requirement, app) pair."""
    slugs = {p["app"] for p in pairs}
    ids = {slug: id_ for id_, slug in db.execute(select(App.id, App.slug).where(App.slug.in_(slugs))).all()}
    candidates = {c.app_id: c for c in load_candidates(db, list(ids.values()), embedder.model_id, {}, {})}
    vecs = embedder.embed_queries([p["requirement"] for p in pairs])
    out = []
    for pair, vec in zip(pairs, vecs, strict=True):
        cand = candidates.get(ids.get(pair["app"]))  # type: ignore[arg-type]
        if cand is None:
            continue
        req = Req(idx=0, text=pair["requirement"], weight=1.0, must=False, stems=stem_map(pair["requirement"]))
        score = score_candidate(vec[None, :], [req], cand, th, lexical_bonus, 1.0)
        out.append((score.evidence[0].score, pair["label"]))
    return out


def _prf(scored: list[tuple[float, bool]], threshold: float) -> tuple[float, float, float]:
    tp = sum(1 for s, pos in scored if s >= threshold and pos)
    fp = sum(1 for s, pos in scored if s >= threshold and not pos)
    fn = sum(1 for s, pos in scored if s < threshold and pos)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def pair_report(scores: list[tuple[float, str]], th: Thresholds) -> dict[str, Any]:
    confusion: dict[str, dict[str, int]] = {}
    for s, label in scores:
        predicted = COVERED if s >= th.covered else PARTIAL if s >= th.partial else "none"
        confusion.setdefault(label, {}).setdefault(predicted, 0)
        confusion[label][predicted] += 1
    cov = _prf([(s, lab == COVERED) for s, lab in scores], th.covered)
    part = _prf([(s, lab in (COVERED, PARTIAL)) for s, lab in scores], th.partial)
    return {
        "confusion (label -> predicted)": confusion,
        "covered_precision": round(cov[0], SCORE_DECIMALS),
        "covered_recall": round(cov[1], SCORE_DECIMALS),
        "partial_or_better_precision": round(part[0], SCORE_DECIMALS),
        "partial_or_better_recall": round(part[1], SCORE_DECIMALS),
    }


def sweep_similarity(scores: list[tuple[float, str]]) -> tuple[float, float]:
    """T_cov: best F1 with covered precision >= target; T_part: best F1 for partial-or-better below T_cov."""
    grid = np.round(np.arange(*EVAL_SIMILARITY_GRID), 2)
    covered = [(s, lab == COVERED) for s, lab in scores]
    options = [(t, *_prf(covered, t)) for t in grid]
    eligible = [o for o in options if o[1] >= EVAL_COVERED_MIN_PRECISION] or options
    t_cov = max(eligible, key=lambda o: (o[3], o[1]))[0]
    partial = [(s, lab in (COVERED, PARTIAL)) for s, lab in scores]
    t_part = max(((t, *_prf(partial, t)) for t in grid if t < t_cov), key=lambda o: o[3])[0]
    return round(float(t_cov), 2), round(float(t_part), 2)


def sweep_no_match(queries: list[LabelledQuery], th: Thresholds, settings: Any) -> Thresholds:
    best, best_key = th, (-1.0, 0.0)
    for nomatch in np.arange(*EVAL_NOMATCH_GRID):
        for top_cov in np.arange(*EVAL_TOP_COVERAGE_GRID):
            cand = replace(th, nomatch=round(float(nomatch), 2), min_top_coverage=round(float(top_cov), 2))
            metrics = ranking_metrics(queries, cand, settings)
            # Ties go to the candidate closest to the current values, for stable recalibration.
            distance = abs(cand.nomatch - th.nomatch) + abs(cand.min_top_coverage - th.min_top_coverage)
            key = (metrics["no_match_balanced_accuracy"], -distance)
            if key > best_key:
                best, best_key = cand, key
    return best


def run_evaluation(queries_path: Path, pairs_path: Path, sweep: bool = False) -> dict[str, Any]:
    settings = get_settings()
    factory = make_session_factory(make_engine(settings.database_url))
    embedder = build_embedder(settings)
    worker = EmbeddingWorker(
        factory, embedder, settings.database_url, settings.embed_worker_batch_size, settings.embed_worker_poll_seconds
    )
    embedded_now = worker.run_once()
    th = thresholds_for(embedder.model_name, settings)

    raw_queries = yaml.safe_load(queries_path.read_text(encoding="utf-8"))["queries"]
    pairs = yaml.safe_load(pairs_path.read_text(encoding="utf-8"))["pairs"]
    with factory() as db:
        slugs = dict(db.execute(select(App.id, App.slug)).all())
        if not slugs:
            raise RuntimeError("The catalog is empty; run `appfit seed eval/seed_apps.json` first")
        queries = [
            LabelledQuery(
                id=q["id"],
                text=q["text"],
                relevant=q.get("relevant") or {},
                expect_no_match=bool(q.get("expect_no_match")),
                prepared=prepare_query(db, embedder, settings, SearchRequest(text=q["text"])),
                slugs=slugs,
            )
            for q in raw_queries
        ]
        scores = pair_scores(db, embedder, pairs, th, settings.lexical_bonus)
        db.rollback()

    result: dict[str, Any] = {
        "model": embedder.model_id,
        "embedded_before_eval": embedded_now,
        "queries": len(queries),
        "pairs": len(scores),
        "rrf_lists": RETRIEVAL_LISTS,
        "rrf_ceiling": round(max_rrf(RETRIEVAL_LISTS, settings.rrf_k), SCORE_DECIMALS),
        "current": {
            "thresholds": th.__dict__,
            "pairs": pair_report(scores, th),
            "ranking": ranking_metrics(queries, th, settings),
        },
    }
    if sweep:
        t_cov, t_part = sweep_similarity(scores)
        tuned = sweep_no_match(queries, replace(th, covered=t_cov, partial=t_part), settings)
        result["suggested"] = {
            "thresholds": tuned.__dict__,
            "pairs": pair_report(scores, tuned),
            "ranking": ranking_metrics(queries, tuned, settings),
            "thresholds_yaml": {
                embedder.model_name: {
                    "covered": tuned.covered,
                    "partial": tuned.partial,
                    "nomatch": tuned.nomatch,
                    "min_top_coverage": tuned.min_top_coverage,
                }
            },
        }
    return result
