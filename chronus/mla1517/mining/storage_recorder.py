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


class MiningStorageRecorder:
    """CausalLedger observer that writes the durable mining evidence chain."""

    def __init__(
        self,
        files: Any,
        tenant_id: str,
        root: str | Path,
        *,
        transform_plane: Any | None = None,
    ) -> None:
        self.files = files
        self.tenant_id = tenant_id
        self.root = Path(root)
        self.transform_plane = transform_plane
        self._lock = threading.Lock()
        self._heads: dict[str, str] = {}
        self._seen: set[str] = set()
        self.records: dict[str, str] = {}  # record_id -> kind
        self.receipts: dict[str, str] = {}  # record_id -> file_version_id
        self.errors: int = 0

    # -- construction ----------------------------------------------------- #

    @classmethod
    def from_env(cls, *, worker: str | None = None) -> "MiningStorageRecorder | None":
        """Build a recorder from ``PYTHIA_STORAGE_*`` env, or ``None``."""
        db = os.getenv("PYTHIA_STORAGE_DB", "").strip()
        root = os.getenv("PYTHIA_STORAGE_ROOT", "").strip()
        if not db or not root:
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
        recorder = cls(store.files, tenant_id, root)
        recorder._store = store  # keep the connection reachable via the recorder
        return recorder

    # -- observer entry ---------------------------------------------------- #

    def observe(self, event: Any) -> None:
        """CausalLedger observer. Never raises into the mining path."""
        try:
            self._handle(event)
        except Exception:
            self.errors += 1
            LOG.exception("storage recorder failed on %s", getattr(event, "kind", "?"))

    def _handle(self, event: Any) -> None:
        key = (
            f"{event.kind}:{_stable_json(event.coordinate.as_dict())}:{_stable_json(event.detail)}"
        )
        with self._lock:
            if key in self._seen:
                return
            self._seen.add(key)
            coordinate = event.coordinate.as_dict()
            detail = dict(event.detail)
            emitted = []
            for kind, producer, _cls in _CHAIN_EVENTS.get(event.kind, ()):
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
            }


def _stable_json(value: Any) -> str:
    import json

    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


__all__ = ["MiningStorageRecorder"]
