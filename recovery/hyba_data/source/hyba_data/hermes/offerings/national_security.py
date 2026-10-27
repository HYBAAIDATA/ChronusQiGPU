from __future__ import annotations

from typing import Any, Mapping

from al_haras.security_core import CryptographicAuditChain
from .millennium_math_adapter import MillenniumMathsAPI
from .toe_platform_adapter import TOEPlatformAdapter

PHI = (1.0 + 5.0**0.5) / 2.0


class NationalSecurityOffering:
    """HYBA national-security inventory with TOE, Millennium Maths and Salamander boundaries.

    This class describes the consolidated architecture and its evidence status.
    It does not provision production infrastructure or establish readiness.
    """

    def __init__(
        self,
        *,
        audit: CryptographicAuditChain | None = None,
        toe_adapter: TOEPlatformAdapter | None = None,
        millennium_api: MillenniumMathsAPI | None = None,
    ):
        self.phi = PHI
        self.audit = audit or CryptographicAuditChain(use_merkle=True)
        self.toe_adapter = toe_adapter or TOEPlatformAdapter()
        self.millennium_api = millennium_api or MillenniumMathsAPI()
        self.stack = self._build_stack()
        self.comparison = self._build_comparison()
        self.audit.add_entry("HYBA_NATIONAL_SECURITY_INVENTORY_INIT")

    def _build_stack(self) -> dict[str, Any]:
        return {
            "reasoning_platform": {
                "name": "TOE",
                "role": (
                    "Canonical domain-general reasoning runtime and evidence/receipt "
                    "substrate for the consolidated HYBA offering."
                ),
                "integration_contract": "toe.problem.Problem + toe.runtime.TOEIntelligenceRuntime",
                "status": "ADAPTER_PRESENT_RUNTIME_VALIDATION_REQUIRED",
                "claim_boundary": (
                    "Runtime availability, evidence quality and production readiness "
                    "must be verified in the target environment."
                ),
            },
            "mathematical_platform": {
                "name": "Millennium Maths API",
                "role": (
                    "Separate bounded mathematical probe service; supplies scoped "
                    "mathematical evidence, not mission authority or proofs of open problems."
                ),
                "integration_contract": "MILLENNIUM_API_BASE_URL + allow-listed /millennium endpoints",
                "status": "CLIENT_PRESENT_ENDPOINT_CONFIGURATION_REQUIRED",
                "claim_boundary": (
                    "The service endpoint must be configured and authenticated. "
                    "Finite numerical probes are not proofs of open Millennium problems."
                ),
            },
            "intelligence": {
                "name": "HYBA Five-Form Intelligence",
                "description": (
                    "Predictive, causal, counterfactual, topological and geometric "
                    "reasoning lenses integrated through shared evidence contracts."
                ),
                "canonical_forms": [
                    "predictive",
                    "causal",
                    "counterfactual",
                    "topological",
                    "geometric",
                ],
                "capabilities": [
                    "Predictive early-warning hypotheses with measured uncertainty",
                    "Causal analysis with explicit assumptions",
                    "Counterfactual scenario comparison",
                    "Topological relationship and connectivity analysis",
                    "Geometric state-space and trajectory analysis",
                ],
                "status": "IMPLEMENTATION_PRESENT_VALIDATION_REQUIRED",
                "claim_boundary": (
                    "No fixed accuracy or operational effectiveness claim without "
                    "reproducible evaluation on a defined, held-out dataset."
                ),
            },
            "resilience": {
                "name": "Salamander Autonomic Control Plane",
                "role": (
                    "Canonical adaptive-resilience layer for anomaly detection, "
                    "fault diagnosis, bounded self-healing and measured self-optimization."
                ),
                "integration_contract": (
                    "salamander.control_plane.AutonomicControlPlane + salamander.models"
                ),
                "capabilities": [
                    "Typed health and anomaly evidence",
                    "Registered bounded recovery plans",
                    "Post-action verification and rollback",
                    "Replay, shadow/canary evaluation and policy lifecycle",
                ],
                "status": "CANONICAL_COMPONENT_PRESENT_END_TO_END_INTEGRATION_REQUIRED",
                "claim_boundary": (
                    "This offering inventory does not instantiate or qualify the "
                    "control plane. Only registered, policy-authorized actions may run; "
                    "unavailable telemetry is not healthy and handler success is not "
                    "proof of recovery."
                ),
            },
            "security": {
                "name": "HYBA AL HARAS and L-HRAS Governance",
                "description": (
                    "Consolidated tenant/capability admission, policy governance, "
                    "defensive assessment and evidence recording."
                ),
                "components": [
                    "al_haras runtime and entitlement boundary",
                    "al_haras.paradigm_shift.SecurityGovernor",
                    "al_haras.security_core audit primitives",
                    "l_hras.guardian governed assessment path",
                ],
                "capabilities": [
                    "Policy-bound allow/deny/escalate decisions where wired",
                    "Tamper-evident local audit primitives",
                    "Evidence-linked security assessment",
                    "Controlled defensive response integration",
                ],
                "status": "INTEGRATION_AND_DEPLOYMENT_EVIDENCE_REQUIRED",
                "claim_boundary": (
                    "A local hash chain is not by itself WORM storage, an external "
                    "witness, hardware-backed attestation or a certification."
                ),
            },
            "optimization": {
                "name": "Classical-first Defensive Optimization",
                "description": (
                    "Optional ranking of authorized defensive plans; optimization "
                    "does not grant authority or execute actions."
                ),
                "capabilities": [
                    "Deterministic baseline and feasibility checks",
                    "Benchmarkable classical and quantum-inspired methods",
                    "Optional provider-backed quantum experiments when configured",
                ],
                "status": "EXPERIMENTAL_UNTIL_BENCHMARKED",
                "claim_boundary": (
                    "No quantum-hardware, quantum-advantage or quantum-resistant "
                    "claim without implementation-specific evidence."
                ),
            },
            "operations": {
                "name": "National-Security Decision Support",
                "description": (
                    "Authorized early warning, scenario analysis, defensive cyber "
                    "risk triage, resilience planning and auditable recommendations."
                ),
                "capabilities": [
                    "Analyst-reviewed risk and scenario assessments",
                    "Source provenance and uncertainty reporting",
                    "Purpose limitation and tenant-scoped access",
                    "Outcome verification and incident feedback",
                ],
                "status": "READINESS_REQUIRES_ENVIRONMENT_SPECIFIC_VALIDATION",
            },
        }

    def assess_with_toe(
        self,
        observation: Mapping[str, Any],
        *,
        tenant_id: str,
        purpose: str,
    ) -> dict[str, Any]:
        """Run a TOE-backed advisory assessment after caller authorization."""
        result = self.toe_adapter.assess(
            observation,
            tenant_id=tenant_id,
            purpose=purpose,
        )
        status = str(result.get("status", "unavailable"))
        # Never put observation contents into the audit log.
        self.audit.add_entry(f"HYBA_TOE_ASSESSMENT|{status}|{tenant_id}|{purpose}")
        result["hyba_audit_integrity"] = self.audit.verify_integrity()
        return result

    def run_millennium_math(
        self,
        operation: str,
        payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run a bounded math probe separately from mission-data assessment.

        Callers must supply only non-sensitive mathematical parameters. This
        method deliberately does not accept or forward the TOE observation.
        """
        result = self.millennium_api.run(operation, dict(payload or {}))
        status = str(result.get("status", "unavailable"))
        self.audit.add_entry(f"HYBA_MILLENNIUM_MATH|{operation}|{status}")
        result["hyba_audit_integrity"] = self.audit.verify_integrity()
        return result

    def _build_comparison(self) -> dict[str, Any]:
        """Return an evidence checklist, not unsupported competitor claims."""
        return {
            "comparison_status": "NOT_ASSESSED",
            "reason": (
                "No independently validated, like-for-like benchmark or sourced "
                "competitor evidence is bundled with this offering."
            ),
            "required_dimensions": [
                "mission-specific outcome quality",
                "forecast calibration and false-alarm rate",
                "end-to-end latency and availability",
                "security and access-control testing",
                "integration coverage and operator workload",
                "deployment and lifecycle cost",
                "independent evaluation and customer acceptance",
            ],
        }

    def _generate_proposal(self) -> str:
        return (
            "HYBA NATIONAL-SECURITY INTELLIGENCE\n"
            "===================================\n\n"
            "Purpose\n"
            "Authorized national-security and critical-infrastructure decision "
            "support: early warning, scenario analysis, defensive cyber risk, "
            "resilience planning and auditable recommendations.\n\n"
            "Consolidated architecture\n"
            "- TOE provides the shared reasoning runtime and evidence/receipt substrate.\n"
            "- Millennium Maths provides separately scoped, bounded mathematical probes.\n"
            "- Five canonical intelligence forms: predictive, causal, "
            "counterfactual, topological and geometric.\n"
            "- Salamander provides governed anomaly detection, bounded recovery, verified rollback and measured self-optimization.\\n"
            "- Existing HYBA AL HARAS and L-HRAS governance and evidence paths.\n"
            "- Classical-first defensive optimization with experimental methods "
            "kept explicitly labelled.\n\n"
            "Operational principles\n"
            "- Evidence, provenance, uncertainty and limitations accompany "
            "material assessments.\n"
            "- Intelligence outputs recommend; HYBA policy governs authority.\n"
            "- Consequential actions require authorized human review or a "
            "narrowly scoped, explicitly approved policy.\n"
            "- Production readiness, prediction quality, external integrations "
            "and security claims require reproducible evidence.\n\n"
            "Status\n"
            "Architecture and adapter entrypoints only. This response does not "
            "provision infrastructure or certify operational readiness."
        )

    def deploy(self) -> dict[str, Any]:
        """Return an inventory snapshot; this method does not deploy services."""
        self.audit.add_entry("HYBA_NATIONAL_SECURITY_INVENTORY_READ")
        return {
            "offering": "HYBA National-Security Intelligence",
            "stack": self.stack,
            "comparison": self.comparison,
            "phi": self.phi,
            "status": "ASSESSMENT_REQUIRED",
            "deployment_performed": False,
            "proposal": self._generate_proposal(),
            "audit_integrity": self.audit.verify_integrity(),
            "audit_root": self.audit.merkle_root or self.audit.get_last_hash(),
        }
