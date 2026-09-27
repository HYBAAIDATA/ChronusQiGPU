"""Deterministic M32 SHA256d solver with Turing-derived ordering.

The solver is a real exhaustive proof checker. Turing and M32 only partition
and order nonce work; they do not change the cryptographic predicate. Every
candidate visited by ``scan`` is converted to a complete 80-byte header and
checked with double SHA256 before it can be returned.
"""

from __future__ import annotations

import time
import struct
from dataclasses import dataclass
from typing import Iterable, Iterator

from .execution import MiningExecutionResult
from .geometry import LANES, M32Topology, PhyllotaxisLaneIndex
from .pow import (
    build_header,
    check_pow,
    compact_target,
    require_lucas_execution_scale,
)
from .turing_adapter import TuringMiningSubstrate


@dataclass(frozen=True)
class SolveResult:
    found_nonce: int | None
    valid: bool
    attempts: int
    elapsed_seconds: float
    lane: int | None
    proof: str = "sha256d"
    ordering: str = "turing_m32_complete"
    execution: MiningExecutionResult | None = None


class M32SearchSolver:
    """Bounded solver with complete lane coverage and Turing ordering."""

    def __init__(
        self,
        topology: M32Topology | None = None,
        turing: TuringMiningSubstrate | None = None,
    ) -> None:
        self.topology = topology or M32Topology()
        if not self.topology.connected():
            raise RuntimeError("M32 topology is disconnected")
        self.turing = turing or TuringMiningSubstrate()
        # Per-lane state is stored in phyllotaxis-folded slots: the
        # golden-ratio index map spreads hot lanes across the storage array.
        self.lane_index = PhyllotaxisLaneIndex()
        self._lane_attempts = [0] * LANES
        # None means no bias applied: the sweep keeps the natural start lane
        # (start_nonce % LANES). An explicit value rotates the declared order.
        self._lane_start_offset: int | None = None
        # The chooser installs this. m32_lane_order is the Turing permutation;
        # exhaustive is the sequential lane sweep. Both cover every lane.
        self._candidate_ordering = "m32_lane_order"

    def set_candidate_ordering(self, ordering: str) -> None:
        """Install the chooser's nonce order. Coverage is unchanged."""
        if ordering not in ("m32_lane_order", "exhaustive"):
            raise ValueError("unsupported candidate ordering")
        self._candidate_ordering = ordering

    def get_candidate_ordering(self) -> str:
        return self._candidate_ordering

    def set_lane_start_offset(self, preferred_face: int) -> None:
        """Sets the starting lane for the 32-face sweep. The lane
        ordering is a cyclic rotation of the canonical face
        order; the underlying search space is unchanged."""
        if (
            isinstance(preferred_face, bool)
            or not isinstance(preferred_face, int)
            or not 0 <= preferred_face < LANES
        ):
            raise ValueError("preferred_face must be an integer in [0, 31]")
        self._lane_start_offset = preferred_face

    def get_lane_start_offset(self) -> int:
        """Return the configured starting lane (0 when no bias is applied)."""
        return self._lane_start_offset if self._lane_start_offset is not None else 0

    def candidates(
        self,
        start_nonce: int = 0,
        budget: int = 1,
        lane_order: Iterable[int] | None = None,
    ) -> Iterator[tuple[int, int]]:
        if not 0 <= start_nonce <= 0xFFFFFFFF:
            raise ValueError("start_nonce must be uint32")
        if budget < 0:
            raise ValueError("budget must be non-negative")
        base = start_nonce - (start_nonce % LANES)
        first_lane = start_nonce % LANES
        if lane_order is not None:
            order = tuple(int(lane) for lane in lane_order)
        elif self._candidate_ordering == "exhaustive":
            order = tuple((first_lane + offset) % LANES for offset in range(LANES))
        else:
            order = self.turing.lane_order(start_nonce)
        if sorted(order) != list(range(LANES)):
            raise ValueError("lane_order must contain every M32 lane exactly once")
        expected_first = first_lane
        if lane_order is None and self._lane_start_offset is not None:
            pivot = order.index(self._lane_start_offset)
            order = order[pivot:] + order[:pivot]
            expected_first = self._lane_start_offset
        if lane_order is None and order[0] != expected_first:
            raise RuntimeError("Turing order failed start-lane alignment")
        for step in range(budget):
            lane = order[step % LANES]
            epoch = step // LANES
            nonce = (base + lane + LANES * epoch) & 0xFFFFFFFF
            yield nonce, lane

    def scan(
        self,
        *,
        version: int,
        previous_hash: str,
        merkle_root: str,
        timestamp: int,
        bits: int | str,
        budget: int,
        start_nonce: int = 0,
        lane_order: Iterable[int] | None = None,
        scale_index: int | None = None,
    ) -> SolveResult:
        # Hardware gate: when a scaled allocation is declared, only Lucas
        # ladder indices may reach the physical grind. Unscaled scans (None)
        # remain legal for the CPU reference path.
        if scale_index is not None:
            require_lucas_execution_scale(scale_index)
        target = compact_target(bits)
        started = time.perf_counter_ns()
        attempts = 0
        for nonce, lane in self.candidates(start_nonce, budget, lane_order):
            attempts += 1
            self._lane_attempts[self.lane_index.slot(lane)] += 1
            header = build_header(version, previous_hash, merkle_root, timestamp, bits, nonce)
            if check_pow(header, target):
                elapsed = (time.perf_counter_ns() - started) / 1e9
                execution = (
                    MiningExecutionResult.observed(
                        requested_backend="cpu_reference",
                        actual_backend="cpu_reference",
                        device_name=None,
                        device_available=False,
                        hardware_execution=False,
                        hashes_computed=attempts,
                        elapsed_seconds=elapsed,
                    )
                    if attempts and elapsed > 0
                    else None
                )
                return SolveResult(nonce, True, attempts, elapsed, lane, execution=execution)
        elapsed = (time.perf_counter_ns() - started) / 1e9
        execution = (
            MiningExecutionResult.observed(
                requested_backend="cpu_reference",
                actual_backend="cpu_reference",
                device_name=None,
                device_available=False,
                hardware_execution=False,
                hashes_computed=attempts,
                elapsed_seconds=elapsed,
            )
            if attempts and elapsed > 0
            else None
        )
        return SolveResult(None, False, attempts, elapsed, None, execution=execution)

    def scan_header(
        self,
        *,
        header: bytes,
        target: int,
        budget: int,
        lane_order: Iterable[int] | None = None,
        scale_index: int = 10,
    ) -> SolveResult:
        """Search the exact negotiated template, preserving its share target."""
        from lucas.core import lucas

        require_lucas_execution_scale(scale_index)
        if len(header) != 80 or type(target) is not int or not 0 < target < 2**256:
            raise ValueError("complete negotiated header and uint256 target required")
        if type(budget) is not int or not 0 < budget <= lucas(scale_index):
            raise ValueError("search budget exceeds the active Lucas rung")
        started = time.perf_counter_ns()
        attempts = 0
        winner = lane_found = None
        for nonce, lane in self.candidates(0, budget, lane_order):
            attempts += 1
            self._lane_attempts[self.lane_index.slot(lane)] += 1
            if check_pow(header[:76] + struct.pack("<I", nonce), target):
                winner, lane_found = nonce, lane
                break
        elapsed = (time.perf_counter_ns() - started) / 1e9
        execution = (
            MiningExecutionResult.observed(
                requested_backend="cpu_reference",
                actual_backend="cpu_reference",
                device_name=None,
                device_available=False,
                hardware_execution=False,
                hashes_computed=attempts,
                elapsed_seconds=elapsed,
            )
            if attempts and elapsed > 0
            else None
        )
        return SolveResult(
            winner, winner is not None, attempts, elapsed, lane_found, execution=execution
        )

    def lane_attempts(self) -> tuple[int, ...]:
        """Per-lane attempt counts unfolded from phyllotaxis slot order."""
        return tuple(self._lane_attempts[self.lane_index.slot(lane)] for lane in range(LANES))
