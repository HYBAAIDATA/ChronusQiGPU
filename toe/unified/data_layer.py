"""Single data layer: batch and stream ingest, quality, governance, audit."""

from __future__ import annotations

import hashlib
import json
import math
import threading
import time
import zlib
from dataclasses import dataclass
from typing import Any, Mapping


def _canonical(row: Mapping[str, Any]) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"), default=str)


def _digest(row: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(row).encode("utf-8")).hexdigest()


@dataclass
class Record:
    source: str
    entity: str
    payload: dict
    digest: str
    batch_id: str
    operator_digest: str
    ingested_at: float
    quarantined: bool = False


@dataclass
class Policy:
    entity: str
    classification: str
    retention_days: int
    owner: str
    max_null_rate: float = 0.2

    def __post_init__(self) -> None:
        if self.classification not in ("public", "internal", "restricted"):
            raise ValueError("classification must be public, internal, or restricted")
        if self.retention_days < 0:
            raise ValueError("retention_days must be >= 0")


@dataclass
class IngestReceipt:
    batch_id: str
    source: str
    entity: str
    received: int
    inserted: int
    duplicates: int
    operator_digest: str
    operator_kind: str


@dataclass
class QualityReport:
    entity: str | None
    rows: int
    quarantined: int
    null_rate: float
    duplicate_rate: float
    fields: dict


