"""
ASI (Artificial Superintelligence) Module

Premium capabilities for internal use and special clients:
- Self-healing and optimization
- Novel quantum algorithm creation
- Continuous web-based learning
- Advanced problem solving
- System evolution

This is the superintelligence layer - beyond AGI.
"""

from .asi_core import ASICore
from .causal_temporal import (
    GrangerResult,
    LagCriterion,
    TemporalCausalGraph,
    discover_temporal_causality,
    granger_causality,
    select_lag,
)
from .problem_solver import NovelProblemSolver, get_problem_solver
from .quantum_creator import QuantumAlgorithmCreator, get_quantum_creator
from .self_healing import SelfHealingEngine
from .system_optimizer import SystemOptimizer
from .web_learner import ContinuousWebLearner, get_web_learner

__version__ = "1.0.0"
__all__ = [
    "ASICore",
    "ContinuousWebLearner",
    "GrangerResult",
    "LagCriterion",
    "NovelProblemSolver",
    "QuantumAlgorithmCreator",
    "SelfHealingEngine",
    "SystemOptimizer",
    "TemporalCausalGraph",
    "create_asi_system",
    "discover_temporal_causality",
    "get_problem_solver",
    "get_quantum_creator",
    "get_web_learner",
    "granger_causality",
    "select_lag",
]


def create_asi_system() -> ASICore:
    """Create the complete ASI system with all superintelligence capabilities.

    Returns an :class:`ASICore` bundling self-healing, quantum algorithm
    creation, continuous learning, novel problem solving and system
    optimization behind one orchestrating object.
    """
    return ASICore()
