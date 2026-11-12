# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""The canonical HYBA Mine search: PYTHIA itinerary, Hendrix traversal, golden stride.

For one job and one extranonce2 the header prefix (76 bytes) is fixed and the
search space is the 2**32 nonces. The plan walks that space in a fixed,
job-bound order:

1. **PYTHIA itinerary.** Plan positions ``0 .. 2**32 - 1`` are cut into
   windows of ``2**window_bits`` consecutive positions. The itinerary hands out
   (extranonce2, position range) work units in order: every window of
   extranonce2 0, then of extranonce2 1, and so on. Units are disjoint and
   together cover every position exactly once.
2. **Hendrix traversal.** Inside a window the 256 lanes (``2**(window_bits-8)``
   positions each) are visited in the order of the F_257 generator cycle read
   from the Hendrix tables: slot ``k`` holds lane ``GF257.antilog(k + r) - 1``.
   Because 3 generates F_257*, the 256 slots hit the 256 lanes exactly once.
3. **Golden-stride bijection.** The traversal index ``i`` becomes the nonce
   ``offset + i * GOLDEN_STRIDE (mod 2**32)``. ``GOLDEN_STRIDE`` (0x9E3779B9,
   from ``chronus.execution.elevation``) is odd, so the map is a bijection of
   the 32-bit space and ``position_of`` inverts it exactly.

``offset`` and the lane rotation ``r`` come from SHA-256 of the header prefix,
so the order is bound to the job, replays identically in any process and
needs no randomness. The plan shapes traversal order and lane partitioning;
whether a candidate is a share is decided only by SHA-256d of its header
against the target, on the device and again on the host.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterator, Optional, Tuple

from chronus.execution.elevation import GOLDEN_STRIDE, verify_golden_stride
from chronus.hendrix import GF257

PLAN_VERSION = "pythia-hendrix-golden/v1"
NONCE_SPACE = 1 << 32
MASK32 = NONCE_SPACE - 1
LANES_PER_WINDOW = GF257.group_order  # 256
LANE_SHIFT = LANES_PER_WINDOW.bit_length() - 1  # 8
DEFAULT_WINDOW_BITS = 20
MIN_WINDOW_BITS = LANE_SHIFT
MAX_WINDOW_BITS = 30
STRIDE_INVERSE = pow(GOLDEN_STRIDE, -1, NONCE_SPACE)

if not verify_golden_stride() or (GOLDEN_STRIDE * STRIDE_INVERSE) & MASK32 != 1:
    raise ImportError("golden stride is not invertible modulo 2**32")
if LANES_PER_WINDOW != 1 << LANE_SHIFT:
    raise ImportError("Hendrix F_257 group order must be a power of two")


def hendrix_lane_table(rotation: int) -> Tuple[int, ...]:
    """Slot -> lane order for one window: the F_257 generator cycle from ``rotation``."""
    if not isinstance(rotation, int) or not 0 <= rotation < LANES_PER_WINDOW:
        raise ValueError("lane rotation must be an integer in [0, 256)")
    return tuple(GF257.antilog(slot + rotation) - 1 for slot in range(LANES_PER_WINDOW))


def hendrix_slot_of_lane(lane: int, rotation: int) -> int:
    """Inverse of the lane table: the slot at which ``lane`` is visited."""
    if not 0 <= lane < LANES_PER_WINDOW:
        raise ValueError("lane must be in [0, 256)")
    return (GF257.discrete_log(lane + 1) - rotation) % LANES_PER_WINDOW


def plan_seed(header_prefix: bytes) -> bytes:
    if not isinstance(header_prefix, (bytes, bytearray)) or len(header_prefix) != 76:
        raise ValueError("header prefix must be exactly 76 bytes")
    return hashlib.sha256(PLAN_VERSION.encode("ascii") + b"|" + bytes(header_prefix)).digest()


