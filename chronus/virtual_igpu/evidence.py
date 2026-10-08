"""Durable, queryable, content-addressed Chronus execution evidence ledger.

Trust model (explicit):
  * runtime_signed — content-addressed receipt + optional HMAC chain
  * device_observed — adapter completed events / device-bound observations
  * hardware_rooted — only when a real verified attestation mechanism supplies it
  * unavailable — missing observations; never invented

A content hash or runtime signature does **not** independently prove physical
GPU execution. PR #95-style checks are integrity checks and are extended here;
they alone do not establish hardware-rooted trust.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from .abi import ABI_VERSION, TrustClass, canonical_json, digest_json
from .attestation import extend_chain


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


LEDGER_LOCK_TIMEOUT_S = 30.0


@contextmanager
def _ledger_file_lock(path: Path, timeout_s: float = LEDGER_LOCK_TIMEOUT_S):
    """Exclusive inter-process lock held while the ledger is read or extended.

    Processes sharing a store must extend the chain from the on-disk head, not
    from the head they loaded earlier: two appenders working from a stale head
    fork the chain, and a forked ledger no longer loads. A lock that cannot be
    acquired within ``timeout_s`` fails the operation closed.
    """
    with path.open("a+b") as fh:
        deadline = time.monotonic() + timeout_s
        while True:
            try:
                _lock_first_byte(fh)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"evidence ledger lock is held: {path}") from None
                time.sleep(0.005)
        try:
            yield
        finally:
            _unlock_first_byte(fh)


def _lock_first_byte(fh) -> None:
    try:
        import fcntl
    except ModuleNotFoundError:
        import msvcrt

        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock_first_byte(fh) -> None:
    try:
        import fcntl
    except ModuleNotFoundError:
        import msvcrt

        fh.seek(0)
        try:
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
    else:
        fcntl.flock(fh, fcntl.LOCK_UN)


@dataclass
class EvidenceRecord:
    record_id: str
    workload_id: str
    adapter_id: str
    kind: str
    trust_class: str
    hardware_rooted: bool
    hardware_executed: bool
    wall_time_ns: int
    device_time_ns: int | None
    content_hash: str
    receipt: dict[str, Any]
    result: dict[str, Any]
    chain_prev: str
    chain_digest: str
    recorded_at: str = field(default_factory=_utc_now)
    hmac_hex: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "workload_id": self.workload_id,
            "adapter_id": self.adapter_id,
            "kind": self.kind,
            "trust_class": self.trust_class,
            "hardware_rooted": self.hardware_rooted,
            "hardware_executed": self.hardware_executed,
            "wall_time_ns": self.wall_time_ns,
            "device_time_ns": self.device_time_ns,
            "content_hash": self.content_hash,
            "receipt": self.receipt,
            "result": self.result,
            "chain_prev": self.chain_prev,
            "chain_digest": self.chain_digest,
            "recorded_at": self.recorded_at,
            "hmac_hex": self.hmac_hex,
            "metadata": self.metadata,
            "abi_version": ABI_VERSION,
        }


@dataclass(frozen=True)
class EvidenceReceipt:
    """Receipt for one content-addressed execution-evidence artifact."""

    execution_id: str
    digest: str
    path: str
    chain: tuple[str, ...]


ARTIFACT_SECTIONS = frozenset(
    {"workload", "planner", "substrate", "execution", "validation", "provenance"}
)


class EvidenceLedger:
    """Append-only, reloadable evidence store with independent validation."""

    def __init__(
        self,
        root: str | Path | None = None,
        signing_key: bytes | str | None = None,
        *,
        hmac_key: bytes | str | None = None,
    ) -> None:
        self.root = Path(root or os.getenv("CHRONUS_VIGPU_STORE", ".chronus-virtual-igpu"))
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "evidence_ledger.jsonl"
        self._lock_path = self.root / "evidence_ledger.lock"
        key = hmac_key if hmac_key is not None else signing_key
        if key is None:
            key = os.getenv("CHRONUS_VIGPU_HMAC_KEY")
        if isinstance(key, str):
            key = key.encode("utf-8")
        self.hmac_key: bytes | None = key
        self._lock = threading.RLock()
        self._last_chain = "genesis"
        self._records: list[EvidenceRecord] = []
        # Bytes of the ledger file already verified and adopted, and the line
        # count they hold, so records appended by other processes are verified
        # incrementally before this process extends the chain.
        self._offset = 0
        self._line_number = 0
        # Content-addressed artifacts live under the canonical `evidence/`
        # directory; the digest is the filename, so bytes hash to their address.
        self.artifacts = self.root / "evidence"
        self.db_path = self.root / "evidence.sqlite3"
        self._load()

    def _load(self) -> None:
        with _ledger_file_lock(self._lock_path):
            self._ingest()

    def _ingest(self) -> None:
        """Verify and adopt every record appended since this ledger last read.

        Callers hold the file lock, so no lock-respecting writer is mid-append.
        """
        if not self.path.exists():
            return
        with self.path.open("rb") as fh:
            fh.seek(self._offset)
            chunk = fh.read()
        if not chunk:
            return
        adopted: list[EvidenceRecord] = []
        expected_prev = self._last_chain
        line_number = self._line_number
        for line in chunk.decode("utf-8").splitlines():
            line_number += 1
            line = line.strip()
            if not line:
                continue
            rec = self._verify_line(line, line_number, expected_prev)
            adopted.append(rec)
            expected_prev = rec.chain_digest
        self._records.extend(adopted)
        self._last_chain = expected_prev
        self._line_number = line_number
        self._offset += len(chunk)

    def _verify_line(self, line: str, line_number: int, expected_prev: str) -> EvidenceRecord:
        try:
            data = json.loads(line)
            rec = EvidenceRecord(
                record_id=str(data["record_id"]),
                workload_id=str(data.get("workload_id", "")),
                adapter_id=str(data.get("adapter_id", "")),
                kind=str(data.get("kind", "")),
                trust_class=str(data.get("trust_class", TrustClass.RUNTIME_SIGNED.value)),
                hardware_rooted=bool(data.get("hardware_rooted", False)),
                hardware_executed=bool(data.get("hardware_executed", False)),
                wall_time_ns=int(data.get("wall_time_ns", 0)),
                device_time_ns=data.get("device_time_ns"),
                content_hash=str(data.get("content_hash", "")),
                receipt=dict(data.get("receipt", {})),
                result=dict(data.get("result", {})),
                chain_prev=str(data.get("chain_prev", "")),
                chain_digest=str(data.get("chain_digest", "")),
                recorded_at=str(data.get("recorded_at", _utc_now())),
                hmac_hex=data.get("hmac_hex"),
                metadata=dict(data.get("metadata", {})),
            )
        except Exception as exc:
            raise ValueError(
                f"invalid evidence ledger record at line {line_number}"
            ) from exc
        body = {
            "workload_id": rec.workload_id,
            "adapter_id": rec.adapter_id,
            "kind": rec.kind,
            "trust_class": rec.trust_class,
            "hardware_rooted": rec.hardware_rooted,
            "hardware_executed": rec.hardware_executed,
            "wall_time_ns": rec.wall_time_ns,
            "device_time_ns": rec.device_time_ns,
            "receipt": rec.receipt,
            "result": rec.result,
            "metadata": rec.metadata,
            "chain_prev": rec.chain_prev,
        }
        expected_hash = digest_json(body)
        expected_chain = hashlib.sha256(
            f"{expected_prev}:{expected_hash}".encode("utf-8")
        ).hexdigest()
        if rec.chain_prev != expected_prev:
            raise ValueError(
                f"evidence chain predecessor mismatch at line {line_number}"
            )
        if rec.content_hash != expected_hash:
            raise ValueError(
                f"evidence content hash mismatch at line {line_number}"
            )
        if rec.chain_digest != expected_chain:
            raise ValueError(
                f"evidence chain digest mismatch at line {line_number}"
            )
        if rec.hmac_hex is not None:
            if self.hmac_key is None:
                raise ValueError(
                    "evidence ledger requires its configured HMAC key"
                )
            expected_hmac = hmac.new(
                self.hmac_key,
                rec.content_hash.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(expected_hmac, rec.hmac_hex):
                raise ValueError(
                    f"evidence HMAC mismatch at line {line_number}"
                )
        return rec

    def append(
        self,
        artifact: Mapping[str, Any] | None = None,
        /,
        *,
        workload_id: str | None = None,
        adapter_id: str | None = None,
        kind: str | None = None,
        result: Mapping[str, Any] | None = None,
        receipt: Mapping[str, Any] | None = None,
        result_dict: Mapping[str, Any] | None = None,
        receipt_dict: Mapping[str, Any] | None = None,
        trust_class: str | TrustClass = TrustClass.RUNTIME_SIGNED,
        hardware_rooted: bool = False,
        wall_time_ns: int | None = None,
        device_time_ns: int | None = None,
        metadata: Mapping[str, Any] | None = None,
        **_extra: Any,
    ) -> EvidenceRecord | EvidenceReceipt:
        """Append a runtime record (keywords) or, given one positional mapping
        carrying every ``ARTIFACT_SECTIONS`` key, a content-addressed artifact."""
        if artifact is not None:
            return self._append_artifact(artifact)
        with self._lock, _ledger_file_lock(self._lock_path):
            self._ingest()
            res = dict(result_dict or result or {})
            rcpt = dict(receipt_dict or receipt or {})
            wid = str(workload_id or res.get("workload_id") or rcpt.get("workload_id") or "")
            aid = str(adapter_id or res.get("adapter_id") or res.get("actual_adapter_id") or "")
            k = str(kind or res.get("kind") or rcpt.get("kind") or "")
            tc = trust_class.value if isinstance(trust_class, TrustClass) else str(trust_class)
            hw_rooted = bool(hardware_rooted or res.get("hardware_rooted") or rcpt.get("hardware_rooted"))
            if tc == TrustClass.HARDWARE_ROOTED.value and not hw_rooted:
                tc = TrustClass.DEVICE_OBSERVED.value

            wns = int(wall_time_ns if wall_time_ns is not None else res.get("wall_time_ns") or 0)
            dns = device_time_ns if device_time_ns is not None else res.get("device_time_ns")
            hardware_executed = bool(res.get("hardware_executed") or rcpt.get("hardware_executed"))
            if "software" in str(aid).lower() or "cpu" in str(aid).lower() or "emulator" in str(aid).lower():
                hardware_executed = bool(res.get("hardware_executed", False))

            body = {
                "workload_id": wid,
                "adapter_id": aid,
                "kind": k,
                "trust_class": tc,
                "hardware_rooted": hw_rooted,
                "hardware_executed": hardware_executed,
                "wall_time_ns": wns,
                "device_time_ns": dns,
                "receipt": rcpt,
                "result": res,
                "metadata": dict(metadata or {}),
                "chain_prev": self._last_chain,
            }
            content_hash = digest_json(body)
            body["content_hash"] = content_hash
            chain_digest = hashlib.sha256(
                f"{self._last_chain}:{content_hash}".encode("utf-8")
            ).hexdigest()
            record_id = content_hash[:32]
            hmac_hex = None
            if self.hmac_key:
                hmac_hex = hmac.new(
                    self.hmac_key, content_hash.encode("utf-8"), hashlib.sha256
                ).hexdigest()

            rec = EvidenceRecord(
                record_id=record_id,
                workload_id=wid,
                adapter_id=aid,
                kind=k,
                trust_class=tc,
                hardware_rooted=hw_rooted,
                hardware_executed=hardware_executed,
                wall_time_ns=wns,
                device_time_ns=dns if dns is None else int(dns),
                content_hash=content_hash,
                receipt=rcpt,
                result=res,
                chain_prev=self._last_chain,
                chain_digest=chain_digest,
                hmac_hex=hmac_hex,
                metadata=dict(metadata or {}),
            )
            line = json.dumps(rec.as_dict(), sort_keys=True, default=str)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
            self._offset = self.path.stat().st_size
            self._line_number += 1
            self._records.append(rec)
            self._last_chain = chain_digest
            return rec

    def _connect(self) -> sqlite3.Connection:
        self.artifacts.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.db_path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("""CREATE TABLE IF NOT EXISTS executions(
            execution_id TEXT PRIMARY KEY, digest TEXT UNIQUE NOT NULL,
            workload_id TEXT NOT NULL, tenant TEXT NOT NULL,
            operation TEXT NOT NULL, adapter_id TEXT NOT NULL,
            status TEXT NOT NULL, wall_time_ns INTEGER,
            device_time_ns INTEGER, created_at TEXT NOT NULL,
            artifact_path TEXT NOT NULL, chain_head TEXT NOT NULL
        )""")
        return db

    def _append_artifact(self, record: Mapping[str, Any]) -> EvidenceReceipt:
        missing = sorted(ARTIFACT_SECTIONS - set(record))
        self.artifacts.mkdir(parents=True, exist_ok=True)
        if missing:
            raise ValueError(f"evidence missing sections: {missing}")
        complete = dict(record)
        complete.setdefault("schema", "chronus.execution-evidence.v2")
        complete.setdefault("execution_id", str(uuid4()))
        complete.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        digest = digest_json(complete)
        chain = extend_chain((), {"execution_digest": digest}, self.hmac_key)
        # The primary artifact is exactly the canonical bytes named by its digest.
        # Authentication is a detached receipt to avoid a circular self-hash.
        payload = canonical_json(complete).encode("utf-8")
        path = self.artifacts / f"{digest}.json"
        receipt_path = self.artifacts / f"{digest}.attestation.json"
        tmp = path.with_suffix(".tmp")
        with self._lock:
            tmp.write_bytes(payload)
            os.replace(tmp, path)
            receipt_path.write_text(canonical_json({"algorithm": "hmac-sha256" if self.hmac_key else "sha256-chain", "evidence_digest": digest, "chain": list(chain)}), encoding="utf-8")
            w, e, s, v = complete["workload"], complete["execution"], complete["substrate"], complete["validation"]
            if e.get("hardware_executed") is True and not v.get("passed"):
                path.unlink(missing_ok=True)
                raise ValueError("hardware result cannot be committed without validation")
            with self._connect() as db:
                db.execute("INSERT INTO executions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (
                    complete["execution_id"], digest, str(w.get("id", "")), str(w.get("tenant", "")),
                    str(w.get("operation", "")), str(s.get("adapter_id", s.get("backend", ""))),
                    str(e.get("status", "ok")), e.get("wall_time_ns"), e.get("device_time_ns"),
                    complete["created_at"], str(path), chain[-1]))
        return EvidenceReceipt(complete["execution_id"], digest, str(path), chain)

    def query(self, *, operation: str | None = None, adapter_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        where, args = [], []
        if operation:
            where.append("operation=?")
            args.append(operation)
        if adapter_id:
            where.append("adapter_id=?")
            args.append(adapter_id)
        sql = "SELECT * FROM executions" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY created_at DESC LIMIT ?"
        args.append(max(1, min(int(limit), 1000)))
        with self._connect() as db:
            return [dict(row) for row in db.execute(sql, args)]

    def get(self, digest: str) -> dict[str, Any]:
        path = self.artifacts / f"{digest}.json"
        data = json.loads(path.read_text())
        if digest_json(data) != digest:
            raise ValueError("evidence digest mismatch")
        receipt_path = self.artifacts / f"{digest}.attestation.json"
        data["attestation"] = json.loads(receipt_path.read_text())
        return data

    def list_records(self) -> list[EvidenceRecord]:
        with self._lock:
            return list(self._records)

    def reload(self) -> None:
        with self._lock:
            self._records.clear()
            self._last_chain = "genesis"
            self._offset = 0
            self._line_number = 0
            self._load()


def _extract_views(artifact: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Normalize acceptance-test and elevation receipt shapes."""
    art = dict(artifact)
    result = dict(art.get("result") or {})
    provenance = dict(art.get("provenance") or art.get("receipt") or {})
    # Flatten single-level receipt documents
    if not result and any(k in art for k in ("trust_class", "hardware_rooted", "actual_backend")):
        result = {
            k: art[k]
            for k in (
                "trust_class",
                "hardware_rooted",
                "actual_backend",
                "adapter_id",
                "verification",
                "timing",
            )
            if k in art
        }
    return art, result, provenance


