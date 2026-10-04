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
import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any
from uuid import uuid4
from .abi import canonical_json, digest_json
from .attestation import extend_chain


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
    def __init__(self, root: str | os.PathLike[str], signing_key: bytes | None = None):
        self.root = Path(root)
        # Content-addressed artifacts live under the canonical `evidence/`
        # directory shared with durable memory persistence — the digest is
        # the filename, so artifact bytes hash back to their address.
        self.artifacts = self.root / "evidence"
        self.artifacts.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "evidence.sqlite3"
        self.signing_key = signing_key
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
            tmp.write_bytes(payload)
            os.replace(tmp, path)
            receipt_path.write_bytes(canonical_json({"algorithm": "hmac-sha256" if self.signing_key else "sha256-chain", "evidence_digest": digest, "chain": list(chain)}))
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
