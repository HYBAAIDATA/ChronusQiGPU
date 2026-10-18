"""McKinsey DevOps for IT Infrastructure Agility Framework.

Operationalizes the six fundamental shifts from Thomas Delaet & Ling Lau (McKinsey Digital):
"DevOps: The key to IT infrastructure agility"
Moving from legacy siloed "plan-build-run" ticket-based infrastructure to a unified,
API-driven, customer-centric software engineering operating model.

Quantified McKinsey Benchmark Targets:
- 25% to 30% increase in capacity creation
- 50% to 75% reduction in time to market (lead time)
- > 50% reduction in failure rates (change failure rate)

The Six Fundamental Shifts:
1. Work as One Team: Cross-functional units delivering full-stack infrastructure as self-service APIs.
2. Apply Design Thinking to IT Infrastructure: User personas, journey mapping, self-service catalogs,
   and rapid test-and-learn cycles.
3. Shift to Next-Gen Technical Practices: Declarative Infrastructure-as-Code (IaC), automated testing,
   continuous delivery of infrastructure (GitOps), and near-instantaneous auto-remediation.
4. Invest in Building Software Engineering Talent: Transitioning system administrators to infrastructure
   software engineers via immersive capability bootcamps.
5. Overinvest in Culture Change: Executive role modeling, embedded DevOps coaches, journey service teams,
   and adoption tracking.
6. Link Incentives to Delivery and Service Goals: Team-based balanced metrics harmonizing business value,
   time-to-market, availability SLA, quality, and employee satisfaction.
"""

from __future__ import annotations

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
    ContainmentInterceptor,
    ContainmentViolationError,
    DecisionRightsTier,
)


# ==============================================================================
# 1. ENUMS & CORE DOMAIN DEFINITIONS
# ==============================================================================

class FundamentalShiftType(str, Enum):
    """The six fundamental shifts required to extend DevOps into IT infrastructure."""
    WORK_AS_ONE_TEAM = "1_WORK_AS_ONE_TEAM"
    APPLY_DESIGN_THINKING = "2_APPLY_DESIGN_THINKING_TO_INFRASTRUCTURE"
    SHIFT_TO_NEXTGEN_PRACTICES = "3_SHIFT_TO_NEXTGEN_TECHNICAL_PRACTICES"
    INVEST_IN_SOFTWARE_TALENT = "4_INVEST_IN_SOFTWARE_ENGINEERING_TALENT"
    OVERINVEST_IN_CULTURE = "5_OVERINVEST_IN_CULTURE_CHANGE"
    LINK_INCENTIVES_TO_GOALS = "6_LINK_INCENTIVES_TO_DELIVERY_AND_SERVICE_GOALS"


class InfrastructureOperatingModel(str, Enum):
    """Evolutionary stages of the infrastructure operating model."""
    LEGACY_SILOED_PLAN_BUILD_RUN = "LEGACY_SILOED_PLAN_BUILD_RUN"
    TRANSITIONAL_AUTOMATED_SILOS = "TRANSITIONAL_AUTOMATED_SILOS"
    CROSS_FUNCTIONAL_DEVOPS_API = "CROSS_FUNCTIONAL_DEVOPS_API"
    AUTONOMOUS_AGILE_PLATFORM = "AUTONOMOUS_AGILE_PLATFORM"


class InfrastructureComponentType(str, Enum):
    """Core infrastructure domains formerly siloed under plan-build-run."""
    COMPUTE = "COMPUTE"
    STORAGE = "STORAGE"
    NETWORK = "NETWORK"
    SECURITY_GATEWAY = "SECURITY_GATEWAY"
    DATABASE_SUBSTRATE = "DATABASE_SUBSTRATE"
    OBSERVABILITY = "OBSERVABILITY"


# ==============================================================================
# 2. SHIFT 1: WORK AS ONE TEAM (API-DRIVEN SELF-SERVICE INFRASTRUCTURE)
# ==============================================================================

@dataclass
class InfrastructureServiceTemplate:
    """Standardized, cross-functional infrastructure product delivered as an API."""
    template_id: str
    name: str
    component_types: List[InfrastructureComponentType]
    version: str
    owner_team: str  # Cross-functional unified team
    declarative_spec: Dict[str, Any]
    sla_availability_target: float  # e.g. 99.99
    compliance_checks: List[str] = field(default_factory=list)


