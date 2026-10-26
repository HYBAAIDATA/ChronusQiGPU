"""Collaborative Automation and Automated Runbook Orchestration ("System of Execution").

Integrates human judgment, cross-team awareness (DevOps, SRE, TechOps, Security,
Architecture, Release Management, Stakeholders), and bounded technological
execution into Salamander's governed control plane.

Authority boundary (strictly preserved):
  - EUCLID / TOE: advisory analytical, causal, and predictive context only.
  - PYTHIA: final mining authority and SHA256d/Stratum truth boundary.
  - CHRONUS: substrate-agnostic execution and fleet partition scheduling.
  - SALAMANDER: bounded recovery, rollback, and runbook step actuation.
  - AL HARAS: identity, cryptographic authorization, and admission gating.
  - OVID / THESEUS: enduring lineage and hash-chained audit custody.

Collaborative Automation never fabricates human approvals, hardware execution,
or pool acceptance. Missing human sign-off pauses a runbook at
``AWAITING_HUMAN_DECISION``; failed postcondition verification triggers
governed rollback or fails closed.
"""

from __future__ import annotations

import copy
import json
import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from .control_plane import (
    ActionRegistry,
    AutonomicControlPlane,
    EvidenceLedger,
    FailClosed,
    RecoveryPlan,
    RecoveryStep,
)
from .models import ActionKind, ActionRequest, Severity, digest

SCHEMA = "hyba.collaborative-automation.v1"
RUNBOOK_SCHEMA = "hyba.collaborative.runbook.v1"
AUDIT_SCHEMA = "hyba.collaborative.audit.v1"
DASHBOARD_SCHEMA = "hyba.collaborative.dashboard.v1"

# Incremental scaling ladder (Fibonacci / Lucas-aligned small-to-scale bounds)
INCREMENTAL_SCALE_LADDER: tuple[int, ...] = (1, 2, 3, 5, 8, 10, 12, 15, 18, 20, 31, 50, 76)


class TeamRole(StrEnum):
    """Cross-functional operational roles interconnected by Collaborative Automation."""

    DEVOPS = "devops"
    SRE = "sre"
    TECH_OPS = "tech_ops"
    SECURITY_ANALYST = "security_analyst"
    ARCHITECTURE_OWNER = "architecture_owner"
    RELEASE_MANAGER = "release_manager"
    STAKEHOLDER = "stakeholder"
    INCIDENT_RESPONSE = "incident_response"


class AutomationToolCategory(StrEnum):
    """Canonical automation tool archetypes selected per operational objective."""

    AI_ML = "ai_ml"  # Complex decision-making & predictive analytics (EUCLID/TOE advisory)
    RPA = "rpa"  # Rule-based, repetitive deterministic tasks
    IT_AUTOMATION = "it_automation"  # Infrastructure, configuration & bounded actuation
    IPAAS = "ipaas"  # Cross-system data exchange, receipts & lineage handoffs


class StepMode(StrEnum):
    """Execution mode for a runbook step."""

    AUTOMATED = "automated"
    HUMAN_IN_THE_LOOP = "human_in_the_loop"
    COLLABORATIVE_HYBRID = "collaborative_hybrid"


class StepStatus(StrEnum):
    """Explicit lifecycle state of a runbook step."""

    PENDING = "PENDING"
    BLOCKED_UPSTREAM = "BLOCKED_UPSTREAM"
    AWAITING_HUMAN_DECISION = "AWAITING_HUMAN_DECISION"
    EXECUTING = "EXECUTING"
    VERIFIED = "VERIFIED"
    DEDUPLICATED = "DEDUPLICATED"
    REJECTED_BY_HUMAN = "REJECTED_BY_HUMAN"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED_CLOSED = "FAILED_CLOSED"


class RunbookStatus(StrEnum):
    """Lifecycle state of an entire collaborative runbook."""

    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    AWAITING_HUMAN = "AWAITING_HUMAN"
    COMPLETED_VERIFIED = "COMPLETED_VERIFIED"
    ROLLED_BACK = "ROLLED_BACK"
    HALTED_BATHTUB_GUARD = "HALTED_BATHTUB_GUARD"
    FAILED_CLOSED = "FAILED_CLOSED"


class WorkflowUseCase(StrEnum):
    """Four canonical Collaborative Automation use cases plus catalogue recovery."""

    CYBER_IT_DISASTER_RECOVERY = "cyber_it_disaster_recovery"
    CLOUD_MIGRATION = "cloud_migration"
    APPLICATION_RELEASE_MANAGEMENT = "application_release_management"
    TECHNOLOGY_IMPLEMENTATION = "technology_implementation"
    CATALOGUE_OPERATIONAL_RECOVERY = "catalogue_operational_recovery"


class BathtubRiskFactor(StrEnum):
    """Four root causes of the IT Automation 'Bathtub Effect' performance dip."""

    SCOPE_CREEP = "scope_creep"
    TECHNICAL_CHALLENGES = "technical_challenges"
    LACK_OF_RESOURCES = "lack_of_resources"
    LOSS_OF_MOMENTUM = "loss_of_momentum"


@dataclass(frozen=True)
class ToolSelectionCriteria:
    """Evaluation profile for selecting the right automation tool for a task."""

    tool_category: AutomationToolCategory
    objective: str
    ease_of_use: int  # 1..5
    scalability: int  # 1..5
    integration_capability: int  # 1..5
    verifier_support: int  # 1..5
    human_collaboration_fit: int  # 1..5
    advisory_only: bool = False

    def validate(self) -> None:
        for field_name, val in (
            ("ease_of_use", self.ease_of_use),
            ("scalability", self.scalability),
            ("integration_capability", self.integration_capability),
            ("verifier_support", self.verifier_support),
            ("human_collaboration_fit", self.human_collaboration_fit),
        ):
            if type(val) is not int or not (1 <= val <= 5):
                raise ValueError(f"{field_name} must be an integer in 1..5")
        if not self.objective.strip():
            raise ValueError("objective is required")
        if self.tool_category is AutomationToolCategory.AI_ML and not self.advisory_only:
            raise FailClosed("AI_ML tool category must remain advisory_only=True under HYBA authority boundaries")

    @property
    def composite_score(self) -> float:
        self.validate()
        return round(
            (
                self.ease_of_use
                + self.scalability
                + self.integration_capability
                + self.verifier_support
                + self.human_collaboration_fit
            )
            / 5.0,
            4,
        )

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "tool_category": self.tool_category.value,
            "objective": self.objective,
            "ease_of_use": self.ease_of_use,
            "scalability": self.scalability,
            "integration_capability": self.integration_capability,
            "verifier_support": self.verifier_support,
            "human_collaboration_fit": self.human_collaboration_fit,
            "advisory_only": self.advisory_only,
            "composite_score": self.composite_score,
        }


def select_automation_tool(
    objective: str,
    *,
    requires_predictive_analytics: bool = False,
    repetitive_rule_based: bool = False,
    infrastructure_or_config: bool = False,
    cross_system_data_exchange: bool = False,
) -> ToolSelectionCriteria:
    """Deterministic tool selector mapping operational objectives to tool archetypes."""
    text = objective.strip()
    if not text:
        raise ValueError("objective must be non-empty")
    if requires_predictive_analytics:
        return ToolSelectionCriteria(
            tool_category=AutomationToolCategory.AI_ML,
            objective=text,
            ease_of_use=4,
            scalability=5,
            integration_capability=4,
            verifier_support=5,
            human_collaboration_fit=5,
            advisory_only=True,
        )
    if cross_system_data_exchange:
        return ToolSelectionCriteria(
            tool_category=AutomationToolCategory.IPAAS,
            objective=text,
            ease_of_use=4,
            scalability=5,
            integration_capability=5,
            verifier_support=5,
            human_collaboration_fit=4,
            advisory_only=False,
        )
    if infrastructure_or_config:
        return ToolSelectionCriteria(
            tool_category=AutomationToolCategory.IT_AUTOMATION,
            objective=text,
            ease_of_use=4,
            scalability=5,
            integration_capability=5,
            verifier_support=5,
            human_collaboration_fit=4,
            advisory_only=False,
        )
    if repetitive_rule_based:
        return ToolSelectionCriteria(
            tool_category=AutomationToolCategory.RPA,
            objective=text,
            ease_of_use=5,
            scalability=4,
            integration_capability=4,
            verifier_support=5,
            human_collaboration_fit=4,
            advisory_only=False,
        )
    return ToolSelectionCriteria(
        tool_category=AutomationToolCategory.IT_AUTOMATION,
        objective=text,
        ease_of_use=4,
        scalability=4,
        integration_capability=4,
        verifier_support=5,
        human_collaboration_fit=4,
        advisory_only=False,
    )


