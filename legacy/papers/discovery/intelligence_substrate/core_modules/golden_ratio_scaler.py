from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Dict, Any

PHI: float = (1.0 + math.sqrt(5.0)) / 2.0

# Per-dimension upper bounds for propose_scaling_plan's proposals.
#
# Previously every dimension was capped at a single hardcoded 144 (a
# reasonable ceiling for a GPU *count*, being F(12) in the 1-indexed
# Fibonacci series), which meant memory_mb could never be proposed above
# 144 *megabytes* -- badly mis-scaling any real workload (real deployments
# routinely need memory in the tens-to-hundreds-of-GB range). Each
# dimension now gets its own real-world-sized bound:
#   - gpus: 144        a single cluster rarely exceeds ~100 accelerators;
#                       144 is also a clean Fibonacci number (F_12).
#   - batch_size: 46368  F_24 -- comfortably covers realistic large-batch
#                         training regimes without being unbounded.
#   - memory_mb: 1_048_576  1 TiB in MB -- a generous but finite ceiling
#                           for a single node/process's memory budget.
#   - search_depth: 4181  F_19 -- deep enough for any realistic recursive
#                         search/tree traversal while still bounded.
DIMENSION_CAPS: Dict[str, int] = {
    "gpus": 144,
    "batch_size": 46368,
    "memory_mb": 1_048_576,
    "search_depth": 4181,
}
DEFAULT_DIMENSION_CAP: int = 144


@dataclass
class ScalingProposal:
    """A single hardware scaling recommendation."""

    dimension: str
    current_value: int
    proposed_value: int
    fibonacci_index: int
    rationale: str


