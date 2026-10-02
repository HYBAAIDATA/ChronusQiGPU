"""Causal coordinate system for the mining voyage.

Every meaningful transition is located by one ``CausalCoordinate``:

    pool_session_id → generation → job_fingerprint → toe_frame_id
    → plan_id → lease_id → execution_id → candidate_id → submission_id
    → learning_record_id                              (+ recovery_id)

Upstream ids are always present when a downstream id is, so any id can be
traced back to the Stratum session that authorised the work. The ledger is
bounded in memory and optionally mirrored to an append-only JSONL file for
replay and audit. It records evidence; it never decides anything.
"""

from __future__ import annotations

import itertools
import json
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Any, Deque, Iterable

from .software_revision import software_revision

_AXES = (
    "pool_session_id",
    "generation",
    "job_fingerprint",
    "toe_frame_id",
    "plan_id",
    "lease_id",
    "execution_id",
    "candidate_id",
    "submission_id",
    "recovery_id",
    "learning_record_id",
)


@dataclass(frozen=True)
class CausalCoordinate:
    pool_session_id: str | None = None
    generation: int | None = None
    job_fingerprint: str | None = None
    toe_frame_id: str | None = None
    plan_id: str | None = None
    lease_id: str | None = None
    execution_id: str | None = None
    candidate_id: str | None = None
    submission_id: str | None = None
    recovery_id: str | None = None
    learning_record_id: str | None = None
    job_id: str | None = None

    def extend(self, **axes: Any) -> "CausalCoordinate":
        unknown = set(axes) - set(_AXES)
        if unknown:
            raise ValueError(f"unknown causal axes: {sorted(unknown)}")
        return replace(self, **axes)

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}

    def contains(self, other: "CausalCoordinate") -> bool:
        """True when every axis set on ``other`` has the same value here."""
        return all(
            getattr(other, f.name) is None or getattr(other, f.name) == getattr(self, f.name)
            for f in fields(self)
        )


@dataclass(frozen=True)
class CausalEvent:
    seq: int
    at: float
    kind: str
    coordinate: CausalCoordinate
    detail: dict[str, Any]
    software_revision: str | None = None

    def as_dict(self) -> dict[str, Any]:
        record = {
            "seq": self.seq,
            "at": self.at,
            "kind": self.kind,
            "coordinate": self.coordinate.as_dict(),
            "detail": self.detail,
        }
        if self.software_revision is not None:
            record["software_revision"] = self.software_revision
        return record


class CausalLedger:
    """Bounded, append-only record of the voyage's causal history."""

    def __init__(
        self,
        *,
        capacity: int = 4096,
        path: str | Path | None = None,
        max_file_bytes: int = 32 * 1024 * 1024,
        revision: str | None = None,
    ) -> None:
        if capacity <= 0 or max_file_bytes <= 0:
            raise ValueError("ledger bounds must be positive")
        self._events: Deque[CausalEvent] = deque(maxlen=capacity)
        self._seq = itertools.count(1)
        self._lock = threading.Lock()
        self._path = Path(path) if path is not None else None
        self._max_file_bytes = max_file_bytes
        self._revision = revision if revision is not None else software_revision()
        self.file_errors = 0

    @property
    def software_revision(self) -> str:
        return self._revision

    def record(self, kind: str, coordinate: CausalCoordinate, **detail: Any) -> CausalEvent:
        with self._lock:
            event = CausalEvent(
                next(self._seq),
                time.time(),
                kind,
                coordinate,
                dict(detail),
                software_revision=self._revision,
            )
            self._events.append(event)
        self._mirror(event)
        return event

    def _mirror(self, event: CausalEvent) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            if self._path.exists() and self._path.stat().st_size >= self._max_file_bytes:
                self._path.replace(self._path.with_name(self._path.name + ".1"))
            with self._path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event.as_dict(), sort_keys=True, default=str) + "\n")
        except OSError:
            self.file_errors += 1

    def events(self) -> list[CausalEvent]:
        with self._lock:
            return list(self._events)

    def trace(self, **axes: Any) -> list[CausalEvent]:
        """The causal chain behind (and through) the event naming ``axes``.

        Returns every event whose coordinate is an ancestor of, or equal to,
        the most specific coordinate carrying the selector, in order.
        """
        selector = CausalCoordinate().extend(**axes)
        events = self.events()
        anchors = [e for e in events if e.coordinate.contains(selector)]
        if not anchors:
            return []
        deepest = max(anchors, key=lambda e: len(e.coordinate.as_dict())).coordinate
        return [
            e for e in events if deepest.contains(e.coordinate) or e.coordinate.contains(selector)
        ]

    def snapshot(self, limit: int = 32) -> list[dict[str, Any]]:
        return [event.as_dict() for event in self.events()[-limit:]]


def load_jsonl(lines: Iterable[str]) -> list[CausalEvent]:
    """Rebuild events from a JSONL mirror for offline replay."""
    events = []
    for line in lines:
        if not line.strip():
            continue
        raw = json.loads(line)
        events.append(
            CausalEvent(
                seq=int(raw["seq"]),
                at=float(raw["at"]),
                kind=str(raw["kind"]),
                coordinate=CausalCoordinate(**raw["coordinate"]),
                detail=dict(raw.get("detail", {})),
                software_revision=raw.get("software_revision"),
            )
        )
    return events
