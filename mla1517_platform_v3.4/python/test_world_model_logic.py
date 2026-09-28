"""World-model logic pinned by values derived independently of the code.

A mutation check of world_model.py against the original intelligence tests
killed 52% of planted mistakes: the identifiability gate, the least-squares
estimate, kernel-time units, forgetting and plan latency could all change
without a test noticing. Each test here fails for one such mistake; the
expected numbers come from exact arithmetic or scipy, never from running
the model.
"""

from __future__ import annotations

import math

import pytest

from mla1517.mining.search_plan import CompletionState
from mla1517.mining.world_model import GammaRate, MiningWorldModel, RouteModel
from test_mining_intelligence import ROUTE, _record


def _feed(model: RouteModel, windows, overhead_s=0.002, sec_per_hash=1e-6, kernel=False):
    for hashes in windows:
        elapsed = overhead_s + hashes * sec_per_hash
        model.observe(hashes, elapsed, hashes * sec_per_hash if kernel else 0.0)


# ── the least-squares route model ────────────────────────────────────── #


def test_fit_recovers_overhead_and_rate_exactly_from_varied_windows():
    model = RouteModel(forgetting=1.0)
    _feed(model, [1_000, 5_000, 20_000, 80_000] * 4)
    overhead, per_hash = model.estimate()
    assert overhead == pytest.approx(0.002, rel=1e-9)
    assert per_hash == pytest.approx(1e-6, rel=1e-9)
    snap = model.snapshot()
    assert snap["overhead_ms"] == pytest.approx(2.0, rel=1e-9)
    assert snap["hash_rate_hs"] == pytest.approx(1e6, rel=1e-9)
    assert (snap["method"], snap["fit_samples"], snap["direct_samples"]) == ("fit", 16, 0)


def test_direct_measurement_averages_overhead_and_pools_kernel_time():
    model = RouteModel(forgetting=1.0)
    for hashes, elapsed, kernel in (
        (1_000, 0.010, 0.004),
        (3_000, 0.020, 0.012),
        (2_000, 0.015, 0.008),
    ):
        model.observe(hashes, elapsed, kernel)
    overhead, per_hash = model.estimate()
    assert overhead == pytest.approx((0.006 + 0.008 + 0.007) / 3, rel=1e-12)
    assert per_hash == pytest.approx(0.024 / 6_000, rel=1e-12)
    assert model.snapshot()["method"] == "direct"


def test_identifiability_needs_three_direct_samples():
    model = RouteModel(forgetting=1.0)
    model.observe(1_000, 0.010, 0.004)
    model.observe(1_000, 0.010, 0.004)
    assert not model.identifiable and model.estimate() is None
    model.observe(1_000, 0.010, 0.004)
    assert model.identifiable and model.estimate() is not None


def test_identifiability_needs_sixteen_fits_with_enough_window_spread():
    # Windows 100/300 alternating: coefficient of variation exactly 0.5.
    model = RouteModel(forgetting=1.0)
    _feed(model, [100, 300] * 7 + [100])
    assert model.fit_samples == 15 and not model.identifiable
    _feed(model, [300])
    assert model._spread == pytest.approx(0.5, rel=1e-12)
    assert model.identifiable  # 0.5 * sqrt(16) = 2 >= 0.5

    # spread * sqrt(n) straddling 0.5 at n = 16: spread 0.124 fails, 0.126 passes.
    for spread, expected in ((0.124, False), (0.126, True)):
        model = RouteModel(forgetting=1.0)
        _feed(model, [round(1_000 * (1 - spread)), round(1_000 * (1 + spread))] * 8)
        assert model._spread == pytest.approx(spread, rel=1e-3)
        assert model.identifiable is expected


def test_identical_windows_never_identify_a_fit():
    model = RouteModel(forgetting=1.0)
    _feed(model, [4_096] * 64)
    assert model._spread == 0.0
    assert model.estimate() is None


