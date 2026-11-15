# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Chronus iGPU on the Apple GPU through Metal (Mode B for HYBA Mine).

The SHA-256 core is not rewritten here. ``metal_source()`` takes the Chronus
OpenCL kernel ``chronus/kernels/sha256d_search.cl`` (the compression function
and K table that CI already runs against a CPU OpenCL runtime), changes only
the address-space spellings OpenCL and the Metal Shading Language disagree on,
and appends the plan kernel below, which maps each thread to a canonical plan
position exactly as ``hyba_mine.plan`` does. The host-side midstate, tail
words and target words come from
``OpenCLSha256dMinerBackend.build_kernel_args``, the same preprocessing the
OpenCL lane uses. If the Chronus kernel text changes shape, the Metal lane
refuses to build instead of guessing.

Bindings come from PyObjC (``pyobjc-framework-Metal``, installed on macOS by
``scripts/mine/setup_mac.sh``). Without them, or without a Metal device, the
lane is unavailable and the router says so.
"""

from __future__ import annotations

import contextlib
import struct
import time
from typing import Optional, Sequence, Tuple

from chronus.execution.asic_sha256 import _H0, sha256_block
from chronus.execution.opencl_sha256d import OpenCLSha256dMinerBackend

from hyba_mine.igpu import ROUTE_LABELS, ROUTE_METAL, LaneFault, LaneUnavailable, node_name
from hyba_mine.plan import MASK32
from hyba_mine.work import Hit, WindowResult, WorkUnit

CHRONUS_KERNEL = "sha256d_search.cl"
KERNEL_NAME = "hyba_sha256d_plan"
PARAMS_FORMAT = "<8I3I8I8I"  # midstate, tail, target words, 8 scalar fields below
PARAM_FIELDS = (
    "midstate[8]", "tail[3]", "target[8]", "offset", "stride", "window_bits",
    "lane_bits", "chunk_position", "count", "max_hits", "probe_index",
)
NO_PROBE = MASK32

METAL_PRELUDE = """#include <metal_stdlib>
using namespace metal;

// SHA-256 core below is chronus/kernels/sha256d_search.cl with OpenCL
// address-space spellings changed to Metal ones; see hyba_mine.metal.
"""

METAL_PLAN_KERNEL = """
struct HybaPlanParams {
    uint midstate[8];
    uint tail[3];
    uint target[8];
    uint offset;
    uint stride;
    uint window_bits;
    uint lane_bits;
    uint chunk_position;
    uint count;
    uint max_hits;
    uint probe_index;
};

