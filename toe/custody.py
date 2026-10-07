"""Durable TOE learning state through THESEUS custody.

Authority split: TOE owns what a snapshot *means* (world-model revisions,
decision/outcome bindings, calibration, memory, contradictions, negative
results); THESEUS owns durable custody (journalled writes, primary +
replica, digest verification, recovery). TOE keeps no private store — when
no custody is bound, persistence is UNAVAILABLE and the machine reports it
instead of pretending to remember.

Snapshots form an append-only hash chain inside custody: record
``toe-<stream>-<revision>`` carries the digest of its parent snapshot and
the parent record id as THESEUS lineage. Recovery lists the stream,
re-verifies every link, and returns the head. A broken or forged chain
raises :class:`SnapshotIntegrityError` — a restart never silently falls back
to a newborn model.

The custody object is injected (any THESEUS ``EnterpriseCustody``-shaped
object exposing ``put_record`` / ``get_record`` / ``list_records``); TOE
never constructs keys or chooses where custody lives.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Optional

SNAPSHOT_KIND = "toe.machine.snapshot"
SNAPSHOT_SCHEMA = "toe.snapshot/v1"
PRODUCER = "toe"


class CustodyUnavailable(RuntimeError):
    """No THESEUS custody is bound/importable; persistence is unavailable."""


class SnapshotIntegrityError(RuntimeError):
    """The stored snapshot chain failed verification — fail closed."""


def theseus_available() -> bool:
    """True when the THESEUS enterprise custody implementation is importable."""
    try:
        from aethel.enterprise import custody as _custody  # noqa: F401
        from aethel.enterprise import records as _records  # noqa: F401
    except Exception:
        return False
    return True


def open_theseus_custody(root: Any, *, hmac_key: bytes, tenant: str = "toe", **kwargs: Any) -> Any:
    """Bind THESEUS enterprise custody at ``root`` (keys come from the caller)."""
    if not theseus_available():
        raise CustodyUnavailable(
            "aethel.enterprise.custody (THESEUS) is not importable; TOE persistence "
            "is UNAVAILABLE on this host (no private substitute store is permitted)"
        )
    from aethel.enterprise.custody import EnterpriseCustody

    return EnterpriseCustody(root, tenant=tenant, hmac_key=hmac_key, **kwargs)


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _safe_stream(stream: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "_", str(stream))
    if not cleaned:
        raise ValueError("snapshot stream name is empty")
    return cleaned


class SnapshotStore:
    """Append-only, hash-chained TOE snapshots held by THESEUS."""

    def __init__(self, custody: Any, *, stream: str = "default") -> None:
        for method in ("put_record", "get_record", "list_records"):
            if not callable(getattr(custody, method, None)):
                raise CustodyUnavailable(f"custody object lacks {method}(); not a THESEUS custody")
        self.custody = custody
        self.stream = _safe_stream(stream)
        self._prefix = f"toe-{self.stream}-"

    def _record_id(self, revision: int) -> str:
        return f"{self._prefix}{revision:08d}"

    def chain(self) -> List[Dict[str, Any]]:
        """Stream records known to custody, oldest first."""
        out = []
        for row in self.custody.list_records():
            rid = str(row.get("record_id", ""))
            if row.get("producer") != PRODUCER or row.get("kind") != SNAPSHOT_KIND:
                continue
            if not rid.startswith(self._prefix):
                continue
            tail = rid[len(self._prefix) :]
            if tail.isdigit():
                out.append({"record_id": rid, "revision": int(tail)})
        return sorted(out, key=lambda r: r["revision"])

    def load_head(self) -> Optional[Dict[str, Any]]:
        """Verify the whole chain and return the newest snapshot envelope.

        Returns ``None`` only when the stream has never been written. Any
        gap, digest mismatch or parent mismatch raises.
        """
        links = self.chain()
        if not links:
            return None
        parent_digest: Optional[str] = None
        envelope: Optional[Dict[str, Any]] = None
        for expected, link in enumerate(links, start=1):
            if link["revision"] != expected:
                raise SnapshotIntegrityError(
                    f"snapshot chain gap: expected revision {expected}, found {link['revision']}"
                )
            record = self.custody.get_record(link["record_id"])
            payload = bytes(record.payload)
            if hashlib.sha256(payload).hexdigest() != record.content_digest:
                raise SnapshotIntegrityError(f"{link['record_id']}: payload digest mismatch")
            try:
                envelope = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise SnapshotIntegrityError(
                    f"{link['record_id']}: unreadable snapshot: {exc}"
                ) from exc
            body = {
                k: envelope[k]
                for k in ("schema", "stream", "revision", "parent_digest", "toe_version", "payload")
            }
            if envelope.get("digest") != hashlib.sha256(_canonical(body)).hexdigest():
                raise SnapshotIntegrityError(f"{link['record_id']}: envelope digest mismatch")
            if envelope.get("schema") != SNAPSHOT_SCHEMA or envelope.get("stream") != self.stream:
                raise SnapshotIntegrityError(f"{link['record_id']}: foreign snapshot schema/stream")
            if (
                envelope.get("revision") != expected
                or envelope.get("parent_digest") != parent_digest
            ):
                raise SnapshotIntegrityError(f"{link['record_id']}: broken parent link")
            parent_digest = envelope["digest"]
        assert envelope is not None
        envelope["record_id"] = links[-1]["record_id"]
        return envelope

    def commit(self, payload: Dict[str, Any], *, toe_version: str) -> Dict[str, Any]:
        """Append one snapshot (the next revision) to the chain."""
        try:
            from aethel.enterprise.records import OperationalRecord
        except ImportError as exc:
            raise CustodyUnavailable(
                "THESEUS OperationalRecord contract is not importable; cannot commit"
            ) from exc

        head = self.load_head()
        revision = 1 if head is None else int(head["revision"]) + 1
        body = {
            "schema": SNAPSHOT_SCHEMA,
            "stream": self.stream,
            "revision": revision,
            "parent_digest": None if head is None else head["digest"],
            "toe_version": toe_version,
            "payload": payload,
        }
        envelope = {**body, "digest": hashlib.sha256(_canonical(body)).hexdigest()}
        data = _canonical(envelope)
        record = OperationalRecord(
            record_id=self._record_id(revision),
            producer=PRODUCER,
            producer_version=toe_version,
            schema_version=1,
            kind=SNAPSHOT_KIND,
            payload=data,
            evidence_state="MEASURED",
            sequence=revision,
            lineage=(() if head is None else (head["record_id"],)),
            correlation_ids={"stream": self.stream},
            meta={"revision": revision, "snapshot_digest": envelope["digest"]},
        )
        self.custody.put_record(record)
        return {
            "record_id": record.record_id,
            "revision": revision,
            "snapshot_digest": envelope["digest"],
            "parent_digest": body["parent_digest"],
            "content_digest": record.content_digest,
            "custody": "theseus",
        }


__all__ = [
    "CustodyUnavailable",
    "PRODUCER",
    "SNAPSHOT_KIND",
    "SNAPSHOT_SCHEMA",
    "SnapshotIntegrityError",
    "SnapshotStore",
    "open_theseus_custody",
    "theseus_available",
]