BINDABLE_RECEIPT_FIELDS = frozenset(
    {
        "protocol_version",
        "package_version",
        "runtime_identity",
        "build_identity",
        "kernel_identity",
        "workload_id",
        "attempt_id",
        "requested_policy",
        "actual_backend",
        "actual_device",
        "input_digest",
        "output_digest",
        "verified_work_count",
        "delivery_mode",
    }
)


def validate_receipt(
    receipt: Mapping[str, Any] | None = None,
    *,
    result: Mapping[str, Any] | None = None,
    expected_runtime: str | None = None,
    expected_kernel: str | None = None,
    expected_package: str | None = None,
    allow_hardware_rooted: bool = False,
    expect_hardware_rooted: bool | None = None,
    hmac_key: bytes | None = None,
    record: Mapping[str, Any] | None = None,
    expect: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Independent receipt validator.

    ``expect`` binds any of ``BINDABLE_RECEIPT_FIELDS`` (protocol/package/runtime/
    build/kernel identity, workload/attempt id, requested policy, actual backend and
    device, input/output digests, verified work count, delivery mode). A bound field
    that is absent or different fails validation; a generic content hash alone is
    never enough to accept a changed execution identity.

    Acceptance-suite contract:
      * validate_receipt(artifact_dict) → {"ok": bool, ...}
      * raises ValueError when hardware_rooted is claimed for CPU/software backend
      * expect_hardware_rooted=True raises if receipt is not hardware-rooted
    """
    artifact = dict(record or receipt or {})
    if result is not None and "result" not in artifact:
        artifact = {**artifact, "result": dict(result)}

    art, res, prov = _extract_views(artifact)

    trust = str(
        res.get("trust_class")
        or prov.get("trust_class")
        or art.get("trust_class")
        or TrustClass.UNAVAILABLE.value
    )
    hw_rooted = bool(
        res.get("hardware_rooted")
        or prov.get("hardware_rooted")
        or art.get("hardware_rooted")
        or (res.get("verification") or {}).get("hardware_rooted")
    )
    backend = str(
        res.get("actual_backend")
        or res.get("adapter_id")
        or art.get("actual_backend")
        or art.get("adapter_id")
        or ""
    ).lower()
    softwareish = any(tok in backend for tok in ("software", "cpu", "emulator"))

    report: dict[str, Any] = {
        "ok": True,
        "errors": [],
        "warnings": [],
        "trust_class": trust,
        "hardware_rooted": hw_rooted,
        "integrity": "unknown",
    }

    # CPU/software cannot claim hardware-rooted
    if hw_rooted and softwareish:
        raise ValueError(
            f"hardware_rooted claim invalid for software/CPU backend {backend!r}"
        )
    if trust == TrustClass.HARDWARE_ROOTED.value and softwareish:
        raise ValueError(
            f"trust_class=hardware_rooted invalid for software/CPU backend {backend!r}"
        )

    if expect_hardware_rooted is True and not hw_rooted:
        raise ValueError("expected hardware_rooted receipt but hardware_rooted is false")
    if expect_hardware_rooted is True and softwareish:
        raise ValueError("expected hardware_rooted but backend is software/CPU")

    if hw_rooted and not allow_hardware_rooted and expect_hardware_rooted is not True:
        # Soft error in report form when not raising
        report["errors"].append(
            "hardware_rooted=true but no verified attestation mechanism configured"
        )

    # timing presence (acceptance uses wall_ms)
    timing = res.get("timing") or art.get("timing") or {}
    wall_ns = int(res.get("wall_time_ns") or 0)
    wall_ms = float(timing.get("wall_ms") or 0.0)
    if wall_ns <= 0 and wall_ms <= 0:
        report["warnings"].append("missing or non-positive wall time")

    # digest consistency if present
    digest = art.get("digest") or art.get("content_hash")
    if digest:
        body = {k: v for k, v in art.items() if k not in {"digest", "content_hash", "hmac_hex"}}
        recomputed = digest_json(body)
        if recomputed == digest:
            report["integrity"] = "content_hash_consistent_unkeyed"
            report["warnings"].append(
                "unkeyed content hash cannot authenticate adversarial edit+rehash"
            )
        else:
            report["errors"].append("digest mismatch")
            report["integrity"] = "digest_mismatch"

    actual_runtime = art.get("runtime_identity") or prov.get("runtime_identity")
    actual_kernel = art.get("kernel_identity") or prov.get("kernel_identity")
    actual_package = art.get("package_version") or prov.get("package_version")
    if expected_runtime and actual_runtime != expected_runtime:
        if actual_runtime != expected_runtime:
            report["errors"].append("runtime_identity mismatch")
    if expected_kernel and actual_kernel != expected_kernel:
        report["errors"].append("kernel_identity mismatch")
    if expected_package and actual_package != expected_package:
        report["errors"].append("package_version mismatch")

    binding_errors: list[str] = []
    for field_name, wanted in (expect or {}).items():
        if field_name not in BINDABLE_RECEIPT_FIELDS:
            raise ValueError(f"unsupported receipt binding: {field_name!r}")
        actual = art[field_name] if field_name in art else prov.get(field_name)
        if actual is None:
            binding_errors.append(f"{field_name} missing")
        elif actual != wanted:
            binding_errors.append(f"{field_name} mismatch")
    report["errors"].extend(binding_errors)

    if hmac_key and art.get("hmac_hex"):
        expected = hmac.new(
            hmac_key, str(digest or "").encode("utf-8"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, str(art.get("hmac_hex"))):
            report["errors"].append("HMAC mismatch")
        else:
            report["integrity"] = "hmac_ok"

    if report["errors"] and expect_hardware_rooted is None and not (
        hw_rooted and softwareish
    ):
        # only mark not-ok for hard integrity errors when not using raise path
        hard = [
            e
            for e in report["errors"]
            if any(
                token in e
                for token in (
                    "digest",
                    "HMAC",
                    "runtime",
                    "kernel",
                    "package",
                )
            )
        ]
        if hard:
            report["ok"] = False
        # hardware_rooted without mechanism stays ok=False only if strict
        if any("hardware_rooted=true" in e for e in report["errors"]):
            # keep ok True for runtime_signed_ok tests that don't claim rooted
            if hw_rooted:
                report["ok"] = False

    # Good runtime_signed software receipts should be ok
    if (
        trust == TrustClass.RUNTIME_SIGNED.value
        and not hw_rooted
        and not report.get("errors")
    ):
        report["ok"] = True
    if trust == TrustClass.RUNTIME_SIGNED.value and not hw_rooted:
        # strip soft hardware_rooted config errors if any slipped in
        report["errors"] = [e for e in report["errors"] if "hardware_rooted=true" not in e]
        if not report["errors"]:
            report["ok"] = True

    if binding_errors:
        report["ok"] = False
    return report


def validate_evidence_artifact(artifact: Mapping[str, Any], **kwargs: Any) -> dict[str, Any]:
    return validate_receipt(artifact, **kwargs)


def validate_ledger_record(record: Mapping[str, Any], **kwargs: Any) -> dict[str, Any]:
    return validate_receipt(record=record, **kwargs)


__all__ = [
    "EvidenceLedger",
    "EvidenceRecord",
    "validate_receipt",
    "validate_ledger_record",
    "validate_evidence_artifact",
]
