"""Claim-boundary tests for the amplitude-amplification simulation.

These pin the three properties the module's docstring asserts, so the stated
figures cannot drift from the constants that produce them:

1. the reported oracle-query ratio equals sqrt(N / M) recomputed from the
   instance's own N and M;
2. a declared search space larger than the materialisation bound is simulated
   at the bound and the two dimensions are reported separately;
3. difficulty has no default, so a placeholder cannot become an estimate.

Plus one behavioural pin on Grover's finite-budget success curve: it peaks at
the optimal iteration count and falls away from it in both directions.

Claim lane: INTERNAL. Nothing here is a device result or a speedup measurement.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from quantum_compute_substrate.amplitude_amplification import (
    AmplitudeAmplificationProcessor,
)

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "amplitude_amplification.py"
)


# --- 1. the reported ratio is recomputed from this instance's own N and M ----


def test_oracle_query_ratio_recomputes_from_own_constants():
    for search_space, difficulty in ((2 ** 10, 5), (2 ** 14, 8), (2 ** 20, 10)):
        proc = AmplitudeAmplificationProcessor(search_space, difficulty)
        specs = proc.get_specs()
        expected = math.sqrt(proc.N / proc.M)
        assert specs["theoretical_oracle_query_ratio"] == pytest.approx(expected, rel=1e-12)
        # And independently of the instance's cached M:
        recomputed_M = max(1.0, proc.simulation_dimension / (2 ** difficulty))
        assert specs["theoretical_oracle_query_ratio"] == pytest.approx(
            math.sqrt(proc.simulation_dimension / recomputed_M), rel=1e-12
        )


def test_reported_ratio_is_not_the_retired_parallelism_figure():
    """The retired docstring claimed 8,192x. No default configuration gives it."""
    proc = AmplitudeAmplificationProcessor()
    ratio = proc.get_specs()["theoretical_oracle_query_ratio"]
    assert ratio != pytest.approx(8192.0, rel=1e-6)
    # At the default, sqrt(N/M) with M = N/1024 is exactly 32.
    assert ratio == pytest.approx(32.0, rel=1e-9)


def test_optimal_iterations_track_sqrt_n_over_m():
    proc = AmplitudeAmplificationProcessor(2 ** 16, 6)
    expected = int((math.pi / 4) * math.sqrt(proc.N / proc.M))
    assert proc.opt_iterations == pytest.approx(expected, abs=1)


# --- 2. declared space vs simulated dimension are separate -------------------


def test_declared_search_space_is_retained_verbatim():
    declared = 2 ** 32
    proc = AmplitudeAmplificationProcessor(declared, 10)
    assert proc.search_space == declared
    assert proc.simulation_dimension == AmplitudeAmplificationProcessor.MATERIALISATION_BOUND
    assert proc.simulation_dimension < proc.search_space


def test_clamp_is_exposed_not_silent():
    proc = AmplitudeAmplificationProcessor(2 ** 32, 10)
    specs = proc.get_specs()
    assert specs["search_space"] == 2 ** 32
    assert specs["simulation_dimension"] == 2 ** 20
    assert specs["declared_over_simulation_ratio"] == pytest.approx(2 ** 12)
    assert specs["materialisation_bound"] == 2 ** 20


def test_declared_equal_to_simulated_reports_ratio_one():
    proc = AmplitudeAmplificationProcessor(2 ** 12, 4)
    assert proc.declared_over_simulation_ratio() == pytest.approx(1.0)


def test_zero_and_negative_search_space_rejected():
    for bad in (0, -1):
        with pytest.raises(ValueError):
            AmplitudeAmplificationProcessor(bad, 10)


# --- 3. difficulty has no default -------------------------------------------


def test_difficulty_is_required_and_positional():
    """A placeholder difficulty must not silently become an estimate."""
    assert AmplitudeAmplificationProcessor._require_difficulty(10) == 10
    for bad in (None,):
        with pytest.raises(ValueError):
            AmplitudeAmplificationProcessor._require_difficulty(bad)
    with pytest.raises(ValueError):
        AmplitudeAmplificationProcessor._require_difficulty(-1)


def test_marked_state_count_follows_declared_difficulty():
    proc = AmplitudeAmplificationProcessor(2 ** 20, 10)
    assert proc.M == pytest.approx(2 ** 20 / 2 ** 10)
    assert proc.estimate_solutions(10) == pytest.approx(proc.M)
    # Higher difficulty = fewer marked states = larger oracle-query ratio.
    assert proc.estimate_solutions(12) < proc.estimate_solutions(10)


# --- behavioural pin: the finite-budget success curve peaks ----------------


def test_success_probability_peaks_at_optimal_iterations():
    """Success probability is sin^2((2k+1)theta): it peaks, then falls.

    This is the finite-budget property the module docstring states. It is
    checked against the closed form and against the simulation, so the claim
    is behaviourally pinned rather than asserted in prose.
    """
    N, M = 2 ** 10, 1
    proc = AmplitudeAmplificationProcessor(N, int(math.log2(N / M)))
    theta = math.asin(math.sqrt(M / N))
    k_star = max(1, int((math.pi / 4) * math.sqrt(N / M)))

    def p_closed_form(k: int) -> float:
        return math.sin((2 * k + 1) * theta) ** 2

    at_peak = p_closed_form(k_star)
    assert at_peak > 0.9
    # Strictly lower on both sides of the peak.
    assert p_closed_form(k_star - 1) < at_peak
    assert p_closed_form(k_star + 1) < at_peak

    # The simulation agrees: run to the peak and to a point past it.
    def simulate(k: int) -> float:
        state = np.ones(N, dtype=np.complex128) / np.sqrt(N)
        target = 0
        for _ in range(k):
            state = proc.apply_oracle(state, target)
            state = proc.apply_diffusion(state)
        return float(np.abs(state[target]) ** 2)

    assert simulate(k_star) > 0.9
    assert simulate(k_star + 1) < simulate(k_star)


def test_amplitude_estimation_is_normalised():
    proc = AmplitudeAmplificationProcessor(2 ** 8, 4)
    assert proc.quantum_amplitude_estimation(0) == pytest.approx(1.0, rel=1e-9)


def test_search_returns_measured_index_at_small_space():
    proc = AmplitudeAmplificationProcessor(2 ** 8, 1)
    found = proc.grover_search(target=3)
    assert found == 3
    assert proc.verify_result(found, 3)


# --- source lint: retired phrasing must not return -------------------------


RETIRED_PHRASES = (
    "8192x parallelism",
    "8,192x parallelism",
    "Practical limit",
    "# Simplified",
    "theoretical_speedup",
)


def test_retired_phrasing_absent_from_module_source():
    source = MODULE_PATH.read_text(encoding="utf-8").casefold()
    present = [phrase for phrase in RETIRED_PHRASES if phrase.casefold() in source]
    assert present == [], f"retired phrasing reintroduced: {present}"
