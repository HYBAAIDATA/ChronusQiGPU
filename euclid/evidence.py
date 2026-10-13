"""Append-only hash-linked evidence with atomic sealed checkpoints."""
from __future__ import annotations

import copy
import json
import threading
import os
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .contracts import canonical_json, domain_hash


@dataclass(frozen=True)
class EvidenceRecord:
    sequence: int
    timestamp: float
    kind: str
    payload: Mapping[str, Any]
    previous_hash: str | None
    record_hash: str


class EvidenceChain:
    def __init__(self, records: Iterable[EvidenceRecord] = ()) -> None:
        self._lock = threading.RLock()
        self._records = copy.deepcopy(list(records))
        self.verify()

    @property
    def records(self) -> tuple[EvidenceRecord, ...]:
        with self._lock:
            return tuple(copy.deepcopy(self._records))

    @property
    def head(self) -> str | None:
        with self._lock:
            return self._records[-1].record_hash if self._records else None

    def append(self, kind: str, payload: Mapping[str, Any]) -> EvidenceRecord:
        with self._lock:
            base = {
                "sequence": len(self._records),
                "timestamp": time.time(),
                "kind": str(kind),
                "payload": copy.deepcopy(dict(payload)),
                "previous_hash": self.head,
            }
            record = EvidenceRecord(**base, record_hash=domain_hash("euclid.evidence.v1", base))
            self._records.append(record)
            return copy.deepcopy(record)

    def verify(self) -> None:
        with self._lock:
            previous = None
            for sequence, record in enumerate(self._records):
                if record.sequence != sequence or record.previous_hash != previous:
                    raise ValueError("evidence chain is discontinuous")
                base = {
                    "sequence": record.sequence,
                    "timestamp": record.timestamp,
                    "kind": record.kind,
                    "payload": dict(record.payload),
                    "previous_hash": record.previous_hash,
                }
                if domain_hash("euclid.evidence.v1", base) != record.record_hash:
                    raise ValueError("evidence record hash mismatch")
                previous = record.record_hash

    def to_payload(self) -> dict[str, Any]:
        with self._lock:
            body = {"schema": "euclid.evidence/1", "records": [asdict(r) for r in self._records]}
            return {**body, "seal": domain_hash("euclid.evidence.seal.v1", body)}

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "EvidenceChain":
        body = {"schema": payload.get("schema"), "records": payload.get("records", [])}
        if body["schema"] != "euclid.evidence/1":
            raise ValueError("unsupported evidence schema")
        if payload.get("seal") != domain_hash("euclid.evidence.seal.v1", body):
            raise ValueError("evidence seal mismatch")
        return cls(EvidenceRecord(**record) for record in body["records"])


def atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        if hasattr(os, "fchmod"):
            # POSIX-only; os.chmod below covers Windows.
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(canonical_json(payload))
            handle.flush()
            os.fsync(handle.fileno())
        for attempt in range(6):
            try:
                os.replace(temporary, path)
                break
            except (PermissionError, OSError):
                if attempt == 5:
                    raise
                time.sleep(0.02 * (attempt + 1))
        if os.name != "nt":
            os.chmod(path, 0o600)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(temporary)
        except (FileNotFoundError, PermissionError):
            pass
        raise


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
