"""
ASI Core — the orchestrating object for the superintelligence layer.

``asi/__init__.py`` declared ``create_asi_system()`` returning an
``asi_core.ASICore``, but that module was never shipped with the earlier
project. This is the missing implementation.

Scope
-----
:class:`ASICore` is a thin composition root. It wires the five real
substrates that *do* exist in this package and exposes a single lifecycle:

    self_healing -> novel_problem_solver -> quantum_creator
                  -> continuous_web_learner -> system_optimizer

What this class is NOT
-----------------------
It is not a consciousness oracle and it does not certify superintelligence.
It reports component availability and per-capability statistics only.

Background-loop contract
------------------------
``SelfHealingEngine.start_monitoring`` and ``ContinuousWebLearner.start`` are
both unbounded ``while <flag>:`` loops that never return. This class therefore
*schedules* them as asyncio tasks and tracks them, rather than awaiting them
(which would deadlock). :attr:`background_tasks` exposes the live handles so a
caller can assert on or cancel them.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

from .problem_solver import NovelProblemSolver, get_problem_solver
from .quantum_creator import QuantumAlgorithmCreator, get_quantum_creator
from .self_healing import SelfHealingEngine
from .system_optimizer import SystemOptimizer
from .web_learner import ContinuousWebLearner, get_web_learner

logger = logging.getLogger(__name__)

__all__ = ["ASICore", "ASI_CAPABILITIES"]

# The capability surface this orchestrator actually composes.
ASI_CAPABILITIES = (
    "self_healing",
    "novel_problem_solving",
    "quantum_algorithm_creation",
    "continuous_learning",
    "system_optimization",
)


# capability -> (substrate attribute, probe method that must exist and be callable)
_PROBES: Dict[str, Any] = {
    "self_healing": ("self_healing", "get_health_report"),
    "novel_problem_solving": ("problem_solver", "get_stats"),
    "quantum_algorithm_creation": ("quantum_creator", "get_stats"),
    "continuous_learning": ("web_learner", "get_stats"),
    "system_optimization": ("system_optimizer", "analyze_system"),
}

# capability -> the ASICore attribute holding that substrate.
_SUBSTRATE_ATTR: Dict[str, str] = {name: attr for name, (attr, _method) in _PROBES.items()}


class ASICore:
    """Compose the ASI substrates behind one lifecycle object.

    Parameters
    ----------
    problem_solver, quantum_creator, web_learner:
        Injected for testing. ``None`` means "use the process-wide singleton"
        (each of these three modules exposes a ``get_*`` factory).
    self_healing, system_optimizer:
        Always constructed per-instance: neither module exposes a singleton
        accessor, and both carry per-instance state.
    """

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
        self._tasks: Dict[str, "asyncio.Task[Any]"] = {}
        logger.info("[ASI] ASICore composed: %s", ", ".join(ASI_CAPABILITIES))

    # -- introspection -----------------------------------------------------

    @property
    def capabilities(self) -> List[str]:
        """The declared capability surface, in composition order."""
        return list(ASI_CAPABILITIES)

    @property
    def background_tasks(self) -> Dict[str, "asyncio.Task[Any]"]:
        """Live asyncio handles for the two unbounded background loops."""
        return dict(self._tasks)

    @property
    def running(self) -> bool:
        """True when both background loops are scheduled and not done."""
        if len(self._tasks) != 2:
            return False
        return all(not task.done() for task in self._tasks.values())

    def component(self, name: str) -> Any | None:
        """Return the composed substrate for ``name``, or ``None`` if unknown."""
        return {
            "self_healing": self.self_healing,
            "novel_problem_solving": self.problem_solver,
            "quantum_algorithm_creation": self.quantum_creator,
            "continuous_learning": self.web_learner,
            "system_optimization": self.system_optimizer,
        }.get(name)

    def capability_report(self) -> Dict[str, Any]:
        """Report per-capability availability and probe statistics.

        ``available`` is True only when the substrate exists AND exposes the
        probe method. The probe is then invoked and its result attached under
        ``statistics``; if the probe raises, availability is downgraded to
        False and the error recorded. This method never reports a capability
        as available on the basis of a probe that was skipped or that failed.
        """
        report: Dict[str, Any] = {
            "capabilities": self.capabilities,
            "running": self.running,
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
            entry: Dict[str, Any] = {"available": True}
            try:
                entry["statistics"] = probe()
            except Exception as exc:
                entry["available"] = False
                entry["reason"] = f"{method}() raised {type(exc).__name__}: {exc}"
            report[name] = entry
        return report

    # -- lifecycle ---------------------------------------------------------

    async def start(self) -> bool:
        """Schedule the two background loops and report whether they took.

        Both entry points are unbounded loops, so they are scheduled rather
        than awaited. Returns True only when both tasks were created and have
        not already faulted; a faulted task is logged and the result is False.
        """
        if self._tasks:
            logger.debug("[ASI] start() called twice; ignoring")
            return self.running

        # self_healing.start_monitoring (async) and web_learner.start (async).
        # Attribute access must be guarded: a substrate missing its loop entry
        # point must fail closed, not raise AttributeError.
        entries = (
            ("self_healing", "start_monitoring"),
            ("continuous_learning", "start"),
        )
        for name, method in entries:
            factory = getattr(getattr(self, _SUBSTRATE_ATTR[name]), method, None)
            if not callable(factory):
                logger.warning("[ASI] %s has no %s() loop", name, method)
                return False
            self._tasks[name] = asyncio.ensure_future(factory())

        # Let each loop run up to its first suspension point so a crash on
        # entry is observed now rather than as a dangling failed task.
        await asyncio.sleep(0)
        for name, task in self._tasks.items():
            if task.done() and task.exception() is not None:
                logger.warning("[ASI] %s loop failed on start", name)
        return self.running

    async def stop(self) -> bool:
        """Signal both loops to exit and await their cancellation.

        ``stop_monitoring`` and ``stop`` are both synchronous flag setters, so
        the loops terminate at their next ``asyncio.sleep`` boundary. Returns
        True when no task remains pending.
        """
        self.self_healing.stop_monitoring()
        self.web_learner.stop()

        for name, task in self._tasks.items():
            task.cancel()
        for name, task in self._tasks.items():
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("[ASI] %s loop raised during shutdown: %s", name, exc)
        self._tasks.clear()
        return not self.running

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"ASICore(running={self.running}, " f"capabilities={len(self.capabilities)})"
