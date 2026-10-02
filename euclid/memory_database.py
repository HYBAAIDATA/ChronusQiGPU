"""Durable, scoped and tamper-evident EUCLID memory database.

SQLite is used as a local transactional store.  The database contains no
network path, no executable payloads and no semantic claim beyond persisted
records.  Encryption at rest is an operator/storage-layer responsibility;
startup reports this boundary explicitly.
"""
from __future__ import annotations

import json
import math
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contracts import RewardAuthority, canonical_json, domain_hash

SCHEMA_VERSION = 1
TIERS = frozenset({"working", "episodic", "semantic", "archival"})


@dataclass(frozen=True)
class MemoryScope:
    tenant_id: str
    mission_id: str
    domain: str

    def __post_init__(self) -> None:
        if not all((self.tenant_id.strip(), self.mission_id.strip(), self.domain.strip())):
            raise ValueError("memory scope fields must be non-empty")


@dataclass(frozen=True)
class MemoryRecord:
    memory_id: str
    scope: MemoryScope
    tier: str
    content: Mapping[str, Any]
    provenance: str
    reward_authority: RewardAuthority
    uncertainty: float
    replay_id: str
    created_at: float
    expires_at: float | None
    content_hash: str


class MemoryDatabase:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(
            str(self.path), timeout=15.0, isolation_level=None
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.execute("PRAGMA trusted_schema=OFF")
        self._migrate()
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "MemoryDatabase":
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    def _migrate(self) -> None:
        self._connection.executescript(
            """
            BEGIN IMMEDIATE;
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS memories (
                memory_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                mission_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                tier TEXT NOT NULL CHECK(tier IN ('working','episodic','semantic','archival')),
                content_json TEXT NOT NULL,
                provenance TEXT NOT NULL,
                reward_authority TEXT NOT NULL,
                uncertainty REAL NOT NULL CHECK(uncertainty >= 0 AND uncertainty <= 1),
                replay_id TEXT NOT NULL UNIQUE,
                created_at REAL NOT NULL,
                expires_at REAL,
                tombstoned INTEGER NOT NULL DEFAULT 0 CHECK(tombstoned IN (0,1)),
                content_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS memories_scope_idx
            ON memories(tenant_id, mission_id, domain, tier, created_at);
            CREATE TABLE IF NOT EXISTS memory_events (
                sequence INTEGER PRIMARY KEY,
                event_id TEXT NOT NULL UNIQUE,
                kind TEXT NOT NULL,
                memory_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                previous_hash TEXT,
                event_hash TEXT NOT NULL UNIQUE,
                created_at REAL NOT NULL,
                FOREIGN KEY(memory_id) REFERENCES memories(memory_id)
            );
            INSERT OR IGNORE INTO schema_migrations(version, applied_at)
            VALUES (1, CAST(strftime('%s','now') AS REAL));
            COMMIT;
            """
        )
        versions = [
            int(row[0])
            for row in self._connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            )
        ]
        if versions != list(range(1, SCHEMA_VERSION + 1)):
            raise RuntimeError("unsupported or discontinuous memory database schema")

    @staticmethod
    def _content_base(
        *,
        memory_id: str,
        scope: MemoryScope,
        tier: str,
        content: Mapping[str, Any],
        provenance: str,
        reward_authority: RewardAuthority,
        uncertainty: float,
        replay_id: str,
        created_at: float,
        expires_at: float | None,
    ) -> dict[str, Any]:
        return {
            "memory_id": memory_id,
            "tenant_id": scope.tenant_id,
            "mission_id": scope.mission_id,
            "domain": scope.domain,
            "tier": tier,
            "content": dict(content),
            "provenance": provenance,
            "reward_authority": reward_authority.value,
            "uncertainty": uncertainty,
            "replay_id": replay_id,
            "created_at": created_at,
            "expires_at": expires_at,
        }

    def put(
        self,
        *,
        scope: MemoryScope,
        tier: str,
        content: Mapping[str, Any],
        provenance: str,
        reward_authority: RewardAuthority,
        uncertainty: float,
        replay_id: str,
        memory_id: str | None = None,
        expires_at: float | None = None,
    ) -> MemoryRecord:
        if tier not in TIERS:
            raise ValueError("unsupported memory tier")
        if not provenance or not replay_id:
            raise ValueError("memory provenance and replay_id are required")
        if not math.isfinite(float(uncertainty)) or not 0 <= float(uncertainty) <= 1:
            raise ValueError("memory uncertainty must be finite and in [0,1]")
        canonical_json(content)  # reject non-serializable content before BEGIN
        created_at = time.time()
        if expires_at is not None and (
            not math.isfinite(float(expires_at)) or float(expires_at) <= created_at
        ):
            raise ValueError("expires_at must be a future finite timestamp")
        memory_id = memory_id or "memory-" + uuid.uuid4().hex
        base = self._content_base(
            memory_id=memory_id,
            scope=scope,
            tier=tier,
            content=content,
            provenance=provenance,
            reward_authority=reward_authority,
            uncertainty=float(uncertainty),
            replay_id=replay_id,
            created_at=created_at,
            expires_at=expires_at,
        )
        digest = domain_hash("euclid.memory.content.v1", base)
        content_json = canonical_json(content).decode("utf-8")
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            self._connection.execute(
                """
                INSERT INTO memories(
                    memory_id, tenant_id, mission_id, domain, tier, content_json,
                    provenance, reward_authority, uncertainty, replay_id,
                    created_at, expires_at, content_hash
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    memory_id, scope.tenant_id, scope.mission_id, scope.domain,
                    tier, content_json, provenance, reward_authority.value,
                    float(uncertainty), replay_id, created_at, expires_at, digest,
                ),
            )
            self._append_event("put", memory_id, {"content_hash": digest})
            self._connection.execute("COMMIT")
        except Exception:
            self._connection.execute("ROLLBACK")
            raise
        return MemoryRecord(
            memory_id, scope, tier, dict(content), provenance, reward_authority,
            float(uncertainty), replay_id, created_at, expires_at, digest,
        )

    def _append_event(
        self, kind: str, memory_id: str, payload: Mapping[str, Any]
    ) -> None:
        row = self._connection.execute(
            "SELECT sequence, event_hash FROM memory_events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        sequence = int(row["sequence"]) + 1 if row else 0
        previous = str(row["event_hash"]) if row else None
        created_at = time.time()
        base = {
            "sequence": sequence,
            "kind": kind,
            "memory_id": memory_id,
            "payload": dict(payload),
            "previous_hash": previous,
            "created_at": created_at,
        }
        event_hash = domain_hash("euclid.memory.event.v1", base)
        self._connection.execute(
            """
            INSERT INTO memory_events(
                sequence,event_id,kind,memory_id,payload_json,previous_hash,
                event_hash,created_at
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                sequence, "event-" + uuid.uuid4().hex, kind, memory_id,
                canonical_json(payload).decode("utf-8"), previous, event_hash,
                created_at,
            ),
        )

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            memory_id=str(row["memory_id"]),
            scope=MemoryScope(
                str(row["tenant_id"]), str(row["mission_id"]), str(row["domain"])
            ),
            tier=str(row["tier"]),
            content=json.loads(row["content_json"]),
            provenance=str(row["provenance"]),
            reward_authority=RewardAuthority(str(row["reward_authority"])),
            uncertainty=float(row["uncertainty"]),
            replay_id=str(row["replay_id"]),
            created_at=float(row["created_at"]),
            expires_at=(
                float(row["expires_at"]) if row["expires_at"] is not None else None
            ),
            content_hash=str(row["content_hash"]),
        )

    def get(
        self, memory_id: str, *, scope: MemoryScope, include_expired: bool = False
    ) -> MemoryRecord:
        row = self._connection.execute(
            """
            SELECT * FROM memories
            WHERE memory_id=? AND tenant_id=? AND mission_id=? AND domain=?
              AND tombstoned=0
            """,
            (memory_id, scope.tenant_id, scope.mission_id, scope.domain),
        ).fetchone()
        if row is None:
            raise KeyError("memory not found in requested scope")
        record = self._row_to_record(row)
        if (
            not include_expired
            and record.expires_at is not None
            and record.expires_at <= time.time()
        ):
            raise KeyError("memory expired")
        self._verify_record(record)
        return record

    def query(
        self,
        *,
        scope: MemoryScope,
        tier: str | None = None,
        limit: int = 100,
    ) -> list[MemoryRecord]:
        if tier is not None and tier not in TIERS:
            raise ValueError("unsupported memory tier")
        if not 1 <= int(limit) <= 1000:
            raise ValueError("limit must be in [1,1000]")
        parameters: list[Any] = [
            scope.tenant_id, scope.mission_id, scope.domain, time.time()
        ]
        tier_clause = ""
        if tier is not None:
            tier_clause = " AND tier=?"
            parameters.append(tier)
        parameters.append(int(limit))
        rows = self._connection.execute(
            f"""
            SELECT * FROM memories
            WHERE tenant_id=? AND mission_id=? AND domain=? AND tombstoned=0
              AND (expires_at IS NULL OR expires_at>?)
              {tier_clause}
            ORDER BY created_at DESC, memory_id ASC LIMIT ?
            """,
            parameters,
        ).fetchall()
        records = [self._row_to_record(row) for row in rows]
        for record in records:
            self._verify_record(record)
        return records

    def tombstone(self, memory_id: str, *, scope: MemoryScope, reason: str) -> None:
        if not reason:
            raise ValueError("tombstone reason is required")
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            cursor = self._connection.execute(
                """
                UPDATE memories SET tombstoned=1
                WHERE memory_id=? AND tenant_id=? AND mission_id=? AND domain=?
                  AND tombstoned=0
                """,
                (memory_id, scope.tenant_id, scope.mission_id, scope.domain),
            )
            if cursor.rowcount != 1:
                raise KeyError("memory not found in requested scope")
            self._append_event("tombstone", memory_id, {"reason": reason})
            self._connection.execute("COMMIT")
        except Exception:
            self._connection.execute("ROLLBACK")
            raise

    def _verify_record(self, record: MemoryRecord) -> None:
        base = self._content_base(
            memory_id=record.memory_id,
            scope=record.scope,
            tier=record.tier,
            content=record.content,
            provenance=record.provenance,
            reward_authority=record.reward_authority,
            uncertainty=record.uncertainty,
            replay_id=record.replay_id,
            created_at=record.created_at,
            expires_at=record.expires_at,
        )
        if domain_hash("euclid.memory.content.v1", base) != record.content_hash:
            raise ValueError("memory content hash mismatch")

    def verify(self) -> dict[str, Any]:
        memories = self._connection.execute("SELECT * FROM memories").fetchall()
        for row in memories:
            self._verify_record(self._row_to_record(row))
        previous = None
        events = self._connection.execute(
            "SELECT * FROM memory_events ORDER BY sequence"
        ).fetchall()
        for expected, row in enumerate(events):
            if int(row["sequence"]) != expected or row["previous_hash"] != previous:
                raise ValueError("memory event chain is discontinuous")
            base = {
                "sequence": expected,
                "kind": str(row["kind"]),
                "memory_id": str(row["memory_id"]),
                "payload": json.loads(row["payload_json"]),
                "previous_hash": row["previous_hash"],
                "created_at": float(row["created_at"]),
            }
            if domain_hash("euclid.memory.event.v1", base) != row["event_hash"]:
                raise ValueError("memory event hash mismatch")
            previous = str(row["event_hash"])
        return {
            "schema": "euclid.memory-verification/1",
            "valid": True,
            "memories": len(memories),
            "events": len(events),
            "event_chain_head": previous,
            "encryption_at_rest": False,
            "encryption_boundary": "requires encrypted volume or SQLCipher deployment",
        }

    def backup(self, destination: str | Path) -> Path:
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        output = sqlite3.connect(str(temporary))
        try:
            self._connection.backup(output)
        finally:
            output.close()
        os.replace(temporary, target)
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass
        return target
