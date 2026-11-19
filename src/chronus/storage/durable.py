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
from chronus.storage import self_heal
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

    def __init__(
        self, path: str, lane_count: int | None = None, *, self_healing: bool | None = None,
        repair_authority: str | None = None,
    ) -> None:
        if not path or not isinstance(path, str):
            raise ValueError("path must be a non-empty string")
        if lane_count is None:
            lane_count = runtime_bounds()["storage_lanes"]
        if not isinstance(lane_count, int) or isinstance(lane_count, bool) or lane_count < 1:
            raise ValueError("lane_count must be a positive integer")
        self.path = str(Path(path))
        self.lane_count = lane_count
        if self_healing is None:
            self_healing = self_heal.self_healing_enabled()
        if not isinstance(self_healing, bool):
            raise ValueError("self_healing must be a bool")
        self.self_healing = self_healing
        self.self_healing_max_bytes = self_heal.self_healing_max_bytes()
        if repair_authority is None:
            repair_authority = self_heal.repair_authority()
        if repair_authority not in self_heal.REPAIR_AUTHORITIES:
            raise ValueError(f"repair_authority must be one of {sorted(self_heal.REPAIR_AUTHORITIES)}")
        self.repair_authority = repair_authority
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._heal_locks: dict[str, threading.Lock] = {}
        self._heal_locks_guard = threading.Lock()
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
                CREATE TABLE IF NOT EXISTS object_parity (
                    object_id TEXT PRIMARY KEY,
                    scheme TEXT NOT NULL,
                    n INTEGER NOT NULL,
                    k INTEGER NOT NULL,
                    parity BLOB NOT NULL,
                    parity_sha256 TEXT NOT NULL,
                    FOREIGN KEY (object_id) REFERENCES objects(object_id)
                );
                CREATE TABLE IF NOT EXISTS self_heal_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    object_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    corrected_bytes INTEGER NOT NULL,
                    detail TEXT NOT NULL,
                    timestamp_ns INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS self_heal_events_object
                    ON self_heal_events(object_id, event_id);
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
        # Encode parity before taking the write lock so writers are not stalled.
        parity = (
            self_heal.encode_parity(payload)
            if self.self_healing and len(payload) <= self.self_healing_max_bytes
            else None
        )
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
                self._ensure_parity(db, object_id, payload, parity)
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
            self._ensure_parity(db, object_id, payload, parity)

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
            repaired = self._try_heal(object_id, payload)
            if repaired is None:
                raise StorageIntegrityError(f"content for {object_id} failed digest verification")
            return repaired
        return payload

    # ------------------------------------------------------------------
    # Bounded self-healing (see chronus.storage.self_heal)
    # ------------------------------------------------------------------

    def _ensure_parity(
        self, db: sqlite3.Connection, object_id: str, payload: bytes,
        precomputed: bytes | None = None,
    ) -> None:
        """Write the Reed-Solomon parity sidecar for a verified payload."""
        if not self.self_healing:
            return
        row = db.execute(
            "SELECT scheme, n, k, parity, parity_sha256 FROM object_parity WHERE object_id=?",
            (object_id,),
        ).fetchone()
        if row is not None and self._sidecar_intact(row):
            return
        # New protection honours the configured limit; an existing sidecar is
        # maintained regardless (up to the encoder limit) so lowering the limit
        # never strands a damaged sidecar that is still used for repair.
        limit = self_heal.encoder_max_bytes() if row is not None else self.self_healing_max_bytes
        if len(payload) > limit:
            return
        parity = precomputed if precomputed is not None else self_heal.encode_parity(payload)
        db.execute(
            "INSERT OR REPLACE INTO object_parity(object_id,scheme,n,k,parity,parity_sha256) "
            "VALUES(?,?,?,?,?,?)",
            (object_id, self_heal.SCHEME, self_heal.RS_N, self_heal.RS_K,
             sqlite3.Binary(parity), hashlib.sha256(parity).hexdigest()),
        )
        if row is not None:
            self._log_heal(db, object_id, "PARITY_REGENERATED", 0, "parity sidecar failed verification")

    @staticmethod
    def _sidecar_intact(row: sqlite3.Row) -> bool:
        return (self_heal.sidecar_metadata_valid(row["scheme"], row["n"], row["k"])
                and hashlib.sha256(bytes(row["parity"])).hexdigest() == row["parity_sha256"])

    @staticmethod
    def _log_heal(db: sqlite3.Connection, object_id: str, kind: str, corrected: int, detail: str) -> None:
        if kind == "UNREPAIRABLE":
            last = db.execute(
                "SELECT kind, detail FROM self_heal_events WHERE object_id=? "
                "ORDER BY event_id DESC LIMIT 1",
                (object_id,),
            ).fetchone()
            if last is not None and last["kind"] == kind and last["detail"] == detail:
                return  # same failure already recorded; don't grow the log on retries
        db.execute(
            "INSERT INTO self_heal_events(object_id,kind,corrected_bytes,detail,timestamp_ns) "
            "VALUES(?,?,?,?,?)",
            (object_id, kind, corrected, detail, time.time_ns()),
        )

    def _try_heal(self, object_id: str, corrupted: bytes) -> bytes | None:
        """Handle a payload that failed its content address on open or read.

        ``repair_authority == "theseus"`` (default): repair in place, accepted
        only if the corrected bytes hash to ``object_id``.
        ``repair_authority == "salamander"``: THESEUS only detects and
        diagnoses; it records a DETECTED (or UNREPAIRABLE) event and the read
        fails closed until :meth:`repair_object` is called by the authorised
        remediation path (``chronus.integration.salamander_theseus``).
        """
        if not self.self_healing:
            return None
        commit = self.repair_authority == "theseus"
        return self._heal_serialised(object_id, commit=commit, authority="theseus-inline")

    def _heal_serialised(self, object_id: str, *, commit: bool, authority: str) -> bytes | None:
        # One decode per object per process: concurrent callers wait, then see
        # the repaired row (or the recorded failure) instead of re-decoding.
        with self._heal_locks_guard:
            object_lock = self._heal_locks.setdefault(object_id, threading.Lock())
        with object_lock:  # entries are kept; one small lock per damaged object seen
            return self._try_heal_locked(object_id, commit=commit, authority=authority)

    def _diagnose_locked(self, object_id: str) -> dict:
        """Read-only diagnosis; decoding runs with no lock or transaction held."""
        with self._connect() as db:
            current = db.execute(
                "SELECT payload, size_bytes FROM objects WHERE object_id=?", (object_id,)
            ).fetchone()
            parity_row = db.execute(
                "SELECT scheme, n, k, parity, parity_sha256 FROM object_parity WHERE object_id=?",
                (object_id,),
            ).fetchone()
        if current is None:
            return {"object_id": object_id, "status": "MISSING", "reason": "no such object"}
        payload = bytes(current["payload"])
        base = {"object_id": object_id, "payload": payload,
                "parity_sha256": None if parity_row is None else parity_row["parity_sha256"]}
        if hashlib.sha256(payload).hexdigest() == object_id:
            return {**base, "status": "HEALTHY", "reason": "content address verified"}
        if parity_row is None:
            return {**base, "status": "UNREPAIRABLE", "reason": "no parity sidecar"}
        if not self._sidecar_intact(parity_row):
            return {**base, "status": "UNREPAIRABLE", "reason": "parity sidecar failed verification"}
        outcome = self_heal.heal_payload(
            payload, object_id, bytes(parity_row["parity"]), int(current["size_bytes"]),
            n=int(parity_row["n"]), k=int(parity_row["k"]),
        )
        if not outcome.ok:
            return {**base, "status": "UNREPAIRABLE", "reason": outcome.reason}
        return {**base, "status": "REPAIRABLE", "reason": "within Reed-Solomon bound",
                "repaired": outcome.repaired, "corrected_bytes": len(outcome.corrected_positions),
                "code": "RS(%d,%d) over GF(257)" % (parity_row["n"], parity_row["k"])}

    def _try_heal_locked(self, object_id: str, *, commit: bool = True,
                         authority: str = "theseus-inline") -> bytes | None:
        # 1-2. Snapshot and decode outside any write transaction.
        diag = self._diagnose_locked(object_id)
        if diag["status"] == "MISSING":
            return None
        if diag["status"] == "HEALTHY":
            return diag["payload"]  # healed concurrently
        # 3. Short write transaction: recheck, then commit repair or audit row.
        with self._lock, self._connect(immediate=True) as db:
            now = db.execute(
                "SELECT payload FROM objects WHERE object_id=?", (object_id,)
            ).fetchone()
            if now is None:
                return None
            now_payload = bytes(now["payload"])
            if hashlib.sha256(now_payload).hexdigest() == object_id:
                return now_payload  # healed concurrently
            if diag["status"] == "UNREPAIRABLE":
                self._log_heal(db, object_id, "UNREPAIRABLE", 0, diag["reason"])
                return None
            if not commit:
                self._log_heal(db, object_id, "DETECTED", diag["corrected_bytes"],
                               "repairable within bound; awaiting authorised remediation")
                return None
            now_parity = db.execute(
                "SELECT parity_sha256 FROM object_parity WHERE object_id=?", (object_id,)
            ).fetchone()
            if (now_payload != diag["payload"] or now_parity is None
                    or now_parity["parity_sha256"] != diag["parity_sha256"]):
                return None  # changed underneath us; caller fails closed, a retry re-decodes
            db.execute(
                "UPDATE objects SET payload=? WHERE object_id=?",
                (sqlite3.Binary(diag["repaired"]), object_id),
            )
            self._log_heal(
                db, object_id, "REPAIRED", diag["corrected_bytes"],
                "Reed-Solomon %s; SHA-256 verified; authority=%s" % (diag["code"], authority),
            )
            return diag["repaired"]

    # Public surface for the remediation authority (Salamander) ----------

    def diagnose_object(self, object_id: str) -> dict:
        """Read-only diagnosis of one object: HEALTHY, REPAIRABLE, UNREPAIRABLE or MISSING."""
        if not isinstance(object_id, str) or len(object_id) != 64:
            raise ValueError("object_id must be a SHA-256 hex digest")
        diag = self._diagnose_locked(object_id)
        return {k: v for k, v in diag.items() if k not in {"payload", "repaired", "parity_sha256"}}

    def scan_integrity(self) -> list[dict]:
        """Observe and detect: diagnose every object whose payload fails its address."""
        with self._connect() as db:
            damaged = [
                str(row["object_id"])
                for row in db.execute("SELECT object_id, payload FROM objects").fetchall()
                if hashlib.sha256(bytes(row["payload"])).hexdigest() != row["object_id"]
            ]
        return [self.diagnose_object(object_id) for object_id in damaged]

    def repair_object(self, object_id: str, *, authority: str) -> dict:
        """Execute one bounded repair (atomic; SHA-256 verified) and report it.

        ``authority`` names who authorised the action and is kept in the
        REPAIRED evidence row. Unrepairable objects are left untouched.
        """
        if not authority or not isinstance(authority, str):
            raise ValueError("authority is required")
        if not self.self_healing:
            raise StorageIntegrityError("self-healing is disabled for this store")
        repaired = self._heal_serialised(object_id, commit=True, authority=authority)
        diag = self.diagnose_object(object_id)
        return {"object_id": object_id, "repaired": repaired is not None, "status": diag["status"],
                "reason": diag["reason"]}

    def self_heal_events(self) -> list[dict]:
        """Self-healing audit trail, oldest first."""
        with self._connect() as db:
            rows = db.execute(
                "SELECT event_id, object_id, kind, corrected_bytes, detail, timestamp_ns "
                "FROM self_heal_events ORDER BY event_id"
            ).fetchall()
        return [dict(row) for row in rows]

    def self_healing_status(self) -> dict:
        with self._connect() as db:
            protected = int(db.execute("SELECT COUNT(*) FROM object_parity").fetchone()[0])
            objects = int(db.execute("SELECT COUNT(*) FROM objects").fetchone()[0])
            repairs = int(db.execute(
                "SELECT COUNT(*) FROM self_heal_events WHERE kind='REPAIRED'"
            ).fetchone()[0])
            failures = int(db.execute(
                "SELECT COUNT(DISTINCT object_id) FROM self_heal_events WHERE kind='UNREPAIRABLE'"
            ).fetchone()[0])
        return {
            "enabled": self.self_healing,
            "scheme": self_heal.SCHEME,
            "code": f"RS({self_heal.RS_N},{self_heal.RS_K}) over GF(257)",
            "correctable_bytes_per_block": (self_heal.RS_N - self_heal.RS_K) // 2,
            "block_bytes": self_heal.RS_K,
            "max_protected_bytes": self.self_healing_max_bytes,
            "objects": objects,
            "protected_objects": protected,
            "repairs": repairs,
            "unrepairable_objects": failures,
            "repair_authority": self.repair_authority,
        }

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
        self, tenant_id: str, event_type: str, payload: bytes
    ) -> TenantStateJournalEntry:
        if not event_type or not isinstance(event_type, str):
            raise ValueError("event_type must be a non-empty string")
        record = self.store(tenant_id, payload)
        ovid_namespace = f"o1_{tenant_id}"
        with self._lock, self._connect(immediate=True) as db:
            previous = db.execute(
                "SELECT sequence,entry_hash FROM journal WHERE tenant_id=? ORDER BY sequence DESC LIMIT 1",
                (tenant_id,),
            ).fetchone()
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

    def get_journal(self, tenant_id: str) -> list[TenantStateJournalEntry]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM journal WHERE tenant_id=? ORDER BY sequence", (tenant_id,)
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

    def verify_journal_continuity(
        self, tenant_id: str, *, quarantined: frozenset[str] = frozenset()
    ) -> bool:
        # ``quarantined`` objects are detected-but-unrepaired (Salamander mode);
        # their content is not reconstructed here, but chain checks still run.
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
            if entry.object_id not in quarantined:
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
            damaged = [
                (str(row["object_id"]), bytes(row["payload"]))
                for row in objects
                if hashlib.sha256(bytes(row["payload"])).hexdigest() != row["object_id"]
            ]
        # Repair outside the read transaction; fail closed on the first object
        # that cannot be repaired within bounds.
        quarantined: set[str] = set()
        for object_id, payload in damaged:
            if self._try_heal(object_id, payload) is not None:
                continue
            if self.self_healing and self.repair_authority == "salamander":
                # Detected and diagnosed; repairable objects stay quarantined
                # (reads fail closed) until the authorised repair runs.
                if self.diagnose_object(object_id)["status"] == "REPAIRABLE":
                    quarantined.add(object_id)
                    continue
            raise StorageIntegrityError(
                f"durable content {object_id} failed digest verification"
            )
        if self.self_healing:
            self._verify_parity_sidecars()
            self._backfill_parity()
        with self._connect() as db:
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
        frozen_quarantine = frozenset(quarantined)
        for tenant_id in tenants:
            if not self.verify_journal_continuity(tenant_id, quarantined=frozen_quarantine):
                raise StorageIntegrityError(
                    f"THESEUS journal continuity failed for tenant {tenant_id}"
                )

    def _verify_parity_sidecars(self) -> None:
        """Regenerate parity whose own digest fails, from verified payloads."""
        with self._connect() as db:
            bad = [
                str(row["object_id"])
                for row in db.execute(
                    "SELECT object_id, scheme, n, k, parity, parity_sha256 FROM object_parity"
                ).fetchall()
                if not self._sidecar_intact(row)
            ]
        for object_id in bad:
            with self._lock, self._connect(immediate=True) as db:
                row = db.execute(
                    "SELECT payload FROM objects WHERE object_id=?", (object_id,)
                ).fetchone()
                if row is not None and hashlib.sha256(bytes(row["payload"])).hexdigest() == object_id:
                    self._ensure_parity(db, object_id, bytes(row["payload"]))

    def _backfill_parity(self, batch: int = 256) -> int:
        """Give verified objects written without parity (older stores) a sidecar.

        Objects are read and encoded outside the write lock; each batch is
        written in one ``BEGIN IMMEDIATE`` transaction that re-checks the
        payload digest and that no sidecar appeared meanwhile. Returns the
        number of sidecars written.
        """
        written = 0
        after = ""
        while True:
            with self._connect() as db:
                rows = db.execute(
                    "SELECT o.object_id, o.payload FROM objects AS o "
                    "LEFT JOIN object_parity AS p USING (object_id) "
                    "WHERE p.object_id IS NULL AND o.size_bytes <= ? AND o.object_id > ? "
                    "ORDER BY o.object_id LIMIT ?",
                    (self.self_healing_max_bytes, after, batch),
                ).fetchall()
            if not rows:
                return written
            after = str(rows[-1]["object_id"])
            candidates = [
                (str(r["object_id"]), bytes(r["payload"]))
                for r in rows
                if hashlib.sha256(bytes(r["payload"])).hexdigest() == r["object_id"]
            ]
            encoded = [(oid, payload, self_heal.encode_parity(payload)) for oid, payload in candidates]
            with self._lock, self._connect(immediate=True) as db:
                for oid, payload, parity in encoded:
                    if db.execute("SELECT 1 FROM object_parity WHERE object_id=?", (oid,)).fetchone():
                        continue
                    now = db.execute("SELECT payload FROM objects WHERE object_id=?", (oid,)).fetchone()
                    if now is None or bytes(now["payload"]) != payload:
                        continue
                    self._ensure_parity(db, oid, payload, parity)
                    self._log_heal(db, oid, "PARITY_BACKFILLED", 0,
                                   "verified object written before parity existed")
                    written += 1
            if len(rows) < batch:
                return written

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
            "self_healing": self.self_healing_status(),
            "stats": self.stats(),
            "checkpoint": self.checkpoint(),
        }
