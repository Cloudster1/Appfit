import uuid

import numpy as np

from appfit.config import MIN_RELATIVE_SCORE, Settings
from appfit.services.search.pipeline import PreparedQuery, score_prepared
from appfit.services.search.scoring import CandCap, Candidate, Req
from appfit.services.search.thresholds import Thresholds

TH = Thresholds(model="t", covered=0.65, partial=0.52, nomatch=0.2, min_top_coverage=0.2)
SETTINGS = Settings(_env_file=None, embedding_backend="fake")  # type: ignore[call-arg]
LIMIT = 10


def unit(cos: float) -> np.ndarray:
    return np.array([cos, np.sqrt(1 - cos**2), 0, 0], dtype=np.float32)


def candidate(*cos: float) -> Candidate:
    caps = [CandCap(uuid.uuid4(), "capability", f"cap {i}", {}) for i in range(len(cos))]
    return Candidate(uuid.uuid4(), None, caps, np.stack([unit(c) for c in cos]), rrf=0.0)


def test_long_tail_below_relative_cutoff_is_hidden() -> None:
    # Regression: generic capabilities (SSO, REST API) pulled many barely related apps into the results.
    reqs = [Req(i, f"req {i}", 1.0, False, {}) for i in range(2)]
    req_vecs = np.stack([np.array([1, 0, 0, 0], dtype=np.float32)] * 2)
    strong, medium, weak = candidate(0.9), candidate(0.6), candidate(0.53)
    prep = PreparedQuery(parsed=[], reqs=reqs, req_vecs=req_vecs, candidates=[weak, medium, strong])

    scored = score_prepared(prep, TH, SETTINGS, LIMIT)

    shown = [s.candidate for s, _ in scored.shown]
    top = scored.ranked[0].final
    assert shown[0] is strong
    assert all(s.final >= top * MIN_RELATIVE_SCORE for s, _ in scored.shown)
    assert weak not in shown
    assert len(scored.ranked) == 3  # hidden, not dropped: still used for catalog gaps and eval
