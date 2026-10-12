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
    PYTHIA_STORAGE_CUSTODY_MAX_PAYLOAD_BYTES   per-record custody cap
    PYTHIA_STORAGE_CUSTODY_MAX_TENANT_BYTES    per-tenant custody cap
    PYTHIA_STORAGE_CUSTODY_MAX_RECORDS         per-tenant record cap

The ``*_CUSTODY_MAX_*`` overrides size the THESEUS custody quotas; unset they
keep the underlying enterprise defaults, which are too small for real mining
lifecycle payloads (a live ``search_plan`` record is multi-MiB).

Attach in ``mining_runtime`` after the coordinator is built:

    recorder = MiningStorageRecorder.from_env(worker=username)
    if recorder is not None:
        coordinator.causal.set_observer(recorder.observe)
"""

from __future__ import annotations

import hashlib
import json
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
        self._restored = False
        # Recovered proof/lease state is never an authority to submit after restart.
        self._fresh_job_observed = False

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
        quota_env = {
            "max_payload": "PYTHIA_STORAGE_CUSTODY_MAX_PAYLOAD_BYTES",
            "max_records": "PYTHIA_STORAGE_CUSTODY_MAX_RECORDS",
            "max_tenant_bytes": "PYTHIA_STORAGE_CUSTODY_MAX_TENANT_BYTES",
        }
        quota_values = {
            field: int(os.getenv(env, "").strip())
            for field, env in quota_env.items()
            if os.getenv(env, "").strip()
        }
        custody_kwargs: dict[str, Any] = {}
        if quota_values:
            from aethel.enterprise.governance import Quotas

            custody_kwargs["quotas"] = Quotas(**quota_values)
        custody = TheseusFileCustody(
            root=custody_root,
            hmac_key=bytes.fromhex(custody_hex),
            **custody_kwargs,
        )
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
            if strict:
                store.close()
                custody.close()
                raise M3StorageError(
                    "strict M3 refuses unknown tenant; provision the storage tenant "
                    "through the authorised admission path before starting the miner"
                )
            client = store.provision_client(
                namespace, Quota(max_records=10**9, max_blob_bytes=10**12)
            )
            tenant_id = client.tenant_id
        # OVID exact transformation is explicitly enabled, not a silent rewrite
        # of the owner's representation/retention policy.
        transform_plane = None
        if os.getenv("PYTHIA_STORAGE_OVID_EXACT", "").strip().lower() in {
            "1", "true", "yes", "on",
        }:
            from hyba_db.ovid_transform import OvidTransformPlane

            transform_plane = OvidTransformPlane(store.files)
        recorder = cls(
            store.files, tenant_id, root, strict=strict, transform_plane=transform_plane,
        )
        recorder._store = store  # keep the connection reachable via the recorder
        try:
            recorder.recover()
        except Exception:
            store.close()
            custody.close()
            raise
        return recorder

    # -- durable restart / exact event replay ----------------------------- #

    @staticmethod
    def _event_key(event: Any) -> str:
        """Hash the *event identity*, not just its kind/detail.

        Repeated observations can be legitimate; reprocessing the very same
        mirrored event after an interrupted run must instead be idempotent.
        """
        return hashlib.sha256(_stable_json(event.as_dict()).encode()).hexdigest()

    def recover(self) -> dict[str, int]:
        """Revalidate THESEUS/SQLite/CAS and restore replay bookkeeping.

        This restores recorded history, not a live pool lease, AL HARAS
        authorisation or a right to submit. A fresh identity_bound event is
        mandatory before strict mining transitions after restart.
        """
        verification = self.files.verify_database(self.tenant_id)
        reconciliation = self.files.reconcile_files(self.tenant_id, self.root)
        if (
            not verification.get("passed")
            or not self.files.verify_mining(self.tenant_id)
            or not reconciliation.passed
        ):
            raise M3StorageError(
                "THESEUS mining recovery failed integrity/reconciliation: "
                + str(verification.get("errors") or reconciliation.unresolved)
            )
        db = self.files.store._db
        rows = db.execute(
            "SELECT record_id,kind,payload_json,content_sha256,parent_ids_json,"
            "custody_record_id FROM mining_lifecycle WHERE tenant_id=? ORDER BY rowid",
            (self.tenant_id,),
        ).fetchall()
        heads: dict[str, str] = {}
        records: dict[str, str] = {}
        for row in rows:
            rid = str(row["record_id"])
            if hashlib.sha256(row["payload_json"].encode()).hexdigest() != row["content_sha256"]:
                raise M3StorageError(f"mining recovery digest mismatch: {rid}")
            if not self.files.custody.verify(self.tenant_id, row["custody_record_id"]):
                raise M3StorageError(f"mining recovery custody invalid: {rid}")
            parents = json.loads(row["parent_ids_json"])
            if any(parent not in records for parent in parents):
                raise M3StorageError(f"mining recovery parent missing or out of order: {rid}")
            kind = str(row["kind"])
            # Heads belong to the *last* bound job; never cross a job boundary.
            if kind == "job":
                heads.clear()
            heads[kind] = rid
            records[rid] = kind

        seen: set[str] = set()
        receipts = db.execute(
            "SELECT fv.storage_uri,fv.content_sha256 FROM file_versions fv "
            "JOIN file_objects fo ON fo.tenant_id=fv.tenant_id "
            "AND fo.file_object_id=fv.file_object_id "
            "WHERE fv.tenant_id=? AND fo.logical_name LIKE 'receipt-%' "
            "AND fo.file_class!='transform' "
            "ORDER BY fv.rowid",
            (self.tenant_id,),
        ).fetchall()
        for receipt in receipts:
            uri = str(receipt["storage_uri"])
            if not uri.startswith("file://"):
                raise M3StorageError("mining recovery receipt is not a local verified blob")
            data = Path(uri[7:]).read_bytes()
            if hashlib.sha256(data).hexdigest() != receipt["content_sha256"]:
                raise M3StorageError("mining recovery receipt digest mismatch")
            doc = json.loads(data)
            if not isinstance(doc, dict) or any(
                field not in doc for field in ("kind", "seq", "at", "coordinate", "detail")
            ):
                raise M3StorageError("mining recovery receipt schema incomplete")
            identity = {
                k: doc[k] for k in ("kind", "seq", "at", "coordinate", "detail")
            }
            if doc.get("software_revision") is not None:
                identity["software_revision"] = doc["software_revision"]
            seen.add(hashlib.sha256(_stable_json(identity).encode()).hexdigest())

        with self._lock:
            self._heads = heads
            self.records = records
            self._seen = seen
            self._restored = bool(rows)
            self._fresh_job_observed = False
        return {"records": len(records), "replayable_events": len(seen)}

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
        key = self._event_key(event)
        with self._lock:
            if key in self._seen:
                return
            if event.kind == "identity_bound":
                # Never attach a new job to the previous job's proof/lease.
                self._heads.clear()
                self._fresh_job_observed = True
            elif (
                self.strict
                and not self._fresh_job_observed
                and event.kind in _CHAIN_EVENTS
                and event.kind not in {
                    "salamander_mode", "chronus107_mining_recovery",
                    "execution_backend_rerouted",
                }
            ):
                raise M3StorageError(
                    "fresh Stratum identity required after restart before mining transition"
                )
            coordinate = event.coordinate.as_dict()
            detail = dict(event.detail)
            emitted = []
            # Kinds already custodied before this event (the strict verified proof): the event
            # receipt may reference them but must not replace their own custody receipt.
            precustodied: set[str] = set()
            for kind, producer, _cls in _CHAIN_EVENTS.get(event.kind, ()):
                if kind == "verified_proof" and self.strict:
                    if "verified_proof" not in self._heads:
                        raise M3StorageError(
                            "submission boundary reached without a synchronously custodied verified proof"
                        )
                    emitted.append(kind)
                    precustodied.add(kind)
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
                self._emit(kind, payload, producer=producer, event_key=key)
                emitted.append(kind)
            # Every causal event — boundary or not — leaves a durable,
            # content-addressed receipt. Boundary receipts link to their mining
            # record; everything else links to the current chain head.
            receipt_class = _RECEIPT_CLASS[emitted[-1]] if emitted else "durable_evidence"
            self._receipt(event, receipt_class, emitted, preserve=precustodied)
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

    def _emit(
        self, kind: str, payload: dict[str, Any], *, producer: str, event_key: str
    ) -> str:
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
            idempotency_key=f"{event_key}:{kind}",
        )
        self._heads[kind] = record_id
        self.records[record_id] = kind
        return record_id

    def _receipt(
        self,
        event: Any,
        file_class: str,
        emitted: list[str],
        preserve: frozenset[str] | set[str] = frozenset(),
    ) -> str | None:
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
            producer_version=str(event.software_revision or "UNAVAILABLE"),
            schema_version=1,
            provenance={
                "source_ids": [
                    self._heads[kind] for kind in emitted if kind in self._heads
                ],
                "correlation_ids": event.coordinate.as_dict(),
                "code_ref": str(event.software_revision or "UNAVAILABLE"),
                "recovery_class": "theseus-canonical",
                "backend": str(event.detail.get("executed_route") or "UNAVAILABLE"),
                "device_identity": str(event.detail.get("device_identity") or "UNAVAILABLE"),
            },
            links=links,
        )
        for kind in emitted:
            if kind in self._heads and kind not in preserve:
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
            if self.strict and not self._fresh_job_observed:
                raise M3StorageError(
                    "verified proof refused: fresh Stratum identity required after restart"
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

    def health(self, *, reconcile: bool = True, full: bool = True) -> dict[str, Any]:
        """Return measured M3 storage/custody health; never synthesize PASS.

        ``full=False`` verifies only records appended since the last pass
        (rowid watermark) and carries forward the last full verdict: a
        failure stays failed until a later full pass succeeds. Without a
        prior successful full pass an incremental request runs in full.
        """
        try:
            last_full_ok = getattr(self, "_last_full_verify_ok", None)
            incremental = not full and last_full_ok is not None
            verification = self.files.verify_database(
                self.tenant_id,
                since=getattr(self, "_verify_watermark", None) if incremental else None,
            )
            if not incremental:
                self._last_full_verify_ok = bool(verification.get("passed"))
            elif not verification.get("passed"):
                self._last_full_verify_ok = False  # new rows failed: sticky until a full pass
            if isinstance(verification.get("watermark"), dict):
                self._verify_watermark = dict(verification["watermark"])
            verification = {
                **verification,
                "passed": bool(verification.get("passed")) and bool(self._last_full_verify_ok),
                "file_plane_ok": bool(verification.get("file_plane_ok"))
                and bool(self._last_full_verify_ok),
            }
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
                and self.files.verify_mining(self.tenant_id)
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
                "verification": "incremental" if incremental else "full",
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
