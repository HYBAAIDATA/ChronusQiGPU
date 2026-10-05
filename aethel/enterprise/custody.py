"""Enterprise Theseus custody — single-root primary+replica+journal."""

from __future__ import annotations

import json
import os
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from .errors import (
    AuthenticityError,
    AuthorityBoundaryError,
    ConcurrencyConflict,
    ReadOnlyModeError,
    SchemaVersionError,
    UnrecoverableCustodyError,
)
from .authenticity import (
    content_digest,
    is_insecure_dev_key,
    mac_create,
    mac_verify,
)
from .checkpoint import CheckpointIntegrityError, CheckpointManager
from .governance import Quotas
from .hooks import AllowAllHook, SecurityHook
from .journal import FileLock, WriteAheadJournal
from .ovid_registry import DEFAULT_OVID_REGISTRY, OvidRegistry, b64d, b64e
from .records import (
    OperationalRecord,
    ProducerRegistry,
    default_dependency_policy,
    default_producer_registry,
)
from .recovery import (
    RecoveryReport,
    build_recovery_report,
    fold_journal_ops,
    replay_into,
    verify_replay,
)
from .retention import RetentionPolicy
from .schema import (
    THESEUS_FORMAT_VERSION,
    OVID_TRANSFORM_V1,
    CustodyEnvelope,
    CustodyEvent,
)
from .telemetry import EvidenceTelemetry


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    text = json.dumps(data, sort_keys=True, indent=2)
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _read_json(path: Path) -> Optional[dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


class EnterpriseCustody:
    """Theseus-shaped enterprise custody under one filesystem root."""

    def __init__(
        self,
        root: Path | str,
        *,
        tenant: str = "default",
        hmac_key: Optional[bytes] = None,
        key_id: str = "k1",
        require_authenticity: bool = True,
        allow_insecure_dev_key: bool = False,
        previous_hmac_keys: Optional[list[bytes]] = None,
        quotas: Optional[Quotas] = None,
        hook: Optional[SecurityHook] = None,
        read_only: bool = False,
        chronus_accel: bool = False,
        ovid: Optional[OvidRegistry] = None,
        telemetry: Optional[EvidenceTelemetry] = None,
        use_ovid_fold: bool = True,
        producer_registry: Optional[ProducerRegistry] = None,
        dependency_policy: Optional[dict[str, tuple[int, ...]]] = None,
        access_contract: Optional[Any] = None,
        require_access_contract: bool = False,
        retention: Optional[RetentionPolicy] = None,
    ) -> None:
        self.root = Path(root)
        self.tenant = tenant
        self.key_id = str(key_id)
        self.require_authenticity = bool(require_authenticity)
        self.allow_insecure_dev_key = bool(allow_insecure_dev_key)
        self.previous_hmac_keys = list(previous_hmac_keys or [])
        self.hmac_key = self._resolve_hmac_key(hmac_key)
        self.quotas = quotas or Quotas()
        self.hook: SecurityHook = hook or AllowAllHook()
        self.read_only = read_only
        self.chronus_accel = bool(chronus_accel)
        self.ovid = ovid or DEFAULT_OVID_REGISTRY
        self.telemetry = telemetry or EvidenceTelemetry()
        self.use_ovid_fold = use_ovid_fold
        self.producer_registry = producer_registry or default_producer_registry()
        self.dependency_policy = (
            dict(dependency_policy)
            if dependency_policy is not None
            else default_dependency_policy(
                theseus_format_version=THESEUS_FORMAT_VERSION,
                ovid_transform_versions=self.ovid.supported(),
            )
        )
        # A stored record does not create authority to access it. Access is
        # granted by an explicitly supplied contract (callable or hook
        # before_get/before_delete); absence is declared, not hidden.
        self.access_contract = access_contract
        self.require_access_contract = bool(require_access_contract)
        self.retention = retention

        self._lock = threading.RLock()
        self.tenant_root = self.root / "tenants" / self._safe_tenant(tenant)
        self.primary_dir = self.tenant_root / "primary"
        self.replica_dir = self.tenant_root / "replica"
        self.journal_path = self.tenant_root / "journal" / "wal.jsonl"
        self.events_path = self.tenant_root / "provenance" / "events.jsonl"
        self.meta_path = self.tenant_root / "meta.json"
        self._file_lock = FileLock(self.tenant_root / "custody.lock")
        self.checkpoints = CheckpointManager(self.tenant_root)
        self._recovery_report = RecoveryReport()

        for d in (
            self.primary_dir,
            self.replica_dir,
            self.journal_path.parent,
            self.events_path.parent,
        ):
            d.mkdir(parents=True, exist_ok=True)

        self.journal = WriteAheadJournal(self.journal_path)
        self._idempotency: dict[str, str] = {}  # key -> record_id
        self._bytes_used = 0
        self._record_count = 0
        self._degraded = False
        self._ready = False
        self._events: list[CustodyEvent] = []

        self.recover()

    @staticmethod
    def _safe_tenant(tenant: str) -> str:
        cleaned = "".join(c if c.isalnum() or c in "-_" else "_" for c in tenant)
        return cleaned or "default"

    def _primary_path(self, record_id: str) -> Path:
        return self.primary_dir / f"{record_id}.json"

    def _replica_path(self, record_id: str) -> Path:
        return self.replica_dir / f"{record_id}.json"

    def _resolve_hmac_key(self, hmac_key: Optional[bytes]) -> bytes:
        """Fail-closed when authenticity required and no usable key is provided.

        No silent production default. Explicit allow_insecure_dev_key=True is
        required for lab/dev placeholder keys. AL HARAS policy is not applied
        here — only key presence/shape.
        """
        if hmac_key is None or hmac_key == b"":
            if self.require_authenticity:
                raise AuthenticityError(
                    "HMAC key required (require_authenticity=True); "
                    "no silent default production key"
                )
            return b""
        key = bytes(hmac_key)
        if (
            self.require_authenticity
            and is_insecure_dev_key(key)
            and not self.allow_insecure_dev_key
        ):
            raise AuthenticityError(
                "refusing insecure/default HMAC key without allow_insecure_dev_key=True"
            )
        if self.require_authenticity and len(key) < 16:
            raise AuthenticityError("HMAC key must be >= 16 bytes")
        return key

    def _append_event(self, event: CustodyEvent) -> None:
        self._events.append(event)
        line = json.dumps(event.to_dict(), sort_keys=True) + "\n"
        with open(self.events_path, "a", encoding="utf-8") as fh:
            fh.write(line)
            fh.flush()

    def recover(self) -> None:
        """Recover journal and rebuild indexes; heal divergent replicas."""
        with self._lock:
            with self._file_lock:
                self.journal.recover()
                self._idempotency.clear()
                self._bytes_used = 0
                self._record_count = 0
                self._degraded = False
                # Load events
                self._events = []
                if self.events_path.exists():
                    for ln in self.events_path.read_text(encoding="utf-8").splitlines():
                        if not ln.strip():
                            continue
                        try:
                            self._events.append(CustodyEvent.from_dict(json.loads(ln)))
                        except (json.JSONDecodeError, KeyError, TypeError):
                            continue
                # Scan primary ids
                ids = {p.stem for p in self.primary_dir.glob("*.json")}
                ids |= {p.stem for p in self.replica_dir.glob("*.json")}
                scan: list[tuple[str, Optional[dict], Optional[str]]] = []
                for rid in sorted(ids):
                    try:
                        env = self._load_envelope(rid, verify=True)
                    except Exception as exc:
                        # Corrupt/forged/stale-schema records mark the store
                        # degraded and are surfaced in the recovery report;
                        # recovery itself completes (fail closed, not crash).
                        self._degraded = True
                        scan.append((rid, None, type(exc).__name__))
                        continue
                    if env is None:
                        # rid came from the on-disk glob — files existed but
                        # neither side parsed: corrupted on both sides.
                        self._degraded = True
                        scan.append((rid, None, "UnrecoverableCustodyError"))
                        continue
                    try:
                        payload = b64d(env.payload_b64)
                    except Exception:
                        self._degraded = True
                        scan.append((rid, None, "PayloadDecodeError"))
                        continue
                    self._bytes_used += len(payload)
                    self._record_count += 1
                    if env.idempotency_key:
                        self._idempotency[env.idempotency_key] = env.record_id
                    scan.append(
                        (
                            rid,
                            env.meta if isinstance(env.meta, dict) else {},
                            None,
                        )
                    )
                self._recovery_report = build_recovery_report(
                    scan, journal_rows=list(self.journal.iter_rows())
                )
                self._ready = True
                self.telemetry.incr("recover_ok")
                self._append_event(
                    CustodyEvent(
                        event_type="recover",
                        record_id="*",
                        generation=0,
                        ts=time.time(),
                        note=f"records={self._record_count}",
                        tenant=self.tenant,
                    )
                )

    def _load_raw_sides(self, record_id: str) -> tuple[Optional[dict], Optional[dict]]:
        return (
            _read_json(self._primary_path(record_id)),
            _read_json(self._replica_path(record_id)),
        )

    def _validate_dict(self, data: dict[str, Any]) -> CustodyEnvelope:
        fmt = int(data.get("format_version", THESEUS_FORMAT_VERSION))
        if fmt != THESEUS_FORMAT_VERSION:
            raise SchemaVersionError(f"unsupported format_version={fmt}")
        ovid_v = int(data.get("ovid_transform_version", OVID_TRANSFORM_V1))
        if ovid_v not in self.ovid.supported():
            raise SchemaVersionError(f"unknown ovid_transform_version={ovid_v}")
        env = CustodyEnvelope.from_dict(data)
        mac = env.mac
        if not mac_verify(self.hmac_key, env, mac, previous_keys=self.previous_hmac_keys):
            raise AuthenticityError(f"MAC verify failed for {env.record_id}")
        try:
            stored = b64d(env.payload_b64)
        except Exception as exc:
            raise UnrecoverableCustodyError(f"payload decode failed: {exc}") from exc
        # content_digest is always the *ingress* payload digest (pre-fold).
        # When Ovid fold is on, stored bytes are working-form; verify via unfold
        # and optional working_digest meta.
        if self.use_ovid_fold or (isinstance(env.meta, dict) and env.meta.get("ingress_digest")):
            wd = env.meta.get("working_digest") if isinstance(env.meta, dict) else None
            if wd and content_digest(stored) != wd:
                raise AuthenticityError(f"working-form digest mismatch for {env.record_id}")
            try:
                ingress = self.ovid.unfold(stored, env.ovid_transform_version)
            except Exception as exc:
                raise AuthenticityError(
                    f"working-form unfold failed for {env.record_id}: {exc}"
                ) from exc
            if content_digest(ingress) != env.content_digest:
                raise AuthenticityError(f"ingress content digest mismatch for {env.record_id}")
        else:
            if content_digest(stored) != env.content_digest:
                raise AuthenticityError(f"content digest mismatch for {env.record_id}")
        return env

    def _side_ok(self, data: Optional[dict]) -> bool:
        if not data:
            return False
        try:
            self._validate_dict(data)
            return True
        except (
            AuthenticityError,
            SchemaVersionError,
            UnrecoverableCustodyError,
            KeyError,
            TypeError,
            ValueError,
        ):
            return False

    def _load_envelope(self, record_id: str, verify: bool = True) -> Optional[CustodyEnvelope]:
        primary, replica = self._load_raw_sides(record_id)
        p_ok = self._side_ok(primary)
        r_ok = self._side_ok(replica)
        if p_ok and primary is not None:
            if not r_ok:
                # heal replica
                _atomic_write_json(self._replica_path(record_id), primary)
                self._degraded = False
                self.telemetry.incr("heal_replica")
            return self._validate_dict(primary) if verify else CustodyEnvelope.from_dict(primary)
        if r_ok and replica is not None:
            _atomic_write_json(self._primary_path(record_id), replica)
            self.telemetry.incr("heal_primary")
            return self._validate_dict(replica) if verify else CustodyEnvelope.from_dict(replica)
        if primary is None and replica is None:
            return None
        raise UnrecoverableCustodyError(f"all replicas bad for record_id={record_id}")

    def put(
        self,
        payload: bytes,
        *,
        record_id: Optional[str] = None,
        idempotency_key: str = "",
        meta: Optional[dict[str, Any]] = None,
    ) -> CustodyEnvelope:
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError("payload must be bytes")
        payload = bytes(payload)
        meta = dict(meta or {})
        meta.setdefault("written_ts", time.time())

        with self._lock:
            if not self._ready:
                raise RuntimeError("custody not ready")
            if self.read_only:
                raise ReadOnlyModeError("put rejected: read_only mode")
            # Chronus accel must not change digest path correctness.
            # Accel flag is recorded only; CPU digest is authoritative.
            if self.chronus_accel:
                self.telemetry.incr("chronus_accel_flag")
                # Authority: accel may not redefine custody digest.
            store_bytes = payload
            ovid_v = OVID_TRANSFORM_V1
            ingress_digest = content_digest(payload)
            if self.use_ovid_fold:
                store_bytes = self.ovid.fold(payload, OVID_TRANSFORM_V1)
                meta = dict(meta)
                meta.setdefault("ingress_digest", ingress_digest)
                meta.setdefault("working_digest", content_digest(store_bytes))

            self.quotas.check_payload(max(len(payload), len(store_bytes)))

            rid = record_id or str(uuid.uuid4())
            if idempotency_key:
                existing_id = self._idempotency.get(idempotency_key)
                if existing_id:
                    existing = self._load_envelope(existing_id)
                    if existing is not None:
                        if existing.content_digest == ingress_digest:
                            self.telemetry.incr("put_idempotent")
                            return existing
                        raise ConcurrencyConflict(
                            f"idempotency_key={idempotency_key} digest conflict"
                        )

            if not self.hook.before_put(self.tenant, rid, payload, meta):
                self.telemetry.incr("hook_deny")
                self._append_event(
                    CustodyEvent(
                        event_type="deny",
                        record_id=rid,
                        generation=0,
                        ts=time.time(),
                        note="before_put denied",
                        tenant=self.tenant,
                    )
                )
                raise AuthorityBoundaryError(f"security hook denied put for record_id={rid}")

            # generation
            prev = None
            try:
                prev = self._load_envelope(rid)
            except UnrecoverableCustodyError:
                prev = None
            generation = (prev.generation + 1) if prev else 1

            incoming = len(store_bytes)
            # If replacing, subtract old size roughly
            used = self._bytes_used
            if prev is not None:
                try:
                    used -= len(b64d(prev.payload_b64))
                except Exception:
                    pass
                records_after = self._record_count
            else:
                records_after = self._record_count + 1
            prev_meta = prev.meta if (prev is not None and isinstance(prev.meta, dict)) else {}
            meta.setdefault("created_ts", prev_meta.get("created_ts", meta["written_ts"]))
            self.quotas.check_records(records_after)
            self.quotas.check_tenant_bytes(max(used, 0), incoming)

            digest = ingress_digest
            env = CustodyEnvelope(
                record_id=rid,
                payload_b64=b64e(store_bytes),
                content_digest=digest,
                generation=generation,
                format_version=THESEUS_FORMAT_VERSION,
                ovid_transform_version=ovid_v,
                tenant=self.tenant,
                idempotency_key=idempotency_key or "",
                mac="",
                meta={**meta, "chronus_accel": self.chronus_accel},
            )
            env.mac = mac_create(self.hmac_key, env)
            data = env.to_dict()

            op_id = str(uuid.uuid4())
            with self._file_lock:
                self.journal.append_intent(
                    {
                        "op_id": op_id,
                        "op": "put",
                        "record_id": rid,
                        "generation": generation,
                        "content_digest": digest,
                    }
                )
                _atomic_write_json(self._primary_path(rid), data)
                _atomic_write_json(self._replica_path(rid), data)
                self.journal.seal(op_id, {"record_id": rid})

            if prev is None:
                self._record_count += 1
                self._bytes_used += incoming
            else:
                try:
                    self._bytes_used = self._bytes_used - len(b64d(prev.payload_b64)) + incoming
                except Exception:
                    self._bytes_used += incoming
            if idempotency_key:
                self._idempotency[idempotency_key] = rid

            self.telemetry.incr("put_ok")
            self._append_event(
                CustodyEvent(
                    event_type="put",
                    record_id=rid,
                    generation=generation,
                    ts=time.time(),
                    content_digest=digest,
                    tenant=self.tenant,
                )
            )
            try:
                self.hook.after_put(self.tenant, rid, data, meta)
            except Exception:
                self.telemetry.incr("hook_after_put_error")
            return env

    def _authorize_access(self, action: str, record_id: str, meta: Optional[dict] = None) -> None:
        """Enforce the supplied custody/access contract — fail closed.

        Order: explicit ``access_contract`` callable > hook
        ``before_get``/``before_delete`` > ``require_access_contract`` closed
        default. No supplied contract and no strict flag means access policy
        was never provided — allowed but declared ``none`` in health.
        """
        meta = dict(meta or {})
        hook_fn = getattr(self.hook, "before_get" if action == "get" else "before_delete", None)
        if self.access_contract is not None:
            decision = bool(self.access_contract(self.tenant, action, record_id, meta))
        elif hook_fn is not None:
            decision = bool(hook_fn(self.tenant, record_id, meta))
        elif self.require_access_contract:
            decision = False
        else:
            return
        if not decision:
            self.telemetry.incr(f"access_deny:{action}")
            self._append_event(
                CustodyEvent(
                    event_type="access_deny",
                    record_id=record_id,
                    generation=0,
                    ts=time.time(),
                    note=f"{action} denied",
                    tenant=self.tenant,
                )
            )
            raise AuthorityBoundaryError(
                f"{action} denied for record_id={record_id} by access contract"
            )

    def get(self, record_id: str, *, raw_folded: bool = False) -> bytes:
        with self._lock:
            # Access is authorized BEFORE any load/heal side effect: a stored
            # record does not create authority to access it.
            self._authorize_access("get", record_id)
            env = self._load_envelope(record_id)
            if env is None:
                raise KeyError(record_id)
            data = b64d(env.payload_b64)
            if self.use_ovid_fold and not raw_folded:
                data = self.ovid.unfold(data, env.ovid_transform_version)
            self.telemetry.incr("get_ok")
            after_get = getattr(self.hook, "after_get", None)
            if after_get is not None:
                try:
                    after_get(
                        self.tenant,
                        record_id,
                        env.meta if isinstance(env.meta, dict) else {},
                    )
                except Exception:
                    self.telemetry.incr("hook_after_get_error")
            return data

    def put_record(
        self,
        record: OperationalRecord,
        *,
        idempotency_key: str = "",
        meta: Optional[dict[str, Any]] = None,
    ) -> CustodyEnvelope:
        """Admit one producer OperationalRecord into durable custody.

        The record is contract-validated (registered producer, supported
        schema version, explicit evidence state, digest binding, verifiable
        dependencies) BEFORE the durable write — custody enforces contracts
        and fails closed; it never adjudicates record semantics.
        """
        try:
            record.validate(self.producer_registry, self.dependency_policy)
        except Exception:
            self.telemetry.incr("record_reject")
            raise
        merged = dict(meta or {})
        merged["op_record"] = record.manifest()
        return self.put(
            record.payload,
            record_id=record.record_id,
            idempotency_key=idempotency_key,
            meta=merged,
        )

    def get_record(self, record_id: str) -> OperationalRecord:
        """Read back an OperationalRecord (manifest + payload) from custody."""
        with self._lock:
            self._authorize_access("get", record_id)
            env = self._load_envelope(record_id)
            if env is None:
                raise KeyError(record_id)
            data = b64d(env.payload_b64)
            if self.use_ovid_fold:
                data = self.ovid.unfold(data, env.ovid_transform_version)
            manifest = env.meta.get("op_record") if isinstance(env.meta, dict) else None
            if not isinstance(manifest, dict):
                raise KeyError(f"record_id={record_id} has no operational manifest")
            self.telemetry.incr("get_record_ok")
            return OperationalRecord(
                record_id=str(manifest.get("record_id", record_id)),
                producer=str(manifest.get("producer", "")),
                producer_version=str(manifest.get("producer_version", "")),
                schema_version=int(manifest.get("schema_version", 1)),
                kind=str(manifest.get("kind", "")),
                payload=data,
                content_digest=str(manifest.get("content_digest", "")),
                evidence_state=str(manifest.get("evidence_state", "MISSING")),
                timestamp=float(manifest.get("timestamp", 0.0)),
                sequence=int(manifest.get("sequence", 0)),
                epoch=str(manifest.get("epoch", "")),
                lineage=tuple(manifest.get("lineage") or ()),
                correlation_ids=dict(manifest.get("correlation_ids") or {}),
                dependencies=dict(manifest.get("dependencies") or {}),
                meta=dict(manifest.get("meta") or {}),
            )

    def delete(self, record_id: str) -> None:
        with self._lock:
            if self.read_only:
                raise ReadOnlyModeError("delete rejected: read_only mode")
            self._authorize_access("delete", record_id)
            env = None
            try:
                env = self._load_envelope(record_id)
            except UnrecoverableCustodyError:
                env = None
            op_id = str(uuid.uuid4())
            with self._file_lock:
                self.journal.append_intent({"op_id": op_id, "op": "delete", "record_id": record_id})
                for p in (self._primary_path(record_id), self._replica_path(record_id)):
                    if p.exists():
                        p.unlink()
                self.journal.seal(op_id, {"record_id": record_id})
            if env is not None:
                try:
                    self._bytes_used = max(0, self._bytes_used - len(b64d(env.payload_b64)))
                except Exception:
                    pass
                self._record_count = max(0, self._record_count - 1)
                if env.idempotency_key and self._idempotency.get(env.idempotency_key) == record_id:
                    del self._idempotency[env.idempotency_key]
            self.telemetry.incr("delete_ok")
            self._append_event(
                CustodyEvent(
                    event_type="delete",
                    record_id=record_id,
                    generation=env.generation if env else 0,
                    ts=time.time(),
                    tenant=self.tenant,
                )
            )

    def heal(self, record_id: Optional[str] = None) -> dict[str, Any]:
        with self._lock:
            ids: list[str]
            if record_id:
                ids = [record_id]
            else:
                ids = sorted(
                    {p.stem for p in self.primary_dir.glob("*.json")}
                    | {p.stem for p in self.replica_dir.glob("*.json")}
                )
            healed = []
            failed = []
            for rid in ids:
                try:
                    env = self._load_envelope(rid)
                    if env is None:
                        failed.append(rid)
                        continue
                    healed.append(rid)
                    detail = {"generation": env.generation, "digest": env.content_digest}
                    self.telemetry.incr("heal_ok")
                    self._append_event(
                        CustodyEvent(
                            event_type="heal",
                            record_id=rid,
                            generation=env.generation,
                            ts=time.time(),
                            content_digest=env.content_digest,
                            tenant=self.tenant,
                        )
                    )
                    try:
                        self.hook.after_heal(self.tenant, rid, detail)
                    except Exception:
                        pass
                except UnrecoverableCustodyError:
                    failed.append(rid)
                    self.telemetry.incr("heal_fail")
            if record_id and failed and not healed:
                raise UnrecoverableCustodyError(f"all replicas bad for record_id={record_id}")
            return {"healed": healed, "failed": failed}

    def corrupt_for_test(self, record_id: str, *, side: str = "replica") -> None:
        """Test helper: corrupt primary or replica bytes."""
        path = self._replica_path(record_id) if side == "replica" else self._primary_path(record_id)
        if not path.exists():
            raise FileNotFoundError(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        # Flip digest to break integrity while leaving structure.
        dig = data.get("content_digest", "")
        data["content_digest"] = ("0" if not dig.startswith("0") else "1") + dig[1:]
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self.telemetry.incr("corrupt_for_test")

    def corrupt_mac_for_test(self, record_id: str, *, side: str = "primary") -> None:
        path = self._primary_path(record_id) if side == "primary" else self._replica_path(record_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        mac = data.get("mac", "")
        data["mac"] = ("f" if not mac.startswith("f") else "0") + mac[1:]
        # Corrupt both sides for MAC reject tests when needed.
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @staticmethod
    def _ignore_lock_files(directory: str, names: list[str]) -> set[str]:
        """Skip advisory lock files that may be held open (esp. Windows)."""
        return {n for n in names if n.endswith(".lock") or n == "custody.lock"}

    def backup(self, dest: Path | str) -> Path:
        dest_p = Path(dest)
        if dest_p.exists():
            shutil.rmtree(dest_p)
        with self._lock:
            # Do not hold FileLock across copytree — Windows cannot copy locked files.
            shutil.copytree(
                self.tenant_root,
                dest_p,
                ignore=self._ignore_lock_files,
            )
        self.telemetry.incr("backup_ok")
        self._append_event(
            CustodyEvent(
                event_type="backup",
                record_id="*",
                generation=0,
                ts=time.time(),
                note=str(dest_p),
                tenant=self.tenant,
            )
        )
        return dest_p

    def restore(self, src: Path | str) -> None:
        if self.read_only:
            raise ReadOnlyModeError("restore rejected: read_only mode")
        src_p = Path(src)
        if not src_p.exists():
            raise FileNotFoundError(src_p)
        with self._lock:
            # Replace durable dirs; leave lock files alone.
            for name in ("primary", "replica", "journal", "provenance", "meta.json"):
                target = self.tenant_root / name
                if target.is_dir():
                    shutil.rmtree(target)
                elif target.is_file():
                    target.unlink()
            for child in src_p.iterdir():
                if child.name.endswith(".lock") or child.name == "custody.lock":
                    continue
                target = self.tenant_root / child.name
                if child.is_dir():
                    if target.exists():
                        shutil.rmtree(target)
                    shutil.copytree(child, target, ignore=self._ignore_lock_files)
                else:
                    shutil.copy2(child, target)
            self.journal = WriteAheadJournal(self.journal_path)
            self.recover()
        self.telemetry.incr("restore_ok")
        self._append_event(
            CustodyEvent(
                event_type="restore",
                record_id="*",
                generation=0,
                ts=time.time(),
                note=str(src_p),
                tenant=self.tenant,
            )
        )

    def provenance(self, record_id: Optional[str] = None) -> list[dict[str, Any]]:
        with self._lock:
            out = []
            for ev in self._events:
                if record_id is None or ev.record_id == record_id or ev.record_id == "*":
                    out.append(ev.to_dict())
            return out

    # -- record inventory --------------------------------------------------

    def list_records(self) -> list[dict[str, Any]]:
        """Verified inventory of all records (integrity-checked read of meta).

        Each entry carries record_id, generation, content_digest, tenant,
        written_ts plus producer/kind/evidence_state when the record holds an
        operational manifest. Unrecoverable records are skipped — they are
        surfaced through ``recovery_report`` instead.
        """
        with self._lock:
            out: list[dict[str, Any]] = []
            ids = sorted(
                {p.stem for p in self.primary_dir.glob("*.json")}
                | {p.stem for p in self.replica_dir.glob("*.json")}
            )
            for rid in ids:
                try:
                    env = self._load_envelope(rid)
                except Exception:
                    continue
                if env is None:
                    continue
                meta = env.meta if isinstance(env.meta, dict) else {}
                op = meta.get("op_record")
                op = op if isinstance(op, dict) else {}
                out.append(
                    {
                        "record_id": env.record_id,
                        "generation": env.generation,
                        "content_digest": env.content_digest,
                        "tenant": env.tenant,
                        "written_ts": meta.get("written_ts"),
                        "created_ts": meta.get("created_ts"),
                        "producer": op.get("producer", "unknown"),
                        "kind": op.get("kind", ""),
                        "evidence_state": op.get("evidence_state", "MISSING"),
                    }
                )
            return out

    # -- retention -----------------------------------------------------------

    def enforce_retention(self, *, now: Optional[float] = None) -> dict[str, Any]:
        """Apply the declared RetentionPolicy via journaled deletes.

        Eviction is deterministic (oldest write first, id tiebreak); every
        delete goes through the normal WAL + provenance path.
        """
        with self._lock:
            if self.read_only:
                raise ReadOnlyModeError("retention rejected: read_only mode")
            if self.retention is None or not self.retention.bounded:
                return {
                    "evict": [],
                    "kept": self._record_count,
                    "reasons": {},
                }
            report = self.retention.evaluate(self.list_records(), now=now)
            for rid in report["evict"]:
                try:
                    self.delete(rid)
                    self.telemetry.incr("retention_evict")
                except Exception:
                    self.telemetry.incr("retention_evict_fail")
            self.telemetry.incr("retention_sweep")
            self._append_event(
                CustodyEvent(
                    event_type="retention",
                    record_id="*",
                    generation=0,
                    ts=time.time(),
                    note=f"evicted={len(report['evict'])}",
                    tenant=self.tenant,
                )
            )
            return report

    # -- checkpoints / rollback ------------------------------------------------

    def checkpoint(self, label: str = "") -> dict[str, Any]:
        """Create an integrity-verified checkpoint of current custody state."""
        with self._lock:
            records = [
                {
                    "record_id": r["record_id"],
                    "generation": r["generation"],
                    "content_digest": r["content_digest"],
                }
                for r in self.list_records()
            ]
            with self._file_lock:
                out = self.checkpoints.create(
                    key=self.hmac_key,
                    records=records,
                    tenant=self.tenant,
                    label=label,
                )
            self.telemetry.incr("checkpoint_ok")
            self._append_event(
                CustodyEvent(
                    event_type="checkpoint",
                    record_id="*",
                    generation=0,
                    ts=time.time(),
                    note=out["checkpoint_id"],
                    tenant=self.tenant,
                )
            )
            return out

    def verify_checkpoint(self, checkpoint_id: str) -> dict[str, Any]:
        """Verify a checkpoint's manifest MAC + file digests (PASS/FAIL)."""
        with self._lock:
            return self.checkpoints.verify(checkpoint_id, key=self.hmac_key)

    def rollback(self, checkpoint_id: str) -> None:
        """Restore custody to a verified checkpoint — fail closed.

        Refuses when the checkpoint is missing/interrupted
        (CheckpointUnavailableError) or fails verification
        (CheckpointIntegrityError); never rolls back unverified state.
        """
        with self._lock:
            if self.read_only:
                raise ReadOnlyModeError("rollback rejected: read_only mode")
            verdict = self.checkpoints.verify(checkpoint_id, key=self.hmac_key)
            if verdict["status"] != "PASS":
                raise CheckpointIntegrityError(
                    f"checkpoint {checkpoint_id} failed verification: " f"{verdict}"
                )
            self.restore(self.checkpoints.checkpoint_dir(checkpoint_id))
            self._append_event(
                CustodyEvent(
                    event_type="rollback",
                    record_id="*",
                    generation=0,
                    ts=time.time(),
                    note=checkpoint_id,
                    tenant=self.tenant,
                )
            )
            self.telemetry.incr("rollback_ok")

    def list_checkpoints(self) -> list[dict[str, Any]]:
        with self._lock:
            return self.checkpoints.list()

    # -- recovery report / semantic revalidation handoff ----------------------

    def recovery_report(self) -> dict[str, Any]:
        """Last recovery report: verified/unrecoverable records, journal state,
        and records pending semantic revalidation grouped by producer.

        THESEUS restores bytes and integrity; producing subsystems own
        meaning — every recovered record stays in ``pending_revalidation``
        until its producer calls ``semantic_revalidated``.
        """
        with self._lock:
            return self._recovery_report.to_dict()

    def pending_revalidation(self, producer: Optional[str] = None) -> dict[str, list[str]]:
        with self._lock:
            pending = self._recovery_report.pending_revalidation
            if producer is None:
                return {k: list(v) for k, v in pending.items()}
            return {producer: list(pending.get(producer, []))}

    def semantic_revalidated(self, record_id: str, *, verdict: str, producer: str = "") -> None:
        """Producer callback: record semantics revalidated post-recovery.

        Retires the record from ``pending_revalidation`` and appends a
        provenance event with the declared verdict. THESEUS records the
        verdict verbatim — it does not judge it.
        """
        with self._lock:
            for key in list(self._recovery_report.pending_revalidation):
                ids = self._recovery_report.pending_revalidation[key]
                if record_id in ids:
                    ids.remove(record_id)
                    if not ids:
                        del self._recovery_report.pending_revalidation[key]
            self._recovery_report.revalidated.append(record_id)
            self._append_event(
                CustodyEvent(
                    event_type="revalidation",
                    record_id=record_id,
                    generation=0,
                    ts=time.time(),
                    note=f"verdict={verdict} producer={producer}",
                    tenant=self.tenant,
                )
            )

    # -- deterministic replay --------------------------------------------------

    def verify_replay(self) -> dict[str, Any]:
        """Fold the sealed WAL into expected state and diff against the
        verified store. Deterministic: identical journal + store -> identical
        report."""
        with self._lock:
            expected = fold_journal_ops(self.journal.iter_rows())
            return verify_replay(expected, self.list_records())

    def replay(self, dest: "EnterpriseCustody") -> dict[str, Any]:
        """Replay this custody's sealed op stream into ``dest`` and verify the
        reconstructed digests match (deterministic recovery/DR path)."""
        with self._lock:
            return replay_into(self, dest)

    # -- custody evidence ------------------------------------------------------

    def custody_evidence(self, record_id: str) -> dict[str, Any]:
        """Complete custody evidence chain for one record.

        Explicit states only — integrity is PASS/FAIL/MISSING per side,
        MAC/authenticity is PASS or FAIL, never inferred.
        """
        with self._lock:
            primary, replica = self._load_raw_sides(record_id)
            p_ok = self._side_ok(primary)
            r_ok = self._side_ok(replica)
            env: Optional[CustodyEnvelope] = None
            integrity = "FAIL"
            try:
                env = self._load_envelope(record_id)
                integrity = "PASS" if env is not None else "MISSING"
            except UnrecoverableCustodyError:
                integrity = "FAIL"
            journal_ops = [
                row
                for row in self.journal.iter_rows()
                if str(row.get("record_id", "")) == record_id
            ]
            checkpoints_containing = []
            for entry in self.checkpoints.list():
                cdir = self.checkpoints.checkpoint_dir(entry["checkpoint_id"])
                manifest_path = cdir / "manifest.json"
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    if any(r.get("record_id") == record_id for r in manifest.get("records", [])):
                        checkpoints_containing.append(entry["checkpoint_id"])
                except (OSError, json.JSONDecodeError):
                    continue
            recovery_pending = any(
                record_id in ids for ids in self._recovery_report.pending_revalidation.values()
            )
            evidence: dict[str, Any] = {
                "record_id": record_id,
                "tenant": self.tenant,
                "integrity": integrity,
                "primary": "PASS" if p_ok else ("MISSING" if primary is None else "FAIL"),
                "replica": "PASS" if r_ok else ("MISSING" if replica is None else "FAIL"),
                "pending_semantic_revalidation": recovery_pending,
                "journal_ops": journal_ops,
                "provenance": self.provenance(record_id),
                "checkpoints": checkpoints_containing,
                "access_contract": (
                    "callable"
                    if self.access_contract is not None
                    else ("hook" if getattr(self.hook, "before_get", None) is not None else "none")
                ),
            }
            if env is not None:
                evidence["envelope"] = {
                    "record_id": env.record_id,
                    "generation": env.generation,
                    "content_digest": env.content_digest,
                    "format_version": env.format_version,
                    "ovid_transform_version": env.ovid_transform_version,
                    "mac_verified": "PASS",
                    "meta": env.meta,
                }
            return evidence

    def health(self) -> dict[str, Any]:
        status = "ok"
        if self.read_only:
            status = "read_only"
        elif self._degraded:
            status = "degraded"
        if not self._ready:
            status = "recovering"
        return {
            "key_id": self.key_id,
            "require_authenticity": self.require_authenticity,
            "status": status,
            "ready": self._ready,
            "degraded": self._degraded,
            "read_only": self.read_only,
            "tenant": self.tenant,
            "records": self._record_count,
            "bytes_used": self._bytes_used,
            "chronus_accel": self.chronus_accel,
            "chronus_required": False,
            "format_version": THESEUS_FORMAT_VERSION,
            "access_contract": (
                "callable"
                if self.access_contract is not None
                else ("hook" if getattr(self.hook, "before_get", None) is not None else "none")
            ),
            "require_access_contract": self.require_access_contract,
            "retention": (
                {
                    "max_age_seconds": self.retention.max_age_seconds,
                    "max_records": self.retention.max_records,
                }
                if self.retention is not None
                else None
            ),
            "recovery": {
                "records_verified": self._recovery_report.records_verified,
                "records_unrecoverable": len(self._recovery_report.records_unrecoverable),
                "pending_revalidation": sum(
                    len(v) for v in self._recovery_report.pending_revalidation.values()
                ),
            },
            "checkpoints": len(self.checkpoints.list()),
            "root": str(self.root),
        }

    def set_read_only(self, value: bool = True) -> None:
        self.read_only = bool(value)

    def close(self) -> None:
        """Flush journal state and mark not ready (stop path)."""
        with self._lock:
            self._ready = False
            self.telemetry.incr("close_ok")


# Alias
EnterpriseTheseus = EnterpriseCustody


def compose(
    root: Path | str,
    *,
    tenant: str = "default",
    hmac_key: Optional[bytes] = None,
    key_id: str = "k1",
    require_authenticity: bool = True,
    allow_insecure_dev_key: bool = False,
    previous_hmac_keys: Optional[list[bytes]] = None,
    quotas: Optional[Quotas] = None,
    hook: Optional[SecurityHook] = None,
    read_only: bool = False,
    chronus_accel: bool = False,
    use_ovid_fold: bool = True,
    telemetry: Any = None,
    ovid: Any = None,
    **kwargs: Any,
) -> "EnterpriseCustody":
    """Factory: open enterprise custody under root (recovers journal first)."""
    return EnterpriseCustody(
        root,
        tenant=tenant,
        hmac_key=hmac_key,
        key_id=key_id,
        require_authenticity=require_authenticity,
        allow_insecure_dev_key=allow_insecure_dev_key,
        previous_hmac_keys=previous_hmac_keys,
        quotas=quotas,
        hook=hook,
        read_only=read_only,
        chronus_accel=chronus_accel,
        use_ovid_fold=use_ovid_fold,
        telemetry=telemetry,
        ovid=ovid,
        **kwargs,
    )


__all__ = [
    "EnterpriseCustody",
    "EnterpriseTheseus",
    "compose",
]