def test_invalid_observations_are_ignored_and_kernel_time_must_fit_in_elapsed():
    model = RouteModel(forgetting=1.0)
    model.observe(0, 0.01, 0.0)
    model.observe(100, 0.0, 0.0)
    model.observe(-5, 0.01, 0.0)
    assert (model.fit_samples, model.direct_samples) == (0, 0)
    model.observe(100, 0.010, 0.011)  # kernel longer than the window: not direct
    assert (model.fit_samples, model.direct_samples) == (1, 0)
    model.observe(100, 0.010, 0.010)  # all kernel, zero overhead: still direct
    assert (model.fit_samples, model.direct_samples) == (2, 1)


def test_forgetting_weights_recent_windows_more():
    model = RouteModel(forgetting=0.5)
    model.observe(1_000, 0.010, 0.004)
    model.observe(1_000, 0.010, 0.004)
    model.observe(1_000, 0.030, 0.004)  # a slower window arrives last
    overhead, _ = model.estimate()
    # Discounted mean overhead: (0.006*0.25 + 0.006*0.5 + 0.026*1) / 1.75
    assert overhead == pytest.approx((0.0015 + 0.003 + 0.026) / 1.75, rel=1e-12)


# ── rates with forgetting ────────────────────────────────────────────── #


def test_gamma_rate_decays_events_and_exposure_by_half_lives():
    rate = GammaRate(prior_events=1.0, prior_seconds=600.0, half_life_s=3600.0)
    rate.event(4)
    rate.advance(3600.0)  # one half-life
    assert rate.events == pytest.approx(2.0, rel=1e-12)
    assert rate.exposure_s == pytest.approx(3600.0, rel=1e-12)
    rate.advance(3600.0)
    assert rate.events == pytest.approx(1.0, rel=1e-12)
    assert rate.exposure_s == pytest.approx(3600.0 * 0.5 + 3600.0, rel=1e-12)
    assert rate.mean == pytest.approx((1.0 + 1.0) / (600.0 + 5400.0), rel=1e-12)
    assert rate.observed_events == 4
    before = (rate.events, rate.exposure_s)
    rate.advance(0.0)
    rate.advance(-10.0)
    assert (rate.events, rate.exposure_s) == before


@pytest.mark.parametrize(
    "events, exposure, p, exact, tolerance",
    [
        # scipy.stats.gamma.ppf(p, shape, scale=1 / rate)
        (4.0, 400.0, 0.9, 0.007993589586052632, 0.005),
        (4.0, 400.0, 0.5, 0.004670908882795984, 0.005),
        (4.0, 400.0, 0.95, 0.009153519026637573, 0.005),
        (4.0, 400.0, 0.8, 0.006720978787486557, 0.005),
        (39.0, 2400.0, 0.9, 0.016096367269211168, 0.002),
        (0.0, 0.0, 0.9, 0.0038376418216567432, 0.02),  # the prior alone, shape 1
    ],
)
def test_gamma_quantile_matches_scipy(events, exposure, p, exact, tolerance):
    rate = GammaRate(prior_events=1.0, prior_seconds=600.0)
    rate.events, rate.exposure_s = events, exposure
    assert rate.quantile(p) == pytest.approx(exact, rel=tolerance)
    with pytest.raises(ValueError):
        rate.quantile(0.99)


def test_rates_are_reported_per_hour():
    rate = GammaRate(prior_events=1.0, prior_seconds=600.0)
    rate.events, rate.exposure_s = 4.0, 400.0
    snap = rate.snapshot()
    assert snap["per_hour_mean"] == pytest.approx(5.0 / 1000.0 * 3600.0, rel=1e-12)
    assert snap["per_hour_p90"] == pytest.approx(0.007993589586052632 * 3600.0, rel=0.005)


# ── the world model around them ──────────────────────────────────────── #