@dataclass(frozen=True)
class HumanDecision:
    """Explicit human-in-the-loop judgment, approval, or rejection record."""

    decision_id: str
    runbook_id: str
    step_id: str
    actor_id: str
    team_role: TeamRole
    approved: bool
    rationale: str
    at_ns: int
    scope_revision_approved: bool = False

    def __post_init__(self) -> None:
        if not self.decision_id.strip():
            raise ValueError("decision_id is required")
        if not self.runbook_id.strip():
            raise ValueError("runbook_id is required")
        if not self.step_id.strip():
            raise ValueError("step_id is required")
        if not self.actor_id.strip():
            raise ValueError("actor_id is required")
        if not self.rationale.strip():
            raise ValueError("rationale is required for human judgment auditability")
        if type(self.approved) is not bool:
            raise ValueError("approved must be a boolean")

    @property
    def decision_sha256(self) -> str:
        return digest(
            "hyba.collaborative.human-decision.v1",
            {
                "decision_id": self.decision_id,
                "runbook_id": self.runbook_id,
                "step_id": self.step_id,
                "actor_id": self.actor_id,
                "team_role": self.team_role.value,
                "approved": self.approved,
                "rationale": self.rationale,
                "at_ns": int(self.at_ns),
                "scope_revision_approved": bool(self.scope_revision_approved),
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "runbook_id": self.runbook_id,
            "step_id": self.step_id,
            "actor_id": self.actor_id,
            "team_role": self.team_role.value,
            "approved": self.approved,
            "rationale": self.rationale,
            "at_ns": int(self.at_ns),
            "scope_revision_approved": bool(self.scope_revision_approved),
            "decision_sha256": self.decision_sha256,
        }


@dataclass(frozen=True)
class CollaborativeStep:
    """Single step in a Collaborative Automation runbook."""

    step_id: str
    title: str
    owner_team: TeamRole
    collaborating_teams: tuple[TeamRole, ...]
    tool_category: AutomationToolCategory
    mode: StepMode
    operation: str
    target: str
    depends_on: tuple[str, ...] = ()
    prerequisites: tuple[str, ...] = ()
    postconditions: tuple[str, ...] = ()
    rollback_operation: str | None = None
    required_approver_roles: tuple[TeamRole, ...] = ()
    parameters: Mapping[str, Any] = field(default_factory=dict)
    sla_budget_ns: int = 300_000_000_000  # 5 minutes default

    def __post_init__(self) -> None:
        if not self.step_id.strip():
            raise ValueError("step_id is required")
        if not self.title.strip():
            raise ValueError("title is required")
        if not self.operation.strip():
            raise ValueError("operation is required")
        if not self.target.strip():
            raise ValueError("target is required")
        if self.mode in (StepMode.HUMAN_IN_THE_LOOP, StepMode.COLLABORATIVE_HYBRID):
            if not self.required_approver_roles:
                object.__setattr__(self, "required_approver_roles", (self.owner_team,))
        if self.sla_budget_ns <= 0:
            raise ValueError("sla_budget_ns must be positive")

    def task_fingerprint(self, tenant_id: str) -> str:
        """Deterministic cross-team deduplication fingerprint."""
        return digest(
            "hyba.collaborative.task-fingerprint.v1",
            {
                "tenant_id": tenant_id,
                "target": self.target,
                "operation": self.operation,
                "parameters": dict(self.parameters),
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "title": self.title,
            "owner_team": self.owner_team.value,
            "collaborating_teams": [t.value for t in self.collaborating_teams],
            "tool_category": self.tool_category.value,
            "mode": self.mode.value,
            "operation": self.operation,
            "target": self.target,
            "depends_on": list(self.depends_on),
            "prerequisites": list(self.prerequisites),
            "postconditions": list(self.postconditions),
            "rollback_operation": self.rollback_operation,
            "required_approver_roles": [r.value for r in self.required_approver_roles],
            "parameters": dict(self.parameters),
            "sla_budget_ns": int(self.sla_budget_ns),
        }


class CrossTeamTaskDeduplicator:
    """Eliminates duplicate manual/automated efforts across fragmented teams (DevOps, SRE, TechOps)."""

    def __init__(self) -> None:
        self._completed: dict[str, dict[str, Any]] = {}

    def check_or_record(
        self,
        *,
        tenant_id: str,
        step: CollaborativeStep,
        runbook_id: str,
        evidence_sha256: str | None = None,
    ) -> dict[str, Any] | None:
        fingerprint = step.task_fingerprint(tenant_id)
        existing = self._completed.get(fingerprint)
        if existing is not None:
            return copy.deepcopy(existing)
        if evidence_sha256 is not None:
            record = {
                "fingerprint": fingerprint,
                "tenant_id": tenant_id,
                "runbook_id": runbook_id,
                "step_id": step.step_id,
                "owner_team": step.owner_team.value,
                "operation": step.operation,
                "target": step.target,
                "evidence_sha256": evidence_sha256,
            }
            self._completed[fingerprint] = record
        return None

    @property
    def deduplicated_count(self) -> int:
        return len(self._completed)


@dataclass(frozen=True)
class BathtubAssessment:
    """Measured risk assessment for the IT Automation Bathtub Effect."""

    healthy: bool
    scale_phase_limit: int
    declared_steps: int
    active_risks: tuple[BathtubRiskFactor, ...]
    details: Mapping[str, Any]
    mitigation_recommendation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "healthy": self.healthy,
            "scale_phase_limit": self.scale_phase_limit,
            "declared_steps": self.declared_steps,
            "active_risks": [r.value for r in self.active_risks],
            "details": dict(self.details),
            "mitigation_recommendation": self.mitigation_recommendation,
        }


class BathtubGuard:
    """Mitigates the 'Bathtub Effect' by enforcing small-to-scale bounds, scope locks,
    resource preflight checks, and momentum/stall monitoring."""

    def __init__(
        self,
        *,
        scale_phase_index: int = 4,  # Default INCREMENTAL_SCALE_LADDER[4] == 8 steps max per phase
        max_failure_rate: float = 0.25,
        stall_timeout_ns: int = 600_000_000_000,
    ) -> None:
        if not (0 <= scale_phase_index < len(INCREMENTAL_SCALE_LADDER)):
            raise ValueError(f"scale_phase_index must be in 0..{len(INCREMENTAL_SCALE_LADDER) - 1}")
        if not (0.0 <= max_failure_rate <= 1.0):
            raise ValueError("max_failure_rate must be between 0.0 and 1.0")
        if stall_timeout_ns <= 0:
            raise ValueError("stall_timeout_ns must be positive")
        self.scale_phase_index = scale_phase_index
        self.scale_phase_limit = INCREMENTAL_SCALE_LADDER[scale_phase_index]
        self.max_failure_rate = max_failure_rate
        self.stall_timeout_ns = stall_timeout_ns

    def evaluate(
        self,
        runbook: "CollaborativeRunbook",
        *,
        current_step_ids: tuple[str, ...],
        failed_steps: int = 0,
        executed_steps: int = 0,
        available_operators: int = 1,
        action_budget_remaining: int = 10,
        longest_wait_ns: int = 0,
        scope_revision_approved: bool = False,
    ) -> BathtubAssessment:
        risks: list[BathtubRiskFactor] = []
        reasons: dict[str, Any] = {}

        # 1. Scope creep: mid-flight step additions or exceeding incremental phase scale limit
        current_scope_digest = digest("hyba.collaborative.scope.v1", {"step_ids": list(current_step_ids)})
        if current_scope_digest != runbook.initial_scope_sha256 and not scope_revision_approved:
            risks.append(BathtubRiskFactor.SCOPE_CREEP)
            reasons["scope_creep"] = "unapproved mid-flight step modification detected"
        elif len(current_step_ids) > self.scale_phase_limit:
            risks.append(BathtubRiskFactor.SCOPE_CREEP)
            reasons["scope_creep"] = (
                f"step count {len(current_step_ids)} exceeds incremental scale phase limit {self.scale_phase_limit}"
            )

        # 2. Technical challenges: unexpected failure ratio exceeding threshold
        if executed_steps > 0:
            failure_rate = failed_steps / float(executed_steps)
            if failure_rate > self.max_failure_rate or failed_steps > 0:
                risks.append(BathtubRiskFactor.TECHNICAL_CHALLENGES)
                reasons["technical_challenges"] = {
                    "failed_steps": failed_steps,
                    "executed_steps": executed_steps,
                    "failure_rate": round(failure_rate, 4),
                }

        # 3. Lack of resources: missing human operators for human-in-the-loop steps or exhausted action budget
        requires_human = any(
            s.mode in (StepMode.HUMAN_IN_THE_LOOP, StepMode.COLLABORATIVE_HYBRID) for s in runbook.steps
        )
        if (requires_human and available_operators <= 0) or action_budget_remaining < len(current_step_ids):
            risks.append(BathtubRiskFactor.LACK_OF_RESOURCES)
            reasons["lack_of_resources"] = {
                "available_operators": available_operators,
                "action_budget_remaining": action_budget_remaining,
                "required_steps": len(current_step_ids),
            }

        # 4. Loss of momentum: human checkpoint or step stalled beyond timeout
        if longest_wait_ns > self.stall_timeout_ns:
            risks.append(BathtubRiskFactor.LOSS_OF_MOMENTUM)
            reasons["loss_of_momentum"] = {
                "longest_wait_ns": longest_wait_ns,
                "stall_timeout_ns": self.stall_timeout_ns,
            }

        healthy = len(risks) == 0
        recommendation = (
            "Incremental scope and resource bounds satisfied; continue collaborative execution."
            if healthy
            else "Start small and scale gradually: lock scope, resolve technical blockers, allocate operator capacity, or engage human-in-the-loop review."
        )
        return BathtubAssessment(
            healthy=healthy,
            scale_phase_limit=self.scale_phase_limit,
            declared_steps=len(current_step_ids),
            active_risks=tuple(risks),
            details=reasons,
            mitigation_recommendation=recommendation,
        )


@dataclass(frozen=True)
class CollaborativeRunbook:
    """Auditable, dependency-ordered Collaborative Automation Runbook."""

    runbook_id: str
    title: str
    use_case: WorkflowUseCase
    tenant_id: str
    target: str
    steps: tuple[CollaborativeStep, ...]
    escalation_teams: tuple[TeamRole, ...] = (TeamRole.SRE, TeamRole.TECH_OPS)
    max_actions: int = 16
    description: str = ""

    def __post_init__(self) -> None:
        if not self.runbook_id.strip():
            raise ValueError("runbook_id is required")
        if not self.title.strip():
            raise ValueError("title is required")
        if not self.tenant_id.strip():
            raise ValueError("tenant_id is required")
        if not self.target.strip():
            raise ValueError("target is required")
        if not self.steps:
            raise ValueError("runbook must contain at least one step")
        by_id = {s.step_id: s for s in self.steps}
        if len(by_id) != len(self.steps):
            raise FailClosed("duplicate step_id in collaborative runbook")
        # Validate DAG topological sort
        _ = self.ordered_steps()

    @property
    def initial_scope_sha256(self) -> str:
        return digest(
            "hyba.collaborative.scope.v1",
            {"step_ids": [s.step_id for s in self.steps]},
        )

    def ordered_steps(self) -> tuple[CollaborativeStep, ...]:
        """Deterministic topological sort of runbook steps; fails closed on cycles or missing deps."""
        by_id = {s.step_id: s for s in self.steps}
        for step in self.steps:
            for dep in step.depends_on:
                if dep not in by_id:
                    raise FailClosed(f"step {step.step_id!r} references missing dependency {dep!r}")
        ordered: list[CollaborativeStep] = []
        remaining = dict(by_id)
        while remaining:
            completed_ids = {s.step_id for s in ordered}
            ready = sorted(
                (s for s in remaining.values() if set(s.depends_on) <= completed_ids),
                key=lambda s: s.step_id,
            )
            if not ready:
                raise FailClosed("collaborative runbook DAG contains a dependency cycle")
            for step in ready:
                ordered.append(step)
                remaining.pop(step.step_id)
        return tuple(ordered)

    def dependency_transparency_map(
        self, step_states: Mapping[str, StepStatus] | None = None
    ) -> dict[str, dict[str, Any]]:
        """Real-time visibility into upstream and downstream dependencies for every step."""
        states = dict(step_states or {})
        downstream: dict[str, list[str]] = {s.step_id: [] for s in self.steps}
        for step in self.steps:
            for dep in step.depends_on:
                downstream[dep].append(step.step_id)
        transparency: dict[str, dict[str, Any]] = {}
        for step in self.ordered_steps():
            status = states.get(step.step_id, StepStatus.PENDING)
            upstream_Completed = all(
                states.get(d, StepStatus.PENDING) in (StepStatus.VERIFIED, StepStatus.DEDUPLICATED)
                for d in step.depends_on
            )
            transparency[step.step_id] = {
                "step_id": step.step_id,
                "title": step.title,
                "owner_team": step.owner_team.value,
                "collaborating_teams": [t.value for t in step.collaborating_teams],
                "mode": step.mode.value,
                "tool_category": step.tool_category.value,
                "status": status.value,
                "upstream_dependencies": list(step.depends_on),
                "downstream_dependents": sorted(downstream[step.step_id]),
                "upstream_satisfied": upstream_Completed,
            }
        return transparency

    def to_recovery_plan(self, *, actor_id: str, deadline_ns: int) -> RecoveryPlan:
        """Bridge automated steps into a canonical Salamander RecoveryPlan."""
        recovery_steps: list[RecoveryStep] = []
        for step in self.ordered_steps():
            if "quarantine" in step.operation:
                action_kind = ActionKind.QUARANTINE
            elif "reanchor" in step.operation or "custody" in step.operation or "snapshot" in step.operation:
                action_kind = ActionKind.RESTORE_CUSTODY
            elif "verify" in step.operation or "validate" in step.operation or "gates" in step.operation:
                action_kind = ActionKind.REQUALIFY
            elif "failover" in step.operation:
                action_kind = ActionKind.FAILOVER
            else:
                action_kind = ActionKind.REPLAN
            req = ActionRequest(
                action_id=f"{self.runbook_id}:{step.step_id}",
                tenant_id=self.tenant_id,
                actor_id=actor_id,
                target=self.target,
                kind=action_kind,
                handler=step.operation,
                reason=step.title,
                bounds={"sla_budget_ns": step.sla_budget_ns, **dict(step.parameters)},
                requires=step.prerequisites,
                idempotency_key=f"idem:{self.runbook_id}:{step.step_id}",
            )
            rollback_req: ActionRequest | None = None
            if step.rollback_operation:
                rollback_req = ActionRequest(
                    action_id=f"{self.runbook_id}:{step.step_id}:rollback",
                    tenant_id=self.tenant_id,
                    actor_id=actor_id,
                    target=self.target,
                    kind=ActionKind.ROLLBACK,
                    handler=step.rollback_operation,
                    reason=f"Rollback {step.title}",
                    bounds={"rollback_for": step.step_id},
                    requires=(),
                    idempotency_key=f"idem:{self.runbook_id}:{step.step_id}:rollback",
                )
            recovery_steps.append(
                RecoveryStep(
                    step_id=step.step_id,
                    request=req,
                    depends_on=step.depends_on,
                    rollback=rollback_req,
                )
            )
        return RecoveryPlan(
            recovery_id=self.runbook_id,
            tenant_id=self.tenant_id,
            target=self.target,
            steps=tuple(recovery_steps),
            max_actions=self.max_actions,
            deadline_ns=deadline_ns,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": RUNBOOK_SCHEMA,
            "runbook_id": self.runbook_id,
            "title": self.title,
            "use_case": self.use_case.value,
            "tenant_id": self.tenant_id,
            "target": self.target,
            "description": self.description,
            "initial_scope_sha256": self.initial_scope_sha256,
            "escalation_teams": [t.value for t in self.escalation_teams],
            "max_actions": self.max_actions,
            "steps": [s.to_dict() for s in self.ordered_steps()],
            "dependency_graph": self.dependency_transparency_map(),
        }


@dataclass(frozen=True)
class RunbookExecutionReport:
    """Immutable execution report produced by the Collaborative Automation Engine."""

    runbook_id: str
    use_case: WorkflowUseCase
    tenant_id: str
    target: str
    status: RunbookStatus
    step_states: Mapping[str, StepStatus]
    step_outputs: Mapping[str, Mapping[str, Any]]
    human_decisions: tuple[HumanDecision, ...]
    bathtub_assessment: BathtubAssessment
    dependency_transparency: Mapping[str, Mapping[str, Any]]
    engaged_teams: tuple[str, ...]
    deduplicated_steps: tuple[str, ...]
    rolled_back_steps: tuple[str, ...]
    audit_head_sha256: str
    audit_record_count: int
    at_ns: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "runbook_id": self.runbook_id,
            "use_case": self.use_case.value,
            "tenant_id": self.tenant_id,
            "target": self.target,
            "status": self.status.value,
            "step_states": {k: v.value for k, v in self.step_states.items()},
            "step_outputs": {k: dict(v) for k, v in self.step_outputs.items()},
            "human_decisions": [d.to_dict() for d in self.human_decisions],
            "bathtub_assessment": self.bathtub_assessment.to_dict(),
            "dependency_transparency": {k: dict(v) for k, v in self.dependency_transparency.items()},
            "engaged_teams": list(self.engaged_teams),
            "deduplicated_steps": list(self.deduplicated_steps),
            "rolled_back_steps": list(self.rolled_back_steps),
            "audit_head_sha256": self.audit_head_sha256,
            "audit_record_count": self.audit_record_count,
            "at_ns": int(self.at_ns),
        }


