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

from chronus.mla1517.mining.search_plan import CompletionState
from chronus.mla1517.mining.world_model import GammaRate, MiningWorldModel, RouteModel
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


def test_plan_latency_quantile_is_the_nearest_rank_of_recent_builds():
    world = MiningWorldModel()
    assert world.plan_latency_quantile() is None and world.snapshot()["plan_latency_p90_ms"] is None
    for ms in (7, 1, 10, 3, 5, 9, 2, 8, 4, 6):
        world.observe_plan_latency(ms / 1000)
    # Sorted 1..10 ms: the 90th percentile is rank ceil(0.9 * 10) = 9, the median rank 5.
    assert world.plan_latency_quantile() == pytest.approx(0.009)
    assert world.plan_latency_quantile(0.5) == pytest.approx(0.005)
    assert world.snapshot()["plan_latency_p90_ms"] == pytest.approx(9.0)
    for _ in range(64):  # only the most recent 64 builds count
        world.observe_plan_latency(0.001)
    assert world.plan_latency_quantile() == 0.001 and world.plan_latency_max_s == 0.010
    restored = MiningWorldModel()
    restored.import_state(world.export_state())
    assert list(restored.plan_latency_recent) == list(world.plan_latency_recent)


def test_each_window_size_keeps_its_measured_elapsed_and_the_line_is_checked_against_it():
    route = RouteModel(forgetting=1.0)
    for hashes in (1_000, 2_000, 4_000) * 3:  # exactly linear: o = 2 ms, 1 us per hash
        route.observe(hashes, 0.002 + hashes * 1e-6, 0.0)
    assert route.measured_elapsed(2_000) == pytest.approx(0.004)
    assert route.measured_elapsed(8_000) is None  # never run
    assert route.misfit() == pytest.approx(0.0, abs=1e-9)
    route.observe(500, 0.01, 0.0)
    assert route.measured_elapsed(500) is None  # one sample is not a measurement
    assert route.measured_elapsed(500, min_samples=1) == pytest.approx(0.01)

    bent = RouteModel(forgetting=1.0)
    for hashes in (1_000, 2_000, 4_000) * 6:  # elapsed grows as hashes squared
        bent.observe(hashes, (hashes / 1_000) ** 2 * 1e-3, 0.0)
    overhead, per_hash = bent.estimate()
    worst = max(
        abs(((h / 1_000) ** 2 * 1e-3) / (overhead + h * per_hash) - 1)
        for h in (1_000, 2_000, 4_000)
    )
    assert bent.misfit() == pytest.approx(worst) and worst > 0.25


def test_measured_sizes_survive_a_restart_and_are_bounded():
    world = MiningWorldModel()
    for hashes in range(1, 80):
        world.observe_execution(_record(hash_count=hashes * 32, elapsed_seconds=0.001 * hashes))
    route = world.route(ROUTE)
    assert len(route.rungs) == 64  # the least-evidenced sizes are forgotten
    restored = MiningWorldModel()
    restored.import_state(world.export_state())
    assert restored.route(ROUTE).rungs == route.rungs


def _sized_route(elapsed_of, sizes=(64, 192, 320, 512, 992)) -> RouteModel:
    route = RouteModel(forgetting=1.0)
    for _ in range(3):
        for hashes in sizes:
            route.observe(hashes, elapsed_of(hashes), 0.0)
    return route


def test_sag_is_the_growth_of_the_marginal_time_per_hash():
    # e(h) = 0.5 ms + 1 us * h * (1 + h / 250): m(h) = 1 us * (1 + h / 125).
    route = _sized_route(lambda h: 0.0005 + h * 1e-6 * (1 + h / 250))
    assert route.sag() == pytest.approx((1 + 992 / 125) / (1 + 64 / 125) - 1, rel=1e-6)
    assert route.snapshot()["sag"] == pytest.approx(route.sag(), abs=1e-4)


