import uuid
from dataclasses import dataclass, field

import numpy as np

from appfit.config import (
    LABEL_PARTIAL_COVERAGE,
    LABEL_STRONG_COVERAGE,
    MUST_GAP_PENALTY,
    PARTIAL_CREDIT,
    SCORE_WEIGHT_COVERAGE,
    SCORE_WEIGHT_RETRIEVAL,
    SCORE_WEIGHT_SOFT,
    SUMMARY_CAP_MARGIN,
)
from appfit.schemas.interface import InterfaceSummary
from appfit.services.search.thresholds import Thresholds

COVERED, PARTIAL, GAP = "covered", "partial", "gap"
FLAG_MISSING_MUST = "missing_must_have"
FLAG_NOT_INDEXED = "not_indexed"
_EPS = 1e-6


@dataclass
class Req:
    idx: int
    text: str
    weight: float
    must: bool
    stems: dict[str, set[str]]


@dataclass
class CandCap:
    """A matchable statement of a candidate: a capability, or an interface seen from this app."""

    id: uuid.UUID
    kind: str
    text: str
    stems: dict[str, set[str]]
    interface: InterfaceSummary | None = None
    capped: bool = False  # planned interfaces can reach "partial" at most


@dataclass
class Candidate:
    app_id: uuid.UUID
    summary_vec: np.ndarray | None
    caps: list[CandCap]
    cap_matrix: np.ndarray | None  # (n_caps, dim), rows aligned with caps
    rrf: float
    ranks: dict[str, int | None] = field(default_factory=dict)


@dataclass
class ReqEvidence:
    req_idx: int
    status: str
    score: float
    similarity: float
    via: str
    capability: CandCap | None = None
    keyword_hits: list[str] = field(default_factory=list)


@dataclass
class AppScore:
    candidate: Candidate
    final: float
    coverage: float
    soft: float
    retrieval: float
    label: str
    flags: list[str]
    evidence: list[ReqEvidence]


def status_for(score: float, th: Thresholds) -> str:
    if score >= th.covered:
        return COVERED
    if score >= th.partial:
        return PARTIAL
    return GAP


def keyword_hits(req: Req, cap: CandCap) -> list[str]:
    shared = req.stems.keys() & cap.stems.keys()
    return sorted({tok for s in shared for tok in req.stems[s]})


def score_candidate(
    req_vecs: np.ndarray,
    reqs: list[Req],
    cand: Candidate,
    th: Thresholds,
    lexical_bonus: float,
    rrf_max: float,
) -> AppScore:
    """Per requirement: best capability (plus lexical bonus) vs. capped summary similarity."""
    m = len(reqs)
    neg_inf = np.full(m, -np.inf, dtype=np.float32)

    cap_best, cap_raw, best_idx = neg_inf, neg_inf, np.zeros(m, dtype=int)
    if cand.caps and cand.cap_matrix is not None:
        sims = req_vecs @ cand.cap_matrix.T
        lex = np.array(
            [[1.0 if r.stems.keys() & c.stems.keys() else 0.0 for c in cand.caps] for r in reqs],
            dtype=np.float32,
        )
        adjusted = sims + lexical_bonus * lex
        # Same cap as for the description: a planned interface is a promise, not a capability.
        limits = np.array(
            [th.covered - SUMMARY_CAP_MARGIN if c.capped else np.inf for c in cand.caps], dtype=np.float32
        )
        adjusted = np.minimum(adjusted, limits)
        best_idx = adjusted.argmax(axis=1)
        rows = np.arange(m)
        cap_best, cap_raw = adjusted[rows, best_idx], sims[rows, best_idx]

    summary_raw = req_vecs @ cand.summary_vec if cand.summary_vec is not None else neg_inf
    summary_capped = np.minimum(summary_raw, th.covered - SUMMARY_CAP_MARGIN)

    evidence: list[ReqEvidence] = []
    for i, req in enumerate(reqs):
        if cap_best[i] == -np.inf and summary_capped[i] == -np.inf:
            evidence.append(ReqEvidence(req.idx, GAP, 0.0, 0.0, "none"))
        elif cap_best[i] >= summary_capped[i]:
            cap = cand.caps[int(best_idx[i])]
            score = float(cap_best[i])
            via = "interface" if cap.interface is not None else "capability"
            evidence.append(
                ReqEvidence(req.idx, status_for(score, th), score, float(cap_raw[i]), via, cap, keyword_hits(req, cap))
            )
        else:
            score = float(summary_capped[i])
            evidence.append(ReqEvidence(req.idx, status_for(score, th), score, float(summary_raw[i]), "summary"))

    total_w = sum(r.weight for r in reqs) or 1.0
    credit = {COVERED: 1.0, PARTIAL: PARTIAL_CREDIT, GAP: 0.0}
    coverage = sum(r.weight * credit[e.status] for r, e in zip(reqs, evidence, strict=True)) / total_w
    span = max(th.covered - th.floor, _EPS)
    soft = (
        sum(
            r.weight * float(np.clip((e.score - th.floor) / span, 0.0, 1.0))
            for r, e in zip(reqs, evidence, strict=True)
        )
        / total_w
    )
    retrieval = min(cand.rrf / rrf_max, 1.0) if rrf_max > 0 else 0.0
    final = SCORE_WEIGHT_COVERAGE * coverage + SCORE_WEIGHT_SOFT * soft + SCORE_WEIGHT_RETRIEVAL * retrieval

    flags: list[str] = []
    must_gap = any(r.must and e.status == GAP for r, e in zip(reqs, evidence, strict=True))
    if must_gap:
        final *= MUST_GAP_PENALTY
        flags.append(FLAG_MISSING_MUST)
    if cand.summary_vec is None and not cand.caps:
        flags.append(FLAG_NOT_INDEXED)

    if coverage >= LABEL_STRONG_COVERAGE and not must_gap:
        label = "strong"
    elif coverage >= LABEL_PARTIAL_COVERAGE:
        label = "partial"
    else:
        label = "weak"
    return AppScore(cand, final, coverage, soft, retrieval, label, flags, evidence)


def rank_scores(scores: list[AppScore]) -> list[AppScore]:
    return sorted(scores, key=lambda s: (-s.final, -s.coverage, -s.candidate.rrf))


def is_no_match(ranked: list[AppScore], th: Thresholds) -> bool:
    if not ranked:
        return True
    top = ranked[0]
    best_coverage = max(s.coverage for s in ranked)
    return top.final < th.nomatch or best_coverage < th.min_top_coverage


def catalog_gaps(scores: list[AppScore], reqs: list[Req]) -> list[int]:
    """Requirements that are a gap for every scored candidate."""
    if not scores:
        return [r.idx for r in reqs]
    return [r.idx for pos, r in enumerate(reqs) if all(s.evidence[pos].status == GAP for s in scores)]


def has_evidence(score: AppScore) -> bool:
    return score.coverage > 0 or score.soft > 0
