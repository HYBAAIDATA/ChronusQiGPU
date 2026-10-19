"""Top-level shim for open_ended module as specified in EUCLID Frontier Pseudocode."""

from euclid.cognition.frontier.open_ended import (
    SimEnv,
    AgentLineage,
    CurriculumGeneratorEngine,
    CurriculumGenerator,
    propose_envs,
    experience_loop,
    inject_shock,
)

__all__ = [
    "SimEnv",
    "AgentLineage",
    "CurriculumGeneratorEngine",
    "CurriculumGenerator",
    "propose_envs",
    "experience_loop",
    "inject_shock",
]
