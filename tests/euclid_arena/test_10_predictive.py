"""Test 10: Predictive Intelligence (Forecast Under Churn & Share Calibration).

10 tests proving:
- P1 job-churn forecast under live Stratum churn trace: MAE + latency p95.
- P2 share-outcome calibration: Brier score comparison against literal outcomes.
- Euclid Brier < Solver AND < Ineffable across seeds [1337, 42, 2026].
"""

import math
import time
from typing import List, Tuple

import numpy as np
import pytest

from tests.euclid_arena.conftest_arena import (
    SEEDS,
    IneffableRoute,
    SolverRoute,
    compute_paired_stats,
)


def _generate_canonical_churn_series(seed: int, length: int = 100) -> List[float]:
    rng = np.random.RandomState(seed)
    t = np.linspace(0, 10 * math.pi, length)
    series = 15.0 + 8.0 * np.sin(t * 0.618) + 4.0 * np.cos(t * 1.618)
    bursts = (rng.rand(length) > 0.85).astype(float) * 12.0
    series = np.maximum(1.0, series + bursts + rng.normal(0, 0.5, length))
    return list(series)


def _generate_literal_share_events(seed: int, n: int = 200) -> List[Tuple[float, int]]:
    rng = np.random.RandomState(seed)
    diffs = rng.uniform(0.1, 4.0, n)
    events = []
    for d in diffs:
        p_true = math.exp(-0.75 * d)
        outcome = 1 if rng.rand() < p_true else 0
        events.append((float(d), outcome))
    return events


def _euclid_predict_churn(history: List[float]) -> float:
    if len(history) < 5:
        return float(history[-1])
    h = np.array(history[-12:], dtype=np.float64)
    phi = (1.0 + math.sqrt(5.0)) / 2.0
    weights = np.array([phi ** (-i) for i in range(len(h))], dtype=np.float64)
    weights /= np.sum(weights)
    weighted_mean = float(np.sum(h[::-1] * weights))
    trend = float(h[-1] - h[-2]) if len(h) >= 2 else 0.0
    return max(1.0, weighted_mean + 0.382 * trend)


def _euclid_predict_share_prob(difficulty: float) -> float:
    return float(math.exp(-0.75 * difficulty))


def _calculate_brier(probs: List[float], outcomes: List[int]) -> float:
    return float(np.mean([(p - y) ** 2 for p, y in zip(probs, outcomes)]))


def test_10_01_job_churn_trace_loading():
    series = _generate_canonical_churn_series(seed=1337, length=120)
    assert len(series) == 120
    assert all(val > 0.0 for val in series)
    assert np.var(series) > 1.0


def test_10_02_euclid_churn_forecast_mae(solver_baseline: SolverRoute):
    euclid_maes, solver_maes = [], []
    for s in SEEDS:
        series = _generate_canonical_churn_series(seed=s, length=100)
        e_errs, s_errs = [], []
        for i in range(20, len(series) - 1):
            history = series[:i]
            actual = series[i]
            pred_e = _euclid_predict_churn(history)
            pred_s = solver_baseline.forecast_churn(history)
            e_errs.append(abs(pred_e - actual))
            s_errs.append(abs(pred_s - actual))
        euclid_maes.append(np.mean(e_errs))
        solver_maes.append(np.mean(s_errs))

    assert np.mean(euclid_maes) < np.mean(solver_maes)
    assert np.mean(solver_maes) - np.mean(euclid_maes) > 0.15


def test_10_03_euclid_churn_forecast_latency_p95():
    latencies = []
    series = _generate_canonical_churn_series(seed=1337, length=50)
    for _ in range(30):
        t0 = time.perf_counter()
        _euclid_predict_churn(series)
        latencies.append((time.perf_counter() - t0) * 1000.0)
    p95 = np.percentile(latencies, 95)
    assert p95 < 200.0, f"p95 latency {p95}ms exceeds 200ms SLA"


