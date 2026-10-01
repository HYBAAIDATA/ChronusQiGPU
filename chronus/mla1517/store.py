from __future__ import annotations
import json
import sqlite3
import hashlib
from pathlib import Path
from .objects import MLAObject


class PrimeDB:
    """Durable reference PRIME-DB using SQLite WAL and content-addressed objects."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS objects (
            object_id TEXT PRIMARY KEY,
            family TEXT NOT NULL,
            scale INTEGER NOT NULL CHECK(scale > 0),
            sequence_index INTEGER NOT NULL CHECK(sequence_index > 0),
            prime_index INTEGER NOT NULL CHECK(prime_index > 0),
            payload_json TEXT NOT NULL,
            object_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        );
        CREATE INDEX IF NOT EXISTS idx_objects_family_scale ON objects(family, scale);
        CREATE INDEX IF NOT EXISTS idx_objects_prime ON objects(prime_index);
        CREATE TABLE IF NOT EXISTS exact_tensor_state (
            tensor_id TEXT PRIMARY KEY,
            payload BLOB NOT NULL,
            global_scale INTEGER NOT NULL CHECK(global_scale >= 0),
            amplitude_count INTEGER NOT NULL CHECK(amplitude_count > 0),
            byte_length INTEGER NOT NULL CHECK(byte_length > 0),
            sha256 TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        );
        """)
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def put(
        self, payload, sequence_index: int, scale: int = 15, family: str = "fibonacci"
    ) -> MLAObject:
        obj = MLAObject.create(payload, sequence_index, scale, family)
        obj.validate()
        encoded = json.dumps(
            obj.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        with self.db:
            self.db.execute(
                """
                INSERT OR IGNORE INTO objects(object_id,family,scale,sequence_index,prime_index,payload_json,object_json)
                VALUES(?,?,?,?,?,?,?)
            """,
                (
                    obj.object_id,
                    obj.family,
                    obj.scale,
                    obj.sequence_index,
                    obj.prime_index,
                    json.dumps(payload, sort_keys=True),
                    encoded,
                ),
            )
        return obj

    def get(self, object_id: str) -> MLAObject:
        row = self.db.execute(
            "SELECT object_json FROM objects WHERE object_id=?", (object_id,)
        ).fetchone()
        if row is None:
            raise KeyError(object_id)
        data = json.loads(row["object_json"])
        data["fibonacci_pair"] = tuple(data["fibonacci_pair"])
        if "exact_state" in data:
            data["exact_state"] = tuple(data["exact_state"])
        obj = MLAObject(**data)
        obj.validate()
        return obj

    def verify(self, object_id: str) -> dict[str, object]:
        obj = self.get(object_id)
        return {
            "object_id": object_id,
            "valid": True,
            "family": obj.family,
            "scale": obj.scale,
            "sequence_index": obj.sequence_index,
        }

    def count(self) -> int:
        return int(self.db.execute("SELECT COUNT(*) FROM objects").fetchone()[0])

    def put_exact_tensor(self, payload: bytes, global_scale: int) -> str:
        """Persist exact 32-byte (long4) amplitudes without truncation."""
        if (
            not isinstance(payload, (bytes, bytearray, memoryview))
            or len(payload) == 0
            or len(payload) % 32
        ):
            raise ValueError("exact tensor payload must be non-empty and a multiple of 32 bytes")
        if not isinstance(global_scale, int) or global_scale < 0:
            raise ValueError("global_scale must be a non-negative integer")
        raw = bytes(payload)
        tensor_id = hashlib.sha256(raw + global_scale.to_bytes(8, "little")).hexdigest()
        with self.db:
            self.db.execute(
                """INSERT OR IGNORE INTO exact_tensor_state
                   (tensor_id,payload,global_scale,amplitude_count,byte_length,sha256)
                   VALUES(?,?,?,?,?,?)""",
                (
                    tensor_id,
                    raw,
                    global_scale,
                    len(raw) // 32,
                    len(raw),
                    hashlib.sha256(raw).hexdigest(),
                ),
            )
        return tensor_id

    def get_exact_tensor(self, tensor_id: str) -> dict[str, object]:
        row = self.db.execute(
            "SELECT payload,global_scale,amplitude_count,byte_length,sha256 FROM exact_tensor_state WHERE tensor_id=?",
            (tensor_id,),
        ).fetchone()
        if row is None:
            raise KeyError(tensor_id)
        raw = bytes(row["payload"])
        if len(raw) != row["byte_length"] or len(raw) != row["amplitude_count"] * 32:
            raise ValueError("exact tensor length invariant failed")
        if hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError("exact tensor checksum invariant failed")
        return {
            "tensor_id": tensor_id,
            "payload": raw,
            "global_scale": row["global_scale"],
            "amplitude_count": row["amplitude_count"],
        }
