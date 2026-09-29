"""Operating-policy logic pinned by hand-derived values.

A mutation check of operating_policy.py against the original intelligence
tests killed 48% of planted mistakes: the thermal de-rate on the legacy and
probe paths, the responsiveness envelope, lookahead, lane alignment, probing
and the Lucas ladder itself could change without a test noticing. Each test
here fails for one such mistake.
"""

from __future__ import annotations

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


def test_precompute_depth_is_the_wait_free_minimum_at_ordinary_churn():
    world = _world(0.002, 1e-6, invalidations_per_s=0.0)  # picks 992: W = 2.992 ms a window
    assert OperatingPolicy(world).decide(_context()).lookahead == 2  # no latency seen: legacy
    world.observe_plan_latency(0.010)
    decision = OperatingPolicy(world).decide(_context())
    # One new job per 120 s (the bind prior): waiting 10 - 2.992 d ms reaches 0
    # at d = 4; the old rule's extra plan (5) would only be discarded.
    assert decision.window == 992 and decision.lookahead == 4
    assert decision.expected["precompute_wait_ms"] == 0.0
    assert decision.expected["precompute_discard_ms"] == pytest.approx(
        (1 / 120) * 0.002992 * 4 * 0.010 * 1e3
    )
    assert decision.expected["job_churn_per_hour"] == pytest.approx(30.0)
    assert OperatingPolicy(world).decide(_context(capacity=3)).lookahead == 3
    shallow = OperatingPolicy(world).decide(_context(capacity=1))
    # Only depth 1 is considered: waiting 10 - 2.992 ms.
    assert shallow.lookahead == 1
    assert shallow.expected["precompute_wait_ms"] == pytest.approx(7.008)


@pytest.mark.parametrize(
    "jobs_per_s, depth, wait_ms, discard_ms",
    [
        # C(d) = max(0, 10 - 2.992 d) + rate * 2.992 * d * 10  (ms, per window)
        (50.0, 3, 1.024, 4.488),  # d=3: 5.512 < d=4: 0 + 5.984
        (200.0, 1, 7.008, 5.984),  # rate * l_mean = 2: a queued plan costs more than it saves
    ],
)
def test_job_churn_cuts_precompute_depth(jobs_per_s, depth, wait_ms, discard_ms):
    world = _world(0.002, 1e-6, invalidations_per_s=0.0)
    world.bind.prior_events = jobs_per_s * world.bind.prior_seconds
    world.observe_plan_latency(0.010)
    decision = OperatingPolicy(world).decide(_context())
    assert decision.lookahead == depth
    assert decision.expected["precompute_wait_ms"] == pytest.approx(wait_ms)
    assert decision.expected["precompute_discard_ms"] == pytest.approx(discard_ms)
    assert f"depth {depth}: wait {wait_ms:.3f} ms" in decision.reason


def test_one_slow_plan_does_not_set_the_depth_forever():
    world = _world(0.002, 1e-6, invalidations_per_s=0.0)
    world.observe_plan_latency(0.100)  # a stall
    stalled = OperatingPolicy(world).decide(_context())
    assert stalled.lookahead == 8  # capacity-bound: still waiting 100 - 8 * 2.992 ms
    assert stalled.expected["precompute_wait_ms"] == pytest.approx(76.064)
    for _ in range(64):
        world.observe_plan_latency(0.001)
    assert world.plan_latency_quantile(0.9) == 0.001 and world.plan_latency_max_s == 0.100
    assert OperatingPolicy(world).decide(_context()).lookahead == 1


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
    assert f"vs legacy {legacy_loss:.4f};" in decision.reason


def _sagging(h: int) -> float:
    """0.5 ms overhead, 1 us per hash, and a rate that halves by 250 hashes."""
    return 0.0005 + h * 1e-6 * (1 + h / 250)


def _bent_world(elapsed_of, sizes=(64, 96, 192, 320, 512, 832, 992)) -> MiningWorldModel:
    """A route whose window sizes took ``elapsed_of(hashes)``, three times each."""
    world = MiningWorldModel()
    route = RouteModel(forgetting=1.0)
    for hashes in sizes * 3:
        route.observe(hashes, elapsed_of(hashes), 0.0)
    world.routes[ROUTE] = route
    world.clean.prior_events = 0.0
    return world


def test_a_misfit_line_hands_the_choice_to_measured_throughput():
    world = _bent_world(_sagging)
    route = world.route(ROUTE)
    # The line cannot bend: its overhead collapses to 0 (the true one is 0.5 ms),
    # which would make the smallest window look free.
    assert route.estimate()[0] == 0.0 and route.misfit() > 0.25
    policy = OperatingPolicy(world)
    policy.decisions = 1  # not a probing turn
    decision = policy.decide(_context())
    # Measured valid H/s: 192 -> 228.7k, 320 -> 260.2k, 512 -> 248.5k.
    assert (decision.source, decision.window) == ("measured", 320)
    assert decision.expected["valid_rate_hs"] == pytest.approx(320 / _sagging(320))
    losses = {c["window"]: c["loss"] for c in decision.candidates}
    assert losses[320] == 0.0 and losses[512] == pytest.approx(
        1 - (512 / _sagging(512)) / (320 / _sagging(320))
    )
    assert "misfit" in decision.reason


def test_measured_mode_climbs_by_probing_an_unmeasured_neighbour():
    world = _bent_world(_sagging, sizes=(64, 96, 192, 320, 832, 992))  # 512 never run
    policy = OperatingPolicy(world)
    policy.decisions = 7  # the next decision (8th) is a probing turn
    decision = policy.decide(_context())
    assert (decision.source, decision.window) == ("probe", 512)
    assert decision.candidates == ()
    policy.decisions = 8  # an ordinary turn: the best measured size
    assert policy.decide(_context()).window == 320