class GoldenRatioScaler:
    def __init__(self, base: int = 1) -> None:
        if base < 1:
            base = 1
        self.base = base
        self._fib_cache: List[int] = [0, 1]
        self._lucas_cache: List[int] = [2, 1]

    def _fib(self, n: int) -> int:
        if n < 0:
            return self.base * ((-1) ** (-n + 1) * self._fib(-n))
        cache = self._fib_cache
        while len(cache) <= n:
            cache.append(cache[-1] + cache[-2])
        return self.base * cache[n]

    def _lucas(self, n: int) -> int:
        if n < 0:
            return self.base * ((-1) ** (-n) * self._lucas(-n))
        cache = self._lucas_cache
        while len(cache) <= n:
            cache.append(cache[-1] + cache[-2])
        return self.base * cache[n]

    def fib_series(self, count: int, start: int = 0) -> List[int]:
        return [self._fib(start + i) for i in range(count)]

    def lucas_series(self, count: int, start: int = 0) -> List[int]:
        return [self._lucas(start + i) for i in range(count)]

    def next_gpu_count(self, current_gpus: int) -> int:
        """Uses Lucas sequence for GPU scaling if current_gpus matches a Lucas number, else Fibonacci."""
        if current_gpus < 1:
            return self._fib(2)

        # L_0 = 2*base is the one point where the Lucas sequence is NOT
        # monotonically increasing (L_0=2 > L_1=1). Scanning from index 0
        # against a current_gpus that exactly equals L_0 used to stop the
        # search at n_l=0 immediately and return L_1 (a *smaller* value) as
        # "next" -- e.g. next_gpu_count(2) incorrectly returned 1. Handle
        # this exact point explicitly and search the rest of the sequence
        # (L_1 < L_2 < L_3 < ...), which is strictly increasing.
        if current_gpus == self._lucas(0):
            return self._lucas(2)

        n_l = 1
        while self._lucas(n_l) < current_gpus:
            n_l += 1

        if self._lucas(n_l) == current_gpus:
            return self._lucas(n_l + 1)

        n_f = 2
        while self._fib(n_f) < current_gpus:
            n_f += 1
        return self._fib(n_f + 1)

    def prev_gpu_count(self, current_gpus: int) -> int:
        """Uses Lucas sequence for scaling down if current_gpus matches a Lucas number, else Fibonacci."""
        if current_gpus <= 1:
            return 1

        # See next_gpu_count for why L_0 = 2*base needs special-casing.
        if current_gpus == self._lucas(0):
            return self._lucas(1)

        n_l = 1
        while self._lucas(n_l) < current_gpus:
            n_l += 1

        if self._lucas(n_l) == current_gpus:
            return self._lucas(max(1, n_l - 1))

        n_f = 2
        while self._fib(n_f) < current_gpus:
            n_f += 1
        return self._fib(max(2, n_f - 1))

    def scale_batch_size(self, current: int, direction: str = "up") -> int:
        """Scale batch size using Lucas numbers."""
        if current < 1:
            current = 1

        if direction == "up":
            n = 0
            while self._lucas(n) <= current:
                n += 1
            return self._lucas(n)
        else:
            # See next_gpu_count for why L_0 = 2*base needs special-casing:
            # without it, scale_batch_size(2, "down") incorrectly returned 2
            # unchanged instead of scaling down to 1.
            if current == self._lucas(0):
                return self._lucas(1)
            n = 1
            while self._lucas(n) < current:
                n += 1
            return self._lucas(max(1, n - 1))

    def scale_memory(self, current_mb: int, direction: str = "up", family: str = "golden") -> int:
        """Scale memory using different metallic means."""
        if current_mb < 1:
            current_mb = 1

        if family == "silver":
            ratio = 1.0 + math.sqrt(2.0)
        elif family == "bronze":
            ratio = (3.0 + math.sqrt(13.0)) / 2.0
        else:  # golden
            ratio = PHI

        if direction == "up":
            target = int(current_mb * ratio)
        else:
            target = int(current_mb / ratio)
        return max(1, target)

    def propose_scaling_plan(
        self,
        dimensions: List[str],
        current: Dict[str, int],
        target_coherence: float,
        phi_density: float,
    ) -> List[ScalingProposal]:
        proposals: List[ScalingProposal] = []
        coherence_factor = max(0.0, min(1.0, target_coherence))

        for dim in dimensions:
            cur = current.get(dim, 1)
            if cur < 1:
                cur = 1

            if coherence_factor >= 0.7:
                direction = "up"
                rationale = f"High coherence ({coherence_factor:.2f}) and phi_density ({phi_density:.2f}) → scale up via φ-series"
            elif coherence_factor >= 0.4:
                direction = "maintain"
                rationale = f"Medium coherence ({coherence_factor:.2f}) → maintain current scale"
            else:
                direction = "down"
                rationale = f"Low coherence ({coherence_factor:.2f}) → defensive scale down"

            if dim == "gpus":
                if direction == "up":
                    proposed = self.next_gpu_count(cur)
                elif direction == "down":
                    proposed = self.prev_gpu_count(cur)
                else:
                    proposed = cur
            elif dim == "batch_size":
                if direction == "up":
                    proposed = self.scale_batch_size(cur, "up")
                elif direction == "down":
                    proposed = self.scale_batch_size(cur, "down")
                else:
                    proposed = cur
            elif dim == "memory_mb":
                # scale_memory has no concept of "maintain" -- it treats any
                # direction other than "up" as "down" and divides by the
                # ratio. Without this guard, a "maintain" verdict (medium
                # coherence) silently shrank memory_mb every time instead of
                # leaving it unchanged, unlike gpus/batch_size/search_depth
                # above which all handle "maintain" explicitly.
                if direction == "maintain":
                    proposed = cur
                else:
                    proposed = self.scale_memory(cur, direction)
            elif dim == "search_depth":
                if direction == "up":
                    n = 2
                    while self._fib(n) <= cur:
                        n += 1
                    proposed = self._fib(n)
                elif direction == "down":
                    # Find the smallest n with fib(n) >= cur (searching
                    # UP, mirroring the "up" branch above), then step back
                    # one index to get the largest Fibonacci term strictly
                    # below cur. The previous version searched from a fixed
                    # n=2 downward (`while self._fib(n) >= cur: n -= 1`),
                    # which only worked when fib(2)=1 already happened to
                    # be >= cur -- for any cur > 1 the loop body never ran
                    # and it collapsed to fib(2)=1 regardless of cur (e.g.
                    # cur=100 incorrectly proposed 1 instead of ~89).
                    n = 2
                    while self._fib(n) < cur:
                        n += 1
                    n -= 1
                    proposed = max(1, self._fib(max(n, 1)))
                else:
                    proposed = cur
            else:
                proposed = cur

            proposed = min(proposed, DIMENSION_CAPS.get(dim, DEFAULT_DIMENSION_CAP))

            fib_idx = 2
            while self._fib(fib_idx) < proposed:
                fib_idx += 1
                if fib_idx > 50:
                    break

            proposals.append(
                ScalingProposal(
                    dimension=dim,
                    current_value=cur,
                    proposed_value=proposed,
                    fibonacci_index=fib_idx,
                    rationale=rationale,
                )
            )

        return proposals

    def to_dict(self) -> Dict[str, Any]:
        return {
            "base": self.base,
            "phi": PHI,
            "silver": 1.0 + math.sqrt(2.0),
            "bronze": (3.0 + math.sqrt(13.0)) / 2.0,
            "fib_series_10": self.fib_series(10, start=1),
            "lucas_series_10": self.lucas_series(10, start=1),
        }
