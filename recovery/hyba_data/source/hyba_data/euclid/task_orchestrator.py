"""
EUCLID Task Orchestrator
=========================

The layer above delegation and below federation. A scheduler that lets EUCLID:
  - Break a large research goal into subtasks
  - Delegate each subtask to the correct organ via the DelegationController
  - Collect partial results
  - Run coherence/truth/causal/feedback gates
  - Integrate only validated results
  - Continue until the research goal is complete

This is the difference between:
  - delegation (single task → single organ), and
  - autonomous research execution (multi-step goal → coordinated organs)

Architecture:
  ResearchGoal → GoalDecomposer → Subtask DAG →
  ExecutionScheduler → DelegationController → IntegrationAggregator →
  GoalCompletionEvaluator

Author: EUCLID Organism CNS
Status: IMPLEMENTED — INTERNAL
Date: 19 July 2026
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from euclid.euclid_delegation import (
    ResearchDomain,
    DelegationTask,
    DelegationResult,
    DelegationVerdict,
    DelegationController,
    DelegationChronicle,
    IntegrationAssessment,
    EvidenceSource,
    create_organ,
    delegation_health_report,
)


# =============================================================================
# Orchestrator Types
# =============================================================================


class SubtaskStatus(Enum):
    PENDING = "pending"
    DELEGATED = "delegated"
    ACCEPTED = "accepted"
    VETOED = "vetoed"
    FALLBACK_SUCCEEDED = "fallback_succeeded"
    FAILED = "failed"


class GoalStatus(Enum):
    CREATED = "created"
    IN_PROGRESS = "in_progress"
    PARTIALLY_COMPLETE = "partially_complete"
    COMPLETE = "complete"
    FAILED = "failed"
    ABORTED = "aborted"


class SubtaskDependency(Enum):
    """How a subtask depends on its predecessors."""
    REQUIRES_ALL = "requires_all"        # All predecessors must succeed
    REQUIRES_ANY = "requires_any"         # At least one must succeed
    OPTIONAL = "optional"                  # Predecessors are informative only


@dataclass
class Subtask:
    """A single unit of work within a research goal."""
    subtask_id: str
    domain: ResearchDomain
    payload: Dict[str, Any]
    description: str
    dependencies: List[str]              # Subtask IDs this depends on
    dependency_mode: SubtaskDependency = SubtaskDependency.REQUIRES_ALL
    status: SubtaskStatus = SubtaskStatus.PENDING
    priority: int = 0
    max_retries: int = 2
    retry_count: int = 0
    assigned_organ_id: Optional[str] = None
    result: Optional[DelegationResult] = None
    assessment: Optional[IntegrationAssessment] = None
    chronicle_entry: Optional[DelegationChronicle] = None
    created_at: float = 0.0
    completed_at: Optional[float] = None
    evidence_hash: Optional[str] = None

    def can_execute(self, completed_subtasks: Dict[str, Subtask]) -> Tuple[bool, str]:
        """Check if dependencies are satisfied."""
        if not self.dependencies:
            return (True, "No dependencies.")

        dep_statuses = {}
        for dep_id in self.dependencies:
            dep = completed_subtasks.get(dep_id)
            if dep is None:
                return (False, f"Dependency {dep_id} not yet executed.")
            dep_statuses[dep_id] = dep.status

        if self.dependency_mode == SubtaskDependency.REQUIRES_ALL:
            all_succeeded = all(
                dep_statuses[d] in (SubtaskStatus.ACCEPTED, SubtaskStatus.FALLBACK_SUCCEEDED)
                for d in self.dependencies
            )
            if not all_succeeded:
                failed = [d for d in self.dependencies
                          if dep_statuses[d] not in (SubtaskStatus.ACCEPTED, SubtaskStatus.FALLBACK_SUCCEEDED)]
                return (False, f"Dependencies not satisfied: {failed}")
            return (True, "All dependencies satisfied.")

        elif self.dependency_mode == SubtaskDependency.REQUIRES_ANY:
            any_succeeded = any(
                dep_statuses[d] in (SubtaskStatus.ACCEPTED, SubtaskStatus.FALLBACK_SUCCEEDED)
                for d in self.dependencies
            )
            if not any_succeeded:
                return (False, "No dependency has succeeded.")
            return (True, "At least one dependency satisfied.")

        else:  # OPTIONAL
            return (True, "Dependencies are optional.")


@dataclass
class ResearchGoal:
    """
    A research goal — the top-level unit of work for the Task Orchestrator.

    A goal is broken into subtasks forming a DAG. The orchestrator executes
    them in dependency order, delegating each to the correct organ, running
    all integration gates, and only integrating validated results.
    """
    goal_id: str
    description: str
    subtasks: Dict[str, Subtask] = field(default_factory=dict)
    status: GoalStatus = GoalStatus.CREATED
    created_at: float = 0.0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    total_subtasks: int = 0
    accepted_count: int = 0
    vetoed_count: int = 0
    fallback_count: int = 0
    failed_count: int = 0
    goal_hash: Optional[str] = None
    origin: str = "CNS"

    @property
    def completion_ratio(self) -> float:
        if self.total_subtasks == 0:
            return 0.0
        completed = self.accepted_count + self.fallback_count
        return completed / self.total_subtasks

    @property
    def all_done(self) -> bool:
        return self.completion_ratio >= 1.0


# =============================================================================
# Goal Decomposer
# =============================================================================


class GoalDecomposer:
    """
    Decomposes a research goal into a DAG of subtasks.

    Each subtask is assigned a domain, payload, and dependencies.
    The decomposer can be extended with domain-specific decomposition
    strategies.
    """

    def __init__(self) -> None:
        self._decomposers: Dict[ResearchDomain, Callable] = {}
        self._subtask_counter: int = 0

    def register_decomposer(
        self, domain: ResearchDomain, decomposer: Callable[[Dict[str, Any]], List[Dict[str, Any]]]
    ) -> None:
        """Register a domain-specific decomposition function."""
        self._decomposers[domain] = decomposer

    def decompose(
        self,
        goal_description: str,
        domains: List[ResearchDomain],
        goal_payload: Optional[Dict[str, Any]] = None,
        dependency_graph: Optional[Dict[str, List[str]]] = None,
    ) -> ResearchGoal:
        """
        Decompose a research goal description into a ResearchGoal with subtasks.

        Args:
            goal_description: Human-readable description of the goal
            domains: Ordered list of domains to decompose into
            goal_payload: Optional shared payload for all subtasks
            dependency_graph: Optional explicit dependency map (subtask_name → [dep_names])

        Returns:
            ResearchGoal with populated subtasks
        """
        goal_id = f"goal_{int(time.time())}_{hashlib.sha256(goal_description.encode()).hexdigest()[:8]}"
        goal = ResearchGoal(
            goal_id=goal_id,
            description=goal_description,
            created_at=time.time(),
        )

        subtasks: Dict[str, Subtask] = {}

        for i, domain in enumerate(domains):
            subtask_id = f"{goal_id}_subtask_{i:02d}"

            # Use domain-specific decomposer if available
            if domain in self._decomposers:
                decomposed = self._decomposers[domain](goal_payload or {})
                if isinstance(decomposed, list) and decomposed:
                    # Create multiple subtasks from decomposition
                    for j, sub_payload in enumerate(decomposed):
                        sub_id = f"{subtask_id}_{j:02d}"
                        deps = self._resolve_dependencies(
                            sub_id, dependency_graph or {}, subtasks, i
                        )
                        subtasks[sub_id] = Subtask(
                            subtask_id=sub_id,
                            domain=domain,
                            payload=sub_payload,
                            description=f"{goal_description} — {domain.value} [{j}]",
                            dependencies=deps,
                            created_at=time.time(),
                        )
                    continue

            # Simple: one subtask per domain
            deps = self._resolve_dependencies(subtask_id, dependency_graph or {}, subtasks, i)
            subtask = Subtask(
                subtask_id=subtask_id,
                domain=domain,
                payload=goal_payload or {"goal": goal_description},
                description=f"{goal_description} — {domain.value}",
                dependencies=deps,
                created_at=time.time(),
            )
            subtasks[subtask_id] = subtask

        goal.subtasks = subtasks
        goal.total_subtasks = len(subtasks)

        # Compute goal hash
        payload = json.dumps({
            "goal_id": goal.goal_id,
            "description": goal.description,
            "subtask_ids": sorted(subtasks.keys()),
            "created_at": goal.created_at,
        }, sort_keys=True)
        goal.goal_hash = hashlib.sha256(payload.encode()).hexdigest()

        return goal

    @staticmethod
    def _resolve_dependencies(
        subtask_id: str,
        dependency_graph: Dict[str, List[str]],
        existing_subtasks: Dict[str, Subtask],
        current_index: int,
    ) -> List[str]:
        """Resolve dependencies for a subtask."""
        # Check explicit dependency graph
        if subtask_id in dependency_graph:
            return dependency_graph[subtask_id]

        # Default: depend on all previous subtasks in the linear order
        deps = []
        for st in existing_subtasks.values():
            deps.append(st.subtask_id)
        return deps


# =============================================================================
# Integration Aggregator
# =============================================================================


@dataclass
class AggregatedResult:
    """The aggregated output of a completed research goal."""
    goal_id: str
    goal_description: str
    status: GoalStatus
    subtask_results: Dict[str, Subtask]
    accepted_subtasks: List[str]
    vetoed_subtasks: List[str]
    fallback_subtasks: List[str]
    failed_subtasks: List[str]
    completion_ratio: float
    all_external_evidence: bool
    any_external_evidence: bool
    evidence_sources: Dict[str, EvidenceSource]
    aggregated_hash: str
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    execution_time: Optional[float] = None


class IntegrationAggregator:
    """
    Aggregates subtask results into a unified goal outcome.

    Produces an AggregatedResult that captures:
    - Which subtasks succeeded, vetoed, or used fallback
    - Whether all evidence is external or any is external
    - A hash-chained aggregate
    """

    def aggregate(self, goal: ResearchGoal) -> AggregatedResult:
        accepted: List[str] = []
        vetoed: List[str] = []
        fallback: List[str] = []
        failed: List[str] = []
        evidence_sources: Dict[str, EvidenceSource] = {}

        for st_id, st in goal.subtasks.items():
            if st.status == SubtaskStatus.ACCEPTED:
                accepted.append(st_id)
            elif st.status == SubtaskStatus.FALLBACK_SUCCEEDED:
                fallback.append(st_id)
            elif st.status == SubtaskStatus.VETOED:
                vetoed.append(st_id)
            else:
                failed.append(st_id)

            if st.assessment is not None:
                # Collect the strongest evidence source from each subtask
                sources = [
                    st.assessment.coherence_source,
                    st.assessment.truth_source,
                    st.assessment.causal_source,
                    st.assessment.feedback_source,
                ]
                if EvidenceSource.EXTERNAL_SUBSYSTEM in sources:
                    evidence_sources[st_id] = EvidenceSource.EXTERNAL_SUBSYSTEM
                elif EvidenceSource.INTERNAL_HEURISTIC in sources:
                    evidence_sources[st_id] = EvidenceSource.INTERNAL_HEURISTIC
                else:
                    evidence_sources[st_id] = EvidenceSource.NONE

        all_external = all(
            s == EvidenceSource.EXTERNAL_SUBSYSTEM
            for s in evidence_sources.values()
        ) if evidence_sources else False

        any_external = any(
            s == EvidenceSource.EXTERNAL_SUBSYSTEM
            for s in evidence_sources.values()
        )

        # Determine goal status
        if goal.completion_ratio >= 1.0:
            goal_status = GoalStatus.COMPLETE
        elif goal.accepted_count + goal.fallback_count > 0:
            goal_status = GoalStatus.PARTIALLY_COMPLETE
        elif goal.failed_count + goal.vetoed_count == goal.total_subtasks:
            goal_status = GoalStatus.FAILED
        else:
            goal_status = goal.status

        # Aggregate hash
        agg_payload = json.dumps({
            "goal_id": goal.goal_id,
            "status": goal_status.value,
            "accepted": sorted(accepted),
            "vetoed": sorted(vetoed),
            "fallback": sorted(fallback),
            "evidence_sources": {k: v.value for k, v in evidence_sources.items()},
        }, sort_keys=True)
        aggregated_hash = hashlib.sha256(agg_payload.encode()).hexdigest()

        return AggregatedResult(
            goal_id=goal.goal_id,
            goal_description=goal.description,
            status=goal_status,
            subtask_results=dict(goal.subtasks),
            accepted_subtasks=accepted,
            vetoed_subtasks=vetoed,
            fallback_subtasks=fallback,
            failed_subtasks=failed,
            completion_ratio=goal.completion_ratio,
            all_external_evidence=all_external,
            any_external_evidence=any_external,
            evidence_sources=evidence_sources,
            aggregated_hash=aggregated_hash,
            started_at=goal.started_at,
            completed_at=goal.completed_at,
            execution_time=(
                (goal.completed_at - goal.started_at)
                if goal.completed_at and goal.started_at else None
            ),
        )


# =============================================================================
# Execution Scheduler
# =============================================================================


class ExecutionScheduler:
    """
    Schedules subtask execution respecting the DAG dependency order.

    At each step:
    1. Find all subtasks whose dependencies are satisfied
    2. Execute them via the DelegationController
    3. On veto: retry with backoff, attempt fallback organ
    4. On success: record result, update goal state
    5. Repeat until all executable subtasks are done
    """

    def __init__(self, delegation_controller: DelegationController) -> None:
        self.controller = delegation_controller
        self._execution_log: List[Dict[str, Any]] = []

    def schedule(self, goal: ResearchGoal) -> ResearchGoal:
        """
        Execute a research goal's subtasks in dependency order.

        Modifies the goal in place and returns it.
        """
        goal.status = GoalStatus.IN_PROGRESS
        goal.started_at = time.time()

        remaining = set(goal.subtasks.keys())
        executed: Dict[str, Subtask] = {}
        max_iterations = len(remaining) * 3  # Safety bound
        iteration = 0

        while remaining and iteration < max_iterations:
            iteration += 1
            progress_made = False

            # Find executable subtasks (dependencies satisfied)
            executable = []
            still_blocked = []
            for st_id in list(remaining):
                st = goal.subtasks[st_id]
                can_exec, reason = st.can_execute(executed)
                if can_exec:
                    executable.append(st_id)
                else:
                    still_blocked.append((st_id, reason))

            if not executable:
                if still_blocked and not progress_made:
                    # Deadlock: remaining subtasks are permanently blocked
                    # Mark remaining as failed
                    for st_id in remaining:
                        st = goal.subtasks[st_id]
                        st.status = SubtaskStatus.FAILED
                        goal.failed_count += 1
                    break
                break

            # Execute executable subtasks
            for st_id in executable:
                st = goal.subtasks[st_id]
                self._execute_subtask(st, goal)
                remaining.discard(st_id)
                executed[st_id] = st
                progress_made = True

        # Finalize goal state
        if goal.all_done:
            goal.status = GoalStatus.COMPLETE
        elif goal.accepted_count + goal.fallback_count > 0:
            goal.status = GoalStatus.PARTIALLY_COMPLETE
        else:
            goal.status = GoalStatus.FAILED

        goal.completed_at = time.time()
        return goal

    def _execute_subtask(self, subtask: Subtask, goal: ResearchGoal) -> None:
        """Execute a single subtask through the delegation pipeline."""
        task = DelegationTask(
            task_id=subtask.subtask_id,
            domain=subtask.domain,
            payload=subtask.payload,
            origin=f"TaskOrchestrator::{goal.goal_id}",
            created_at=time.time(),
        )

        subtask.status = SubtaskStatus.DELEGATED
        result, assessment, chronicle = self.controller.delegate(task)

        subtask.chronicle_entry = chronicle

        if result is not None and assessment.verdict == DelegationVerdict.ACCEPTED:
            subtask.status = SubtaskStatus.ACCEPTED
            subtask.result = result
            subtask.assessment = assessment
            subtask.assigned_organ_id = result.organ_id
            subtask.completed_at = time.time()
            subtask.evidence_hash = assessment.assessment_hash
            goal.accepted_count += 1

        elif result is not None and assessment.verdict == DelegationVerdict.VETOED:
            # The delegation controller already attempted fallback routing.
            # Check if the chronicle shows a different organ (fallback succeeded)
            if chronicle.organ_id != "__none__" and chronicle.integration_assessment.verdict == DelegationVerdict.ACCEPTED:
                subtask.status = SubtaskStatus.FALLBACK_SUCCEEDED
                subtask.result = result
                subtask.assessment = assessment
                subtask.assigned_organ_id = chronicle.organ_id
                subtask.completed_at = time.time()
                goal.fallback_count += 1
            else:
                # Retry logic
                if subtask.retry_count < subtask.max_retries:
                    subtask.retry_count += 1
                    # Retry — the controller may have backoff applied
                    self._execute_subtask(subtask, goal)
                    return
                else:
                    subtask.status = SubtaskStatus.VETOED
                    subtask.assessment = assessment
                    subtask.completed_at = time.time()
                    goal.vetoed_count += 1
        else:
            # Complete failure
            if subtask.retry_count < subtask.max_retries:
                subtask.retry_count += 1
                self._execute_subtask(subtask, goal)
                return
            subtask.status = SubtaskStatus.FAILED
            subtask.assessment = assessment
            subtask.completed_at = time.time()
            goal.failed_count += 1

        # Log execution
        self._execution_log.append({
            "subtask_id": subtask.subtask_id,
            "status": subtask.status.value,
            "organ_id": subtask.assigned_organ_id,
            "verdict": assessment.verdict.value if assessment else "unknown",
            "timestamp": time.time(),
        })

    @property
    def execution_log(self) -> List[Dict[str, Any]]:
        return list(self._execution_log)


# =============================================================================
# Goal Completion Evaluator
# =============================================================================


class GoalCompletionEvaluator:
    """
    Evaluates whether a completed goal meets the acceptance criteria.

    A goal is considered successfully completed when:
    - completion_ratio reaches 1.0 (or configured threshold)
    - At minimum, critical subtasks (marked with priority >= critical_threshold) passed
    - The aggregated evidence meets the required evidence bar
    """

    def __init__(
        self,
        completion_threshold: float = 1.0,
        critical_priority: int = 2,
        require_external_evidence: bool = False,
    ) -> None:
        self.completion_threshold = completion_threshold
        self.critical_priority = critical_priority
        self.require_external_evidence = require_external_evidence

    def evaluate(self, aggregated: AggregatedResult) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Evaluate goal completion.

        Returns (passed: bool, reason: str, details: dict).
        """
        checks = {}

        # Check 1: Completion ratio
        ratio_ok = aggregated.completion_ratio >= self.completion_threshold
        checks["completion_ratio"] = {
            "passed": ratio_ok,
            "value": aggregated.completion_ratio,
            "threshold": self.completion_threshold,
        }

        # Check 2: Critical subtasks
        critical_passed = True
        critical_failures = []
        for st_id, st in aggregated.subtask_results.items():
            if st.priority >= self.critical_priority:
                if st.status not in (SubtaskStatus.ACCEPTED, SubtaskStatus.FALLBACK_SUCCEEDED):
                    critical_passed = False
                    critical_failures.append(st_id)
        checks["critical_subtasks"] = {
            "passed": critical_passed,
            "failures": critical_failures,
        }

        # Check 3: Evidence bar (if required)
        evidence_ok = True
        if self.require_external_evidence:
            evidence_ok = aggregated.all_external_evidence
        checks["external_evidence"] = {
            "passed": evidence_ok,
            "required": self.require_external_evidence,
            "all_external": aggregated.all_external_evidence,
            "any_external": aggregated.any_external_evidence,
        }

        all_passed = ratio_ok and critical_passed and evidence_ok

        if not all_passed:
            failures = []
            if not ratio_ok:
                failures.append(f"completion ratio {aggregated.completion_ratio:.2f} < {self.completion_threshold}")
            if not critical_passed:
                failures.append(f"critical subtasks failed: {critical_failures}")
            if not evidence_ok:
                failures.append("external evidence required but not all gates carry EXTERNAL evidence")
            return (False, f"Goal evaluation FAILED: {'; '.join(failures)}", checks)

        return (True, "Goal evaluation PASSED: all criteria satisfied.", checks)


