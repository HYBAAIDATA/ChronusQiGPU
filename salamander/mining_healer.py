"""Salamander Autonomic Healer for Mining Intelligence.

Implements the canonical 7-stage closed loop:
    observe -> classify -> bounded-action -> actuator-ack -> post-observe -> verified-recovery -> resume

LAW: HEALER OUTRANKS OPTIMISER.
When a stale rate spike, identity mismatch, or difficulty jump occurs, the healer steps in,
locks the optimizer, halts exploratory trials, bounds recovery actions, verifies independent recovery,
and only then releases the lock. Consensus SHA256d and Stratum truth are inviolable.
Every healing action generates an ExecutionRecord and an EvidenceLedger record.
"""

from __future__ import annotations

import copy
import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping

from chronus.mla1517.mining.recovery_authority import (
    RecoveryGovernor,
    RecoveryRecord,
    RecoveryState,
)
from chronus.mla1517.mining.search_plan import (
    CompletionState,
    EvidenceClass,
    ExecutionRecord,
    PlanSource,
    PoolOutcome,
)
from salamander.control_plane import EvidenceLedger
from salamander.models import digest as model_digest
from salamander.runtime import ActionClass, DurableEvidenceLedger, FaultClass

LOG = logging.getLogger("salamander.mining_healer")


class HealerState(StrEnum):
    IDLE = "IDLE"
    OBSERVING = "OBSERVING"
    CLASSIFIED = "CLASSIFIED"
    ACTUATING = "ACTUATING"
    AWAITING_ACK = "AWAITING_ACK"
    POST_OBSERVING = "POST_OBSERVING"
    VERIFYING = "VERIFYING"
    RECOVERED = "RECOVERED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class HealObservation:
    observed_at_ns: int
    adapter_job_id: str | None
    generation_job_id: str | None
    adapter_target: int | None
    generation_target: int | None
    in_flight_leases: int
    stale_plan_count: int
    stale_rate: float
    difficulty_jump_ratio: float | None
    trigger_reason: str | None
    is_mismatch: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HealDiagnosis:
    diagnosis_id: str
    fault_class: FaultClass
    symptom: str
    root_cause: str
    action_class: ActionClass
    proposed_actions: tuple[str, ...]
    bounds: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "diagnosis_id": self.diagnosis_id,
            "fault_class": self.fault_class.value,
            "symptom": self.symptom,
            "root_cause": self.root_cause,
            "action_class": self.action_class.value,
            "proposed_actions": list(self.proposed_actions),
            "bounds": dict(self.bounds),
        }


@dataclass(frozen=True)
class HealActionAck:
    action_id: str
    timestamp_ns: int
    actuator: str
    status: str
    executed_commands: tuple[str, ...]
    details: Mapping[str, Any]


@dataclass(frozen=True)
class HealPostObservation:
    healthy: bool
    resolved_identity: Any | None
    reason: str | None
    adapter_generation_match: bool
    target_match: bool
    stale_leases_cleared: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "healthy": self.healthy,
            "reason": self.reason,
            "adapter_generation_match": self.adapter_generation_match,
            "target_match": self.target_match,
            "stale_leases_cleared": self.stale_leases_cleared,
            "resolved_identity_generation": getattr(self.resolved_identity, "generation", None),
            "resolved_identity_job_id": getattr(self.resolved_identity, "job_id", None),
            "resolved_identity_fingerprint": getattr(self.resolved_identity, "job_fingerprint", None),
        }


@dataclass(frozen=True)
class HealAuditRecord:
    recovery_id: str
    timestamp_ns: int
    fault_class: str
    diagnosis: Mapping[str, Any]
    actions_taken: tuple[str, ...]
    post_observation: Mapping[str, Any]
    verified: bool
    evidence_sha256: str
    execution_record: ExecutionRecord


