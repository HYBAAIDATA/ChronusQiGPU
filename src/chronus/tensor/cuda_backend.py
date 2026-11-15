"""Fail-closed CUDA tensor backend using Chronus-owned CUDA C kernels."""

from __future__ import annotations

import numpy as np


class CUDATensorUnavailable(RuntimeError):
    pass


_CUDA_SOURCE = r"""
extern "C" __global__
void tensor_add(const float* a, const float* b, float* out, unsigned int n) {
    unsigned int i = blockDim.x * blockIdx.x + threadIdx.x;
    if (i < n) out[i] = a[i] + b[i];
}
extern "C" __global__
void tensor_hadamard(const float* a, const float* b, float* out, unsigned int n) {
    unsigned int i = blockDim.x * blockIdx.x + threadIdx.x;
    if (i < n) out[i] = a[i] * b[i];
}
extern "C" __global__
void tensor_scale(const float* a, float* out, float alpha, unsigned int n) {
    unsigned int i = blockDim.x * blockIdx.x + threadIdx.x;
    if (i < n) out[i] = a[i] * alpha;
}
extern "C" __global__
void tensor_matmul(
    const float* a, const float* b, float* out,
    unsigned int m, unsigned int k, unsigned int n) {
    unsigned int row = blockDim.y * blockIdx.y + threadIdx.y;
    unsigned int col = blockDim.x * blockIdx.x + threadIdx.x;
    if (row >= m || col >= n) return;
    float acc = 0.0f;
    for (unsigned int t = 0; t < k; ++t) {
        acc += a[row * k + t] * b[t * n + col];
    }
    out[row * n + col] = acc;
}
extern "C" __global__
void tensor_kron2(
    const float* a, const float* b, float* out,
    unsigned int ar, unsigned int ac, unsigned int br, unsigned int bc) {
    unsigned int row = blockDim.y * blockIdx.y + threadIdx.y;
    unsigned int col = blockDim.x * blockIdx.x + threadIdx.x;
    unsigned int rows = ar * br;
    unsigned int cols = ac * bc;
    if (row >= rows || col >= cols) return;
    unsigned int ai = row / br;
    unsigned int bi = row % br;
    unsigned int aj = col / bc;
    unsigned int bj = col % bc;
    out[row * cols + col] = a[ai * ac + aj] * b[bi * bc + bj];
}
"""


