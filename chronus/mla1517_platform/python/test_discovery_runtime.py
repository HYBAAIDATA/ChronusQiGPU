"""The discovery worker: the Active Discovery Engine on a twin of the miner."""

from __future__ import annotations

import pytest

import discovery_runtime as dr
from chronus.mla1517.knowledge import KnowledgeFabric

EFFECTS = {"a": 0.1, "b": 0.0, "c": -0.1}
LEVERS = {name: name for name in EFFECTS}


def _planted_twin(levers, _state):
    effect = sum(EFFECTS[lever] for lever in levers)
    return effect + 0.5 * sum(1 for pair in zip(levers, levers[1:]) if pair == ("a", "b"))


def _lucas(n: int) -> int:
    a, b = 2, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def _world(fabric: KnowledgeFabric, rate: float = 90_000.0):
    return fabric.publish(
        "mining.world_model",
        "mining.world",
        {
            "routes": {
                "cpu_reference": {"hash_rate_hs": rate, "overhead_ms": 0.25, "method": "wall"},
                "opencl": {"hash_rate_hs": 5e8, "overhead_ms": None, "method": "direct"},
            },
            "invalidations_per_hour": 12.0,
        },
        evidence="measured",
    )


def test_a_replicated_interaction_is_published_bound_to_the_world_it_was_found_in():
    fabric = KnowledgeFabric()
    world = _world(fabric)
    summary = dr.run_campaign(fabric, cycles=40, seeds=5, twin=_planted_twin, levers=LEVERS)

    # The two levers that act, and the one interaction beyond their sum.
    assert sorted(summary["published"]) == [
        "discovery.policy.a",
        "discovery.policy.a∘b",
        "discovery.policy.c",
    ]
    assert summary["lever_effects"] == EFFECTS
    assert fabric.observe("discovery.policy.c").value["efficiency_change"] == pytest.approx(-0.1)
    finding = fabric.observe("discovery.policy.a∘b")
    assert finding.source == "discovery.engine" and finding.evidence == "simulated"
    assert finding.value["levers"] == ["a", "b"]
    assert finding.value["predicted_change"] == pytest.approx(0.1)  # additive: a + b
    assert finding.value["efficiency_change"] == pytest.approx(0.6)
    assert finding.value["twin"]["basis"] == "live world model"
    assert finding.depends_on == (world.fact_id,)

    campaign = fabric.observe("discovery.campaign")
    assert not fabric.stale(finding) and not fabric.stale(campaign)
    _world(fabric, rate=45_000.0)  # the miner learns something different
    assert fabric.stale(finding) and fabric.stale(campaign)


def test_on_the_measured_route_no_operating_lever_beats_the_learned_policy():
    # The learned window minimises o/(o+T) + lambda*T/2 at T = sqrt(2 o / lambda)
    # = sqrt(2 * 0.000246 s / (6 / 3600 s)) = 0.54 s: inside even the halved
    # 1 s envelope, far below a Lucas rung of the 3.0M ceiling and a 512K chunk.
    # Every lever is inert, so every paired difference is exactly zero.
    fabric = KnowledgeFabric()
    summary = dr.run_campaign(fabric, cycles=30, seconds=10.0, seeds=3)
    assert summary["discoveries"] == 0 and summary["published"] == []
    assert summary["lever_effects"] == {lever: 0.0 for lever in dr.LEVERS}
    assert summary["twin"]["basis"].startswith("declared")
    assert fabric.observe("discovery.campaign").depends_on == ()


def test_the_twin_is_built_from_the_fastest_fully_learned_route():
    fabric = KnowledgeFabric()
    world = _world(fabric)
    regime, basis = dr.twin_regime(world)
    # opencl is faster but its overhead is not yet separable from its rate.
    assert (regime.route, regime.hash_rate, regime.overhead_s) == (
        "cpu_reference",
        90_000.0,
        0.00025,
    )
    assert regime.invalidations_per_hour == 12.0 and regime.max_window == _lucas(31)
    assert basis["basis"] == "live world model" and world.fact_id[:12] in regime.evidence

    declared, basis = dr.twin_regime(None)
    assert declared.hash_rate == 88_288.0 and declared.max_window == _lucas(31)
    assert basis["basis"].startswith("declared")


def test_levers_compose_on_the_twin():
    twin = dr.PolicyTwin(dr.twin_regime(None)[0])
    regime, envelope = twin.configure(["envelope_half", "envelope_half"])
    assert envelope == 0.5
    regime, _ = twin.configure(["rung_down"])
    assert regime.max_window == _lucas(30) // 32 * 32  # one rung lower, whole lanes
    regime, envelope = twin.configure(["chunk_half", "envelope_double"])
    assert (regime.chunk_cap, envelope) == (1 << 19, 4.0)
    with pytest.raises(ValueError, match="unknown lever"):
        twin.configure(["overclock"])


def test_campaigns_follow_the_world_not_the_clock():
    every = dr.CAMPAIGN_EVERY_S
    assert dr.campaign_due("w1", False, None, 0.0)  # first start
    assert not dr.campaign_due("w1", False, "w1", 10 * every)  # nothing moved
    assert not dr.campaign_due("w2", False, "w1", every / 2)  # moved, too soon
    assert dr.campaign_due("w2", False, "w1", every)
    assert dr.campaign_due("w1", True, "w1", every)  # its findings decohered


def test_a_live_applicable_finding_enters_the_promotion_gate_and_a_widening_one_never_does():
    effects = {"envelope_half": 0.05, "rung_down": -0.05, "envelope_double": 0.2}

    def twin(levers, _state):
        return sum(effects[lever] for lever in levers)

    fabric = KnowledgeFabric()
    _world(fabric)
    summary = dr.run_campaign(fabric, cycles=30, seeds=5, twin=twin, levers={k: k for k in effects})
    assert "discovery.policy.envelope_double" in summary["published"]  # found, but...
    assert summary["promotion_candidates"] == [
        {"levers": ["envelope_half"], "verdict": "shadow"}
    ]  # ...only the tightening lever is a candidate
    candidate = fabric.observe("promotion.candidate")
    assert candidate.evidence == "simulated"
    assert candidate.value["wins"] == dr.TRIAL_SEEDS and candidate.value["p_value"] < 0.05
