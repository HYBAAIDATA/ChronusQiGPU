"""Governed, advisory EUCLID capabilities exposed by HYBA MCP."""

from __future__ import annotations

from importlib import import_module
from typing import Any

SKILL_MODULES = {
    "proof.emergence_verify": "hyba_mcp.skills.emergence_verify",
    "reasoning.causal_explain": "hyba_mcp.skills.causal_explain",
    "healing.propose_repair": "hyba_mcp.skills.propose_repair",
    "security.verify_authority": "hyba_mcp.skills.verify_authority",
    "adaptation.trajectory_predict": "hyba_mcp.skills.trajectory_predict",
    "mining.guidance": "hyba_mcp.skills.mining_guidance",
}


def get_skill_module(skill_id: str) -> Any:
    """Load a registered skill module; arbitrary module paths are never accepted."""
    module_path = SKILL_MODULES.get(skill_id)
    if module_path is None:
        raise KeyError(f"unknown skill: {skill_id}")
    return import_module(module_path)


def discover_skills() -> list[dict[str, Any]]:
    """Return registered public contracts and limitations."""
    skills = []
    for skill_id in SKILL_MODULES:
        module = get_skill_module(skill_id)
        skills.append(
            {
                "skill_id": skill_id,
                "title": module.TITLE,
                "source": module.SOURCE,
                "input_schema": module.INPUT_SCHEMA,
                "output_schema": module.OUTPUT_SCHEMA,
                "time_estimate_seconds": module.TIME_ESTIMATE,
                "cost_estimate": module.COST_ESTIMATE,
                "risk_level": module.RISK_LEVEL,
                "examples": list(module.EXAMPLES),
                "limitations": list(module.LIMITATIONS),
            }
        )
    return skills


__all__ = ["SKILL_MODULES", "discover_skills", "get_skill_module"]
