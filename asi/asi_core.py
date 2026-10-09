"""ASI composition facade with explicit authority boundaries.

The ASI package remains a compatibility surface.  Self-healing and
optimisation are SALAMANDER-owned, security is AL HARAS-owned, and optional web
learning is unavailable unless a real research backend exists.  No background
forever-loop is started by this composition root.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from .problem_solver import NovelProblemSolver, get_problem_solver
from .quantum_creator import QuantumAlgorithmCreator, get_quantum_creator
from .self_healing import SelfHealingEngine
from .system_optimizer import SystemOptimizer
from .web_learner import ContinuousWebLearner, get_web_learner

logger = logging.getLogger(__name__)

__all__ = ["ASICore", "ASI_CAPABILITIES"]

ASI_CAPABILITIES = (
    "self_healing",
    "novel_problem_solving",
    "quantum_algorithm_creation",
    "continuous_learning",
    "system_optimization",
)

_PROBES: Dict[str, Any] = {
    "self_healing": ("self_healing", "get_health_report"),
    "novel_problem_solving": ("problem_solver", "get_stats"),
    "quantum_algorithm_creation": ("quantum_creator", "get_stats"),
    "continuous_learning": ("web_learner", "get_stats"),
    "system_optimization": ("system_optimizer", "analyze_system"),
}


class ASICore:
    """Compatibility composition root; it is not an autonomy authority."""

    def __init__(
        self,
        problem_solver: NovelProblemSolver | None = None,
        quantum_creator: QuantumAlgorithmCreator | None = None,
        web_learner: ContinuousWebLearner | None = None,
        self_healing: SelfHealingEngine | None = None,
        system_optimizer: SystemOptimizer | None = None,
    ) -> None:
        self.problem_solver = problem_solver or get_problem_solver()
        self.quantum_creator = quantum_creator or get_quantum_creator()
        self.web_learner = web_learner or get_web_learner()
        self.self_healing = self_healing or SelfHealingEngine()
        self.system_optimizer = system_optimizer or SystemOptimizer()
        self._running = False

    @property
    def capabilities(self) -> List[str]:
        return list(ASI_CAPABILITIES)

    @property
    def background_tasks(self) -> Dict[str, Any]:
        """ASI deliberately owns no persistent background tasks."""
        return {}

    @property
    def running(self) -> bool:
        return self._running

    def component(self, name: str) -> Any | None:
        return {
            "self_healing": self.self_healing,
            "novel_problem_solving": self.problem_solver,
            "quantum_algorithm_creation": self.quantum_creator,
            "continuous_learning": self.web_learner,
            "system_optimization": self.system_optimizer,
        }.get(name)

    def capability_report(self) -> Dict[str, Any]:
        report: Dict[str, Any] = {
            "capabilities": self.capabilities,
            "running": self.running,
            "authority": {
                "self_healing": "SALAMANDER",
                "system_optimization": "SALAMANDER",
                "security_governance": "AL_HARAS",
            },
        }
        for name, (attr, method) in _PROBES.items():
            substrate = getattr(self, attr, None)
            probe = getattr(substrate, method, None) if substrate is not None else None
            if not callable(probe):
                report[name] = {
                    "available": False,
                    "reason": f"no callable {method}() on {attr}",
                }
                continue
            try:
                statistics = probe()
            except Exception as exc:
                report[name] = {
                    "available": False,
                    "reason": f"{method}() raised {type(exc).__name__}: {exc}",
                }
                continue
            available = True
            reason = None
            if isinstance(statistics, dict) and statistics.get("backend_available") is False:
                available = False
                reason = "required backend unavailable"
            entry: Dict[str, Any] = {
                "available": available,
                "statistics": statistics,
            }
            if reason:
                entry["reason"] = reason
            report[name] = entry
        return report

    async def start(self) -> bool:
        """Run bounded startup probes; no forever-loop is created."""
        if self._running:
            return True
        healing = getattr(self.self_healing, "start_monitoring", None)
        if not callable(healing):
            return False
        try:
            healing_ok = await healing(max_cycles=1)
        except TypeError:
            # A non-canonical injected substrate is not allowed to hide a
            # lifecycle mismatch behind an unbounded legacy entry point.
            return False
        self._running = bool(healing_ok)
        return self._running

    async def stop(self) -> bool:
        stop_healing = getattr(self.self_healing, "stop_monitoring", None)
        if callable(stop_healing):
            stop_healing()
        stop_learning = getattr(self.web_learner, "stop", None)
        if callable(stop_learning):
            stop_learning()
        self._running = False
        return True

    def __repr__(self) -> str:
        return f"ASICore(running={self.running}, capabilities={len(self.capabilities)})"