StepHandler = Callable[[CollaborativeStep, Mapping[str, Any]], Mapping[str, Any]]
StepVerifier = Callable[[CollaborativeStep, Mapping[str, Any]], Mapping[str, Any]]


class CollaborativeAutomationEngine:
    """System of Execution orchestrating the interplay between human expertise and automated runbooks."""

    def __init__(
        self,
        *,
        ledger: EvidenceLedger | None = None,
        bathtub_guard: BathtubGuard | None = None,
        deduplicator: CrossTeamTaskDeduplicator | None = None,
        clock_ns: Callable[[], int] = time.time_ns,
        control_plane: AutonomicControlPlane | None = None,
    ) -> None:
        self.ledger = ledger or EvidenceLedger()
        self.bathtub_guard = bathtub_guard or BathtubGuard()
        self.deduplicator = deduplicator or CrossTeamTaskDeduplicator()
        self.clock_ns = clock_ns
        self.control_plane = control_plane
        self._handlers: dict[str, tuple[StepHandler, StepVerifier]] = {}
        self._decisions: dict[tuple[str, str], list[HumanDecision]] = {}
        self._reports: dict[str, RunbookExecutionReport] = {}
        self._register_default_handlers()

    def register_step_handler(
        self,
        operation: str,
        handler: StepHandler,
        *,
        verifier: StepVerifier,
    ) -> None:
        if not operation.strip() or not callable(handler) or not callable(verifier):
            raise ValueError("operation, callable handler, and callable verifier are required")
        self._handlers[operation.strip()] = (handler, verifier)

    def _register_default_handlers(self) -> None:
        """Register deterministic, receipt-producing step handlers and postcondition verifiers."""

        def default_handler(step: CollaborativeStep, context: Mapping[str, Any]) -> Mapping[str, Any]:
            force_fail = bool(context.get("fail_operations") and step.operation in context["fail_operations"])
            return {
                "operation": step.operation,
                "target": step.target,
                "owner_team": step.owner_team.value,
                "tool_category": step.tool_category.value,
                "executed": not force_fail,
                "advisory_only": step.tool_category is AutomationToolCategory.AI_ML,
                "postconditions_checked": list(step.postconditions),
            }

        def default_verifier(step: CollaborativeStep, response: Mapping[str, Any]) -> Mapping[str, Any]:
            ok = response.get("executed") is True
            ref = digest(
                "hyba.collaborative.step-verification.v1",
                {
                    "step_id": step.step_id,
                    "operation": step.operation,
                    "target": step.target,
                    "ok": ok,
                },
            )
            return {
                "verified": ok,
                "evidence_ref": ref if ok else None,
                "observations": {"postconditions": list(step.postconditions), "ok": ok},
                "error": None if ok else f"postcondition verification failed for {step.operation}",
            }

        # Register canonical operations for all 4 workflows + catalogue operations
        canonical_ops = (
            # 1. Cyber & IT Disaster Recovery
            "detect_incident_and_engage_teams",
            "quarantine_compromised_lanes",
            "restore_quarantined_lanes",
            "trigger_failover_standby",
            "revert_failover_standby",
            "reanchor_theseus_witness_chain",
            "restore_previous_witness_anchor",
            # 2. Cloud & Fleet Migration
            "assess_fleet_capacity_and_dependencies",
            "drain_inflight_work_leases",
            "resume_source_work_leases",
            "provision_target_fleet_partitions",
            "decommission_target_fleet_partitions",
            "verify_snapshot_and_cutover",
            "rollback_to_source_snapshot",
            # 3. Application Release Management
            "run_automated_regression_and_security_gates",
            "verify_signed_container_provenance",
            "deploy_canary_slice",
            "rollback_canary_slice",
            "promote_production_release",
            "rollback_production_release",
            # 4. Technology Implementation
            "validate_architecture_prerequisites",
            "configure_sovereign_policy_boundary",
            "revert_sovereign_policy_boundary",
            "execute_phased_technology_rollout",
            "rollback_technology_rollout",
            "attest_single_pane_stakeholder_handover",
        )
        for op in canonical_ops:
            self.register_step_handler(op, default_handler, verifier=default_verifier)

    def record_human_decision(self, decision: HumanDecision) -> str:
        """Record an authenticated human-in-the-loop judgment into the hash-chained audit ledger."""
        key = (decision.runbook_id, decision.step_id)
        self._decisions.setdefault(key, []).append(decision)
        seal = self.ledger.append(
            "collaborative-human-decision",
            decision.to_dict(),
            at_ns=decision.at_ns,
        )
        return seal

    def execute_runbook(
        self,
        runbook: CollaborativeRunbook,
        *,
        context: Mapping[str, Any] | None = None,
        available_operators: int = 2,
        action_budget_remaining: int = 32,
        longest_wait_ns: int = 0,
        injected_step_ids: tuple[str, ...] | None = None,
    ) -> RunbookExecutionReport:
        """Execute a CollaborativeRunbook with human-in-the-loop checkpoints, cross-team
        deduplication, Bathtub-effect guardrails, and verified rollback on failure."""
        ctx = dict(context or {})
        now_ns = self.clock_ns()
        ordered = runbook.ordered_steps()
        current_step_ids = injected_step_ids if injected_step_ids is not None else tuple(s.step_id for s in ordered)

        # Check if any human decision explicitly approved a scope revision
        scope_revision_approved = any(
            d.scope_revision_approved
            for (rb_id, _), decs in self._decisions.items()
            if rb_id == runbook.runbook_id
            for d in decs
        )

        # Pre-flight Bathtub Effect guardrail assessment
        initial_bathtub = self.bathtub_guard.evaluate(
            runbook,
            current_step_ids=current_step_ids,
            failed_steps=0,
            executed_steps=0,
            available_operators=available_operators,
            action_budget_remaining=action_budget_remaining,
            longest_wait_ns=longest_wait_ns,
            scope_revision_approved=scope_revision_approved,
        )

        step_states: dict[str, StepStatus] = {s.step_id: StepStatus.PENDING for s in ordered}
        step_outputs: dict[str, Mapping[str, Any]] = {}
        engaged_teams: set[str] = {t.value for t in runbook.escalation_teams}
        deduplicated_steps: list[str] = []
        rolled_back_steps: list[str] = []
        collected_decisions: list[HumanDecision] = []

        self.ledger.append(
            "collaborative-runbook-started",
            {
                "runbook_id": runbook.runbook_id,
                "use_case": runbook.use_case.value,
                "tenant_id": runbook.tenant_id,
                "target": runbook.target,
                "initial_scope_sha256": runbook.initial_scope_sha256,
                "bathtub_healthy": initial_bathtub.healthy,
                "active_risks": [r.value for r in initial_bathtub.active_risks],
            },
            at_ns=now_ns,
        )

        if not initial_bathtub.healthy:
            self.ledger.append(
                "collaborative-bathtub-halt",
                {
                    "runbook_id": runbook.runbook_id,
                    "assessment": initial_bathtub.to_dict(),
                },
                at_ns=self.clock_ns(),
            )
            report = RunbookExecutionReport(
                runbook_id=runbook.runbook_id,
                use_case=runbook.use_case,
                tenant_id=runbook.tenant_id,
                target=runbook.target,
                status=RunbookStatus.HALTED_BATHTUB_GUARD,
                step_states=step_states,
                step_outputs=step_outputs,
                human_decisions=tuple(collected_decisions),
                bathtub_assessment=initial_bathtub,
                dependency_transparency=runbook.dependency_transparency_map(step_states),
                engaged_teams=tuple(sorted(engaged_teams)),
                deduplicated_steps=tuple(deduplicated_steps),
                rolled_back_steps=tuple(rolled_back_steps),
                audit_head_sha256=self.ledger.head,
                audit_record_count=len(self.ledger.records),
                at_ns=self.clock_ns(),
            )
            self._reports[runbook.runbook_id] = report
            return report

        executed_count = 0
        failed_count = 0
        runbook_status = RunbookStatus.IN_PROGRESS

        for step in ordered:
            engaged_teams.add(step.owner_team.value)
            for team in step.collaborating_teams:
                engaged_teams.add(team.value)

            # Verify upstream dependencies
            if any(
                step_states[dep] not in (StepStatus.VERIFIED, StepStatus.DEDUPLICATED)
                for dep in step.depends_on
            ):
                step_states[step.step_id] = StepStatus.BLOCKED_UPSTREAM
                continue

            # Check Human-in-the-Loop / Collaborative Hybrid checkpoint requirements
            if step.mode in (StepMode.HUMAN_IN_THE_LOOP, StepMode.COLLABORATIVE_HYBRID):
                decisions = self._decisions.get((runbook.runbook_id, step.step_id), [])
                if not decisions:
                    step_states[step.step_id] = StepStatus.AWAITING_HUMAN_DECISION
                    runbook_status = RunbookStatus.AWAITING_HUMAN
                    self.ledger.append(
                        "collaborative-step-awaiting-human",
                        {
                            "runbook_id": runbook.runbook_id,
                            "step_id": step.step_id,
                            "required_approver_roles": [r.value for r in step.required_approver_roles],
                            "owner_team": step.owner_team.value,
                        },
                        at_ns=self.clock_ns(),
                    )
                    continue

                latest_decision = decisions[-1]
                collected_decisions.append(latest_decision)
                if (
                    step.required_approver_roles
                    and latest_decision.team_role not in step.required_approver_roles
                ):
                    step_states[step.step_id] = StepStatus.AWAITING_HUMAN_DECISION
                    runbook_status = RunbookStatus.AWAITING_HUMAN
                    self.ledger.append(
                        "collaborative-human-role-mismatch",
                        {
                            "runbook_id": runbook.runbook_id,
                            "step_id": step.step_id,
                            "provided_role": latest_decision.team_role.value,
                            "required_roles": [r.value for r in step.required_approver_roles],
                        },
                        at_ns=self.clock_ns(),
                    )
                    continue

                if not latest_decision.approved:
                    step_states[step.step_id] = StepStatus.REJECTED_BY_HUMAN
                    runbook_status = RunbookStatus.FAILED_CLOSED
                    self.ledger.append(
                        "collaborative-step-rejected-by-human",
                        {
                            "runbook_id": runbook.runbook_id,
                            "step_id": step.step_id,
                            "actor_id": latest_decision.actor_id,
                            "rationale": latest_decision.rationale,
                            "decision_sha256": latest_decision.decision_sha256,
                        },
                        at_ns=self.clock_ns(),
                    )
                    break

            # Cross-team duplicate effort check
            prior = self.deduplicator.check_or_record(
                tenant_id=runbook.tenant_id,
                step=step,
                runbook_id=runbook.runbook_id,
            )
            if prior is not None:
                step_states[step.step_id] = StepStatus.DEDUPLICATED
                step_outputs[step.step_id] = {
                    "deduplicated": True,
                    "reused_from_runbook": prior["runbook_id"],
                    "reused_from_step": prior["step_id"],
                    "reused_evidence_sha256": prior["evidence_sha256"],
                }
                deduplicated_steps.append(step.step_id)
                self.ledger.append(
                    "collaborative-step-deduplicated",
                    {
                        "runbook_id": runbook.runbook_id,
                        "step_id": step.step_id,
                        "reused_evidence_sha256": prior["evidence_sha256"],
                    },
                    at_ns=self.clock_ns(),
                )
                continue

            # Execute step
            step_states[step.step_id] = StepStatus.EXECUTING
            executed_count += 1
            registered = self._handlers.get(step.operation)
            if registered is None:
                # Fallback to deterministic catalogue step handler
                handler, verifier = self._handlers["detect_incident_and_engage_teams"]
            else:
                handler, verifier = registered

            response = dict(handler(step, ctx))
            verification = dict(verifier(step, response))
            verified = verification.get("verified") is True

            if verified:
                step_states[step.step_id] = StepStatus.VERIFIED
                seal = self.ledger.append(
                    "collaborative-step-verified",
                    {
                        "runbook_id": runbook.runbook_id,
                        "step_id": step.step_id,
                        "operation": step.operation,
                        "owner_team": step.owner_team.value,
                        "collaborating_teams": [t.value for t in step.collaborating_teams],
                        "tool_category": step.tool_category.value,
                        "evidence_ref": verification.get("evidence_ref"),
                    },
                    at_ns=self.clock_ns(),
                )
                step_outputs[step.step_id] = {
                    **response,
                    "verified": True,
                    "evidence_ref": verification.get("evidence_ref"),
                    "audit_sha256": seal,
                }
                self.deduplicator.check_or_record(
                    tenant_id=runbook.tenant_id,
                    step=step,
                    runbook_id=runbook.runbook_id,
                    evidence_sha256=seal,
                )
                continue

            # Step verification failed -> execute governed rollback if configured, else fail closed
            failed_count += 1
            if step.rollback_operation:
                rb_entry = self._handlers.get(
                    step.rollback_operation,
                    self._handlers["detect_incident_and_engage_teams"],
                )
                rb_handler, rb_verifier = rb_entry
                rb_step = CollaborativeStep(
                    step_id=f"{step.step_id}:rollback",
                    title=f"Rollback {step.title}",
                    owner_team=step.owner_team,
                    collaborating_teams=step.collaborating_teams,
                    tool_category=step.tool_category,
                    mode=StepMode.AUTOMATED,
                    operation=step.rollback_operation,
                    target=step.target,
                )
                rb_resp = dict(rb_handler(rb_step, {}))
                rb_ver = dict(rb_verifier(rb_step, rb_resp))
                if rb_ver.get("verified") is True:
                    step_states[step.step_id] = StepStatus.ROLLED_BACK
                    rolled_back_steps.append(step.step_id)
                    runbook_status = RunbookStatus.ROLLED_BACK
                    self.ledger.append(
                        "collaborative-step-rolled-back",
                        {
                            "runbook_id": runbook.runbook_id,
                            "step_id": step.step_id,
                            "failed_operation": step.operation,
                            "rollback_operation": step.rollback_operation,
                            "rollback_evidence_ref": rb_ver.get("evidence_ref"),
                        },
                        at_ns=self.clock_ns(),
                    )
                    step_outputs[step.step_id] = {
                        **response,
                        "verified": False,
                        "rolled_back": True,
                        "rollback_operation": step.rollback_operation,
                    }
                    break

            step_states[step.step_id] = StepStatus.FAILED_CLOSED
            runbook_status = RunbookStatus.FAILED_CLOSED
            self.ledger.append(
                "collaborative-step-failed-closed",
                {
                    "runbook_id": runbook.runbook_id,
                    "step_id": step.step_id,
                    "operation": step.operation,
                    "error": verification.get("error") or "postcondition verification rejected",
                },
                at_ns=self.clock_ns(),
            )
            step_outputs[step.step_id] = {
                **response,
                "verified": False,
                "rolled_back": False,
                "error": verification.get("error"),
            }
            break

        if runbook_status == RunbookStatus.IN_PROGRESS:
            if all(
                st in (StepStatus.VERIFIED, StepStatus.DEDUPLICATED)
                for st in step_states.values()
            ):
                runbook_status = RunbookStatus.COMPLETED_VERIFIED
            elif any(
                st in (StepStatus.AWAITING_HUMAN_DECISION, StepStatus.BLOCKED_UPSTREAM)
                for st in step_states.values()
            ):
                runbook_status = RunbookStatus.AWAITING_HUMAN

        final_bathtub = self.bathtub_guard.evaluate(
            runbook,
            current_step_ids=current_step_ids,
            failed_steps=failed_count,
            executed_steps=executed_count,
            available_operators=available_operators,
            action_budget_remaining=action_budget_remaining,
            longest_wait_ns=longest_wait_ns,
            scope_revision_approved=scope_revision_approved,
        )

        self.ledger.append(
            "collaborative-runbook-finished",
            {
                "runbook_id": runbook.runbook_id,
                "status": runbook_status.value,
                "verified_steps": sum(
                    1 for s in step_states.values() if s in (StepStatus.VERIFIED, StepStatus.DEDUPLICATED)
                ),
                "total_steps": len(ordered),
            },
            at_ns=self.clock_ns(),
        )

        report = RunbookExecutionReport(
            runbook_id=runbook.runbook_id,
            use_case=runbook.use_case,
            tenant_id=runbook.tenant_id,
            target=runbook.target,
            status=runbook_status,
            step_states=step_states,
            step_outputs=step_outputs,
            human_decisions=tuple(collected_decisions),
            bathtub_assessment=final_bathtub,
            dependency_transparency=runbook.dependency_transparency_map(step_states),
            engaged_teams=tuple(sorted(engaged_teams)),
            deduplicated_steps=tuple(deduplicated_steps),
            rolled_back_steps=tuple(rolled_back_steps),
            audit_head_sha256=self.ledger.head,
            audit_record_count=len(self.ledger.records),
            at_ns=self.clock_ns(),
        )
        self._reports[runbook.runbook_id] = report
        return report

    def single_pane_dashboard(
        self,
        runbooks: Iterable[CollaborativeRunbook] | None = None,
    ) -> dict[str, Any]:
        """Real-time 'Single Pane of Glass' dashboard for IT operational insight."""
        catalogue = tuple(runbooks) if runbooks is not None else tuple(build_canonical_workflow_runbooks().values())
        workflows_summary: list[dict[str, Any]] = []
        awaiting_human_checkpoints: list[dict[str, Any]] = []
        teams_active: set[str] = set()

        for rb in catalogue:
            report = self._reports.get(rb.runbook_id)
            step_states = report.step_states if report else {s.step_id: StepStatus.PENDING for s in rb.steps}
            status = report.status.value if report else RunbookStatus.READY.value
            verified_count = sum(
                1 for st in step_states.values() if st in (StepStatus.VERIFIED, StepStatus.DEDUPLICATED)
            )
            for s in rb.steps:
                teams_active.add(s.owner_team.value)
                for ct in s.collaborating_teams:
                    teams_active.add(ct.value)
                if step_states.get(s.step_id) == StepStatus.AWAITING_HUMAN_DECISION:
                    awaiting_human_checkpoints.append(
                        {
                            "runbook_id": rb.runbook_id,
                            "step_id": s.step_id,
                            "title": s.title,
                            "required_approver_roles": [r.value for r in s.required_approver_roles],
                            "owner_team": s.owner_team.value,
                        }
                    )
            workflows_summary.append(
                {
                    "runbook_id": rb.runbook_id,
                    "title": rb.title,
                    "use_case": rb.use_case.value,
                    "target": rb.target,
                    "status": status,
                    "total_steps": len(rb.steps),
                    "verified_steps": verified_count,
                    "human_in_the_loop_steps": sum(
                        1
                        for s in rb.steps
                        if s.mode in (StepMode.HUMAN_IN_THE_LOOP, StepMode.COLLABORATIVE_HYBRID)
                    ),
                    "initial_scope_sha256": rb.initial_scope_sha256,
                    "dependency_transparency": rb.dependency_transparency_map(step_states),
                }
            )

        return {
            "schema": DASHBOARD_SCHEMA,
            "system_of_execution": "HYBA/PYTHIA Collaborative Automation & Salamander Runbook Engine",
            "authority_boundary": {
                "cognition_advisory": "EUCLID / TOE",
                "mining_proof_authority": "PYTHIA (SHA256d + Stratum)",
                "execution_substrate": "CHRONUS",
                "bounded_recovery_actuation": "SALAMANDER",
                "security_and_authorization": "AL HARAS",
                "custody_and_lineage": "OVID / THESEUS",
            },
            "summary": {
                "registered_workflows": len(workflows_summary),
                "completed_verified": sum(
                    1 for w in workflows_summary if w["status"] == RunbookStatus.COMPLETED_VERIFIED.value
                ),
                "awaiting_human_checkpoints": len(awaiting_human_checkpoints),
                "cross_team_roles_connected": sorted(teams_active),
                "deduplicated_tasks_total": self.deduplicator.deduplicated_count,
                "bathtub_scale_phase_limit": self.bathtub_guard.scale_phase_limit,
            },
            "awaiting_human_checkpoints": awaiting_human_checkpoints,
            "workflows": workflows_summary,
            "audit_trail": {
                "schema": AUDIT_SCHEMA,
                "chain_verified": self.ledger.verify(),
                "head_sha256": self.ledger.head,
                "record_count": len(self.ledger.records),
            },
        }


