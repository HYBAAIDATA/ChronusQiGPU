"""Technology Operations Guide to Collaborative Automation.

Implements the enterprise framework from Cutover:
"The technology operations guide to Collaborative Automation"

Collaborative Automation interconnects people and technology into a unified
'System of Execution' that values, recognizes, and incorporates human judgment,
awareness, and collaboration alongside automated tools.

Key Foundations:
1. Solving the Chaos of Siloed Teams:
   - Eliminating duplicate efforts, delivery inefficiencies, and customer impact
     across DevOps, SRE, and Tech Ops.
2. Mitigating the 'Bathtub Effect':
   - Preventing the performance dip and complexity spike from uncontrolled automation
     through phased scaling, scope creep detection, and human-in-the-loop governance.
3. Dispelling Automation Myths:
   - Myth 1: Automation eliminates jobs -> Reality: Augments human capability.
   - Myth 2: One-size-fits-all -> Reality: Tailored processes for specific objectives.
   - Myth 3: Easy to implement -> Reality: Requires continuous governance and change management.
4. Overcoming Open-Source Orchestration Tool Limits:
   - Providing centralized visibility, consistent UX, and deep enterprise integration
     instead of fragmented point tools.
5. Four Primary Use Cases:
   - Cyber and IT Disaster Recovery (DR) with immutable auditability.
   - Cloud Migration with dependency transparency and automated provisioning.
   - Application Release Management with automated quality gates and human sign-offs.
   - Complex Technology Implementation with single-pane-of-glass coordination.
"""

from __future__ import annotations

import collections
import copy
import hashlib
import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from governance.agent_governance import (
    AuditLedger,
    AuditRecord,
    DecisionRightsTier,
)


# ==============================================================================
# 1. ENUMS & CORE COLLABORATIVE AUTOMATION DEFINITIONS
# ==============================================================================

class AutomationUseCaseType(str, Enum):
    """The four core technology operations use cases for collaborative automation."""
    CYBER_AND_IT_DISASTER_RECOVERY = "CYBER_AND_IT_DISASTER_RECOVERY"
    CLOUD_MIGRATION = "CLOUD_MIGRATION"
    APPLICATION_RELEASE_MANAGEMENT = "APPLICATION_RELEASE_MANAGEMENT"
    COMPLEX_TECHNOLOGY_IMPLEMENTATION = "COMPLEX_TECHNOLOGY_IMPLEMENTATION"


class RunbookTaskType(str, Enum):
    """Types of tasks within an automated runbook."""
    AUTOMATED_TASK = "AUTOMATED_TASK"          # Script, API call, Ansible, Terraform
    HUMAN_IN_THE_LOOP = "HUMAN_IN_THE_LOOP"    # Human verification, judgment, crisis decision
    DECISION_GATE = "DECISION_GATE"            # Go/No-Go evaluation checkpoint
    COMMUNICATION_BROADCAST = "COMMUNICATION"  # Stakeholder status broadcast


