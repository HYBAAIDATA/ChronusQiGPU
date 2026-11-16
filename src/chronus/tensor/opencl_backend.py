"""Fail-closed OpenCL tensor backend.

Only OpenCL-reported GPU devices are eligible. There is no implicit CPU
OpenCL route and no internal reference fallback.
"""

from __future__ import annotations

from importlib.resources import files
import os

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
        # Default remains an OpenCL GPU, never an inferred integrated GPU.
        # Operators may bind by explicit identity; no silently substituted GPU.
        requested = os.getenv("CHRONUS_OPENCL_DEVICE_MATCH", "").strip().lower()
        if requested:
            matching = [d for d in devices if requested in (
                str(d.name) + " " + str(d.vendor) + " " + str(d.driver_version)
            ).lower()]
            if len(matching) != 1:
                raise OpenCLTensorUnavailable(
                    "requested OpenCL device identity did not resolve uniquely"
                )
            device = matching[0]
        else:
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
            # Every exposed kernel must pass actual on-device known answers,
            # including non-square matmul and a rectangular Kronecker output.
            # Small integers remain exactly representable in binary32.
            a = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
            b = np.array([[5.0, 6.0], [7.0, 8.0]], dtype=np.float32)
            m = np.array([[1.0, 2.0, 3.0],
                          [4.0, 5.0, 6.0]], dtype=np.float32)
            n = np.array([[1.0, 2.0],
                          [3.0, 4.0],
                          [5.0, 6.0]], dtype=np.float32)
            cases = [
                ("add", (a, b), None, a + b),
                ("hadamard", (a, b), None, a * b),
                ("scale", (a,), 2.0, a * np.float32(2.0)),
                ("matmul", (m, n), None, m @ n),
                ("kron", (m, a), None, np.kron(m, a)),
            ]
            for op, operands, factor, expected in cases:
                actual = self.execute(op, *operands, scalar=factor)["output"]
                if not np.array_equal(actual, expected):
                    raise OpenCLTensorUnavailable(
                        f"OpenCL {op} kernel known-answer check failed"
                    )
            self._self_tested = True
        except Exception as exc:
            self._self_tested = False
            self._program = None
            self._queue = None
            self._context = None
            self._device = None
            if isinstance(exc, OpenCLTensorUnavailable):
                raise
            raise OpenCLTensorUnavailable(
                "OpenCL tensor all-operation known-answer check failed"
            ) from exc

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
            "device_identity_policy": (
                "operator_selected" if os.getenv("CHRONUS_OPENCL_DEVICE_MATCH")
                else "first_discovered_opencl_gpu"
            ),
            "integrated_gpu_verified": False,
            "self_tested_operations": (
                ["add", "hadamard", "scale", "matmul", "kron"]
                if self._self_tested else []
            ),
            "vendor": str(self._device.vendor),
            "driver_version": str(self._device.driver_version),
            "measured": False,
            "known_answer_self_test": "PASS" if self._self_tested else "NOT_RUN",
        }

    @staticmethod
    def _f32(value: np.ndarray) -> np.ndarray:
        array = np.asarray(value)
        if array.dtype != np.dtype("float32"):
            raise ValueError(
                "OpenCL tensor kernel requires native float32 input; "
                "no implicit complex/fp64 narrowing"
            )
        if array.size == 0 or array.size > np.iinfo(np.uint32).max:
            raise ValueError("tensor element count outside uint32 kernel policy")
        if not np.all(np.isfinite(array)):
            raise ValueError("OpenCL tensor inputs must be finite")
        return np.ascontiguousarray(array)

    def execute(self, operation: str, *values: np.ndarray, scalar: float | None = None) -> dict:
        self._initialize()
        cl = self._cl
        op = operation.lower()
        arrays = [self._f32(v) for v in values]
        mf = cl.mem_flags
        if not arrays:
            raise ValueError("at least one source tensor required")
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
            if (isinstance(scalar, (str, bytes, bool))
                    or np.iscomplexobj(scalar) or not np.isscalar(scalar)):
                raise ValueError("float32 scale scalar must be real, finite and numeric")
            try:
                converted_scalar = np.float32(scalar)
            except (ValueError, TypeError, OverflowError) as exc:
                raise ValueError("float32 scale scalar outside numerical policy") from exc
            if (not np.isfinite(converted_scalar) or not np.isfinite(scalar)
                    or float(converted_scalar) != float(scalar)):
                raise ValueError("scale scalar would lose precision in float32")
            out = np.empty_like(arrays[0])
            out_buf = cl.Buffer(self._context, mf.WRITE_ONLY, out.nbytes)
            self._program.tensor_scale(
                self._queue, (out.size,), None, buffers[0], out_buf,
                converted_scalar, np.uint32(out.size)
            )
        elif op == "matmul":
            if len(arrays) != 2 or arrays[0].ndim != 2 or arrays[1].ndim != 2:
                raise ValueError("matmul requires two rank-2 tensors")
            m, k = arrays[0].shape
            kb, n = arrays[1].shape
            if k != kb:
                raise ValueError("matmul inner dimensions do not agree")
            if m * n > 16_777_216:
                raise ValueError("matmul output exceeds bounded 64 MiB policy")
            out = np.empty((m, n), dtype=np.float32)
            out_buf = cl.Buffer(self._context, mf.WRITE_ONLY, out.nbytes)
            self._program.tensor_matmul(
                self._queue, (n, m), None, buffers[0], buffers[1], out_buf,
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
            if ar * br * ac * bc > 16_777_216:
                raise ValueError("Kronecker output exceeds bounded 64 MiB policy")
            out = np.empty((ar * br, ac * bc), dtype=np.float32)
            out_buf = cl.Buffer(self._context, mf.WRITE_ONLY, out.nbytes)
            self._program.tensor_kron2(
                self._queue, (out.shape[1], out.shape[0]), None,
                abuf, bbuf, out_buf,
                np.uint32(ar), np.uint32(ac), np.uint32(br), np.uint32(bc)
            )
        else:
            raise ValueError(f"unsupported OpenCL tensor operation: {operation}")

        cl.enqueue_copy(self._queue, out, out_buf).wait()
        self._queue.finish()
        if not np.all(np.isfinite(out)):
            raise OpenCLTensorUnavailable(
                f"OpenCL tensor {op} returned non-finite numerical output"
            )
        # Verify the complete produced result, not just an unrelated startup
        # test. Host reference checks are deliberately included in the call
        # boundary and must not be reported as accelerator-only throughput.
        if op == "matmul":
            from chronus.tensor.geodesic import TopologicalIntegrityGate
            verdict = TopologicalIntegrityGate().verify_float32_matmul(
                out, arrays[0], arrays[1]
            )
            verified = bool(verdict.passed)
            method = "higham_componentwise_gamma_k"
        else:
            if op == "add":
                reference = arrays[0] + arrays[1]
            elif op == "hadamard":
                reference = arrays[0] * arrays[1]
            elif op == "scale":
                reference = arrays[0] * np.float32(scalar)
            else:
                reference = np.kron(a, b)
            verified = bool(np.array_equal(out, reference))
            method = "float32_same_operation_reference_exact"
        if not verified:
            raise OpenCLTensorUnavailable(
                f"OpenCL tensor {op} result failed host numerical integrity"
            )
        return {
            "output": out,
            "backend": self.name,
            "device": self.device_record(),
            "physical_execution": True,
            "output_integrity_verified": True,
            "verification_method": method,
            "performance_measurement": "UNAVAILABLE_HOST_REFERENCE_INCLUDED",
        }