def test_kernel_milliseconds_become_seconds_for_direct_measurement():
    world = MiningWorldModel()
    for _ in range(3):
        world.observe_execution(_record(hash_count=1_000, elapsed_seconds=0.010, kernel_ms=4.0))
    route = world.route(ROUTE)
    assert route.direct_samples == 3
    overhead, per_hash = route.estimate()
    assert overhead == pytest.approx(0.006, rel=1e-12)
    assert per_hash == pytest.approx(4e-6, rel=1e-12)


def test_invalidated_windows_count_but_never_train_the_route():
    world = MiningWorldModel()
    world.observe_execution(_record(completion_state=CompletionState.INVALIDATED))
    assert world.route(ROUTE) is None
    assert world.completions == {CompletionState.INVALIDATED.value: 1}


def test_only_clean_jobs_and_new_sessions_count_as_invalidations():
    world = MiningWorldModel()
    world.observe_bind(0.0, clean_jobs=False)
    world.observe_bind(1.0, clean_jobs=True)
    world.observe_bind(2.0, clean_jobs=False, new_session=True)
    assert world.bind.observed_events == 3
    assert world.clean.observed_events == 2
    world.tick(2.0)  # no time passed: exposure unchanged
    assert world.clean.exposure_s == pytest.approx(1.0 * 0.5 ** (1 / 3600) + 1.0, rel=1e-12)


def test_plan_latency_tracks_the_worst_case_and_a_smoothed_mean():
    world = MiningWorldModel()
    world.observe_plan_latency(-1.0)
    assert (world.plan_samples, world.plan_latency_s) == (0, None)
    for seconds in (0.010, 0.050, 0.020):
        world.observe_plan_latency(seconds)
    assert world.plan_samples == 3
    assert world.plan_latency_max_s == 0.050
    assert world.plan_latency_s == pytest.approx(0.9 * (0.9 * 0.010 + 0.1 * 0.050) + 0.1 * 0.020)


def test_state_round_trips_through_export_and_import():
    world = MiningWorldModel()
    world.observe_bind(0.0, clean_jobs=True)
    world.tick(120.0)
    for hashes in (1_000, 5_000, 20_000, 80_000) * 4:
        world.observe_execution(_record(hash_count=hashes, elapsed_seconds=0.002 + hashes * 1e-6))
    for seconds in (0.01, 0.03):
        world.observe_plan_latency(seconds)
    restored = MiningWorldModel()
    restored.import_state(world.export_state())
    # Learned state persists; per-run completion counters start fresh.
    assert restored.completions == {} and world.completions == {"COMPLETE": 16}
    assert {k: v for k, v in restored.snapshot().items() if k != "completions"} == {
        k: v for k, v in world.snapshot().items() if k != "completions"
    }
    assert (restored.plan_samples, restored.plan_latency_max_s) == (2, 0.03)
    assert restored.route(ROUTE).estimate() == pytest.approx(world.route(ROUTE).estimate())
    assert math.isclose(restored.clean.mean, world.clean.mean)


def test_edge_observations_count_and_an_empty_route_reports_no_evidence():
    empty = RouteModel().snapshot()
    assert empty["method"] == "insufficient_evidence"
    assert (empty["overhead_ms"], empty["hash_rate_hs"], empty["window_spread"]) == (
        None,
        None,
        0.0,
    )
    model = RouteModel(forgetting=1.0)
    model.observe(1, 0.001, 0.0)  # a one-hash window is a real window
    assert model.fit_samples == 1
    world = MiningWorldModel()
    world.observe_plan_latency(0.0)  # an instant plan is a real sample
    world.observe_plan_latency(0.004)
    snap = world.snapshot()
    assert world.plan_samples == 2
    assert snap["plan_latency_ms"] == pytest.approx(0.4)  # 0.9 * 0 + 0.1 * 4 ms
    assert snap["plan_latency_max_ms"] == pytest.approx(4.0)
