"""Bounded, integrity-checked persistence for complete MLA1517 records."""
from __future__ import annotations

import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from queue import Full, Queue
from typing import Any

from .cassini_seal import InvalidCassiniSeal, compute_seal, verify_seal


class PersistenceError(RuntimeError):
    """A record could not be persisted or recovered safely."""


class CorruptRecord(PersistenceError):
    """A persisted record failed its ABI or Cassini integrity check."""


class BackpressureRequired(PersistenceError):
    """The bounded queue is full; the caller must apply backpressure."""


@dataclass(frozen=True)
class PersistedRecord:
    record_id: str
    state: bytes
    sequence: int
    watermark: int
    lane_id: int
    seal: str
    created_ns: int


class TelemetryCounters:
    """Writer-side counters incremented only after successful writes."""

    def __init__(self) -> None:
        self._values: dict[str, int] = {}

    def increment(self, name: str, amount: int = 1) -> None:
        if amount < 0:
            raise ValueError("telemetry increments cannot be negative")
        self._values[name] = self._values.get(name, 0) + amount

    def snapshot(self) -> dict[str, int]:
        return dict(self._values)


class PrimeDBPersistence:
    """SQLite WAL persistence with exact state ABI and quarantine handling."""

    def __init__(self, path: str | Path, *, telemetry: TelemetryCounters | None = None) -> None:
        self.path = str(path)
        self.telemetry = telemetry or TelemetryCounters()
        self.db = sqlite3.connect(self.path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS records (
                record_id TEXT PRIMARY KEY,
                state BLOB NOT NULL,
                sequence INTEGER NOT NULL UNIQUE,
                watermark INTEGER NOT NULL,
                lane_id INTEGER NOT NULL,
                seal TEXT NOT NULL,
                created_ns INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS quarantine (
                record_id TEXT PRIMARY KEY,
                state BLOB,
                sequence INTEGER,
                watermark INTEGER,
                lane_id INTEGER,
                seal TEXT,
                reason TEXT NOT NULL,
                quarantined_ns INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cursors (
                name TEXT PRIMARY KEY,
                next_sequence INTEGER NOT NULL
            );
            """
        )
        self.db.commit()

    def append(self, *, state: bytes, sequence: int, watermark: int, lane_id: int) -> PersistedRecord:
        if not isinstance(state, bytes) or len(state) != 64:
            raise PersistenceError("state ABI requires exactly 64 bytes")
        if min(sequence, watermark, lane_id) < 0:
            raise PersistenceError("record coordinates cannot be negative")
        if sequence < self.recover_cursor():
            raise PersistenceError("sequence is behind the recovered PRIME-DB cursor")
        seal = compute_seal(state=state, sequence=sequence, watermark=watermark, lane_id=lane_id)
        record = PersistedRecord(uuid.uuid4().hex, state, sequence, watermark, lane_id, seal, time.time_ns())
        try:
            with self.db:
                self.db.execute(
                    "INSERT INTO records(record_id,state,sequence,watermark,lane_id,seal,created_ns) VALUES(?,?,?,?,?,?,?)",
                    (record.record_id, record.state, record.sequence, record.watermark, record.lane_id, record.seal, record.created_ns),
                )
                self.db.execute(
                    "INSERT INTO cursors(name,next_sequence) VALUES('main',?) ON CONFLICT(name) DO UPDATE SET next_sequence=excluded.next_sequence",
                    (sequence + 1,),
                )
        except sqlite3.IntegrityError as exc:
            raise PersistenceError("duplicate or conflicting sequence") from exc
        self.telemetry.increment("records_written")
        return record

    def recover_cursor(self) -> int:
        row = self.db.execute("SELECT MAX(sequence) FROM records").fetchone()
        maximum = row[0] if row and row[0] is not None else -1
        return int(maximum) + 1

    def get(self, record_id: str) -> PersistedRecord:
        row = self.db.execute(
            "SELECT record_id,state,sequence,watermark,lane_id,seal,created_ns FROM records WHERE record_id=?",
            (record_id,),
        ).fetchone()
        if row is None:
            raise PersistenceError("record not found")
        record = PersistedRecord(row[0], bytes(row[1]), row[2], row[3], row[4], row[5], row[6])
        try:
            verify_seal(state=record.state, sequence=record.sequence, watermark=record.watermark, lane_id=record.lane_id, seal=record.seal)
        except InvalidCassiniSeal as exc:
            self.quarantine(record.record_id, str(exc))
            raise CorruptRecord(str(exc)) from exc
        self.telemetry.increment("records_read")
        return record

    def quarantine(self, record_id: str, reason: str) -> None:
        row = self.db.execute(
            "SELECT record_id,state,sequence,watermark,lane_id,seal FROM records WHERE record_id=?",
            (record_id,),
        ).fetchone()
        if row is None:
            raise PersistenceError("cannot quarantine missing record")
        with self.db:
            self.db.execute(
                "INSERT OR REPLACE INTO quarantine(record_id,state,sequence,watermark,lane_id,seal,reason,quarantined_ns) VALUES(?,?,?,?,?,?,?,?)",
                (*row, reason, time.time_ns()),
            )
            self.db.execute("DELETE FROM records WHERE record_id=?", (record_id,))
        self.telemetry.increment("records_quarantined")

    def close(self) -> None:
        self.db.close()


class BoundedPersistenceQueue:
    """Bounded writer queue that raises instead of silently dropping records."""

    def __init__(self, max_pending: int) -> None:
        if max_pending <= 0:
            raise ValueError("max_pending must be positive")
        self._queue: Queue[Any] = Queue(maxsize=max_pending)

    def submit(self, item: Any) -> None:
        try:
            self._queue.put_nowait(item)
        except Full as exc:
            raise BackpressureRequired("persistence queue is full; apply backpressure") from exc

    def receive(self) -> Any:
        return self._queue.get_nowait()
