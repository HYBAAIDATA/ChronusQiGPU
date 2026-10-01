"""Training under a misspecified world: the device slows as a window runs.

The policy learns ``elapsed = o + hashes / H``. The simulator's sag regime
breaks that assumption: the rate falls as ``H / (1 + t / tau)`` within each
window, and nothing tells the policy. The line then bends away from what the
window sizes actually take; its fitted overhead collapses towards zero, which
once made the smallest window look free (36% efficiency under strong sag).
When the line misfits the measured window sizes, the policy now judges them
by measured valid-hash throughput instead.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from policy_bench import REGIMES, simulate

CPU_LADDER = next(r for r in REGIMES if r.name == "cpu_mainnet_rung10_ladder_ceiling")


def _run(tau: float | None, seconds: float = 60.0) -> tuple[float, float, int]:
    regime = replace(CPU_LADDER, sag_tau_s=tau)
    legacy = simulate(regime, mode="legacy", seconds=seconds)
    model = simulate(regime, mode="model", seconds=seconds)
    return legacy["efficiency"], model["efficiency"], model["final_window"]


def test_without_sag_the_integrated_simulator_matches_the_linear_one():
    legacy, model, window = _run(None)
    assert legacy == pytest.approx(0.8155, abs=0.002)
    assert model == pytest.approx(0.998, abs=0.002)
    assert window == 15104


def test_mild_sag_still_learns_most_of_the_gain():
    # tau = 0.5 s: the best fixed window (1344) reaches 0.969.
    legacy, model, _ = _run(0.5)
    assert model > legacy + 0.10
    assert model > 0.95


def test_moderate_sag_no_longer_collapses_to_the_smallest_window():
    # tau = 0.2 s: the fitted overhead once collapsed to 0 and the policy ran
    # 32-nonce windows at 43% efficiency.
    legacy, model, window = _run(0.2)
    assert model > 0.9 and window > 32


def test_strong_sag_is_judged_by_measured_throughput():
    legacy, model, window = _run(0.05)
    # The best fixed window reaches 0.907 (window 512); the fixed 96 window 0.808.
    assert model > legacy
    assert model > 0.83 and window < 2048