class UnifiedInfrastructureTeamEngine:
    """
    Shift 1: Work as one team.
    Eliminates siloed hand-offs across compute, network, and storage.
    Exposes the entire infrastructure solution as a self-service API.
    """

    def __init__(
        self,
        ledger: Optional[AuditLedger] = None,
        initial_operating_model: InfrastructureOperatingModel = InfrastructureOperatingModel.LEGACY_SILOED_PLAN_BUILD_RUN,
    ) -> None:
        self.ledger = ledger or AuditLedger()
        self._operating_model = initial_operating_model
        self._templates: Dict[str, InfrastructureServiceTemplate] = {}
        self._lock = threading.RLock()

    @property
    def current_operating_model(self) -> InfrastructureOperatingModel:
        with self._lock:
            return self._operating_model

    def transition_operating_model(
        self, new_model: InfrastructureOperatingModel, rationale: str = ""
    ) -> None:
        """Transitions the organization's infrastructure operating model toward cross-functional agility."""
        with self._lock:
            prev = self._operating_model
            self._operating_model = new_model
            self.ledger.record_action(
                agent_id="unified_infra_team_engine",
                accountable_owner="head_of_infrastructure",
                action_type="TRANSITION_OPERATING_MODEL",
                tool_name="UnifiedInfrastructureTeamEngine.transition_operating_model",
                data_compartments_accessed=["infrastructure_operating_model"],
                decision_rights_tier=DecisionRightsTier.BOUNDED_AUTONOMY.value,
                containment_passed=True,
                status="OPERATING_MODEL_TRANSITIONED",
                rationale_summary=f"Transitioned operating model from {prev.value} to {new_model.value}. {rationale}",
            )

    def register_service_template(
        self,
        template_or_id: Union[InfrastructureServiceTemplate, str],
        name: Optional[str] = None,
        component_types: Optional[List[InfrastructureComponentType]] = None,
        owner_team: Optional[str] = None,
        declarative_spec: Optional[Dict[str, Any]] = None,
        sla_target: float = 99.99,
        compliance_checks: Optional[List[str]] = None,
        registering_team: Optional[str] = None,
    ) -> InfrastructureServiceTemplate:
        """Registers a cross-functional infrastructure service product template."""
        with self._lock:
            if isinstance(template_or_id, InfrastructureServiceTemplate):
                template = template_or_id
            else:
                template = InfrastructureServiceTemplate(
                    template_id=template_or_id,
                    name=name or template_or_id,
                    component_types=component_types or [InfrastructureComponentType.COMPUTE],
                    version="v1.0",
                    owner_team=owner_team or registering_team or "Platform Team",
                    declarative_spec=declarative_spec or {},
                    sla_availability_target=sla_target,
                    compliance_checks=compliance_checks or ["AL_HARAS_ZERO_TRUST", "ENCRYPT_AT_REST"],
                )
            self._templates[template.template_id] = template

            self.ledger.record_action(
                agent_id="unified_infra_team_engine",
                accountable_owner=template.owner_team,
                action_type="REGISTER_INFRASTRUCTURE_SERVICE_TEMPLATE",
                tool_name="UnifiedInfrastructureTeamEngine.register_service_template",
                data_compartments_accessed=["infrastructure_templates"],
                decision_rights_tier=DecisionRightsTier.BOUNDED_AUTONOMY.value,
                containment_passed=True,
                status="TEMPLATE_REGISTERED",
                rationale_summary=f"Published unified self-service infra template '{template.name}' across {[c.value for c in template.component_types]}",
            )
            return template


    def get_template(self, template_id: str) -> Optional[InfrastructureServiceTemplate]:
        with self._lock:
            return self._templates.get(template_id)

    def list_templates(self) -> List[InfrastructureServiceTemplate]:
        with self._lock:
            return list(self._templates.values())


# ==============================================================================
# 3. SHIFT 2: APPLY DESIGN THINKING TO IT INFRASTRUCTURE
# ==============================================================================

@dataclass
class DeveloperPersona:
    """User persona consuming infrastructure (Application Developer, Data Scientist, ML Engineer)."""
    persona_id: str
    role_title: str
    key_tasks: List[str]
    pain_points: List[str]  # e.g. "Wait 2 weeks for network firewall ticket"
    delighters: List[str]   # e.g. "Instant 1-click sandbox with pre-approved security"


