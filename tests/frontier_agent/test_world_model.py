from dataclasses import replace
from fractions import Fraction as F
from chronus.agent._contracts import digest
from tests.frontier_agent.conftest import H
from chronus.agent.world_model import (
    WorldModel,
    Fact,
    FactState,
    EvidenceQuality,
    AdjudicationPolicy,
    adjudicate_contradiction,
)


def quality(score, groups=("g1", "g2")):
    return EvidenceQuality(groups, *((score,) * 7), (H, "b" * 64))


def test_confidence_alone_never_supersedes(ledger):
    m = WorldModel(ledger)
    old = Fact("old", "p", "old", H, F(1), 1, 1, None)
    new = replace(old, id="new", value="new")
    m.add_fact(old, now=1, verified=True)
    m.add_fact(new, now=2, verified=True)
    assert all(f.state == FactState.CONTESTED for f in m.facts)
    policy = AdjudicationPolicy((1,) * 7, F(1, 10), F(1, 2), 2)
    assert (
        m.resolve_fact_conflict("new", "old", quality(F(1)), quality(F(0)), policy, now=3)
        == "SUPERSEDE"
    )
    assert {f.id: f.state for f in m.facts} == {
        "old": FactState.SUPERSEDED,
        "new": FactState.ACTIVE,
    }
    assert (
        adjudicate_contradiction(quality(F(1), ("same", "same")), quality(F(0)), policy)
        == "DEFER_TO_EXPERIMENT"
    )


def test_transitive_staleness(ledger):
    m = WorldModel(ledger)
    for f in (
        Fact("root", "a", "v", H, F(1), 1, 1, 2),
        Fact("middle", "b", "v", H, F(1), 1, 1, None, dependencies=("root",)),
        Fact("leaf", "c", "v", H, F(1), 1, 1, None, dependencies=("middle",)),
    ):
        m.add_fact(f, now=1, verified=True)
    m.refresh_stale_facts(now=3)
    assert all(f.state == FactState.STALE for f in m.facts)


def test_a1_uncalibrated_weights_do_not_override_partial_order():
    # Very recent but strictly less direct evidence cannot buy supersession
    # with a hand-selected recency weight.
    new = replace(quality(F(1)), directness=F(0))
    old = replace(quality(F(0)), directness=F(1))
    policy = AdjudicationPolicy((0, 100, 0, 0, 0, 0, 0), F(0), F(1, 2), 2)
    assert adjudicate_contradiction(new, old, policy) != "SUPERSEDE"


def test_a1_missing_reference_corpus_cannot_activate_weighted_scoring():
    from chronus.agent.world_model import CalibrationLineage

    policy = AdjudicationPolicy((1,) * 7, F(0), F(1, 2), 2)
    lineage = CalibrationLineage(
        199,
        H,
        "unit-cross-validation",
        digest(policy.weights),
        F(1),
        (F(1),) * 7,
        ((F(0), F(1)),) * 7,
        0,
        1000,
        "unit",
    )
    assert not lineage.admitted(policy, now=1, verify_signature=lambda *_: True)
