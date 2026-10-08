"""Production runtime evidence bridge for the Salamander control plane.

The mining coordinator already has one recovery writer (``RecoveryGovernor``)
and one measured optimiser (``ClosedLoopOptimizer``). This module does not
create a second actuator. It makes the repository-wide
``AutonomicControlPlane`` a live supervisor over those canonical authorities:

    production evidence -> classify -> existing actuator -> measured outcome
    -> durable Salamander evidence

Only values present in a production snapshot are marked measured. Missing
values stay ``UNAVAILABLE`` and no confidence or success value is invented.
"""
from __future__ import annotations

import copy
import json
import math
import os
import time
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping

from .outcome_evidence import CustodiedMiningOutcomeVerifier, OutcomeVerification, unqualified_readiness

from .control_plane import (
    ActionRegistry,
    AutonomicControlPlane,
    EVIDENCE_SCHEMA,
    EvidenceLedger,
)
from .models import Availability, HealthObservation
from .models import digest as model_digest

SCHEMA = "salamander.runtime-autonomy.v1"
MINING_SCHEMA = "pythia.mining_evidence/1"


class FaultClass(StrEnum):
    NONE = "NONE"
    TRANSIENT = "TRANSIENT"
    PERSISTENT = "PERSISTENT"
    RECOVERABLE_DEGRADATION = "RECOVERABLE_DEGRADATION"
    HARD_FAILURE = "HARD_FAILURE"
    UNSAFE_STATE = "UNSAFE_STATE"


class ActionClass(StrEnum):
    SAFE_AUTOMATIC = "SAFE_AUTOMATIC"
    BOUNDED_EXPERIMENT = "BOUNDED_EXPERIMENT"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"
    FORBIDDEN = "FORBIDDEN"


_SAFE_MINING_COMMANDS = frozenset(
    {
        "SEVER_LANE",
        "FLUSH_LANE",
        "RESTART_LANE",
        "APPLY_BACKPRESSURE",
        "QUARANTINE_RECORD",
        "FLUSH_PERSISTENCE_RING",
        "RESET_CURSOR",
    }
)


