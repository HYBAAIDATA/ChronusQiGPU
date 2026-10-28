"""TOE causal-factor explanation capability."""

from __future__ import annotations

from typing import Any

from .common import SkillError, json_safe

SKILL_ID = "reasoning.causal_explain"
TITLE = "Rank descriptive TOE causal factors"
SOURCE = "Intelligence.orchestrator.IntelligenceOrchestrator.toe_explain_causality(self, data)"
INPUT_SCHEMA = {
    "type": "object",
    "properties": {"data": {"type": "object"}, "query": {"type": "string", "minLength": 1}},
    "required": ["data", "query"],
    "additionalProperties": False,
}
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "factors": {"type": "array", "items": {"type": "object"}},
        "causal_ranking": {"type": "object"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "available": {"type": "boolean"},
        "limitations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["factors", "causal_ranking", "confidence"],
}
COST_ESTIMATE = 5
RISK_LEVEL = 0.2
TIME_ESTIMATE = 10.0
EXAMPLES = (
    {
        "input": {"data": {"load": 0.8, "temperature": 42}, "query": "What factors rank highest?"},
        "output": {"factors": [], "causal_ranking": {}, "confidence": 0.0, "available": True},
    },
)
LIMITATIONS = (
    "The source method accepts data only; query is retained as request context and is not interpreted.",
    "The source reports descriptive factor ranking, not identified causal effects or interventions.",
    "Results are advisory and depend on the supplied data representation.",
)


def run(data: dict[str, Any], query: str) -> dict[str, Any]:
    """Run the exact IntelligenceOrchestrator method; never upgrade ranking to causality."""
    try:
        from Intelligence.orchestrator import IntelligenceOrchestrator
        from toe.bridge import TOEBridge

        orchestrator = object.__new__(IntelligenceOrchestrator)
        orchestrator.toe = TOEBridge()
        analysis = orchestrator.toe_explain_causality(data)
    except Exception as exc:
        raise SkillError(f"TOE causal explanation unavailable: {exc}") from exc

    details = analysis.as_dict()
    if not analysis.available:
        raise SkillError("TOE causal analysis returned unavailable")
    factors = [{"factor": name, "weight": weight} for name, weight in analysis.key_factors]
    return {
        "factors": factors,
        "causal_ranking": dict(analysis.factor_weights),
        "confidence": float(analysis.confidence or 0.0),
        "available": True,
        "query_context": query,
        "diagnostics": json_safe(details.get("diagnostics", {})),
        "limitations": list(LIMITATIONS),
    }
