"""Evidence-first telemetry for Bitcoin's 2016-block retarget windows.

The tracker consumes canonical Stratum status snapshots. Pool-job BIP34
height is treated as pool-provided chain evidence (the same boundary used by
``PoolChainObserver``); no height is guessed when that evidence is absent.

Effective Stratum hashrate is derived only from *accepted* shares whose
negotiated share difficulty is known: ``sum(difficulty * 2**32) / elapsed``.
If even one accepted share lacks a numeric difficulty, the value remains
Unavailable (``None``) rather than reporting a partial estimate as truth.
"""

from __future__ import annotations

import json
import math
import os
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Mapping

RETARGET_BLOCKS = 2016
DIFF1_WORK = float(2**32)
SCHEMA = "pythia.retarget_windows/1"


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) and result > 0 else None


class RetargetWindowTracker:
    """Bounded persistent aggregate of measured pool work per retarget epoch."""

    def __init__(self, path: str | os.PathLike[str] | None, *, keep_windows: int = 8) -> None:
        if keep_windows <= 0:
            raise ValueError("keep_windows must be positive")
        self.path = Path(path) if path else None
        self.keep_windows = keep_windows
        self.windows: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._last_counters: dict[str, dict[str, int]] = {}
        self._last_stale: dict[str, int] = {}
        self._last_share_work: dict[str, tuple[float, int]] = {}
        self._load()

    def _load(self) -> None:
        if self.path is None or not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
            return
        raw = payload.get("windows", {})
        if not isinstance(raw, dict):
            return
        for key, value in raw.items():
            if isinstance(value, dict):
                self.windows[str(key)] = value
        while len(self.windows) > self.keep_windows:
            self.windows.popitem(last=False)

    def _persist(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": SCHEMA,
            "updated_at": time.time(),
            "windows": dict(self.windows),
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        os.replace(tmp, self.path)

    @staticmethod
    def _counter_map(snapshot: Mapping[str, Any]) -> dict[str, int]:
        counters = snapshot.get("counters", {})
        if not isinstance(counters, Mapping):
            return {"submitted": 0, "accepted": 0, "rejected": 0, "unknown": 0}
        return {
            name: max(0, int(counters.get(name, 0) or 0))
            for name in ("submitted", "accepted", "rejected", "unknown")
        }

    @staticmethod
    def _stale_count(snapshot: Mapping[str, Any]) -> int:
        outcomes = snapshot.get("outcomes", {})
        if not isinstance(outcomes, Mapping):
            return 0
        try:
            return max(0, int(outcomes.get("stale_dropped", 0) or 0))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _delta(current: int, previous: int) -> int:
        # A new client/session resets its counters. Session keys normally
        # prevent this case; fail closed to the current count if one is reused.
        return current - previous if current >= previous else current

    def observe(self, snapshot: Mapping[str, Any]) -> dict[str, Any] | None:
        job = snapshot.get("job", {})
        if not isinstance(job, Mapping):
            return self.snapshot()
        height = job.get("block_height")
        if type(height) is not int or height < 0:
            return self.snapshot()

        epoch = height // RETARGET_BLOCKS
        key = str(epoch)
        now = time.time()
        entry = self.windows.get(key)
        if entry is None:
            entry = {
                "epoch": epoch,
                "first_observed_at": now,
                "last_observed_at": now,
                "first_height": height,
                "last_height": height,
                "jobs": [],
                "submitted": 0,
                "accepted": 0,
                "rejected": 0,
                "unknown": 0,
                "stale": 0,
                "accepted_difficulty_work": 0.0,
                "accepted_without_difficulty": 0,
                "difficulty_min": None,
                "difficulty_max": None,
                "difficulty_last": None,
                "submit_rtt_last_ms": None,
            }
            self.windows[key] = entry
        self.windows.move_to_end(key)
        while len(self.windows) > self.keep_windows:
            self.windows.popitem(last=False)

        dirty = False
        if entry.get("last_height") != height:
            entry["last_height"] = height
            dirty = True
        entry["last_observed_at"] = now

        fingerprint = job.get("fingerprint")
        jobs = entry.setdefault("jobs", [])
        if isinstance(fingerprint, str) and fingerprint and fingerprint not in jobs:
            jobs.append(fingerprint)
            # A retarget epoch cannot contain more than 2016 canonical blocks;
            # allow some pool job churn while still bounding disk/memory use.
            if len(jobs) > RETARGET_BLOCKS * 2:
                del jobs[: len(jobs) - RETARGET_BLOCKS * 2]
            dirty = True

        difficulty = _number(job.get("difficulty"))
        if difficulty is not None:
            if entry.get("difficulty_last") != difficulty:
                entry["difficulty_last"] = difficulty
                current_min = entry.get("difficulty_min")
                current_max = entry.get("difficulty_max")
                entry["difficulty_min"] = (
                    difficulty if current_min is None else min(float(current_min), difficulty)
                )
                entry["difficulty_max"] = (
                    difficulty if current_max is None else max(float(current_max), difficulty)
                )
                dirty = True

        primary = snapshot.get("primary", {})
        pool_id = primary.get("pool_id") if isinstance(primary, Mapping) else None
        session_id = snapshot.get("session_id")
        if isinstance(pool_id, str) and isinstance(session_id, str) and session_id:
            session_key = f"{pool_id}:{session_id}"
            counters = self._counter_map(snapshot)
            previous = self._last_counters.get(
                session_key, {"submitted": 0, "accepted": 0, "rejected": 0, "unknown": 0}
            )
            deltas = {
                name: self._delta(counters[name], previous.get(name, 0))
                for name in counters
            }
            self._last_counters[session_key] = counters
            stale_now = self._stale_count(snapshot)
            stale_delta = self._delta(stale_now, self._last_stale.get(session_key, 0))
            self._last_stale[session_key] = stale_now
            if any(deltas.values()) or stale_delta:
                for name in ("submitted", "accepted", "rejected", "unknown"):
                    entry[name] = int(entry.get(name, 0)) + deltas[name]
                entry["stale"] = int(entry.get("stale", 0)) + stale_delta
                accepted_delta = deltas["accepted"]
                share_work = snapshot.get("share_work", {})
                work_bound = False
                if isinstance(share_work, Mapping):
                    try:
                        work_now = float(
                            share_work.get("accepted_difficulty_work", 0.0) or 0.0
                        )
                        missing_now = max(
                            0,
                            int(share_work.get("accepted_without_difficulty", 0) or 0),
                        )
                    except (TypeError, ValueError, OverflowError):
                        work_now = -1.0
                        missing_now = -1
                    if math.isfinite(work_now) and work_now >= 0 and missing_now >= 0:
                        previous_work, previous_missing = self._last_share_work.get(
                            session_key, (0.0, 0)
                        )
                        work_delta = (
                            work_now - previous_work
                            if work_now >= previous_work
                            else work_now
                        )
                        missing_delta = self._delta(missing_now, previous_missing)
                        self._last_share_work[session_key] = (work_now, missing_now)
                        entry["accepted_difficulty_work"] = float(
                            entry.get("accepted_difficulty_work", 0.0)
                        ) + work_delta
                        entry["accepted_without_difficulty"] = int(
                            entry.get("accepted_without_difficulty", 0)
                        ) + missing_delta
                        work_bound = True
                if accepted_delta and not work_bound:
                    # Compatibility fallback for older status producers.
                    if difficulty is None:
                        entry["accepted_without_difficulty"] = int(
                            entry.get("accepted_without_difficulty", 0)
                        ) + accepted_delta
                    else:
                        entry["accepted_difficulty_work"] = float(
                            entry.get("accepted_difficulty_work", 0.0)
                        ) + accepted_delta * difficulty
                dirty = True

        submission = snapshot.get("submission", {})
        if isinstance(submission, Mapping):
            rtt = submission.get("rtt_ms", {})
            if isinstance(rtt, Mapping):
                last_rtt = _number(rtt.get("last"))
                if last_rtt is not None and entry.get("submit_rtt_last_ms") != last_rtt:
                    entry["submit_rtt_last_ms"] = last_rtt
                    dirty = True

        if dirty:
            self._persist()
        return self.snapshot(height=height)

    def snapshot(self, *, height: int | None = None) -> dict[str, Any] | None:
        if height is None:
            if not self.windows:
                return None
            entry = next(reversed(self.windows.values()))
            height = int(entry.get("last_height", 0))
        else:
            entry = self.windows.get(str(height // RETARGET_BLOCKS))
            if entry is None:
                return None

        submitted = int(entry.get("submitted", 0) or 0)
        accepted = int(entry.get("accepted", 0) or 0)
        rejected = int(entry.get("rejected", 0) or 0)
        unknown = int(entry.get("unknown", 0) or 0)
        stale = int(entry.get("stale", 0) or 0)
        candidate_total = submitted + stale
        elapsed = max(
            0.0,
            float(entry.get("last_observed_at", 0)) - float(entry.get("first_observed_at", 0)),
        )
        unweighted = int(entry.get("accepted_without_difficulty", 0) or 0)
        difficulty_work = float(entry.get("accepted_difficulty_work", 0.0) or 0.0)
        effective = None
        if accepted > 0 and unweighted == 0 and elapsed > 0:
            effective = difficulty_work * DIFF1_WORK / elapsed

        next_retarget = ((height // RETARGET_BLOCKS) + 1) * RETARGET_BLOCKS
        return {
            "schema": SCHEMA,
            "epoch": height // RETARGET_BLOCKS,
            "block_height": height,
            "position": height % RETARGET_BLOCKS,
            "next_retarget_height": next_retarget,
            "blocks_until_next_retarget": next_retarget - height,
            "observed_jobs": len(entry.get("jobs", [])),
            "candidate_total": candidate_total,
            "submitted": submitted,
            "accepted": accepted,
            "rejected": rejected,
            "unknown": unknown,
            "stale": stale,
            "accepted_ratio": accepted / candidate_total if candidate_total else None,
            "rejected_ratio": rejected / candidate_total if candidate_total else None,
            "unknown_ratio": unknown / candidate_total if candidate_total else None,
            "stale_ratio": stale / candidate_total if candidate_total else None,
            "difficulty_min": entry.get("difficulty_min"),
            "difficulty_max": entry.get("difficulty_max"),
            "difficulty_last": entry.get("difficulty_last"),
            "submit_rtt_last_ms": entry.get("submit_rtt_last_ms"),
            "effective_stratum_hashrate_hs": effective,
            "effective_hashrate_complete": accepted > 0 and unweighted == 0,
            "accepted_without_difficulty": unweighted,
            "elapsed_observed_s": elapsed,
        }


__all__ = ["DIFF1_WORK", "RETARGET_BLOCKS", "RetargetWindowTracker"]
