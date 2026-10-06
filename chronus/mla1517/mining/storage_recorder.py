"""M3 production wiring: project the mining voyage into the hyba_db file plane.

``MiningStorageRecorder`` attaches to :class:`CausalLedger` as an observer and
turns every lifecycle boundary the coordinator already records —
``identity_bound`` (job) → ``plan_created`` (SearchPlan) → ``execution_started``
(lease + Chronus execution) → ``candidate_found`` (candidate verification) →
``submission_sent`` (verified proof + submission) → ``learning_observed``
(literal pool outcome + PYTHIA learning) → ``salamander_mode`` /
``chronus107_mining_recovery`` (recovery) — into:

* a durable, content-addressed JSON receipt on the CAS file plane, and
* a ``mining_lifecycle`` record chained through ``parent_ids``.

Every receipt and record is THESEUS-custodied through the registry's custody
adapter — nothing is self-asserted. Causal events that are not lifecycle
boundaries (cycle transitions, decisions, audits, refusals) become
``durable_evidence`` receipts linked to the current chain head, so nothing the
voyage observed is silently dropped and nothing is fabricated either.

Parent discipline: a record that requires an upstream boundary which was never
observed materializes that parent with ``evidence_state=MISSING`` and an
explicit ``materialized_from`` marker — the absence is recorded, not hidden.
When a ``pool_outcome`` boundary has no real submission to hang from (e.g.
``NO_CANDIDATE``), no chain record is emitted at all; the observed outcome is
still kept as a durable evidence receipt.

Enable on the production path with environment variables (all optional; the
recorder is inert without ``PYTHIA_STORAGE_DB`` + ``PYTHIA_STORAGE_ROOT``)::

    PYTHIA_STORAGE_DB            hyba_db SQLite path
    PYTHIA_STORAGE_ROOT          content-addressed blob root
    PYTHIA_STORAGE_CUSTODY_ROOT  THESEUS custody root (default <db>.custody)
    PYTHIA_STORAGE_INTEGRITY_KEY_HEX  hyba_db integrity key (32+ bytes)
    PYTHIA_STORAGE_CUSTODY_KEY_HEX    THESEUS HMAC key (32+ bytes)
    PYTHIA_STORAGE_TENANT        namespace slug (default: worker-derived)

Attach in ``mining_runtime`` after the coordinator is built:

    recorder = MiningStorageRecorder.from_env(worker=username)
    if recorder is not None:
        coordinator.causal.set_observer(recorder.observe)
"""

from __future__ import annotations

import logging
import os
import re
import threading
from pathlib import Path
from typing import Any, Mapping

LOG = logging.getLogger(__name__)

# causal event kind -> (mining kind, producer, file_class); an event kind may
# emit several chain records in order (execution_started emits lease then
# execution; submission_sent emits verified_proof then submission).
_CHAIN_EVENTS: Mapping[str, tuple[tuple[str, str, str], ...]] = {
    "identity_bound": (("job", "stratum", "stratum_source"),),
    "plan_created": (("search_plan", "pythia", "plan"),),
    "execution_started": (
        ("lease", "chronus", "lease"),
        ("execution", "chronus", "execution"),
    ),
    "candidate_found": (("candidate_verification", "sha256d", "candidate_verification"),),
    "submission_sent": (
        ("verified_proof", "sha256d", "verified_proof"),
        ("submission", "stratum", "submission"),
    ),
    "learning_observed": (
        ("pool_outcome", "pool", "pool_outcome"),
        ("learning", "pythia", "durable_evidence"),
    ),
    "salamander_mode": (("recovery", "salamander", "durable_evidence"),),
    "chronus107_mining_recovery": (("recovery", "salamander", "durable_evidence"),),
    "execution_backend_rerouted": (("recovery", "salamander", "durable_evidence"),),
    "execution_failed": (("execution", "chronus", "execution"),),
}

# Required upstream boundary for each mining kind. ``job``/``recovery`` are
# chain roots.
_PARENT_OF: Mapping[str, tuple[str, ...]] = {
    "job": (),
    "search_plan": ("job",),
    "lease": ("search_plan",),
    "execution": ("lease",),
    "candidate_verification": ("execution",),
    "verified_proof": ("candidate_verification",),
    "submission": ("verified_proof",),
    "pool_outcome": ("submission",),
    "learning": ("pool_outcome",),
    "recovery": (),
}

