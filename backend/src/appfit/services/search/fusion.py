from collections.abc import Hashable, Sequence


def reciprocal_rank_fusion[K: Hashable](lists: Sequence[Sequence[K]], k: int) -> dict[K, float]:
    """Sum of 1 / (k + rank) over every ranked list (rank starts at 1)."""
    scores: dict[K, float] = {}
    for ranked in lists:
        for rank, key in enumerate(ranked, start=1):
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
    return scores


def max_rrf(n_lists: int, k: int) -> float:
    return n_lists / (k + 1)