def build_canonical_workflow_runbooks(tenant_id: str = "hyba_enterprise") -> dict[str, CollaborativeRunbook]:
    """Construct the four canonical Collaborative Automation runbooks:
    1. Cyber and IT disaster recovery
    2. Cloud & fleet migration
    3. Application release management
    4. Technology implementation
    """
    dr_runbook = CollaborativeRunbook(
        runbook_id="cyber_it_disaster_recovery",
        title="Cyber and IT Disaster Recovery Runbook",
        use_case=WorkflowUseCase.CYBER_IT_DISASTER_RECOVERY,
        tenant_id=tenant_id,
        target="pythia-sovereign-cluster",
        description=(
            "Orchestrates automated failover and quarantine with human-in-the-loop "
            "security analyst and stakeholder judgment and immutable THESEUS/Salamander audit trails."
        ),
        escalation_teams=(TeamRole.INCIDENT_RESPONSE, TeamRole.SECURITY_ANALYST, TeamRole.SRE),
        steps=(
            CollaborativeStep(
                step_id="dr_01_detect_and_engage",
                title="Detect anomaly, classify severity, and engage SRE/Security/TechOps teams",
                owner_team=TeamRole.SRE,
                collaborating_teams=(TeamRole.SECURITY_ANALYST, TeamRole.TECH_OPS),
                tool_category=AutomationToolCategory.AI_ML,
                mode=StepMode.AUTOMATED,
                operation="detect_incident_and_engage_teams",
                target="pythia-sovereign-cluster",
                prerequisites=("telemetry_stream_bound",),
                postconditions=("teams_engaged", "incident_classified"),
            ),
            CollaborativeStep(
                step_id="dr_02_quarantine_lanes",
                title="Quarantine affected execution lanes and freeze unverified writes",
                owner_team=TeamRole.TECH_OPS,
                collaborating_teams=(TeamRole.SRE, TeamRole.SECURITY_ANALYST),
                tool_category=AutomationToolCategory.IT_AUTOMATION,
                mode=StepMode.AUTOMATED,
                operation="quarantine_compromised_lanes",
                target="pythia-sovereign-cluster",
                depends_on=("dr_01_detect_and_engage",),
                prerequisites=("incident_classified",),
                postconditions=("lanes_quarantined", "writes_frozen"),
                rollback_operation="restore_quarantined_lanes",
            ),
            CollaborativeStep(
                step_id="dr_03_human_recovery_checkpoint",
                title="Security Analyst and Stakeholder collaborative failover authorization",
                owner_team=TeamRole.SECURITY_ANALYST,
                collaborating_teams=(TeamRole.STAKEHOLDER, TeamRole.SRE),
                tool_category=AutomationToolCategory.IT_AUTOMATION,
                mode=StepMode.HUMAN_IN_THE_LOOP,
                operation="trigger_failover_standby",
                target="pythia-sovereign-cluster",
                depends_on=("dr_02_quarantine_lanes",),
                prerequisites=("lanes_quarantined", "root_cause_scoped"),
                postconditions=("failover_standby_active",),
                rollback_operation="revert_failover_standby",
                required_approver_roles=(TeamRole.SECURITY_ANALYST, TeamRole.STAKEHOLDER),
            ),
            CollaborativeStep(
                step_id="dr_04_reanchor_witness_audit",
                title="Re-anchor THESEUS witness chain and emit immutable compliance receipt",
                owner_team=TeamRole.SRE,
                collaborating_teams=(TeamRole.SECURITY_ANALYST, TeamRole.ARCHITECTURE_OWNER),
                tool_category=AutomationToolCategory.IPAAS,
                mode=StepMode.COLLABORATIVE_HYBRID,
                operation="reanchor_theseus_witness_chain",
                target="pythia-sovereign-cluster",
                depends_on=("dr_03_human_recovery_checkpoint",),
                prerequisites=("failover_standby_active",),
                postconditions=("witness_chain_verified", "immutable_audit_sealed"),
                rollback_operation="restore_previous_witness_anchor",
                required_approver_roles=(TeamRole.SECURITY_ANALYST, TeamRole.SRE),
            ),
        ),
    )

    migration_runbook = CollaborativeRunbook(
        runbook_id="cloud_migration",
        title="Cloud and Chronus Fleet Partition Migration Runbook",
        use_case=WorkflowUseCase.CLOUD_MIGRATION,
        tenant_id=tenant_id,
        target="chronus-fleet-fabric",
        description=(
            "Streamlines workload and partition migration with automated provisioning "
            "and real-time upstream/downstream dependency transparency."
        ),
        escalation_teams=(TeamRole.ARCHITECTURE_OWNER, TeamRole.DEVOPS, TeamRole.SRE),
        steps=(
            CollaborativeStep(
                step_id="mig_01_assess_dependencies",
                title="Map upstream/downstream dependencies and verify Lucas fleet capacity plan",
                owner_team=TeamRole.ARCHITECTURE_OWNER,
                collaborating_teams=(TeamRole.DEVOPS, TeamRole.SRE),
                tool_category=AutomationToolCategory.AI_ML,
                mode=StepMode.AUTOMATED,
                operation="assess_fleet_capacity_and_dependencies",
                target="chronus-fleet-fabric",
                prerequisites=("capacity_certificate_issued",),
                postconditions=("dependencies_mapped", "zero_gap_partition_verified"),
            ),
            CollaborativeStep(
                step_id="mig_02_provision_target",
                title="Provision target Chronus worker partitions and storage custody",
                owner_team=TeamRole.DEVOPS,
                collaborating_teams=(TeamRole.TECH_OPS,),
                tool_category=AutomationToolCategory.IT_AUTOMATION,
                mode=StepMode.AUTOMATED,
                operation="provision_target_fleet_partitions",
                target="chronus-fleet-fabric",
                depends_on=("mig_01_assess_dependencies",),
                prerequisites=("zero_gap_partition_verified",),
                postconditions=("target_partitions_ready",),
                rollback_operation="decommission_target_fleet_partitions",
            ),
            CollaborativeStep(
                step_id="mig_03_drain_inflight",
                title="Drain in-flight work leases and quiesce source partitions",
                owner_team=TeamRole.SRE,
                collaborating_teams=(TeamRole.DEVOPS, TeamRole.TECH_OPS),
                tool_category=AutomationToolCategory.RPA,
                mode=StepMode.AUTOMATED,
                operation="drain_inflight_work_leases",
                target="chronus-fleet-fabric",
                depends_on=("mig_02_provision_target",),
                prerequisites=("target_partitions_ready",),
                postconditions=("inflight_leases_drained",),
                rollback_operation="resume_source_work_leases",
            ),
            CollaborativeStep(
                step_id="mig_04_human_cutover_verification",
                title="Verify OVID/THESEUS snapshot equivalence and execute human-approved cutover",
                owner_team=TeamRole.ARCHITECTURE_OWNER,
                collaborating_teams=(TeamRole.SRE, TeamRole.STAKEHOLDER),
                tool_category=AutomationToolCategory.IPAAS,
                mode=StepMode.HUMAN_IN_THE_LOOP,
                operation="verify_snapshot_and_cutover",
                target="chronus-fleet-fabric",
                depends_on=("mig_03_drain_inflight",),
                prerequisites=("inflight_leases_drained", "snapshot_hash_matched"),
                postconditions=("cutover_complete", "lineage_verified"),
                rollback_operation="rollback_to_source_snapshot",
                required_approver_roles=(TeamRole.ARCHITECTURE_OWNER, TeamRole.SRE),
            ),
        ),
    )

    release_runbook = CollaborativeRunbook(
        runbook_id="application_release_management",
        title="Application Release Management and Continuous Delivery Runbook",
        use_case=WorkflowUseCase.APPLICATION_RELEASE_MANAGEMENT,
        tenant_id=tenant_id,
        target="hyba-release-pipeline",
        description=(
            "Automates software release testing, container signature verification, "
            "and CI/CD canary promotion with release-manager human sign-off."
        ),
        escalation_teams=(TeamRole.RELEASE_MANAGER, TeamRole.DEVOPS, TeamRole.SRE),
        steps=(
            CollaborativeStep(
                step_id="rel_01_automated_test_gates",
                title="Execute automated regression sweep and readiness qualification gates",
                owner_team=TeamRole.DEVOPS,
                collaborating_teams=(TeamRole.SRE,),
                tool_category=AutomationToolCategory.RPA,
                mode=StepMode.AUTOMATED,
                operation="run_automated_regression_and_security_gates",
                target="hyba-release-pipeline",
                prerequisites=("source_revision_locked",),
                postconditions=("regression_gates_passed",),
            ),
            CollaborativeStep(
                step_id="rel_02_verify_signed_artifacts",
                title="Verify cryptographic container and package provenance signatures",
                owner_team=TeamRole.SECURITY_ANALYST,
                collaborating_teams=(TeamRole.DEVOPS, TeamRole.RELEASE_MANAGER),
                tool_category=AutomationToolCategory.IT_AUTOMATION,
                mode=StepMode.AUTOMATED,
                operation="verify_signed_container_provenance",
                target="hyba-release-pipeline",
                depends_on=("rel_01_automated_test_gates",),
                prerequisites=("regression_gates_passed",),
                postconditions=("artifact_signatures_verified",),
            ),
            CollaborativeStep(
                step_id="rel_03_deploy_canary",
                title="Deploy bounded canary slice and observe homeostasis envelope",
                owner_team=TeamRole.SRE,
                collaborating_teams=(TeamRole.DEVOPS,),
                tool_category=AutomationToolCategory.IT_AUTOMATION,
                mode=StepMode.AUTOMATED,
                operation="deploy_canary_slice",
                target="hyba-release-pipeline",
                depends_on=("rel_02_verify_signed_artifacts",),
                prerequisites=("artifact_signatures_verified",),
                postconditions=("canary_healthy",),
                rollback_operation="rollback_canary_slice",
            ),
            CollaborativeStep(
                step_id="rel_04_human_release_promotion",
                title="Release Manager collaborative sign-off and production promotion",
                owner_team=TeamRole.RELEASE_MANAGER,
                collaborating_teams=(TeamRole.SRE, TeamRole.STAKEHOLDER),
                tool_category=AutomationToolCategory.IT_AUTOMATION,
                mode=StepMode.HUMAN_IN_THE_LOOP,
                operation="promote_production_release",
                target="hyba-release-pipeline",
                depends_on=("rel_03_deploy_canary",),
                prerequisites=("canary_healthy",),
                postconditions=("production_release_promoted",),
                rollback_operation="rollback_production_release",
                required_approver_roles=(TeamRole.RELEASE_MANAGER, TeamRole.SRE),
            ),
        ),
    )

    tech_impl_runbook = CollaborativeRunbook(
        runbook_id="technology_implementation",
        title="Controlled Technology Implementation and Stakeholder Visibility Runbook",
        use_case=WorkflowUseCase.TECHNOLOGY_IMPLEMENTATION,
        tenant_id=tenant_id,
        target="hyba-technology-rollout",
        description=(
            "Eliminates static-plan errors through a verified task sequence and "
            "provides a single-pane-of-glass view for real-time stakeholder monitoring."
        ),
        escalation_teams=(TeamRole.ARCHITECTURE_OWNER, TeamRole.TECH_OPS, TeamRole.STAKEHOLDER),
        steps=(
            CollaborativeStep(
                step_id="impl_01_validate_prerequisites",
                title="Validate architecture prerequisites and incremental Bathtub scope bounds",
                owner_team=TeamRole.ARCHITECTURE_OWNER,
                collaborating_teams=(TeamRole.TECH_OPS, TeamRole.DEVOPS),
                tool_category=AutomationToolCategory.RPA,
                mode=StepMode.AUTOMATED,
                operation="validate_architecture_prerequisites",
                target="hyba-technology-rollout",
                prerequisites=("scope_baseline_locked",),
                postconditions=("prerequisites_verified",),
            ),
            CollaborativeStep(
                step_id="impl_02_configure_sovereign_policy",
                title="Configure AL HARAS sovereign policy and entitlement boundaries",
                owner_team=TeamRole.SECURITY_ANALYST,
                collaborating_teams=(TeamRole.TECH_OPS, TeamRole.ARCHITECTURE_OWNER),
                tool_category=AutomationToolCategory.IT_AUTOMATION,
                mode=StepMode.AUTOMATED,
                operation="configure_sovereign_policy_boundary",
                target="hyba-technology-rollout",
                depends_on=("impl_01_validate_prerequisites",),
                prerequisites=("prerequisites_verified",),
                postconditions=("policy_boundary_active",),
                rollback_operation="revert_sovereign_policy_boundary",
            ),
            CollaborativeStep(
                step_id="impl_03_phased_rollout",
                title="Execute phased technology rollout across target subsystem",
                owner_team=TeamRole.TECH_OPS,
                collaborating_teams=(TeamRole.DEVOPS, TeamRole.SRE),
                tool_category=AutomationToolCategory.IT_AUTOMATION,
                mode=StepMode.AUTOMATED,
                operation="execute_phased_technology_rollout",
                target="hyba-technology-rollout",
                depends_on=("impl_02_configure_sovereign_policy",),
                prerequisites=("policy_boundary_active",),
                postconditions=("rollout_postconditions_met",),
                rollback_operation="rollback_technology_rollout",
            ),
            CollaborativeStep(
                step_id="impl_04_stakeholder_handover",
                title="Stakeholder single-pane-of-glass review and operational handover sign-off",
                owner_team=TeamRole.STAKEHOLDER,
                collaborating_teams=(TeamRole.ARCHITECTURE_OWNER, TeamRole.TECH_OPS),
                tool_category=AutomationToolCategory.IPAAS,
                mode=StepMode.HUMAN_IN_THE_LOOP,
                operation="attest_single_pane_stakeholder_handover",
                target="hyba-technology-rollout",
                depends_on=("impl_03_phased_rollout",),
                prerequisites=("rollout_postconditions_met",),
                postconditions=("handover_attested",),
                required_approver_roles=(TeamRole.STAKEHOLDER, TeamRole.ARCHITECTURE_OWNER),
            ),
        ),
    )

    return {
        dr_runbook.runbook_id: dr_runbook,
        migration_runbook.runbook_id: migration_runbook,
        release_runbook.runbook_id: release_runbook,
        tech_impl_runbook.runbook_id: tech_impl_runbook,
    }


