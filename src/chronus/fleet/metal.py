# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""Metal adapter: the Chronus iGPU in Mode B on Apple GPU silicon.

Two engines, tried in this order unless ``CHRONUS_FLEET_METAL_ENGINE`` picks
one (``mlx`` or ``pyobjc``):

* MLX (``pip install mlx``, Apple Silicon only): integer array kernels pinned
  to the GPU stream (``mx.stream(mx.gpu)``). The route is unavailable unless
  ``mx.metal.is_available()`` is true, so MLX's CPU backend is never reported
  as GPU work.
* PyObjC Metal (``pip install pyobjc-framework-Metal``): a Metal Shading
  Language kernel compiled at start-up and dispatched on the system default
  MTLDevice.

Apple Silicon shares one unified memory between CPU and GPU; MLX arrays and
``MTLResourceStorageModeShared`` buffers live in it. The adapter is loaded only
on macOS, and only when an engine imports and a device answers. Like every
route it must reproduce each kernel's known answers before it receives work.
Nothing here has been measured until a timed run on the Mac records it.
"""

from __future__ import annotations

import os
import platform
import struct
import sys
from typing import Any

from chronus.fleet.adapters import MODE_B, DeviceAdapter
from chronus.fleet.errors import DeviceUnavailableError
from chronus.fleet.kernels import ROUTE_METAL

ENGINE_ENV = "CHRONUS_FLEET_METAL_ENGINE"

MSL_SOURCE = """
#include <metal_stdlib>
using namespace metal;

kernel void m15_pairs(device const uchar *in_pairs [[buffer(0)]],
                      device uchar *out_pairs [[buffer(1)]],
                      constant uint *m [[buffer(2)]],
                      constant uint &pairs [[buffer(3)]],
                      uint gid [[thread_position_in_grid]]) {
    if (gid >= pairs) {
        return;
    }
    uint a = in_pairs[2 * gid];
    uint b = in_pairs[2 * gid + 1];
    out_pairs[2 * gid] = (uchar)((m[0] * a + m[1] * b) & 0xFFu);
    out_pairs[2 * gid + 1] = (uchar)((m[2] * a + m[3] * b) & 0xFFu);
}