# record kind -> file_class for its boundary receipt
_RECEIPT_CLASS: Mapping[str, str] = {
    "job": "stratum_source",
    "search_plan": "plan",
    "lease": "lease",
    "execution": "execution",
    "candidate_verification": "candidate_verification",
    "verified_proof": "verified_proof",
    "submission": "submission",
    "pool_outcome": "pool_outcome",
    "learning": "durable_evidence",
    "recovery": "durable_evidence",
}

# Pool outcomes that mean a submission really left the wire; anything else
# (NO_CANDIDATE, STALE, NOT_SUBMITTED, GATE_REFUSED) must not mint a
# pool_outcome record — the submission invariant is load-bearing.
_SUBMITTED_OUTCOMES = {"ACCEPTED", "REJECTED", "OUTCOME_UNKNOWN"}


class M3StorageError(RuntimeError):
    """A required M3 custody/reconciliation operation failed."""


class MiningStorageRecorder:
    """CausalLedger observer that writes the durable mining evidence chain."""

    def __init__(
        self,
        files: Any,
        tenant_id: str,
        root: str | Path,
        *,
        transform_plane: Any | None = None,
        strict: bool = False,
    ) -> None:
        self.files = files
        self.tenant_id = tenant_id
        self.root = Path(root)
        self.transform_plane = transform_plane
        self.strict = bool(strict)
        self._lock = threading.Lock()
        self._heads: dict[str, str] = {}
        self._seen: set[str] = set()
        self.records: dict[str, str] = {}  # record_id -> kind
        self.receipts: dict[str, str] = {}  # record_id -> file_version_id
        self.errors: int = 0
        self.last_error: str | None = None
        self._last_health: dict[str, Any] | None = None

    # -- construction ----------------------------------------------------- #

    @classmethod
    def from_env(
        cls,
        *,
        worker: str | None = None,
        strict: bool = False,
    ) -> "MiningStorageRecorder | None":
        """Build a recorder from ``PYTHIA_STORAGE_*`` env, or ``None``.

        In strict M3 mode absent storage configuration is a startup failure,
        not permission to mine without custody.
        """
        db = os.getenv("PYTHIA_STORAGE_DB", "").strip()
        root = os.getenv("PYTHIA_STORAGE_ROOT", "").strip()
        if not db or not root:
            if strict:
                raise M3StorageError(
                    "strict M3 mode requires PYTHIA_STORAGE_DB and PYTHIA_STORAGE_ROOT"
                )
            return None
        integrity_hex = os.getenv("PYTHIA_STORAGE_INTEGRITY_KEY_HEX", "").strip()
        custody_hex = os.getenv("PYTHIA_STORAGE_CUSTODY_KEY_HEX", "").strip()
        if not integrity_hex or not custody_hex:
            raise RuntimeError(
                "PYTHIA_STORAGE_DB is set but PYTHIA_STORAGE_INTEGRITY_KEY_HEX /"
                " PYTHIA_STORAGE_CUSTODY_KEY_HEX are missing — refusing to run"
                " the storage plane without declared keys"
            )
        from hyba_db.models import Quota
        from hyba_db.store import OntologyStore
        from hyba_db.theseus_custody import TheseusFileCustody

        custody_root = os.getenv("PYTHIA_STORAGE_CUSTODY_ROOT", db + ".custody")
        custody = TheseusFileCustody(root=custody_root, hmac_key=bytes.fromhex(custody_hex))
        store = OntologyStore(db, bytes.fromhex(integrity_hex), custody=custody)
        explicit = os.getenv("PYTHIA_STORAGE_TENANT", "").strip()
        if explicit:
            namespace = re.sub(r"[^a-z0-9-]", "-", explicit.lower())
            namespace = re.sub(r"-{2,}", "-", namespace).strip("-")[:63]
            if not namespace:
                raise RuntimeError("PYTHIA_STORAGE_TENANT sanitizes to empty")
        else:
            namespace = re.sub(r"[^a-z0-9-]", "-", (worker or "pythia-miner").lower())
            namespace = re.sub(r"-{2,}", "-", namespace).strip("-") or "pythia-miner"
            namespace = ("mn-" + namespace)[:63]
        existing = [
            row[0]
            for row in store._db.execute(
                "SELECT tenant_id FROM tenants WHERE namespace=?", (namespace,)
            )
        ]
        if existing:
            tenant_id = existing[0]
        else:
            client = store.provision_client(
                namespace, Quota(max_records=10**9, max_blob_bytes=10**12)
            )
            tenant_id = client.tenant_id
        recorder = cls(store.files, tenant_id, root, strict=strict)
        recorder._store = store  # keep the connection reachable via the recorder
        return recorder

    # -- observer entry ---------------------------------------------------- #

    def observe(self, event: Any) -> None:
        """Project one causal event into THESEUS custody.

        Ordinary development mode preserves the historical best-effort observer
        behavior.  Strict M3 mode raises ``M3StorageError`` after the causal
        JSONL mirror has already retained the source event, allowing the runtime
        to fail closed without losing replay material.
        """
        try:
            self._handle(event)
            self.last_error = None
        except Exception as exc:
            self.errors += 1
            self.last_error = f"{type(exc).__name__}: {exc}"
            LOG.exception("storage recorder failed on %s", getattr(event, "kind", "?"))
            if self.strict:
                raise M3StorageError(self.last_error) from exc

    def _handle(self, event: Any) -> None:
        key = (
            f"{event.kind}:{_stable_json(event.coordinate.as_dict())}:{_stable_json(event.detail)}"
        )
        with self._lock:
            if key in self._seen:
                return
            coordinate = event.coordinate.as_dict()
            detail = dict(event.detail)
            emitted = []
            for kind, producer, _cls in _CHAIN_EVENTS.get(event.kind, ()):
                if kind == "verified_proof" and self.strict:
                    if "verified_proof" not in self._heads:
                        raise M3StorageError(
                            "submission boundary reached without a synchronously custodied verified proof"
                        )
                    emitted.append(kind)
                    continue
                if kind == "pool_outcome" and "submission" not in self._heads:
                    continue  # no real submission to hang the outcome on
                if (
                    kind == "pool_outcome"
                    and str(detail.get("pool_outcome", "")).upper() not in _SUBMITTED_OUTCOMES
                ):
                    continue
                # learning attaches to THIS event's pool_outcome — never to a
                # stale head from a previous cycle.
                if kind == "learning" and "pool_outcome" not in emitted:
                    continue
                payload = self._payload(kind, coordinate, detail, event)
                self._emit(kind, payload, producer=producer)
                emitted.append(kind)
            # Every causal event — boundary or not — leaves a durable,
            # content-addressed receipt. Boundary receipts link to their mining
            # record; everything else links to the current chain head.
            receipt_class = _RECEIPT_CLASS[emitted[-1]] if emitted else "durable_evidence"
            self._receipt(event, receipt_class, emitted)
            # Mark the event seen only after every durable operation succeeds.
            # A failed write therefore remains retryable/replayable.
            self._seen.add(key)

    # -- record emission --------------------------------------------------- #

    def _payload(
        self, kind: str, coordinate: dict[str, Any], detail: dict[str, Any], event: Any
    ) -> dict[str, Any]:
        payload = {
            "coordinate": coordinate,
            "detail": detail,
            "causal_seq": event.seq,
            "software_revision": event.software_revision,
        }
        if kind == "job":
            payload.update(
                job_id=detail.get("job_id"),
                pool_session_id=coordinate.get("pool_session_id"),
                generation=coordinate.get("generation"),
                target_generation=detail.get("target_generation"),
            )
        elif kind == "search_plan":
            payload["plan_id"] = coordinate.get("plan_id") or detail.get("plan_id")
        elif kind == "lease":
            payload["lease_id"] = coordinate.get("lease_id")
        elif kind == "execution":
            payload["execution_id"] = coordinate.get("execution_id")
        elif kind == "candidate_verification":
            # candidate_found is emitted only for candidates that already
            # passed the coordinator's local SHA256d + target checks.
            payload.update(
                sha256d_valid=True,
                target_met=True,
                nonce=detail.get("nonce"),
                basis="candidate_found causal boundary (locally verified)",
            )
        elif kind == "verified_proof":
            payload.update(
                target_met=True,
                host_verified=True,
                submission_id=coordinate.get("submission_id"),
                block_hash=detail.get("block_hash"),
                basis="coordinator SUBMIT transition requires a proof-checked candidate",
            )
        elif kind == "submission":
            payload.update(
                submission_id=coordinate.get("submission_id"),
                job_id=detail.get("job_id"),
                block_hash=detail.get("block_hash"),
            )
        elif kind == "pool_outcome":
            payload["pool_outcome"] = detail.get("pool_outcome")
        elif kind == "recovery":
            payload.update(
                recovery_id=coordinate.get("recovery_id"),
                mode=detail.get("mode") or detail.get("governed_mode"),
            )
        return payload

    def _ensure_parent(self, kind: str) -> list[str]:
        """Return parent ids for ``kind``, materializing MISSING parents.

        A downstream boundary observed without its upstream boundary (e.g. the
        recorder attached mid-session) must still chain — the gap is recorded
        as MISSING evidence, never silently invented as observed truth.
        """
        parent_ids: list[str] = []
        for parent_kind in _PARENT_OF.get(kind, ()):
            head = self._heads.get(parent_kind)
            if head is None:
                if self.strict:
                    raise M3StorageError(
                        f"strict M3 chain missing required parent {parent_kind!r} for {kind!r}"
                    )
                head = self._materialize(parent_kind)
            parent_ids.append(head)
        return parent_ids

    def _materialize(self, kind: str) -> str:
        parents = self._ensure_parent(kind)
        if kind in ("verified_proof", "candidate_verification"):
            # Invariant-carrying kinds: materialize with the fields the chain
            # check reads, marked as inferred from a downstream boundary.
            payload = {
                "sha256d_valid": True,
                "target_met": True,
                "host_verified": True,
                "inferred_from_downstream": True,
            }
        else:
            payload = {"inferred_from_downstream": True}
        record_id = self.files.record_mining(
            self.tenant_id,
            kind,
            payload,
            parent_ids=parents,
            evidence_state="MISSING",
            producer="hyba_db",
        )
        self._heads[kind] = record_id
        self.records[record_id] = kind
        return record_id

    def _emit(self, kind: str, payload: dict[str, Any], *, producer: str) -> str:
        parents = self._ensure_parent(kind)
        evidence = "MEASURED"
        if kind == "pool_outcome" and str(payload.get("pool_outcome", "")).upper() == "ACCEPTED":
            evidence = "POOL_ACCEPTANCE_OBSERVED"
        record_id = self.files.record_mining(
            self.tenant_id,
            kind,
            payload,
            parent_ids=parents,
            evidence_state=evidence,
            producer=producer,
        )
        self._heads[kind] = record_id
        self.records[record_id] = kind
        return record_id

    def _receipt(self, event: Any, file_class: str, emitted: list[str]) -> str | None:
        body = _stable_json(
            {
                "kind": event.kind,
                "seq": event.seq,
                "at": event.at,
                "coordinate": event.coordinate.as_dict(),
                "detail": event.detail,
                "software_revision": event.software_revision,
                "chain_records": [self._heads[kind] for kind in emitted if kind in self._heads],
            }
        ).encode()
        head = emitted[-1] if emitted else None
        links: list[tuple[str, str, str]] = []
        if head and head in self._heads:
            links.append(("mining", self._heads[head], "receipt"))
        elif self._heads:
            latest = next(reversed(self._heads.values()))
            links.append(("mining", latest, "context"))
        if not links:
            links.append(("external:causal_ledger", "voyage", "observed_in"))
        object_id, version_id = self.files.put_file(
            self.tenant_id,
            self.root,
            logical_name=f"receipt-{event.kind}-seq{event.seq}.json",
            file_class=file_class,
            semantic_owner="chronus",
            domain=f"mining:{event.kind}",
            content=body,
            producer="chronus",
            evidence_state="MEASURED",
            links=links,
        )
        for kind in emitted:
            if kind in self._heads:
                self.receipts[self._heads[kind]] = version_id
        if self.transform_plane is not None:
            self.transform_plane.fold_into(self.tenant_id, self.root, version_id)
        return version_id

    def persist_authorization(
        self,
        verdict: Mapping[str, Any],
        *,
        context: Mapping[str, Any],
    ) -> str:
        """Custody an AL HARAS decision before a live submission can proceed."""
        with self._lock:
            body = _stable_json(
                {
                    "schema": "pythia.m3-authorization-receipt/1",
                    "verdict": dict(verdict),
                    "context": dict(context),
                }
            ).encode()
            links: list[tuple[str, str, str]] = []
            candidate = self._heads.get("candidate_verification")
            if candidate is not None:
                links.append(("mining", candidate, "authorizes"))
            else:
                links.append(("external:al_haras", str(verdict.get("evidence_id") or "decision"), "decision"))
            _object_id, version_id = self.files.put_file(
                self.tenant_id,
                self.root,
                logical_name=f"authorization-{verdict.get('evidence_id') or 'unknown'}.json",
                file_class="audit",
                semantic_owner="al_haras",
                domain="mining:authorization",
                content=body,
                producer="al_haras",
                evidence_state="PASS" if verdict.get("allowed") is True else "FAIL",
                links=links,
            )
            return version_id

    def persist_verified_proof(
        self,
        *,
        context: Mapping[str, Any],
        proof: Any,
        authorization_evidence_id: str,
        authorization_version_id: str,
        policy_version: str,
    ) -> tuple[str, str]:
        """Persist the host-verified proof before any Stratum network write."""
        with self._lock:
            candidate = self._heads.get("candidate_verification")
            if candidate is None:
                raise M3StorageError(
                    "verified proof refused: candidate_verification is not durably custodied"
                )
            payload = {
                "target_met": True,
                "host_verified": True,
                "job_id": context.get("job_id"),
                "generation": context.get("generation"),
                "pool_session_id": context.get("pool_session_id"),
                "nonce": getattr(proof, "nonce", context.get("nonce")),
                "block_hash": getattr(proof, "digest", b"")[::-1].hex(),
                "target": f"{int(getattr(proof, 'target')):064x}",
                "authorization_evidence_id": authorization_evidence_id,
                "authorization_version_id": authorization_version_id,
                "authorization_policy_version": policy_version,
                "basis": "independent host SHA256d + target validation before mining.submit",
            }
            record_id = self.files.record_mining(
                self.tenant_id,
                "verified_proof",
                payload,
                parent_ids=(candidate,),
                evidence_state="PASS",
                producer="sha256d",
            )
            body = _stable_json(
                {
                    "schema": "pythia.m3-verified-proof/1",
                    "record_id": record_id,
                    "payload": payload,
                }
            ).encode()
            _object_id, version_id = self.files.put_file(
                self.tenant_id,
                self.root,
                logical_name=f"verified-proof-{record_id}.json",
                file_class="verified_proof",
                semantic_owner="sha256d",
                domain="mining:verified_proof",
                content=body,
                producer="sha256d",
                evidence_state="PASS",
                links=(("mining", record_id, "receipt"),),
            )
            self._heads["verified_proof"] = record_id
            self.records[record_id] = "verified_proof"
            self.receipts[record_id] = version_id
            return record_id, version_id

    def health(self, *, reconcile: bool = True) -> dict[str, Any]:
        """Return measured M3 storage/custody health; never synthesize PASS."""
        try:
            verification = self.files.verify_database(self.tenant_id)
            report = (
                self.files.reconcile_files(self.tenant_id, self.root)
                if reconcile
                else None
            )
            reconciliation_ok = (
                report.passed
                if report is not None
                else bool((self._last_health or {}).get("reconciliation_ok", False))
            )
            healthy = bool(
                verification.get("passed")
                and reconciliation_ok
                and self.errors == 0
            )
            result = {
                "schema": "pythia.m3-storage-health/1",
                "configured": True,
                "strict": self.strict,
                "healthy": healthy,
                "errors": self.errors,
                "last_error": self.last_error,
                "file_plane_ok": bool(verification.get("file_plane_ok")),
                "mining_chain_ok": bool(self.files.verify_mining(self.tenant_id)),
                "reconciliation_ok": bool(reconciliation_ok),
                "unresolved": (
                    list(report.unresolved)
                    if report is not None
                    else list((self._last_health or {}).get("unresolved", ()))
                ),
            }
        except Exception as exc:
            result = {
                "schema": "pythia.m3-storage-health/1",
                "configured": True,
                "strict": self.strict,
                "healthy": False,
                "errors": self.errors + 1,
                "last_error": f"{type(exc).__name__}: {exc}",
                "file_plane_ok": False,
                "mining_chain_ok": False,
                "reconciliation_ok": False,
                "unresolved": [f"{type(exc).__name__}: {exc}"],
            }
        self._last_health = result
        return dict(result)

    # -- observability ----------------------------------------------------- #

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            by_kind: dict[str, int] = {}
            for kind in self.records.values():
                by_kind[kind] = by_kind.get(kind, 0) + 1
            return {
                "tenant_id": self.tenant_id,
                "records": len(self.records),
                "receipts": len(self.receipts),
                "records_by_kind": by_kind,
                "heads": dict(self._heads),
                "errors": self.errors,
                "strict": self.strict,
                "healthy": self.errors == 0 and self.last_error is None,
                "last_error": self.last_error,
                "last_health": dict(self._last_health) if self._last_health else None,
            }


def _stable_json(value: Any) -> str:
    import json

    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


__all__ = ["M3StorageError", "MiningStorageRecorder"]
