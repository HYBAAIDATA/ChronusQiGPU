"""The promotion gate: twin round, shadow round, and only tightening levers."""

from __future__ import annotations

import math

import pytest

from mla1517.mining.operating_policy import PolicyContext, PolicyDecision
from mla1517.mining.promotion import (
    ShadowTrial,
    apply_levers,
    applicable,
    judge,
    judge_twin,
    measured_valid_rate,
    sign_test,
)
from mla1517.mining.world_model import MiningWorldModel, RouteModel

ROUTE = "cpu_reference"


def _ctx(**overrides) -> PolicyContext:
    base = dict(
        route=ROUTE,
        lanes=32,
        max_window=1_000,
        legacy_window=192,
        legacy_lookahead=2,
        capacity=8,
        chunk_cap=1_000,
        max_window_seconds=2.0,
    )
    base.update(overrides)
    return PolicyContext(**base)


def _timed_world(elapsed: dict[int, float]) -> MiningWorldModel:
    world = MiningWorldModel()
    route = RouteModel(forgetting=1.0)
    for _ in range(4):
        for hashes, seconds in elapsed.items():
            route.observe(hashes, seconds, 0.0)
    world.routes[ROUTE] = route
    world.clean.prior_events = 0.0
    return world


def test_the_sign_test_is_exact():
    assert sign_test(6, 0) == 1 / 64
    assert sign_test(0, 0) == 1.0
    assert sign_test(7, 2) == pytest.approx(sum(math.comb(9, k) for k in (7, 8, 9)) / 512)


def test_six_straight_wins_promote_and_fewer_pairs_never_decide():
    assert judge(5, 0) == "undecided"  # 1/32 < 5%, but too few pairs
    assert judge(6, 0) == "promote"
    assert judge(0, 6) == "reject"
    assert judge(5, 3) == "undecided"


def test_the_twin_round_needs_paired_wins():
    assert judge_twin([0.01] * 8)["verdict"] == "shadow"
    record = judge_twin([0.01] * 4 + [-0.01] * 4)
    assert record["verdict"] == "rejected" and record["wins"] == record["losses"] == 4


def test_levers_only_tighten_the_operators_bounds():
    ctx = _ctx()
    assert apply_levers(ctx, ("envelope_half",)).max_window_seconds == 1.0
    assert apply_levers(ctx, ("rung_down",)).max_window == 832  # ladder [.., 832, 992]
    assert not applicable(["envelope_double"]) and not applicable(["chunk_half"])
    assert not applicable([])
    with pytest.raises(ValueError):
        apply_levers(ctx, ("envelope_double",))
    with pytest.raises(ValueError):
        ShadowTrial(("envelope_double",), MiningWorldModel())


def test_valid_rate_is_measured_or_nothing():
    world = _timed_world({64: 2**-12, 320: 2**-8, 992: 2**-7})
    assert measured_valid_rate(world, ROUTE, 64, 1_000) == 64 * 2**12
    assert measured_valid_rate(world, ROUTE, 96, 1_000) is None
    assert measured_valid_rate(world, "opencl_m32", 64, 1_000) is None


def _run(trial: ShadowTrial, champion_window: int, decisions: int) -> None:
    for _ in range(decisions):
        trial.observe(_ctx(), PolicyDecision(champion_window, 2, "model", "stub"))


def test_a_candidate_that_wins_in_shadow_is_promoted_and_then_applied():
    # 64 is by far the fastest measured size; the champion keeps choosing 992.
    # 64 at 131 kH/s is 3% better than 992 at 127 kH/s: small, but measured.
    world = _timed_world({64: 2**-11, 320: 2**-8, 512: 2**-8 + 2**-10, 992: 2**-7})
    trial = ShadowTrial(("envelope_half",), world, epoch=8)
    _run(trial, 992, 5 * 8)
    assert trial.status == "shadow" and trial.wins == 5 and trial.epochs == 5
    # Every eighth decision probes an unmeasured neighbour: no information.
    assert trial.informative == 5 * 7
    assert trial.context(_ctx()).max_window_seconds == 2.0  # not yet applied
    _run(trial, 992, 8)
    assert trial.status == "promoted" and trial.snapshot()["p_value"] == 1 / 64
    assert trial.context(_ctx()).max_window_seconds == 1.0


def test_a_candidate_that_loses_in_shadow_is_rejected():
    # 992 is fastest; one rung lower the candidate cannot reach it.
    world = _timed_world({64: 2**-10, 320: 2**-12, 512: 2**-11, 992: 2**-11})
    trial = ShadowTrial(("rung_down",), world, epoch=8)
    _run(trial, 992, 6 * 8)
    assert trial.status == "rejected" and trial.losses == trial.epochs == 6
    assert trial.context(_ctx()).max_window == 1_000


def test_a_candidate_with_no_measured_difference_is_rejected_at_the_limit():
    world = _timed_world({64: 2**-12, 320: 2**-8, 512: 2**-8 + 2**-10, 992: 2**-7})
    trial = ShadowTrial(("envelope_half",), world, epoch=8, max_epochs=3)
    _run(trial, 64, 3 * 8)  # both choose 64: no information
    assert trial.status == "rejected" and trial.epochs == 0 and trial.informative == 0


def test_decision_thresholds_and_defaults():
    assert sign_test(1, 0) == 0.5
    assert judge(6, 1) == "undecided"  # p = 8/128 = 0.0625: not below 5%
    assert judge(9, 1) == "promote"  # p = 11/1024
    trial = ShadowTrial(("rung_down",), MiningWorldModel())
    assert (trial.epoch, trial.max_epochs) == (64, 40)


def test_twin_record_counts_ties_as_neither():
    record = judge_twin([0.0] * 8)
    assert (record["wins"], record["losses"], record["verdict"]) == (0, 0, "rejected")
    assert judge_twin([0.01, 0.03])["mean_difference"] == pytest.approx(0.02)
    assert judge_twin([])["mean_difference"] == 0.0


def test_levers_at_the_bottom_of_the_ladder():
    assert apply_levers(_ctx(max_window=32), ("rung_down",)).max_window == 32
    assert apply_levers(_ctx(max_window=64), ("rung_down",)).max_window == 32
    assert apply_levers(_ctx(max_window_seconds=None), ("envelope_half",)).max_window_seconds is None


def test_measured_valid_rate_charges_half_a_chunk_per_invalidation():
    world = _timed_world({64: 2**-12, 320: 2**-8, 992: 2**-7})
    world.clean.prior_events = 400.0 * world.clean.prior_seconds
    rate, t = world.clean.mean, 2**-8
    assert measured_valid_rate(world, ROUTE, 320, 256) == pytest.approx(
        320 / t * (1 - rate * t * 256 / 320 / 2)
    )
