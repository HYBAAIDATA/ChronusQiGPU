"""Native vendor tensor execution for Chronus.

OpenCL is one Chronus execution substrate, not the Chronus architecture.
This module provides independent local tensor execution paths for:

* CUDA, using CuPy only as the Python binding to the CUDA runtime while the
  arithmetic kernels themselves are Chronus-owned CUDA C kernels.
* Metal, using MLX as the Apple GPU execution binding.

Both paths are optional, lazy, and fail closed. Neither falls back to OpenCL
or CPU internally. Existing OpenCL execution remains independent and unchanged.
"""
from __future__ import annotations

import platform
from dataclasses import dataclass
from threading import Lock
from typing import Any, Sequence

import numpy as np


_OPERATIONS = ("matmul", "add", "scale", "kron", "hadamard")
_DTYPES = ("float32",)


class ChronusNativeTensorUnavailable(RuntimeError):
    """Raised when a requested native vendor runtime cannot execute."""


class ChronusNativeTensorValidationError(ValueError):
    """Raised when input data disagrees with the declared tensor contract."""


@dataclass(frozen=True)
class NativeTensorProbe:
    """Observed availability of one native Chronus tensor execution path."""

    backend: str
    available: bool
    device_id: str
    device_name: str
    platform_name: str
    reason: str
    operations: tuple[str, ...] = _OPERATIONS
    dtypes: tuple[str, ...] = _DTYPES

    def as_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "available": self.available,
            "device_id": self.device_id,
            "device_name": self.device_name,
            "platform_name": self.platform_name,
            "reason": self.reason,
            "operations": self.operations,
            "dtypes": self.dtypes,
            "opencl_required": False,
        }


def _load_cupy():
    import cupy as cp

    return cp


def _load_mlx():
    import mlx.core as mx

    return mx


def _cupy_property(props: dict[Any, Any], name: str, default: Any = None) -> Any:
    """Read a CuPy device property across byte-key/string-key versions."""
    if name in props:
        return props[name]
    encoded = name.encode("utf-8")
    if encoded in props:
        return props[encoded]
    return default


