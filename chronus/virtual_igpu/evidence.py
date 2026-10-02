"""Durable, queryable, content-addressed Chronus execution evidence ledger."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import json, os, sqlite3, threading
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4
from .abi import canonical_json, digest_json
from .attestation import extend_chain


@dataclass(frozen=True)
class EvidenceReceipt:
    execution_id: str
    digest: str
    path: str
    chain: tuple[str, ...]


class EvidenceLedger:
    def __init__(self, root: str | os.PathLike[str], signing_key: bytes | None = None):
        self.root = Path(root)
        self.artifacts = self.root / "evidence-ledger"
        self.artifacts.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "evidence.sqlite3"
        self.signing_key = signing_key
        self._lock = threading.RLock()
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS executions(
                execution_id TEXT PRIMARY KEY, digest TEXT UNIQUE NOT NULL,
                workload_id TEXT NOT NULL, tenant TEXT NOT NULL,
                operation TEXT NOT NULL, adapter_id TEXT NOT NULL,
                status TEXT NOT NULL, wall_time_ns INTEGER,
                device_time_ns INTEGER, created_at TEXT NOT NULL,
                artifact_path TEXT NOT NULL, chain_head TEXT NOT NULL
            )""")

    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def append(self, record: dict[str, Any]) -> EvidenceReceipt:
        required = {"workload", "planner", "substrate", "execution", "validation", "provenance"}
        missing = sorted(required - set(record))
        if missing:
            raise ValueError(f"evidence missing sections: {missing}")
        complete = dict(record)
        complete.setdefault("schema", "chronus.execution-evidence.v2")
        complete.setdefault("execution_id", str(uuid4()))
        complete.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        digest = digest_json(complete)
        chain = extend_chain((), {"execution_digest": digest}, self.signing_key)
        artifact = {**complete, "attestation": {"algorithm": "hmac-sha256" if self.signing_key else "sha256-chain", "chain": list(chain)}}
        payload = canonical_json(artifact)
        path = self.artifacts / f"{digest}.json"
        tmp = path.with_suffix(".tmp")
        with self._lock:
            tmp.write_bytes(payload); os.replace(tmp, path)
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
        if operation: where.append("operation=?"); args.append(operation)
        if adapter_id: where.append("adapter_id=?"); args.append(adapter_id)
        sql = "SELECT * FROM executions" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY created_at DESC LIMIT ?"
        args.append(max(1, min(int(limit), 1000)))
        with self._connect() as db:
            return [dict(row) for row in db.execute(sql, args)]

    def get(self, digest: str) -> dict[str, Any]:
        path = self.artifacts / f"{digest}.json"
        data = json.loads(path.read_text())
        attestation = data.pop("attestation")
        if digest_json(data) != digest:
            raise ValueError("evidence digest mismatch")
        data["attestation"] = attestation
        return data
