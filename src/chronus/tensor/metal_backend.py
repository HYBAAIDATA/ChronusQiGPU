"""Fail-closed Apple Metal tensor backend through MLX.

Opt-in client-Apple-Silicon climb-in route only. Requires macOS/ARM plus
MLX with an available Metal device; otherwise raises
``MetalTensorUnavailable``. No physical-device execution is inferred on
other hosts or in Linux CI.
"""

from __future__ import annotations

import platform

import numpy as np


class MetalTensorUnavailable(RuntimeError):
    pass


class MetalTensorBackend:
    name = "chronus-metal-tensor"
    execution_mode = "PHYSICAL_ACCELERATOR"

    def __init__(self) -> None:
        self._mx = None
        self._self_tested = False

    def _initialize(self) -> None:
        if self._mx is not None:
            return
        if platform.system() != "Darwin" or platform.machine().lower() not in {"arm64", "aarch64"}:
            raise MetalTensorUnavailable("Apple Silicon host required")
        try:
            import mlx.core as mx
        except Exception as exc:
            raise MetalTensorUnavailable("MLX unavailable") from exc
        try:
            if not bool(mx.metal.is_available()):
                raise MetalTensorUnavailable("MLX Metal device unavailable")
        except MetalTensorUnavailable:
            raise
        except Exception as exc:
            raise MetalTensorUnavailable("MLX Metal initialization failed") from exc
        self._mx = mx
        try:
            actual = self.execute(
                "add",
                np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32),
                np.array([4.0, 3.0, 2.0, 1.0], dtype=np.float32),
            )["output"]
            if not np.array_equal(actual, np.array([5.0, 5.0, 5.0, 5.0], dtype=np.float32)):
                raise MetalTensorUnavailable("Metal tensor known-answer check failed")
            self._self_tested = True
        except Exception as exc:
            self._mx = None
            if isinstance(exc, MetalTensorUnavailable):
                raise
            raise MetalTensorUnavailable("Metal tensor known-answer check failed") from exc

    def is_available(self) -> bool:
        try:
            self._initialize()
            return True
        except MetalTensorUnavailable:
            return False

    def device_record(self) -> dict:
        self._initialize()
        return {
            "backend": self.name,
            "execution_mode": self.execution_mode,
            "device_name": "Apple Metal via MLX",
            "host_machine": platform.machine(),
            "macos": platform.mac_ver()[0],
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
        mx = self._mx
        op = operation.lower()
        arrays = [self._f32(v) for v in values]
        with mx.stream(mx.gpu):
            values_mx = [mx.array(v) for v in arrays]

        with mx.stream(mx.gpu):
            if op == "add":
                if len(arrays) != 2 or arrays[0].shape != arrays[1].shape:
                    raise ValueError("add requires two identically shaped tensors")
                out = values_mx[0] + values_mx[1]
            elif op == "hadamard":
                if len(arrays) != 2 or arrays[0].shape != arrays[1].shape:
                    raise ValueError("hadamard requires two identically shaped tensors")
                out = values_mx[0] * values_mx[1]
            elif op == "scale":
                if len(arrays) != 1 or scalar is None:
                    raise ValueError("scale requires one tensor and scalar")
                out = values_mx[0] * float(scalar)
            elif op == "matmul":
                if len(arrays) != 2 or arrays[0].ndim != 2 or arrays[1].ndim != 2:
                    raise ValueError("matmul requires two rank-2 tensors")
                if arrays[0].shape[1] != arrays[1].shape[0]:
                    raise ValueError("matmul inner dimensions do not agree")
                out = mx.matmul(values_mx[0], values_mx[1])
            elif op == "kron":
                if len(arrays) != 2 or arrays[0].ndim not in (1, 2) or arrays[1].ndim not in (1, 2):
                    raise ValueError("kron supports rank-1 or rank-2 tensors")
                a = values_mx[0].reshape((arrays[0].shape[0], 1)) if arrays[0].ndim == 1 else values_mx[0]
                b = values_mx[1].reshape((arrays[1].shape[0], 1)) if arrays[1].ndim == 1 else values_mx[1]
                ar, ac = a.shape
                br, bc = b.shape
                out = (a[:, None, :, None] * b[None, :, None, :]).reshape((ar * br, ac * bc))
            else:
                raise ValueError(f"unsupported Metal tensor operation: {operation}")
            mx.eval(out)
        return {
            "output": np.array(out),
            "backend": self.name,
            "device": self.device_record(),
            "physical_execution": True,
        }