kernel void hyba_sha256d_plan(
    constant HybaPlanParams& p [[buffer(0)]],
    constant uint* lane_table [[buffer(1)]],
    device uint* hits [[buffer(2)]],
    device atomic_uint* hit_count [[buffer(3)]],
    device uint* probe [[buffer(4)]],
    uint tid [[thread_position_in_grid]])
{
    if (tid >= p.count) {
        return;
    }
    uint position = p.chunk_position + tid;
    uint window_mask = (1u << p.window_bits) - 1u;
    uint lane_mask = (1u << p.lane_bits) - 1u;
    uint within = position & window_mask;
    uint lane = lane_table[within >> p.lane_bits];
    uint index = (position & ~window_mask) | (lane << p.lane_bits) | (within & lane_mask);
    uint nonce = p.offset + index * p.stride;

    uint state[8];
    for (int i = 0; i < 8; ++i) { state[i] = p.midstate[i]; }
    uint w[64];
    w[0] = p.tail[0];
    w[1] = p.tail[1];
    w[2] = p.tail[2];
    w[3] = bswap32(nonce);
    w[4] = 0x80000000U;
    for (int i = 5; i < 15; ++i) { w[i] = 0U; }
    w[15] = 0x00000280U;
    compress(state, w);

    uint inner[8] = {
        0x6a09e667U, 0xbb67ae85U, 0x3c6ef372U, 0xa54ff53aU,
        0x510e527fU, 0x9b05688cU, 0x1f83d9abU, 0x5be0cd19U,
    };
    for (int i = 0; i < 8; ++i) { w[i] = state[i]; }
    w[8] = 0x80000000U;
    for (int i = 9; i < 15; ++i) { w[i] = 0U; }
    w[15] = 0x00000100U;
    compress(inner, w);

    uint v[8];
    for (int i = 0; i < 8; ++i) { v[i] = bswap32(inner[i]); }
    if (tid == p.probe_index) {
        for (int i = 0; i < 8; ++i) { probe[i] = v[i]; }
    }
    bool le = true;
    for (int j = 7; j >= 0; --j) {
        if (v[j] != p.target[j]) {
            le = v[j] < p.target[j];
            break;
        }
    }
    if (!le) {
        return;
    }
    uint slot = atomic_fetch_add_explicit(hit_count, 1u, memory_order_relaxed);
    if (slot < p.max_hits) {
        hits[2u * slot] = tid;
        hits[2u * slot + 1u] = nonce;
    }
}
"""

_TRANSLATIONS = (
    ("__constant uint K[64]", "constant uint K[64]"),
    ("inline void compress(uint state[8], uint w[64])", "inline void compress(thread uint* state, thread uint* w)"),
)


def chronus_kernel_text() -> str:
    try:
        from chronus.igpu import kernel_source
    except ImportError:
        from importlib import resources

        return resources.files("chronus.kernels").joinpath(CHRONUS_KERNEL).read_text(encoding="utf-8")
    return kernel_source(CHRONUS_KERNEL)


def metal_source(kernel_text: Optional[str] = None) -> str:
    """Metal Shading Language source: Chronus SHA-256 core plus the plan kernel."""
    text = chronus_kernel_text() if kernel_text is None else kernel_text
    try:
        start = text.index("#define MASK32")
        end = text.index("__kernel void sha256d_search(")
    except ValueError as exc:
        raise LaneFault("the Chronus SHA-256d kernel no longer has the expected layout") from exc
    core = text[start:end]
    for old, new in _TRANSLATIONS:
        if core.count(old) != 1:
            raise LaneFault(f"the Chronus SHA-256d kernel changed ({old!r} not found once)")
        core = core.replace(old, new)
    core = "\n".join(line for line in core.splitlines() if not line.strip().startswith("#pragma"))
    if "__" in core or "get_global_id" in core:
        raise LaneFault("an OpenCL-only construct is left in the SHA-256 core")
    return METAL_PRELUDE + core + METAL_PLAN_KERNEL


def pack_params(
    header_prefix: bytes,
    target: int,
    offset: int,
    stride: int,
    window_bits: int,
    chunk_position: int,
    count: int,
    max_hits: int,
    probe_index: int,
) -> bytes:
    midstate, tail, target_words = OpenCLSha256dMinerBackend.build_kernel_args(
        bytes(header_prefix) + b"\x00\x00\x00\x00", target, 0
    )
    return struct.pack(
        PARAMS_FORMAT,
        *midstate, *tail, *target_words,
        offset, stride, window_bits, window_bits - 8, chunk_position & MASK32, count, max_hits, probe_index,
    )


def _bswap32(x: int) -> int:
    return int.from_bytes(x.to_bytes(4, "big"), "little")


def model_thread(params: bytes, lane_table: Sequence[int], tid: int) -> Tuple[int, Tuple[int, ...], bool]:
    """Python model of one kernel thread: (nonce, value words, is hit).

    Mirrors ``hyba_sha256d_plan`` statement by statement using the Chronus
    unrolled SHA-256 engine, so tests can check the parameter packing and the
    position mapping against hashlib without a GPU.
    """
    fields = struct.unpack(PARAMS_FORMAT, params)
    midstate, tail, target = fields[0:8], fields[8:11], fields[11:19]
    offset, stride, window_bits, lane_bits, chunk_position = fields[19:24]
    position = (chunk_position + tid) & MASK32
    window_mask = (1 << window_bits) - 1
    lane_mask = (1 << lane_bits) - 1
    within = position & window_mask
    lane = lane_table[within >> lane_bits]
    index = (position & ~window_mask & MASK32) | (lane << lane_bits) | (within & lane_mask)
    nonce = (offset + index * stride) & MASK32
    block2 = b"".join(w.to_bytes(4, "big") for w in tail) + nonce.to_bytes(4, "little")
    block2 += b"\x80" + b"\x00" * 39 + (640).to_bytes(8, "big")
    first = sha256_block(tuple(midstate), block2)
    block_inner = b"".join(w.to_bytes(4, "big") for w in first) + b"\x80" + b"\x00" * 23 + (256).to_bytes(8, "big")
    inner = sha256_block(_H0, block_inner)
    value = tuple(_bswap32(w) for w in inner)
    hit = True
    for j in range(7, -1, -1):
        if value[j] != target[j]:
            hit = value[j] < target[j]
            break
    return nonce, value, hit


def _size(metal, n: int):
    make = getattr(metal, "MTLSizeMake", None)
    return make(n, 1, 1) if make is not None else metal.MTLSize(n, 1, 1)


def _autorelease_pool():
    """Drain Objective-C autoreleased objects per dispatch.

    Units run on a long-lived worker thread; without a pool per dispatch the
    autoreleased command buffers and encoders (and the buffers they retain)
    would accumulate for the life of the thread.
    """
    try:
        import objc  # type: ignore[import-not-found]
    except ImportError:
        return contextlib.nullcontext()
    return objc.autorelease_pool()


def _view(buffer, nbytes: int):
    contents = buffer.contents()
    as_buffer = getattr(contents, "as_buffer", None)
    if as_buffer is None:
        raise LaneUnavailable("PyObjC cannot map Metal buffer memory on this installation")
    return as_buffer(nbytes)


class MetalLane:
    """Chronus iGPU bound to the Apple GPU through Metal."""

    route = ROUTE_METAL
    label = ROUTE_LABELS[ROUTE_METAL]
    MAX_THREADS = 1 << 22
    MAX_HITS = 1024
    HARD_HIT_CAP = 1 << 20

    def __init__(self, metal, device, pipeline, queue) -> None:
        self._metal = metal
        self._device = device
        self._pipeline = pipeline
        self._queue = queue
        width = int(pipeline.threadExecutionWidth())
        limit = int(pipeline.maxTotalThreadsPerThreadgroup())
        self._group = max(width, (min(256, limit) // width) * width)
        self._shared = metal.MTLResourceStorageModeShared

    @classmethod
    def open(cls) -> "MetalLane":
        try:
            import Metal  # type: ignore[import-not-found]
        except ImportError as exc:
            raise LaneUnavailable(
                "Metal bindings are not installed (pip install pyobjc-framework-Metal)"
            ) from exc
        device = Metal.MTLCreateSystemDefaultDevice()
        if device is None:
            raise LaneUnavailable("MTLCreateSystemDefaultDevice returned no Metal device")
        options = Metal.MTLCompileOptions.alloc().init()
        library, error = device.newLibraryWithSource_options_error_(metal_source(), options, None)
        if library is None:
            raise LaneFault(f"the Metal compiler rejected the plan kernel: {error}")
        function = library.newFunctionWithName_(KERNEL_NAME)
        if function is None:
            raise LaneFault(f"kernel function {KERNEL_NAME} not found after compilation")
        pipeline, error = device.newComputePipelineStateWithFunction_error_(function, None)
        if pipeline is None:
            raise LaneFault(f"Metal could not build the compute pipeline: {error}")
        return cls(Metal, device, pipeline, device.newCommandQueue())

    def describe(self) -> dict:
        return {
            "route": self.route,
            "label": self.label,
            "device": str(self._device.name()),
            "threads_per_group": self._group,
            "max_threads_per_dispatch": self.MAX_THREADS,
        }

    def _buffer(self, data: bytes):
        return self._device.newBufferWithBytes_length_options_(data, len(data), self._shared)

    def _dispatch(self, params: bytes, lane_table: bytes, count: int, capacity: int):
        with _autorelease_pool():
            return self._dispatch_once(params, lane_table, count, capacity)

    def _dispatch_once(self, params: bytes, lane_table: bytes, count: int, capacity: int):
        hits_buf = self._device.newBufferWithLength_options_(8 * capacity, self._shared)
        count_buf = self._buffer(b"\x00" * 4)
        probe_buf = self._buffer(b"\x00" * 32)
        command = self._queue.commandBuffer()
        encoder = command.computeCommandEncoder()
        encoder.setComputePipelineState_(self._pipeline)
        encoder.setBuffer_offset_atIndex_(self._buffer(params), 0, 0)
        encoder.setBuffer_offset_atIndex_(self._buffer(lane_table), 0, 1)
        encoder.setBuffer_offset_atIndex_(hits_buf, 0, 2)
        encoder.setBuffer_offset_atIndex_(count_buf, 0, 3)
        encoder.setBuffer_offset_atIndex_(probe_buf, 0, 4)
        groups = (count + self._group - 1) // self._group
        encoder.dispatchThreadgroups_threadsPerThreadgroup_(
            _size(self._metal, groups), _size(self._metal, self._group)
        )
        encoder.endEncoding()
        started = time.perf_counter_ns()
        command.commit()
        command.waitUntilCompleted()
        wall = time.perf_counter_ns() - started
        if command.status() != self._metal.MTLCommandBufferStatusCompleted or command.error() is not None:
            raise LaneFault(f"Metal command buffer failed: {command.error()}")
        try:
            gpu = (float(command.GPUEndTime()) - float(command.GPUStartTime())) * 1e9
        except AttributeError:
            gpu = 0.0
        device_ns = int(gpu) if gpu > 0 else wall
        found = struct.unpack("<I", bytes(_view(count_buf, 4)))[0]
        stored = min(found, capacity)
        pairs = struct.unpack(f"<{2 * stored}I", bytes(_view(hits_buf, 8 * stored))) if stored else ()
        probe = struct.unpack("<8I", bytes(_view(probe_buf, 32)))
        timing = "gpu_timestamps" if gpu > 0 else "host_wall_clock"
        return found, pairs, probe, device_ns, timing

    def execute(self, unit: WorkUnit) -> WindowResult:
        plan = unit.plan
        lane_table = struct.pack("<256I", *plan.lane_table)
        hits: list[Hit] = []
        probe_words = None
        device_ns = 0
        timing = set()
        rel = 0
        while rel < unit.count:
            count = min(self.MAX_THREADS, unit.count - rel)
            probe_index = unit.probe_offset - rel if rel <= unit.probe_offset < rel + count else NO_PROBE
            capacity = self.MAX_HITS
            while True:
                params = pack_params(
                    plan.header_prefix, unit.target, plan.offset, plan.stride, plan.window_bits,
                    unit.start + rel, count, capacity, probe_index,
                )
                found, pairs, probe, elapsed, how = self._dispatch(params, lane_table, count, capacity)
                device_ns += elapsed
                timing.add(how)
                if found <= capacity or capacity >= self.HARD_HIT_CAP:
                    break
                capacity = min(found, self.HARD_HIT_CAP)
            if found > capacity:
                raise LaneFault("more hits than the hit buffer can hold; target is too easy for mining")
            hits.extend(Hit(rel + pairs[2 * i], pairs[2 * i + 1]) for i in range(len(pairs) // 2))
            if probe_index != NO_PROBE:
                probe_words = tuple(probe)
            rel += count
        return WindowResult(
            unit_id=unit.unit_id,
            executed=unit.count,
            device_ns=max(1, device_ns),
            hits=tuple(sorted(hits, key=lambda h: h.offset)),
            probe_words=probe_words,
            executed_route=self.route,
            node=node_name(),
            detail={"timing": "+".join(sorted(timing)), "device": str(self._device.name())},
        )

    def close(self) -> None:
        self._queue = None
