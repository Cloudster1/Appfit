"""Pairs of connected result apps that cover more requirements together than either alone."""

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class Link:
    a: str
    b: str
    interface_id: uuid.UUID
    interface_name: str
    interface_status: str


@dataclass(frozen=True)
class Pair:
    apps: tuple[str, str]
    covered: frozenset[int]
    link: Link


def find_combinations(
    covered: dict[str, set[int]],
    finals: dict[str, float],
    links: list[Link],
    weights: dict[int, float],
    limit: int,
) -> list[Pair]:
    """Best pairs by weighted coverage of the union; a pair must beat both apps on their own."""

    def weight(idxs: set[int] | frozenset[int]) -> float:
        return sum(weights.get(i, 0.0) for i in idxs)

    best: dict[frozenset[str], Pair] = {}
    for link in links:
        if link.a not in covered or link.b not in covered:
            continue
        union = frozenset(covered[link.a] | covered[link.b])
        if weight(union) <= max(weight(covered[link.a]), weight(covered[link.b])):
            continue
        key = frozenset((link.a, link.b))
        if key not in best:  # the first link between two apps names the pair
            best[key] = Pair((link.a, link.b), union, link)
    ranked = sorted(
        best.values(),
        key=lambda p: (-weight(p.covered), -(finals[p.apps[0]] + finals[p.apps[1]]), p.apps),
    )
    return ranked[:limit]
