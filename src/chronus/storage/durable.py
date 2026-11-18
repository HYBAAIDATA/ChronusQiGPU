"""Durable THESEUS custody for production Chronus deployments.

THESEUS owns persistence, integrity, continuity, restart recovery and the
append-only custody journal. OVID remains an in-process representation service;
it is deliberately not used as the system of record here.
"""

from __future__ import annotations

import hashlib
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from chronus.config import runtime_bounds
from chronus.storage.phyllotaxis import PhyllotaxisCoordinate, phyllotaxis_coordinate
from chronus.storage.theseus import StorageIntegrityError, TenantStateJournalEntry, TheseusRecord


_SCHEMA_VERSION = 1
_ZERO_HASH = "0" * 64


class CustodyUnavailableError(RuntimeError):
    """Durable custody cannot be opened or verified."""


class CustodyConflictError(RuntimeError):
    """A durable write conflicts with an existing authoritative record."""


class DurableTheseusService:
    """SQLite/WAL-backed THESEUS custody with fail-closed restart verification.

    The store is single-root durable custody. It provides atomic local
    transactions, content verification, tenant isolation, append-only journal
    continuity and fresh-process recovery. Geo replication remains a deployment
    concern and is not inferred from this class.
    """

    def __init__(self, path: str, lane_count: int | None = None) -> None:
        if not path or not isinstance(path, str):
            raise ValueError("path must be a non-empty string")
        if lane_count is None:
            lane_count = runtime_bounds()["storage_lanes"]
        if not isinstance(lane_count, int) or isinstance(lane_count, bool) or lane_count < 1:
            raise ValueError("lane_count must be a positive integer")
        self.path = str(Path(path))
        self.lane_count = lane_count
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._bootstrap()
        self.verify_store()

    @contextmanager
    def _connect(self, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=30000")
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _bootstrap(self) -> None:
        with self._lock, self._connect(immediate=True) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS custody_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS objects (
                    object_id TEXT PRIMARY KEY,
                    payload BLOB NOT NULL,
                    size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0)
                );
                CREATE TABLE IF NOT EXISTS records (
                    tenant_id TEXT NOT NULL,
                    object_id TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    sequence INTEGER NOT NULL,
                    golden_turns_numerator TEXT NOT NULL,
                    golden_turns_denominator TEXT NOT NULL,
                    lane INTEGER NOT NULL,
                    scale_index INTEGER NOT NULL,
                    PRIMARY KEY (tenant_id, object_id),
                    FOREIGN KEY (object_id) REFERENCES objects(object_id)
                );
                CREATE INDEX IF NOT EXISTS records_tenant_sequence
                    ON records(tenant_id, sequence);
                CREATE TABLE IF NOT EXISTS journal (
                    tenant_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    ovid_namespace TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    object_id TEXT NOT NULL,
                    prev_entry_hash TEXT NOT NULL,
                    entry_hash TEXT NOT NULL,
                    timestamp_ns INTEGER NOT NULL,
                    coordinate_sequence INTEGER NOT NULL,
                    golden_turns_numerator TEXT NOT NULL,
                    golden_turns_denominator TEXT NOT NULL,
                    lane INTEGER NOT NULL,
                    PRIMARY KEY (tenant_id, sequence),
                    FOREIGN KEY (object_id) REFERENCES objects(object_id)
                );
                """
            )
            row = db.execute(
                "SELECT value FROM custody_meta WHERE key='schema_version'"
            ).fetchone()
            if row is None:
                db.execute(
                    "INSERT INTO custody_meta(key,value) VALUES('schema_version',?)",
                    (str(_SCHEMA_VERSION),),
                )
            elif int(row["value"]) != _SCHEMA_VERSION:
                raise CustodyUnavailableError(
                    f"unsupported THESEUS schema version {row['value']}"
                )

    @staticmethod
    def _validate_payload(tenant_id: str, payload: bytes, scale_index: int) -> None:
        if not tenant_id or not isinstance(tenant_id, str):
            raise ValueError("tenant_id must be a non-empty string")
        max_payload = runtime_bounds()["max_payload_bytes"]
        if not isinstance(payload, bytes) or not 1 <= len(payload) <= max_payload:
            raise ValueError(f"payload must be 1 to {max_payload} bytes")
        if not isinstance(scale_index, int) or isinstance(scale_index, bool) or scale_index < 0:
            raise ValueError("scale_index must be a non-negative integer")

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> TheseusRecord:
        return TheseusRecord(
            object_id=row["object_id"],
            tenant_id=row["tenant_id"],
            size_bytes=int(row["size_bytes"]),
            coordinate=PhyllotaxisCoordinate(
                sequence=int(row["sequence"]),
                golden_turns_numerator=int(row["golden_turns_numerator"]),
                golden_turns_denominator=int(row["golden_turns_denominator"]),
                lane=int(row["lane"]),
            ),
            scale_index=int(row["scale_index"]),
        )


    def _verify_record_geometry(self, row: sqlite3.Row) -> None:
        """Fail closed if logical phyllotaxis coordinates differ from their inputs."""
        try:
            sequence = int(row["sequence"])
            digest = bytes.fromhex(str(row["object_id"]))
            expected = phyllotaxis_coordinate(sequence, digest, self.lane_count)
            actual = PhyllotaxisCoordinate(
                sequence=sequence,
                golden_turns_numerator=int(row["golden_turns_numerator"]),
                golden_turns_denominator=int(row["golden_turns_denominator"]),
                lane=int(row["lane"]),
            )
            scale_index = int(row["scale_index"])
        except (ValueError, TypeError, OverflowError) as exc:
            raise StorageIntegrityError("invalid phyllotaxis metadata") from exc
        if actual != expected or scale_index < 0:
            raise StorageIntegrityError(
                f"phyllotaxis metadata mismatch for {row['object_id']}"
            )

    def store(self, tenant_id: str, payload: bytes, scale_index: int = 0) -> TheseusRecord:
        self._validate_payload(tenant_id, payload, scale_index)
        object_id = hashlib.sha256(payload).hexdigest()
        with self._lock, self._connect(immediate=True) as db:
            existing = db.execute(
                "SELECT * FROM records WHERE tenant_id=? AND object_id=?",
                (tenant_id, object_id),
            ).fetchone()
            if existing is not None:
                stored = db.execute(
                    "SELECT payload FROM objects WHERE object_id=?", (object_id,)
                ).fetchone()
                if stored is None or bytes(stored["payload"]) != payload:
                    raise StorageIntegrityError(
                        f"authoritative content for {object_id} failed equality verification"
                    )
                return self._record_from_row(existing)

            object_row = db.execute(
                "SELECT payload FROM objects WHERE object_id=?", (object_id,)
            ).fetchone()
            if object_row is None:
                db.execute(
                    "INSERT INTO objects(object_id,payload,size_bytes) VALUES(?,?,?)",
                    (object_id, sqlite3.Binary(payload), len(payload)),
                )
            elif hashlib.sha256(bytes(object_row["payload"])).hexdigest() != object_id:
                raise StorageIntegrityError(
                    f"existing content for {object_id} failed digest verification"
                )

            seq = int(
                db.execute(
                    "SELECT COALESCE(MAX(sequence),-1)+1 AS next_sequence FROM records"
                ).fetchone()["next_sequence"]
            )
            coordinate = phyllotaxis_coordinate(seq, bytes.fromhex(object_id), self.lane_count)
            db.execute(
                """
                INSERT INTO records(
                    tenant_id,object_id,size_bytes,sequence,
                    golden_turns_numerator,golden_turns_denominator,lane,scale_index
                ) VALUES(?,?,?,?,?,?,?,?)
                """,
                (
                    tenant_id,
                    object_id,
                    len(payload),
                    coordinate.sequence,
                    str(coordinate.golden_turns_numerator),
                    str(coordinate.golden_turns_denominator),
                    coordinate.lane,
                    scale_index,
                ),
            )
            return TheseusRecord(
                object_id=object_id,
                tenant_id=tenant_id,
                size_bytes=len(payload),
                coordinate=coordinate,
                scale_index=scale_index,
            )

    def query(self, tenant_id: str) -> list[str]:
        if not tenant_id or not isinstance(tenant_id, str):
            raise ValueError("tenant_id must be a non-empty string")
        with self._connect() as db:
            rows = db.execute(
                "SELECT object_id FROM records WHERE tenant_id=? ORDER BY sequence",
                (tenant_id,),
            ).fetchall()
        return [str(row["object_id"]) for row in rows]

    def get_record(self, tenant_id: str, object_id: str) -> TheseusRecord:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM records WHERE tenant_id=? AND object_id=?",
                (tenant_id, object_id),
            ).fetchone()
        if row is None:
            raise KeyError(object_id)
        self._verify_record_geometry(row)
        return self._record_from_row(row)

    def reconstruct(self, tenant_id: str, object_id: str) -> bytes:
        self.get_record(tenant_id, object_id)
        with self._connect() as db:
            row = db.execute(
                "SELECT payload FROM objects WHERE object_id=?", (object_id,)
            ).fetchone()
        if row is None:
            raise StorageIntegrityError(f"content for {object_id} is unavailable")
        payload = bytes(row["payload"])
        if hashlib.sha256(payload).hexdigest() != object_id:
            raise StorageIntegrityError(f"content for {object_id} failed digest verification")
        return payload

    def scale_record(self, tenant_id: str, object_id: str, increment: int) -> TheseusRecord:
        if not isinstance(increment, int) or isinstance(increment, bool) or increment < 0:
            raise ValueError("increment must be a non-negative integer")
        current = self.get_record(tenant_id, object_id)
        next_scale = current.scale_index + increment
        max_index = runtime_bounds()["max_trinity_index"]
        if next_scale > max_index:
            raise ValueError(f"scale index exceeds configured maximum {max_index}")
        with self._lock, self._connect(immediate=True) as db:
            seq = int(
                db.execute(
                    "SELECT COALESCE(MAX(sequence),-1)+1 AS next_sequence FROM records"
                ).fetchone()["next_sequence"]
            )
            coordinate = phyllotaxis_coordinate(seq, bytes.fromhex(object_id), self.lane_count)
            db.execute(
                """
                UPDATE records
                SET sequence=?, golden_turns_numerator=?, golden_turns_denominator=?,
                    lane=?, scale_index=?
                WHERE tenant_id=? AND object_id=?
                """,
                (
                    coordinate.sequence,
                    str(coordinate.golden_turns_numerator),
                    str(coordinate.golden_turns_denominator),
                    coordinate.lane,
                    next_scale,
                    tenant_id,
                    object_id,
                ),
            )
        return TheseusRecord(
            object_id=object_id,
            tenant_id=tenant_id,
            size_bytes=current.size_bytes,
            coordinate=coordinate,
            scale_index=next_scale,
        )

    def append_journal_event(
        self, tenant_id: str, event_type: str, payload: bytes,
        *, expected_last_sequence: int | None = None,
    ) -> TenantStateJournalEntry:
        """Append one hash-chained journal entry.

        ``expected_last_sequence`` (optional) makes the append a compare-and-swap
        inside the same ``BEGIN IMMEDIATE`` transaction: the entry is written only
        if the tenant's newest sequence is exactly that value (-1 = empty journal);
        otherwise ``CustodyConflictError`` is raised and nothing is appended.
        """
        if not event_type or not isinstance(event_type, str):
            raise ValueError("event_type must be a non-empty string")
        if expected_last_sequence is not None and (
            isinstance(expected_last_sequence, bool) or not isinstance(expected_last_sequence, int)
            or expected_last_sequence < -1
        ):
            raise ValueError("expected_last_sequence must be an integer >= -1")
        record = self.store(tenant_id, payload)
        ovid_namespace = f"o1_{tenant_id}"
        with self._lock, self._connect(immediate=True) as db:
            previous = db.execute(
                "SELECT sequence,entry_hash FROM journal WHERE tenant_id=? ORDER BY sequence DESC LIMIT 1",
                (tenant_id,),
            ).fetchone()
            last = -1 if previous is None else int(previous["sequence"])
            if expected_last_sequence is not None and last != expected_last_sequence:
                raise CustodyConflictError(
                    f"journal tip moved: expected sequence {expected_last_sequence}, found {last}"
                )
            sequence = 0 if previous is None else int(previous["sequence"]) + 1
            prev_hash = _ZERO_HASH if previous is None else str(previous["entry_hash"])
            timestamp_ns = time.time_ns()
            material = (
                f"{ovid_namespace}|{sequence}|{event_type}|{record.object_id}|"
                f"{prev_hash}|{timestamp_ns}"
            ).encode("utf-8")
            entry_hash = hashlib.sha256(material).hexdigest()
            c = record.coordinate
            db.execute(
                """
                INSERT INTO journal(
                    tenant_id,sequence,ovid_namespace,event_type,object_id,
                    prev_entry_hash,entry_hash,timestamp_ns,coordinate_sequence,
                    golden_turns_numerator,golden_turns_denominator,lane
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    tenant_id,
                    sequence,
                    ovid_namespace,
                    event_type,
                    record.object_id,
                    prev_hash,
                    entry_hash,
                    timestamp_ns,
                    c.sequence,
                    str(c.golden_turns_numerator),
                    str(c.golden_turns_denominator),
                    c.lane,
                ),
            )
        return TenantStateJournalEntry(
            sequence=sequence,
            tenant_id=tenant_id,
            ovid_namespace=ovid_namespace,
            event_type=event_type,
            object_id=record.object_id,
            prev_entry_hash=prev_hash,
            entry_hash=entry_hash,
            timestamp_ns=timestamp_ns,
            coordinate=record.coordinate,
        )

    def get_journal(
        self, tenant_id: str, *, after_sequence: int | None = None
    ) -> list[TenantStateJournalEntry]:
        """Tenant journal in sequence order; ``after_sequence`` returns only newer entries."""
        with self._connect() as db:
            if after_sequence is None:
                rows = db.execute(
                    "SELECT * FROM journal WHERE tenant_id=? ORDER BY sequence", (tenant_id,)
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM journal WHERE tenant_id=? AND sequence>? ORDER BY sequence",
                    (tenant_id, int(after_sequence)),
                ).fetchall()
        return [
            TenantStateJournalEntry(
                sequence=int(row["sequence"]),
                tenant_id=str(row["tenant_id"]),
                ovid_namespace=str(row["ovid_namespace"]),
                event_type=str(row["event_type"]),
                object_id=str(row["object_id"]),
                prev_entry_hash=str(row["prev_entry_hash"]),
                entry_hash=str(row["entry_hash"]),
                timestamp_ns=int(row["timestamp_ns"]),
                coordinate=PhyllotaxisCoordinate(
                    sequence=int(row["coordinate_sequence"]),
                    golden_turns_numerator=int(row["golden_turns_numerator"]),
                    golden_turns_denominator=int(row["golden_turns_denominator"]),
                    lane=int(row["lane"]),
                ),
            )
            for row in rows
        ]

    def verify_journal_continuity(self, tenant_id: str) -> bool:
        entries = self.get_journal(tenant_id)
        if not entries:
            return False
        expected_prev = _ZERO_HASH
        for expected_sequence, entry in enumerate(entries):
            if entry.sequence != expected_sequence or entry.prev_entry_hash != expected_prev:
                return False
            if entry.tenant_id != tenant_id or entry.ovid_namespace != f"o1_{tenant_id}":
                return False
            try:
                coordinate = phyllotaxis_coordinate(
                    entry.coordinate.sequence, bytes.fromhex(entry.object_id),
                    self.lane_count,
                )
            except (ValueError, TypeError, OverflowError):
                return False
            if entry.coordinate != coordinate:
                return False
            self.reconstruct(tenant_id, entry.object_id)
            material = (
                f"{entry.ovid_namespace}|{entry.sequence}|{entry.event_type}|"
                f"{entry.object_id}|{entry.prev_entry_hash}|{entry.timestamp_ns}"
            ).encode("utf-8")
            if hashlib.sha256(material).hexdigest() != entry.entry_hash:
                return False
            expected_prev = entry.entry_hash
        return True

    def verify_store(self) -> None:
        with self._connect() as db:
            integrity = str(db.execute("PRAGMA integrity_check").fetchone()[0])
            if integrity.lower() != "ok":
                raise CustodyUnavailableError(f"SQLite integrity check failed: {integrity}")
            # integrity_check is not a foreign-key check. Fail closed on orphaned
            # records/journal pointers even if SQLite page integrity is fine.
            foreign_key_errors = db.execute("PRAGMA foreign_key_check").fetchall()
            if foreign_key_errors:
                raise StorageIntegrityError("THESEUS durable foreign-key integrity failed")
            objects = db.execute("SELECT object_id,payload FROM objects").fetchall()
            for row in objects:
                payload = bytes(row["payload"])
                if hashlib.sha256(payload).hexdigest() != row["object_id"]:
                    raise StorageIntegrityError(
                        f"durable content {row['object_id']} failed digest verification"
                    )
            records = db.execute(
                "SELECT r.*, o.size_bytes AS object_size "
                "FROM records AS r JOIN objects AS o USING (object_id)"
            ).fetchall()
            for record in records:
                self._verify_record_geometry(record)
                if int(record["size_bytes"]) != int(record["object_size"]):
                    raise StorageIntegrityError(
                        f"durable record size mismatch for {record['object_id']}"
                    )
            tenants = [
                str(row["tenant_id"])
                for row in db.execute("SELECT DISTINCT tenant_id FROM journal").fetchall()
            ]
        for tenant_id in tenants:
            if not self.verify_journal_continuity(tenant_id):
                raise StorageIntegrityError(
                    f"THESEUS journal continuity failed for tenant {tenant_id}"
                )

    def checkpoint(self) -> dict:
        # sqlite3's connection context manager commits or rolls back the
        # transaction; it does NOT close the handle. Using it here leaked an
        # open connection, which keeps the database file locked and makes the
        # enclosing temporary directory undeletable on Windows.
        connection = sqlite3.connect(self.path, timeout=30.0)
        try:
            row = connection.execute("PRAGMA wal_checkpoint(FULL)").fetchone()
        finally:
            connection.close()
        return {
            "mode": "sqlite-wal",
            "busy": int(row[0]),
            "log_frames": int(row[1]),
            "checkpointed_frames": int(row[2]),
        }

    def stats(self) -> dict:
        with self._connect() as db:
            records = int(db.execute("SELECT COUNT(*) FROM records").fetchone()[0])
            tenants = int(db.execute("SELECT COUNT(DISTINCT tenant_id) FROM records").fetchone()[0])
            journal_entries = int(db.execute("SELECT COUNT(*) FROM journal").fetchone()[0])
            histogram = [0] * self.lane_count
            for row in db.execute("SELECT lane,COUNT(*) AS n FROM records GROUP BY lane"):
                histogram[int(row["lane"])] = int(row["n"])
        return {
            "records": records,
            "tenants": tenants,
            "journal_entries": journal_entries,
            "lane_count": self.lane_count,
            "lane_histogram": histogram,
            "durable": True,
            "backend": "sqlite-wal",
            "schema_version": _SCHEMA_VERSION,
        }

    def evidence(self) -> dict:
        self.verify_store()
        return {
            "authority": "THESEUS",
            "durable": True,
            "backend": "sqlite-wal",
            "path": str(Path(self.path).resolve()),
            "schema_version": _SCHEMA_VERSION,
            "integrity": "PASS",
            "stats": self.stats(),
            "checkpoint": self.checkpoint(),
        }
