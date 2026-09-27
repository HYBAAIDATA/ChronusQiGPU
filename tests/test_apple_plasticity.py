"""Tests for Apple Silicon + plasticity wiring."""

from Intelligence.apple_plasticity import ApplePlasticity


def test_apple_plasticity_init():
    ap = ApplePlasticity()
    assert ap.plasticity is not None
    assert len(ap.plasticity.subsystems) > 0


def test_apple_workload():
    ap = ApplePlasticity()
    result = ap.execute_apple_workload("ane_inference")
    assert "report" in result
    assert result["reward"] > 0


def test_apple_telemetry():
    ap = ApplePlasticity()
    tel = ap.telemetry()
    assert "apple" in tel
    assert "plasticity" in tel