class SalamanderMiningHealer:
    """Supervisory autonomic healer enforcing healer outranks optimiser law."""

    def __init__(
        self,
        ledger: EvidenceLedger | None = None,
        *,
        evidence_path: str | Path | None = None,
    ) -> None:
        if ledger is not None:
            self.ledger = ledger
        elif evidence_path is not None:
            self.ledger = DurableEvidenceLedger(evidence_path)
        else:
            self.ledger = EvidenceLedger()

        self._lock = threading.Lock()
        self.state = HealerState.IDLE
        self.active_recovery_id: str | None = None
        self.last_audit: HealAuditRecord | None = None
        self.heal_count = 0
        self.audit_history: list[HealAuditRecord] = []

    @property
    def is_healing_active(self) -> bool:
        return self.state not in (HealerState.IDLE, HealerState.RECOVERED, HealerState.FAILED)

    # -------------------------------------------------------------------------
    # STAGE 1: OBSERVE
    # -------------------------------------------------------------------------
    def observe(self, coordinator: Any, trigger_reason: str | None = None) -> HealObservation:
        """Stage 1: Ingest live coordinator state and detect anomalies."""
        self.state = HealerState.OBSERVING
        now_ns = time.time_ns()

        client = getattr(coordinator, "client", None)
        adapter = getattr(client, "proof_adapter", None)
        state = getattr(client, "runtime_state", None)

        generation = getattr(state, "current_job", None) if state else None
        adapter_job = getattr(adapter, "current_job", None) if adapter else None

        adapter_job_id = getattr(adapter_job, "job_id", None)
        generation_job_id = getattr(generation, "job_id", None)

        adapter_target = getattr(adapter_job, "target", None)
        generation_target = getattr(generation, "target", None)

        agentic_snapshot = coordinator.agentic.snapshot() if hasattr(coordinator, "agentic") else {}
        plans_created = int(agentic_snapshot.get("plans_created", 0))
        plans_stale = int(agentic_snapshot.get("plans_stale", 0))
        stale_rate = (plans_stale / max(1, plans_created)) if plans_created > 0 else 0.0

        leases_ledger = getattr(coordinator.agentic, "_leases", None) if hasattr(coordinator, "agentic") else None
        active_leases = getattr(leases_ledger, "_active", {}) if leases_ledger is not None else {}
        in_flight = len(active_leases)

        is_mismatch = (
            (adapter_job_id is not None and generation_job_id is not None and adapter_job_id != generation_job_id)
            or (adapter_target is not None and generation_target is not None and adapter_target != generation_target)
            or trigger_reason == "IDENTITY_MISMATCH"
        )

        return HealObservation(
            observed_at_ns=now_ns,
            adapter_job_id=adapter_job_id,
            generation_job_id=generation_job_id,
            adapter_target=adapter_target,
            generation_target=generation_target,
            in_flight_leases=in_flight,
            stale_plan_count=plans_stale,
            stale_rate=stale_rate,
            difficulty_jump_ratio=None,
            trigger_reason=trigger_reason,
            is_mismatch=is_mismatch,
        )

    # -------------------------------------------------------------------------
    # STAGE 2: CLASSIFY
    # -------------------------------------------------------------------------
    def classify(self, obs: HealObservation) -> HealDiagnosis:
        """Stage 2: Classify anomaly into rigorous fault class and bounded action space."""
        self.state = HealerState.CLASSIFIED
        diag_id = f"diag:{uuid.uuid4().hex[:12]}"

        if obs.is_mismatch or obs.trigger_reason == "IDENTITY_MISMATCH":
            return HealDiagnosis(
                diagnosis_id=diag_id,
                fault_class=FaultClass.RECOVERABLE_DEGRADATION,
                symptom="IDENTITY_MISMATCH",
                root_cause=(
                    f"proof_adapter job ({obs.adapter_job_id}) or target ({obs.adapter_target}) "
                    f"desynchronized from Stratum generation ({obs.generation_job_id}, {obs.generation_target})"
                ),
                action_class=ActionClass.SAFE_AUTOMATIC,
                proposed_actions=(
                    "LOCK_OPTIMIZER",
                    "DRAIN_PRECOMPUTE",
                    "INVALIDATE_IN_FLIGHT_LEASES",
                    "RESYNC_PROOF_ADAPTER",
                ),
                bounds={
                    "timeout_ms": 5000,
                    "max_retries": 3,
                    "consensus_inviolable": True,
                    "preserves_pool_truth": True,
                },
            )

        if obs.stale_rate > 0.15:
            return HealDiagnosis(
                diagnosis_id=diag_id,
                fault_class=FaultClass.RECOVERABLE_DEGRADATION,
                symptom="STALE_RATE_SPIKE",
                root_cause=f"Stale lease rate {obs.stale_rate:.2%} exceeded envelope threshold (15.0%)",
                action_class=ActionClass.SAFE_AUTOMATIC,
                proposed_actions=(
                    "LOCK_OPTIMIZER",
                    "DRAIN_PRECOMPUTE",
                    "RESET_CURSOR",
                ),
                bounds={"timeout_ms": 3000, "max_retries": 2},
            )

        if obs.trigger_reason in ("STALE_JOB", "CLEAN_JOBS"):
            return HealDiagnosis(
                diagnosis_id=diag_id,
                fault_class=FaultClass.TRANSIENT,
                symptom="STALE_JOB",
                root_cause="Pool broadcast clean_jobs; active generation superseded",
                action_class=ActionClass.SAFE_AUTOMATIC,
                proposed_actions=(
                    "LOCK_OPTIMIZER",
                    "DRAIN_PRECOMPUTE",
                    "INVALIDATE_IN_FLIGHT_LEASES",
                ),
                bounds={"timeout_ms": 2000, "max_retries": 1},
            )

        # Fallback benign / unclassified
        return HealDiagnosis(
            diagnosis_id=diag_id,
            fault_class=FaultClass.NONE,
            symptom="BENIGN",
            root_cause="No anomalous deviation detected",
            action_class=ActionClass.SAFE_AUTOMATIC,
            proposed_actions=(),
            bounds={},
        )

    # -------------------------------------------------------------------------
    # STAGE 3: BOUNDED ACTION (HEALER OUTRANKS OPTIMISER)
    # -------------------------------------------------------------------------
    def bounded_action(
        self, coordinator: Any, diagnosis: HealDiagnosis
    ) -> tuple[str, HealActionAck]:
        """Stage 3: Execute strictly bounded actions. Halts optimizer and drains stale state."""
        self.state = HealerState.ACTUATING
        recovery_id = f"salamander:heal:{uuid.uuid4().hex[:12]}"
        self.active_recovery_id = recovery_id
        now_ns = time.time_ns()
        executed_commands: list[str] = []

        LOG.warning(
            "SALAMANDER HEALER ACTIVE: %s (root_cause: %s) -> recovery_id=%s",
            diagnosis.symptom,
            diagnosis.root_cause,
            recovery_id,
        )

        # A safety inhibit is allowed even when recovery authorization fails;
        # no drain, lease mutation or proof-adapter write bypasses the governor.
        optimizer = getattr(coordinator, "optimization", None)
        if optimizer is None:
            self.state = HealerState.FAILED
            raise RuntimeError("recovery requires an optimizer safety lock")
        optimizer.lock(f"salamander_healer: {diagnosis.symptom}")
        rec_gov = getattr(coordinator, "recovery", None)
        if rec_gov is None:
            self.state = HealerState.FAILED
            raise RuntimeError("recovery governor unavailable")
        allowed = {"LOCK_OPTIMIZER", "DRAIN_PRECOMPUTE",
                   "INVALIDATE_IN_FLIGHT_LEASES", "RESYNC_PROOF_ADAPTER", "RESET_CURSOR"}
        if not diagnosis.proposed_actions or set(diagnosis.proposed_actions) - allowed:
            self.state = HealerState.FAILED
            raise RuntimeError("empty or unsupported recovery action set")

        def act(command: str) -> str:
            if command == "LOCK_OPTIMIZER":
                optimizer.lock(f"salamander_healer: {diagnosis.symptom}")
            elif command in ("DRAIN_PRECOMPUTE", "RESET_CURSOR"):
                coordinator.agentic.clear_work(diagnosis.symptom)
            elif command == "INVALIDATE_IN_FLIGHT_LEASES":
                coordinator.agentic._leases.invalidate_reserved()
            elif command == "RESYNC_PROOF_ADAPTER":
                client = coordinator.client
                generation = client.runtime_state.current_job
                if generation is None or client.proof_adapter is None:
                    raise RuntimeError("pool generation or proof adapter unavailable")
                client.proof_adapter.current_job = generation
            executed_commands.append(command)
            return command

        try:
            record = rec_gov.propose(diagnosis.proposed_actions, diagnosis.symptom)
            if record is None:
                raise RuntimeError("recovery proposal refused")
            recovery_id = record.recovery_id
            self.active_recovery_id = recovery_id
            self._action_started = time.monotonic()
            rec_gov.dispatch(record, [(cmd, lambda cmd=cmd: act(cmd))
                                      for cmd in diagnosis.proposed_actions])
            if (tuple(executed_commands) != diagnosis.proposed_actions
                    or record.state not in (RecoveryState.DISPATCHED, RecoveryState.ACKED)):
                raise RuntimeError("recovery dispatch incomplete or deferred")
        except Exception:
            self.state = HealerState.FAILED
            # Deliberately leave the safety inhibit engaged. No resume/ACK.
            raise

        # 6. Actuator ack record
        ack = HealActionAck(
            action_id=f"ack:{uuid.uuid4().hex[:12]}",
            timestamp_ns=now_ns,
            actuator="SalamanderMiningHealer",
            status="ACKNOWLEDGED",
            executed_commands=tuple(executed_commands),
            details={"recovery_id": recovery_id, "symptom": diagnosis.symptom},
        )
        return recovery_id, ack

    # -------------------------------------------------------------------------
    # STAGE 4: ACTUATOR ACK
    # -------------------------------------------------------------------------
    def actuator_ack(self, ack: HealActionAck) -> bool:
        """Stage 4: Verify actuator acknowledged bounded execution."""
        self.state = HealerState.AWAITING_ACK
        verified_ack = ack.status == "ACKNOWLEDGED" and len(ack.executed_commands) > 0
        if not verified_ack:
            self.state = HealerState.FAILED
            raise RuntimeError(f"Actuator ACK rejected or empty for action {ack.action_id}")
        return True

    # -------------------------------------------------------------------------
    # STAGE 5: POST-OBSERVE
    # -------------------------------------------------------------------------
    def post_observe(self, coordinator: Any) -> HealPostObservation:
        """Stage 5: Independently re-observe system state to evaluate true recovery."""
        self.state = HealerState.POST_OBSERVING

        identity, reason = coordinator._resolve_work_identity()
        client = getattr(coordinator, "client", None)
        adapter = getattr(client, "proof_adapter", None)
        state = getattr(client, "runtime_state", None)

        gen = getattr(state, "current_job", None) if state else None
        adj = getattr(adapter, "current_job", None) if adapter else None

        match_job = (
            gen is not None
            and adj is not None
            and getattr(gen, "job_id", None) == getattr(adj, "job_id", None)
        )
        match_target = (
            gen is not None
            and adj is not None
            and getattr(gen, "target", None) == getattr(adj, "target", None)
        )

        leases = getattr(getattr(coordinator, "agentic", None), "_leases", None)
        lease_snapshot = leases.snapshot() if leases is not None else None
        stale_leases_cleared = bool(
            lease_snapshot is not None
            and lease_snapshot.get("reserved") == 0
            and lease_snapshot.get("executing") == 0
        )
        healthy = (identity is not None and reason is None and match_job
                   and match_target and stale_leases_cleared)

        return HealPostObservation(
            healthy=healthy,
            resolved_identity=identity,
            reason=reason,
            adapter_generation_match=match_job,
            target_match=match_target,
            stale_leases_cleared=stale_leases_cleared,
        )

    # -------------------------------------------------------------------------
    # STAGE 6: VERIFIED RECOVERY
    # -------------------------------------------------------------------------
    def verified_recovery(
        self,
        coordinator: Any,
        diagnosis: HealDiagnosis,
        post_obs: HealPostObservation,
        recovery_id: str,
    ) -> HealAuditRecord:
        """Stage 6: Validate postcondition. Generates ExecutionRecord and evidence ledger entry."""
        self.state = HealerState.VERIFYING
        now_ns = time.time_ns()

        if not post_obs.healthy:
            self.state = HealerState.FAILED
            rec_gov: RecoveryGovernor | None = getattr(coordinator, "recovery", None)
            if rec_gov is not None:
                rec_gov.observe(healthy=False, recovery_id=recovery_id)
            raise RuntimeError(
                f"Autonomic healing postcondition failed: reason={post_obs.reason}, "
                f"job_match={post_obs.adapter_generation_match}, target_match={post_obs.target_match}"
            )

        # Postcondition proven! Update RecoveryGovernor
        rec_gov: RecoveryGovernor | None = getattr(coordinator, "recovery", None)
        if rec_gov is not None:
            rec_gov.observe(healthy=True, recovery_id=recovery_id)

        # Record in EvidenceLedger
        evidence_payload = {
            "recovery_id": recovery_id,
            "diagnosis": diagnosis.as_dict(),
            "post_observation": post_obs.as_dict(),
            "healer_law": "HEALER_OUTRANKS_OPTIMISER",
            "healer_verified": True,
            "consensus_truth": "INVIOLABLE",
        }
        evidence_sha = self.ledger.append(
            "runtime-healing-outcome",
            evidence_payload,
            at_ns=now_ns,
        )

        # Generate mandatory ExecutionRecord for healing event
        ident = post_obs.resolved_identity
        gen_id = getattr(ident, "generation", None)
        job_fp = getattr(ident, "job_fingerprint", "salamander_healed_fingerprint")

        exec_record = ExecutionRecord(
            plan_id=None,
            job_fingerprint=job_fp,
            policy_id="salamander.autonomic_healer.v1",
            planned_window=1,
            actual_window=0,
            device_used="salamander_healer",
            hash_count=0,
            elapsed_seconds=max(0.0, time.monotonic() - self._action_started),
            kernel_ms=0.0,
            temperature_c=None,
            locally_valid_shares=0,
            pool_accepted=0,
            pool_rejected=0,
            pool_stale=0,
            recovery_event=True,
            lane_order=tuple(range(32)),
            preferred_face=0,
            plan_source=PlanSource.BASELINE_FALLBACK,
            plan_fallback_reason=f"healed:{diagnosis.symptom}",
            requested_route=None,
            executed_route=None,
            completion_state=CompletionState.COMPLETE,
            evidence_class=EvidenceClass.SOFTWARE_VERIFIED,
            generation=gen_id,
            recorded_at=time.monotonic(),
        )

        # Causal ledger entry if coordinator has one
        if hasattr(coordinator, "causal") and coordinator.causal is not None:
            try:
                from chronus.mla1517.mining.causal_ledger import CausalCoordinate
                coord = CausalCoordinate(
                    recovery_id=recovery_id,
                    generation=gen_id,
                    job_fingerprint=job_fp,
                )
                coordinator.causal.record(
                    "salamander_healed_identity",
                    coord,
                    recovery_id=recovery_id,
                    symptom=diagnosis.symptom,
                    evidence_sha256=evidence_sha,
                )
            except Exception as exc:
                LOG.warning("Causal ledger record skipped: %s", exc)

        audit = HealAuditRecord(
            recovery_id=recovery_id,
            timestamp_ns=now_ns,
            fault_class=diagnosis.fault_class.value,
            diagnosis=diagnosis.as_dict(),
            actions_taken=diagnosis.proposed_actions,
            post_observation=post_obs.as_dict(),
            verified=True,
            evidence_sha256=evidence_sha,
            execution_record=exec_record,
        )
        self.last_audit = audit
        self.audit_history.append(audit)
        self.heal_count += 1
        self.state = HealerState.RECOVERED
        self.active_recovery_id = None
        return audit

    # -------------------------------------------------------------------------
    # STAGE 7: RESUME
    # -------------------------------------------------------------------------
    def resume(self, coordinator: Any, audit: HealAuditRecord) -> Any | None:
        """Stage 7: Safely bind healed identity and wake precompute & execution loops."""
        self.state = HealerState.RECOVERED
        # Direct call to refresh or bind work
        if hasattr(coordinator, "agentic") and coordinator.agentic is not None:
            work_ident, reason = coordinator._resolve_work_identity()
            expected_generation = audit.post_observation.get("resolved_identity_generation")
            if (work_ident is not None and reason is None
                    and getattr(work_ident, "generation", None) == expected_generation
                    and getattr(work_ident, "job_fingerprint", None)
                    == audit.post_observation.get("resolved_identity_fingerprint")):
                coordinator.agentic.bind_work(work_ident)
                if hasattr(coordinator, "_precompute_wake"):
                    coordinator._precompute_wake.set()
                if hasattr(coordinator, "_work_wake"):
                    coordinator._work_wake.set()
                coordinator.optimization.unlock()
                self.state = HealerState.IDLE
                return work_ident

        self.state = HealerState.FAILED
        raise RuntimeError("recovery could not rebind work; optimizer remains locked")

    # -------------------------------------------------------------------------
    # HIGH-LEVEL ORCHESTRATION ENTRANCE
    # -------------------------------------------------------------------------
    def heal_identity_mismatch(self, coordinator: Any) -> Any | None:
        """Full 7-step autonomic heal orchestration for IDENTITY_MISMATCH."""
        with self._lock:
            # 1. Observe
            obs = self.observe(coordinator, trigger_reason="IDENTITY_MISMATCH")
            # 2. Classify
            diagnosis = self.classify(obs)
            # 3. Bounded Action
            recovery_id, ack = self.bounded_action(coordinator, diagnosis)
            # 4. Actuator Ack
            self.actuator_ack(ack)
            # 5. Post-Observe
            post_obs = self.post_observe(coordinator)
            # 6. Verified Recovery
            audit = self.verified_recovery(coordinator, diagnosis, post_obs, recovery_id)
            # 7. Resume
            healed_identity = self.resume(coordinator, audit)
            return healed_identity
