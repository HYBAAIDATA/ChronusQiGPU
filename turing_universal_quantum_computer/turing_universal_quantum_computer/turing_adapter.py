"""Turing-core ordering adapter for the canonical PYTHIA solver.

Turing is the original PYTHIA mining substrate.  This adapter imports its
verified multi-family integer schedule into the canonical MLA1517 solver.
It changes probe order only; it never decides proof validity and never drops
an unvisited nonce.  If the Turing core cannot be imported, the adapter fails
closed instead of substituting a shim or a synthetic schedule.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

LANES = 32


class TuringCoreUnavailable(RuntimeError):
    """The canonical Turing mining substrate is unavailable."""


@dataclass(frozen=True)
class TuringScheduleEvidence:
    """Evidence attached to a deterministic Turing-derived ordering."""

    seed: int
    window: int
    prefix_length: int
    complete_coverage: bool
    source: str = "turing_core.extended_nonce_schedule"


class TuringMiningSubstrate:
    """Expose Turing's exact integer scheduling primitives to MLA1517."""

    def __init__(self, core: Any | None = None) -> None:
        if core is None:
            try:
                from . import turing_core as core  # type: ignore
            except ImportError as exc:  # fail closed; no replacement schedule
                raise TuringCoreUnavailable(
                    "turing_core is required for canonical PYTHIA ordering"
                ) from exc
        schedule = getattr(core, "extended_nonce_schedule", None)
        if not callable(schedule):
            raise TuringCoreUnavailable(
                "turing_core.extended_nonce_schedule is required"
            )
        self._core = core
        self._schedule = schedule

    def lane_order(self, start_nonce: int = 0) -> tuple[int, ...]:
        """Return a complete Turing-derived permutation of the 32 M32 lanes."""
        if not 0 <= int(start_nonce) <= 0xFFFFFFFF:
            raise ValueError("start_nonce must be uint32")
        raw = self._schedule(LANES, seed=int(start_nonce), cap=LANES)
        order: list[int] = []
        seen: set[int] = set()
        for offset in raw:
            lane = int(offset) % LANES
            if lane not in seen:
                order.append(lane)
                seen.add(lane)
        # The family schedule may contain repeated residues.  Completing the
        # declared lane set preserves full coverage without inventing a second
        # acceptance rule or silently omitting a lane.
        order.extend(lane for lane in range(LANES) if lane not in seen)
        if len(order) != LANES or set(order) != set(range(LANES)):
            raise TuringCoreUnavailable("Turing schedule did not produce 32 lanes")
        first = int(start_nonce) % LANES
        pivot = order.index(first)
        return tuple(order[pivot:] + order[:pivot])

    def exhaustive_order(self, window: int, seed: int = 0) -> tuple[int, ...]:
        """Return a complete permutation of offsets in ``[0, window)``.

        Turing's multi-family schedule forms the deterministic prefix.  The
        untouched offsets are appended in ascending order, so the result is a
        reordering of the full search window rather than a pruning heuristic.
        """
        window = int(window)
        if window < 0:
            raise ValueError("window must be non-negative")
        if window == 0:
            return ()
        prefix = self._schedule(window, seed=int(seed), cap=min(window, 1000))
        order: list[int] = []
        seen: set[int] = set()
        for offset in prefix:
            value = int(offset)
            if 0 <= value < window and value not in seen:
                order.append(value)
                seen.add(value)
        order.extend(value for value in range(window) if value not in seen)
        if len(order) != window or set(order) != set(range(window)):
            raise TuringCoreUnavailable("Turing exhaustive order lost search coverage")
        return tuple(order)

    def evidence(self, window: int, seed: int = 0) -> TuringScheduleEvidence:
        """Return structural evidence without making a mining claim."""
        ordered = self.exhaustive_order(window, seed)
        prefix = min(len(ordered), min(max(window, 0), 1000))
        return TuringScheduleEvidence(
            seed=int(seed),
            window=int(window),
            prefix_length=prefix,
            complete_coverage=len(ordered) == max(int(window), 0),
        )
