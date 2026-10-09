"""Measured, bounded optimisation lifecycle for the production mining loop.

This controller never predicts a mining result. It admits only completed
execution windows, compares useful work per wall-clock second, and owns the
trial/accept/rollback lifecycle for mutable window-size changes. Consensus
verification and pool acknowledgement remain outside this module.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from Intelligence.lucas_scales import ladder_capacity

from .software_revision import software_revision

# LUCAS_SCALED (lemma_lucas_universal): retention/cadence envelopes are
# ladder stops. min_samples/cooldown_windows/max_attempts are control
# bounds and stay raw.
_SAMPLE_RETENTION = ladder_capacity(32)
_HISTORY_RETENTION = ladder_capacity(64)
_PERSIST_EVERY = ladder_capacity(16)

SCHEMA = "pythia.closed-loop-optimisation/1"


class ActionClass(StrEnum):
    SAFE_AUTOMATIC = "SAFE_AUTOMATIC"
    BOUNDED_EXPERIMENT = "BOUNDED_EXPERIMENT"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"
    FORBIDDEN = "FORBIDDEN"


@dataclass(frozen=True)
class OptimizationEvent:
    event: str
    route: str
    baseline_window: int
    candidate_window: int | None
    baseline_rate: float | None
    candidate_rate: float | None
    accepted: bool | None
    rollback: bool
    reason: str
    at: float
    software_revision: str | None = None
    implementation: str = SCHEMA


class ClosedLoopOptimizer:
    """One-at-a-time bounded trials with measured acceptance and rollback."""

    def __init__(
        self,
        *,
        min_samples: int = 3,
        min_improvement: float = 0.02,
        cooldown_windows: int = 4,
        max_attempts: int = 2,
        state_path: str | Path | None = None,
        evidence_source: str = "measured execution observation",
    ) -> None:
        if min_samples < 2 or not 0 <= min_improvement <= 1:
            raise ValueError("invalid optimisation evidence bounds")
        if cooldown_windows < 0 or max_attempts <= 0:
            raise ValueError("invalid anti-flapping bounds")
        self.min_samples = min_samples
        self.min_improvement = min_improvement
        self.cooldown_windows = cooldown_windows
        self.max_attempts = max_attempts
        if not evidence_source:
            raise ValueError("evidence_source is required")
        self.evidence_source = evidence_source
        self.state_path = Path(state_path) if state_path else None
        self.active: dict[str, int] = {}
        self.samples: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=_SAMPLE_RETENTION))
        self.cooldown: dict[str, int] = defaultdict(int)
        self.attempts: dict[str, int] = defaultdict(int)
        self._software_revision = software_revision()
        self.trial: dict[str, Any] | None = None
        self.history: deque[OptimizationEvent] = deque(maxlen=_HISTORY_RETENTION)
        self.last_observation: dict[str, Any] | None = None
        if self.state_path is not None:
            self.load()

    @staticmethod
    def _key(route: str, window: int) -> str:
        return f"{route}:{int(window)}"

    @staticmethod
    def _mean(values: list[float] | deque[float]) -> float | None:
        return sum(values) / len(values) if values else None

    def set_state_path(self, path: str | Path) -> None:
        self.state_path = Path(path)
        self.load()

    def select(
        self,
        *,
        route: str,
        proposed_window: int,
        safety_override: bool = False,
        reason: str = "operating policy",
    ) -> int:
        """Return the only window the runtime is authorised to execute next."""
        proposed = max(1, int(proposed_window))
        current = self.active.setdefault(route, proposed)
        if safety_override:
            if self.trial is not None and self.trial["route"] == route:
                self._finish(False, None, "safety override aborted trial")
            self.active[route] = min(current, proposed)
            self._persist()
            return self.active[route]
        if self.trial is not None:
            return int(self.trial["candidate"] if self.trial["route"] == route else current)
        if proposed == current or self.cooldown[route] > 0:
            return current
        baseline = self.samples[self._key(route, current)]
        pair = f"{route}:{current}->{proposed}"
        if len(baseline) < self.min_samples or self.attempts[pair] >= self.max_attempts:
            return current
        self.attempts[pair] += 1
        self.trial = {
            "route": route,
            "baseline": current,
            "candidate": proposed,
            "baseline_rate": self._mean(baseline),
            "candidate_rates": [],
            "reason": reason,
            "started_at": time.time(),
            "action_class": ActionClass.BOUNDED_EXPERIMENT.value,
        }
        self.history.append(
            OptimizationEvent(
                "TRIAL_STARTED",
                route,
                current,
                proposed,
                self._mean(baseline),
                None,
                None,
                False,
                reason,
                time.time(),
                self._software_revision,
            )
        )
        self._persist()
        return proposed

    def observe(
        self,
        *,
        route: str,
        planned_window: int,
        completed_work: int,
        elapsed_seconds: float,
        completion_state: str,
        device_error: str | None = None,
        executed_route: str | None = None,
    ) -> None:
        """Consume one real execution outcome and settle a trial when bounded."""
        if self.cooldown[route] > 0:
            self.cooldown[route] -= 1
        route_matched = executed_route is None or executed_route == route
        measurable = (
            route_matched
            and completion_state in {"COMPLETE", "FALLBACK_COMPLETE"}
            and completed_work == planned_window
            and completed_work > 0
            and elapsed_seconds > 0
            and device_error is None
        )
        rate = completed_work / elapsed_seconds if measurable else None
        self.last_observation = {
            "route": route,
            "planned_window": planned_window,
            "completed_work": completed_work,
            "elapsed_seconds": elapsed_seconds,
            "completion_state": completion_state,
            "device_error": device_error,
            "executed_route": executed_route or route,
            "useful_work_per_second": rate if rate is not None else "Unavailable",
        }
        if self.trial is not None and self.trial["route"] == route:
            if planned_window != self.trial["candidate"]:
                return
            if not route_matched:
                self._finish(
                    False,
                    None,
                    f"candidate route fell back from {route} to {executed_route}",
                )
                return
            if device_error is not None or completion_state == "DEVICE_ERROR":
                self._finish(
                    False, None, f"candidate execution failed: {device_error or completion_state}"
                )
                return
            if rate is None:
                return
            self.trial["candidate_rates"].append(rate)
            if len(self.trial["candidate_rates"]) >= self.min_samples:
                candidate = self._mean(self.trial["candidate_rates"])
                baseline = float(self.trial["baseline_rate"])
                accepted = candidate >= baseline * (1.0 + self.min_improvement)
                self._finish(
                    accepted,
                    candidate,
                    (
                        f"measured gain {(candidate / baseline - 1.0):.2%} met threshold"
                        if accepted
                        else f"measured gain {(candidate / baseline - 1.0):.2%} below threshold"
                    ),
                )
            return
        if rate is not None and planned_window == self.active.get(route):
            values = self.samples[self._key(route, planned_window)]
            values.append(rate)
            # Avoid an fsync on every mining window. Persist once the baseline
            # first becomes trial-eligible and then in bounded checkpoints.
            if len(values) == self.min_samples or len(values) % _PERSIST_EVERY == 0:
                self._persist()

    def fail_closed(self, route: str, reason: str) -> int | None:
        """Rollback an open mutable trial after a runtime fault."""
        if self.trial is not None and self.trial["route"] == route:
            baseline = int(self.trial["baseline"])
            self._finish(False, None, reason)
            return baseline
        return self.active.get(route)

    def _finish(self, accepted: bool, candidate_rate: float | None, reason: str) -> None:
        assert self.trial is not None
        trial = self.trial
        route = str(trial["route"])
        baseline = int(trial["baseline"])
        candidate = int(trial["candidate"])
        self.active[route] = candidate if accepted else baseline
        if accepted and candidate_rate is not None:
            self.samples[self._key(route, candidate)].extend(trial["candidate_rates"])
        self.cooldown[route] = self.cooldown_windows
        self.history.append(
            OptimizationEvent(
                "ACCEPTED" if accepted else "ROLLED_BACK",
                route,
                baseline,
                candidate,
                float(trial["baseline_rate"]),
                candidate_rate,
                accepted,
                not accepted,
                reason,
                time.time(),
                self._software_revision,
            )
        )
        self.trial = None
        self._persist()

    def snapshot(self) -> dict[str, Any]:
        last = asdict(self.history[-1]) if self.history else None
        return {
            "schema": SCHEMA,
            "status": "TRIAL" if self.trial else "MONITORING",
            "software_revision": self._software_revision,
            "action_class": (
                self.trial["action_class"] if self.trial else ActionClass.SAFE_AUTOMATIC.value
            ),
            "current_configuration": dict(self.active),
            "trial": dict(self.trial) if self.trial else None,
            "last_event": last or "Unavailable",
            "last_observation": self.last_observation or "Unavailable",
            "cooldown_windows": dict(self.cooldown),
            "minimum_samples": self.min_samples,
            "minimum_improvement": self.min_improvement,
            "evidence_source": self.evidence_source,
        }

    def _body(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "config": {
                "min_samples": self.min_samples,
                "min_improvement": self.min_improvement,
                "cooldown_windows": self.cooldown_windows,
                "max_attempts": self.max_attempts,
                "evidence_source": self.evidence_source,
            },
            "active": self.active,
            "samples": {k: list(v) for k, v in self.samples.items()},
            "cooldown": dict(self.cooldown),
            "attempts": dict(self.attempts),
            "history": [asdict(e) for e in self.history],
            # Trials are deliberately not resumed across process loss.
            "trial": None,
        }

    def _persist(self) -> None:
        if self.state_path is None:
            return
        body = self._body()
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
        envelope = {"body": body, "sha256": hashlib.sha256(canonical.encode()).hexdigest()}
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_name(self.state_path.name + ".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(envelope, handle, sort_keys=True, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.state_path)
        try:
            os.chmod(self.state_path, 0o600)
        except OSError:
            pass

    def load(self) -> bool:
        if self.state_path is None or not self.state_path.exists():
            return False
        try:
            envelope = json.loads(self.state_path.read_text(encoding="utf-8"))
            body = envelope["body"]
            canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
            if (
                body.get("schema") != SCHEMA
                or envelope.get("sha256") != hashlib.sha256(canonical.encode()).hexdigest()
            ):
                raise ValueError("optimisation state integrity failure")
            config = body.get("config", {})
            self.min_samples = int(config.get("min_samples", self.min_samples))
            self.min_improvement = float(config.get("min_improvement", self.min_improvement))
            self.cooldown_windows = int(config.get("cooldown_windows", self.cooldown_windows))
            self.max_attempts = int(config.get("max_attempts", self.max_attempts))
            self.evidence_source = str(config.get("evidence_source", self.evidence_source))
            if (
                self.min_samples < 2
                or not 0 <= self.min_improvement <= 1
                or self.cooldown_windows < 0
                or self.max_attempts <= 0
                or not self.evidence_source
            ):
                raise ValueError("persisted optimisation bounds are invalid")
            self.active = {str(k): int(v) for k, v in body.get("active", {}).items()}
            self.samples = defaultdict(lambda: deque(maxlen=_SAMPLE_RETENTION))
            for key, values in body.get("samples", {}).items():
                self.samples[str(key)].extend(float(v) for v in values[-_SAMPLE_RETENTION:])
            self.cooldown = defaultdict(
                int, {str(k): int(v) for k, v in body.get("cooldown", {}).items()}
            )
            self.attempts = defaultdict(
                int, {str(k): int(v) for k, v in body.get("attempts", {}).items()}
            )
            self.history = deque(
                (OptimizationEvent(**item) for item in body.get("history", [])), maxlen=64
            )
            self.trial = None
            return True
        except Exception:
            self.active, self.trial = {}, None
            self.samples = defaultdict(lambda: deque(maxlen=_SAMPLE_RETENTION))
            self.history = deque(maxlen=_HISTORY_RETENTION)
            return False