class CUDATensorBackend:
    name = "chronus-cuda-tensor"
    execution_mode = "PHYSICAL_ACCELERATOR"

    def __init__(self, device_id: int = 0) -> None:
        self.device_id = int(device_id)
        self._cp = None
        self._module = None
        self._device = None

    def _initialize(self) -> None:
        if self._module is not None:
            return
        try:
            import cupy as cp
        except Exception as exc:
            raise CUDATensorUnavailable("CuPy unavailable") from exc
        try:
            count = int(cp.cuda.runtime.getDeviceCount())
        except Exception as exc:
            raise CUDATensorUnavailable("CUDA device discovery failed") from exc
        if self.device_id < 0 or self.device_id >= count:
            raise CUDATensorUnavailable(
                f"CUDA device {self.device_id} unavailable; discovered {count}"
            )
        try:
            device = cp.cuda.Device(self.device_id)
            device.use()
            module = cp.RawModule(code=_CUDA_SOURCE, options=("--std=c++11",))
            for name in ("tensor_add", "tensor_hadamard", "tensor_scale", "tensor_matmul", "tensor_kron2"):
                module.get_function(name)
        except Exception as exc:
            raise CUDATensorUnavailable("CUDA tensor kernel build failed") from exc
        self._cp, self._device, self._module = cp, device, module

    def is_available(self) -> bool:
        try:
            self._initialize()
            return True
        except CUDATensorUnavailable:
            return False

    def device_record(self) -> dict:
        self._initialize()
        cp = self._cp
        props = cp.cuda.runtime.getDeviceProperties(self.device_id)
        name = props.get("name", b"cuda-device")
        if isinstance(name, bytes):
            name = name.decode("utf-8", "replace")
        return {
            "backend": self.name,
            "execution_mode": self.execution_mode,
            "device_id": self.device_id,
            "device_name": str(name),
            "runtime_version": int(cp.cuda.runtime.runtimeGetVersion()),
            "driver_version": int(cp.cuda.runtime.driverGetVersion()),
            "measured": False,
        }

    @staticmethod
    def _f32(value: np.ndarray) -> np.ndarray:
        array = np.ascontiguousarray(value, dtype=np.float32)
        if array.size == 0:
            raise ValueError("empty tensors are not supported")
        return array

    def _launch_1d(self, name: str, args: tuple, n: int) -> None:
        block = 256
        grid = ((n + block - 1) // block,)
        self._module.get_function(name)(grid, (block,), args)

    def execute(self, operation: str, *values: np.ndarray, scalar: float | None = None) -> dict:
        self._initialize()
        cp = self._cp
        op = operation.lower()
        arrays = [self._f32(v) for v in values]
        device_arrays = [cp.asarray(v) for v in arrays]

        if op in {"add", "hadamard"}:
            if len(arrays) != 2 or arrays[0].shape != arrays[1].shape:
                raise ValueError(f"{op} requires two identically shaped tensors")
            out = cp.empty_like(device_arrays[0])
            kernel = "tensor_add" if op == "add" else "tensor_hadamard"
            self._launch_1d(kernel, (device_arrays[0], device_arrays[1], out, np.uint32(out.size)), int(out.size))
        elif op == "scale":
            if len(arrays) != 1 or scalar is None:
                raise ValueError("scale requires one tensor and scalar")
            out = cp.empty_like(device_arrays[0])
            self._launch_1d(
                "tensor_scale",
                (device_arrays[0], out, np.float32(scalar), np.uint32(out.size)),
                int(out.size),
            )
        elif op == "matmul":
            if len(arrays) != 2 or arrays[0].ndim != 2 or arrays[1].ndim != 2:
                raise ValueError("matmul requires two rank-2 tensors")
            m, k = arrays[0].shape
            kb, n = arrays[1].shape
            if k != kb:
                raise ValueError("matmul inner dimensions do not agree")
            out = cp.empty((m, n), dtype=cp.float32)
            block = (16, 16)
            grid = ((n + 15) // 16, (m + 15) // 16)
            self._module.get_function("tensor_matmul")(
                grid, block,
                (device_arrays[0], device_arrays[1], out, np.uint32(m), np.uint32(k), np.uint32(n))
            )
        elif op == "kron":
            if len(arrays) != 2 or arrays[0].ndim not in (1, 2) or arrays[1].ndim not in (1, 2):
                raise ValueError("kron supports rank-1 or rank-2 tensors")
            a = device_arrays[0].reshape((arrays[0].shape[0], 1)) if arrays[0].ndim == 1 else device_arrays[0]
            b = device_arrays[1].reshape((arrays[1].shape[0], 1)) if arrays[1].ndim == 1 else device_arrays[1]
            ar, ac = a.shape
            br, bc = b.shape
            out = cp.empty((ar * br, ac * bc), dtype=cp.float32)
            block = (16, 16)
            grid = ((out.shape[1] + 15) // 16, (out.shape[0] + 15) // 16)
            self._module.get_function("tensor_kron2")(
                grid, block,
                (a, b, out, np.uint32(ar), np.uint32(ac), np.uint32(br), np.uint32(bc))
            )
        else:
            raise ValueError(f"unsupported CUDA tensor operation: {operation}")

        cp.cuda.get_current_stream().synchronize()
        return {
            "output": cp.asnumpy(out),
            "backend": self.name,
            "device": self.device_record(),
            "physical_execution": True,
        }