@dataclass
class JourneyStep:
    """Individual interaction step in the infrastructure provisioning journey."""
    step_id: str
    step_name: str
    is_automated: bool
    manual_ticket_required: bool
    duration_minutes: float
    friction_score: float  # 1.0 (seamless) to 10.0 (high friction)


@dataclass
class CustomerJourneyMap:
    """Maps the developer experience journey from application conception to production hosting."""
    journey_id: str
    developer_persona: str
    steps: List[JourneyStep]
    total_duration_hours: float
    average_friction_score: float
    has_manual_bottleneck: bool


class InfrastructureDesignThinkingEngine:
    """
    Shift 2: Apply design thinking to IT infrastructure.
    Focuses on developer customer journeys, eliminating manual ticket bottlenecks
    and measuring self-service friction.
    """

    @staticmethod
    def map_provisioning_journey(
        journey_id: str,
        persona: DeveloperPersona,
        steps: List[JourneyStep],
    ) -> CustomerJourneyMap:
        total_duration = round(sum(s.duration_minutes for s in steps) / 60.0, 2)
        avg_friction = round(sum(s.friction_score for s in steps) / max(1, len(steps)), 2)
        manual_bottleneck = any(s.manual_ticket_required for s in steps)

        return CustomerJourneyMap(
            journey_id=journey_id,
            developer_persona=persona.role_title,
            steps=steps,
            total_duration_hours=total_duration,
            average_friction_score=avg_friction,
            has_manual_bottleneck=manual_bottleneck,
        )

    @staticmethod
    def generate_delighter_catalog() -> List[Dict[str, Any]]:
        return [
            {
                "delighter_id": "DELIGHT-01",
                "feature": "1-Click Ephemeral Staging Environments",
                "impact": "Reduces dev provisioning lead time from 10 days to 90 seconds",
            },
            {
                "delighter_id": "DELIGHT-02",
                "feature": "Automated Policy-as-Code Pre-flight Compliance",
                "impact": "Eliminates security approval delays via deterministic guardrail gates",
            },
            {
                "delighter_id": "DELIGHT-03",
                "feature": "Self-Service Database Replica Provisioning",
                "impact": "Enables instant test-and-learn data validation with zero ticket friction",
            },
        ]


# ==============================================================================
# 4. SHIFT 3: NEXT-GENERATION TECHNICAL PRACTICES (IaC & GITOPS)
# ==============================================================================

