# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Chronus iGPU Mode A kernel: the canonical plan range on the software-defined GPU.

Standard library only, so the worker processes of the Mode A lane start fast.
The mapping from plan position to nonce is the same as ``hyba_mine.plan`` and
the Metal kernel: window, Hendrix lane slot, golden-stride index. SHA-256d uses
a SHA-256 midstate of the first 64 header bytes; a candidate is a hit exactly
when ``int.from_bytes(sha256d(header), "little") <= target``.

A run can be stopped early: ``should_stop`` is checked every
``ABORT_CHECK_STRIDE`` candidates and at lane boundaries, and the run then
returns the executed prefix (its hits and probe are exactly those of an
unstopped run restricted to that prefix). Worker processes read a shared
abort ticket installed by ``install_abort_ticket``.
"""

from __future__ import annotations

import hashlib
import struct
from typing import Callable, List, Optional, Sequence, Tuple

MASK32 = 0xFFFFFFFF
ABORT_CHECK_STRIDE = 4096
_PACK = struct.Struct("<I").pack
_ABORT_TICKET = None


def run_range(
    prefix: bytes,
    target: int,
    start: int,
    count: int,
    window_bits: int,
    offset: int,
    stride: int,
    lane_table: Sequence[int],
    probe_offset: Optional[int],
    should_stop: Optional[Callable[[], bool]] = None,
) -> Tuple[int, List[Tuple[int, int]], Optional[Tuple[int, ...]]]:
    """Hash plan positions [start, start + count); return (executed, hits, probe words).

    Hits are (offset from ``start``, nonce). The probe words are the eight
    little-endian 32-bit words of the hash at ``probe_offset`` (relative to
    ``start``), taken from inside the loop as a canary of executed work.
    When ``should_stop`` returns true the run ends early and ``executed`` is
    the length of the prefix that was hashed.
    """
    if len(prefix) != 76:
        raise ValueError("header prefix must be 76 bytes")
    if should_stop is not None and should_stop():
        return 0, [], None
    lane_bits = window_bits - 8
    lane_size = 1 << lane_bits
    window_mask = (1 << window_bits) - 1
    lane_mask = lane_size - 1
    midstate = hashlib.sha256(prefix[:64])
    tail = prefix[64:76]
    sha256 = hashlib.sha256
    from_bytes = int.from_bytes
    top_byte = (target >> 248) & 0xFF
    hits: List[Tuple[int, int]] = []
    probe: Optional[Tuple[int, ...]] = None
    executed = 0
    position = start
    end = start + count
    while position < end:
        within = position & window_mask
        lane = lane_table[within >> lane_bits]
        j = within & lane_mask
        index = (position - within) | (lane << lane_bits) | j
        nonce = (offset + index * stride) & MASK32
        run = min(lane_size - j, end - position)
        rel = position - start
        probe_at = probe_offset - rel if probe_offset is not None and rel <= probe_offset < rel + run else -1
        for k0 in range(0, run, ABORT_CHECK_STRIDE):
            k1 = min(run, k0 + ABORT_CHECK_STRIDE)
            for k in range(k0, k1):
                ctx = midstate.copy()
                ctx.update(tail + _PACK(nonce))
                digest = sha256(ctx.digest()).digest()
                if digest[31] <= top_byte and from_bytes(digest, "little") <= target:
                    hits.append((rel + k, nonce))
                if k == probe_at:
                    value = from_bytes(digest, "little")
                    probe = tuple((value >> (32 * i)) & MASK32 for i in range(8))
                nonce = (nonce + stride) & MASK32
            if should_stop is not None and k1 < run and should_stop():
                return executed + k1, hits, probe
        executed += run
        position += run
        if should_stop is not None and position < end and should_stop():
            return executed, hits, probe
    return executed, hits, probe


def run_task(args: tuple) -> Tuple[int, List[Tuple[int, int]], Optional[Tuple[int, ...]]]:
    """Picklable entry point for the Mode A process pool."""
    return run_range(*args)


def install_abort_ticket(shared) -> None:
    """Process-pool initializer: the shared ticket that tells a worker its unit is still wanted."""
    global _ABORT_TICKET
    _ABORT_TICKET = shared


def run_task_abortable(args: tuple, ticket: int) -> Tuple[int, List[Tuple[int, int]], Optional[Tuple[int, ...]]]:
    """Like ``run_task``, but stops once the shared ticket no longer equals ``ticket``."""
    shared = _ABORT_TICKET
    if shared is None:
        return run_range(*args)
    return run_range(*args, should_stop=lambda: shared.value != ticket)