def _decode_device_name(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").rstrip("\x00")
    return str(value or "unknown").strip()


def _best_cuda_device(cp) -> tuple[int, dict[Any, Any]]:
    try:
        count = int(cp.cuda.runtime.getDeviceCount())
    except Exception as exc:
        raise ChronusNativeTensorUnavailable(
            f"CUDA enumeration failed: {type(exc).__name__}: {exc}"
        ) from exc
    if count <= 0:
        raise ChronusNativeTensorUnavailable("no CUDA GPU device found")

    candidates: list[tuple[tuple[int, int], int, dict[Any, Any]]] = []
    for index in range(count):
        try:
            props = dict(cp.cuda.runtime.getDeviceProperties(index))
        except Exception:
            props = {}
        multiprocessors = int(_cupy_property(props, "multiProcessorCount", 0) or 0)
        memory = int(_cupy_property(props, "totalGlobalMem", 0) or 0)
        candidates.append(((multiprocessors, memory), index, props))
    _, index, props = max(candidates, key=lambda item: item[0])
    return index, props


def probe_cuda() -> NativeTensorProbe:
    """Report CUDA only after a real CUDA device is enumerated."""
    try:
        cp = _load_cupy()
        index, props = _best_cuda_device(cp)
        name = _decode_device_name(_cupy_property(props, "name", f"cuda:{index}"))
        driver = int(cp.cuda.runtime.driverGetVersion())
        runtime = int(cp.cuda.runtime.runtimeGetVersion())
    except Exception as exc:
        return NativeTensorProbe(
            backend="cuda",
            available=False,
            device_id="unavailable",
            device_name="",
            platform_name="CUDA",
            reason=f"{type(exc).__name__}: {exc}",
        )
    return NativeTensorProbe(
        backend="cuda",
        available=True,
        device_id=f"cuda:{index}:{name}",
        device_name=name,
        platform_name=f"CUDA driver={driver} runtime={runtime}",
        reason="",
    )


def _mlx_gpu_is_selected(mx) -> bool:
    try:
        return "gpu" in str(mx.default_device()).lower()
    except Exception:
        return False


def probe_metal() -> NativeTensorProbe:
    """Report Metal only after MLX executes a real Apple GPU operation."""
    if platform.system() != "Darwin":
        return NativeTensorProbe(
            backend="metal",
            available=False,
            device_id="unavailable",
            device_name="",
            platform_name="Metal",
            reason="Metal native tensor execution requires Darwin",
        )
    try:
        mx = _load_mlx()
        if not _mlx_gpu_is_selected(mx):
            raise ChronusNativeTensorUnavailable(
                "MLX is importable but its active device is not a GPU"
            )
        value = mx.array([1.0], dtype=mx.float32)
        result = value + value
        mx.eval(result)
        device = str(mx.default_device())
    except Exception as exc:
        return NativeTensorProbe(
            backend="metal",
            available=False,
            device_id="unavailable",
            device_name="",
            platform_name="Metal/MLX",
            reason=f"{type(exc).__name__}: {exc}",
        )
    machine = platform.machine() or "unknown"
    return NativeTensorProbe(
        backend="metal",
        available=True,
        device_id=f"metal:{machine}:{device}",
        device_name=f"Apple {machine}",
        platform_name="Metal/MLX",
        reason="",
    )


def _float32_array(value: Any, shape: Sequence[int]) -> np.ndarray:
    array = np.asarray(value, dtype=np.float32, order="C")
    declared = tuple(int(v) for v in shape)
    if tuple(array.shape) != declared:
        raise ChronusNativeTensorValidationError(
            f"input shape {array.shape} does not match declared shape {declared}"
        )
    return np.ascontiguousarray(array)


def _validate_common(
    operation: str,
    arrays: Sequence[np.ndarray],
    output_shape: Sequence[int],
) -> None:
    out = tuple(int(v) for v in output_shape)
    if operation in {"add", "hadamard"}:
        if len(arrays) != 2 or arrays[0].shape != arrays[1].shape:
            raise ChronusNativeTensorValidationError(
                f"{operation} requires two equal shapes"
            )
        if out != arrays[0].shape:
            raise ChronusNativeTensorValidationError(
                f"{operation} output shape disagrees with inputs"
            )
        return
    if operation == "scale":
        if len(arrays) != 2 or arrays[1].size != 1:
            raise ChronusNativeTensorValidationError(
                "scale requires a tensor and one scalar"
            )
        if out != arrays[0].shape:
            raise ChronusNativeTensorValidationError("scale output shape disagrees")
        return
    if operation == "matmul":
        if len(arrays) != 2 or arrays[0].ndim != 2 or arrays[1].ndim != 2:
            raise ChronusNativeTensorValidationError("matmul requires two rank-2 inputs")
        m, k = arrays[0].shape
        k2, n = arrays[1].shape
        if k != k2 or out != (m, n):
            raise ChronusNativeTensorValidationError(
                "matmul dimensions/output shape disagree"
            )
        return
    if operation == "kron":
        if len(arrays) != 2 or arrays[0].ndim != arrays[1].ndim:
            raise ChronusNativeTensorValidationError("kron requires equal-rank inputs")
        if arrays[0].ndim == 1:
            expected = (arrays[0].size * arrays[1].size,)
        elif arrays[0].ndim == 2:
            expected = (
                arrays[0].shape[0] * arrays[1].shape[0],
                arrays[0].shape[1] * arrays[1].shape[1],
            )
        else:
            raise ChronusNativeTensorValidationError(
                "Chronus kron supports rank 1 or 2"
            )
        if out != expected:
            raise ChronusNativeTensorValidationError("kron output shape disagrees")
        return
    raise ChronusNativeTensorValidationError(f"unsupported operation {operation!r}")


_CUDA_SOURCE = r"""
extern "C" __global__ void tensor_add_f32(
    const float* a, const float* b, float* out, unsigned int count) {
    unsigned int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < count) out[i] = a[i] + b[i];
}
extern "C" __global__ void tensor_hadamard_f32(
    const float* a, const float* b, float* out, unsigned int count) {
    unsigned int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < count) out[i] = a[i] * b[i];
}
extern "C" __global__ void tensor_scale_f32(
    const float* a, const float* scalar, float* out, unsigned int count) {
    unsigned int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < count) out[i] = a[i] * scalar[0];
}
extern "C" __global__ void tensor_matmul_f32(
    const float* a, const float* b, float* out,
    unsigned int m, unsigned int k, unsigned int n) {
    unsigned int i = blockIdx.x * blockDim.x + threadIdx.x;
    unsigned int count = m * n;
    if (i >= count) return;
    unsigned int row = i / n;
    unsigned int col = i % n;
    float acc = 0.0f;
    for (unsigned int p = 0; p < k; ++p) {
        acc += a[row * k + p] * b[p * n + col];
    }
    out[i] = acc;
}
extern "C" __global__ void tensor_kron_1d_f32(
    const float* a, const float* b, float* out,
    unsigned int an, unsigned int bn) {
    unsigned int i = blockIdx.x * blockDim.x + threadIdx.x;
    unsigned int count = an * bn;
    if (i < count) out[i] = a[i / bn] * b[i % bn];
}
extern "C" __global__ void tensor_kron_2d_f32(
    const float* a, const float* b, float* out,
    unsigned int ar, unsigned int ac, unsigned int br, unsigned int bc) {
    unsigned int rows = ar * br;
    unsigned int cols = ac * bc;
    unsigned int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= rows * cols) return;
    unsigned int row = i / cols;
    unsigned int col = i % cols;
    unsigned int arow = row / br;
    unsigned int brow = row % br;
    unsigned int acol = col / bc;
    unsigned int bcol = col % bc;
    out[i] = a[arow * ac + acol] * b[brow * bc + bcol];
}
"""


class ChronusCudaTensorRuntime:
    """Chronus-owned CUDA C tensor kernels launched on a physical CUDA GPU."""

    _KERNEL_NAMES = (
        "tensor_add_f32",
        "tensor_hadamard_f32",
        "tensor_scale_f32",
        "tensor_matmul_f32",
        "tensor_kron_1d_f32",
        "tensor_kron_2d_f32",
    )

    def __init__(self) -> None:
        try:
            cp = _load_cupy()
            index, props = _best_cuda_device(cp)
            device = cp.cuda.Device(index)
            device.use()
            kernels = {
                name: cp.RawKernel(_CUDA_SOURCE, name, options=("--std=c++11",))
                for name in self._KERNEL_NAMES
            }
        except Exception as exc:
            raise ChronusNativeTensorUnavailable(
                f"CUDA tensor runtime unavailable: {type(exc).__name__}: {exc}"
            ) from exc
        self.cp = cp
        self.device = device
        self.kernels = kernels
        self.device_name = _decode_device_name(
            _cupy_property(props, "name", f"cuda:{index}")
        )
        self.device_id = f"cuda:{index}:{self.device_name}"

    def _launch(self, name: str, count: int, args: tuple[Any, ...]) -> None:
        threads = 256
        blocks = (int(count) + threads - 1) // threads
        self.kernels[name]((blocks,), (threads,), args)

    def execute(
        self,
        operation: str,
        inputs: Sequence[Any],
        input_shapes: Sequence[Sequence[int]],
        output_shape: Sequence[int],
    ) -> np.ndarray:
        if len(inputs) != len(input_shapes):
            raise ChronusNativeTensorValidationError(
                "input count does not match declared shapes"
            )
        arrays = [_float32_array(v, s) for v, s in zip(inputs, input_shapes)]
        _validate_common(operation, arrays, output_shape)

        cp = self.cp
        with self.device:
            gpu = [cp.asarray(array) for array in arrays]
            out_size = int(np.prod(tuple(output_shape), dtype=np.int64))
            out = cp.empty(out_size, dtype=cp.float32)
            u32 = np.uint32
            if operation in {"add", "hadamard"}:
                self._launch(
                    f"tensor_{operation}_f32",
                    out_size,
                    (gpu[0], gpu[1], out, u32(out_size)),
                )
            elif operation == "scale":
                self._launch(
                    "tensor_scale_f32",
                    out_size,
                    (gpu[0], gpu[1], out, u32(out_size)),
                )
            elif operation == "matmul":
                m, k = arrays[0].shape
                _, n = arrays[1].shape
                self._launch(
                    "tensor_matmul_f32",
                    out_size,
                    (gpu[0], gpu[1], out, u32(m), u32(k), u32(n)),
                )
            elif operation == "kron" and arrays[0].ndim == 1:
                an = arrays[0].size
                bn = arrays[1].size
                self._launch(
                    "tensor_kron_1d_f32",
                    out_size,
                    (gpu[0], gpu[1], out, u32(an), u32(bn)),
                )
            elif operation == "kron":
                ar, ac = arrays[0].shape
                br, bc = arrays[1].shape
                self._launch(
                    "tensor_kron_2d_f32",
                    out_size,
                    (gpu[0], gpu[1], out, u32(ar), u32(ac), u32(br), u32(bc)),
                )
            cp.cuda.get_current_stream().synchronize()
            return cp.asnumpy(out).reshape(tuple(int(v) for v in output_shape))


class ChronusMetalTensorRuntime:
    """Native Apple GPU tensor execution through MLX/Metal."""

    def __init__(self) -> None:
        probe = probe_metal()
        if not probe.available:
            raise ChronusNativeTensorUnavailable(probe.reason)
        self.mx = _load_mlx()
        self.device_id = probe.device_id
        self.device_name = probe.device_name

    def execute(
        self,
        operation: str,
        inputs: Sequence[Any],
        input_shapes: Sequence[Sequence[int]],
        output_shape: Sequence[int],
    ) -> np.ndarray:
        if len(inputs) != len(input_shapes):
            raise ChronusNativeTensorValidationError(
                "input count does not match declared shapes"
            )
        arrays = [_float32_array(v, s) for v, s in zip(inputs, input_shapes)]
        _validate_common(operation, arrays, output_shape)
        mx = self.mx
        values = [mx.array(array, dtype=mx.float32) for array in arrays]
        if operation == "add":
            result = values[0] + values[1]
        elif operation == "hadamard":
            result = values[0] * values[1]
        elif operation == "scale":
            result = values[0] * values[1].reshape(())
        elif operation == "matmul":
            result = mx.matmul(values[0], values[1])
        elif arrays[0].ndim == 1:
            result = (
                values[0].reshape((-1, 1)) * values[1].reshape((1, -1))
            ).reshape(tuple(int(v) for v in output_shape))
        else:
            ar, ac = arrays[0].shape
            br, bc = arrays[1].shape
            result = (
                values[0].reshape((ar, 1, ac, 1))
                * values[1].reshape((1, br, 1, bc))
            ).reshape(tuple(int(v) for v in output_shape))
        mx.eval(result)
        return np.asarray(result, dtype=np.float32).reshape(
            tuple(int(v) for v in output_shape)
        )


_CUDA_RUNTIME: ChronusCudaTensorRuntime | None = None
_METAL_RUNTIME: ChronusMetalTensorRuntime | None = None
_CUDA_LOCK = Lock()
_METAL_LOCK = Lock()


def get_cuda_runtime() -> ChronusCudaTensorRuntime:
    global _CUDA_RUNTIME
    if _CUDA_RUNTIME is None:
        with _CUDA_LOCK:
            if _CUDA_RUNTIME is None:
                _CUDA_RUNTIME = ChronusCudaTensorRuntime()
    return _CUDA_RUNTIME


def get_metal_runtime() -> ChronusMetalTensorRuntime:
    global _METAL_RUNTIME
    if _METAL_RUNTIME is None:
        with _METAL_LOCK:
            if _METAL_RUNTIME is None:
                _METAL_RUNTIME = ChronusMetalTensorRuntime()
    return _METAL_RUNTIME


__all__ = [
    "ChronusCudaTensorRuntime",
    "ChronusMetalTensorRuntime",
    "ChronusNativeTensorUnavailable",
    "ChronusNativeTensorValidationError",
    "NativeTensorProbe",
    "get_cuda_runtime",
    "get_metal_runtime",
    "probe_cuda",
    "probe_metal",
]
