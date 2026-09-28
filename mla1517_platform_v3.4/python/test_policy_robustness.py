"""Training under a misspecified world: the device slows as a window runs.

The policy learns ``elapsed = o + hashes / H`` and minimises
``J(T) = o/(o+T) + lambda*min(T, T_chunk)/2``. The simulator's sag regime
breaks the model's assumption: the rate falls as ``H / (1 + t / tau)`` within
each window, and nothing tells the policy. These tests record where learning
still helps and where it currently fails.
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
    assert model > 0.93


@pytest.mark.xfail(
    strict=True,
    reason=(
        "J(T) rewards time spent hashing, not hashes per second, and the linear route model "
        "cannot represent a rate that sags within a window: under strong sag the policy keeps "
        "the largest window (36% efficiency against 81% for the fixed window; the best fixed "
        "window reaches 91%). Fix: judge rungs by measured throughput, or step down when "
        "observed elapsed persistently exceeds the model's prediction."
    ),
)
def test_strong_sag_never_leaves_the_policy_worse_than_the_fixed_window():
    legacy, model, _ = _run(0.05)
    assert model >= legacy - 0.02
