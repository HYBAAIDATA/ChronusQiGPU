"""TOE trajectory forecast capability."""

from __future__ import annotations

from typing import Any

from .common import SkillError, json_safe

SKILL_ID = "adaptation.trajectory_predict"
TITLE = "Forecast a bounded TOE trajectory"
SOURCE = "Intelligence.orchestrator.IntelligenceOrchestrator.toe_predict_trajectory(self, data)"
INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "state_data": {"type": "object"},
        "horizon": {"type": "integer", "minimum": 1, "maximum": 6},
    },
    "required": ["state_data", "horizon"],
    "additionalProperties": False,
}
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "trajectory": {"type": "array", "items": {"type": "number"}},
        "uncertainty": {"type": "number", "minimum": 0, "maximum": 1},
        "intervention_points": {"type": "array", "items": {"type": "object"}},
        "available": {"type": "boolean"},
    },
    "required": ["trajectory", "uncertainty", "intervention_points"],
}
COST_ESTIMATE = 5
RISK_LEVEL = 0.2
TIME_ESTIMATE = 10.0
EXAMPLES = (
    {
        "input": {"state_data": {"load": 0.8, "temperature": 42}, "horizon": 3},
        "output": {
            "trajectory": [],
            "uncertainty": 0.0,
            "intervention_points": [],
            "available": True,
        },
    },
)
LIMITATIONS = (
    "The TOE source computes a fixed six-point forecast; horizon selects a prefix and cannot request a longer forecast.",
    "Uncertainty is 1 minus the source's measured state-fidelity confidence; it is not a calibrated interval.",
    "Forecasts are advisory and do not authorize actions.",
)


def run(state_data: dict[str, Any], horizon: int) -> dict[str, Any]:
    """Invoke the orchestrator's existing fixed-horizon trajectory method."""
    try:
        from Intelligence.orchestrator import IntelligenceOrchestrator
        from toe.bridge import TOEBridge

        orchestrator = object.__new__(IntelligenceOrchestrator)
        orchestrator.toe = TOEBridge()
        forecast = orchestrator.toe_predict_trajectory(state_data)
    except Exception as exc:
        raise SkillError(f"TOE trajectory prediction unavailable: {exc}") from exc
    if not forecast.available:
        raise SkillError("TOE trajectory prediction returned unavailable")
    energies = forecast.diagnostics.get("energies", [])
    trajectory = [float(value) for value in energies[:horizon]]
    confidence = float(forecast.confidence or 0.0)
    points = [point for point in forecast.intervention_points if point.get("time", 0) <= horizon]
    return {
        "trajectory": trajectory,
        "uncertainty": min(1.0, max(0.0, 1.0 - confidence)),
        "intervention_points": json_safe(points),
        "available": True,
        "confidence": confidence,
        "diagnostics": json_safe(forecast.diagnostics),
        "limitations": list(LIMITATIONS),
    }
