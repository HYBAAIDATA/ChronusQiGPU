"""Bounded Stratum telemetry event stream derived from runtime snapshots.

The Stratum client publishes a full ``chronus.mla1517.stratum/1`` snapshot on every
session edge. This log turns consecutive snapshots into discrete events
(state transitions, new jobs, difficulty and target changes, share results,
errors) so the control plane can serve ``/api/v1/telemetry/events``.

Every value is copied from a snapshot the pool produced; nothing is derived
or estimated. Share totals survive reconnects: each new session starts its
counters at zero, and a counter that goes down is read as a new session.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Any, Callable, Mapping

SCHEMA = "pythia.telemetry_events/1"
_SHARE_COUNTERS = {"accepted": "ACCEPTED", "rejected": "REJECTED", "unknown": "OUTCOME_UNKNOWN"}
_TOTALS = ("jobs_received", "disconnects", "submitted", "accepted", "rejected", "unknown")


class StratumEventLog:
    def __init__(
        self,
        maxlen: int = 200,
        clock: Callable[[], float] = time.time,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self._events: deque[dict[str, Any]] = deque(maxlen=maxlen)
        self._clock = clock
        self._on_event = on_event
        self._seq = 0
        self._last: Mapping[str, Any] | None = None
        self._session_counters: dict[str, int] = {}
        self.totals = {name: 0 for name in _TOTALS}

    def _emit(self, kind: str, **fields: Any) -> None:
        self._seq += 1
        event = {"seq": self._seq, "at": self._clock(), "kind": kind, **fields}
        self._events.append(event)
        if self._on_event is not None:
            try:
                self._on_event(event)
            except Exception:
                pass

    def observe(self, snapshot: Mapping[str, Any]) -> None:
        primary = snapshot.get("primary") or {}
        job = snapshot.get("job") or {}
        submission = snapshot.get("submission") or {}
        counters = snapshot.get("counters") or {}
        last = self._last or {}
        last_primary = last.get("primary") or {}
        last_job = last.get("job") or {}

        state = snapshot.get("state")
        if state != last.get("state"):
            self._emit(
                "state",
                previous=last.get("state"),
                state=state,
                pool_id=primary.get("pool_id"),
                endpoint=primary.get("endpoint"),
                subscribed=primary.get("subscribed"),
                authorized=primary.get("authorized"),
            )
        error = primary.get("last_error")
        if error and error != last_primary.get("last_error"):
            self._emit("error", pool_id=primary.get("pool_id"), message=str(error))
        generation = job.get("generation")
        if (
            job.get("active")
            and generation is not None
            and (
                generation != last_job.get("generation")
                or job.get("job_id") != last_job.get("job_id")
            )
        ):
            self._emit(
                "job",
                job_id=job.get("job_id"),
                generation=generation,
                clean_jobs=job.get("clean_jobs"),
                difficulty=job.get("difficulty"),
                share_target=job.get("share_target"),
            )
        difficulty = job.get("difficulty")
        if difficulty is not None and difficulty != last_job.get("difficulty"):
            self._emit("difficulty", difficulty=difficulty, source=job.get("difficulty_source"))
        target = job.get("share_target")
        if target and target != last_job.get("share_target"):
            self._emit(
                "target", share_target=target, target_generation=job.get("target_generation")
            )

        for name in _TOTALS:
            try:
                value = int(counters.get(name) or 0)
            except (TypeError, ValueError):
                continue
            previous = self._session_counters.get(name, 0)
            delta = value - previous if value >= previous else value
            self._session_counters[name] = value
            if delta <= 0:
                continue
            self.totals[name] += delta
            if name in _SHARE_COUNTERS:
                self._emit(
                    "share",
                    result=_SHARE_COUNTERS[name],
                    count=delta,
                    job_id=submission.get("job_id"),
                    generation=submission.get("generation"),
                    total=self.totals[name],
                )
        self._last = snapshot

    def events(self) -> list[dict[str, Any]]:
        return list(self._events)

    def payload(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "last_seq": self._seq,
            "totals": dict(self.totals),
            "events": self.events(),
        }
