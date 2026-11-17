# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Chronus iGPU bound to an OpenCL GPU (Windows, Linux; any OpenCL GPU vendor).

The SHA-256 core is not rewritten here. ``opencl_source()`` takes the Chronus
OpenCL kernel (``src/chronus/kernels/sha256d_search.cl``) verbatim, from
``#define MASK32`` up to its own search kernel, and appends a plan kernel that
is a line-for-line translation of ``metal.METAL_PLAN_KERNEL``: same position ->
window/lane/index -> nonce mapping, same two compressions, same little-endian
target compare, same probe and hit-buffer contract. Parameters are packed by
``metal.pack_params`` (which uses the Chronus OpenCL backend's own
``build_kernel_args``), so the Metal, OpenCL and host paths share one packing.

A device is mined on only after it passes the known-answer and probe-parity
checks in ``bist`` on that device. Discovery never raises: a missing pyopencl,
a missing platform or a machine without an OpenCL GPU device is an honest
"unavailable" reason, and the CPU keeps mining through Mode A. OpenCL CPU devices are skipped (the CPU already mines through
Mode A), and so is a second view of the same physical GPU.

pyopencl is imported only inside functions, so importing this module is safe
on a machine without it.
"""

from __future__ import annotations

import contextlib
import os
import re
import struct
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from hyba_mine.igpu import (
    BACKEND_OPENCL,
    COMPUTE_OPENCL_GPU,
    LaneFault,
    LaneUnavailable,
    node_name,
    opencl_route,
    route_label,
)
from hyba_mine.metal import CHRONUS_KERNEL, NO_PROBE, PARAM_FIELDS, PARAMS_FORMAT, chronus_kernel_text, pack_params
from hyba_mine.work import Hit, UnitAborted, WindowResult, WorkUnit

KERNEL_NAME = "hyba_sha256d_plan"
DISABLE_ENV = "HYBA_MINE_DISABLE_OPENCL"
LAYERED_PLATFORMS = ("OpenCLOn12", "clvk")


def _param_index() -> dict:
    index, at = {}, 0
    for name in PARAM_FIELDS:
        match = re.fullmatch(r"(\w+)(?:\[(\d+)\])?", name)
        index[match.group(1)] = at
        at += int(match.group(2) or 1)
    if at != struct.calcsize(PARAMS_FORMAT) // 4:
        raise ImportError("hyba_mine.metal PARAM_FIELDS no longer matches PARAMS_FORMAT")
    return index


PARAM_INDEX = _param_index()

OPENCL_PRELUDE = f"/* HYBA Mine plan kernel; SHA-256 core from Chronus {CHRONUS_KERNEL}, unchanged. */\n"

OPENCL_PLAN_KERNEL = "\n".join(f"#define P_{name.upper()} {at}" for name, at in PARAM_INDEX.items()) + r"""

