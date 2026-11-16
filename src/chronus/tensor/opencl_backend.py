"""Fail-closed OpenCL tensor backend.

Only OpenCL-reported GPU devices are eligible. There is no implicit CPU
OpenCL route and no internal reference fallback.
"""

from __future__ import annotations

from importlib.resources import files

import numpy as np


class OpenCLTensorUnavailable(RuntimeError):
    pass


class OpenCLTensorBackend:
    name = "chronus-opencl-tensor"
    execution_mode = "PHYSICAL_ACCELERATOR"

    def __init__(self) -> None:
        self._cl = None
        self._context = None
        self._queue = None
        self._program = None
        self._device = None
        self._self_tested = False

    def _initialize(self) -> None:
        if self._program is not None:
            return
        try:
            import pyopencl as cl
        except Exception as exc:
            raise OpenCLTensorUnavailable("pyopencl unavailable") from exc
        devices = []
        try:
            for platform in cl.get_platforms():
                devices.extend(
                    d for d in platform.get_devices()
                    if int(d.type) & int(cl.device_type.GPU)
                )
        except Exception as exc:
            raise OpenCLTensorUnavailable("OpenCL GPU discovery failed") from exc
        if not devices:
            raise OpenCLTensorUnavailable("no OpenCL GPU device available")
        device = devices[0]
        context = cl.Context([device])
        queue = cl.CommandQueue(context, device=device)
        source = files("chronus.kernels").joinpath("tensor_ops.cl").read_text(encoding="utf-8")
        try:
            program = cl.Program(context, source).build()
        except Exception as exc:
            raise OpenCLTensorUnavailable("OpenCL tensor kernel build failed") from exc
        self._cl, self._context, self._queue, self._program, self._device = (
            cl, context, queue, program, device
        )
        try:
            actual = self.execute(
                "add",
                np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32),
                np.array([4.0, 3.0, 2.0, 1.0], dtype=np.float32),
            )["output"]
            if not np.array_equal(actual, np.array([5.0, 5.0, 5.0, 5.0], dtype=np.float32)):
                raise OpenCLTensorUnavailable("OpenCL tensor known-answer check failed")
            self._self_tested = True
        except Exception as exc:
            self._program = None
            self._queue = None
            self._context = None
            self._device = None
            if isinstance(exc, OpenCLTensorUnavailable):
                raise
            raise OpenCLTensorUnavailable("OpenCL tensor known-answer check failed") from exc

    def is_available(self) -> bool:
        try:
            self._initialize()
            return True
        except OpenCLTensorUnavailable:
            return False

    def device_record(self) -> dict:
        self._initialize()
        return {
            "backend": self.name,
            "execution_mode": self.execution_mode,
            "device_name": str(self._device.name),
            "vendor": str(self._device.vendor),
            "driver_version": str(self._device.driver_version),
            "measured": False,
            "known_answer_self_test": "PASS" if self._self_tested else "NOT_RUN",
        }

    @staticmethod
    def _f32(value: np.ndarray) -> np.ndarray:
        array = np.ascontiguousarray(value, dtype=np.float32)
        if array.size == 0:
            raise ValueError("empty tensors are not supported")
        return array

    def execute(self, operation: str, *values: np.ndarray, scalar: float | None = None) -> dict:
        self._initialize()
        cl = self._cl
        op = operation.lower()
        arrays = [self._f32(v) for v in values]
        mf = cl.mem_flags
        buffers = [
            cl.Buffer(self._context, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=a)
            for a in arrays
        ]

        if op in {"add", "hadamard"}:
            if len(arrays) != 2 or arrays[0].shape != arrays[1].shape:
                raise ValueError(f"{op} requires two identically shaped tensors")
            out = np.empty_like(arrays[0])
            out_buf = cl.Buffer(self._context, mf.WRITE_ONLY, out.nbytes)
            kernel = self._program.tensor_add if op == "add" else self._program.tensor_hadamard
            kernel(self._queue, (out.size,), None, buffers[0], buffers[1], out_buf, np.uint32(out.size))
        elif op == "scale":
            if len(arrays) != 1 or scalar is None:
                raise ValueError("scale requires one tensor and scalar")
            out = np.empty_like(arrays[0])
            out_buf = cl.Buffer(self._context, mf.WRITE_ONLY, out.nbytes)
            self._program.tensor_scale(
                self._queue, (out.size,), None, buffers[0], out_buf,
                np.float32(scalar), np.uint32(out.size)
            )
        elif op == "matmul":
            if len(arrays) != 2 or arrays[0].ndim != 2 or arrays[1].ndim != 2:
                raise ValueError("matmul requires two rank-2 tensors")
            m, k = arrays[0].shape
            kb, n = arrays[1].shape
            if k != kb:
                raise ValueError("matmul inner dimensions do not agree")
            out = np.empty((m, n), dtype=np.float32)
            out_buf = cl.Buffer(self._context, mf.WRITE_ONLY, out.nbytes)
            self._program.tensor_matmul(
                self._queue, (m, n), None, buffers[0], buffers[1], out_buf,
                np.uint32(m), np.uint32(k), np.uint32(n)
            )
        elif op == "kron":
            if len(arrays) != 2 or arrays[0].ndim not in (1, 2) or arrays[1].ndim not in (1, 2):
                raise ValueError("kron supports rank-1 or rank-2 tensors")
            a = arrays[0].reshape((arrays[0].shape[0], 1)) if arrays[0].ndim == 1 else arrays[0]
            b = arrays[1].reshape((arrays[1].shape[0], 1)) if arrays[1].ndim == 1 else arrays[1]
            # Recreate buffers for reshaped contiguous views.
            a, b = np.ascontiguousarray(a), np.ascontiguousarray(b)
            abuf = cl.Buffer(self._context, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=a)
            bbuf = cl.Buffer(self._context, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=b)
            ar, ac = a.shape
            br, bc = b.shape
            out = np.empty((ar * br, ac * bc), dtype=np.float32)
            out_buf = cl.Buffer(self._context, mf.WRITE_ONLY, out.nbytes)
            self._program.tensor_kron2(
                self._queue, out.shape, None, abuf, bbuf, out_buf,
                np.uint32(ar), np.uint32(ac), np.uint32(br), np.uint32(bc)
            )
        else:
            raise ValueError(f"unsupported OpenCL tensor operation: {operation}")

        cl.enqueue_copy(self._queue, out, out_buf).wait()
        self._queue.finish()
        return {
            "output": out,
            "backend": self.name,
            "device": self.device_record(),
            "physical_execution": True,
        }
