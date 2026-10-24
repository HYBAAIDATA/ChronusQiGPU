"""Trusted-core EmergentQualificationService (EQS)."""

from __future__ import annotations
import hashlib
import secrets
import math
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
    QualificationAuthorization,
    InvalidGovernanceTokenError,
    UnauthorizedOperationalLoopCallError,
)
from .stress import stress_test
from .measured import MeasuredEvidenceVerifier
from .receipts import QualificationReceiptIssuer
from ..substrate.executors import ReproductionEvidence
from ..substrate import engine
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
        authorization: Optional[QualificationAuthorization] = None,
        journal: Optional[ImmutableEmergenceJournal] = None,
        divergence_monitor: Optional[DivergenceMonitor] = None,
        margin: float = DEFAULT_MARGIN,
        registered_substrates=None,
        receipt_issuer: Optional[QualificationReceiptIssuer] = None,
        entropy_tripwire: float = 0.85,
    ):
        if authorization is not None and not isinstance(authorization, QualificationAuthorization):
            raise TypeError("host-configured QualificationAuthorization required")
        import math
        if type(margin) not in (int, float) or not math.isfinite(margin) or margin < self.DEFAULT_MARGIN:
            raise ValueError("finite stress margin of at least 1.5 required")
        if not engine.finite_number(entropy_tripwire) or not 0 <= entropy_tripwire <= 0.85:
            raise ValueError("finite normalized entropy tripwire <=0.85 required")
        if receipt_issuer is not None and type(receipt_issuer) is not QualificationReceiptIssuer:
            raise TypeError("explicit host qualification receipt issuer required")
        self.evidence_verifier = MeasuredEvidenceVerifier(registered_substrates)
        self.receipt_issuer, self.entropy_tripwire = receipt_issuer, entropy_tripwire
        self.authorization = authorization
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
        if type(governance_token) is not GovernanceToken or self.authorization is None:
            raise InvalidGovernanceTokenError("Explicit trusted public-key authorization required; no default authority.")

        original_candidate = candidate
        snapshot = None
        try:
            snapshot = CandidateSnapshot.capture(candidate)
            candidate = snapshot.materialize()
            try:
                self.authorization.authorize(governance_token, candidate_fingerprint=snapshot.fingerprint)
            except InvalidGovernanceTokenError:
                self.journal.append("AUTHORIZATION_REFUSED", candidate.candidate_id, {
                    "candidate_fingerprint": snapshot.fingerprint,
                    "reason": "invalid_scope_trust_time_or_replay",
                })
                raise
            self.journal.append("QUALIFICATION_INPUT_SNAPSHOT", candidate.candidate_id, {
                "candidate_fingerprint": snapshot.fingerprint,
                "protocol_hash": candidate.reproduction_steps.compute_protocol_hash(),
                "custody_scope": "local_service_entry_only",
                "independent_attestation": False,
            })
            if not all(isinstance(e, BaseExecutor) for e in (executor_A, executor_B)):
                raise CandidateCustodyError("INSUFFICIENT_SUBSTRATE_DIVERSITY: two registered executors required")
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
                    reason=f"INSUFFICIENT_SUBSTRATE_DIVERSITY: Executors violate independence criteria: {'; '.join(isolation_violations)}",
                    evidence={"isolation_violations": isolation_violations},
                )
                self.journal.append("REJECT", candidate.candidate_id, verdict.to_dict())
                return verdict

            # Registry keys are supplied by the host, never learned from an evidence payload.
            registry = self.evidence_verifier.registrations
            if any(e.substrate_id not in registry for e in (executor_A, executor_B)):
                raise CandidateCustodyError("lacks measured reproduction: unregistered substrate")
            if registry[executor_A.substrate_id].backend == registry[executor_B.substrate_id].backend:
                raise CandidateCustodyError("INSUFFICIENT_SUBSTRATE_DIVERSITY: distinct measured backends required")
            if self.receipt_issuer is None:
                raise CandidateCustodyError("explicit qualification receipt signer unavailable")
            challenge_A, challenge_B = secrets.token_hex(32), secrets.token_hex(32)
            view_A = snapshot.materialize()
            r1 = executor_A.reproduce(view_A.reproduction_steps, challenge=challenge_A, candidate_fingerprint=snapshot.fingerprint)
            snapshot.verify(view_A)
            snapshot.verify(original_candidate)
            view_B = snapshot.materialize()
            r2 = executor_B.reproduce(view_B.reproduction_steps, challenge=challenge_B, candidate_fingerprint=snapshot.fingerprint)
            snapshot.verify(view_B)
            snapshot.verify(original_candidate)
            r1, window_A = self.evidence_verifier.verify(r1, candidate.reproduction_steps,
                fingerprint=snapshot.fingerprint, challenge=challenge_A)
            r2, window_B = self.evidence_verifier.verify(r2, candidate.reproduction_steps,
                fingerprint=snapshot.fingerprint, challenge=challenge_B)
            if r1.substrate_id != executor_A.substrate_id or r2.substrate_id != executor_B.substrate_id:
                raise CandidateCustodyError('INSUFFICIENT_SUBSTRATE_DIVERSITY: returned substrate identity mismatch')
            if any(r.execution_metrics['stability'] < 0.70 for r in (r1, r2)):
                raise CandidateCustodyError("UNSTABLE_EXECUTION: output trajectory stability below 0.70")

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
            stress_challenge = secrets.token_hex(32)
            stress_passed, stress_details = stress_test(
                candidate=candidate,
                envelope=expanded_envelope,
                executor=executor_A,
                margin=self.margin,
                challenge=stress_challenge,
            )

            snapshot.verify(candidate)
            snapshot.verify(original_candidate)
            if stress_details.get("execution_kind") != "MEASURED":
                raise CandidateCustodyError("Gate 2 lacks measured executor stress evidence")

            stress_execution, _ = self.evidence_verifier.verify(
                ReproductionEvidence(**stress_details['execution']), candidate.reproduction_steps,
                fingerprint=snapshot.fingerprint, challenge=stress_challenge, factor=self.margin,
                envelope=expanded_envelope.to_dict())
            if stress_execution.substrate_id != executor_A.substrate_id:
                raise CandidateCustodyError('stress substrate identity mismatch')
            stress_passed = (stress_passed and stress_execution.observed
                and stress_execution.execution_metrics['stability'] >= 0.70
                and engine.finite_number(expanded_envelope.compute_budget_sec)
                and expanded_envelope.compute_budget_sec > 0
                and all(t['duration_ms'] / 1000 <= expanded_envelope.compute_budget_sec
                        for t in stress_execution.details['trials']))

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

            # Gate 3 consumes complete telemetry signed with the current challenge-bound runs.
            # This is the qualification-run window, not a claim of production monitoring.
            measured_window = window_A + window_B
            if not measured_window:
                raise CandidateCustodyError("Gate 3 requires a nonempty observation window")
            if post_qualification_window is not None:
                if ([r.compute_digest() for r in post_qualification_window] !=
                        [r.compute_digest() for r in measured_window]):
                    raise CandidateCustodyError("Gate 3 supplied window is not the complete authenticated current window")
            for result in (r1, r2):
                if result.execution_metrics['entropy'] > self.entropy_tripwire:
                    return self.suspend(candidate, {'divergence_metric': 'telemetry_entropy_tripwire',
                        'divergence_value': result.execution_metrics['entropy'],
                        'threshold': self.entropy_tripwire, 'reason': 'TRIPWIRE_BREACH'})
            from collections import Counter
            declared_action_profile = dict(Counter(s['action'] for s in candidate.reproduction_steps.steps))
            divergence_detected, div_report = self.monitor.divergence_detected(
                candidate=candidate, window=measured_window, baseline_profile=declared_action_profile)
            if divergence_detected:
                return self.suspend(candidate, div_report)
            snapshot.verify(candidate)
            snapshot.verify(original_candidate)
            # All gates passed: Issue qualification certificate
            gate_artifacts = {'gate_1': [r1.to_dict(), r2.to_dict()], 'gate_2': stress_details,
                'gate_3': {'window_digests': [r.compute_digest() for r in measured_window],
                           'divergence': div_report, 'entropy_limit': self.entropy_tripwire}}
            receipt = self.receipt_issuer.issue(candidate, gate_artifacts)
            cert_token = receipt.encode()

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
                governance_signature=receipt.signature,
                qualification_receipt=cert_token,
                gate_3_monitoring=gate_artifacts['gate_3'],
                gates_digest=receipt.gates_digest,
            )

            self.journal.append("QUALIFY", candidate.candidate_id, qualified.to_dict())
            self._qualified_candidates[candidate.candidate_id] = qualified
            return qualified
        except InvalidGovernanceTokenError:
            raise
        except (CandidateCustodyError, TypeError, ValueError, KeyError, OSError) as exc:
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

    def is_receipt_active(self, receipt) -> bool:
        """Host admission hook; restart/missing qualification state fails closed."""
        qualified = self._qualified_candidates.get(receipt.candidate_id)
        return (qualified is not None and qualified.qualification_receipt == receipt.encode())
