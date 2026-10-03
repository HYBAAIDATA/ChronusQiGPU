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
    ResourceExhausted,
    SchemaVersionError,
    UnrecoverableCustodyError,
)
from .authenticity import (
    content_digest,
    is_insecure_dev_key,
    mac_create,
    mac_verify,
)
from .governance import Quotas
from .hooks import AllowAllHook, SecurityHook
from .journal import FileLock, WriteAheadJournal
from .ovid_registry import DEFAULT_OVID_REGISTRY, OvidRegistry, b64d, b64e
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

        self._lock = threading.RLock()
        self.tenant_root = self.root / "tenants" / self._safe_tenant(tenant)
        self.primary_dir = self.tenant_root / "primary"
        self.replica_dir = self.tenant_root / "replica"
        self.journal_path = self.tenant_root / "journal" / "wal.jsonl"
        self.events_path = self.tenant_root / "provenance" / "events.jsonl"
        self.meta_path = self.tenant_root / "meta.json"
        self._file_lock = FileLock(self.tenant_root / "custody.lock")

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
                for rid in sorted(ids):
                    try:
                        env = self._load_envelope(rid, verify=True)
                    except UnrecoverableCustodyError:
                        self._degraded = True
                        continue
                    except AuthenticityError:
                        self._degraded = True
                        continue
                    except SchemaVersionError:
                        self._degraded = True
                        continue
                    if env is None:
                        continue
                    try:
                        payload = b64d(env.payload_b64)
                    except Exception:
                        self._degraded = True
                        continue
                    self._bytes_used += len(payload)
                    self._record_count += 1
                    if env.idempotency_key:
                        self._idempotency[env.idempotency_key] = env.record_id
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
        if self.use_ovid_fold or (
            isinstance(env.meta, dict) and env.meta.get("ingress_digest")
        ):
            wd = env.meta.get("working_digest") if isinstance(env.meta, dict) else None
            if wd and content_digest(stored) != wd:
                raise AuthenticityError(
                    f"working-form digest mismatch for {env.record_id}"
                )
            try:
                ingress = self.ovid.unfold(stored, env.ovid_transform_version)
            except Exception as exc:
                raise AuthenticityError(
                    f"working-form unfold failed for {env.record_id}: {exc}"
                ) from exc
            if content_digest(ingress) != env.content_digest:
                raise AuthenticityError(
                    f"ingress content digest mismatch for {env.record_id}"
                )
        else:
            if content_digest(stored) != env.content_digest:
                raise AuthenticityError(
                    f"content digest mismatch for {env.record_id}"
                )
        return env

    def _side_ok(self, data: Optional[dict]) -> bool:
        if not data:
            return False
        try:
            self._validate_dict(data)
            return True
        except (AuthenticityError, SchemaVersionError, UnrecoverableCustodyError, KeyError, TypeError, ValueError):
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
        raise UnrecoverableCustodyError(
            f"all replicas bad for record_id={record_id}"
        )

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
                raise AuthorityBoundaryError(
                    f"security hook denied put for record_id={rid}"
                )

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

    def get(self, record_id: str, *, raw_folded: bool = False) -> bytes:
        with self._lock:
            env = self._load_envelope(record_id)
            if env is None:
                raise KeyError(record_id)
            data = b64d(env.payload_b64)
            if self.use_ovid_fold and not raw_folded:
                data = self.ovid.unfold(data, env.ovid_transform_version)
            self.telemetry.incr("get_ok")
            return data

    def delete(self, record_id: str) -> None:
        with self._lock:
            if self.read_only:
                raise ReadOnlyModeError("delete rejected: read_only mode")
            env = None
            try:
                env = self._load_envelope(record_id)
            except UnrecoverableCustodyError:
                env = None
            op_id = str(uuid.uuid4())
            with self._file_lock:
                self.journal.append_intent(
                    {"op_id": op_id, "op": "delete", "record_id": record_id}
                )
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
                raise UnrecoverableCustodyError(
                    f"all replicas bad for record_id={record_id}"
                )
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