kernel void pv_field_scale(device const ushort2 *inputs [[buffer(0)]],
                           device ushort2 *outputs [[buffer(1)]],
                           constant uint *factor [[buffer(2)]],
                           constant uint &pairs [[buffer(3)]],
                           uint gid [[thread_position_in_grid]]) {
    if (gid >= pairs) return;
    uint a=inputs[gid].x, b=inputs[gid].y, c=factor[0], d=factor[1];
    outputs[gid] = ushort2((a*c+b*d)%257u, (a*d+b*c+b*d)%257u);
}
"""


class MLXEngine:
    """Integer kernels on the Apple GPU through MLX (unified memory)."""

    engine = "mlx"
    ops = frozenset({"m15_pairs", "dual_space", "gf_matvec", "pv_field_scale"})

    def __init__(self, mx: Any, np: Any) -> None:
        self.mx = mx
        self.np = np

    def _u32(self, data: Any) -> Any:
        return self.mx.array(data).astype(self.mx.uint32)

    def m15_pairs(self, tile: bytes, matrix: tuple[int, int, int, int]) -> bytes:
        mx, np = self.mx, self.np
        m00, m01, m10, m11 = matrix
        with mx.stream(mx.gpu):
            pairs = self._u32(np.frombuffer(tile, dtype=np.uint8).reshape(-1, 2))
            a, b = pairs[:, 0], pairs[:, 1]
            y0 = mx.remainder(a * m00 + b * m01, 256)
            y1 = mx.remainder(a * m10 + b * m11, 256)
            out = mx.stack([y0, y1], axis=1).astype(mx.uint8)
            mx.eval(out)
        return np.array(out).astype(np.uint8).tobytes()

    def dual_space(self, q: bytes, y: bytes, inverse: tuple[int, int, int, int]) -> int:
        mx, np = self.mx, self.np
        e, f, g, h = inverse
        with mx.stream(mx.gpu):
            qp = self._u32(np.frombuffer(q, dtype=np.uint8).reshape(-1, 2))
            yp = self._u32(np.frombuffer(y, dtype=np.uint8).reshape(-1, 2))
            qa = mx.remainder(qp[:, 0] * e + qp[:, 1] * f, 256)
            qb = mx.remainder(qp[:, 0] * g + qp[:, 1] * h, 256)
            terms = mx.remainder(qa * yp[:, 0] + qb * yp[:, 1], 256)
            total = mx.sum(terms)
            mx.eval(total)
        return int(total.item())

    def gf_matvec(self, tile: bytes, rows: int, cols: int, p: int) -> bytes:
        mx, np = self.mx, self.np
        words = np.frombuffer(tile, dtype="<u4").astype(np.uint32)
        with mx.stream(mx.gpu):
            x = self._u32(words[-cols:])
            a = self._u32(words[:-cols].reshape(rows, cols))
            products = mx.remainder(a * x[None, :], p)
            y = mx.remainder(mx.sum(products, axis=1), p)
            mx.eval(y)
        return np.array(y).astype("<u4").tobytes()

    def pv_field_scale(self, tile: bytes, index: int) -> bytes:
        from chronus.core.scaling import PVScale
        mx, np = self.mx, self.np
        c,d = PVScale(index).field_factor()
        with mx.stream(mx.gpu):
            pairs = self._u32(np.frombuffer(tile, dtype='<u2').reshape(-1,2))
            a,b = pairs[:,0], pairs[:,1]
            out = mx.stack([mx.remainder(a*c+b*d,257),
                            mx.remainder(a*d+b*c+b*d,257)],axis=1).astype(mx.uint16)
            mx.eval(out)
        return np.array(out).astype('<u2').tobytes()


class PyObjCMetalEngine:
    """The M15 pair kernel in Metal Shading Language, dispatched through PyObjC."""

    engine = "metal-pyobjc"
    ops = frozenset({"m15_pairs", "pv_field_scale"})

    def __init__(self, metal: Any, device: Any) -> None:
        self.Metal = metal
        self.device = device
        library, error = device.newLibraryWithSource_options_error_(MSL_SOURCE, None, None)
        if library is None:
            raise DeviceUnavailableError(f"Metal kernel compilation failed: {error}")
        function = library.newFunctionWithName_("m15_pairs")
        pipeline, error = device.newComputePipelineStateWithFunction_error_(function, None)
        if pipeline is None:
            raise DeviceUnavailableError(f"Metal pipeline creation failed: {error}")
        self.pipeline = pipeline
        function = library.newFunctionWithName_("pv_field_scale")
        field_pipeline, error = device.newComputePipelineStateWithFunction_error_(function, None)
        if field_pipeline is None:
            raise DeviceUnavailableError(f"Metal field pipeline creation failed: {error}")
        self.field_pipeline = field_pipeline
        self.queue = device.newCommandQueue()

    def m15_pairs(self, tile: bytes, matrix: tuple[int, int, int, int]) -> bytes:
        metal = self.Metal
        pairs = len(tile) // 2
        if pairs == 0:
            return b""
        shared = metal.MTLResourceStorageModeShared
        in_buffer = self.device.newBufferWithBytes_length_options_(tile, len(tile), shared)
        out_buffer = self.device.newBufferWithLength_options_(len(tile), shared)
        m_buffer = self.device.newBufferWithBytes_length_options_(struct.pack("<4I", *matrix), 16, shared)
        n_buffer = self.device.newBufferWithBytes_length_options_(struct.pack("<I", pairs), 4, shared)
        command = self.queue.commandBuffer()
        encoder = command.computeCommandEncoder()
        encoder.setComputePipelineState_(self.pipeline)
        for index, buffer in enumerate((in_buffer, out_buffer, m_buffer, n_buffer)):
            encoder.setBuffer_offset_atIndex_(buffer, 0, index)
        width = max(1, min(int(self.pipeline.maxTotalThreadsPerThreadgroup()), pairs))
        encoder.dispatchThreads_threadsPerThreadgroup_(
            metal.MTLSizeMake(pairs, 1, 1), metal.MTLSizeMake(width, 1, 1)
        )
        encoder.endEncoding()
        command.commit()
        command.waitUntilCompleted()
        if command.status() != metal.MTLCommandBufferStatusCompleted:
            raise DeviceUnavailableError(f"Metal command buffer did not complete: {command.error()}")
        return bytes(out_buffer.contents().as_buffer(len(tile)))

    def pv_field_scale(self, tile: bytes, index: int) -> bytes:
        from chronus.core.scaling import PVScale
        factor = PVScale(index).field_factor()
        return self._field_dispatch(tile, factor)

    def _field_dispatch(self, tile, factor):
        metal, pairs = self.Metal, len(tile)//4
        if pairs == 0:
            return b''
        shared = metal.MTLResourceStorageModeShared
        buffers = (
            self.device.newBufferWithBytes_length_options_(tile, len(tile), shared),
            self.device.newBufferWithLength_options_(len(tile), shared),
            self.device.newBufferWithBytes_length_options_(struct.pack('<2I',*factor),8,shared),
            self.device.newBufferWithBytes_length_options_(struct.pack('<I',pairs),4,shared),
        )
        if any(buffer is None for buffer in buffers):
            raise DeviceUnavailableError('Metal field buffer allocation failed')
        command = self.queue.commandBuffer()
        encoder = command.computeCommandEncoder()
        encoder.setComputePipelineState_(self.field_pipeline)
        for index, buffer in enumerate(buffers):
            encoder.setBuffer_offset_atIndex_(buffer,0,index)
        width = max(1,min(int(self.field_pipeline.maxTotalThreadsPerThreadgroup()),pairs))
        encoder.dispatchThreads_threadsPerThreadgroup_(metal.MTLSizeMake(pairs,1,1),metal.MTLSizeMake(width,1,1))
        encoder.endEncoding()
        command.commit()
        command.waitUntilCompleted()
        if command.status() != metal.MTLCommandBufferStatusCompleted:
            raise DeviceUnavailableError(f'Metal field dispatch failed: {command.error()}')
        return bytes(buffers[1].contents().as_buffer(len(tile)))


def _detect_mlx() -> tuple[bool, dict[str, Any], str | None, Any]:
    if platform.machine() != "arm64":
        return False, {}, "MLX needs Apple Silicon (arm64)", None
    try:
        import mlx.core as mx
        import numpy as np
    except ImportError as exc:
        return False, {}, f"MLX not importable ({exc})", None
    if not mx.metal.is_available():
        return False, {}, "MLX imported but Metal is not available to it", None
    info: dict[str, Any] = {}
    for getter in (getattr(mx, "device_info", None), getattr(mx.metal, "device_info", None)):
        if getter is None:
            continue
        try:
            info = {k: (v if isinstance(v, (int, str, bool)) else str(v)) for k, v in dict(getter()).items()}
            break
        except Exception:
            continue
    device = {
        "engine": "mlx",
        "mlx_version": getattr(mx, "__version__", None),
        "stream": "gpu",
        "metal_device_info": info,
        "unified_memory": True,
        "machine": platform.machine(),
        "macos": platform.mac_ver()[0],
    }
    return True, device, None, MLXEngine(mx, np)


def _detect_pyobjc() -> tuple[bool, dict[str, Any], str | None, Any]:
    try:
        import Metal
    except ImportError as exc:
        return False, {}, f"PyObjC Metal not importable ({exc})", None
    device = Metal.MTLCreateSystemDefaultDevice()
    if device is None:
        return False, {}, "MTLCreateSystemDefaultDevice returned no device", None
    engine = PyObjCMetalEngine(Metal, device)
    description = {
        "engine": "metal-pyobjc",
        "device_name": str(device.name()),
        "registry_id": int(device.registryID()),
        "unified_memory": bool(device.hasUnifiedMemory()),
        "recommended_max_working_set_bytes": int(device.recommendedMaxWorkingSetSize()),
        "machine": platform.machine(),
        "macos": platform.mac_ver()[0],
    }
    return True, description, None, engine


class MetalAdapter(DeviceAdapter):
    route = ROUTE_METAL
    name = "apple-metal"
    silicon = "gpu"
    mode = MODE_B

    def _detect(self):
        if sys.platform != "darwin":
            return False, {}, "Metal is only available on macOS", None
        choice = os.environ.get(ENGINE_ENV, "auto").strip().lower()
        if choice not in ("auto", "mlx", "pyobjc"):
            return False, {}, f"{ENGINE_ENV} must be auto, mlx or pyobjc", None
        reasons = []
        for name, detect in (("mlx", _detect_mlx), ("pyobjc", _detect_pyobjc)):
            if choice not in ("auto", name):
                continue
            try:
                available, device, reason, engine = detect()
            except Exception as exc:
                reasons.append(f"{name}: {type(exc).__name__}")
                continue
            if available:
                return True, device, None, engine
            reasons.append(reason)
        return False, {}, "; ".join(r for r in reasons if r), None
