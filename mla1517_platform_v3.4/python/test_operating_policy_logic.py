"""Operating-policy logic pinned by hand-derived values.

A mutation check of operating_policy.py against the original intelligence
tests killed 48% of planted mistakes: the thermal de-rate on the legacy and
probe paths, the responsiveness envelope, lookahead, lane alignment, probing
and the Lucas ladder itself could change without a test noticing. Each test
here fails for one such mistake.
"""

from __future__ import annotations

import math

import pytest

from mla1517.mining.operating_policy import (
    OperatingPolicy,
    PolicyContext,
    expected_loss,
    lucas_ladder,
)
from mla1517.mining.world_model import MiningWorldModel, RouteModel

ROUTE = "cpu_reference"


def _context(**overrides) -> PolicyContext:
    base = dict(
        route=ROUTE,
        lanes=32,
        max_window=1_000,
        legacy_window=192,
        legacy_lookahead=2,
        capacity=8,
        chunk_cap=1_000,
    )
    base.update(overrides)
    return PolicyContext(**base)


def _world(
    overhead_s: float, sec_per_hash: float, *, invalidations_per_s: float
) -> MiningWorldModel:
    """A world whose route is measured directly and whose rate is exact."""
    world = MiningWorldModel()
    route = RouteModel(forgetting=1.0)
    for _ in range(3):
        route.observe(1_000, overhead_s + 1_000 * sec_per_hash, 1_000 * sec_per_hash)
    world.routes[ROUTE] = route
    world.clean.prior_events = invalidations_per_s * world.clean.prior_seconds
    return world


def _unidentified_world(fit_samples: int) -> MiningWorldModel:
    world = MiningWorldModel()
    route = RouteModel(forgetting=1.0)
    for _ in range(fit_samples):
        route.observe(192, 0.001, 0.0)  # one window size: never separable
    world.routes[ROUTE] = route
    return world


# ── the ladder and the loss ──────────────────────────────────────────── #


def test_ladder_rungs_are_lucas_numbers_floored_to_whole_lanes():
    # L1..L11 = 1, 3, 4, 7, 11, 18, 29, 47, 76, 123, 199; plus the cap.
    assert lucas_ladder(200, 1) == [1, 3, 4, 7, 11, 18, 29, 47, 76, 123, 199, 200]
    # L8..L14 = 47, 76, 123, 199, 322, 521, 843 floored to 32; cap 1000 -> 992.
    assert lucas_ladder(1_000, 32) == [32, 64, 96, 192, 320, 512, 832, 992]


def test_ladder_keeps_rungs_equal_to_one_lane_and_a_cap_of_one_lane():
    assert lucas_ladder(10, 4) == [4, 8]  # L3 = 4 is exactly one lane epoch
    assert lucas_ladder(5, 5) == [5]  # no Lucas rung fits; the cap is one lane
    assert lucas_ladder(3, 5) == []


def test_expected_loss_is_overhead_fraction_plus_half_a_chunk_of_staleness():
    total, overhead, stale = expected_loss(1_000, 0.001, 1e-6, 2.0, 500)
    assert overhead == pytest.approx(0.5)  # 1 ms overhead, 1 ms hashing
    assert stale == pytest.approx(2.0 * (500 * 1e-6) / 2.0)  # chunk capped at 500
    assert total == pytest.approx(0.5 + 0.0005)
    assert expected_loss(0, 0.0, 1e-6, 1.0, 500)[1] == 1.0  # nothing done: all overhead


# ── legacy, hold and probe paths ─────────────────────────────────────── #


def test_legacy_windows_are_lane_aligned_and_obey_the_thermal_derate():
    policy = OperatingPolicy(MiningWorldModel())
    decision = policy.decide(_context(legacy_window=1_000))
    assert (decision.source, decision.window) == ("legacy", 992)
    derated = policy.decide(_context(legacy_window=1_000, derate_cap=500))
    assert derated.window == 480
    held = policy.decide(_context(legacy_window=1_000, derate_cap=500, recovery_active=True))
    assert (held.source, held.window) == ("hold", 480)
    assert policy.decide(_context(legacy_window=1)).window == 32  # never below one lane epoch


def test_probing_starts_at_four_fits_every_eighth_decision_one_rung_up():
    policy = OperatingPolicy(_unidentified_world(fit_samples=4))
    sources = [policy.decide(_context()).source for _ in range(16)]
    assert sources[7] == sources[15] == "probe"
    assert sources.count("probe") == 2
    assert policy.last.window == 320  # 192 is a rung; the next one up is 320

    cautious = OperatingPolicy(_unidentified_world(fit_samples=3))
    assert {cautious.decide(_context()).source for _ in range(16)} == {"legacy"}


