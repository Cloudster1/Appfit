import pytest

from appfit.evaluation import _dcg, _prf, pair_report, sweep_similarity
from appfit.services.search.thresholds import Thresholds

TH = Thresholds(model="t", covered=0.7, partial=0.5, nomatch=0.3, min_top_coverage=0.34)


def test_prf() -> None:
    scored = [(0.9, True), (0.8, False), (0.4, True)]
    precision, recall, f1 = _prf(scored, 0.75)
    assert precision == pytest.approx(0.5)
    assert recall == pytest.approx(0.5)
    assert f1 == pytest.approx(0.5)


def test_dcg_discounts_by_rank() -> None:
    assert _dcg([2.0, 1.0]) > _dcg([1.0, 2.0])


def test_pair_report_confusion() -> None:
    report = pair_report([(0.9, "covered"), (0.6, "partial"), (0.2, "none"), (0.75, "partial")], TH)
    assert report["confusion (label -> predicted)"] == {
        "covered": {"covered": 1},
        "partial": {"partial": 1, "covered": 1},
        "none": {"none": 1},
    }
    assert report["covered_precision"] == pytest.approx(0.5)


def test_sweep_separates_well_ordered_labels() -> None:
    scores = [(0.9, "covered"), (0.85, "covered"), (0.65, "partial"), (0.62, "partial"), (0.45, "none"), (0.4, "none")]
    t_cov, t_part = sweep_similarity(scores)
    assert 0.65 < t_cov <= 0.85
    assert 0.45 < t_part <= 0.62
