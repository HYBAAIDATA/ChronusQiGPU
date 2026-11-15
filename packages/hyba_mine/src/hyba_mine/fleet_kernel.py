# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""HYBA Mine's kernel for the Chronus iGPU fleet: a ``CHRONUS_FLEET_KERNELS`` plugin.

Register it on every fleet machine before ``chronus-fleet join`` (and on the
coordinator)::

    export CHRONUS_FLEET_KERNELS=hyba_mine.fleet_kernel

All mining logic stays in HYBA Mine. The fleet sees a generic, item-parallel
kernel: it stripes the items over its scheduling lattice, leases tiles to the
backends each machine selected, checks tiles against this kernel's reference
and signs the receipt. It never learns what the items mean.

Work unit (``chronus.fleet.WorkUnit``):

* ``payload``: the 76-byte header prefix;
* ``params``: ``target_hex``, ``window_bits``, ``offset``, ``stride``,
  ``lane_table`` (256 entries), ``start``, ``count`` and ``probe_offset``; no
  pool identity and no login;
* items: the ``count`` plan positions ``start .. start + count``.

Output (canonical and independent of how the fleet tiles the unit, so the
merged result equals the whole-unit reference byte for byte): ``HMW1``,
executed (u32), hit count (u32), probe flag (u8), hits as (offset u32, nonce
u32) with offsets from the unit start, then the eight probe words (u32) when
the probe position is in the range. ``decode_output`` reads it back.
"""

from __future__ import annotations

import struct
from functools import lru_cache
from typing import Any, Mapping, Optional, Sequence, Tuple

from chronus.fleet.errors import KernelError
from chronus.fleet.kernels import Kernel, KnownAnswer, Prepared

from hyba_mine import _mode_a_kernel

KERNEL_NAME = "hyba_mine.nonce_window"
KERNEL_VERSION = "1"
MAGIC = b"HMW1"
_HEAD = struct.Struct("<4sIIB")
_PAIR = struct.Struct("<II")
_PROBE = struct.Struct("<8I")
PARAMS = ("target_hex", "window_bits", "offset", "stride", "lane_table", "start", "count", "probe_offset")
#: SHA-256 of the known-answer output: the genesis block's real nonce in its plan lane (pinned).
GENESIS_LANE_OUTPUT_SHA256 = "de9c2b837fd5b650b091983af7ad4559ec36f37bd853409a099a99550dbedbe8"


def encode_output(executed: int, hits: Sequence[Tuple[int, int]], probe: Optional[Sequence[int]]) -> bytes:
    ordered = sorted((int(o), int(n)) for o, n in hits)
    parts = [_HEAD.pack(MAGIC, executed, len(ordered), 1 if probe is not None else 0)]
    parts.extend(_PAIR.pack(o, n) for o, n in ordered)
    if probe is not None:
        parts.append(_PROBE.pack(*probe))
    return b"".join(parts)


def _decode_one(data: bytes, at: int) -> tuple:
    magic, executed, count, has_probe = _HEAD.unpack_from(data, at)
    if magic != MAGIC:
        raise KernelError("not a HYBA Mine window output")
    at += _HEAD.size
    hits = [_PAIR.unpack_from(data, at + i * _PAIR.size) for i in range(count)]
    at += count * _PAIR.size
    probe = None
    if has_probe:
        probe = _PROBE.unpack_from(data, at)
        at += _PROBE.size
    return executed, hits, probe, at


def decode_output(data: bytes) -> tuple:
    """(executed, [(offset, nonce)], probe words or None) from one encoded output."""
    executed, hits, probe, end = _decode_one(bytes(data), 0)
    if end != len(data):
        raise KernelError("trailing bytes after a HYBA Mine window output")
    return executed, [tuple(h) for h in hits], probe


def unit_params(unit: Any) -> dict:
    """Fleet params for a ``hyba_mine.work.WorkUnit``."""
    plan = unit.plan
    return {
        "target_hex": f"{unit.target:064x}",
        "window_bits": plan.window_bits,
        "offset": plan.offset,
        "stride": plan.stride,
        "lane_table": list(plan.lane_table),
        "start": unit.start,
        "count": unit.count,
        "probe_offset": unit.probe_offset,
    }


class NonceWindowKernel(Kernel):
    name = KERNEL_NAME
    version = KERNEL_VERSION
    description = "HYBA Mine: SHA-256d over a window of canonical plan positions (plugin; not part of the fleet)."

    def prepare(self, params: Mapping[str, Any], payload: bytes) -> Prepared:
        if not isinstance(params, Mapping) or set(params) != set(PARAMS):
            raise KernelError(f"params must be exactly {', '.join(PARAMS)}")
        if len(payload) != 76:
            raise KernelError("payload must be the 76-byte header prefix")
        ints = {k: params[k] for k in PARAMS if k not in ("target_hex", "lane_table")}
        if not all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in ints.values()):
            raise KernelError("window_bits, offset, stride, start, count and probe_offset must be integers >= 0")
        table = params["lane_table"]
        if not isinstance(table, list) or sorted(table) != list(range(256)):
            raise KernelError("lane_table must be a permutation of 0..255")
        try:
            target = int(params["target_hex"], 16)
        except (TypeError, ValueError):
            raise KernelError("target_hex must be hexadecimal") from None
        if not 0 < target < 1 << 256 or not 9 <= params["window_bits"] <= 32:
            raise KernelError("target or window_bits out of range")
        if params["count"] < 1 or params["start"] + params["count"] > 1 << 32 or params["probe_offset"] >= params["count"]:
            raise KernelError("count, start and probe_offset must lie inside the nonce space")
        return Prepared(dict(params), bytes(payload), params["count"])

    def tile_input(self, prepared: Prepared, start: int, stop: int) -> bytes:
        return prepared.payload

    def run_reference(self, ctx: Any, params: Mapping[str, Any], tile: bytes, start: int, stop: int) -> bytes:
        probe = params["probe_offset"] - start if start <= params["probe_offset"] < stop else None
        executed, hits, words = _mode_a_kernel.run_range(
            tile, int(params["target_hex"], 16), params["start"] + start, stop - start, params["window_bits"],
            params["offset"], params["stride"], params["lane_table"], probe,
        )
        return encode_output(executed, [(start + o, n) for o, n in hits], words)

    def merge(self, params: Mapping[str, Any], outputs: Sequence[bytes]) -> bytes:
        executed, hits, probe = 0, [], None
        for output in outputs:
            done, found, words = decode_output(output)
            executed += done
            hits.extend(found)
            probe = words if words is not None else probe
        return encode_output(executed, hits, probe)

    def known_answers(self) -> Sequence[KnownAnswer]:
        params, payload = genesis_lane()
        return (KnownAnswer("genesis-block-lane", params, payload, GENESIS_LANE_OUTPUT_SHA256),)


@lru_cache(maxsize=1)
def genesis_lane() -> tuple:
    """Block 0's header prefix and its plan lane holding the real nonce, under the block target."""
    from chronus.stratum.gatekeeper import decode_nbits_target

    from hyba_mine.plan import NoncePlan
    from hyba_mine.vectors import GENESIS

    plan = NoncePlan.for_header(GENESIS.prefix)
    position = plan.position_of(GENESIS.nonce)
    start = position - position % plan.lane_size
    params = {
        "target_hex": f"{decode_nbits_target(GENESIS.nbits):064x}",
        "window_bits": plan.window_bits,
        "offset": plan.offset,
        "stride": plan.stride,
        "lane_table": list(plan.lane_table),
        "start": start,
        "count": plan.lane_size,
        "probe_offset": position - start,
    }
    return params, bytes(GENESIS.prefix)


FLEET_KERNELS = [NonceWindowKernel()]
