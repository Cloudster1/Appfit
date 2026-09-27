import uuid

import numpy as np
import pytest

from appfit.services.search.fusion import max_rrf, reciprocal_rank_fusion
from appfit.services.search.scoring import (
    FLAG_MISSING_MUST,
    CandCap,
    Candidate,
    Req,
    catalog_gaps,
    is_no_match,
    rank_scores,
    score_candidate,
)
from appfit.services.search.thresholds import Thresholds
from appfit.text import stem_map

TH = Thresholds(model="test", covered=0.65, partial=0.52, nomatch=0.40, min_top_coverage=0.34)
DIM = 4


def unit(*xs: float) -> np.ndarray:
    v = np.array(xs, dtype=np.float32)
    return v / np.linalg.norm(v)


def vec_with_cos(cos: float) -> np.ndarray:
    """A unit vector with the given cosine to E0."""
    return np.array([cos, np.sqrt(1 - cos**2), 0, 0], dtype=np.float32)


def req(idx: int, text: str = "", weight: float = 1.0, must: bool = False) -> Req:
    return Req(idx=idx, text=text, weight=weight, must=must, stems=stem_map(text))


def cap(text: str) -> CandCap:
    return CandCap(id=uuid.uuid4(), kind="capability", text=text, stems=stem_map(text))


def candidate(caps: list[tuple[CandCap, np.ndarray]], summary: np.ndarray | None = None, rrf: float = 0.0):
    matrix = np.stack([v for _, v in caps]) if caps else None
    return Candidate(uuid.uuid4(), summary, [c for c, _ in caps], matrix, rrf)


E0 = unit(1, 0, 0, 0)
E2 = unit(0, 0, 1, 0)


def test_rrf_sums_reciprocal_ranks() -> None:
    scores = reciprocal_rank_fusion([["a", "b"], ["b", "c"]], k=60)
    assert scores["b"] == pytest.approx(1 / 62 + 1 / 61)
    assert scores["a"] == pytest.approx(1 / 61)
    assert max_rrf(3, 60) == pytest.approx(3 / 61)


@pytest.mark.parametrize(
    ("cos", "status"),
    [(0.70, "covered"), (0.651, "covered"), (0.649, "partial"), (0.521, "partial"), (0.519, "gap")],
)
def test_threshold_boundaries(cos: float, status: str) -> None:
    c = candidate([(cap("x"), vec_with_cos(cos))])
    s = score_candidate(np.stack([E0]), [req(0)], c, TH, lexical_bonus=0.0, rrf_max=1.0)
    assert s.evidence[0].status == status
    assert s.evidence[0].via == "capability"


def test_summary_can_only_make_a_requirement_partial() -> None:
    c = candidate([], summary=E0)
    s = score_candidate(np.stack([E0]), [req(0)], c, TH, lexical_bonus=0.0, rrf_max=1.0)
    ev = s.evidence[0]
    assert ev.via == "summary"
    assert ev.status == "partial"
    assert ev.similarity == pytest.approx(1.0)
    assert ev.score < TH.covered


def test_lexical_bonus_can_lift_partial_to_covered_and_reports_hits() -> None:
    c = candidate([(cap("Export invoices to SAP"), vec_with_cos(0.63))])
    reqs = [req(0, "SAP export required")]
    without = score_candidate(np.stack([E0]), reqs, c, TH, lexical_bonus=0.0, rrf_max=1.0)
    with_bonus = score_candidate(np.stack([E0]), reqs, c, TH, lexical_bonus=0.03, rrf_max=1.0)
    assert without.evidence[0].status == "partial"
    assert with_bonus.evidence[0].status == "covered"
    assert with_bonus.evidence[0].similarity == pytest.approx(0.63, abs=1e-5)
    assert set(with_bonus.evidence[0].keyword_hits) == {"export", "sap"}


def test_coverage_is_weighted_and_partial_counts_half() -> None:
    c = candidate([(cap("a"), E0)])
    reqs = [req(0, weight=1.0), req(1, weight=0.3)]
    s = score_candidate(np.stack([E0, E2]), reqs, c, TH, lexical_bonus=0.0, rrf_max=1.0)
    assert [e.status for e in s.evidence] == ["covered", "gap"]
    assert s.coverage == pytest.approx(1.0 / 1.3)


def test_missing_must_have_penalizes_and_flags() -> None:
    c = candidate([(cap("a"), E0)])
    base = score_candidate(np.stack([E0, E2]), [req(0), req(1)], c, TH, 0.0, 1.0)
    must = score_candidate(np.stack([E0, E2]), [req(0), req(1, must=True)], c, TH, 0.0, 1.0)
    assert FLAG_MISSING_MUST in must.flags
    assert must.final == pytest.approx(base.final * 0.75)
    assert must.label != "strong"


def test_labels_and_no_match() -> None:
    strong = score_candidate(np.stack([E0]), [req(0)], candidate([(cap("a"), E0)]), TH, 0.0, 1.0)
    weak = score_candidate(np.stack([E0]), [req(0)], candidate([(cap("b"), E2)]), TH, 0.0, 1.0)
    assert strong.label == "strong"
    assert weak.label == "weak"
    assert not is_no_match(rank_scores([weak, strong]), TH)
    assert is_no_match([weak], TH)
    assert is_no_match([], TH)


def test_catalog_gaps_are_requirements_no_candidate_covers() -> None:
    reqs = [req(0), req(1)]
    r = np.stack([E0, E2])
    a = score_candidate(r, reqs, candidate([(cap("a"), E0)]), TH, 0.0, 1.0)
    b = score_candidate(r, reqs, candidate([(cap("b"), vec_with_cos(0.6))]), TH, 0.0, 1.0)
    assert catalog_gaps([a, b], reqs) == [1]


def test_not_indexed_candidate_has_only_gaps() -> None:
    s = score_candidate(np.stack([E0]), [req(0)], candidate([]), TH, 0.0, 1.0)
    assert s.evidence[0].status == "gap"
    assert s.evidence[0].via == "none"
    assert "not_indexed" in s.flags