class UnifiedDataLayer:
    def __init__(self) -> None:
        self._records: dict[str, Record] = {}
        self._policies: dict[str, Policy] = {}
        self.audit: list[dict] = []
        self._batch = 0
        self._lock = threading.Lock()
        self._by_entity: dict[str, list[str]] = {}
        self._blobs: dict[str, bytes] = {}
        self.raw_bytes = 0
        self.stored_bytes = 0
        self.index_visits = 0
        self.scan_visits = 0
        self.row_audit: list[str] = []
        # Every payload a batch presented — duplicates included. Batch
        # quality (null rate) is a property of what was received, not just
        # of the novel rows that landed.
        self._batch_payloads: dict[str, list[dict]] = {}

    def set_policy(self, policy: Policy) -> Policy:
        with self._lock:
            self._policies[policy.entity] = policy
            self._audit("policy", policy.entity, {"classification": policy.classification})
        return policy

    def policy_for(self, entity: str) -> Policy:
        return self._policies.get(
            entity, Policy(entity=entity, classification="internal", retention_days=365, owner="unassigned")
        )

    def ingest(
        self,
        source: str,
        entity: str,
        rows: list[Mapping[str, Any]],
        *,
        operator_digest: str,
        operator_kind: str,
    ) -> IngestReceipt:
        for row in rows:
            if not isinstance(row, Mapping):
                raise TypeError("every row must be an object")
        with self._lock:
            self._batch += 1
            batch_id = f"b{self._batch}"
            inserted = 0
            duplicates = 0
            now = time.time()
            batch_received = self._batch_payloads.setdefault(batch_id, [])
            for row in rows:
                payload = dict(row)
                batch_received.append(payload)
                digest = _digest({"source": source, "entity": entity, "payload": payload})
                if digest in self._records:
                    duplicates += 1
                    continue
                raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
                blob = zlib.compress(raw, level=9)
                self._blobs[digest] = blob
                self.raw_bytes += len(raw)
                self.stored_bytes += len(blob)
                self._records[digest] = Record(
                    source=source,
                    entity=entity,
                    payload=payload,
                    digest=digest,
                    batch_id=batch_id,
                    operator_digest=operator_digest,
                    ingested_at=now,
                )
                self._by_entity.setdefault(entity.casefold(), []).append(digest)
                self.row_audit.append(digest)
                inserted += 1
            self._audit("ingest", entity, {"source": source, "batch_id": batch_id, "inserted": inserted})
            return IngestReceipt(
                batch_id=batch_id,
                source=source,
                entity=entity,
                received=len(rows),
                inserted=inserted,
                duplicates=duplicates,
                operator_digest=operator_digest,
                operator_kind=operator_kind,
            )

    def quarantine_payloads(self, rows: list[tuple[str, str, dict]]) -> int:
        """Mark already-ingested records quarantined by (source, entity, payload)."""
        with self._lock:
            count = 0
            for source, entity, payload in rows:
                digest = _digest({"source": source, "entity": entity, "payload": dict(payload)})
                record = self._records.get(digest)
                if record is not None and not record.quarantined:
                    record.quarantined = True
                    count += 1
            self._audit("quarantine", "payloads", {"rows": count})
            return count

    def quarantine(self, batch_id: str) -> int:
        with self._lock:
            count = 0
            for record in self._records.values():
                if record.batch_id == batch_id and not record.quarantined:
                    record.quarantined = True
                    count += 1
            self._audit("quarantine", batch_id, {"rows": count})
            return count

    def release(self, batch_id: str) -> int:
        with self._lock:
            count = 0
            for record in self._records.values():
                if record.batch_id == batch_id and record.quarantined:
                    record.quarantined = False
                    count += 1
            self._audit("release", batch_id, {"rows": count})
            return count

    def snapshot(self) -> list[dict]:
        with self._lock:
            rows = [
                {
                    "source": record.source,
                    "entity": record.entity,
                    "payload": dict(record.payload),
                    "digest": record.digest,
                    "operator_digest": record.operator_digest,
                    "quarantined": record.quarantined,
                }
                for record in self._records.values()
            ]
        return sorted(rows, key=lambda row: row["digest"])

    def rows(self, entity: str, *, include_quarantined: bool = False) -> list[Record]:
        self._audit("read", entity, {})
        key = entity.casefold()
        # Iterate under _lock — the monitor thread calls in while ingest
        # mutates _records/_by_entity on the caller's thread.
        with self._lock:
            digests = list(self._by_entity.get(key, []))
            self.index_visits += len(digests)
            return [
                self._records[digest]
                for digest in digests
                if include_quarantined or not self._records[digest].quarantined
            ]

    def scan_rows(self, entity: str) -> list[Record]:
        with self._lock:
            self.scan_visits += len(self._records)
            return [
                record
                for record in self._records.values()
                if _same(record.entity, entity) and not record.quarantined
            ]

    def storage_ratio(self) -> float:
        if self.stored_bytes == 0:
            return 1.0
        return self.raw_bytes / self.stored_bytes

    def restore_payload(self, digest: str) -> dict:
        raw = zlib.decompress(self._blobs[digest])
        return json.loads(raw.decode("utf-8"))

    def quality(self, entity: str | None = None) -> QualityReport:
        with self._lock:
            chosen = [
                record
                for record in self._records.values()
                if entity is None or _same(record.entity, entity)
            ]
        if not chosen:
            return QualityReport(entity, 0, 0, 0.0, 0.0, {})
        fields: dict[str, dict] = {}
        nulls = 0
        cells = 0
        for record in chosen:
            for key, value in record.payload.items():
                stat = fields.setdefault(key, {"present": 0, "null": 0, "types": {}})
                stat["present"] += 1
                cells += 1
                if value is None or value == "":
                    stat["null"] += 1
                    nulls += 1
                else:
                    stat["types"][type(value).__name__] = stat["types"].get(type(value).__name__, 0) + 1
        received = sum(1 for _ in chosen)
        quarantined = sum(1 for record in chosen if record.quarantined)
        duplicate_rate = 0.0
        return QualityReport(
            entity=entity,
            rows=received,
            quarantined=quarantined,
            null_rate=(nulls / cells) if cells else 0.0,
            duplicate_rate=duplicate_rate,
            fields=fields,
        )

    def aggregate(
        self,
        entity: str,
        metric: str,
        dimension: str | None = None,
        where: tuple[tuple[str, str, Any], ...] = (),
    ) -> list[dict]:
        grouped: dict[Any, list[float]] = {}
        counts: dict[Any, int] = {}
        for record in self.rows(entity):
            payload = record.payload
            if not _matches(payload, where):
                continue
            key = payload.get(dimension) if dimension else None
            counts[key] = counts.get(key, 0) + 1
            if metric != "count":
                value = payload.get(metric)
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    continue
                grouped.setdefault(key, []).append(float(value))
        results = []
        keys = set(counts) | set(grouped)
        for key in sorted(keys, key=lambda item: (item is None, str(item))):
            if metric == "count":
                value = counts.get(key, 0)
            else:
                series = grouped.get(key) or []
                value = sum(series) if series else 0.0
            results.append({dimension or "all": key, metric: value, "rows": counts.get(key, 0)})
        if not results and metric == "count":
            results.append({dimension or "all": None, metric: 0, "rows": 0})
        return results

    def batch_null_rate(self, batch_id: str) -> float:
        # Score every payload the batch carried — a duplicate row still
        # counts toward the receiving batch's quality even though it lands
        # under its original batch id.
        with self._lock:
            payloads = self._batch_payloads.get(batch_id)
            if payloads is None:
                chosen = [record for record in self._records.values() if record.batch_id == batch_id]
                payloads = [record.payload for record in chosen]
        cells = 0
        nulls = 0
        for payload in payloads:
            for value in payload.values():
                cells += 1
                if value is None or value == "":
                    nulls += 1
        return (nulls / cells) if cells else 0.0

    def _audit(self, action: str, subject: str, detail: Mapping[str, Any]) -> None:
        self.audit.append({"action": action, "subject": subject, "detail": dict(detail), "at": time.time()})


def _same(left: str | None, right: str | None) -> bool:
    if left is None or right is None:
        return left == right
    return left.casefold() == right.casefold()


def _matches(payload: Mapping[str, Any], where: tuple[tuple[str, str, Any], ...]) -> bool:
    for field_name, op, expected in where:
        actual = payload.get(field_name)
        if op == "=" and actual != expected:
            return False
        if op == "!=" and actual == expected:
            return False
        if op in (">", ">=", "<", "<="):
            if not isinstance(actual, (int, float)) or isinstance(actual, bool):
                return False
            # A non-numeric bound would compare float against str — the query
            # contract is a QueryError, not an uncaught TypeError.  Deferred
            # import: bi.py depends on this module, so the name resolves at
            # call time.
            if not isinstance(expected, (int, float)) or isinstance(expected, bool):
                from .bi import QueryError

                raise QueryError(f"ordered comparison {op} requires a numeric bound, got {expected!r}")
            if op == ">" and not actual > expected:
                return False
            if op == ">=" and not actual >= expected:
                return False
            if op == "<" and not actual < expected:
                return False
            if op == "<=" and not actual <= expected:
                return False
    return True
