import uuid

import numpy as np

from appfit.models import InterfaceStatus, InterfaceType
from appfit.schemas.interface import EndpointOut, InterfaceSummary
from appfit.services.search.combine import Link, find_combinations
from appfit.services.search.scoring import CandCap, score_candidate

from .test_scoring import E0, TH, candidate, cap, req, vec_with_cos


def iface_cap(status: InterfaceStatus = InterfaceStatus.active) -> CandCap:
    summary = InterfaceSummary(
        id=uuid.uuid4(),
        name="Rechnungen an SAP",
        direction="outgoing",
        counterpart=EndpointOut(kind="system", id=uuid.uuid4(), name="SAP S/4HANA"),
        interface_type=InterfaceType.rest_api,
        data_objects=["invoices"],
        frequency=None,
        status=status,
    )
    text = "Interface Belegfix to SAP S/4HANA: Rechnungen an SAP."
    return CandCap(uuid.uuid4(), "interface", text, {}, interface=summary, capped=status == InterfaceStatus.planned)


def score(c: CandCap, cos: float):
    reqs = [req(0, "Integration mit SAP S/4HANA")]
    return score_candidate(E0[None, :], reqs, candidate([(c, vec_with_cos(cos))]), TH, 0.0, 1.0).evidence[0]


def test_active_interface_covers_a_requirement_and_names_itself() -> None:
    c = iface_cap()
    ev = score(c, 0.80)
    assert (ev.status, ev.via) == ("covered", "interface")
    assert ev.capability is c and ev.capability.interface is not None


def test_planned_interface_reaches_partial_at_most() -> None:
    ev = score(iface_cap(InterfaceStatus.planned), 0.95)
    assert (ev.status, ev.via) == ("partial", "interface")
    assert ev.score < TH.covered
    assert ev.similarity > 0.9  # the raw similarity stays visible


def test_capability_beats_capped_planned_interface() -> None:
    reqs = [req(0, "Integration mit SAP")]
    caps = [(iface_cap(InterfaceStatus.planned), vec_with_cos(0.95)), (cap("SAP export"), vec_with_cos(0.70))]
    ev = score_candidate(E0[None, :], reqs, candidate(caps), TH, 0.0, 1.0).evidence[0]
    assert (ev.status, ev.via) == ("covered", "capability")


def test_combinations_need_a_link_and_must_beat_both_apps() -> None:
    link = Link("belegfix", "finanzbuch", uuid.uuid4(), "Buchungsstapel", "active")
    covered = {"belegfix": {0, 1}, "finanzbuch": {2}, "traveldesk": {0, 1, 2}}
    finals = {"belegfix": 0.8, "finanzbuch": 0.6, "traveldesk": 0.7}
    weights = {0: 1.0, 1: 1.0, 2: 1.0}

    pairs = find_combinations(covered, finals, [link], weights, limit=3)
    assert [(p.apps, sorted(p.covered)) for p in pairs] == [(("belegfix", "finanzbuch"), [0, 1, 2])]

    # No gain over the better app alone: no combination.
    assert find_combinations({"belegfix": {0, 1}, "finanzbuch": {1}}, finals, [link], weights, limit=3) == []
    # Apps that are not both in the results are ignored.
    assert find_combinations({"belegfix": {0}}, finals, [link], weights, limit=3) == []


def test_combinations_rank_by_weighted_coverage_and_respect_the_limit() -> None:
    links = [
        Link("a", "b", uuid.uuid4(), "ab", "active"),
        Link("a", "c", uuid.uuid4(), "ac", "planned"),
        Link("b", "a", uuid.uuid4(), "ba", "active"),  # second link between a and b is not a new pair
    ]
    covered = {"a": {0}, "b": {1}, "c": {2}}
    weights = {0: 1.0, 1: 0.3, 2: 1.0}
    pairs = find_combinations(covered, {"a": 0.5, "b": 0.5, "c": 0.5}, links, weights, limit=5)
    assert [p.link.interface_name for p in pairs] == ["ac", "ab"]
    assert len(find_combinations(covered, {"a": 0.5, "b": 0.5, "c": 0.5}, links, weights, limit=1)) == 1
    assert np.isclose(sum(weights[i] for i in pairs[0].covered), 2.0)