def test_a_straight_line_has_no_sag_and_too_few_sizes_say_nothing():
    assert _sized_route(lambda h: 0.0005 + h * 1e-6).sag() == pytest.approx(0.0, abs=1e-9)
    assert _sized_route(lambda h: 0.0005 + h * 1e-6, sizes=(64, 992)).sag() is None
    # Speeding up (a warming cache) is negative sag.
    assert _sized_route(lambda h: 0.0005 + h * 1e-6 * (1 - h / 4000)).sag() < 0


def test_plan_readiness_follows_the_depth_model():
    world = MiningWorldModel()
    assert world.plan_ready_probability(2, 0.01) is None
    for latency in (0.001, 0.002, 0.015, 0.030):
        world.observe_plan_latency(latency)
    world.bind.prior_events = 0.0  # no new jobs: only the lead time matters
    # d W = 20 ms covers three of four builds: (3 + 0.5) / 5.
    assert world.plan_ready_probability(2, 0.010) == pytest.approx(0.7)
    assert world.plan_ready_probability(4, 0.010) == pytest.approx(0.9)
    # Jobs every 10 ms on average: mostly the drained queue decides.
    world.bind.prior_events = 100.0 * world.bind.prior_seconds
    no_job = math.exp(-world.bind.mean * 0.010)
    drained = ((1 - 0.1) + (1 - 0.2)) / 4
    assert world.plan_ready_probability(2, 0.010) == pytest.approx(
        no_job * 0.7 + (1 - no_job) * drained
    )


def test_sag_needs_exactly_three_sizes_and_is_scale_free():
    three = _sized_route(lambda h: 0.0005 + h * 1e-6 * (1 + h / 250), sizes=(64, 320, 992))
    assert three.sag() == pytest.approx((1 + 992 / 125) / (1 + 64 / 125) - 1, rel=1e-6)
    # A marginal time that is not positive at the smallest size has no ratio.
    falling = _sized_route(lambda h: 0.0005 - 1e-6 * h + 2e-9 * h * h, sizes=(64, 320, 992))
    assert falling.sag() is None


def test_plan_readiness_is_clamped_and_depth_is_at_least_one():
    world = MiningWorldModel()
    world.bind.prior_events = 0.0
    for _ in range(200):
        world.observe_plan_latency(0.0001)
    assert world.plan_ready_probability(2, 0.010) == 0.99  # (200.5 / 201), clamped
    world = MiningWorldModel()
    world.bind.prior_events = 0.0
    for latency in (0.005, 0.015):
        world.observe_plan_latency(latency)
    # Depth 0 counts as one plan of lead: 10 ms covers one of two builds.
    assert world.plan_ready_probability(0, 0.010) == pytest.approx(1.5 / 3)
    assert world.plan_ready_probability(2, 0.0) is None


def test_route_model_constants_and_identifiability_thresholds_are_locked():
    """Lock the measurement contracts so mutations of sample thresholds,
    spread gate, forgetting default, or plan-latency smoothing cannot survive."""
    model = RouteModel()
    assert model.forgetting == 0.995
    assert model.direct_samples == 0 and model.fit_samples == 0
    # Direct path requires exactly 3 samples
    model.observe(1000, 0.01, 0.004)
    model.observe(1000, 0.01, 0.004)
    assert not model.identifiable
    model.observe(1000, 0.01, 0.004)
    assert model.identifiable and model.direct_samples == 3
    # Fit path requires 16 samples and spread*sqrt(n) >= 0.5
    fit = RouteModel(forgetting=1.0)
    for _ in range(15):
        fit.observe(1000, 0.01, 0.0)
    assert fit.fit_samples == 15 and not fit.identifiable
    fit.observe(1000, 0.01, 0.0)
    # With identical windows spread is 0, so still not identifiable
    assert fit.fit_samples == 16 and not fit.identifiable
    # Plan latency smoothing and recent window
    world = MiningWorldModel()
    assert world.plan_latency_recent.maxlen == 64
    world.observe_plan_latency(0.1)
    assert world.plan_latency_s == 0.1
    world.observe_plan_latency(0.2)
    assert world.plan_latency_s == pytest.approx(0.9 * 0.1 + 0.1 * 0.2)