def test_measured_mode_respects_the_envelope_with_measured_time():
    world = _bent_world(_sagging)
    policy = OperatingPolicy(world)
    policy.decisions = 1
    # 320 took 1.23 ms, 192 took 0.84 ms: a 1 ms bound keeps 192.
    assert policy.decide(_context(max_window_seconds=0.001)).window == 192


def test_a_line_that_fits_keeps_the_model():
    world = _bent_world(lambda h: 0.0005 + h * 1e-6)
    assert world.route(ROUTE).misfit() < 1e-9
    assert OperatingPolicy(world).decide(_context()).source == "model"


def _timed_world(elapsed: dict[int, float]) -> MiningWorldModel:
    """A route whose window sizes took exactly ``elapsed[size]``, four times each."""
    world = MiningWorldModel()
    route = RouteModel(forgetting=1.0)
    for _ in range(4):
        for hashes, seconds in elapsed.items():
            route.observe(hashes, seconds, 0.0)
    world.routes[ROUTE] = route
    world.clean.prior_events = 0.0
    return world


# Dyadic times, so measured means are exact. 64 is by far the fastest size.
FAST_64 = {64: 2**-12, 320: 2**-8, 512: 2**-8 + 2**-10, 832: 2**-8 + 2**-9, 992: 2**-7}


def test_measured_mode_probes_both_neighbours_in_turn_timed_by_the_line():
    world = _timed_world(FAST_64)
    overhead, per_hash = world.route(ROUTE).estimate()
    assert overhead > 0 and world.route(ROUTE).misfit() > 0.25
    policy = OperatingPolicy(world)
    policy.decisions = 1
    decision = policy.decide(_context())
    assert (decision.source, decision.window) == ("measured", 64)
    assert "window 64 at 262144 valid H/s" in decision.reason
    assert decision.expected["overhead_ms"] == pytest.approx(overhead * 1e3)
    assert decision.expected["hash_rate_hs"] == pytest.approx(1 / per_hash)
    # Every eighth decision measures a neighbour on the ladder
    # [32, 64, 96, ...], right then left; unmeasured sizes are timed by the line.
    for turn, probe in ((7, 96), (15, 32)):
        policy.decisions = turn
        decision = policy.decide(_context())
        assert (decision.source, decision.window) == ("probe", probe)
        assert f"measuring window {probe} beside 64" in decision.reason
        assert decision.expected["valid_rate_hs"] == pytest.approx(
            probe / (overhead + probe * per_hash)
        )


def test_measured_valid_rate_charges_half_a_chunk_per_invalidation():
    world = _timed_world(FAST_64)
    world.clean.prior_events = 400.0 * world.clean.prior_seconds
    rate = world.clean.mean
    policy = OperatingPolicy(world)
    policy.decisions = 1
    decision = policy.decide(_context(chunk_cap=256))

    def valid(w: int) -> float:
        t = FAST_64[w]
        return w / t * max(0.0, 1.0 - rate * t * min(w, 256) / w / 2.0)

    top = max(valid(w) for w in FAST_64)
    assert decision.window == 64
    assert decision.expected["valid_rate_hs"] == pytest.approx(valid(64))
    assert decision.expected["invalidations_per_hour"] == pytest.approx(rate * 3600)
    assert {c["window"]: c["loss"] for c in decision.candidates} == pytest.approx(
        {w: 1.0 - valid(w) / top for w in FAST_64}
    )


def test_measured_envelope_is_inclusive_and_falls_back_to_the_smallest_rung():
    policy = OperatingPolicy(_timed_world(FAST_64))
    policy.decisions = 1
    # 320 took exactly 2^-8 s: an envelope of 2^-8 s keeps it.
    decision = policy.decide(_context(max_window_seconds=2**-8))
    assert {c["window"] for c in decision.candidates} == {64, 320}
    # Nothing fits a 2^-13 s envelope: only the smallest rung is left.
    assert policy.decide(_context(max_window_seconds=2**-13)).window == 32


def test_measured_mode_probes_around_the_legacy_window_when_bounds_exclude_every_measured_size():
    world = _timed_world({320: 2**-10, 512: 2**-8, 832: 2**-7, 992: 2**-6})
    assert world.route(ROUTE).misfit() > 0.25
    policy = OperatingPolicy(world)
    # De-rated to 180: ladder [32, 64, 96, 160]; legacy 128 is nearest 96.
    for turn, probe in ((0, 64), (7, 160)):
        policy.decisions = turn
        decision = policy.decide(_context(legacy_window=128, derate_cap=180))
        assert (decision.source, decision.window) == ("probe", probe)
        assert "beside 96" in decision.reason


@pytest.mark.parametrize("misfit, source", [(0.25, "model"), (0.2501, "probe")])
def test_measured_mode_starts_above_a_quarter_misfit(monkeypatch, misfit, source):
    world = _world(0.002, 1e-6, invalidations_per_s=0.0)
    monkeypatch.setattr(world.route(ROUTE), "misfit", lambda min_samples=3: misfit)
    assert OperatingPolicy(world).decide(_context()).source == source


def test_the_model_envelope_is_inclusive():
    world = _world(2**-9, 2**-20, invalidations_per_s=0.0)  # exact estimate
    assert world.route(ROUTE).estimate() == (2**-9, 2**-20)
    assert OperatingPolicy(world).decide(_context(max_window_seconds=320 * 2**-20)).window == 320
