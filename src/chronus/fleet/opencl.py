# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""OpenCL adapter: the Chronus iGPU in Mode B on an OpenCL GPU device.

Loaded only when pyopencl imports and an OpenCL device of type GPU exists
(Intel UHD/Iris, AMD, NVIDIA, or Apple GPUs through Apple's OpenCL). CPU
OpenCL devices are never used for this route, so CPU work cannot be
reported as GPU work. ``CHRONUS_FLEET_OPENCL_DEVICE`` selects among several
GPU devices by index.

Kernels:

* ``m15_pairs`` from the packaged ``chronus/kernels/m15_fold.cl``, read through
  ``chronus.igpu.kernel_source`` and refused unless its SHA-256 matches;
* ``pv_lattice_fold`` through the existing ``chronus.backends.opencl_pv``
  backend, which has its own pinned kernel digest, Lucas known-answer test
  and host-side exact parity check.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any

from chronus.fleet.adapters import MODE_B, DeviceAdapter
from chronus.fleet.errors import DeviceUnavailableError
from chronus.fleet.kernels import ROUTE_OPENCL

DEVICE_ENV = "CHRONUS_FLEET_OPENCL_DEVICE"
M15_KERNEL_FILE = "m15_fold.cl"
M15_KERNEL_SHA256 = "341439f2540b007fe2a41897e41887bde094c89830f1b2ec36478b7d826d1b88"


class OpenCLEngine:
    engine = "pyopencl"

    def __init__(self, cl: Any, np: Any, device: Any) -> None:
        from chronus.igpu import kernel_source

        source = kernel_source(M15_KERNEL_FILE)
        if hashlib.sha256(source.encode("utf-8")).hexdigest() != M15_KERNEL_SHA256:
            raise DeviceUnavailableError("packaged m15_fold.cl does not match its pinned digest")
        self.cl = cl
        self.np = np
        self.device = device
        self.context = cl.Context([device])
        self.queue = cl.CommandQueue(self.context)
        self.program = cl.Program(self.context, source).build()
        self.ops = {"m15_pairs"}
        self.pv_backend = None
        self.pv_reason = None
        try:
            from chronus.backends.opencl_pv import OpenCLPVBackend

            self.pv_backend = OpenCLPVBackend(device=device)
            self.ops.update({"pv_lattice_fold", "pv_field_scale"})
        except Exception as exc:
            self.pv_reason = f"{type(exc).__name__}: {exc}"

    def m15_pairs(self, tile: bytes, matrix: tuple[int, int, int, int]) -> bytes:
        cl, np = self.cl, self.np
        pairs = len(tile) // 2
        if pairs == 0:
            return b""
        flags = cl.mem_flags
        host = np.frombuffer(tile, dtype=np.uint8).copy()
        d_in = cl.Buffer(self.context, flags.READ_ONLY | flags.COPY_HOST_PTR, hostbuf=host)
        d_out = cl.Buffer(self.context, flags.WRITE_ONLY, size=len(tile))
        m00, m01, m10, m11 = (np.uint32(v) for v in matrix)
        self.program.m15_pairs(self.queue, (pairs,), None, d_in, d_out, m00, m01, m10, m11, np.uint32(pairs))
        out = np.empty(len(tile), dtype=np.uint8)
        cl.enqueue_copy(self.queue, out, d_out)
        self.queue.finish()
        return out.tobytes()

    def pv_lattice_fold(self, values: list, order: int) -> list:
        if self.pv_backend is None:
            raise DeviceUnavailableError(f"OpenCL PV backend unavailable: {self.pv_reason}")
        outputs, _ = self.pv_backend.dispatch_pv_fold(values, order)
        return outputs

    def pv_field_scale(self, tile: bytes, index: int) -> bytes:
        import struct
        if self.pv_backend is None:
            raise DeviceUnavailableError(f"OpenCL PV backend unavailable: {self.pv_reason}")
        outputs = self.pv_backend.dispatch_field_scale(list(struct.iter_unpack('<HH', tile)), index)
        return b''.join(struct.pack('<HH', *pair) for pair in outputs)


class OpenCLAdapter(DeviceAdapter):
    route = ROUTE_OPENCL
    name = "opencl-gpu"
    silicon = "gpu"
    mode = MODE_B

    def _detect(self):
        try:
            import numpy as np
            import pyopencl as cl
        except ImportError as exc:
            return False, {}, f"pyopencl not importable ({exc})", None
        try:
            devices = [
                (platform, device)
                for platform in cl.get_platforms()
                for device in platform.get_devices()
                if device.type & cl.device_type.GPU
            ]
        except cl.Error as exc:
            return False, {}, f"OpenCL platform query failed: {exc}", None
        if not devices:
            return False, {}, "no OpenCL GPU device (CPU OpenCL devices are not used for this route)", None
        index = int(os.environ.get(DEVICE_ENV, "0"))
        if not 0 <= index < len(devices):
            return False, {}, f"{DEVICE_ENV}={index} but {len(devices)} GPU device(s) exist", None
        platform, device = devices[index]
        engine = OpenCLEngine(cl, np, device)
        description = {
            "engine": "pyopencl",
            "platform": platform.name.strip(),
            "device_name": device.name.strip(),
            "vendor": device.vendor.strip(),
            "driver_version": device.driver_version.strip(),
            "opencl_version": device.version.strip(),
            "compute_units_reported": int(device.max_compute_units),
            "global_memory_bytes": int(device.global_mem_size),
            "host_unified_memory": bool(device.host_unified_memory),
            "pv_lattice_fold": "available" if engine.pv_backend is not None else engine.pv_reason,
        }
        return True, description, None, engine
