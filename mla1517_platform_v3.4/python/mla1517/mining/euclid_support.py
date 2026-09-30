"""EUCLID mining-support seam for the canonical production coordinator.

EUCLID is allowed to influence bounded operating policy only. This module is
intentionally downstream of Stratum/job truth and upstream of search breadth;
it cannot change Bitcoin headers, SHA256d, pool targets, proof validation,
submission parameters, credentials, or pool acknowledgement semantics.

The recovered EUCLID substrate is optional during staged convergence. A
missing package is reported as UNAVAILABLE and produces a neutral policy. It
is never represented as active merely because configuration names it.
"""
from __future__ import annotations

import math
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from .production_transport import ProductionMiningCoordinator


@dataclass(frozen=True)
class EuclidMiningAdvice:
    state: str
    action: str
    dispatch_breadth: int
    reason: str
    evidence: Mapping[str, Any]


class EuclidMiningSupport:
    """Evidence-first bridge from measured mining state to EUCLID learning.

    The action space is deliberately tiny: HOLD, REDUCE, RESTORE. All three
    affect only the number of already-valid candidate nonces considered in a
    dispatch window. REDUCE is fail-safe; RESTORE never exceeds the baseline
    breadth declared by the canonical coordinator.
    """

    TASK_ID = "bitcoin-mining-operating-breadth"
    ACTIONS = ("hold", "reduce", "restore")

    def __init__(self, baseline_breadth: int, *, state_path: str | None = None) -> None:
        self.baseline_breadth = max(1, int(baseline_breadth))
        self.current_breadth = self.baseline_breadth
        self.state_path = state_path or os.getenv(
            "PYTHIA_EUCLID_MINING_STATE", "data/euclid_mining_policy.json"
        )
        try:
            interval = float(os.getenv("PYTHIA_EUCLID_DECISION_INTERVAL_S", "5"))
        except ValueError:
            interval = 5.0
        self.decision_interval_s = max(0.1, interval)
        self.available = False
        self.unavailable_reason: str | None = None
        self.learner: Any = None
        self._last_state: dict[str, Any] | None = None
        self._last_action: str | None = None
        self._last_reward_at = 0.0
        self._last_advice: EuclidMiningAdvice | None = None
        self._last_decision_at = float("-inf")
        self._last_outcome_key: tuple[int, int, int, int, int] | None = None
        self._load_runtime()

    def _load_runtime(self) -> None:
        try:
            from hyba_substrate.euclid_experience_superlearner import ExperienceSuperlearner
        except Exception as exc:  # import boundary is reported, never hidden
            self.unavailable_reason = f"{type(exc).__name__}: {exc}"
            return
        try:
            Path(self.state_path).parent.mkdir(parents=True, exist_ok=True)
            learner = ExperienceSuperlearner(
                self.state_path,
                epsilon=0.0,  # production policy never explores blindly
                seed=20260718,
            )
            learner.register_task(
                self.TASK_ID,
                self.ACTIONS,
                difficulty=0.5,
                reward_range=(-1.0, 1.0),
                transfer_group="mining-operations",
                metadata={
                    "authority": "operational-only",
                    "forbidden": [
                        "sha256d",
                        "target",
                        "header",
                        "share-validity",
                        "credentials",
                        "pool-outcome",
                    ],
                },
            )
            self.learner = learner
            self.available = True
            self.unavailable_reason = None
        except Exception as exc:
            self.unavailable_reason = f"{type(exc).__name__}: {exc}"

    @staticmethod
    def _band(value: float | None, edges: tuple[float, ...]) -> int | None:
        if value is None or not math.isfinite(float(value)):
            return None
        number = float(value)
        for index, edge in enumerate(edges):
            if number < edge:
                return index
        return len(edges)

    def state_from_snapshot(
        self,
        snapshot: Mapping[str, Any] | None,
        *,
        recovery_mode: str | None,
        hashrate_hs: float | None,
    ) -> dict[str, Any]:
        snap = dict(snapshot or {})
        outcomes = dict(snap.get("outcomes") or {})
        submission = dict(snap.get("submission") or {})
        rtt = dict(submission.get("rtt_ms") or {})
        # Production transport may expose the tracker as retarget_window while
        # lower-level callers can provide retarget directly.
        retarget = dict(snap.get("retarget_window") or snap.get("retarget") or {})
        return {
            "ready": bool(snap.get("ready", False)),
            "recovery": str(recovery_mode or "unknown"),
            "accepted_band": self._band(outcomes.get("accepted_ratio"), (0.5, 0.9, 0.99)),
            "rejected_band": self._band(outcomes.get("rejected_ratio"), (0.001, 0.01, 0.05)),
            "unknown_band": self._band(outcomes.get("unknown_ratio"), (0.001, 0.01, 0.05)),
            "stale_band": self._band(outcomes.get("stale_ratio"), (0.001, 0.01, 0.05)),
            "rtt_band": self._band(rtt.get("p95"), (50.0, 150.0, 500.0, 1500.0)),
            "retarget_near": (
                int(retarget["blocks_until_retarget"]) <= 24
                if retarget.get("blocks_until_retarget") is not None
                else None
            ),
            "hashrate_band": self._band(hashrate_hs, (1e5, 1e6, 1e7, 1e9, 1e12)),
        }

    @staticmethod
    def reward(snapshot: Mapping[str, Any] | None) -> float | None:
        """Return a bounded reward derived only from observed transport truth."""
        snap = dict(snapshot or {})
        outcomes = dict(snap.get("outcomes") or {})
        values = {
            key: outcomes.get(key)
            for key in ("accepted_ratio", "rejected_ratio", "unknown_ratio", "stale_ratio")
        }
        # No submission evidence means no learning reward; do not invent one.
        if all(value is None for value in values.values()):
            return None
        accepted = float(values["accepted_ratio"] or 0.0)
        rejected = float(values["rejected_ratio"] or 0.0)
        unknown = float(values["unknown_ratio"] or 0.0)
        stale = float(values["stale_ratio"] or 0.0)
        return max(-1.0, min(1.0, accepted - rejected - unknown - stale))

    @staticmethod
    def _outcome_key(snapshot: Mapping[str, Any] | None) -> tuple[int, int, int, int, int] | None:
        """Identity for a measured outcome generation; prevents replay learning."""
        snap = dict(snapshot or {})
        counters = dict(snap.get("counters") or {})
        outcomes = dict(snap.get("outcomes") or {})
        submitted = counters.get("submitted")
        stale_dropped = outcomes.get("stale_dropped")
        if submitted is None and stale_dropped is None:
            return None
        return (
            int(submitted or 0),
            int(counters.get("accepted") or 0),
            int(counters.get("rejected") or 0),
            int(counters.get("unknown") or 0),
            int(stale_dropped or 0),
        )

    def advise(
        self,
        snapshot: Mapping[str, Any] | None,
        *,
        recovery_mode: str | None,
        hashrate_hs: float | None,
    ) -> EuclidMiningAdvice:
        state = self.state_from_snapshot(
            snapshot, recovery_mode=recovery_mode, hashrate_hs=hashrate_hs
        )
        if not self.available or self.learner is None:
            advice = EuclidMiningAdvice(
                "UNAVAILABLE",
                "hold",
                self.current_breadth,
                self.unavailable_reason or "EUCLID substrate unavailable",
                {"state": state, "claim_boundary": "no EUCLID runtime loaded"},
            )
            self._last_advice = advice
            return advice

        now_wall = time.time()
        outcome_key = self._outcome_key(snapshot)
        reward = self.reward(snapshot)
        if (
            reward is not None
            and outcome_key is not None
            and outcome_key != self._last_outcome_key
            and self._last_state is not None
            and self._last_action is not None
        ):
            self.learner.observe(
                self.TASK_ID,
                self._last_state,
                self._last_action,
                reward,
                state,
                metadata={
                    "source": "measured-mining-transport",
                    "observed_at": now_wall,
                    "outcome_key": outcome_key,
                    "claim_boundary": "operational policy only",
                },
            )
            self._last_reward_at = now_wall
        if outcome_key is not None:
            self._last_outcome_key = outcome_key

        now = time.monotonic()
        if (
            self._last_advice is not None
            and now - self._last_decision_at < self.decision_interval_s
        ):
            return self._last_advice

        action = str(self.learner.select_action(self.TASK_ID, state, explore=False))
        if action == "reduce":
            breadth = max(1, self.baseline_breadth // 2)
        elif action == "restore":
            breadth = self.baseline_breadth
        else:
            action = "hold"
            breadth = self.current_breadth

        # Safety clamp is local and unconditional, even if learner state is corrupt.
        breadth = max(1, min(self.baseline_breadth, int(breadth)))
        self.current_breadth = breadth
        self._last_state = state
        self._last_action = action
        self._last_decision_at = now
        advice = EuclidMiningAdvice(
            "ACTIVE",
            action,
            breadth,
            "experience policy evaluated measured mining state",
            {
                "state": state,
                "reward_observed": reward,
                "outcome_key": outcome_key,
                "last_reward_at": self._last_reward_at or None,
                "claim_boundary": "bounded operating policy; no consensus authority",
            },
        )
        self._last_advice = advice
        return advice

    def snapshot(self) -> dict[str, Any]:
        advice = self._last_advice
        return {
            "schema": "pythia.euclid_mining_support/1",
            "available": self.available,
            "unavailable_reason": self.unavailable_reason,
            "baseline_dispatch_breadth": self.baseline_breadth,
            "current_dispatch_breadth": self.current_breadth,
            "decision_interval_s": self.decision_interval_s,
            "last_outcome_key": self._last_outcome_key,
            "last_advice": asdict(advice) if advice is not None else None,
            "authority": "operational-only",
        }


class EuclidProductionMiningCoordinator(ProductionMiningCoordinator):
    """Production coordinator with EUCLID as a bounded advisory layer."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.euclid_support = EuclidMiningSupport(self._dispatch_breadth)

    def _euclid_transport_snapshot(self) -> Mapping[str, Any] | None:
        client = self.client
        if client is None:
            return None
        snapshot = getattr(client, "status_snapshot", None)
        if not callable(snapshot):
            return None
        try:
            return snapshot()
        except Exception:
            return None

    async def before_hardware_poll(self) -> bool:
        permitted = await super().before_hardware_poll()
        measured = self.measured_hashing()
        advice = self.euclid_support.advise(
            self._euclid_transport_snapshot(),
            recovery_mode=getattr(self.recovery, "mode", None),
            hashrate_hs=measured.get("hashrate_hs"),
        )
        # This is the only causal actuator. It is bounded by the baseline and
        # cannot affect proof construction or submission truth.
        self._dispatch_breadth = advice.dispatch_breadth
        return permitted

    def evidence_snapshot(self) -> dict[str, Any]:
        snapshot = super().evidence_snapshot()
        snapshot["euclid_support"] = self.euclid_support.snapshot()
        return snapshot


__all__ = [
    "EuclidMiningAdvice",
    "EuclidMiningSupport",
    "EuclidProductionMiningCoordinator",
]
