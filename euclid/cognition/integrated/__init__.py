"""EUCLID integrated adaptive intelligence (v17).

Specialists that make :class:`~euclid.cognition.core.GeneralIntelligenceCore`
operate as one adaptive system over interactive task worlds: a Bayesian
mechanism world model, information-gain discrimination, value-of-information
metacognition, contextual strategy meta-learning, structural analogy,
hierarchical model-based planning with measured representation restructuring,
autonomous primitive discovery, adaptive multi-objective decisions, dynamic
objectives with proxy auditing, and episode consolidation with transfer
bookkeeping.  φ/Fibonacci machinery is used operationally and ablatable.
"""
from .agent import SYSTEMS, AccountingExecutor, EpisodeResult, IntegratedAgent, build_problem
from .context import AgentConfig, EpisodeContext, structural_class, structure_tokens
from .memory import AgentKnowledge, StructuralMemory
from .skills import SkillLibrary
from .world_model import MechanismPosterior

__all__ = [
    "AccountingExecutor",
    "AgentConfig",
    "AgentKnowledge",
    "EpisodeContext",
    "EpisodeResult",
    "IntegratedAgent",
    "MechanismPosterior",
    "SYSTEMS",
    "SkillLibrary",
    "StructuralMemory",
    "build_problem",
    "structural_class",
    "structure_tokens",
]
