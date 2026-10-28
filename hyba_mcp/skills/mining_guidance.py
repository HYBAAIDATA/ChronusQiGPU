"""Advisory TOE mining guidance capability."""

from __future__ import annotations

from typing import Any

from .common import SkillError, json_safe

SKILL_ID = "mining.guidance"
TITLE = "Produce advisory TOE mining guidance"
SOURCE = (
    "Intelligence.orchestrator.IntelligenceOrchestrator.toe_guide_mining"
    "(self, header: bytes, target: bytes, block_context=None)"
)
INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "header": {
            "type": "array",
            "items": {"type": "integer", "minimum": 0, "maximum": 255},
            "maxItems": 256,
        },
        "target": {
            "type": "array",
            "items": {"type": "integer", "minimum": 0, "maximum": 255},
            "maxItems": 32,
        },
        "context": {"type": "object"},
    },
    "required": ["header", "target", "context"],
    "additionalProperties": False,
}
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "search_space": {"type": "object"},
        "expected_value": {"type": ["number", "null"]},
        "quantum_guidance": {"type": "object"},
        "advisory_only": {"type": "boolean"},
    },
    "required": ["search_space", "expected_value", "quantum_guidance"],
}
COST_ESTIMATE = 8
RISK_LEVEL = 0.3
TIME_ESTIMATE = 15.0
EXAMPLES = (
    {
        "input": {"header": [0] * 80, "target": [255] * 32, "context": {}},
        "output": {
            "search_space": {"ordering_advice": "not provided"},
            "expected_value": None,
            "quantum_guidance": {},
        },
    },
)
LIMITATIONS = (
    "The source guidance does not prove a nonce ordering advantage or predict SHA256d success.",
    "expected_value is null because the source does not compute mining expected value.",
    "Consensus hashing and target verification remain external validity authorities.",
)


def run(header: bytes, target: bytes, context: dict[str, Any]) -> dict[str, Any]:
    """Call the mining guidance API without submitting work or asserting validity."""
    if not isinstance(header, bytes) or not isinstance(target, bytes):
        raise SkillError("header and target must be bytes")
    try:
        from Intelligence.orchestrator import IntelligenceOrchestrator
        from toe.bridge import TOEBridge

        orchestrator = object.__new__(IntelligenceOrchestrator)
        orchestrator.toe = TOEBridge()
        guidance = orchestrator.toe_guide_mining(header, target, context)
    except Exception as exc:
        raise SkillError(f"TOE mining guidance unavailable: {exc}") from exc
    return {
        "search_space": {
            "header_length_bytes": len(header),
            "target_length_bytes": len(target),
            "ordering_advice": "not provided by this endpoint",
        },
        "expected_value": None,
        "quantum_guidance": json_safe(guidance),
        "advisory_only": True,
        "limitations": list(LIMITATIONS),
    }