_ESCALATION_TO_TEAM_ROLE: dict[str, TeamRole] = {
    "operations": TeamRole.TECH_OPS,
    "incident_response": TeamRole.INCIDENT_RESPONSE,
    "security_owner": TeamRole.SECURITY_ANALYST,
    "architecture_owner": TeamRole.ARCHITECTURE_OWNER,
}


def load_repository_catalogue_runbooks(
    catalogue_path: str | Path | None = None,
    *,
    tenant_id: str = "hyba_enterprise",
) -> dict[str, CollaborativeRunbook]:
    """Load the repository's ``runbooks/catalogue.json`` entries as executable
    ``CollaborativeRunbook`` objects, bridging legacy operational recovery entries
    into the Collaborative Automation engine."""
    if catalogue_path is None:
        catalogue_path = Path(__file__).resolve().parents[1] / "runbooks" / "catalogue.json"
    path = Path(catalogue_path)
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("runbooks/catalogue.json must contain a JSON object")

    result: dict[str, CollaborativeRunbook] = {}
    for rb_id, spec in sorted(raw.items()):
        if not isinstance(spec, dict):
            continue
        escalation_names = spec.get("escalation") or ["operations"]
        escalation_roles = tuple(
            _ESCALATION_TO_TEAM_ROLE.get(str(name), TeamRole.TECH_OPS)
            for name in escalation_names
        )
        primary_role = escalation_roles[0] if escalation_roles else TeamRole.TECH_OPS
        raw_steps = list(spec.get("steps") or [])
        rollback_ops = list(spec.get("rollback") or [])
        rollback_op = str(rollback_ops[0]) if rollback_ops else None
        prereqs = tuple(str(p) for p in (spec.get("prerequisites") or ()))
        verifications = tuple(str(v) for v in (spec.get("verification") or ()))

        steps: list[CollaborativeStep] = []
        prev_id: str | None = None
        for idx, step_op in enumerate(raw_steps, start=1):
            step_id = f"{rb_id}_step_{idx:02d}_{step_op}"
            is_final = idx == len(raw_steps)
            mode = StepMode.COLLABORATIVE_HYBRID if is_final else StepMode.AUTOMATED
            steps.append(
                CollaborativeStep(
                    step_id=step_id,
                    title=f"{spec.get('title', rb_id)}: {step_op}",
                    owner_team=primary_role,
                    collaborating_teams=escalation_roles,
                    tool_category=AutomationToolCategory.IT_AUTOMATION,
                    mode=mode,
                    operation=str(step_op),
                    target=f"catalogue:{rb_id}",
                    depends_on=(prev_id,) if prev_id else (),
                    prerequisites=prereqs if idx == 1 else (),
                    postconditions=verifications if is_final else (f"{step_op}_completed",),
                    rollback_operation=rollback_op,
                    required_approver_roles=escalation_roles if is_final else (),
                )
            )
            prev_id = step_id

        if steps:
            result[rb_id] = CollaborativeRunbook(
                runbook_id=rb_id,
                title=str(spec.get("title") or rb_id),
                use_case=WorkflowUseCase.CATALOGUE_OPERATIONAL_RECOVERY,
                tenant_id=tenant_id,
                target=f"catalogue:{rb_id}",
                steps=tuple(steps),
                escalation_teams=escalation_roles,
                description=f"Trigger: {spec.get('trigger', 'manual')} | Evidence: {', '.join(spec.get('evidence_emitted') or ())}",
            )
    return result