@dataclass
class InfrastructureAsCodeSpec:
    """Declarative specification for infrastructure as code."""
    spec_id: str
    environment: str  # DEV, STAGING, PROD
    compute_units: int
    memory_gb: int
    storage_type: str
    network_vpc_id: str
    ingress_allowed_ports: List[int]
    immutable_audit_logging: bool = True
    tags: Dict[str, str] = field(default_factory=dict)

    def compute_spec_digest(self) -> str:
        canonical = json.dumps(asdict(self), sort_keys=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class IaCDeploymentResult:
    deployment_id: str
    spec_id: str
    status: str  # PROVISIONED, COMPLIANCE_FAILED, ROLLED_BACK
    provisioning_latency_seconds: float
    compliance_passed: bool
    drift_detected: bool
    details: Dict[str, Any]


class NextGenInfrastructurePracticesEngine:
    """
    Shift 3: Shift to next-generation technical practices.
    Implements Infrastructure-as-Code (IaC), automated testing, drift detection,
    and instantaneous GitOps continuous deployment.
    """

    def __init__(self, ledger: Optional[AuditLedger] = None) -> None:
        self.ledger = ledger or AuditLedger()
        self._active_deployments: Dict[str, InfrastructureAsCodeSpec] = {}
        self._lock = threading.RLock()

    def deploy_infrastructure_as_code(
        self,
        spec: InfrastructureAsCodeSpec,
        compliance_validator: Optional[Callable[[InfrastructureAsCodeSpec], bool]] = None,
    ) -> IaCDeploymentResult:
        with self._lock:
            start_time = time.time()
            dep_id = f"iac_{uuid.uuid4().hex[:12]}"

            # Policy-as-Code validation (e.g. no open SSH 22 in production, encryption mandated)
            compliance_passed = True
            if spec.environment == "PROD" and 22 in spec.ingress_allowed_ports:
                compliance_passed = False
            if compliance_validator is not None and not compliance_validator(spec):
                compliance_passed = False

            if not compliance_passed:
                latency = round(time.time() - start_time, 3)
                self.ledger.record_action(
                    agent_id="nextgen_infra_engine",
                    accountable_owner="platform_engineering_lead",
                    action_type="IAC_PROVISIONING_FAILED",
                    tool_name="NextGenInfrastructurePracticesEngine.deploy_infrastructure_as_code",
                    data_compartments_accessed=["iac_deployments"],
                    decision_rights_tier=DecisionRightsTier.BOUNDED_AUTONOMY.value,
                    containment_passed=False,
                    status="COMPLIANCE_BLOCKED",
                    rationale_summary=f"Deployment {dep_id} blocked: Insecure ports or policy-as-code failed",
                )
                return IaCDeploymentResult(
                    deployment_id=dep_id,
                    spec_id=spec.spec_id,
                    status="COMPLIANCE_FAILED",
                    provisioning_latency_seconds=latency,
                    compliance_passed=False,
                    drift_detected=False,
                    details={"error": "Policy-as-code security violation detected."},
                )

            # Successful automated provisioning
            self._active_deployments[dep_id] = spec
            latency = round(time.time() - start_time, 3)

            self.ledger.record_action(
                agent_id="nextgen_infra_engine",
                accountable_owner="platform_engineering_lead",
                action_type="IAC_PROVISIONING_SUCCESS",
                tool_name="NextGenInfrastructurePracticesEngine.deploy_infrastructure_as_code",
                data_compartments_accessed=["iac_deployments"],
                decision_rights_tier=DecisionRightsTier.BOUNDED_AUTONOMY.value,
                containment_passed=True,
                status="PROVISIONED",
                rationale_summary=f"Provisioned declarative IaC {spec.spec_id} ({spec.environment}) in {latency}s",
            )

            return IaCDeploymentResult(
                deployment_id=dep_id,
                spec_id=spec.spec_id,
                status="PROVISIONED",
                provisioning_latency_seconds=latency,
                compliance_passed=True,
                drift_detected=False,
                details={"digest": spec.compute_spec_digest(), "nodes_active": spec.compute_units},
            )

    def check_configuration_drift(
        self, deployment_id: str, live_spec: InfrastructureAsCodeSpec
    ) -> bool:
        """Compares live state against declarative source of truth to detect drift."""
        with self._lock:
            stored_spec = self._active_deployments.get(deployment_id)
            if not stored_spec:
                return True
            return stored_spec.compute_spec_digest() != live_spec.compute_spec_digest()


# ==============================================================================
# 5. SHIFT 4: INVEST IN SOFTWARE ENGINEERING TALENT
# ==============================================================================

@dataclass
class TalentUpskillingProfile:
    """Tracks the transition from traditional system administrator to infrastructure software engineer."""
    employee_id: str
    name: str
    legacy_role: str  # e.g. "Unix SysAdmin", "Storage Specialist"
    target_role: str  # e.g. "Site Reliability Engineer", "Platform Engineer"
    bootcamp_modules_completed: List[str]
    git_iac_proficiency_pct: float
    automated_testing_proficiency_pct: float
    learning_quotient_score: float  # 0.0 to 100.0


class InfraTalentBootcampManager:
    """
    Shift 4: Invest in building software engineering talent.
    Implements immersive boot camps, modern talent acquisition strategies,
    and capability building for infrastructure teams.
    """

    CORE_BOOTCAMP_CURRICULUM: List[str] = [
        "1. Declarative Infrastructure-as-Code (Terraform / CloudFormation)",
        "2. Automated Infrastructure Testing (Testinfra / Terratest)",
        "3. GitOps Continuous Delivery & Pipeline Orchestration",
        "4. Distributed Systems & High-Availability Topology",
        "5. AL HARAS Sovereign Security & Zero-Trust Architecture",
    ]

    def __init__(self) -> None:
        self._profiles: Dict[str, TalentUpskillingProfile] = {}
        self._lock = threading.RLock()

    def enroll_employee(
        self,
        employee_id: str,
        name: str,
        legacy_role: str,
        target_role: str = "Platform Engineer",
    ) -> TalentUpskillingProfile:
        with self._lock:
            profile = TalentUpskillingProfile(
                employee_id=employee_id,
                name=name,
                legacy_role=legacy_role,
                target_role=target_role,
                bootcamp_modules_completed=[],
                git_iac_proficiency_pct=15.0,
                automated_testing_proficiency_pct=10.0,
                learning_quotient_score=85.0,
            )
            self._profiles[employee_id] = profile
            return profile

    def complete_module(
        self, employee_id: str, module_name: str, proficiency_gain: float = 20.0
    ) -> TalentUpskillingProfile:
        with self._lock:
            if employee_id not in self._profiles:
                raise KeyError(f"Employee '{employee_id}' not enrolled in bootcamp.")
            prof = self._profiles[employee_id]
            if module_name not in prof.bootcamp_modules_completed:
                prof.bootcamp_modules_completed.append(module_name)
                prof.git_iac_proficiency_pct = min(100.0, prof.git_iac_proficiency_pct + proficiency_gain)
                prof.automated_testing_proficiency_pct = min(
                    100.0, prof.automated_testing_proficiency_pct + proficiency_gain
                )
            return prof

    def get_talent_readiness_index(self) -> float:
        """Returns average engineering proficiency across all enrolled infrastructure engineers."""
        with self._lock:
            if not self._profiles:
                return 0.0
            avg = sum(
                (p.git_iac_proficiency_pct + p.automated_testing_proficiency_pct) / 2.0
                for p in self._profiles.values()
            ) / len(self._profiles)
            return round(avg, 1)


# ==============================================================================
# 6. SHIFT 5: OVERINVEST IN CULTURE CHANGE
# ==============================================================================

@dataclass
class CultureChangeMetrics:
    """Tracks organizational and behavioral transformation towards DevOps."""
    executive_role_modeling_score: float  # 0.0 to 100.0
    active_devops_coaches_count: int
    journey_focused_service_teams_count: int
    blameless_postmortem_adoption_pct: float
    adoption_velocity_score: float  # 0.0 to 100.0
    status: str  # HIGH_MOMENTUM, HEALTHY_PROGRESS, CULTURAL_HEADWINDS


class DevOpsCultureGovernor:
    """
    Shift 5: Overinvest in culture change.
    Monitors executive vision articulation, coaching deployment,
    and end-to-end journey alignment.
    """

    @staticmethod
    def assess_culture(
        exec_modeling_score: float,
        devops_coaches: int,
        journey_service_teams: int,
        blameless_postmortems_pct: float,
    ) -> CultureChangeMetrics:
        velocity = (
            exec_modeling_score * 0.4
            + min(devops_coaches * 10.0, 30.0)
            + blameless_postmortems_pct * 0.3
        )
        velocity = min(round(velocity, 1), 100.0)

        if velocity >= 80.0:
            status = "HIGH_MOMENTUM"
        elif velocity >= 60.0:
            status = "HEALTHY_PROGRESS"
        else:
            status = "CULTURAL_HEADWINDS"

        return CultureChangeMetrics(
            executive_role_modeling_score=exec_modeling_score,
            active_devops_coaches_count=devops_coaches,
            journey_focused_service_teams_count=journey_service_teams,
            blameless_postmortem_adoption_pct=blameless_postmortems_pct,
            adoption_velocity_score=velocity,
            status=status,
        )


# ==============================================================================
# 7. SHIFT 6: LINK INCENTIVES TO DELIVERY AND SERVICE GOALS
# ==============================================================================

@dataclass
class DevOpsBalancedScorecard:
    """
    Shift 6: Balanced metrics harmonizing business value, delivery velocity,
    service availability, quality, and employee satisfaction.
    Directly measures McKinsey's quantified impact benchmarks.
    """
    # DORA Core Metrics
    deployment_frequency_per_day: float
    lead_time_for_changes_hours: float
    change_failure_rate_pct: float
    mean_time_to_recover_minutes: float

    # McKinsey Quantified Benchmark Impact
    capacity_creation_increase_pct: float  # Target: 25% to 30%
    time_to_market_reduction_pct: float    # Target: 50% to 75%
    failure_rate_reduction_pct: float      # Target: > 50%

    # Service & People Dimensions
    service_availability_sla_pct: float    # Target: >= 99.99%
    employee_satisfaction_enps: float      # Employee Net Promoter Score (-100 to +100)

    # Alignment status
    team_incentive_aligned: bool
    performance_tier: str  # ELITE_PERFORMER, HIGH_PERFORMER, MEDIUM_PERFORMER, LOW_PERFORMER


class DevOpsBalancedScorecardEngine:
    """
    Shift 6: Link incentives to delivery and service goals.
    Calculates team performance, aligning developers, infrastructure engineers,
    and business leaders.
    """

    @staticmethod
    def calculate_scorecard(
        deployments_per_day: float,
        lead_time_hours: float,
        change_failure_rate_pct: float,
        mttr_minutes: float,
        baseline_capacity_hours: float,
        actual_capacity_hours: float,
        baseline_ttm_days: float,
        actual_ttm_days: float,
        baseline_failure_rate: float,
        actual_failure_rate: float,
        availability_sla_pct: float,
        employee_enps: float,
    ) -> DevOpsBalancedScorecard:
        # 1. Capacity Creation Increase
        capacity_inc = round(
            ((actual_capacity_hours - baseline_capacity_hours) / max(1.0, baseline_capacity_hours)) * 100.0,
            1,
        )

        # 2. Time-to-Market Reduction
        ttm_reduction = round(
            ((baseline_ttm_days - actual_ttm_days) / max(1.0, baseline_ttm_days)) * 100.0,
            1,
        )

        # 3. Failure Rate Reduction
        failure_reduction = round(
            ((baseline_failure_rate - actual_failure_rate) / max(0.01, baseline_failure_rate)) * 100.0,
            1,
        )

        # Performance Tier Classification (DORA + McKinsey benchmarks)
        if (
            deployments_per_day >= 5.0
            and lead_time_hours <= 2.0
            and change_failure_rate_pct <= 5.0
            and capacity_inc >= 25.0
            and ttm_reduction >= 50.0
            and failure_reduction >= 50.0
        ):
            tier = "ELITE_PERFORMER"
            aligned = True
        elif deployments_per_day >= 1.0 and lead_time_hours <= 24.0 and change_failure_rate_pct <= 10.0:
            tier = "HIGH_PERFORMER"
            aligned = True
        elif deployments_per_day >= 0.2 and lead_time_hours <= 168.0:
            tier = "MEDIUM_PERFORMER"
            aligned = False
        else:
            tier = "LOW_PERFORMER"
            aligned = False

        return DevOpsBalancedScorecard(
            deployment_frequency_per_day=deployments_per_day,
            lead_time_for_changes_hours=lead_time_hours,
            change_failure_rate_pct=change_failure_rate_pct,
            mean_time_to_recover_minutes=mttr_minutes,
            capacity_creation_increase_pct=capacity_inc,
            time_to_market_reduction_pct=ttm_reduction,
            failure_rate_reduction_pct=failure_reduction,
            service_availability_sla_pct=availability_sla_pct,
            employee_satisfaction_enps=employee_enps,
            team_incentive_aligned=aligned,
            performance_tier=tier,
        )


# ==============================================================================
# 8. MASTER INFRASTRUCTURE AGILITY ORCHESTRATOR
# ==============================================================================

class DevOpsInfrastructureAgilityOrchestrator:
    """
    Master Enterprise Orchestrator synthesizing the six fundamental shifts
    for IT Infrastructure Agility.
    """

    def __init__(self, ledger: Optional[AuditLedger] = None) -> None:
        self.ledger = ledger or AuditLedger()
        self.team_engine = UnifiedInfrastructureTeamEngine(self.ledger)
        self.design_thinking = InfrastructureDesignThinkingEngine()
        self.nextgen_engine = NextGenInfrastructurePracticesEngine(self.ledger)
        self.talent_manager = InfraTalentBootcampManager()
        self.culture_governor = DevOpsCultureGovernor()
        self.scorecard_engine = DevOpsBalancedScorecardEngine()

    def run_full_infrastructure_agility_audit(
        self,
        operating_model: InfrastructureOperatingModel,
        developer_steps: List[JourneyStep],
        deployments_per_day: float,
        lead_time_hours: float,
        change_failure_rate_pct: float,
        mttr_minutes: float,
        baseline_capacity_hours: float,
        actual_capacity_hours: float,
        baseline_ttm_days: float,
        actual_ttm_days: float,
        baseline_failure_rate: float,
        actual_failure_rate: float,
        availability_sla_pct: float,
        employee_enps: float,
        exec_modeling_score: float,
        devops_coaches_count: int,
        journey_service_teams: int,
        blameless_postmortems_pct: float,
    ) -> Dict[str, Any]:
        """
        Executes an end-to-end audit across all six shifts and assesses realization
        of McKinsey's 25-30% capacity, 50-75% TTM reduction, and >50% failure reduction.
        """
        # Shift 1 & 2: Journey Mapping
        persona = DeveloperPersona(
            persona_id="dev-01",
            role_title="Enterprise Application Developer",
            key_tasks=["Ship new microservices", "Request staging DB and VPC network"],
            pain_points=["Manual ticket handoffs across storage/compute/network"],
            delighters=["Self-service API provisioning under 60 seconds"],
        )
        journey = self.design_thinking.map_provisioning_journey("journey-provisioning-01", persona, developer_steps)

        # Shift 4: Talent Readiness
        talent_index = self.talent_manager.get_talent_readiness_index()

        # Shift 5: Culture Assessment
        culture = self.culture_governor.assess_culture(
            exec_modeling_score=exec_modeling_score,
            devops_coaches=devops_coaches_count,
            journey_service_teams=journey_service_teams,
            blameless_postmortems_pct=blameless_postmortems_pct,
        )

        # Shift 6: Balanced Scorecard & Benchmark Achievement
        scorecard = self.scorecard_engine.calculate_scorecard(
            deployments_per_day=deployments_per_day,
            lead_time_hours=lead_time_hours,
            change_failure_rate_pct=change_failure_rate_pct,
            mttr_minutes=mttr_minutes,
            baseline_capacity_hours=baseline_capacity_hours,
            actual_capacity_hours=actual_capacity_hours,
            baseline_ttm_days=baseline_ttm_days,
            actual_ttm_days=actual_ttm_days,
            baseline_failure_rate=baseline_failure_rate,
            actual_failure_rate=actual_failure_rate,
            availability_sla_pct=availability_sla_pct,
            employee_enps=employee_enps,
        )

        # Check achievement of McKinsey's 3 core benchmarks
        benchmarks = {
            "capacity_creation_achieved": scorecard.capacity_creation_increase_pct >= 25.0,
            "ttm_reduction_achieved": scorecard.time_to_market_reduction_pct >= 50.0,
            "failure_reduction_achieved": scorecard.failure_rate_reduction_pct >= 50.0,
        }
        all_benchmarks_met = all(benchmarks.values())

        audit_id = f"devops_audit_{uuid.uuid4().hex[:12]}"

        # Audit result to cryptographic hash-chain ledger
        self.ledger.record_action(
            agent_id="devops_agility_orchestrator",
            accountable_owner="head_of_infrastructure",
            action_type="DEVOPS_INFRASTRUCTURE_AGILITY_AUDIT",
            tool_name="DevOpsInfrastructureAgilityOrchestrator.run_full_infrastructure_agility_audit",
            data_compartments_accessed=["infrastructure_operations_telemetry"],
            decision_rights_tier=DecisionRightsTier.BOUNDED_AUTONOMY.value,
            containment_passed=True,
            status="AUDIT_COMPLETED",
            rationale_summary=(
                f"Infrastructure agility audit completed: Operating model {operating_model.value}. "
                f"Performance tier: {scorecard.performance_tier}. All McKinsey benchmarks met: {all_benchmarks_met}."
            ),
        )

        return {
            "audit_id": audit_id,
            "operating_model": operating_model.value,
            "shifts_evaluated": [s.value for s in FundamentalShiftType],
            "customer_journey": asdict(journey),
            "talent_readiness_index": talent_index,
            "culture_metrics": asdict(culture),
            "balanced_scorecard": asdict(scorecard),
            "mckinsey_benchmarks": {
                "target_capacity_increase": "25% - 30%",
                "achieved_capacity_increase": f"{scorecard.capacity_creation_increase_pct}%",
                "target_ttm_reduction": "50% - 75%",
                "achieved_ttm_reduction": f"{scorecard.time_to_market_reduction_pct}%",
                "target_failure_rate_reduction": "> 50%",
                "achieved_failure_rate_reduction": f"{scorecard.failure_rate_reduction_pct}%",
                "all_benchmarks_met": all_benchmarks_met,
            },
            "executive_summary": (
                "IT Infrastructure has successfully cleared the agile bottleneck. "
                "Application development, operations, and infrastructure work as one unified team, "
                "delivering self-service APIs with continuous verification."
                if all_benchmarks_met
                else "Bottlenecks detected in manual ticket handoffs or cultural adoption; follow shift recommendations."
            ),
        }
