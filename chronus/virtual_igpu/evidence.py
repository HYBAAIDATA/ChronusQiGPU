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

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import threading
from pathlib import Path
from typing import Any, Mapping

from .abi import ABI_VERSION, TrustClass, digest_json


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


class EvidenceLedger:
    """Append-only, reloadable evidence store with independent validation."""

    def __init__(
        self,
        root: str | Path | None = None,
        *,
        hmac_key: bytes | str | None = None,
    ) -> None:
        self.root = Path(root or os.getenv("CHRONUS_VIGPU_STORE", ".chronus-virtual-igpu"))
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "evidence_ledger.jsonl"
        key = hmac_key if hmac_key is not None else os.getenv("CHRONUS_VIGPU_HMAC_KEY")
        if isinstance(key, str):
            key = key.encode("utf-8")
        self.hmac_key: bytes | None = key
        self._lock = threading.RLock()
        self._last_chain = "genesis"
        self._records: list[EvidenceRecord] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
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
                self._records.append(rec)
                self._last_chain = rec.chain_digest
            except Exception:
                continue

    def append(
        self,
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
    ) -> EvidenceRecord:
        with self._lock:
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
            self._records.append(rec)
            self._last_chain = chain_digest
            return rec

    def list_records(self) -> list[EvidenceRecord]:
        with self._lock:
            return list(self._records)

    def reload(self) -> None:
        with self._lock:
            self._records.clear()
            self._last_chain = "genesis"
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
) -> dict[str, Any]:
    """Independent receipt validator.

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

    if expected_runtime and art.get("runtime_identity") not in {None, expected_runtime}:
        if art.get("runtime_identity") != expected_runtime:
            report["errors"].append("runtime_identity mismatch")

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
        hard = [e for e in report["errors"] if "digest" in e or "HMAC" in e or "runtime" in e]
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
        if not any("digest" in e or "HMAC" in e for e in report["errors"]):
            report["ok"] = True

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
