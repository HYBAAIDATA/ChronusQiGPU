from __future__ import annotations

from typing import Any

from al_haras.security_core import CryptographicAuditChain

PHI = (1.0 + 5.0**0.5) / 2.0


class NationalSecurityOffering:
    """HYBA national-security capability inventory.

    This class describes the consolidated architecture and its evidence status.
    It does not itself provision production infrastructure or establish mission
    readiness. Capability claims must be backed by tests and deployment evidence.
    """

    def __init__(self, *, audit: CryptographicAuditChain | None = None):
        self.phi = PHI
        self.audit = audit or CryptographicAuditChain(use_merkle=True)
        self.stack = self._build_stack()
        self.comparison = self._build_comparison()
        self.audit.add_entry("HYBA_NATIONAL_SECURITY_INVENTORY_INIT")

    def _build_stack(self) -> dict[str, Any]:
        return {
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
            "- Five canonical intelligence forms: predictive, causal, "
            "counterfactual, topological and geometric.\n"
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
            "Architecture inventory only. This response does not provision "
            "infrastructure or certify operational readiness."
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