class TaskExecutionStatus(str, Enum):
    """State machine for task execution within the runbook."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    AWAITING_HUMAN_APPROVAL = "AWAITING_HUMAN_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    ROLLED_BACK = "ROLLED_BACK"


class AutomationToolCategory(str, Enum):
    """Categorization of automation technologies integrated into the system."""
    AI_MACHINE_LEARNING = "AI_MACHINE_LEARNING"  # Predictive analytics & complex decisioning
    RPA = "ROBOTIC_PROCESS_AUTOMATION"          # Rule-based repetitive desktop tasks
    IT_AUTOMATION = "IT_AUTOMATION"              # Ansible, Terraform, Puppet, scripts
    IPAAS = "IPAAS"                              # Inter-system data exchange and integration
    COLLABORATIVE_RUNBOOK = "COLLABORATIVE_RUNBOOK"  # Cutover-style system of execution


class BathtubRiskLevel(str, Enum):
    """Classification of risk from the Bathtub Effect (complexity spikes and performance dips)."""
    LOW_STABLE = "LOW_STABLE"
    MODERATE_CREEP = "MODERATE_CREEP"
    HIGH_BATHTUB_COMPLEXITY_SPIKE = "HIGH_BATHTUB_COMPLEXITY_SPIKE"


# ==============================================================================
# 2. RUNBOOK DATA STRUCTURES (SYSTEM OF EXECUTION)
# ==============================================================================

@dataclass
class RunbookTask:
    """An individual unit of work in a collaborative runbook."""
    task_id: str
    name: str
    task_type: RunbookTaskType
    tool_category: AutomationToolCategory
    assigned_owner: str                      # Human role (e.g. SRE Lead) or automated agent
    dependencies: List[str] = field(default_factory=list)  # IDs of predecessor tasks
    estimated_duration_seconds: float = 60.0
    actual_duration_seconds: float = 0.0
    status: TaskExecutionStatus = TaskExecutionStatus.PENDING
    human_judgment_notes: Optional[str] = None
    approval_actor: Optional[str] = None
    automated_payload: Dict[str, Any] = field(default_factory=dict)
    critical_path: bool = False
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


@dataclass
class AutomatedRunbook:
    """The overarching Cutover-style System of Execution combining human and automated tasks."""
    runbook_id: str
    name: str
    use_case: AutomationUseCaseType
    tasks: Dict[str, RunbookTask] = field(default_factory=dict)
    critical_path_task_ids: List[str] = field(default_factory=list)
    total_estimated_duration_seconds: float = 0.0
    status: str = "DRAFT"                    # DRAFT, ACTIVE, PAUSED, COMPLETED, ABORTED
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


@dataclass
class BathtubEffectMetrics:
    """Metrics tracking the 'Bathtub Effect'—complexity spikes after initial enthusiasm."""
    initial_task_count: int
    current_task_count: int
    scope_creep_ratio: float                 # current / initial
    unexpected_failure_rate_pct: float
    duration_variance_pct: float
    risk_level: BathtubRiskLevel
    mitigation_recommendations: List[str]


@dataclass
class OperationalVisibilityDashboard:
    """Single pane of glass providing real-time technology operations insight."""
    runbook_id: str
    runbook_name: str
    use_case: str
    status: str
    overall_progress_pct: float
    human_tasks_pending_count: int
    automated_tasks_running_count: int
    completed_tasks_count: int
    failed_tasks_count: int
    critical_path_delay_seconds: float
    live_telemetry_feed: List[Dict[str, Any]] = field(default_factory=list)


# ==============================================================================
# 3. COLLABORATIVE RUNBOOK EXECUTION ENGINE
# ==============================================================================

class CollaborativeRunbookExecutionEngine:
    """
    Core System of Execution orchestrating the interplay between human expertise
    and automated tools across complex technology operations.
    """

    def __init__(self, ledger: Optional[AuditLedger] = None) -> None:
        self.ledger = ledger or AuditLedger()
        self._runbooks: Dict[str, AutomatedRunbook] = {}
        self._automated_handlers: Dict[str, Callable[[RunbookTask], bool]] = {}
        self._lock = threading.RLock()

    def register_automated_handler(
        self, tool_category_or_name: str, handler: Callable[[RunbookTask], bool]
    ) -> None:
        """Registers an executable handler for automated runbook tasks."""
        with self._lock:
            self._automated_handlers[tool_category_or_name] = handler

    def create_runbook(
        self,
        runbook_id: str,
        name: str,
        use_case: AutomationUseCaseType,
    ) -> AutomatedRunbook:
        """Initializes a collaborative runbook."""
        with self._lock:
            runbook = AutomatedRunbook(
                runbook_id=runbook_id,
                name=name,
                use_case=use_case,
            )
            self._runbooks[runbook_id] = runbook

            self.ledger.record_action(
                agent_id="collaborative_runbook_engine",
                accountable_owner="tech_ops_director",
                action_type="CREATE_COLLABORATIVE_RUNBOOK",
                tool_name="CollaborativeRunbookExecutionEngine.create_runbook",
                data_compartments_accessed=["runbook_registry"],
                decision_rights_tier=DecisionRightsTier.BOUNDED_AUTONOMY.value,
                containment_passed=True,
                status="RUNBOOK_CREATED",
                rationale_summary=f"Created runbook '{name}' for use case {use_case.value}",
            )
            return runbook

    def add_task(
        self,
        runbook_id: str,
        task: RunbookTask,
    ) -> None:
        """Adds a task with dependency links to the runbook."""
        with self._lock:
            if runbook_id not in self._runbooks:
                raise KeyError(f"Runbook '{runbook_id}' does not exist.")
            rb = self._runbooks[runbook_id]
            rb.tasks[task.task_id] = task
            self._recalculate_runbook_metadata(rb)

    def _recalculate_runbook_metadata(self, runbook: AutomatedRunbook) -> None:
        """Recalculates total duration and identifies the critical path."""
        # Simple topological duration accumulation for critical path
        total_dur = sum(t.estimated_duration_seconds for t in runbook.tasks.values())
        runbook.total_estimated_duration_seconds = total_dur

        # Mark tasks on the longest dependency chain as critical path
        critical_ids: List[str] = []
        for tid, task in runbook.tasks.items():
            if task.dependencies or any(tid in other.dependencies for other in runbook.tasks.values()):
                task.critical_path = True
                critical_ids.append(tid)
            else:
                task.critical_path = False
        runbook.critical_path_task_ids = critical_ids

    def start_runbook(self, runbook_id: str) -> None:
        """Activates runbook execution, setting ready tasks in motion."""
        with self._lock:
            if runbook_id not in self._runbooks:
                raise KeyError(f"Runbook '{runbook_id}' does not exist.")
            rb = self._runbooks[runbook_id]
            rb.status = "ACTIVE"
            rb.started_at = time.time()

            self.ledger.record_action(
                agent_id="collaborative_runbook_engine",
                accountable_owner="incident_commander",
                action_type="START_COLLABORATIVE_RUNBOOK",
                tool_name="CollaborativeRunbookExecutionEngine.start_runbook",
                data_compartments_accessed=["live_operations"],
                decision_rights_tier=DecisionRightsTier.BOUNDED_AUTONOMY.value,
                containment_passed=True,
                status="RUNBOOK_ACTIVE",
                rationale_summary=f"Runbook '{rb.name}' activated with {len(rb.tasks)} tasks.",
            )
            self._advance_runbook(rb)

    def _advance_runbook(self, runbook: AutomatedRunbook) -> None:
        """Advances ready tasks whose dependencies are satisfied."""
        for tid, task in runbook.tasks.items():
            if task.status != TaskExecutionStatus.PENDING:
                continue

            # Check if all predecessor dependencies are completed
            deps_met = all(
                runbook.tasks[dep_id].status == TaskExecutionStatus.COMPLETED
                for dep_id in task.dependencies
                if dep_id in runbook.tasks
            )

            if deps_met:
                if task.task_type in (RunbookTaskType.HUMAN_IN_THE_LOOP, RunbookTaskType.DECISION_GATE):
                    task.status = TaskExecutionStatus.AWAITING_HUMAN_APPROVAL
                    task.started_at = time.time()
                elif task.task_type == RunbookTaskType.AUTOMATED_TASK:
                    task.status = TaskExecutionStatus.IN_PROGRESS
                    task.started_at = time.time()
                    self._dispatch_automated_task(task, runbook)
                elif task.task_type == RunbookTaskType.COMMUNICATION_BROADCAST:
                    task.status = TaskExecutionStatus.COMPLETED
                    task.started_at = time.time()
                    task.completed_at = time.time()

        # Check if all tasks completed
        if runbook.tasks and all(
            t.status in (TaskExecutionStatus.COMPLETED, TaskExecutionStatus.SKIPPED)
            for t in runbook.tasks.values()
        ):
            runbook.status = "COMPLETED"
            runbook.completed_at = time.time()

    def _dispatch_automated_task(self, task: RunbookTask, runbook: AutomatedRunbook) -> None:
        """Executes an automated task handler synchronously or marks completion."""
        handler = (
            self._automated_handlers.get(task.tool_category.value)
            or self._automated_handlers.get(task.name)
        )
        t_start = time.time()
        success = True
        if handler:
            try:
                success = handler(task)
            except Exception:
                success = False

        task.actual_duration_seconds = round(time.time() - t_start, 3)
        task.completed_at = time.time()
        task.status = TaskExecutionStatus.COMPLETED if success else TaskExecutionStatus.FAILED

        self.ledger.record_action(
            agent_id="automated_task_runner",
            accountable_owner=task.assigned_owner,
            action_type="EXECUTE_AUTOMATED_TASK",
            tool_name="CollaborativeRunbookExecutionEngine._dispatch_automated_task",
            data_compartments_accessed=["task_execution_runtime"],
            decision_rights_tier=DecisionRightsTier.BOUNDED_AUTONOMY.value,
            containment_passed=success,
            status="TASK_COMPLETED" if success else "TASK_FAILED",
            rationale_summary=f"Automated task '{task.name}' ({task.tool_category.value}) result: {task.status.value}",
        )
        self._advance_runbook(runbook)

    def submit_human_decision(
        self,
        runbook_id: str,
        task_id: str,
        approved: bool,
        actor_name: str,
        judgment_notes: str = "",
    ) -> bool:
        """
        Records human-in-the-loop judgment, unblocking downstream automated workflows.
        Values people for critical awareness, complex trade-offs, and compliance sign-off.
        """
        with self._lock:
            if runbook_id not in self._runbooks:
                raise KeyError(f"Runbook '{runbook_id}' does not exist.")
            rb = self._runbooks[runbook_id]
            if task_id not in rb.tasks:
                raise KeyError(f"Task '{task_id}' not found in runbook '{runbook_id}'.")

            task = rb.tasks[task_id]
            if task.status != TaskExecutionStatus.AWAITING_HUMAN_APPROVAL:
                return False

            task.approval_actor = actor_name
            task.human_judgment_notes = judgment_notes
            task.completed_at = time.time()
            if task.started_at:
                task.actual_duration_seconds = round(task.completed_at - task.started_at, 2)

            task.status = TaskExecutionStatus.COMPLETED if approved else TaskExecutionStatus.FAILED

            self.ledger.record_action(
                agent_id="human_in_the_loop_gateway",
                accountable_owner=actor_name,
                action_type="RECORD_HUMAN_JUDGMENT",
                tool_name="CollaborativeRunbookExecutionEngine.submit_human_decision",
                data_compartments_accessed=["human_decisions"],
                decision_rights_tier=DecisionRightsTier.HIGH_IMPACT_GATED.value,
                containment_passed=True,
                status="APPROVED" if approved else "REJECTED",
                rationale_summary=f"Human judgment by '{actor_name}' on task '{task.name}': approved={approved}. Notes: {judgment_notes}",
            )

            # Advance runbook to unlock dependent automated steps
            self._advance_runbook(rb)
            return True

    def get_operational_dashboard(self, runbook_id: str) -> OperationalVisibilityDashboard:
        """Generates real-time single-pane-of-glass operational visibility."""
        with self._lock:
            if runbook_id not in self._runbooks:
                raise KeyError(f"Runbook '{runbook_id}' does not exist.")
            rb = self._runbooks[runbook_id]

            total_tasks = len(rb.tasks)
            completed = sum(1 for t in rb.tasks.values() if t.status == TaskExecutionStatus.COMPLETED)
            failed = sum(1 for t in rb.tasks.values() if t.status == TaskExecutionStatus.FAILED)
            pending_human = sum(
                1 for t in rb.tasks.values() if t.status == TaskExecutionStatus.AWAITING_HUMAN_APPROVAL
            )
            running_auto = sum(
                1 for t in rb.tasks.values() if t.status == TaskExecutionStatus.IN_PROGRESS
            )

            progress_pct = round((completed / max(1, total_tasks)) * 100.0, 1)

            # Calculate critical path delay
            delay = 0.0
            for tid in rb.critical_path_task_ids:
                t = rb.tasks[tid]
                if t.actual_duration_seconds > t.estimated_duration_seconds:
                    delay += (t.actual_duration_seconds - t.estimated_duration_seconds)

            telemetry = [
                {
                    "task_id": t.task_id,
                    "name": t.name,
                    "type": t.task_type.value,
                    "status": t.status.value,
                    "owner": t.assigned_owner,
                    "critical": t.critical_path,
                }
                for t in rb.tasks.values()
            ]

            return OperationalVisibilityDashboard(
                runbook_id=runbook_id,
                runbook_name=rb.name,
                use_case=rb.use_case.value,
                status=rb.status,
                overall_progress_pct=progress_pct,
                human_tasks_pending_count=pending_human,
                automated_tasks_running_count=running_auto,
                completed_tasks_count=completed,
                failed_tasks_count=failed,
                critical_path_delay_seconds=round(delay, 2),
                live_telemetry_feed=telemetry,
            )


# ==============================================================================
# 4. BATHTUB EFFECT RISK GOVERNOR
# ==============================================================================

class BathtubEffectRiskGovernor:
    """
    Mitigates the 'Bathtub Effect'—where initial progress is followed by a sharp
    complexity increase and performance dip due to scope creep, unresourced automation,
    or technical surprises.
    """

    @staticmethod
    def assess_runbook_risk(
        initial_task_count: int,
        current_task_count: int,
        failed_tasks_count: int,
        duration_variance_pct: float,
    ) -> BathtubEffectMetrics:
        scope_ratio = round(current_task_count / max(1, initial_task_count), 2)
        failure_rate = round((failed_tasks_count / max(1, current_task_count)) * 100.0, 1)

        recommendations: List[str] = []

        if scope_ratio >= 1.5 or failure_rate >= 20.0 or duration_variance_pct >= 40.0:
            risk = BathtubRiskLevel.HIGH_BATHTUB_COMPLEXITY_SPIKE
            recommendations.append("HALT SCOPE EXPANSION: Institute a formal change-freeze on runbook steps.")
            recommendations.append("INJECT HUMAN CHECKPOINTS: Replace fully unmonitored scripts with human decision gates.")
            recommendations.append("SCALE GRADUALLY: Decompose monolithic runbook into smaller, verified sub-workflows.")
        elif scope_ratio >= 1.2 or failure_rate >= 10.0 or duration_variance_pct >= 20.0:
            risk = BathtubRiskLevel.MODERATE_CREEP
            recommendations.append("Review recent tasks added since inception to prune non-essential steps.")
            recommendations.append("Verify resource allocation and operational owner availability.")
        else:
            risk = BathtubRiskLevel.LOW_STABLE
            recommendations.append("Workflow is operating within healthy collaborative automation bounds.")

        return BathtubEffectMetrics(
            initial_task_count=initial_task_count,
            current_task_count=current_task_count,
            scope_creep_ratio=scope_ratio,
            unexpected_failure_rate_pct=failure_rate,
            duration_variance_pct=duration_variance_pct,
            risk_level=risk,
            mitigation_recommendations=recommendations,
        )


# ==============================================================================
# 5. SPECIALIZED OPERATIONS ORCHESTRATORS (THE FOUR USE CASES)
# ==============================================================================

class DisasterRecoveryOrchestrator:
    """
    Use Case 1: Cyber and IT Disaster Recovery.
    Combines automated failover procedures with human-in-the-loop security sign-offs
    and immutable regulatory audit trails.
    """

    def __init__(self, engine: CollaborativeRunbookExecutionEngine) -> None:
        self.engine = engine

    def build_disaster_recovery_runbook(
        self,
        incident_id: str,
        target_datacenter_or_cloud: str,
    ) -> AutomatedRunbook:
        rb_id = f"dr_{incident_id}_{uuid.uuid4().hex[:8]}"
        rb = self.engine.create_runbook(
            runbook_id=rb_id,
            name=f"IT & Cyber DR Failover: {incident_id}",
            use_case=AutomationUseCaseType.CYBER_AND_IT_DISASTER_RECOVERY,
        )

        # Step 1: Automated containment & snapshot
        self.engine.add_task(
            rb_id,
            RunbookTask(
                task_id="dr_step_1",
                name="Automated Database Snapshot & Primary Isolation",
                task_type=RunbookTaskType.AUTOMATED_TASK,
                tool_category=AutomationToolCategory.IT_AUTOMATION,
                assigned_owner="dr_automation_agent",
                estimated_duration_seconds=120.0,
            ),
        )

        # Step 2: Human Security Analyst Go/No-Go Decision Gate
        self.engine.add_task(
            rb_id,
            RunbookTask(
                task_id="dr_step_2",
                name="Security Analyst Integrity & Ransomware Check Sign-Off",
                task_type=RunbookTaskType.HUMAN_IN_THE_LOOP,
                tool_category=AutomationToolCategory.COLLABORATIVE_RUNBOOK,
                assigned_owner="Lead Security Analyst",
                dependencies=["dr_step_1"],
                estimated_duration_seconds=300.0,
            ),
        )

        # Step 3: Automated Failover DNS & Compute Spin-Up
        self.engine.add_task(
            rb_id,
            RunbookTask(
                task_id="dr_step_3",
                name="Promote Secondary Standby & Update Route53/DNS",
                task_type=RunbookTaskType.AUTOMATED_TASK,
                tool_category=AutomationToolCategory.IT_AUTOMATION,
                assigned_owner="dr_automation_agent",
                dependencies=["dr_step_2"],
                estimated_duration_seconds=180.0,
                automated_payload={"target_region": target_datacenter_or_cloud},
            ),
        )

        # Step 4: Executive Incident Commander Final Certification
        self.engine.add_task(
            rb_id,
            RunbookTask(
                task_id="dr_step_4",
                name="Executive Disaster Recovery Sign-Off & Public Notification",
                task_type=RunbookTaskType.HUMAN_IN_THE_LOOP,
                tool_category=AutomationToolCategory.COLLABORATIVE_RUNBOOK,
                assigned_owner="Incident Commander",
                dependencies=["dr_step_3"],
                estimated_duration_seconds=180.0,
            ),
        )

        return rb


class CloudMigrationOrchestrator:
    """
    Use Case 2: Cloud Migration.
    Orchestrates complex multi-tier workload cutovers, provisioning infrastructure,
    verifying dependencies, and providing complete operational transparency.
    """

    def __init__(self, engine: CollaborativeRunbookExecutionEngine) -> None:
        self.engine = engine

    def build_cloud_migration_runbook(
        self,
        application_name: str,
        source_environment: str,
        target_cloud: str,
    ) -> AutomatedRunbook:
        rb_id = f"mig_{application_name.lower().replace(' ', '_')}_{uuid.uuid4().hex[:8]}"
        rb = self.engine.create_runbook(
            runbook_id=rb_id,
            name=f"Cloud Migration Cutover: {application_name}",
            use_case=AutomationUseCaseType.CLOUD_MIGRATION,
        )

        # Step 1: Automated infrastructure provisioning
        self.engine.add_task(
            rb_id,
            RunbookTask(
                task_id="mig_step_1",
                name="Provision Cloud VPC, Storage, and Kubernetes Clusters",
                task_type=RunbookTaskType.AUTOMATED_TASK,
                tool_category=AutomationToolCategory.IT_AUTOMATION,
                assigned_owner="terraform_cloud_agent",
                estimated_duration_seconds=300.0,
                automated_payload={"target_cloud": target_cloud},
            ),
        )

        # Step 2: Automated data sync & replication catch-up
        self.engine.add_task(
            rb_id,
            RunbookTask(
                task_id="mig_step_2",
                name="Database Sync & Delta Replication Catch-Up",
                task_type=RunbookTaskType.AUTOMATED_TASK,
                tool_category=AutomationToolCategory.IPAAS,
                assigned_owner="data_migration_worker",
                dependencies=["mig_step_1"],
                estimated_duration_seconds=240.0,
            ),
        )

        # Step 3: Human Cutover Verification & Go/No-Go Gate
        self.engine.add_task(
            rb_id,
            RunbookTask(
                task_id="mig_step_3",
                name="Database Consistency Verification & Cutover Approval",
                task_type=RunbookTaskType.DECISION_GATE,
                tool_category=AutomationToolCategory.COLLABORATIVE_RUNBOOK,
                assigned_owner="Database Administrator Lead",
                dependencies=["mig_step_2"],
                estimated_duration_seconds=180.0,
            ),
        )

        # Step 4: Automated Traffic Shift & Ingress Switch
        self.engine.add_task(
            rb_id,
            RunbookTask(
                task_id="mig_step_4",
                name="Shift Production Ingress Traffic to Cloud",
                task_type=RunbookTaskType.AUTOMATED_TASK,
                tool_category=AutomationToolCategory.IT_AUTOMATION,
                assigned_owner="ingress_traffic_agent",
                dependencies=["mig_step_3"],
                estimated_duration_seconds=60.0,
            ),
        )

        return rb


class ApplicationReleaseOrchestrator:
    """
    Use Case 3: Application Release Management.
    Synchronizes automated CI/CD pipelines, automated testing, and human stakeholder sign-off.
    """

    def __init__(self, engine: CollaborativeRunbookExecutionEngine) -> None:
        self.engine = engine

    def build_release_runbook(
        self,
        service_name: str,
        release_version: str,
    ) -> AutomatedRunbook:
        rb_id = f"rel_{service_name}_{release_version.replace('.', '_')}_{uuid.uuid4().hex[:8]}"
        rb = self.engine.create_runbook(
            runbook_id=rb_id,
            name=f"Release {service_name} v{release_version}",
            use_case=AutomationUseCaseType.APPLICATION_RELEASE_MANAGEMENT,
        )

        self.engine.add_task(
            rb_id,
            RunbookTask(
                task_id="rel_step_1",
                name="Deploy Canary Containers & Run Smoke Tests",
                task_type=RunbookTaskType.AUTOMATED_TASK,
                tool_category=AutomationToolCategory.IT_AUTOMATION,
                assigned_owner="cicd_pipeline_agent",
                estimated_duration_seconds=120.0,
            ),
        )

        self.engine.add_task(
            rb_id,
            RunbookTask(
                task_id="rel_step_2",
                name="Canary Telemetry & Error Budget Evaluation",
                task_type=RunbookTaskType.DECISION_GATE,
                tool_category=AutomationToolCategory.COLLABORATIVE_RUNBOOK,
                assigned_owner="Release Manager",
                dependencies=["rel_step_1"],
                estimated_duration_seconds=180.0,
            ),
        )

        self.engine.add_task(
            rb_id,
            RunbookTask(
                task_id="rel_step_3",
                name="Full Fleet Production Promotion",
                task_type=RunbookTaskType.AUTOMATED_TASK,
                tool_category=AutomationToolCategory.IT_AUTOMATION,
                assigned_owner="cicd_pipeline_agent",
                dependencies=["rel_step_2"],
                estimated_duration_seconds=90.0,
            ),
        )

        return rb


class TechnologyImplementationOrchestrator:
    """
    Use Case 4: Complex Technology Implementation.
    Eliminates errors from static implementation plans by orchestrating interdependent
    technical tasks with live stakeholder visibility.
    """

    def __init__(self, engine: CollaborativeRunbookExecutionEngine) -> None:
        self.engine = engine

    def build_implementation_runbook(
        self,
        project_name: str,
        system_components: List[str],
    ) -> AutomatedRunbook:
        rb_id = f"impl_{project_name.lower().replace(' ', '_')}_{uuid.uuid4().hex[:8]}"
        rb = self.engine.create_runbook(
            runbook_id=rb_id,
            name=f"Technology Implementation: {project_name}",
            use_case=AutomationUseCaseType.COMPLEX_TECHNOLOGY_IMPLEMENTATION,
        )

        # Interconnected sequence
        prev_id: Optional[str] = None
        for i, comp in enumerate(system_components, 1):
            tid = f"impl_step_{i}"
            deps = [prev_id] if prev_id else []
            self.engine.add_task(
                rb_id,
                RunbookTask(
                    task_id=tid,
                    name=f"Configure & Validate Component: {comp}",
                    task_type=RunbookTaskType.AUTOMATED_TASK,
                    tool_category=AutomationToolCategory.IT_AUTOMATION,
                    assigned_owner="system_provisioning_agent",
                    dependencies=deps,
                    estimated_duration_seconds=100.0,
                ),
            )
            prev_id = tid

        # Final Human Architecture Sign-Off
        self.engine.add_task(
            rb_id,
            RunbookTask(
                task_id="impl_final_signoff",
                name="Enterprise Architecture Commissioning Sign-Off",
                task_type=RunbookTaskType.HUMAN_IN_THE_LOOP,
                tool_category=AutomationToolCategory.COLLABORATIVE_RUNBOOK,
                assigned_owner="Chief Architect",
                dependencies=[prev_id] if prev_id else [],
                estimated_duration_seconds=150.0,
            ),
        )

        return rb


# ==============================================================================
# 6. MASTER COLLABORATIVE AUTOMATION SYSTEM
# ==============================================================================

class CollaborativeAutomationMasterSystem:
    """
    Master coordination platform implementing the full Technology Operations
    Guide to Collaborative Automation.
    """

    def __init__(self, ledger: Optional[AuditLedger] = None) -> None:
        self.ledger = ledger or AuditLedger()
        self.engine = CollaborativeRunbookExecutionEngine(self.ledger)
        self.dr_orchestrator = DisasterRecoveryOrchestrator(self.engine)
        self.migration_orchestrator = CloudMigrationOrchestrator(self.engine)
        self.release_orchestrator = ApplicationReleaseOrchestrator(self.engine)
        self.implementation_orchestrator = TechnologyImplementationOrchestrator(self.engine)
        self.bathtub_governor = BathtubEffectRiskGovernor()

    def run_collaborative_automation_assessment(
        self,
        active_runbooks_count: int,
        human_judgment_interventions_count: int,
        automated_actions_count: int,
        bathtub_scope_creep_ratio: float,
        bathtub_failure_rate_pct: float,
    ) -> Dict[str, Any]:
        """
        Executes a holistic assessment of collaborative automation health,
        verifying that people are valued and incorporated alongside automation.
        """
        audit_id = f"collab_eval_{uuid.uuid4().hex[:12]}"

        total_actions = human_judgment_interventions_count + automated_actions_count
        human_ratio_pct = round((human_judgment_interventions_count / max(1, total_actions)) * 100.0, 1)

        # Collaborative balance check: healthy collaborative automation keeps people in the loop
        is_symbiotic = 5.0 <= human_ratio_pct <= 40.0
        bathtub_risk = self.bathtub_governor.assess_runbook_risk(
            initial_task_count=10,
            current_task_count=int(10 * bathtub_scope_creep_ratio),
            failed_tasks_count=int(10 * (bathtub_failure_rate_pct / 100.0)),
            duration_variance_pct=15.0,
        )

        self.ledger.record_action(
            agent_id="collaborative_automation_system",
            accountable_owner="vp_technology_operations",
            action_type="COLLABORATIVE_AUTOMATION_ASSESSMENT",
            tool_name="CollaborativeAutomationMasterSystem.run_collaborative_automation_assessment",
            data_compartments_accessed=["tech_ops_telemetry"],
            decision_rights_tier=DecisionRightsTier.BOUNDED_AUTONOMY.value,
            containment_passed=is_symbiotic and bathtub_risk.risk_level != BathtubRiskLevel.HIGH_BATHTUB_COMPLEXITY_SPIKE,
            status="ASSESSMENT_COMPLETED",
            rationale_summary=(
                f"Assessment {audit_id}: Human involvement ratio={human_ratio_pct}%. "
                f"Symbiotic balance: {is_symbiotic}. Bathtub risk: {bathtub_risk.risk_level.value}."
            ),
        )

        return {
            "audit_id": audit_id,
            "human_in_the_loop_ratio_pct": human_ratio_pct,
            "is_symbiotic_collaboration": is_symbiotic,
            "bathtub_effect_assessment": asdict(bathtub_risk),
            "use_cases_enabled": [u.value for u in AutomationUseCaseType],
            "executive_summary": (
                "Collaborative automation is operating in a healthy symbiotic state: "
                "people provide critical judgment, awareness, and risk governance, "
                "while automation delivers speed, scale, and consistency."
                if is_symbiotic and bathtub_risk.risk_level != BathtubRiskLevel.HIGH_BATHTUB_COMPLEXITY_SPIKE
                else "Imbalance detected: either over-automating without human judgment (high Bathtub Effect risk) "
                "or failing to automate repetitive tasks."
            ),
        }
