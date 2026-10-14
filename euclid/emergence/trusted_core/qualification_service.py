"""Trusted-core EmergentQualificationService (EQS)."""

from __future__ import annotations
import hashlib
import time
from typing import Optional, Sequence, Union, Tuple, Dict, Any

from ..models.candidate import EmergentCandidate
from ..models.qualification import (
    QualifiedEmergent,
    RejectedQualification,
    SuspendedQualification,
    QualificationStatus,
    QualificationOutcome,
)
from ..models.telemetry import TelemetryRecord
from ..substrate.executors import BaseExecutor
from ..substrate.isolation import SubstrateIndependenceVerifier
from .access_control import (
    CallerBoundaryGuard,
    GovernanceToken,
    InvalidGovernanceTokenError,
    UnauthorizedOperationalLoopCallError,
)
from .stress import stress_test
from .custody import CandidateSnapshot, CandidateCustodyError
from .monitor import DivergenceMonitor
from .journal import ImmutableEmergenceJournal


class EmergentQualificationService:
    """Trusted Core Emergent Qualification Service (EQS).

    Principle: Emergent capabilities enter through a STRICTER gate than engineered ones.
    Self-certification is strictly forbidden. The operational loop CANNOT call this service.
    """

    DEFAULT_MARGIN: float = 1.5

    def __init__(
        self,
        governance_secret_key: str = "euclid_trusted_core_secret_key",
        journal: Optional[ImmutableEmergenceJournal] = None,
        divergence_monitor: Optional[DivergenceMonitor] = None,
        margin: float = DEFAULT_MARGIN,
    ):
        self.governance_secret_key = governance_secret_key
        self.journal = journal or ImmutableEmergenceJournal()
        self.monitor = divergence_monitor or DivergenceMonitor()
        self.margin = margin
        self._qualified_candidates: Dict[str, QualifiedEmergent] = {}
        self._suspended_candidates: Dict[str, SuspendedQualification] = {}

    def qualify(
        self,
        candidate: EmergentCandidate,
        executor_A: BaseExecutor,
        executor_B: BaseExecutor,
        governance_token: Optional[GovernanceToken] = None,
        post_qualification_window: Optional[Sequence[TelemetryRecord]] = None,
    ) -> QualificationOutcome:
        """Evaluate candidate emergent capability through the strict three-gate qualification pipeline."""

        # 0. Architectural Security Enforcement: Loop CANNOT call this
        CallerBoundaryGuard.assert_trusted_caller()

        # Capability-Based Access Control Verification
        if governance_token is None or not governance_token.verify(self.governance_secret_key):
            raise InvalidGovernanceTokenError("Valid GovernanceToken required to invoke EmergentQualificationService.")

        original_candidate = candidate
        snapshot = None
        try:
            snapshot = CandidateSnapshot.capture(candidate)
            candidate = snapshot.materialize()
            self.journal.append("QUALIFICATION_INPUT_SNAPSHOT", candidate.candidate_id, {
                "candidate_fingerprint": snapshot.fingerprint,
                "protocol_hash": candidate.reproduction_steps.compute_protocol_hash(),
                "custody_scope": "local_service_entry_only",
                "independent_attestation": False,
            })
            # Substrate independence verification between executor_A and executor_B
            is_independent, isolation_violations = SubstrateIndependenceVerifier.verify_isolation(
                executor_A.properties,
                executor_B.properties,
                executor_A,
                executor_B,
            )
            if not is_independent:
                verdict = RejectedQualification(
                    candidate_id=candidate.candidate_id,
                    capability_name=candidate.capability_name,
                    gate_failed="Gate 1 (Substrate Independence Prerequisite)",
                    reason=f"Executors violate independence criteria: {'; '.join(isolation_violations)}",
                    evidence={"isolation_violations": isolation_violations},
                )
                self.journal.append("REJECT", candidate.candidate_id, verdict.to_dict())
                return verdict

            # Gate 1 — Reproduction by TWO INDEPENDENT executors
            view_A = snapshot.materialize()
            r1 = executor_A.reproduce(view_A.reproduction_steps)
            snapshot.verify(view_A)
            snapshot.verify(original_candidate)
            view_B = snapshot.materialize()
            r2 = executor_B.reproduce(view_B.reproduction_steps)
            snapshot.verify(view_B)
            snapshot.verify(original_candidate)
            if any(r.details.get("execution_kind") != "MEASURED" for r in (r1, r2)):
                raise CandidateCustodyError("Gate 1 lacks measured reproduction evidence; simulation is not qualification")

            if not (r1.observed and r2.observed):
                rejection_reason = "not substrate-independent"
                if not r1.observed and not r2.observed:
                    rejection_reason = "reproduction failed on both independent executors"
                elif not r1.observed:
                    rejection_reason = f"reproduction failed on executor_A ({executor_A.substrate_id})"
                else:
                    rejection_reason = f"reproduction failed on executor_B ({executor_B.substrate_id})"

                verdict = RejectedQualification(
                    candidate_id=candidate.candidate_id,
                    capability_name=candidate.capability_name,
                    gate_failed="Gate 1 (Cross-Substrate Reproduction)",
                    reason=rejection_reason,
                    evidence={
                        "executor_A": r1.to_dict(),
                        "executor_B": r2.to_dict(),
                    },
                )
                self.journal.append("REJECT", candidate.candidate_id, verdict.to_dict())
                return verdict

            # Gate 2 — Stress envelope WIDER than discovery envelope
            expanded_envelope = candidate.discovery_envelope.scale_margin(self.margin)
            stress_passed, stress_details = stress_test(
                candidate=candidate,
                envelope=expanded_envelope,
                executor=executor_A,
            )

            snapshot.verify(candidate)
            snapshot.verify(original_candidate)
            if stress_details.get("execution_kind") != "MEASURED":
                raise CandidateCustodyError("Gate 2 lacks measured executor stress evidence")

            if not stress_passed:
                verdict = RejectedQualification(
                    candidate_id=candidate.candidate_id,
                    capability_name=candidate.capability_name,
                    gate_failed="Gate 2 (Stress Envelope Expansion)",
                    reason="fails outside discovery conditions",
                    evidence=stress_details,
                )
                self.journal.append("REJECT", candidate.candidate_id, verdict.to_dict())
                return verdict

            # A missing window is unverified, not an implicit pass.
            if not post_qualification_window:
                raise CandidateCustodyError("Gate 3 requires a nonempty observation window")

            # Gate 3 — Divergence check
            if post_qualification_window is not None and len(post_qualification_window) > 0:
                divergence_detected, div_report = self.monitor.divergence_detected(
                    candidate=candidate,
                    window=post_qualification_window,
                )
                snapshot.verify(candidate)
                snapshot.verify(original_candidate)
                if divergence_detected:
                    suspended_verdict = self.suspend(candidate, div_report)
                    return suspended_verdict

            snapshot.verify(candidate)
            snapshot.verify(original_candidate)
            # All gates passed: Issue qualification certificate
            cert_payload = f"CERT:{candidate.candidate_id}:{time.time()}:{r1.signed_journal_hash}:{r2.signed_journal_hash}"
            cert_token = hashlib.sha256(cert_payload.encode("utf-8")).hexdigest()

            qualified = QualifiedEmergent(
                candidate_id=candidate.candidate_id,
                capability_name=candidate.capability_name,
                score=min(1.0, (r1.reproduction_rate + r2.reproduction_rate) / 2.0),
                gate_1_reproduction={
                    "executor_A": r1.to_dict(),
                    "executor_B": r2.to_dict(),
                },
                gate_2_stress_envelope=stress_details,
                certification_token=cert_token,
                governance_signature=governance_token.token_digest,
            )

            self._qualified_candidates[candidate.candidate_id] = qualified
            self.journal.append("QUALIFY", candidate.candidate_id, qualified.to_dict())
            return qualified
        except (CandidateCustodyError, TypeError, ValueError) as exc:
            verdict = RejectedQualification(
                candidate_id=candidate.candidate_id,
                capability_name=candidate.capability_name,
                gate_failed="Custody / Required Execution Evidence",
                reason=str(exc),
                evidence={
                    "independent_attestation": False,
                    "candidate_fingerprint": snapshot.fingerprint if snapshot else None,
                },
            )
            self.journal.append("REJECT", candidate.candidate_id, verdict.to_dict())
            return verdict

    def check_and_apply_divergence_suspension(
        self,
        candidate: EmergentCandidate,
        post_qualification_window: Sequence[TelemetryRecord],
    ) -> Optional[SuspendedQualification]:
        CallerBoundaryGuard.assert_trusted_caller()

        divergence_detected, div_report = self.monitor.divergence_detected(
            candidate=candidate,
            window=post_qualification_window,
        )
        if divergence_detected:
            return self.suspend(candidate, div_report)
        return None

    def suspend(
        self,
        candidate_or_colony: Any,
        divergence_report: Dict[str, Any],
    ) -> SuspendedQualification:
        CallerBoundaryGuard.assert_trusted_caller()

        cand_id = getattr(candidate_or_colony, "candidate_id", str(candidate_or_colony))
        cap_name = getattr(candidate_or_colony, "capability_name", "colony_capability")

        if cand_id in self._qualified_candidates:
            del self._qualified_candidates[cand_id]

        suspended = SuspendedQualification(
            candidate_id=cand_id,
            capability_name=cap_name,
            divergence_metric=divergence_report.get("divergence_metric", "unknown"),
            divergence_value=divergence_report.get("divergence_value", 0.0),
            threshold=divergence_report.get("threshold", 0.0),
            reason=divergence_report.get("reason", "post-qualification divergence"),
            divergence_report=divergence_report,
        )

        self._suspended_candidates[cand_id] = suspended
        self.journal.append("SUSPEND", cand_id, suspended.to_dict())
        return suspended

    def is_qualified(self, candidate_id: str) -> bool:
        return candidate_id in self._qualified_candidates
