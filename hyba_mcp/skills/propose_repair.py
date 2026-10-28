"""Advisory-only SALAMANDER repair proposal capability."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .common import SkillError

SKILL_ID = "healing.propose_repair"
TITLE = "Propose a SALAMANDER repair without executing it"
SOURCE = "Intelligence.salamander.SelfRepairEngine.diagnose(failure_type, details)"
INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "telemetry": {"type": "object"},
        "fault_type": {"type": "string", "minLength": 1},
    },
    "required": ["telemetry", "fault_type"],
    "additionalProperties": False,
}
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "proposal": {"type": "object"},
        "executed": {"type": "boolean"},
        "risk_score": {"type": "number", "minimum": 0, "maximum": 1},
        "risk_measure": {"type": "string"},
    },
    "required": ["proposal", "executed", "risk_score"],
}
COST_ESTIMATE = 2
RISK_LEVEL = 0.1
TIME_ESTIMATE = 2.0
EXAMPLES = (
    {
        "input": {"telemetry": {"component": "toe"}, "fault_type": "timeout"},
        "output": {"proposal": {}, "executed": False, "risk_score": 0.0},
    },
)
LIMITATIONS = (
    "Only SALAMANDER diagnosis/proposal is called; approval, application, and verification stages are never entered.",
    "risk_score is a categorical proxy (known safe diagnosis: 0; unclassified: 1), not a calibrated risk probability.",
)


def run(telemetry: dict[str, Any], fault_type: str) -> dict[str, Any]:
    """Use SALAMANDER's Stage 3 proposal mechanism and categorically prevent actuation."""
    try:
        from Intelligence.salamander import SelfRepairEngine

        proposal = SelfRepairEngine().diagnose(fault_type, telemetry)
    except Exception as exc:
        raise SkillError(f"SALAMANDER proposal unavailable: {exc}") from exc
    proposal.applied = False
    return {
        "proposal": asdict(proposal),
        "executed": False,
        "risk_score": 0.0 if proposal.is_safe else 1.0,
        "risk_measure": "categorical safety proxy; not a calibrated probability",
    }
