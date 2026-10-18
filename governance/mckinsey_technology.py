"""McKinsey Technology Transformation Substrate.

Modernizing technology and accelerating impact through three core approach pillars:
1. Reimagine the Role of Technology:
   Drive tech-forward business strategies, implement integrated solutions, and enhance digital experiences.
2. Reinvent Technology Delivery:
   Help organizations adopt agile workflows, next-gen infrastructure, and engineering excellence.
3. Rewire the Foundation:
   Modernize core platforms with adaptable architecture, minimize tech debt, ensure data ubiquity,
   and strengthen cybersecurity.

Delivering end-to-end tech-enabled transformations across six capability domains:
1. Infrastructure & Cloud: Multi-cloud optimization, elastic scalability, FinOps tokenomics.
2. Enterprise Architecture & Digital Platforms: Platform engineering, enterprise AI architecture, tech debt reduction.
3. Tech Resiliency & Cybersecurity: Digital resilience measurement, critical asset prioritization, build-or-buy decisions.
4. Adoption & Scaling: Tech-led operating models, 6-12 week bounded pilots, federated execution.
5. Tech Talent, Sourcing & Partnerships: AI-native workforce upskilling, partner ecosystems, vendor capability scaling.
6. Data & AI: Data products, digital twins, AI trust, and agentic governance integration.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from governance.agent_governance import (
    AgentGovernanceManifest,
    AgentInventoryRegistry,
    AuditLedger,
    AuditRecord,
    BoardReadinessAssessor,
    DecisionRightsTier,
    MCPGateway,
    ModelTierRouter,
    RollbackEngine,
    SovereigntyMode,
)


# ==============================================================================
# 1. TRANSFORMATION PILLARS & CLIENT DOMAINS
# ==============================================================================

class TransformationPillar(str, Enum):
    """The three core approach pillars of McKinsey Technology."""
    REIMAGINE_ROLE = "REIMAGINE_THE_ROLE_OF_TECHNOLOGY"
    REINVENT_DELIVERY = "REINVENT_TECHNOLOGY_DELIVERY"
    REWIRE_FOUNDATION = "REWIRE_THE_FOUNDATION"


class TransformationDomain(str, Enum):
    """The six client capability transformation domains."""
    INFRASTRUCTURE_CLOUD = "INFRASTRUCTURE_AND_CLOUD"
    ENTERPRISE_ARCHITECTURE = "ENTERPRISE_ARCHITECTURE_DIGITAL_PLATFORMS"
    TECH_RESILIENCY_CYBERSECURITY = "TECH_RESILIENCY_AND_CYBERSECURITY"
    ADOPTION_SCALING = "ADOPTION_AND_SCALING"
    TALENT_SOURCING_PARTNERSHIPS = "TECH_TALENT_SOURCING_PARTNERSHIPS"
    DATA_AND_AI = "DATA_AND_AI"


class BuildOrBuyVerdict(str, Enum):
    """Outcomes from strategic build-or-buy analysis."""
    BUILD_IN_HOUSE = "BUILD_IN_HOUSE"
    BUY_COMMERCIAL = "BUY_COMMERCIAL_OFF_THE_SHELF"
    STRATEGIC_PARTNERSHIP = "STRATEGIC_PARTNERSHIP"
    HYBRID_SCAFFOLD = "HYBRID_SCAFFOLD"


class PilotVerdict(str, Enum):
    """Outcomes from the 6-to-12 week bounded pilot framework."""
    SCALE_TO_PRODUCTION = "SCALE_TO_PRODUCTION"
    ITERATE_HYPOTHESIS = "ITERATE_HYPOTHESIS"
    PIVOT_BUSINESS_CASE = "PIVOT_BUSINESS_CASE"
    DECOMMISSION = "DECOMMISSION"


# ==============================================================================
# 2. ASSESSMENT & SCORECARD DATA STRUCTURES
# ==============================================================================

@dataclass
class DomainMaturityScore:
    """Maturity evaluation for a transformation domain."""
    domain: TransformationDomain
    score_pct: float  # 0.0 to 100.0
    current_tier: str  # TIER_1_FOUNDATIONAL, TIER_2_STRUCTURED, TIER_3_OPTIMIZED, TIER_4_TECH_LED
    strengths: List[str]
    gaps: List[str]
    recommendations: List[str]


@dataclass
class DigitalResilienceScore:
    """Measures technical and operational digital resilience."""
    resilience_score_pct: float  # 0.0 to 100.0
    rto_minutes: float  # Recovery Time Objective
    rpo_minutes: float  # Recovery Point Objective
    critical_asset_coverage_pct: float
    chaos_recovery_tested: bool
    cyber_containment_active: bool
    status: str  # HIGHLY_RESILIENT, ACCEPTABLE, ELEVATED_RISK, CRITICAL_DEFICIT


@dataclass
class TechDebtReport:
    """Measures architectural technical debt and refactoring priorities."""
    overall_debt_index: float  # 0.0 (clean) to 1.0 (crippling)
    estimated_remediation_weeks: float
    circular_dependencies_count: int
    deprecated_api_count: int
    unbounded_legacy_modules: List[str]
    critical_refactoring_targets: List[str]


@dataclass
class BuildOrBuyRecommendation:
    """Decision framework balancing differentiation, TCO, and sovereignty."""
    capability_name: str
    verdict: BuildOrBuyVerdict
    strategic_differentiation_score: float  # 0.0 to 1.0
    tco_advantage: str
    sovereignty_risk: str
    rationale: str


@dataclass
class DataProductManifest:
    """Defines an enterprise data product for data ubiquity and digital twins."""
    product_id: str
    name: str
    domain: str
    owner: str
    schema_version: str
    freshness_slo_seconds: float
    is_digital_twin_enabled: bool
    governance_classification: str  # PUBLIC, INTERNAL, SENSITIVE, STRICT_SOVEREIGN


@dataclass
class PilotEvaluation:
    """Tracks and evaluates 6-to-12 week bounded transformation pilots."""
    pilot_id: str
    name: str
    business_case: str
    duration_weeks: int
    target_roi_multiplier: float
    achieved_roi_multiplier: float
    user_adoption_pct: float
    safety_breaches_count: int
    verdict: PilotVerdict
    rationale: str


@dataclass
class TransformationAssessment:
    """Master assessment aggregating the 3 approach pillars and 6 domains."""
    assessment_id: str
    organization_name: str
    timestamp: float
    overall_maturity_score_pct: float
    pillar_scores: Dict[str, float]
    domain_scores: Dict[str, DomainMaturityScore]
    digital_resilience: DigitalResilienceScore
    tech_debt: TechDebtReport
    pilots_evaluated: List[PilotEvaluation]
    data_products_count: int
    executive_summary: str
    strategic_roadmap: List[Dict[str, Any]]


# ==============================================================================
# 3. DOMAIN ENGINES (HOW WE HELP CLIENTS)
# ==============================================================================

class InfrastructureCloudOptimizer:
    """
    Infrastructure & Cloud Domain:
    Optimizes multi-cloud environments, compute efficiency (Chronus scaling),
    and elastic cloud scalability.
    """

    @staticmethod
    def evaluate_multi_cloud_optimization(
        cloud_providers: List[str],
        workload_portability_score: float,
        elastic_scaling_tested: bool,
        monthly_spend_usd: float,
        waste_reduction_opportunity_pct: float,
    ) -> Dict[str, Any]:
        has_multi_cloud = len(cloud_providers) > 1
        efficiency_score = (workload_portability_score * 0.5) + (50.0 if elastic_scaling_tested else 0.0)

        potential_savings = monthly_spend_usd * (waste_reduction_opportunity_pct / 100.0)

        return {
            "efficiency_score": efficiency_score,
            "has_multi_cloud_resilience": has_multi_cloud,
            "providers": cloud_providers,
            "elastic_scaling_ready": elastic_scaling_tested,
            "monthly_spend_usd": monthly_spend_usd,
            "estimated_annual_savings_usd": potential_savings * 12.0,
            "status": "OPTIMIZED" if efficiency_score >= 80.0 else "REMEDIATION_RECOMMENDED",
            "recommendation": (
                "Workload portability is robust; expand FinOps dynamic allocation."
                if efficiency_score >= 80.0
                else "Implement containerised/substrate-agnostic runtimes to eliminate vendor lock-in."
            ),
        }


class EnterpriseArchitectureEngine:
    """
    Enterprise Architecture & Digital Platforms Domain:
    Platform engineering, AI architecture, modular service constitutions, and tech debt reduction.
    """

    @staticmethod
    def audit_tech_debt(
        total_loc: int,
        circular_dependencies: int,
        deprecated_routes: int,
        untested_critical_modules: int,
    ) -> TechDebtReport:
        # Debt calculation index from 0.0 to 1.0
        circ_penalty = min(circular_dependencies * 0.15, 0.40)
        depr_penalty = min(deprecated_routes * 0.05, 0.30)
        untested_penalty = min(untested_critical_modules * 0.10, 0.30)

        debt_index = round(circ_penalty + depr_penalty + untested_penalty, 2)
        est_weeks = round(debt_index * 12.0, 1)

        targets = []
        if circular_dependencies > 0:
            targets.append(f"Decouple {circular_dependencies} circular module cycles")
        if deprecated_routes > 0:
            targets.append(f"Decommission {deprecated_routes} deprecated API routes")
        if untested_critical_modules > 0:
            targets.append(f"Inject automated test harnesses into {untested_critical_modules} critical modules")

        return TechDebtReport(
            overall_debt_index=debt_index,
            estimated_remediation_weeks=est_weeks,
            circular_dependencies_count=circular_dependencies,
            deprecated_api_count=deprecated_routes,
            unbounded_legacy_modules=["legacy_core", "untyped_adapters"] if debt_index > 0.4 else [],
            critical_refactoring_targets=targets,
        )


class TechResiliencyCybersecurityGovernor:
    """
    Tech Resiliency & Cybersecurity Domain:
    Digital resilience scoring, critical asset prioritization (R0-R4 tiers),
    and build-or-buy strategic analysis.
    """

    @staticmethod
    def measure_digital_resilience(
        rto_minutes: float,
        rpo_minutes: float,
        critical_assets_isolated_pct: float,
        chaos_tested: bool,
        immutable_audit_active: bool,
    ) -> DigitalResilienceScore:
        # Benchmark targets: RTO < 60 min, RPO < 15 min
        rto_score = 30.0 if rto_minutes <= 60.0 else max(0.0, 30.0 - (rto_minutes - 60.0) * 0.2)
        rpo_score = 20.0 if rpo_minutes <= 15.0 else max(0.0, 20.0 - (rpo_minutes - 15.0) * 0.2)
        asset_score = critical_assets_isolated_pct * 0.3
        chaos_score = 10.0 if chaos_tested else 0.0
        audit_score = 10.0 if immutable_audit_active else 0.0

        total_score = round(rto_score + rpo_score + asset_score + chaos_score + audit_score, 1)

        if total_score >= 85.0:
            status = "HIGHLY_RESILIENT"
        elif total_score >= 70.0:
            status = "ACCEPTABLE"
        elif total_score >= 50.0:
            status = "ELEVATED_RISK"
        else:
            status = "CRITICAL_DEFICIT"

        return DigitalResilienceScore(
            resilience_score_pct=total_score,
            rto_minutes=rto_minutes,
            rpo_minutes=rpo_minutes,
            critical_asset_coverage_pct=critical_assets_isolated_pct,
            chaos_recovery_tested=chaos_tested,
            cyber_containment_active=immutable_audit_active,
            status=status,
        )

    @staticmethod
    def evaluate_build_or_buy(
        capability_name: str,
        is_core_differentiator: bool,
        estimated_internal_build_cost_usd: float,
        commercial_vendor_annual_license_usd: float,
        sovereignty_control_mandated: bool,
    ) -> BuildOrBuyRecommendation:
        """
        McKinsey build-or-buy framework:
        - If core differentiator or strict sovereignty required -> BUILD IN HOUSE
        - If commodity non-differentiating and vendor available -> BUY COTS
        - If complex ecosystem or hybrid -> STRATEGIC PARTNERSHIP
        """
        five_year_vendor_tco = commercial_vendor_annual_license_usd * 5.0

        if sovereignty_control_mandated or is_core_differentiator:
            verdict = BuildOrBuyVerdict.BUILD_IN_HOUSE
            diff_score = 0.95 if is_core_differentiator else 0.75
            rationale = (
                f"{capability_name} is a core competitive differentiator or legally mandates "
                "full sovereignty control. Third-party dependency creates unacceptable strategic risk."
            )
        elif estimated_internal_build_cost_usd > five_year_vendor_tco * 1.5:
            verdict = BuildOrBuyVerdict.BUY_COMMERCIAL
            diff_score = 0.20
            rationale = (
                f"{capability_name} is a commodity capability. Commercial off-the-shelf purchase "
                f"saves estimated ${round(estimated_internal_build_cost_usd - five_year_vendor_tco, 2)} over 5 years."
            )
        else:
            verdict = BuildOrBuyVerdict.STRATEGIC_PARTNERSHIP
            diff_score = 0.50
            rationale = (
                f"{capability_name} benefits from co-development with a certified partner to "
                "accelerate time to market while preserving core IP ownership."
            )

        return BuildOrBuyRecommendation(
            capability_name=capability_name,
            verdict=verdict,
            strategic_differentiation_score=diff_score,
            tco_advantage=(
                "Lower TCO via in-house IP longevity"
                if verdict == BuildOrBuyVerdict.BUILD_IN_HOUSE
                else "Lower TCO via commercial off-the-shelf scaling"
            ),
            sovereignty_risk="ZERO" if verdict == BuildOrBuyVerdict.BUILD_IN_HOUSE else "CONTRACTUALLY_MITIGATED",
            rationale=rationale,
        )


class AdoptionScalingCoordinator:
    """
    Adoption & Scaling Domain:
    Empowers organizations to become tech-led, managing 6-12 week bounded pilots
    and federated execution models.
    """

    @staticmethod
    def evaluate_pilot(
        pilot_id: str,
        name: str,
        business_case: str,
        duration_weeks: int,
        target_roi_multiplier: float,
        achieved_roi_multiplier: float,
        user_adoption_pct: float,
        safety_breaches_count: int,
    ) -> PilotEvaluation:
        # Enforce 6-to-12 week bound rule
        if not (6 <= duration_weeks <= 12):
            verdict = PilotVerdict.ITERATE_HYPOTHESIS
            rationale = f"Pilot duration of {duration_weeks} weeks violates 6-12 week bounded pilot rule."
        elif safety_breaches_count > 0:
            verdict = PilotVerdict.DECOMMISSION
            rationale = f"Pilot incurred {safety_breaches_count} safety breaches; cannot scale to production."
        elif achieved_roi_multiplier >= target_roi_multiplier and user_adoption_pct >= 70.0:
            verdict = PilotVerdict.SCALE_TO_PRODUCTION
            rationale = (
                f"Business case verified: achieved {achieved_roi_multiplier}x ROI "
                f"with {user_adoption_pct}% user adoption over {duration_weeks} weeks."
            )
        elif achieved_roi_multiplier >= target_roi_multiplier * 0.7:
            verdict = PilotVerdict.ITERATE_HYPOTHESIS
            rationale = "Promising ROI trajectory but adoption requires operational tuning before enterprise rollout."
        else:
            verdict = PilotVerdict.PIVOT_BUSINESS_CASE
            rationale = f"Achieved ROI ({achieved_roi_multiplier}x) significantly below target ({target_roi_multiplier}x)."

        return PilotEvaluation(
            pilot_id=pilot_id,
            name=name,
            business_case=business_case,
            duration_weeks=duration_weeks,
            target_roi_multiplier=target_roi_multiplier,
            achieved_roi_multiplier=achieved_roi_multiplier,
            user_adoption_pct=user_adoption_pct,
            safety_breaches_count=safety_breaches_count,
            verdict=verdict,
            rationale=rationale,
        )


class TechTalentSourcingManager:
    """
    Tech Talent, Sourcing & Partnerships Domain:
    AI-native employee upskilling, partner ecosystems, and vendor capability scaling.
    """

    @staticmethod
    def evaluate_workforce_readiness(
        total_technical_headcount: int,
        ai_native_trained_pct: float,
        human_in_the_loop_governor_count: int,
        strategic_partner_count: int,
    ) -> Dict[str, Any]:
        score = (ai_native_trained_pct * 0.6) + min(human_in_the_loop_governor_count * 5.0, 30.0) + min(strategic_partner_count * 2.5, 10.0)
        score = min(round(score, 1), 100.0)

        return {
            "talent_readiness_score_pct": score,
            "total_headcount": total_technical_headcount,
            "ai_native_trained_pct": ai_native_trained_pct,
            "certified_hitl_governors": human_in_the_loop_governor_count,
            "active_partnerships": strategic_partner_count,
            "status": "FUTURE_READY" if score >= 80.0 else "UPSKILLING_REQUIRED",
            "action_plan": (
                "Workforce is ready to govern high-autonomy agentic swarms."
                if score >= 80.0
                else "Accelerate internal training program for prompt engineering, kill-switch operations, and HITL supervision."
            ),
        }


class DataAITransformer:
    """
    Data & AI Domain:
    Data products, digital twins, AI trust, and agentic governance integration.
    """

    def __init__(self, ledger: Optional[AuditLedger] = None) -> None:
        self.ledger = ledger or AuditLedger()
        self._data_products: Dict[str, DataProductManifest] = {}

    def register_data_product(
        self,
        product_id: str,
        name: str,
        domain: str,
        owner: str,
        schema_version: str = "v1.0",
        freshness_slo_seconds: float = 300.0,
        is_digital_twin_enabled: bool = False,
        governance_classification: str = "INTERNAL",
    ) -> DataProductManifest:
        manifest = DataProductManifest(
            product_id=product_id,
            name=name,
            domain=domain,
            owner=owner,
            schema_version=schema_version,
            freshness_slo_seconds=freshness_slo_seconds,
            is_digital_twin_enabled=is_digital_twin_enabled,
            governance_classification=governance_classification,
        )
        self._data_products[product_id] = manifest

        self.ledger.record_action(
            agent_id="data_ai_transformer",
            accountable_owner=owner,
            action_type="REGISTER_DATA_PRODUCT",
            tool_name="DataAITransformer.register_data_product",
            data_compartments_accessed=[domain],
            decision_rights_tier="TIER_2_BOUNDED_AUTONOMY",
            containment_passed=True,
            status="REGISTERED",
            rationale_summary=f"Registered data product '{name}' in domain '{domain}' (Digital Twin: {is_digital_twin_enabled})",
        )
        return manifest

    def get_data_product(self, product_id: str) -> Optional[DataProductManifest]:
        return self._data_products.get(product_id)

    def list_data_products(self) -> List[DataProductManifest]:
        return list(self._data_products.values())


# ==============================================================================
# 4. MASTER TRANSFORMATION ORCHESTRATOR
# ==============================================================================

class McKinseyTechnologyTransformer:
    """
    Master Technology Transformation Orchestrator.
    Executes end-to-end technology transformations across the 3 approach pillars:
    1. Reimagine the role of technology
    2. Reinvent technology delivery
    3. Rewire the foundation
    And across the 6 client capability domains.
    """

    def __init__(
        self,
        registry: Optional[AgentInventoryRegistry] = None,
        gateway: Optional[MCPGateway] = None,
        ledger: Optional[AuditLedger] = None,
        rollback_engine: Optional[RollbackEngine] = None,
    ) -> None:
        self.ledger = ledger or AuditLedger()
        self.registry = registry or AgentInventoryRegistry()
        self.gateway = gateway or MCPGateway(self.registry, self.ledger)
        self.rollback_engine = rollback_engine or RollbackEngine(self.ledger)

        # Domain engines
        self.infra_cloud = InfrastructureCloudOptimizer()
        self.arch_engine = EnterpriseArchitectureEngine()
        self.cyber_governor = TechResiliencyCybersecurityGovernor()
        self.adoption_coordinator = AdoptionScalingCoordinator()
        self.talent_manager = TechTalentSourcingManager()
        self.data_ai = DataAITransformer(self.ledger)

    def run_full_enterprise_assessment(
        self,
        organization_name: str,
        cloud_providers: List[str],
        workload_portability: float,
        monthly_cloud_spend_usd: float,
        cloud_waste_pct: float,
        total_loc: int,
        circular_dependencies: int,
        deprecated_routes: int,
        untested_critical_modules: int,
        rto_minutes: float,
        rpo_minutes: float,
        critical_assets_isolated_pct: float,
        chaos_tested: bool,
        total_headcount: int,
        ai_trained_pct: float,
        hitl_supervisors: int,
        strategic_partners: int,
        pilots: Optional[List[PilotEvaluation]] = None,
    ) -> TransformationAssessment:
        """
        Executes an end-to-end transformation evaluation and generates a strategic roadmap.
        """
        # 1. Evaluate Infrastructure & Cloud
        cloud_eval = self.infra_cloud.evaluate_multi_cloud_optimization(
            cloud_providers=cloud_providers,
            workload_portability_score=workload_portability,
            elastic_scaling_tested=chaos_tested,
            monthly_spend_usd=monthly_cloud_spend_usd,
            waste_reduction_opportunity_pct=cloud_waste_pct,
        )
        infra_score = DomainMaturityScore(
            domain=TransformationDomain.INFRASTRUCTURE_CLOUD,
            score_pct=cloud_eval["efficiency_score"],
            current_tier="TIER_3_OPTIMIZED" if cloud_eval["efficiency_score"] >= 80 else "TIER_2_STRUCTURED",
            strengths=["Multi-cloud operational resilience", "Elastic capacity enabled"] if cloud_eval["has_multi_cloud_resilience"] else ["Standardized host cloud"],
            gaps=["Cloud waste reduction opportunity identified"] if cloud_waste_pct > 15.0 else [],
            recommendations=[cloud_eval["recommendation"]],
        )

        # 2. Evaluate Architecture & Tech Debt
        tech_debt = self.arch_engine.audit_tech_debt(
            total_loc=total_loc,
            circular_dependencies=circular_dependencies,
            deprecated_routes=deprecated_routes,
            untested_critical_modules=untested_critical_modules,
        )
        arch_score_val = max(0.0, round((1.0 - tech_debt.overall_debt_index) * 100.0, 1))
        arch_score = DomainMaturityScore(
            domain=TransformationDomain.ENTERPRISE_ARCHITECTURE,
            score_pct=arch_score_val,
            current_tier="TIER_3_OPTIMIZED" if arch_score_val >= 80 else "TIER_2_STRUCTURED",
            strengths=["Modular service constitution active", "Standardized contract interfaces"],
            gaps=[f"Architectural debt index at {tech_debt.overall_debt_index}"],
            recommendations=tech_debt.critical_refactoring_targets,
        )

        # 3. Evaluate Resilience & Cybersecurity
        chain_intact, _ = self.ledger.verify_chain()
        resilience = self.cyber_governor.measure_digital_resilience(
            rto_minutes=rto_minutes,
            rpo_minutes=rpo_minutes,
            critical_assets_isolated_pct=critical_assets_isolated_pct,
            chaos_tested=chaos_tested,
            immutable_audit_active=chain_intact,
        )
        resil_score = DomainMaturityScore(
            domain=TransformationDomain.TECH_RESILIENCY_CYBERSECURITY,
            score_pct=resilience.resilience_score_pct,
            current_tier="TIER_4_TECH_LED" if resilience.resilience_score_pct >= 85 else "TIER_3_OPTIMIZED",
            strengths=["Cryptographic audit chain active", "Zero-trust asset isolation"],
            gaps=["RTO exceeds 60m threshold"] if rto_minutes > 60 else [],
            recommendations=["Maintain automated continuous disaster recovery validation"],
        )

        # 4. Evaluate Adoption & Scaling
        pilots_list = pilots or []
        successful_pilots = sum(1 for p in pilots_list if p.verdict == PilotVerdict.SCALE_TO_PRODUCTION)
        adoption_val = round((successful_pilots / max(1, len(pilots_list))) * 100.0, 1) if pilots_list else 75.0
        adoption_score = DomainMaturityScore(
            domain=TransformationDomain.ADOPTION_SCALING,
            score_pct=adoption_val,
            current_tier="TIER_3_OPTIMIZED" if adoption_val >= 70 else "TIER_2_STRUCTURED",
            strengths=["6-12 week bounded pilot governance"],
            gaps=["Scale-out velocity friction"] if adoption_val < 70 else [],
            recommendations=["Promote vetted pilots to production through automated deployment pipelines"],
        )

        # 5. Evaluate Talent & Partnerships
        talent = self.talent_manager.evaluate_workforce_readiness(
            total_technical_headcount=total_headcount,
            ai_native_trained_pct=ai_trained_pct,
            human_in_the_loop_governor_count=hitl_supervisors,
            strategic_partner_count=strategic_partners,
        )
        talent_score = DomainMaturityScore(
            domain=TransformationDomain.TALENT_SOURCING_PARTNERSHIPS,
            score_pct=talent["talent_readiness_score_pct"],
            current_tier="TIER_3_OPTIMIZED" if talent["talent_readiness_score_pct"] >= 75 else "TIER_2_STRUCTURED",
            strengths=["Active HITL supervisor corps", "Cultivated partner ecosystem"],
            gaps=["AI-native training coverage below 80%"] if ai_trained_pct < 80 else [],
            recommendations=[talent["action_plan"]],
        )

        # 6. Evaluate Data & AI
        data_prods = self.data_ai.list_data_products()
        board_scorecard = BoardReadinessAssessor.evaluate_governance_posture(
            registry=self.registry,
            gateway=self.gateway,
            ledger=self.ledger,
            rollback_engine=self.rollback_engine,
        )
        data_ai_val = board_scorecard["readiness_score_pct"]
        data_ai_score = DomainMaturityScore(
            domain=TransformationDomain.DATA_AND_AI,
            score_pct=data_ai_val,
            current_tier="TIER_4_TECH_LED" if data_ai_val == 100.0 else "TIER_3_OPTIMIZED",
            strengths=["Isenberg Decision Rights Tiering", "MCP Gateway Leases", "Tamper-evident Audit Ledger"],
            gaps=[] if data_ai_val == 100.0 else ["Complete outstanding board audit questions"],
            recommendations=["Scale enterprise data products and digital twins under full-stack sovereignty"],
        )

        # Domain map
        domain_scores = {
            TransformationDomain.INFRASTRUCTURE_CLOUD.value: infra_score,
            TransformationDomain.ENTERPRISE_ARCHITECTURE.value: arch_score,
            TransformationDomain.TECH_RESILIENCY_CYBERSECURITY.value: resil_score,
            TransformationDomain.ADOPTION_SCALING.value: adoption_score,
            TransformationDomain.TALENT_SOURCING_PARTNERSHIPS.value: talent_score,
            TransformationDomain.DATA_AND_AI.value: data_ai_score,
        }

        # Pillar scores
        reimagine_score = round((adoption_val + data_ai_val) / 2.0, 1)
        reinvent_score = round((infra_score.score_pct + talent_score.score_pct) / 2.0, 1)
        rewire_score = round((arch_score.score_pct + resil_score.score_pct) / 2.0, 1)

        pillar_scores = {
            TransformationPillar.REIMAGINE_ROLE.value: reimagine_score,
            TransformationPillar.REINVENT_DELIVERY.value: reinvent_score,
            TransformationPillar.REWIRE_FOUNDATION.value: rewire_score,
        }

        overall_maturity = round((reimagine_score + reinvent_score + rewire_score) / 3.0, 1)

        # Strategic roadmap
        roadmap = [
            {
                "phase": "Phase 1: Rewire Foundation (Weeks 1-4)",
                "actions": [
                    "Remediate top architectural circular dependencies",
                    "Enforce immutable audit chains across all mutating workloads",
                    "Mandate MCP Gateway situational access for all agentic workflows",
                ],
                "expected_impact": "Zero unmonitored shadow agents; tech debt reduced by 40%",
            },
            {
                "phase": "Phase 2: Reinvent Technology Delivery (Weeks 5-8)",
                "actions": [
                    "Deploy multi-cloud elastic compute auto-scaling",
                    "Certify 80%+ of developers in AI-native prompt & HITL governance",
                    "Execute automated chaos recovery drills",
                ],
                "expected_impact": "RTO < 30 minutes; FinOps waste cut by 25%",
            },
            {
                "phase": "Phase 3: Reimagine the Role of Technology (Weeks 9-12)",
                "actions": [
                    "Scale validated 6-12 week bounded pilots to production",
                    "Publish enterprise data products with digital twin integration",
                    "Deliver Board Readiness 100% compliance certificate",
                ],
                "expected_impact": "Accelerated business ROI; scalable trusted innovation",
            },
        ]

        assessment = TransformationAssessment(
            assessment_id=f"mck_trans_{uuid.uuid4().hex[:12]}",
            organization_name=organization_name,
            timestamp=time.time(),
            overall_maturity_score_pct=overall_maturity,
            pillar_scores=pillar_scores,
            domain_scores=domain_scores,
            digital_resilience=resilience,
            tech_debt=tech_debt,
            pilots_evaluated=pilots_list,
            data_products_count=len(data_prods),
            executive_summary=(
                f"{organization_name} achieves an overall transformation maturity score of {overall_maturity}%. "
                f"Digital resilience is rated {resilience.status} ({resilience.resilience_score_pct}%). "
                f"Core foundations are rewired with non-bypassable guardrails and verifiable decision rights."
            ),
            strategic_roadmap=roadmap,
        )

        # Audit the transformation assessment
        self.ledger.record_action(
            agent_id="mckinsey_transformation_engine",
            accountable_owner="chief_technology_officer",
            action_type="ENTERPRISE_TRANSFORMATION_ASSESSMENT",
            tool_name="McKinseyTechnologyTransformer.run_full_enterprise_assessment",
            data_compartments_accessed=["enterprise_architecture_state"],
            decision_rights_tier="TIER_3_HIGH_IMPACT_GATED",
            containment_passed=True,
            status="ASSESSMENT_COMPLETED",
            rationale_summary=f"Completed transformation assessment for {organization_name}: maturity {overall_maturity}%",
        )

        return assessment