__kernel void hyba_sha256d_plan(__constant uint* p, __constant uint* lane_table,
    __global uint* hits, __global uint* hit_count, __global uint* probe)
{
    uint tid = (uint)get_global_id(0);
    if (tid >= p[P_COUNT]) {
        return;
    }
    uint position = p[P_CHUNK_POSITION] + tid;
    uint window_mask = (1u << p[P_WINDOW_BITS]) - 1u;
    uint lane_mask = (1u << p[P_LANE_BITS]) - 1u;
    uint within = position & window_mask;
    uint lane = lane_table[within >> p[P_LANE_BITS]];
    uint index = (position & ~window_mask) | (lane << p[P_LANE_BITS]) | (within & lane_mask);
    uint nonce = p[P_OFFSET] + index * p[P_STRIDE];

    uint state[8];
    for (int i = 0; i < 8; ++i) { state[i] = p[P_MIDSTATE + i]; }
    uint w[64];
    w[0] = p[P_TAIL];
    w[1] = p[P_TAIL + 1];
    w[2] = p[P_TAIL + 2];
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
    if (tid == p[P_PROBE_INDEX]) {
        for (int i = 0; i < 8; ++i) { probe[i] = v[i]; }
    }
    bool le = true;
    for (int j = 7; j >= 0; --j) {
        if (v[j] != p[P_TARGET + j]) {
            le = v[j] < p[P_TARGET + j];
            break;
        }
    }
    if (!le) {
        return;
    }
    uint slot = atomic_inc(hit_count);
    if (slot < p[P_MAX_HITS]) {
        hits[2u * slot] = tid;
        hits[2u * slot + 1u] = nonce;
    }
}
"""


def opencl_source(kernel_text: Optional[str] = None) -> str:
    text = chronus_kernel_text() if kernel_text is None else kernel_text
    try:
        core = text[text.index("#define MASK32"):text.index("__kernel void sha256d_search(")]
    except ValueError:
        raise LaneFault("the Chronus SHA-256d kernel no longer has the expected layout") from None
    for needle in ("__constant uint K[64]", "inline void compress(uint state[8], uint w[64])",
                   "inline uint bswap32(uint x)"):
        if core.count(needle) != 1:
            raise LaneFault(f"the Chronus SHA-256d kernel changed ({needle!r} not found once)")
    if "get_global_id" in core or "__kernel" in core:
        raise LaneFault("the Chronus SHA-256 core now contains a kernel entry point")
    return OPENCL_PRELUDE + core + OPENCL_PLAN_KERNEL


# ------------------------------------------------------------------ discovery
def _safe(read, default=None):
    try:
        return read()
    except Exception:  # driver attributes vary by vendor; absence is not an error
        return default


def _device_type(cl, value: int) -> str:
    # Classify by bits: AMD reports the type string as "ALL | GPU".
    if value & cl.device_type.GPU:
        return "GPU"
    if value & cl.device_type.CPU:
        return "CPU"
    if value & getattr(cl.device_type, "ACCELERATOR", 0):
        return "ACCELERATOR"
    return "OTHER"


def _physical_id(device) -> Optional[str]:
    topo = _safe(lambda: device.topology_amd)
    if topo is not None:
        bus, dev, fn = (_safe(lambda: getattr(topo, n)) for n in ("bus", "device", "function"))
        if bus is not None and dev is not None:
            return f"pci:{int(bus):02x}:{int(dev):02x}.{int(fn or 0)}"
    bus = _safe(lambda: device.pci_bus_id_nv)
    slot = _safe(lambda: device.pci_slot_id_nv)
    if bus is not None and slot is not None:
        return f"pci:{int(bus):02x}:{int(slot) >> 3:02x}.{int(slot) & 7}"
    info = _safe(lambda: device.pci_bus_info_khr)
    if info is not None:
        return f"pci:{_safe(lambda: info.pci_bus, 0):02x}:{_safe(lambda: info.pci_device, 0):02x}.{_safe(lambda: info.pci_function, 0)}"
    return None


@dataclass(frozen=True)
class OpenCLDevice:
    platform_index: int
    device_index: int
    platform: str
    platform_version: str
    name: str
    board_name: Optional[str]
    vendor: str
    driver_version: str
    opencl_version: str
    device_type: str
    compute_units_reported: int
    max_work_group_size: int
    global_mem_bytes: int
    physical_id: Optional[str]
    handle: Any = field(default=None, compare=False, repr=False)

    @property
    def key(self) -> str:
        return f"p{self.platform_index}d{self.device_index}"

    @property
    def route(self) -> str:
        return opencl_route(self.platform_index, self.device_index)

    def to_dict(self) -> dict:
        return {
            "device_key": self.key, "route": self.route, "device": self.name, "board_name": self.board_name,
            "platform": self.platform, "platform_version": self.platform_version, "vendor": self.vendor,
            "driver_version": self.driver_version, "opencl_version": self.opencl_version,
            "device_type": self.device_type, "compute_units_reported": self.compute_units_reported,
            "max_work_group_size": self.max_work_group_size, "global_mem_bytes": self.global_mem_bytes,
            "physical_id": self.physical_id,
        }


@dataclass(frozen=True)
class OpenCLDiscovery:
    available: bool
    reason: Optional[str]
    pyopencl_version: Optional[str] = None
    devices: tuple = ()
    skipped: tuple = ()  # (OpenCLDevice, stage, reason)
    errors: tuple = ()

    @property
    def gpus(self) -> tuple:
        skipped = {d.key for d, _, _ in self.skipped}
        return tuple(d for d in self.devices if d.device_type == "GPU" and d.key not in skipped)

    def records(self) -> list:
        out = []
        skipped = {d.key: (stage, reason) for d, stage, reason in self.skipped}
        for device in self.devices:
            stage, reason = skipped.get(device.key, ("detect", "GPU candidate; qualifies only after its self-test"))
            out.append({"backend": BACKEND_OPENCL, **device.to_dict(),
                        "eligible": False if device.key in skipped else None, "stage": stage, "reason": reason})
        return out

    @classmethod
    def unavailable(cls, reason: str, version: Optional[str] = None) -> "OpenCLDiscovery":
        return cls(False, reason, version)


def discover(env: Optional[Mapping[str, str]] = None, cl_module=None) -> OpenCLDiscovery:
    """Enumerate OpenCL devices and decide which GPUs are candidates. Never raises."""
    env = os.environ if env is None else env
    if env.get(DISABLE_ENV) == "1":
        return OpenCLDiscovery.unavailable(f"OPENCL_DISABLED: {DISABLE_ENV}=1 is set")
    cl = cl_module
    if cl is None:
        try:
            import pyopencl as cl  # type: ignore[import-not-found]
        except ImportError:
            return OpenCLDiscovery.unavailable("OPENCL_UNAVAILABLE: pyopencl is not installed (pip install 'hyba-mine[opencl]')")
        except Exception as exc:  # a broken install (e.g. its numpy) must not stop CPU mining
            return OpenCLDiscovery.unavailable(f"OPENCL_UNAVAILABLE: pyopencl failed to import ({type(exc).__name__}: {exc})")
    version = getattr(cl, "VERSION_TEXT", None)
    try:
        platforms = list(cl.get_platforms())
    except Exception as exc:
        return OpenCLDiscovery.unavailable(f"OPENCL_NO_PLATFORM: {type(exc).__name__}: {exc}", version)
    if not platforms:
        return OpenCLDiscovery.unavailable("OPENCL_NO_PLATFORM: no OpenCL platform is installed", version)

    devices, errors = [], []
    for pi, plat in enumerate(platforms):
        try:
            plat_devices = list(plat.get_devices())
        except Exception as exc:
            errors.append({"platform_index": pi, "error": f"{type(exc).__name__}: {exc}"})
            continue
        for di, dev in enumerate(plat_devices):
            devices.append(OpenCLDevice(
                platform_index=pi, device_index=di,
                platform=str(_safe(lambda: plat.name, "")).strip(),
                platform_version=str(_safe(lambda: plat.version, "")).strip(),
                name=str(_safe(lambda: dev.name, "")).strip(),
                board_name=_safe(lambda: str(dev.board_name_amd).strip()),
                vendor=str(_safe(lambda: dev.vendor, "")).strip(),
                driver_version=str(_safe(lambda: dev.driver_version, "")).strip(),
                opencl_version=str(_safe(lambda: dev.version, "")).strip(),
                device_type=_device_type(cl, int(_safe(lambda: dev.type, 0))),
                compute_units_reported=int(_safe(lambda: dev.max_compute_units, 0)),
                max_work_group_size=int(_safe(lambda: dev.max_work_group_size, 0)),
                global_mem_bytes=int(_safe(lambda: dev.global_mem_size, 0)),
                physical_id=_physical_id(dev),
                handle=dev,
            ))

    native_gpu = any(d.device_type == "GPU" and not d.platform.startswith(LAYERED_PLATFORMS) for d in devices)
    skipped, seen_physical = [], {}
    for d in devices:
        if d.device_type == "CPU":
            skipped.append((d, "policy", "OpenCL CPU device skipped: the CPU already mines through Chronus iGPU Mode A (no double counting)"))
        elif d.device_type != "GPU":
            skipped.append((d, "policy", "not a GPU device; HYBA Mine offers OpenCL routes on GPU devices only"))
        elif native_gpu and d.platform.startswith(LAYERED_PLATFORMS):
            skipped.append((d, "policy", f"layered platform {d.platform} re-exposes GPUs of native platforms; skipped to avoid hashing one GPU twice"))
        elif d.physical_id and d.physical_id in seen_physical:
            skipped.append((d, "policy", f"same physical GPU as {seen_physical[d.physical_id]} ({d.physical_id}); skipped"))
        elif d.physical_id:
            seen_physical[d.physical_id] = d.key

    disc = OpenCLDiscovery(True, None, version, tuple(devices), tuple(skipped), tuple(errors))
    if not disc.gpus:
        reasons = "; ".join(f"{d.key}: {r}" for d, _, r in skipped) or "no devices"
        return OpenCLDiscovery(True, f"OPENCL_NO_GPU: no OpenCL GPU device ({len(skipped)} device(s) skipped: {reasons})",
                               version, tuple(devices), tuple(skipped), tuple(errors))
    return disc


# ------------------------------------------------------------------------ lane
class OpenCLLane:
    """Chronus iGPU plan kernel on one OpenCL GPU.

    ``abort(unit_id)`` stops the unit at the next dispatch boundary; dispatches
    are kept short (about ``DISPATCH_TARGET_S`` of device time, adapted per
    dispatch within ``MIN_THREADS``..``MAX_THREADS``) so an abort lands quickly
    and no launch nears the Windows display-driver watchdog. The executed count
    of an aborted unit covers whole completed dispatches only. An abort that
    arrives before ``execute`` registered its unit is remembered and refused.
    """

    backend = BACKEND_OPENCL
    MAX_HITS = 1024
    HARD_HIT_CAP = 1 << 20
    MIN_THREADS = 1 << 16
    MAX_THREADS = 1 << 22
    START_THREADS = 1 << 18
    DISPATCH_TARGET_S = 0.05

    def __init__(self, cl, device: OpenCLDevice, context, queue, kernel, *, profiling: bool) -> None:
        self._cl = cl
        self.device = device
        self.route = device.route
        self.label = route_label(self.route)
        self._ctx, self._queue, self._kernel = context, queue, kernel
        self._profiling = profiling
        wg = int(_safe(lambda: kernel.get_work_group_info(cl.kernel_work_group_info.WORK_GROUP_SIZE, device.handle), 64))
        group = 1
        while group * 2 <= min(256, max(1, wg)):
            group *= 2
        self._group = group
        mf = cl.mem_flags
        self._params_buf = cl.Buffer(context, mf.READ_ONLY, size=struct.calcsize(PARAMS_FORMAT))
        self._lane_buf = cl.Buffer(context, mf.READ_ONLY, size=256 * 4)
        self._hits_capacity = self.MAX_HITS
        self._hits_buf = cl.Buffer(context, mf.WRITE_ONLY, size=8 * self._hits_capacity)
        self._count_buf = cl.Buffer(context, mf.READ_WRITE, size=4)
        self._probe_buf = cl.Buffer(context, mf.WRITE_ONLY, size=32)
        self._threads = self.START_THREADS
        self._limit: Optional[int] = None
        self._state = threading.Lock()
        self._current: Optional[str] = None
        self._stop = threading.Event()
        self._pending_abort: Optional[str] = None
        self._closed = False

    @classmethod
    def open(cls, device: OpenCLDevice, *, cl_module=None) -> "OpenCLLane":
        cl = cl_module
        if cl is None:
            try:
                import pyopencl as cl  # type: ignore[import-not-found]
            except ImportError as exc:
                raise LaneUnavailable("pyopencl is not installed (pip install 'hyba-mine[opencl]')") from exc
        try:
            ctx = cl.Context([device.handle])
            try:
                queue = cl.CommandQueue(ctx, device.handle, properties=cl.command_queue_properties.PROFILING_ENABLE)
                profiling = True
            except cl.Error:
                queue = cl.CommandQueue(ctx, device.handle)
                profiling = False
        except cl.Error as exc:
            raise LaneUnavailable(f"OpenCL context or queue could not be created on {device.name}: {exc}") from None
        program = cl.Program(ctx, opencl_source())
        try:
            program.build()
        except cl.Error as exc:
            log = str(_safe(lambda: program.get_build_info(device.handle, cl.program_build_info.LOG), ""))
            raise LaneFault(f"OpenCL compiler rejected the plan kernel on {device.name}: {exc}; build log: {log[:400]}") from None
        try:
            kernel = cl.Kernel(program, KERNEL_NAME)
            return cls(cl, device, ctx, queue, kernel, profiling=profiling)
        except cl.Error as exc:
            raise LaneFault(f"OpenCL kernel setup failed on {device.name}: {exc}") from None

    def describe(self) -> dict:
        d = self.device
        return {
            "route": self.route, "label": self.label, "device": d.name, "device_key": d.key,
            "board_name": d.board_name, "platform": d.platform, "vendor": d.vendor,
            "driver_version": d.driver_version, "opencl_version": d.opencl_version,
            "pyopencl_version": getattr(self._cl, "VERSION_TEXT", None), "device_type": d.device_type,
            "compute_units_reported": d.compute_units_reported,
            "compute_units_basis": "CL_DEVICE_MAX_COMPUTE_UNITS as reported by the driver",
            "max_work_group_size": d.max_work_group_size, "work_group_size": self._group,
            "threads_per_dispatch": {"min": self.MIN_THREADS, "max": self.MAX_THREADS, "current": self._threads},
            "dispatch_target_s": self.DISPATCH_TARGET_S,
            "timing_basis": "opencl_event_profiling" if self._profiling else "host_wall_clock",
            "compute_unit": COMPUTE_OPENCL_GPU,
        }

    @contextlib.contextmanager
    def limited_dispatch(self, threads: int):
        """Cap threads per dispatch (tests and parity checks force chunk boundaries with it)."""
        previous, self._limit = self._limit, max(1, int(threads))
        try:
            yield self
        finally:
            self._limit = previous

    def _dispatch(self, params: bytes, count: int, capacity: int):
        cl = self._cl
        try:
            if capacity > self._hits_capacity:
                self._hits_buf = cl.Buffer(self._ctx, cl.mem_flags.WRITE_ONLY, size=8 * capacity)
                self._hits_capacity = capacity
            cl.enqueue_copy(self._queue, self._params_buf, params, is_blocking=True)
            cl.enqueue_copy(self._queue, self._count_buf, b"\x00\x00\x00\x00", is_blocking=True)
            self._kernel.set_args(self._params_buf, self._lane_buf, self._hits_buf, self._count_buf, self._probe_buf)
            size = (count + self._group - 1) // self._group * self._group
            started = time.perf_counter_ns()
            event = cl.enqueue_nd_range_kernel(self._queue, self._kernel, (size,), (self._group,))
            event.wait()
            wall = time.perf_counter_ns() - started
            device_ns, timing = wall, "host_wall_clock"
            if self._profiling:
                profiled = _safe(lambda: int(event.profile.end - event.profile.start))
                if profiled and profiled > 0:
                    device_ns, timing = profiled, "opencl_event_profiling"
            found_raw = bytearray(4)
            cl.enqueue_copy(self._queue, found_raw, self._count_buf, is_blocking=True)
            found = struct.unpack("<I", found_raw)[0]
            stored = min(found, capacity)
            pairs: tuple = ()
            if stored:
                raw = bytearray(8 * stored)
                cl.enqueue_copy(self._queue, raw, self._hits_buf, is_blocking=True)
                pairs = struct.unpack(f"<{2 * stored}I", raw)
            probe_raw = bytearray(32)
            cl.enqueue_copy(self._queue, probe_raw, self._probe_buf, is_blocking=True)
        except cl.Error as exc:
            raise LaneFault(f"OpenCL dispatch failed on {self.device.name}: {exc}") from None
        return found, pairs, struct.unpack("<8I", probe_raw), device_ns, timing

    def execute(self, unit: WorkUnit) -> WindowResult:
        if self._closed:
            raise LaneUnavailable(f"{self.route} is closed")
        plan = unit.plan
        try:
            self._cl.enqueue_copy(self._queue, self._lane_buf, struct.pack("<256I", *plan.lane_table), is_blocking=True)
        except self._cl.Error as exc:
            raise LaneFault(f"OpenCL lane-table upload failed on {self.device.name}: {exc}") from None
        hits: list = []
        probe_words = None
        device_ns = 0
        timing: set = set()
        dispatches = 0
        rel = 0
        with self._state:
            pending, self._pending_abort = self._pending_abort, None
            if pending == unit.unit_id:
                raise UnitAborted(unit.unit_id, 0, 0, self.route, node_name())
            self._current = unit.unit_id
            self._stop.clear()
        try:
            while rel < unit.count:
                if self._stop.is_set():
                    raise UnitAborted(unit.unit_id, rel, max(1, device_ns), self.route, node_name(),
                                      hits_found=len(hits))
                threads = self._threads if self._limit is None else min(self._threads, self._limit)
                count = min(threads, unit.count - rel)
                probe_index = unit.probe_offset - rel if rel <= unit.probe_offset < rel + count else NO_PROBE
                capacity = self.MAX_HITS
                while True:
                    params = pack_params(plan.header_prefix, unit.target, plan.offset, plan.stride, plan.window_bits,
                                         unit.start + rel, count, capacity, probe_index)
                    found, pairs, probe, elapsed, how = self._dispatch(params, count, capacity)
                    dispatches += 1
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
                seconds = elapsed / 1e9
                if count == threads and seconds < self.DISPATCH_TARGET_S / 2 and self._threads * 2 <= self.MAX_THREADS:
                    self._threads *= 2
                elif seconds > 2 * self.DISPATCH_TARGET_S and self._threads // 2 >= self.MIN_THREADS:
                    self._threads //= 2
        finally:
            with self._state:
                self._current = None
        return WindowResult(
            unit_id=unit.unit_id,
            executed=unit.count,
            device_ns=max(1, device_ns),
            hits=tuple(sorted(hits, key=lambda h: h.offset)),
            probe_words=probe_words,
            executed_route=self.route,
            node=node_name(),
            detail={"timing": "+".join(sorted(timing)), "device": self.device.name, "device_key": self.device.key,
                    "dispatches": dispatches, "threads_per_dispatch": self._threads},
        )

    def abort(self, unit_id: str) -> bool:
        with self._state:
            if self._current != unit_id:
                self._pending_abort = unit_id
                return True
            self._stop.set()
            return True

    def close(self) -> None:
        if self._closed:
            return
        self._stop.set()
        self._closed = True
        with contextlib.suppress(Exception):
            self._queue.finish()
        for name in ("_params_buf", "_lane_buf", "_hits_buf", "_count_buf", "_probe_buf"):
            buf = getattr(self, name, None)
            if buf is not None:
                with contextlib.suppress(Exception):
                    buf.release()
            setattr(self, name, None)
        self._kernel = self._queue = self._ctx = None
