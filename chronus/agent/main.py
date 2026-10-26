"""Euclid operational facade: explicit host wiring, no signer/trust mutation methods."""

from __future__ import annotations

from typing import Any, Callable

from ._contracts import ContractError
from .goal import infer_real_objective
from .identity import LifecycleState
from .operational_loop import operational_loop


class FrontierAgent:
    def __init__(
        self,
        identity: str,
        task_class: str,
        *,
        capabilities: dict[str, Any],
        permissions: dict[str, Any],
        budgets: dict[str, Any],
        safety: dict[str, Any],
        audit: list[dict[str, Any]],
        authority_snapshot: dict[str, Any],
        verify_authority: Callable[[dict[str, Any]], bool],
        verification_provider: Any,
        verification_policy: Any,
        objective_verification_provider: Any,
        execution_guard: Callable[[Any], bool],
        rollback_guard: Callable[[Any], bool],
        clock: Callable[[], float],
        lifecycle: LifecycleState = LifecycleState.DRAFT,
    ) -> None:
        self.identity = identity
        self.task_class = task_class
        self.capabilities = capabilities
        self.permissions = permissions
        self.budgets = budgets
        self.safety = safety
        self.audit = audit
        self.authority_snapshot = authority_snapshot
        self.verify_authority = verify_authority
        self.verification_provider = verification_provider
        self.verification_policy = verification_policy
        if not callable(execution_guard):
            raise ContractError(
                "external execution guard is mandatory; no direct-execution fallback"
            )
        if not callable(rollback_guard):
            raise ContractError("external rollback guard is mandatory")
        self.rollback_guard = rollback_guard
        self.execution_guard = execution_guard
        self.objective_verification_provider = objective_verification_provider
        self.clock = clock
        self.lifecycle = lifecycle
        self._learning_queue: list[Any] = []
        self._iteration_counter = 0
        audit.append(
            "agent_boot",
            {"identity": identity, "task_class": task_class, "lifecycle": lifecycle},
            now=clock(),
        )

    @property
    def learning_queue(self) -> tuple[Any, ...]:
        return tuple(self._learning_queue)

    @property
    def iteration_counter(self) -> int:
        return self._iteration_counter

    @property
    def counter(self) -> int:
        return self._iteration_counter

    def drain_learning_queue(self) -> tuple[Any, ...]:
        """Host archival: drain and clear the learning evidence queue before the 10,000-item cap."""
        items = tuple(self._learning_queue)
        self._learning_queue.clear()
        return items

    def record_evidence(self, outcome: Any) -> None:
        if len(self._learning_queue) >= 10_000:
            raise ContractError("learning evidence queue full; host must archive")
        self._learning_queue.append(outcome)

    def run(self, objective: Any, cognition: Any, plan: Any) -> Any:
        if len(self._learning_queue) >= 10_000:
            raise ContractError("archive evidence before accepting more tasks")
        infer_real_objective(objective, self.audit, now=self.clock())
        outcome = operational_loop(self, objective, cognition, plan)
        self._iteration_counter += outcome.counter
        return outcome


def frontier_main(agent: FrontierAgent, objective: Any, cognition: Any, plan: Any) -> Any:
    """No second unbudgeted retry and no qualification/elevation call."""
    return agent.run(objective, cognition, plan)