@dataclass(frozen=True)
class NoncePlan:
    """The canonical order of all 2**32 nonces for one header prefix."""

    header_prefix: bytes
    window_bits: int
    offset: int
    rotation: int
    lane_table: Tuple[int, ...]
    stride: int = GOLDEN_STRIDE

    @classmethod
    def for_header(cls, header_prefix: bytes, window_bits: int = DEFAULT_WINDOW_BITS) -> "NoncePlan":
        if not isinstance(window_bits, int) or not MIN_WINDOW_BITS <= window_bits <= MAX_WINDOW_BITS:
            raise ValueError(f"window_bits must be in [{MIN_WINDOW_BITS}, {MAX_WINDOW_BITS}]")
        seed = plan_seed(header_prefix)
        offset = int.from_bytes(seed[0:4], "little")
        rotation = seed[4]
        return cls(bytes(header_prefix), window_bits, offset, rotation, hendrix_lane_table(rotation))

    @property
    def window_size(self) -> int:
        return 1 << self.window_bits

    @property
    def lane_bits(self) -> int:
        return self.window_bits - LANE_SHIFT

    @property
    def lane_size(self) -> int:
        return 1 << self.lane_bits

    @property
    def window_count(self) -> int:
        return NONCE_SPACE >> self.window_bits

    def index_at(self, position: int) -> int:
        if not 0 <= position < NONCE_SPACE:
            raise ValueError("plan position must be in [0, 2**32)")
        within = position & (self.window_size - 1)
        lane = self.lane_table[within >> self.lane_bits]
        return (position - within) | (lane << self.lane_bits) | (within & (self.lane_size - 1))

    def nonce_at(self, position: int) -> int:
        return (self.offset + self.index_at(position) * self.stride) & MASK32

    def position_of(self, nonce: int) -> int:
        if not 0 <= nonce < NONCE_SPACE:
            raise ValueError("nonce must be a 32-bit unsigned integer")
        index = ((nonce - self.offset) * STRIDE_INVERSE) & MASK32
        within = index & (self.window_size - 1)
        lane = within >> self.lane_bits
        slot = hendrix_slot_of_lane(lane, self.rotation)
        return (index - within) | (slot << self.lane_bits) | (within & (self.lane_size - 1))

    def segments(self, start: int, count: int) -> Iterator[Tuple[int, int, int]]:
        """Yield (first position, first nonce, length) runs inside one lane.

        Inside a lane consecutive positions are consecutive indices, so the
        nonce advances by the stride; devices iterate these runs directly.
        """
        if count < 0 or not 0 <= start <= NONCE_SPACE - count:
            raise ValueError("position range must lie inside [0, 2**32)")
        position = start
        end = start + count
        while position < end:
            lane_end = (position | (self.lane_size - 1)) + 1
            length = min(lane_end, end) - position
            yield position, self.nonce_at(position), length
            position += length

    def describe(self) -> dict:
        return {
            "plan": PLAN_VERSION,
            "window_bits": self.window_bits,
            "offset": self.offset,
            "rotation": self.rotation,
            "stride": self.stride,
        }


@dataclass(frozen=True)
class UnitSpec:
    """One itinerary step: extranonce2 counter and a plan position range."""

    en2_counter: int
    start: int
    count: int


class PythiaItinerary:
    """Job-bound schedule of disjoint work units covering the plan in order.

    Units start at ``windows_per_unit`` windows and the runtime resizes them in
    whole windows (``resize``) so each takes about the target device time; a
    unit always starts where the previous one ended, so coverage stays exact.
    ``override`` replaces the schedule with an explicit list of units (used by
    the known-answer tests to aim a unit at a real block's nonce); it is
    consumed once and then the itinerary ends.
    """

    def __init__(
        self,
        window_bits: int = DEFAULT_WINDOW_BITS,
        windows_per_unit: int = 1,
        en2_start: int = 0,
        override: Optional[Tuple[UnitSpec, ...]] = None,
    ) -> None:
        if not MIN_WINDOW_BITS <= window_bits <= MAX_WINDOW_BITS:
            raise ValueError(f"window_bits must be in [{MIN_WINDOW_BITS}, {MAX_WINDOW_BITS}]")
        if windows_per_unit < 1 or (windows_per_unit << window_bits) > NONCE_SPACE:
            raise ValueError("windows_per_unit must be >= 1 and fit in the nonce space")
        if en2_start < 0:
            raise ValueError("en2_start must be >= 0")
        self.window_bits = window_bits
        self.unit_size = windows_per_unit << window_bits
        self.en2_start = en2_start
        self.override = override

    @property
    def window_size(self) -> int:
        return 1 << self.window_bits

    def resize(self, device_seconds: float, target_seconds: float, max_size: int = 1 << 30) -> None:
        """Double or halve the unit (in whole windows) toward ``target_seconds`` of device time."""
        if self.override is not None or device_seconds <= 0:
            return
        if device_seconds < target_seconds / 2 and self.unit_size * 2 <= max_size:
            self.unit_size *= 2
        elif device_seconds > target_seconds * 2 and self.unit_size > self.window_size:
            self.unit_size //= 2

    def units(self, en2_limit: int) -> Iterator[UnitSpec]:
        if self.override is not None:
            for unit in self.override:
                if not 0 <= unit.en2_counter < en2_limit:
                    raise ValueError("override unit extranonce2 counter is out of range")
                yield unit
            return
        for en2_counter in range(self.en2_start, en2_limit):
            start = 0
            while start < NONCE_SPACE:
                size = min(self.unit_size, NONCE_SPACE - start)
                yield UnitSpec(en2_counter, start, size)
                start += size
