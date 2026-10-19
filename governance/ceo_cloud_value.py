"""McKinsey Framework: Three Actions CEOs Can Take to Get Value from Cloud Computing.

Operationalizes the strategic leadership framework from Chhavi Arora, Tanguy Catlin,
Will Forrest, James Kaplan, and Lars Vinter (McKinsey Digital / McKinsey Quarterly, July 21, 2020).

Addresses the enterprise transition to cloud as a fundamental *collective-action problem*
that requires CEO orchestration across the C-suite:
- CEO: Baton-wielder and orchestrator, providing air cover for CIO/CTO and demanding business unit adoption.
- CFO: Co-architect of a sustainable funding model, managing the "double-bubble" cost curve and FinOps.
- CIO & CTO: Co-creators of the business-technology operating model, platform-as-a-product, and cloud-native velocity.
- CHRO: Partner in overhauling legacy HR, compensation caps, dual-track engineering careers, and location policies.
- CISO: Partner in embedding automated security landing zones and compliance-as-code guardrails.
- Business-Unit Heads: Held accountable for redesigning commercial processes to leverage cloud elasticity,
  eliminating the excuse of "subpar technology."

The Three CEO Interventions:
1. Establish a Sustainable Funding Model (with the CFO):
   - Overcome rigid annual CapEx budgeting with dynamic value-stream OpEx allocation.
   - Actively model and manage the transition "double bubble" (parallel on-prem run costs + cloud build costs).
   - Implement real-time FinOps governance, unit economics, and bill shock mitigation.
2. Develop a New Business-Technology Operating Model (with the CIO/CTO and Business Leads):
   - Move from siloed, ticket-based legacy IT to self-service cloud platform-as-a-product.
   - Empower cross-functional BizDevSecOps product teams to release features in days.
   - Enforce business-unit accountability: business leaders must redesign customer workflows and adopt cloud.
3. Put in Place HR, Compensation, and Location Strategies (with the CHRO):
   - Uncouple specialized cloud engineering compensation from traditional managerial salary caps.
   - Institute dual career ladders (Distinguished Engineer / Technical Fellow peer to VP/Director).
   - Modernize location policies: build specialized tech hubs in innovation centers and enable distributed talent.
   - Scale in-house cloud academies for continuous workforce upskilling.
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
    DecisionRightsTier,
)


# ==============================================================================
# 1. ENUMS & CORE C-SUITE STAKEHOLDER DEFINITIONS
# ==============================================================================

class CEOCloudActionType(str, Enum):
    """The three executive interventions defined by McKinsey for CEOs."""
    ACTION_1_SUSTAINABLE_FUNDING_MODEL = "1_ESTABLISH_SUSTAINABLE_FUNDING_MODEL"
    ACTION_2_BUSINESS_TECH_OPERATING_MODEL = "2_DEVELOP_BUSINESS_TECH_OPERATING_MODEL"
    ACTION_3_TALENT_COMPENSATION_LOCATION = "3_HR_COMPENSATION_LOCATION_POLICIES"


class CSuiteStakeholderRole(str, Enum):
    """Key stakeholders in the cloud collective-action problem."""
    CEO = "CHIEF_EXECUTIVE_OFFICER"
    CFO = "CHIEF_FINANCIAL_OFFICER"
    CIO = "CHIEF_INFORMATION_OFFICER"
    CTO = "CHIEF_TECHNOLOGY_OFFICER"
    CHRO = "CHIEF_HUMAN_RESOURCES_OFFICER"
    CISO = "CHIEF_INFORMATION_SECURITY_OFFICER"
    BUSINESS_UNIT_LEAD = "BUSINESS_UNIT_LEAD"


class FundingModelType(str, Enum):
    """Evolutionary stages of cloud financial management."""
    LEGACY_PROJECT_CAPEX = "LEGACY_PROJECT_CAPEX"
    DOUBLE_BUBBLE_TRANSITION = "DOUBLE_BUBBLE_TRANSITION"
    VALUE_LINKED_OPEX_FINOPS = "VALUE_LINKED_OPEX_FINOPS"
    PRODUCT_STREAM_DYNAMIC_ALLOCATION = "PRODUCT_STREAM_DYNAMIC_ALLOCATION"


class CloudOperatingModelTier(str, Enum):
    """Maturity stages of the business-technology operating model."""
    CENTRAL_IT_TICKET_BASED = "CENTRAL_IT_TICKET_BASED"
    LIFT_AND_SHIFT_HOSTING = "LIFT_AND_SHIFT_HOSTING"
    PLATFORM_AS_A_PRODUCT = "PLATFORM_AS_A_PRODUCT"
    BIZDEVSECOPS_AUTONOMOUS_VALUE_STREAM = "BIZDEVSECOPS_AUTONOMOUS_VALUE_STREAM"


class CareerTrackType(str, Enum):
    """Career progression tracks for technology talent."""
    MANAGEMENT_LADDER = "MANAGEMENT_LADDER"
    DISTINGUISHED_ENGINEER_TECHNICAL_FELLOW = "DISTINGUISHED_ENGINEER_TECHNICAL_FELLOW"


# ==============================================================================
# 2. ACTION 1: ESTABLISH A SUSTAINABLE FUNDING MODEL (WITH THE CFO)
# ==============================================================================

@dataclass
class DoubleBubbleForecast:
    """
    Models the 'double bubble' financial trajectory during cloud migration:
    simultaneous run costs of legacy data centers alongside cloud investment and ramp costs.
    """
    duration_years: int
    legacy_datacenter_baseline_annual: float  # e.g., $50M/yr
    annual_cloud_migration_investment: float  # e.g., $15M/yr
    annual_cloud_run_cost: float              # e.g., ramps from $5M to $35M
    annual_decommissioned_legacy_savings: float  # e.g., ramps up as DC shuts down
    net_annual_expenditure: float
    double_bubble_premium_annual: float       # Extra cost above legacy baseline
    is_bubble_peaked: bool
    crossover_year_achieved: bool             # When net spend drops below baseline


@dataclass
class FinOpsUnitEconomics:
    """Real-time FinOps governance metrics to eliminate cloud bill shock."""
    monthly_cloud_spend_usd: float
    cost_per_active_user_usd: float
    cost_per_business_transaction_usd: float
    tagging_compliance_pct: float             # Must be >= 95%
    resource_rightsizing_efficiency_pct: float  # CPU/RAM utilization efficiency
    reserved_or_savings_plan_coverage_pct: float
    unallocated_waste_spend_usd: float
    bill_shock_anomaly_detected: bool


@dataclass
class ValueDrivenFundingRequest:
    """Value-linked funding request replacing traditional infrastructure CapEx."""
    request_id: str
    business_domain: str
    initiative_name: str
    requested_budget_usd: float
    projected_business_value_usd: float
    projected_roi_multiple: float
    time_to_first_value_months: float
    approval_status: str                      # APPROVED, MODIFIED, REJECTED
    funding_rationale: str


class SustainableFundingEngine:
    """
    Action 1: Establish a sustainable funding model to support the investments
    required to get business value from the cloud (partnership with CFO).
    """

    def __init__(self, ledger: Optional[AuditLedger] = None) -> None:
        self.ledger = ledger or AuditLedger()
        self._funding_requests: Dict[str, ValueDrivenFundingRequest] = {}
        self._lock = threading.RLock()

    def model_double_bubble_trajectory(
        self,
        legacy_annual_baseline: float,
        migration_duration_years: int,
        year_index: int,
        cloud_migration_investment: float,
        cloud_run_cost: float,
        decommissioned_savings: float,
    ) -> DoubleBubbleForecast:
        """
        Calculates the financial dynamics of the double-bubble period, enabling
        the CEO and CFO to budget sufficient air cover before decommissioning pays off.
        """
        net_annual = (
            legacy_annual_baseline
            + cloud_migration_investment
            + cloud_run_cost
            - decommissioned_savings
        )
        double_bubble_premium = max(0.0, net_annual - legacy_annual_baseline)
        crossover = net_annual <= legacy_annual_baseline and decommissioned_savings > 0

        # Peaked if cloud migration investment has reached midpoint or decommissioning has started
        is_peaked = year_index >= max(1, migration_duration_years // 2)

        return DoubleBubbleForecast(
            duration_years=migration_duration_years,
            legacy_datacenter_baseline_annual=round(legacy_annual_baseline, 2),
            annual_cloud_migration_investment=round(cloud_migration_investment, 2),
            annual_cloud_run_cost=round(cloud_run_cost, 2),
            annual_decommissioned_legacy_savings=round(decommissioned_savings, 2),
            net_annual_expenditure=round(net_annual, 2),
            double_bubble_premium_annual=round(double_bubble_premium, 2),
            is_bubble_peaked=is_peaked,
            crossover_year_achieved=crossover,
        )

    def evaluate_finops_governance(
        self,
        monthly_spend: float,
        monthly_active_users: int,
        monthly_transactions: int,
        tagging_pct: float,
        rightsizing_pct: float,
        savings_plan_pct: float,
        anomaly_spike_pct: float = 0.0,
    ) -> FinOpsUnitEconomics:
        """Evaluates cloud unit economics and detects bill shock anomalies."""
        cost_per_user = round(monthly_spend / max(1, monthly_active_users), 4)
        cost_per_tx = round(monthly_spend / max(1, monthly_transactions), 4)
        
        # Estimate unallocated or wasted spend from lack of tagging or rightsizing
        waste_pct = max(0.0, (100.0 - rightsizing_pct) * 0.4 + (100.0 - tagging_pct) * 0.2)
        waste_usd = round(monthly_spend * (waste_pct / 100.0), 2)
        bill_shock = anomaly_spike_pct >= 25.0 or waste_usd > (monthly_spend * 0.25)

        return FinOpsUnitEconomics(
            monthly_cloud_spend_usd=monthly_spend,
            cost_per_active_user_usd=cost_per_user,
            cost_per_business_transaction_usd=cost_per_tx,
            tagging_compliance_pct=tagging_pct,
            resource_rightsizing_efficiency_pct=rightsizing_pct,
            reserved_or_savings_plan_coverage_pct=savings_plan_pct,
            unallocated_waste_spend_usd=waste_usd,
            bill_shock_anomaly_detected=bill_shock,
        )

    def allocate_value_driven_funding(
        self,
        domain: str,
        initiative_name: str,
        requested_budget: float,
        projected_value: float,
        time_to_first_value_months: float,
        executive_sponsor: str = "CFO",
    ) -> ValueDrivenFundingRequest:
        """
        Allocates cloud funding based on business ROI and speed to value,
        rather than treating cloud as a static IT cost-center line item.
        """
        with self._lock:
            req_id = f"fund_{uuid.uuid4().hex[:10]}"
            roi_multiple = round(projected_value / max(1.0, requested_budget), 2)

            if roi_multiple >= 3.0 and time_to_first_value_months <= 6.0:
                status = "APPROVED"
                rationale = f"High-yield business innovation: {roi_multiple}x ROI with fast delivery ({time_to_first_value_months} mo)."
            elif roi_multiple >= 1.5 and time_to_first_value_months <= 12.0:
                status = "APPROVED"
                rationale = f"Viable core modernization: {roi_multiple}x ROI within 12 months."
            elif roi_multiple >= 1.0:
                status = "MODIFIED"
                rationale = f"Marginal return ({roi_multiple}x); conditionally approved subject to scope optimization."
            else:
                status = "REJECTED"
                rationale = f"Insufficient business return ({roi_multiple}x); funding withheld per CEO/CFO value governance."

            req = ValueDrivenFundingRequest(
                request_id=req_id,
                business_domain=domain,
                initiative_name=initiative_name,
                requested_budget_usd=requested_budget,
                projected_business_value_usd=projected_value,
                projected_roi_multiple=roi_multiple,
                time_to_first_value_months=time_to_first_value_months,
                approval_status=status,
                funding_rationale=rationale,
            )
            self._funding_requests[req_id] = req

            self.ledger.record_action(
                agent_id="sustainable_funding_engine",
                accountable_owner=executive_sponsor,
                action_type="ALLOCATE_VALUE_DRIVEN_FUNDING",
                tool_name="SustainableFundingEngine.allocate_value_driven_funding",
                data_compartments_accessed=["cloud_financial_allocation"],
                decision_rights_tier=DecisionRightsTier.BOUNDED_AUTONOMY.value,
                containment_passed=True,
                status=status,
                rationale_summary=f"Funding request {req_id} for '{initiative_name}' ({domain}): {status}. {rationale}",
            )
            return req


# ==============================================================================
# 3. ACTION 2: DEVELOP A NEW BUSINESS-TECHNOLOGY OPERATING MODEL (CIO/CTO & BUs)
# ==============================================================================

@dataclass
class PlatformAsAProductSpec:
    """Self-service platform asset produced by the centralized cloud platform team."""
    product_id: str
    name: str
    description: str
    target_users: List[str]                  # Developers, Data Scientists, Product Owners
    self_service_api_available: bool
    provisioning_sla_seconds: float          # e.g., < 120s
    built_in_security_guardrails: List[str]  # Landing zone, OPA, encryption, IAM
    monthly_active_dev_consumers: int


@dataclass
class BusinessUnitAccountabilityScorecard:
    """
    Enforces the CEO's demand that Business-Unit heads actively redesign
    processes to capture cloud speed, rather than blaming IT.
    """
    business_unit_name: str
    business_unit_lead_name: str
    cloud_adoption_pct: float                 # Target: >= 70%
    processes_digitally_redesigned_pct: float # Target: >= 60%
    deployment_lead_time_days: float          # Target: <= 5 days
    commercial_velocity_increase_pct: float  # Target: >= 30%
    it_blaming_excuses_logged_count: int      # Target: 0 (no more deflection)
    is_accountability_met: bool
    performance_verdict: str


class CloudOperatingModelEngine:
    """
    Action 2: Develop a new business-technology operating model that exploits
    cloud for speed, agility, and efficient scalability (with CIO, CTO, and BU heads).
    """

    def __init__(self, ledger: Optional[AuditLedger] = None) -> None:
        self.ledger = ledger or AuditLedger()
        self._platform_products: Dict[str, PlatformAsAProductSpec] = {}
        self._bu_scorecards: Dict[str, BusinessUnitAccountabilityScorecard] = {}
        self._lock = threading.RLock()

    def register_platform_product(
        self,
        product_id: str,
        name: str,
        description: str,
        target_users: List[str],
        self_service_api_available: bool,
        provisioning_sla_seconds: float,
        built_in_security_guardrails: List[str],
        active_consumers: int = 0,
    ) -> PlatformAsAProductSpec:
        """Registers a platform-as-a-product capability for self-service consumption."""
        with self._lock:
            product = PlatformAsAProductSpec(
                product_id=product_id,
                name=name,
                description=description,
                target_users=target_users,
                self_service_api_available=self_service_api_available,
                provisioning_sla_seconds=provisioning_sla_seconds,
                built_in_security_guardrails=built_in_security_guardrails,
                monthly_active_dev_consumers=active_consumers,
            )
            self._platform_products[product_id] = product

            self.ledger.record_action(
                agent_id="cloud_operating_model_engine",
                accountable_owner="chief_technology_officer",
                action_type="REGISTER_PLATFORM_PRODUCT",
                tool_name="CloudOperatingModelEngine.register_platform_product",
                data_compartments_accessed=["cloud_platform_products"],
                decision_rights_tier=DecisionRightsTier.BOUNDED_AUTONOMY.value,
                containment_passed=True,
                status="PRODUCT_REGISTERED",
                rationale_summary=f"Published platform-as-a-product '{name}' with {len(built_in_security_guardrails)} guardrails",
            )
            return product

    def evaluate_business_unit_accountability(
        self,
        bu_name: str,
        lead_name: str,
        cloud_adoption_pct: float,
        redesigned_processes_pct: float,
        lead_time_days: float,
        commercial_velocity_increase_pct: float,
        it_blaming_excuses_count: int,
    ) -> BusinessUnitAccountabilityScorecard:
        """
        Evaluates whether a business unit is fulfilling the CEO mandate to leverage
        the cloud for speed and innovation, without deflecting to legacy IT excuses.
        """
        with self._lock:
            # McKinsey mandate: BUs must adopt cloud and redesign customer journeys
            meets_adoption = cloud_adoption_pct >= 70.0
            meets_redesign = redesigned_processes_pct >= 50.0
            meets_velocity = commercial_velocity_increase_pct >= 25.0
            zero_deflection = it_blaming_excuses_count == 0

            accountability_met = (
                meets_adoption and meets_redesign and meets_velocity and zero_deflection
            )

            if accountability_met:
                verdict = "HIGH_PERFORMANCE_VALUE_CREATOR"
            elif meets_adoption and zero_deflection:
                verdict = "PROGRESSING_ADOPTER"
            elif it_blaming_excuses_count > 0:
                verdict = "DEFLECTING_TO_LEGACY_EXCUSES"
            else:
                verdict = "UNDERPERFORMING_LAGGARD"

            scorecard = BusinessUnitAccountabilityScorecard(
                business_unit_name=bu_name,
                business_unit_lead_name=lead_name,
                cloud_adoption_pct=cloud_adoption_pct,
                processes_digitally_redesigned_pct=redesigned_processes_pct,
                deployment_lead_time_days=lead_time_days,
                commercial_velocity_increase_pct=commercial_velocity_increase_pct,
                it_blaming_excuses_logged_count=it_blaming_excuses_count,
                is_accountability_met=accountability_met,
                performance_verdict=verdict,
            )
            self._bu_scorecards[bu_name] = scorecard

            self.ledger.record_action(
                agent_id="cloud_operating_model_engine",
                accountable_owner="chief_executive_officer",
                action_type="ASSESS_BU_CLOUD_ACCOUNTABILITY",
                tool_name="CloudOperatingModelEngine.evaluate_business_unit_accountability",
                data_compartments_accessed=["business_unit_cloud_performance"],
                decision_rights_tier=DecisionRightsTier.BOUNDED_AUTONOMY.value,
                containment_passed=True,
                status="ACCOUNTABILITY_ASSESSED",
                rationale_summary=f"BU '{bu_name}' ({lead_name}) evaluated: {verdict}. Met: {accountability_met}.",
            )
            return scorecard

    def determine_operating_model_tier(
        self,
        self_service_api_pct: float,
        automated_guardrails_pct: float,
        cross_functional_teams_pct: float,
        feature_release_cycle_days: float,
    ) -> CloudOperatingModelTier:
        """Determines enterprise-wide business-technology operating model tier."""
        if (
            self_service_api_pct >= 85.0
            and automated_guardrails_pct >= 90.0
            and cross_functional_teams_pct >= 80.0
            and feature_release_cycle_days <= 3.0
        ):
            return CloudOperatingModelTier.BIZDEVSECOPS_AUTONOMOUS_VALUE_STREAM
        elif self_service_api_pct >= 60.0 and automated_guardrails_pct >= 70.0:
            return CloudOperatingModelTier.PLATFORM_AS_A_PRODUCT
        elif self_service_api_pct >= 20.0:
            return CloudOperatingModelTier.LIFT_AND_SHIFT_HOSTING
        else:
            return CloudOperatingModelTier.CENTRAL_IT_TICKET_BASED


# ==============================================================================
# 4. ACTION 3: HR, COMPENSATION, AND LOCATION POLICIES (WITH THE CHRO)
# ==============================================================================

@dataclass
class SpecializedCloudRoleProfile:
    """Specialized cloud engineering profile breaking legacy IT salary caps."""
    role_id: str
    title: str                                # e.g. Principal Cloud Architect, Staff SRE
    legacy_salary_cap_usd: float              # Traditional IT cap, e.g. $140,000
    market_competitive_salary_usd: float      # Competitive benchmark, e.g. $260,000
    uncoupled_from_legacy_bands: bool
    salary_premium_unlocked_pct: float


@dataclass
class DualCareerTrackAppointment:
    """
    Appoints a distinguished individual contributor on the technical fellow ladder,
    matching or exceeding VP/Director compensation without requiring people management.
    """
    appointment_id: str
    employee_id: str
    name: str
    specialization_domain: str                # e.g., Distributed Cloud Storage, Serverless Mesh
    career_track: CareerTrackType
    peer_executive_equivalent_level: str      # e.g. "Vice President / Managing Director"
    management_duties_required: bool          # False: 100% technical focus
    total_compensation_usd: float
    equity_or_long_term_incentive_eligible: bool


@dataclass
class LocationAndSourcingPolicy:
    """
    Modern location strategy removing rigid low-cost center mandates
    and establishing innovation hubs in premier talent markets.
    """
    innovation_hub_cities: List[str]          # e.g., Seattle, Bay Area, Austin, London, Zurich
    distributed_remote_engineering_allowed_pct: float  # e.g., up to 100%
    legacy_low_cost_location_mandate_removed: bool
    average_time_to_hire_days: float
    talent_acceptance_rate_pct: float


class CloudTalentStrategyEngine:
    """
    Action 3: Put in place the HR, compensation, and location strategies
    to attract and retain world-class cloud talent (partnership with CHRO).
    """

    def __init__(self, ledger: Optional[AuditLedger] = None) -> None:
        self.ledger = ledger or AuditLedger()
        self._specialized_roles: Dict[str, SpecializedCloudRoleProfile] = {}
        self._dual_track_appointments: Dict[str, DualCareerTrackAppointment] = {}
        self._lock = threading.RLock()

    def uncouple_compensation_from_legacy_bands(
        self,
        role_id: str,
        title: str,
        legacy_salary_cap: float,
        market_competitive_salary: float,
    ) -> SpecializedCloudRoleProfile:
        """
        Removes legacy HR salary band restrictions that prevent hiring top cloud engineers.
        """
        with self._lock:
            premium = round(
                ((market_competitive_salary - legacy_salary_cap) / max(1.0, legacy_salary_cap)) * 100.0,
                1,
            )
            profile = SpecializedCloudRoleProfile(
                role_id=role_id,
                title=title,
                legacy_salary_cap_usd=legacy_salary_cap,
                market_competitive_salary_usd=market_competitive_salary,
                uncoupled_from_legacy_bands=True,
                salary_premium_unlocked_pct=premium,
            )
            self._specialized_roles[role_id] = profile

            self.ledger.record_action(
                agent_id="cloud_talent_strategy_engine",
                accountable_owner="chief_human_resources_officer",
                action_type="UNCOUPLE_LEGACY_COMPENSATION_BANDS",
                tool_name="CloudTalentStrategyEngine.uncouple_compensation_from_legacy_bands",
                data_compartments_accessed=["hr_compensation_policies"],
                decision_rights_tier=DecisionRightsTier.BOUNDED_AUTONOMY.value,
                containment_passed=True,
                status="COMPENSATION_UNCOUPLED",
                rationale_summary=f"Uncoupled role '{title}' from legacy band ({legacy_salary_cap} -> {market_competitive_salary}, +{premium}%)",
            )
            return profile

    def appoint_dual_career_track_fellow(
        self,
        employee_id: str,
        name: str,
        specialization_domain: str,
        total_compensation: float,
        peer_level: str = "Vice President",
        equity_eligible: bool = True,
    ) -> DualCareerTrackAppointment:
        """
        Creates an individual contributor executive technical track, enabling elite
        engineers to advance without being forced into people management.
        """
        with self._lock:
            app_id = f"dual_track_{uuid.uuid4().hex[:10]}"
            appointment = DualCareerTrackAppointment(
                appointment_id=app_id,
                employee_id=employee_id,
                name=name,
                specialization_domain=specialization_domain,
                career_track=CareerTrackType.DISTINGUISHED_ENGINEER_TECHNICAL_FELLOW,
                peer_executive_equivalent_level=peer_level,
                management_duties_required=False,
                total_compensation_usd=total_compensation,
                equity_or_long_term_incentive_eligible=equity_eligible,
            )
            self._dual_track_appointments[employee_id] = appointment

            self.ledger.record_action(
                agent_id="cloud_talent_strategy_engine",
                accountable_owner="chief_human_resources_officer",
                action_type="APPOINT_TECHNICAL_FELLOW",
                tool_name="CloudTalentStrategyEngine.appoint_dual_career_track_fellow",
                data_compartments_accessed=["hr_career_tracks"],
                decision_rights_tier=DecisionRightsTier.BOUNDED_AUTONOMY.value,
                containment_passed=True,
                status="APPOINTED",
                rationale_summary=f"Appointed {name} as Technical Fellow (peer to {peer_level}) in {specialization_domain} with zero management duty requirement",
            )
            return appointment

    def modernize_location_strategy(
        self,
        innovation_hubs: List[str],
        distributed_remote_pct: float,
        average_time_to_hire_days: float,
        acceptance_rate_pct: float,
    ) -> LocationAndSourcingPolicy:
        """
        Eliminates rigid legacy off-shoring mandates, replacing them with
        high-gravity innovation hubs and distributed talent acquisition.
        """
        return LocationAndSourcingPolicy(
            innovation_hub_cities=innovation_hubs,
            distributed_remote_engineering_allowed_pct=distributed_remote_pct,
            legacy_low_cost_location_mandate_removed=True,
            average_time_to_hire_days=average_time_to_hire_days,
            talent_acceptance_rate_pct=acceptance_rate_pct,
        )


# ==============================================================================
# 5. MASTER ORCHESTRATOR: CEO CLOUD VALUE ORCHESTRATOR
# ==============================================================================

class CEOCloudValueOrchestrator:
    """
    Master Orchestrator executing the CEO's 'baton-wielding' role across the top team.
    Solves the collective-action problem across CEO, CFO, CIO, CTO, CHRO, CISO, and BUs.
    """

    def __init__(self, ledger: Optional[AuditLedger] = None) -> None:
        self.ledger = ledger or AuditLedger()
        self.funding_engine = SustainableFundingEngine(self.ledger)
        self.operating_model_engine = CloudOperatingModelEngine(self.ledger)
        self.talent_engine = CloudTalentStrategyEngine(self.ledger)

    def verify_csuite_collective_action_alignment(
        self,
        stakeholder_commitments: Dict[CSuiteStakeholderRole, bool],
    ) -> Dict[str, Any]:
        """
        Verifies that all members of the top team are aligned on the cloud transformation.
        Identifies any lagging executive function that threatens the collective effort.
        """
        all_aligned = all(stakeholder_commitments.values())
        dissenting_roles = [
            role.value for role, committed in stakeholder_commitments.items() if not committed
        ]

        return {
            "collective_action_aligned": all_aligned,
            "total_stakeholders_committed": sum(1 for c in stakeholder_commitments.values() if c),
            "total_stakeholders_required": len(CSuiteStakeholderRole),
            "dissenting_or_unaligned_roles": dissenting_roles,
            "air_cover_status": "FULL_AIR_COVER_ACTIVE" if all_aligned else "COLLECTIVE_ACTION_FRICTION",
        }

    def execute_ceo_cloud_value_audit(
        self,
        # Collective Action Stakeholders
        csuite_commitments: Dict[CSuiteStakeholderRole, bool],
        # Action 1: Sustainable Funding & Double Bubble
        legacy_annual_baseline: float,
        migration_duration_years: int,
        current_year_index: int,
        cloud_migration_investment: float,
        cloud_run_cost: float,
        decommissioned_savings: float,
        monthly_spend: float,
        monthly_active_users: int,
        monthly_transactions: int,
        tagging_compliance_pct: float,
        rightsizing_efficiency_pct: float,
        savings_plan_coverage_pct: float,
        # Action 2: Operating Model & BU Accountability
        self_service_api_pct: float,
        automated_guardrails_pct: float,
        cross_functional_teams_pct: float,
        feature_release_cycle_days: float,
        bu_scorecards: List[BusinessUnitAccountabilityScorecard],
        # Action 3: HR, Compensation & Location Strategy
        specialized_roles_uncoupled_count: int,
        dual_track_fellows_count: int,
        innovation_hubs: List[str],
        distributed_remote_pct: float,
        time_to_hire_days: float,
        talent_acceptance_rate_pct: float,
    ) -> Dict[str, Any]:
        """
        Executes a comprehensive CEO cloud value audit synthesizing all three interventions
        and verifying C-suite collective action orchestration.
        """
        audit_id = f"ceo_cloud_audit_{uuid.uuid4().hex[:12]}"

        # 1. Collective Action Check
        alignment = self.verify_csuite_collective_action_alignment(csuite_commitments)

        # 2. Action 1: Funding & Double Bubble Analysis
        double_bubble = self.funding_engine.model_double_bubble_trajectory(
            legacy_annual_baseline=legacy_annual_baseline,
            migration_duration_years=migration_duration_years,
            year_index=current_year_index,
            cloud_migration_investment=cloud_migration_investment,
            cloud_run_cost=cloud_run_cost,
            decommissioned_savings=decommissioned_savings,
        )
        finops = self.funding_engine.evaluate_finops_governance(
            monthly_spend=monthly_spend,
            monthly_active_users=monthly_active_users,
            monthly_transactions=monthly_transactions,
            tagging_pct=tagging_compliance_pct,
            rightsizing_pct=rightsizing_efficiency_pct,
            savings_plan_pct=savings_plan_coverage_pct,
        )

        # 3. Action 2: Operating Model & BU Accountability
        operating_model_tier = self.operating_model_engine.determine_operating_model_tier(
            self_service_api_pct=self_service_api_pct,
            automated_guardrails_pct=automated_guardrails_pct,
            cross_functional_teams_pct=cross_functional_teams_pct,
            feature_release_cycle_days=feature_release_cycle_days,
        )
        bu_accountability_met = all(bu.is_accountability_met for bu in bu_scorecards)

        # 4. Action 3: Talent, Compensation & Location Strategy
        location_policy = self.talent_engine.modernize_location_strategy(
            innovation_hubs=innovation_hubs,
            distributed_remote_pct=distributed_remote_pct,
            average_time_to_hire_days=time_to_hire_days,
            acceptance_rate_pct=talent_acceptance_rate_pct,
        )
        talent_transformation_sound = (
            specialized_roles_uncoupled_count >= 3
            and dual_track_fellows_count >= 1
            and location_policy.legacy_low_cost_location_mandate_removed
            and talent_acceptance_rate_pct >= 75.0
        )

        # Overall CEO Cloud Value Readiness Assessment
        all_actions_healthy = (
            alignment["collective_action_aligned"]
            and not finops.bill_shock_anomaly_detected
            and operating_model_tier in (
                CloudOperatingModelTier.PLATFORM_AS_A_PRODUCT,
                CloudOperatingModelTier.BIZDEVSECOPS_AUTONOMOUS_VALUE_STREAM,
            )
            and bu_accountability_met
            and talent_transformation_sound
        )

        # Cryptographic Audit Record
        self.ledger.record_action(
            agent_id="ceo_cloud_value_orchestrator",
            accountable_owner="chief_executive_officer",
            action_type="EXECUTE_CEO_CLOUD_VALUE_AUDIT",
            tool_name="CEOCloudValueOrchestrator.execute_ceo_cloud_value_audit",
            data_compartments_accessed=["executive_cloud_governance_telemetry"],
            decision_rights_tier=DecisionRightsTier.BOUNDED_AUTONOMY.value,
            containment_passed=True,
            status="AUDIT_COMPLETED",
            rationale_summary=(
                f"CEO Cloud Value Audit {audit_id}: All actions healthy={all_actions_healthy}. "
                f"Operating tier: {operating_model_tier.value}. Collective alignment: {alignment['air_cover_status']}."
            ),
        )

        return {
            "audit_id": audit_id,
            "csuite_collective_action": alignment,
            "action_1_sustainable_funding": {
                "double_bubble_forecast": asdict(double_bubble),
                "finops_unit_economics": asdict(finops),
                "double_bubble_air_cover_adequate": not finops.bill_shock_anomaly_detected,
            },
            "action_2_operating_model": {
                "operating_model_tier": operating_model_tier.value,
                "business_unit_accountability_met": bu_accountability_met,
                "business_units_evaluated": [asdict(bu) for bu in bu_scorecards],
            },
            "action_3_talent_compensation_location": {
                "specialized_roles_uncoupled_count": specialized_roles_uncoupled_count,
                "dual_track_fellows_count": dual_track_fellows_count,
                "location_and_sourcing_policy": asdict(location_policy),
                "talent_transformation_sound": talent_transformation_sound,
            },
            "overall_ceo_cloud_readiness": {
                "all_interventions_healthy": all_actions_healthy,
                "executive_mandate_summary": (
                    "The CEO has successfully orchestrated the C-suite collective-action problem. "
                    "A sustainable funding model cushions the double bubble, a self-service operating model "
                    "enforces business-unit accountability, and modern compensation and location policies "
                    "attract top cloud talent."
                    if all_actions_healthy
                    else "Interventions required: Resolve C-suite friction, uncouple compensation, or enforce business unit accountability."
                ),
            },
        }