def test_probe_steps_down_from_the_top_rung_and_respects_the_derate():
    policy = OperatingPolicy(_unidentified_world(fit_samples=4))
    policy.decisions = 7
    assert policy.decide(_context(legacy_window=992)).window == 832
    policy.decisions = 7
    # Derated to 500: rungs [32, 64, 96, 192, 320, 480]; 192 probes to 320.
    assert policy.decide(_context(derate_cap=500)).window == 320
    policy.decisions = 7
    assert policy.decide(_context(derate_cap=500, legacy_window=480)).window == 320


# ── the model path ───────────────────────────────────────────────────── #


def test_model_picks_the_minimum_loss_rung_and_explains_it_in_real_units():
    world = _world(0.002, 1e-6, invalidations_per_s=0.5)
    decision = OperatingPolicy(world).decide(_context())
    rate = world.clean.mean
    losses = {w: expected_loss(w, 0.002, 1e-6, rate, 1_000)[0] for w in lucas_ladder(1_000, 32)}
    assert decision.source == "model"
    assert decision.window == min(losses, key=lambda w: (losses[w], -w))
    assert decision.expected["overhead_ms"] == pytest.approx(2.0)
    assert decision.expected["hash_rate_hs"] == pytest.approx(1e6)
    assert decision.expected["invalidations_per_hour"] == pytest.approx(rate * 3600.0)
    assert decision.expected["loss"] == pytest.approx(losses[decision.window])


def test_equal_losses_prefer_the_larger_window():
    world = _world(0.0, 1e-6, invalidations_per_s=0.0)  # every rung costs nothing
    assert OperatingPolicy(world).decide(_context()).window == 992


def test_no_window_may_hash_longer_than_the_responsiveness_envelope():
    world = _world(0.002, 1e-6, invalidations_per_s=0.0)  # bigger is always better
    assert OperatingPolicy(world).decide(_context()).window == 992
    # 1e-6 s per hash: 0.0002 s allows at most 200 hashes, so 192.
    assert OperatingPolicy(world).decide(_context(max_window_seconds=0.0002)).window == 192
    # Nothing fits: the smallest rung, never nothing.
    assert OperatingPolicy(world).decide(_context(max_window_seconds=1e-9)).window == 32


def test_the_model_obeys_the_thermal_derate():
    world = _world(0.002, 1e-6, invalidations_per_s=0.0)
    assert OperatingPolicy(world).decide(_context(derate_cap=500)).window == 480


def test_lookahead_covers_the_worst_planning_latency_within_capacity():
    world = _world(0.002, 1e-6, invalidations_per_s=0.0)  # picks 992: 2.992 ms a window
    assert OperatingPolicy(world).decide(_context()).lookahead == 2  # no latency seen: legacy
    world.observe_plan_latency(0.010)
    decision = OperatingPolicy(world).decide(_context())
    window_s = 0.002 + decision.window * 1e-6
    assert decision.lookahead == math.ceil(0.010 / window_s) + 1 == 5
    assert OperatingPolicy(world).decide(_context(capacity=3)).lookahead == 3
    assert OperatingPolicy(world).decide(_context(capacity=1)).lookahead == 1


def test_decisions_and_contexts_are_immutable_once_made():
    # Decisions are audited and attested; nothing may edit one afterwards.
    decision = OperatingPolicy(MiningWorldModel()).decide(_context())
    for obj, field_name in ((decision, "window"), (_context(), "max_window")):
        with pytest.raises(AttributeError):
            setattr(obj, field_name, 1)


def test_probe_edges_step_up_from_the_second_rung_and_down_from_a_two_rung_top():
    policy = OperatingPolicy(_unidentified_world(fit_samples=4))
    policy.decisions = 7
    assert policy.decide(_context(legacy_window=832)).window == 992
    policy.decisions = 7
    assert policy.decide(_context(max_window=64, legacy_window=64)).window == 32


def test_the_reason_states_the_legacy_loss_it_beat():
    world = _world(0.002, 1e-6, invalidations_per_s=0.5)
    decision = OperatingPolicy(world).decide(_context())
    legacy_loss = expected_loss(192, 0.002, 1e-6, world.clean.mean, 1_000)[0]
    assert decision.reason.endswith(f"vs legacy {legacy_loss:.4f}")
