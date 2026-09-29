"""recovery.effect: a verified recovery is judged by the throughput after it."""

from __future__ import annotations

import pytest

from mla1517.mining.recovery_effect import RecoveryEffects


def _windows(effects: RecoveryEffects, n: int, rate_hs: float) -> list[str]:
    settled = []
    for _ in range(n):
        settled += effects.observe_window(1_000, 1_000 / rate_hs)
    return settled


def test_a_recovery_is_scored_by_the_rate_after_it_against_the_rate_before():
    effects = RecoveryEffects(span=4)
    _windows(effects, 4, 50_000.0)  # degraded
    effects.recovery_verified("r1", ["SEVER_LANE", "RESET_QUEUE"])
    assert _windows(effects, 3, 100_000.0) == []
    assert _windows(effects, 1, 100_000.0) == ["r1"]
    entry = effects.snapshot()["by_commands"]["RESET_QUEUE+SEVER_LANE"]
    assert entry["recoveries"] == 1 and entry["restored"] == 1
    assert entry["last_ratio"] == pytest.approx(2.0)


def test_a_recovery_that_did_not_help_is_recorded_as_such():
    effects = RecoveryEffects(span=4)
    _windows(effects, 4, 80_000.0)
    effects.recovery_verified("r1", ["THROTTLE"])
    _windows(effects, 4, 40_000.0)
    entry = effects.snapshot()["by_commands"]["THROTTLE"]
    assert entry["restored"] == 0 and entry["mean_ratio"] == pytest.approx(0.5)


def test_no_history_means_no_claim():
    effects = RecoveryEffects(span=4)
    assert effects.snapshot()["by_commands"] is None  # the question stays open
    _windows(effects, 2, 80_000.0)
    effects.recovery_verified("r1", ["THROTTLE"])
    _windows(effects, 8, 80_000.0)
    assert effects.snapshot()["by_commands"] is None and effects.unmeasured == 1
