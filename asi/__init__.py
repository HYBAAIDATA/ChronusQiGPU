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

from .problem_solver import NovelProblemSolver
from .quantum_creator import QuantumAlgorithmCreator
from .self_healing import SelfHealingEngine
from .system_optimizer import SystemOptimizer
from .web_learner import ContinuousWebLearner

__version__ = "1.0.0"
__all__ = [
    "ContinuousWebLearner",
    "NovelProblemSolver",
    "QuantumAlgorithmCreator",
    "SelfHealingEngine",
    "SystemOptimizer",
    "create_asi_system",
]


def create_asi_system():
    """
    Create complete ASI system with all superintelligence capabilities

    Returns:
        ASI system instance with:
        - Self-healing
        - Quantum algorithm creation
        - Continuous learning
        - Novel problem solving
        - System optimization
    """
    from .asi_core import ASICore

    return ASICore()