# =============================================================================
# Task Orchestrator (Main Facade)
# =============================================================================


class TaskOrchestrator:
    """
    The main Task Orchestrator facade.

    Wires GoalDecomposer, ExecutionScheduler, IntegrationAggregator, and
    GoalCompletionEvaluator into a single pipeline:

        goal_description → decompose → schedule → aggregate → evaluate

    Usage:
        orchestrator = TaskOrchestrator(delegation_controller)
        aggregated = orchestrator.execute(
            "Probe the PHI-Space boundary for O(log N) search evidence",
            domains=[ResearchDomain.MATHEMATICAL_ENGINE, ResearchDomain.EMERGENCE_ENGINE],
        )
    """

    def __init__(
        self,
        delegation_controller: DelegationController,
        completion_threshold: float = 1.0,
        require_external_evidence: bool = False,
    ) -> None:
        self.controller = delegation_controller
        self.decomposer = GoalDecomposer()
        self.scheduler = ExecutionScheduler(delegation_controller)
        self.aggregator = IntegrationAggregator()
        self.evaluator = GoalCompletionEvaluator(
            completion_threshold=completion_threshold,
            require_external_evidence=require_external_evidence,
        )
        self._completed_goals: List[ResearchGoal] = []
        self._aggregated_results: List[AggregatedResult] = []

    def execute(
        self,
        goal_description: str,
        domains: List[ResearchDomain],
        goal_payload: Optional[Dict[str, Any]] = None,
        dependency_graph: Optional[Dict[str, List[str]]] = None,
    ) -> Tuple[ResearchGoal, AggregatedResult, bool, str]:
        """
        Execute a research goal end-to-end.

        Returns (goal, aggregated_result, passed, evaluation_reason).
        """
        # Stage 1: Decompose
        goal = self.decomposer.decompose(
            goal_description, domains, goal_payload, dependency_graph
        )

        # Stage 2: Schedule and execute
        goal = self.scheduler.schedule(goal)
        self._completed_goals.append(goal)

        # Stage 3: Aggregate
        aggregated = self.aggregator.aggregate(goal)
        self._aggregated_results.append(aggregated)

        # Stage 4: Evaluate
        passed, reason, checks = self.evaluator.evaluate(aggregated)

        return (goal, aggregated, passed, reason)

    def execute_with_custom_decomposition(
        self,
        goal: ResearchGoal,
    ) -> Tuple[ResearchGoal, AggregatedResult, bool, str]:
        """Execute a pre-composed ResearchGoal (custom decomposition)."""
        goal = self.scheduler.schedule(goal)
        self._completed_goals.append(goal)
        aggregated = self.aggregator.aggregate(goal)
        self._aggregated_results.append(aggregated)
        passed, reason, checks = self.evaluator.evaluate(aggregated)
        return (goal, aggregated, passed, reason)

    @property
    def completed_goals(self) -> List[ResearchGoal]:
        return list(self._completed_goals)

    @property
    def aggregated_results(self) -> List[AggregatedResult]:
        return list(self._aggregated_results)

    @property
    def execution_log(self) -> List[Dict[str, Any]]:
        return self.scheduler.execution_log

    def health_report(self) -> Dict[str, Any]:
        delegation_health = delegation_health_report(self.controller)
        return {
            "subsystem": "task_orchestrator",
            "status": delegation_health["status"],
            "completed_goals": len(self._completed_goals),
            "total_subtasks_executed": len(self.execution_log),
            "delegation": delegation_health,
            "last_goal_hash": (
                self._completed_goals[-1].goal_hash if self._completed_goals else None
            ),
        }