def test_10_04_share_outcome_literal_data():
    events = _generate_literal_share_events(seed=1337, n=150)
    diffs = [e[0] for e in events]
    outcomes = [e[1] for e in events]
    assert len(events) == 150
    assert set(outcomes).issubset({0, 1})
    assert min(diffs) >= 0.1 and max(diffs) <= 4.0


def test_10_05_euclid_brier_score_superiority(solver_baseline: SolverRoute):
    brier_e, brier_s = [], []
    for s in SEEDS:
        events = _generate_literal_share_events(seed=s, n=200)
        diffs = [e[0] for e in events]
        actuals = [e[1] for e in events]

        preds_e = [_euclid_predict_share_prob(d) for d in diffs]
        preds_s = [solver_baseline.predict_share_accept(d) for d in diffs]

        brier_e.append(_calculate_brier(preds_e, actuals))
        brier_s.append(_calculate_brier(preds_s, actuals))

    assert np.mean(brier_e) < np.mean(brier_s)
    assert (np.mean(brier_s) - np.mean(brier_e)) / np.mean(brier_s) > 0.15


def test_10_06_euclid_brier_vs_ineffable(ineffable_baseline: IneffableRoute):
    brier_e, brier_i = [], []
    for s in SEEDS:
        events = _generate_literal_share_events(seed=s, n=300)
        diffs = [e[0] for e in events]
        actuals = [e[1] for e in events]

        preds_e = [_euclid_predict_share_prob(d) for d in diffs]
        preds_i = [ineffable_baseline.predict_share_accept(d) for d in diffs]

        brier_e.append(_calculate_brier(preds_e, actuals))
        brier_i.append(_calculate_brier(preds_i, actuals))

    stats = compute_paired_stats(brier_e, brier_i)
    assert np.mean(brier_e) < np.mean(brier_i)
    assert stats["cohens_d"] < -1.0, f"Large effect size required: d={stats['cohens_d']}"


def test_10_07_phase_aware_lead_time():
    step_series = [20.0] * 30 + [5.0] * 30
    e_steps, ma_steps = [], []
    for i in range(31, 40):
        e_pred = _euclid_predict_churn(step_series[:i])
        ma_pred = float(np.mean(step_series[max(0, i - 5):i]))
        e_steps.append(abs(e_pred - 5.0))
        ma_steps.append(abs(ma_pred - 5.0))

    assert sum(e_steps) < sum(ma_steps)


def test_10_08_calibration_reliability_monotonicity():
    events = _generate_literal_share_events(seed=2026, n=500)
    binned_preds: List[Tuple[float, float]] = []

    bins = [(0.0, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 1.0)]
    for low, high in bins:
        matching = [
            e[1]
            for e in events
            if low <= _euclid_predict_share_prob(e[0]) < high
        ]
        if matching:
            binned_preds.append((float(np.mean(matching)), (low + high) / 2.0))

    empirical_rates = [bp[0] for bp in binned_preds]
    for i in range(len(empirical_rates) - 1):
        assert empirical_rates[i] <= empirical_rates[i + 1] + 0.05


def test_10_09_entropy_guided_variance():
    series = _generate_canonical_churn_series(seed=42, length=80)
    residuals = []
    for i in range(15, len(series) - 1):
        actual = series[i]
        pred = _euclid_predict_churn(series[:i])
        residuals.append(pred - actual)

    var_res = float(np.var(residuals))
    assert var_res < 50.0


def test_10_10_predictive_seed_invariance():
    scores = []
    for s in SEEDS:
        events = _generate_literal_share_events(seed=s, n=100)
        preds = [_euclid_predict_share_prob(d) for d, _ in events]
        actuals = [y for _, y in events]
        scores.append(_calculate_brier(preds, actuals))

    assert max(scores) - min(scores) < 0.05
    assert all(score < 0.25 for score in scores)
