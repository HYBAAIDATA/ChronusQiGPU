"""Euclid operational facade: explicit host wiring, no signer/trust mutation methods."""

from .identity import LifecycleState
from .goal import infer_real_objective
from .operational_loop import operational_loop
from ._contracts import ContractError


class FrontierAgent:
    def __init__(
        self,
        identity,
        task_class,
        *,
        capabilities,
        permissions,
        budgets,
        safety,
        audit,
        authority_snapshot,
        verify_authority,
        verification_provider,
        verification_policy,
        objective_verification_provider,
        execution_guard,
        rollback_guard,
        clock,
        lifecycle=LifecycleState.DRAFT,
    ):
        self.identity, self.task_class = identity, task_class
        self.capabilities, self.permissions, self.budgets = capabilities, permissions, budgets
        self.safety, self.audit = safety, audit
        self.authority_snapshot, self.verify_authority = authority_snapshot, verify_authority
        self.verification_provider, self.verification_policy = (
            verification_provider,
            verification_policy,
        )
        if not callable(execution_guard):
            raise ContractError(
                "external execution guard is mandatory; no direct-execution fallback"
            )
        if not callable(rollback_guard):
            raise ContractError("external rollback guard is mandatory")
        self.rollback_guard = rollback_guard
        self.execution_guard = execution_guard
        self.objective_verification_provider = objective_verification_provider
        self.clock, self.lifecycle = clock, lifecycle
        self._learning_queue = []
        self._iteration_counter = 0
        audit.append(
            "agent_boot",
            {"identity": identity, "task_class": task_class, "lifecycle": lifecycle},
            now=clock(),
        )

    @property
    def learning_queue(self):
        return tuple(self._learning_queue)

    @property
    def iteration_counter(self):
        return self._iteration_counter

    @property
    def counter(self):
        return self._iteration_counter

    def drain_learning_queue(self) -> tuple:
        """Host archival: drain and clear the learning evidence queue before the 10,000-item cap."""
        items = tuple(self._learning_queue)
        self._learning_queue.clear()
        return items

    def record_evidence(self, outcome):
        if len(self._learning_queue) >= 10000:
            raise ContractError("learning evidence queue full; host must archive")
        self._learning_queue.append(outcome)

    def run(self, objective, cognition, plan):
        if len(self._learning_queue) >= 10000:
            raise ContractError("archive evidence before accepting more tasks")
        infer_real_objective(objective, self.audit, now=self.clock())
        outcome = operational_loop(self, objective, cognition, plan)
        self._iteration_counter += outcome.counter
        return outcome


def frontier_main(agent, objective, cognition, plan):
    """No second unbudgeted retry and no qualification/elevation call."""
    return agent.run(objective, cognition, plan)
