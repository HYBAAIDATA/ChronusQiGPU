"""Which recoveries restore throughput: before and after, measured.

Salamander verifies a recovery when its commands were acknowledged and the
device answered. That says the treatment was applied, not that it worked.
This learner answers ``recovery.effect``: for every verified recovery it
compares the miner's measured hash rate over the ``span`` windows before it
with the ``span`` windows after it, and keeps the record per set of
commands. A ratio at or above 1 restored throughput; below 1 it did not.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

from Intelligence.lucas_scales import ladder_capacity

# LUCAS_SCALED (lemma_lucas_universal): the comparison span is a retention
# envelope — a ladder stop. MIN_BEFORE stays raw (evidence minimum).
SPAN = ladder_capacity(16)
MIN_BEFORE = 4


@dataclass
class _Pending:
    key: str
    before_hs: float
    hashes: int = 0
    seconds: float = 0.0
    windows: int = 0


@dataclass
class RecoveryEffects:
    span: int = SPAN
    _recent: deque = field(default_factory=deque)
    _pending: dict[str, _Pending] = field(default_factory=dict)
    by_commands: dict[str, dict[str, Any]] = field(default_factory=dict)
    unmeasured: int = 0  # recoveries with too little history before them

    def observe_window(self, hashes: int, elapsed_s: float) -> list[str]:
        """One completed window; returns the recoveries this window settled."""
        if hashes <= 0 or elapsed_s <= 0:
            return []
        self._recent.append((hashes, elapsed_s))
        while len(self._recent) > self.span:
            self._recent.popleft()
        settled = []
        for recovery_id, p in list(self._pending.items()):
            p.hashes += hashes
            p.seconds += elapsed_s
            p.windows += 1
            if p.windows >= self.span:
                self._settle(p)
                del self._pending[recovery_id]
                settled.append(recovery_id)
        return settled

    def recovery_verified(self, recovery_id: str, commands: list[str]) -> None:
        if len(self._recent) < MIN_BEFORE:
            self.unmeasured += 1
            return
        hashes = sum(h for h, _ in self._recent)
        seconds = sum(s for _, s in self._recent)
        key = "+".join(sorted(set(commands))) or "none"
        self._pending[recovery_id] = _Pending(key, hashes / seconds)

    def _settle(self, p: _Pending) -> None:
        ratio = (p.hashes / p.seconds) / p.before_hs
        entry = self.by_commands.setdefault(
            p.key, {"recoveries": 0, "restored": 0, "ratio_sum": 0.0}
        )
        entry["recoveries"] += 1
        entry["restored"] += int(ratio >= 1.0)
        entry["ratio_sum"] += ratio
        entry["mean_ratio"] = entry["ratio_sum"] / entry["recoveries"]
        entry["last_ratio"] = ratio

    def snapshot(self) -> dict[str, Any]:
        return {
            "by_commands": (
                {
                    key: {k: v for k, v in entry.items() if k != "ratio_sum"}
                    for key, entry in sorted(self.by_commands.items())
                }
                or None
            ),
            "pending": len(self._pending),
            "unmeasured": self.unmeasured,
            "span_windows": self.span,
        }
