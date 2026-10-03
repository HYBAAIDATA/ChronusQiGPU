"""Append-only telemetry history persisted by the mining worker (§7).

The Stratum event stream and the measured-hashing counters already flow
through canonical in-memory channels. This store is the smallest durable
projection over them: every observed Stratum event (job arrivals, state
transitions, difficulty/target changes, share outcomes, errors) plus a
bounded-rate hashrate sample, appended to a rotated JSONL file the control
API reads back for ``/api/v1/telemetry/history``.

Values are recorded as observed — nothing here derives, estimates, or
fabricates telemetry. Rotation mirrors the causal ledger policy: at
``max_bytes`` the file is renamed to ``<name>.1`` and a fresh file starts.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import time
from collections import deque
from pathlib import Path
from typing import Any, Iterable, Mapping

LOG = logging.getLogger(__name__)

SCHEMA = "pythia.telemetry_history/1"
DEFAULT_MAX_BYTES = 16 << 20
# ``hashrate`` counters publish every ~1s while mining; samples every 5s keep
# the series honest without dwarfing the discrete events.
DEFAULT_MIN_INTERVAL_S = {"hashrate": 5.0}


def default_history_path() -> str:
    return os.getenv("PYTHIA_TELEMETRY_HISTORY_PATH", "data/telemetry_history.jsonl")


class TelemetryHistory:
    """Append-only JSONL writer with per-kind rate bounds and rotation."""

    def __init__(
        self,
        path: str | os.PathLike[str] | None,
        *,
        max_bytes: int = DEFAULT_MAX_BYTES,
        min_interval_s: Mapping[str, float] | None = None,
        clock: Any = time.time,
    ) -> None:
        self.path = Path(path) if path else None
        self.max_bytes = max_bytes
        self._min_interval_s = dict(DEFAULT_MIN_INTERVAL_S)
        if min_interval_s:
            self._min_interval_s.update(min_interval_s)
        self._clock = clock
        self._last_kind_at: dict[str, float] = {}
        self._seq = 0
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def _allows(self, kind: str, now: float) -> bool:
        interval = self._min_interval_s.get(kind, 0.0)
        if interval <= 0:
            return True
        if now - self._last_kind_at.get(kind, float("-inf")) < interval:
            return False
        self._last_kind_at[kind] = now
        return True

    def _write(self, record: dict[str, Any]) -> None:
        if self.path is None:
            return
        line = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        try:
            if self.path.exists() and self.path.stat().st_size >= self.max_bytes:
                rotated = self.path.with_name(self.path.name + ".1")
                with contextlib.suppress(OSError):
                    rotated.unlink()
                with contextlib.suppress(OSError):
                    self.path.rename(rotated)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(line)
        except OSError:
            LOG.warning("telemetry history write failed: %s", self.path)

    def append(self, event: Mapping[str, Any]) -> dict[str, Any] | None:
        """Persist one observed Stratum event verbatim."""
        kind = str(event.get("kind", "event"))
        at = float(event.get("at", self._clock()))
        if not self._allows(kind, at):
            return None
        self._seq += 1
        record = {
            "seq": self._seq,
            "at": at,
            "kind": kind,
            "data": dict(event),
        }
        self._write(record)
        return record

    def record_metrics(self, counters: Mapping[str, Any]) -> dict[str, Any] | None:
        """Persist a measured-hashing sample, rate-bounded per kind."""
        now = self._clock()
        if not self._allows("hashrate", now):
            return None
        self._seq += 1
        record = {
            "seq": self._seq,
            "at": now,
            "kind": "hashrate",
            "data": dict(counters),
        }
        self._write(record)
        return record


def tail_history(
    path: str | os.PathLike[str] | None,
    limit: int,
    kinds: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Read the newest ``limit`` records of a persisted history file.

    The reader is read-only and tolerant: a missing or unreadable file
    returns an empty list so the API can report ``available=false`` instead
    of inventing history.
    """
    if not path or limit <= 0:
        return []
    wanted = set(kinds) if kinds else None
    records: deque[dict[str, Any]] = deque(maxlen=int(limit))
    try:
        with open(path, "rb") as stream:
            for line in stream:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(record, dict):
                    continue
                if wanted is not None and record.get("kind") not in wanted:
                    continue
                records.append(record)
    except OSError:
        return list(records)
    return list(records)


__all__ = [
    "TelemetryHistory",
    "tail_history",
    "default_history_path",
    "SCHEMA",
    "DEFAULT_MAX_BYTES",
]