class DurableEvidenceLedger(EvidenceLedger):
    """Append-only canonical Salamander evidence that survives restart."""

    def __init__(self, path: str | Path) -> None:
        super().__init__()
        self.path = Path(path)
        if not self.path.exists():
            return
        loaded: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise RuntimeError(
                        f"Salamander evidence is malformed at line {number}"
                    ) from exc
                if not isinstance(record, dict):
                    raise RuntimeError(
                        f"Salamander evidence record {number} is not an object"
                    )
                loaded.append(record)
        self._records = loaded
        self._head = loaded[-1]["evidence_sha256"] if loaded else "0" * 64
        self.verify()

    def append(self, kind: str, payload: Mapping[str, Any], *, at_ns: int) -> str:
        if not kind:
            raise ValueError("evidence kind is required")
        body = {
            "schema": EVIDENCE_SCHEMA,
            "kind": kind,
            "at_ns": int(at_ns),
            "previous_sha256": self._head,
            "payload": copy.deepcopy(dict(payload)),
        }
        seal = model_digest("salamander.autonomic.evidence.v1", body)
        record = {**body, "evidence_sha256": seal}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(
            record,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(encoded + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._records.append(record)
        self._head = seal
        return seal


class MiningAutonomyBridge:
    """Live Salamander observer for the canonical production mining runtime."""

    def __init__(
        self, evidence_path: str | Path, *,
        outcome_verifier: CustodiedMiningOutcomeVerifier | None = None,
    ) -> None:
        self.outcome_verifier = outcome_verifier
        self.ledger = DurableEvidenceLedger(evidence_path)
        self.control = AutonomicControlPlane(
            registry=ActionRegistry(),
            ledger=self.ledger,
        )
        self._seen_recoveries: set[str] = set()
        self._seen_optimisation: set[str] = set()
        self._last_health = "UNKNOWN"
        self._last_issue: dict[str, Any] | None = None
        self._last_action: dict[str, Any] | None = None
        self._last_result: dict[str, Any] | None = None
        self._last_successful_healing: dict[str, Any] | None = None
        self._last_successful_optimisation: dict[str, Any] | None = None
        self._last_optimisation: dict[str, Any] | None = None
        self._self_healing_evidenced = False
        self._self_optimising_evidenced = False
        self._observations = 0
        self._restore_from_ledger()

    @classmethod
    def from_environment(cls) -> "MiningAutonomyBridge":
        return cls(
            os.getenv(
                "PYTHIA_SALAMANDER_EVIDENCE_PATH",
                "data/salamander_autonomy.jsonl",
            )
        )

    @staticmethod
    def _event_key(prefix: str, value: Mapping[str, Any]) -> str:
        return prefix + ":" + model_digest(SCHEMA, dict(value))

    def _restore_from_ledger(self) -> None:
        for record in self.ledger.records:
            kind = record.get("kind")
            payload = record.get("payload")
            if not isinstance(payload, dict):
                continue
            if kind == "runtime-healing-outcome":
                key = payload.get("event_key")
                if isinstance(key, str):
                    self._seen_recoveries.add(key)
                self._last_result = payload
                # Historical records remain evidence, not current certification.
                # Fresh independent revalidation is required in this process.
            elif kind == "runtime-optimisation-outcome":
                key = payload.get("event_key")
                if isinstance(key, str):
                    self._seen_optimisation.add(key)
                self._last_optimisation = payload
                # Prior optimiser claims are not verified trial/rollback evidence.
            elif kind == "runtime-diagnosis":
                self._last_issue = payload

    @staticmethod
    def _availability(value: Any) -> Availability:
        if isinstance(value, float) and not math.isfinite(value):
            return Availability.UNAVAILABLE
        if isinstance(value, (bool, str, int, float)):
            return Availability.MEASURED
        return Availability.UNAVAILABLE

    def _observation(
        self,
        *,
        dimension: str,
        value: Any,
        source: str,
        now_ns: int,
        invert_bool: bool = False,
    ) -> HealthObservation:
        availability = self._availability(value)
        measured = value if availability is Availability.MEASURED else None
        if invert_bool and isinstance(measured, bool):
            measured = not measured
        return HealthObservation(
            subsystem="mining",
            dimension=dimension,
            tenant_id="system",
            observed_at_ns=now_ns,
            availability=availability,
            value=measured,
            source=source,
            evidence_ref=self.ledger.head,
        )

    @staticmethod
    def _completion_state(last_execution: Any) -> str | None:
        if not isinstance(last_execution, Mapping):
            return None
        raw = last_execution.get(
            "completion_state",
            last_execution.get("completion"),
        )
        if raw is None:
            return None
        return str(getattr(raw, "value", raw))

    def _diagnose(self, snapshot: Mapping[str, Any]) -> dict[str, Any] | None:
        lifecycle = snapshot.get("lifecycle") or {}
        recovery = snapshot.get("recovery") or {}
        agents = snapshot.get("agents") or {}
        completion = self._completion_state(snapshot.get("last_execution"))

        if bool(recovery.get("faulted")):
            return {
                "fault_class": FaultClass.HARD_FAILURE.value,
                "issue": "recovery authority faulted",
                "diagnosis": "bounded recovery failed to restore health",
                "action_class": ActionClass.REQUIRES_APPROVAL.value,
                "proposed_action": "isolate failed route and require operator review",
            }
        open_recovery = recovery.get("open")
        if isinstance(open_recovery, list) and open_recovery:
            commands = open_recovery[-1].get("commands") or []
            automatic = bool(commands) and all(
                command in _SAFE_MINING_COMMANDS for command in commands
            )
            return {
                "fault_class": FaultClass.RECOVERABLE_DEGRADATION.value,
                "issue": open_recovery[-1].get("reason") or "active recovery",
                "diagnosis": "RecoveryGovernor has an open bounded recovery",
                "action_class": (
                    ActionClass.SAFE_AUTOMATIC.value
                    if automatic
                    else ActionClass.REQUIRES_APPROVAL.value
                ),
                "proposed_action": commands or "Unavailable",
            }
        if completion == "DEVICE_ERROR":
            restart_available = None
            if isinstance(agents, Mapping):
                salamander = agents.get("salamander") or {}
                if isinstance(salamander, Mapping):
                    restart_available = salamander.get(
                        "device_restart_available"
                    )
            return {
                "fault_class": (
                    FaultClass.RECOVERABLE_DEGRADATION.value
                    if restart_available
                    else FaultClass.HARD_FAILURE.value
                ),
                "issue": "execution backend reported DEVICE_ERROR",
                "diagnosis": (
                    "configured backend can be re-probed and rerouted"
                    if restart_available
                    else "no verified restart factory is available"
                ),
                "action_class": (
                    ActionClass.SAFE_AUTOMATIC.value
                    if restart_available
                    else ActionClass.REQUIRES_APPROVAL.value
                ),
                "proposed_action": (
                    "RESTART_LANE" if restart_available else "isolate route"
                ),
            }
        connected = (
            lifecycle.get("transport_connected")
            if isinstance(lifecycle, Mapping)
            else None
        )
        if connected is False:
            return {
                "fault_class": FaultClass.TRANSIENT.value,
                "issue": "pool transport disconnected",
                "diagnosis": "Stratum transport is not connected",
                "action_class": ActionClass.SAFE_AUTOMATIC.value,
                "proposed_action": "bounded reconnect/failover",
            }
        return None

    def _record_recoveries(self, recovery: Any, now_ns: int) -> None:
        if not isinstance(recovery, Mapping):
            return
        recent = recovery.get("recent")
        if not isinstance(recent, list):
            return
        for item in recent:
            if not isinstance(item, Mapping):
                continue
            key = self._event_key("recovery", item)
            if key in self._seen_recoveries:
                continue
            commands = list(item.get("commands") or [])
            automatic = bool(commands) and all(
                command in _SAFE_MINING_COMMANDS for command in commands
            )
            action_taken = list(item.get("dispatched") or [])
            verification = (
                self.outcome_verifier.verify(item, now_ns=now_ns)
                if self.outcome_verifier is not None
                else OutcomeVerification(False, "UNAVAILABLE", "independent verifier unavailable")
            )
            payload = {
                "event_key": key,
                "recovery_id": item.get("recovery_id"),
                "state": ("VERIFIED" if verification.verified else
                          "FAILED" if item.get("state") == "FAILED" else "UNVERIFIED"),
                "reported_state": item.get("state", "Unavailable"),
                "claim_class": verification.claim_class,
                "proof_binding_id": verification.proof_binding_id,
                "causal_attribution": verification.causal_claim,
                "proposed_actions": commands,
                "deferred_actions": list(item.get("deferred") or []),
                "diagnosis": item.get("reason", "Unavailable"),
                "action_taken": action_taken,
                "action_class": (
                    ActionClass.SAFE_AUTOMATIC.value
                    if automatic
                    else ActionClass.REQUIRES_APPROVAL.value
                ),
                "verification": verification.reason,
                "failure": item.get("failure") or "Unavailable",
                "closed_at": item.get("closed_at", "Unavailable"),
                "evidence_source": "RecoveryGovernor.snapshot.recent",
            }
            self.ledger.append(
                "runtime-healing-outcome",
                payload,
                at_ns=now_ns,
            )
            self._seen_recoveries.add(key)
            self._last_action = payload
            self._last_result = payload
            if verification.verified:
                self._last_successful_healing = payload
                self._self_healing_evidenced = True

    def _record_optimisation(self, optimisation: Any, now_ns: int) -> None:
        if not isinstance(optimisation, Mapping):
            return
        event = optimisation.get("last_event")
        if not isinstance(event, Mapping):
            return
        key = self._event_key("optimisation", event)
        if key in self._seen_optimisation:
            return
        payload = {
            "event_key": key,
            "event": event.get("event", "Unavailable"),
            "route": event.get("route", "Unavailable"),
            "baseline": {
                "window": event.get("baseline_window", "Unavailable"),
                "useful_work_per_second": event.get(
                    "baseline_rate",
                    "Unavailable",
                ),
            },
            "candidate": {
                "window": event.get("candidate_window", "Unavailable"),
                "useful_work_per_second": event.get(
                    "candidate_rate",
                    "Unavailable",
                ),
            },
            "accepted": "UNAVAILABLE",
            "reported_accepted": event.get("accepted", "Unavailable"),
            "rollback": "UNAVAILABLE",
            "reported_rollback": event.get("rollback", "Unavailable"),
            "claim_class": "OBSERVED",
            "verification": "UNAVAILABLE",
            "causal_attribution": "UNAVAILABLE",
            "reason": event.get("reason", "Unavailable"),
            "action_class": ActionClass.BOUNDED_EXPERIMENT.value,
            "current_configuration": copy.deepcopy(
                optimisation.get("current_configuration", "Unavailable")
            ),
            "evidence_source": optimisation.get(
                "evidence_source",
                "Unavailable",
            ),
            "software_revision": event.get(
                "software_revision",
                optimisation.get("software_revision", "Unavailable"),
            ),
        }
        self.ledger.append(
            "runtime-optimisation-outcome",
            payload,
            at_ns=now_ns,
        )
        self._seen_optimisation.add(key)
        self._last_optimisation = payload
        self._last_result = payload
        # Trial acceptance is retained as an observation. It does not prove
        # causal gain, authorised promotion, or independently verified rollback.

    def observe_mining_snapshot(
        self,
        snapshot: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Consume one real coordinator snapshot and return operator state."""
        if snapshot.get("schema") != MINING_SCHEMA:
            raise ValueError("invalid mining evidence schema")
        now_ns = time.time_ns()
        lifecycle = snapshot.get("lifecycle") or {}
        recovery = snapshot.get("recovery") or {}
        optimisation = snapshot.get("optimization") or {}
        completion = self._completion_state(snapshot.get("last_execution"))

        observations = []
        for dimension in (
            "transport_connected",
            "subscribed",
            "authorized",
            "job_available",
            "target_available",
        ):
            value = (
                lifecycle.get(dimension)
                if isinstance(lifecycle, Mapping)
                else None
            )
            observations.append(
                self._observation(
                    dimension=dimension,
                    value=value,
                    source="IntelligentPoolCoordinator.lifecycle",
                    now_ns=now_ns,
                )
            )
        observations.append(
            self._observation(
                dimension="recovery_not_faulted",
                value=(
                    recovery.get("faulted")
                    if isinstance(recovery, Mapping)
                    else None
                ),
                source="RecoveryGovernor.snapshot",
                now_ns=now_ns,
                invert_bool=True,
            )
        )
        execution_health = None
        if completion is not None:
            # Non-error completion labels are not a device health contract.
            execution_health = "FAILED" if completion == "DEVICE_ERROR" else None
        observations.append(
            self._observation(
                dimension="execution",
                value=execution_health,
                source="ExecutionRecord",
                now_ns=now_ns,
            )
        )
        optimisation_available = (
            isinstance(optimisation, Mapping)
            and optimisation.get("schema")
            == "pythia.closed-loop-optimisation/1"
        )
        observations.append(
            self._observation(
                dimension="optimisation_evidence",
                value=True if optimisation_available else None,
                source="ClosedLoopOptimizer.snapshot",
                now_ns=now_ns,
            )
        )
        decision = self.control.observe(
            tuple(observations),
            policy_id="mining-runtime-v1",
        )
        self._last_health = decision.state.value
        self._observations += 1

        diagnosis = self._diagnose(snapshot)
        if diagnosis is not None:
            changed = (
                self._last_issue is None
                or self._last_issue.get("issue") != diagnosis.get("issue")
                or self._last_issue.get("fault_class")
                != diagnosis.get("fault_class")
            )
            self._last_issue = {
                **diagnosis,
                "observed_at_ns": now_ns,
            }
            if changed:
                self.ledger.append(
                    "runtime-diagnosis",
                    self._last_issue,
                    at_ns=now_ns,
                )
        elif self._last_health == "HEALTHY":
            self._last_issue = None

        self._record_recoveries(recovery, now_ns)
        self._record_optimisation(optimisation, now_ns)
        return self.snapshot(snapshot)

    def snapshot(
        self,
        mining_snapshot: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        optimisation = (
            mining_snapshot.get("optimization")
            if isinstance(mining_snapshot, Mapping)
            else None
        )
        recovery = (
            mining_snapshot.get("recovery")
            if isinstance(mining_snapshot, Mapping)
            else None
        )
        current_configuration: Any = "Unavailable"
        if isinstance(optimisation, Mapping):
            current_configuration = copy.deepcopy(
                optimisation.get("current_configuration", "Unavailable")
            )
        active_recovery: Any = "Unavailable"
        if isinstance(recovery, Mapping):
            active_recovery = (
                recovery.get("active_recovery_id") or "Unavailable"
            )
        return {
            "schema": SCHEMA,
            "health": self._last_health,
            "detected_issue": self._last_issue or "Unavailable",
            "diagnosis": (
                self._last_issue.get("diagnosis", "Unavailable")
                if self._last_issue
                else "Unavailable"
            ),
            "proposed_action": (
                self._last_issue.get("proposed_action", "Unavailable")
                if self._last_issue
                else "Unavailable"
            ),
            "action_taken": self._last_action or "Unavailable",
            "active_recovery_id": active_recovery,
            "measured_result": self._last_result or "Unavailable",
            "last_successful_healing_event": (
                self._last_successful_healing or "Unavailable"
            ),
            "last_successful_optimisation": (
                self._last_successful_optimisation or "Unavailable"
            ),
            "last_optimisation_outcome": (
                self._last_optimisation or "Unavailable"
            ),
            "current_configuration": current_configuration,
            "evidence_source": (
                MINING_SCHEMA if self._observations else "Unavailable"
            ),
            "evidence_head": self.ledger.head,
            "evidence_records": len(self.ledger.records),
            "observations": self._observations,
            "qualification": unqualified_readiness(),
            "evidence_custody": "LOCAL_MIRROR_NOT_CANONICAL_THESEUS",
            "classification": {
                "PRESENT": True,
                "WIRED": self._observations > 0,
                "ACTIVE": self._observations > 0,
                "SELF_HEALING": self._self_healing_evidenced,
                "SELF_OPTIMISING": self._self_optimising_evidenced,
            },
        }