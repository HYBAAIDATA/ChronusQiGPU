"""Salamander-governed remediation of THESEUS storage faults (closed loop).

Authority split (unchanged; see ``docs/SELF_HEALING.md``):

* THESEUS (``DurableTheseusService``) owns storage integrity and custody. It
  observes and detects (``scan_integrity``), diagnoses (``diagnose_object``)
  and executes one bounded, atomic, SHA-256-verified repair
  (``repair_object``) when asked.
* Salamander owns remediation. This module uses the recovered canonical
  Salamander package (distribution ``hyba-salamander-self-healing`` 1.0.0,
  import ``salamander``; source ``hybadatadevops1/HYBAEnterprise`` ``salamander/``)
  rather than a re-implementation: its ``AutonomicControlPlane``,
  ``ActionRegistry``, ``RecoveryPlan`` and hash-chained ``EvidenceLedger``.
* AL HARAS authorises every action through ``build_authorized_control_plane``
  (the guardian and an out-of-band token provider are supplied by the host;
  there is no opt-out).
* Chronus executes: the registered handler runs THESEUS's repair in this
  process.
* EUCLID keeps intelligence orchestration: this module makes no planning
  decisions beyond the bounded storage remediation and is driven by
  ``run_cycle`` from whatever schedule the orchestrator sets.

One ``run_cycle`` is: Observe -> Detect -> Diagnose -> Select remediation ->
Authorise -> Execute -> Verify (independent re-read of the SQLite file) ->
Accept or rollback -> Retain evidence (every ledger record is also written to
THESEUS as a content-addressed object) -> report, ready for the next cycle.

The Salamander package is proprietary and is not vendored here. When it is not
installed, :class:`SalamanderUnavailable` is raised; nothing is substituted.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from chronus.storage.durable import DurableTheseusService

REPAIR_HANDLER = "theseus.reed_solomon_repair"
CONFIRM_HANDLER = "theseus.confirm_no_partial_write"
REPAIR_VERIFIER = "theseus.independent_sqlite_reread"
EVIDENCE_TENANT = "salamander-evidence"


class SalamanderUnavailable(RuntimeError):
    """The canonical Salamander package is not installed; no substitute is used."""


def _salamander():
    try:
        import salamander
        from salamander import ActionRegistry, EvidenceLedger, build_authorized_control_plane
        from salamander.control_plane import FailClosed, RecoveryPlan, RecoveryStep
        from salamander.models import ActionKind, ActionRequest, Availability, HealthObservation
    except ImportError as exc:  # pragma: no cover - exercised where the package is absent
        raise SalamanderUnavailable(
            "hyba-salamander-self-healing is not installed; Salamander-governed remediation "
            "is unavailable (THESEUS keeps fail-closed behaviour)"
        ) from exc
    return {
        "version": salamander.__version__,
        "ActionRegistry": ActionRegistry,
        "EvidenceLedger": EvidenceLedger,
        "build_authorized_control_plane": build_authorized_control_plane,
        "FailClosed": FailClosed,
        "RecoveryPlan": RecoveryPlan,
        "RecoveryStep": RecoveryStep,
        "ActionKind": ActionKind,
        "ActionRequest": ActionRequest,
        "Availability": Availability,
        "HealthObservation": HealthObservation,
    }


def _payload_sha(path: str, object_id: str) -> str | None:
    """Independent read: a fresh read-only SQLite connection, not the service."""
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)) as db:
        row = db.execute("SELECT payload FROM objects WHERE object_id=?", (object_id,)).fetchone()
    return None if row is None else hashlib.sha256(bytes(row[0])).hexdigest()


@dataclass
class CycleReport:
    observed_damaged: int = 0
    repaired: list[str] = field(default_factory=list)
    escalated: list[dict] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)
    out_of_scope: int = 0  # count only: other tenants' objects are not described
    health_before: str = ""
    health_after: str = ""
    evidence_head: str = ""


class SalamanderTheseusRemediation:
    """Wire THESEUS repair into Salamander's AL HARAS-authorised control plane."""

    def __init__(
        self,
        store: DurableTheseusService,
        *,
        guardian: Any,
        token_provider: Callable[[Any], str],
        tenant_id: str,
        actor_id: str,
        max_recoveries_per_target: int = 2,
        retain_evidence_in_theseus: bool = True,
        clock_ns: Callable[[], int] = time.time_ns,
    ) -> None:
        self._s = _salamander()
        if not store.self_healing:
            raise ValueError("THESEUS self-healing (parity) must be enabled for remediation")
        self.store = store
        self.tenant_id = tenant_id
        self.actor_id = actor_id
        self.clock_ns = clock_ns
        self._snapshots: dict[str, str | None] = {}
        self._in_flight: set[tuple[str, str]] = set()
        self.retained_evidence: list[str] = []
        sink = self._retain_in_theseus if retain_evidence_in_theseus else None
        self.ledger = self._s["EvidenceLedger"](sink=sink)
        registry = self._s["ActionRegistry"]()
        kinds = self._s["ActionKind"]
        registry.register(REPAIR_HANDLER, {kinds.RESTORE_CUSTODY}, self._execute_repair,
                          verifier_id=REPAIR_VERIFIER, verifier=self._verify_repair)
        registry.register(CONFIRM_HANDLER, {kinds.ROLLBACK}, self._execute_confirm,
                          verifier_id=REPAIR_VERIFIER, verifier=self._verify_confirm)
        self.plane = self._s["build_authorized_control_plane"](
            registry=registry, guardian=guardian, token_provider=token_provider,
            ledger=self.ledger, clock_ns=clock_ns,
            max_recoveries_per_target=max_recoveries_per_target,
        )
        # Bind last: a failed construction must not leave the store bound to a dead instance.
        if store.repair_authority == "salamander":
            store.bind_repair_authority(self._authorised_now)

    # Retain evidence --------------------------------------------------
    def _retain_in_theseus(self, record: Mapping[str, Any]) -> None:
        body = json.dumps(record, sort_keys=True, separators=(",", ":"), default=str).encode()
        stored = self.store.store(EVIDENCE_TENANT, body)
        self.retained_evidence.append(stored.object_id)

    # Execute (Chronus process, THESEUS-owned operation) ----------------
    def _authorised_now(self, object_id: str, authority: str) -> bool:
        # True only inside a handler call, which Salamander's registry makes
        # only after consuming a valid single-use AL HARAS decision.
        return (object_id, authority) in self._in_flight

    def _execute_repair(self, request) -> Mapping[str, Any]:
        authority = f"salamander:{request.action_id}"
        token = (request.target, authority)
        self._in_flight.add(token)
        try:
            result = self.store.repair_object(request.target, authority=authority)
        finally:
            self._in_flight.discard(token)
        return {"handler_reported": result}

    def _execute_confirm(self, request) -> Mapping[str, Any]:
        # THESEUS commits a repair in one transaction and only with bytes that
        # match the content address, so a rejected repair leaves no partial
        # write to undo. Rollback here is confirming that, independently.
        return {"confirmation_requested": request.target}

    # Verify (independent of the handler's report) ---------------------
    def _verify_repair(self, request, response) -> Mapping[str, Any]:
        observed = _payload_sha(self.store.path, request.target)
        ok = observed == request.target
        return {"verified": ok, "evidence_ref": f"sqlite-reread:{request.target}:{observed}" if ok else None,
                "observations": {"observed_sha256": observed, "content_address": request.target},
                "error": None if ok else "payload does not hash to its content address after repair"}

    def _verify_confirm(self, request, response) -> Mapping[str, Any]:
        observed = _payload_sha(self.store.path, request.target)
        before = self._snapshots.get(request.target)
        ok = observed is not None and observed in {before, request.target}
        return {"verified": ok, "evidence_ref": f"sqlite-reread:{request.target}:{observed}" if ok else None,
                "observations": {"observed_sha256": observed, "pre_action_sha256": before},
                "error": None if ok else "payload changed to bytes that are neither the original nor verified"}

    # Observe / Detect --------------------------------------------------
    def _observe(self, damaged: int, unrepairable: int):
        s = self._s
        state = "HEALTHY" if damaged == 0 else ("FAILED" if unrepairable else "DEGRADED")
        obs = s["HealthObservation"](
            subsystem="THESEUS", dimension="content_integrity", tenant_id=self.tenant_id,
            observed_at_ns=self.clock_ns(), availability=s["Availability"].MEASURED, value=state,
            source="DurableTheseusService.scan_integrity",
        )
        return self.plane.observe([obs]).state.value

    def run_cycle(self) -> CycleReport:
        s = self._s
        report = CycleReport()
        findings = self.store.scan_integrity()  # Observe + Detect + Diagnose
        report.observed_damaged = len(findings)
        unrepairable = [f for f in findings if f["status"] == "UNREPAIRABLE"]
        report.health_before = self._observe(len(findings), len(unrepairable))
        for finding in findings:
            object_id = finding["object_id"]
            holders = self.store.tenants_for_object(object_id)
            if self.tenant_id not in holders and EVIDENCE_TENANT not in holders:
                # Custody scope: this remediation tenant holds no record for the
                # object, so it may not act on it. Only a count is reported, so a
                # tenant-scoped report reveals nothing about other tenants' data.
                report.out_of_scope += 1
                continue
            if finding["status"] != "REPAIRABLE":
                # Select remediation: outside the bound there is no safe automatic
                # action; escalate to a human with the evidence.
                self.ledger.append("remediation-escalated", dict(finding), at_ns=self.clock_ns())
                report.escalated.append(finding)
                continue
            observed = _payload_sha(self.store.path, object_id)
            self._snapshots[object_id] = observed
            key = f"{object_id}:{observed}"
            repair = s["ActionRequest"](
                action_id=f"theseus-repair:{key}", kind=s["ActionKind"].RESTORE_CUSTODY,
                handler=REPAIR_HANDLER, tenant_id=self.tenant_id, target=object_id,
                reason=f"content address mismatch; {finding['reason']}",
                bounds={"max_attempts": 1, "max_corrected_bytes": finding.get("corrected_bytes", 0)},
                idempotency_key=f"repair:{key}", actor_id=self.actor_id,
            )
            confirm = s["ActionRequest"](
                action_id=f"theseus-confirm:{key}", kind=s["ActionKind"].ROLLBACK,
                handler=CONFIRM_HANDLER, tenant_id=self.tenant_id, target=object_id,
                reason="confirm a rejected repair left no partial write",
                bounds={"max_attempts": 1}, idempotency_key=f"confirm:{key}", actor_id=self.actor_id,
            )
            plan = s["RecoveryPlan"](
                recovery_id=f"theseus-recovery:{key}", tenant_id=self.tenant_id, target=object_id,
                steps=(s["RecoveryStep"]("repair", repair, rollback=confirm),),
                max_actions=2, deadline_ns=self.clock_ns() + 60_000_000_000,
            )
            try:
                results = self.plane.recover(plan)  # Authorise + Execute + Verify + accept/rollback
            except s["FailClosed"] as exc:
                report.rejected.append({"object_id": object_id, "reason": str(exc)})
                continue
            if results and results[0].verified:
                report.repaired.append(object_id)
            else:
                report.rejected.append({"object_id": object_id,
                                        "reason": results[0].error if results else "no result"})
        remaining = self.store.scan_integrity()
        report.health_after = self._observe(
            len(remaining), sum(1 for f in remaining if f["status"] == "UNREPAIRABLE"))
        report.evidence_head = self.ledger.head
        return report
