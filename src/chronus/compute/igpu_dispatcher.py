"""Evidence-first Chronus iGPU compute abstraction for the 32x600 H4 basis.

Chronus owns scheduling; TURING owns exact finite Hilbert operators.
Exact tasks execute as mathematical host operations. Optional Metal tasks
execute actual MLX float32 kernels through the maintained, fail-closed
MetalTensorBackend with measured time and independent host parity.
No full 19200x19200 Hamiltonian, false zero-copy claim, or silent fallback.
MLX float32 results are NOT exact quantum evolution.
"""
from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass
from hashlib import sha256
from threading import Lock
from time import perf_counter_ns
from typing import Any, Callable


class ComputeUnavailable(RuntimeError):
    """Selected surface unavailable or request exceeds verified bounds."""


@dataclass(frozen=True)
class ComputeTask:
    task_id: str
    operation: str
    data: dict[str, Any]
    callback: Callable[[dict[str, Any]], None] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.task_id, str) or not 0 < len(self.task_id) <= 128:
            raise ValueError("task_id must be a bounded nonempty string")
        if self.operation not in {
            "exact-dual-laplacian", "exact-involution",
            "metal-dual-laplacian", "metal-matmul",
        }:
            raise ValueError(f"unsupported compute operation: {self.operation}")
        if not isinstance(self.data, dict):
            raise TypeError("task data must be a dictionary")


class iGPUDispatcher:
    """Bounded asynchronous dispatch with explicit execution classifications.

    A worker thread is not proof of GPU execution. The GPU is probed only
    when a Metal task is selected. Failure does not trigger CPU fallback.
    """

    def __init__(self, max_pending: int = 8,
                 max_buffer_bytes: int = 64 * 1024 * 1024) -> None:
        if type(max_pending) is not int or not 1 <= max_pending <= 1024:
            raise ValueError("max_pending outside 1..1024")
        if type(max_buffer_bytes) is not int or max_buffer_bytes < 8192:
            raise ValueError("max_buffer_bytes must be >=8192")
        self.max_pending = max_pending
        self.max_buffer_bytes = max_buffer_bytes
        self._lock = Lock()
        self._executor: concurrent.futures.ThreadPoolExecutor | None = None
        self._pending: dict[str, concurrent.futures.Future] = {}
        self._used_ids: set[str] = set()
        self._stats = {
            "tasks_submitted": 0, "tasks_completed": 0, "tasks_failed": 0,
            "measured_worker_ns": 0, "metal_tasks": 0, "exact_host_tasks": 0,
        }

    def start(self) -> None:
        with self._lock:
            if self._executor is None:
                self._executor = concurrent.futures.ThreadPoolExecutor(
                    max_workers=1, thread_name_prefix="chronus-igpu")

    def stop(self, *, wait: bool = True) -> None:
        with self._lock:
            executor, self._executor = self._executor, None
        if executor is not None:
            executor.shutdown(wait=wait, cancel_futures=not wait)

    def submit(self, task: ComputeTask) -> str:
        with self._lock:
            if self._executor is None:
                raise RuntimeError("start the dispatcher before submitting")
            if task.task_id in self._used_ids:
                raise ValueError("duplicate task id")
            if sum(not f.done() for f in self._pending.values()) >= self.max_pending:
                raise ComputeUnavailable("bounded compute queue is full")
            self._pending[task.task_id] = self._executor.submit(self._execute, task)
            self._used_ids.add(task.task_id)
            self._stats["tasks_submitted"] += 1
        return task.task_id

    def result(self, task_id: str, timeout: float | None = None) -> dict[str, Any]:
        with self._lock:
            try:
                future = self._pending[task_id]
            except KeyError:
                raise KeyError(f"unknown or already consumed task id: {task_id}") from None
        try:
            return future.result(timeout=timeout)
        finally:
            if future.done():
                with self._lock:
                    self._pending.pop(task_id, None)

    def submit_sync(self, task: ComputeTask,
                    timeout: float | None = 60) -> dict[str, Any]:
        return self.result(self.submit(task), timeout)

    def _execute(self, task: ComputeTask) -> dict[str, Any]:
        began = perf_counter_ns()
        try:
            if task.operation == "exact-dual-laplacian":
                output = self._exact_dual_laplacian(task.data)
                classification = "MATHEMATICAL_EXECUTION_HOST"
            elif task.operation == "exact-involution":
                output = self._exact_involution(task.data)
                classification = "MATHEMATICAL_EXECUTION_HOST"
            elif task.operation == "metal-dual-laplacian":
                output = self._metal_dual_laplacian(task.data)
                classification = "METAL_APPROXIMATE_FLOAT32"
            else:
                output = self._metal_matmul(task.data)
                classification = "METAL_APPROXIMATE_FLOAT32"
            record = dict(output)
            record.update({
                "task_id": task.task_id,
                "execution_classification": classification,
                "measured_worker_ns": perf_counter_ns() - began,
                "hardware_attested": False,
            })
            if task.callback is not None:
                task.callback(record)
            with self._lock:
                self._stats["tasks_completed"] += 1
                self._stats["measured_worker_ns"] += record["measured_worker_ns"]
                self._stats["metal_tasks" if classification.startswith("METAL")
                            else "exact_host_tasks"] += 1
            return record
        except Exception:
            with self._lock:
                self._stats["tasks_failed"] += 1
                self._stats["measured_worker_ns"] += perf_counter_ns() - began
            raise

    @staticmethod
    def _dual_neighbors() -> tuple[tuple[int, ...], ...]:
        from chronus.geodesic.dual_120cell import build_dual_120_cell
        neighbors: list[set[int]] = [set() for _ in range(600)]
        for a, b in build_dual_120_cell().edges:
            neighbors[a].add(b)
            neighbors[b].add(a)
        if any(len(v) != 4 for v in neighbors):
            raise AssertionError("dual H4 graph degree is not four")
        return tuple(tuple(sorted(v)) for v in neighbors)

    @classmethod
    def _exact_dual_laplacian(cls, data: dict[str, Any]) -> dict[str, Any]:
        state = data.get("state")
        if (not isinstance(state, (tuple, list)) or len(state) != 32 or any(
                not isinstance(row, (tuple, list)) or len(row) != 600 or
                any(type(x) is not int for x in row) for row in state)):
            raise ValueError("exact dual state requires 32x600 Python integers")
        neighbors = cls._dual_neighbors()
        output = tuple(tuple(
            4 * row[i] - sum(row[j] for j in neighbors[i])
            for i in range(600)) for row in state)
        if any(sum(row) != 0 for row in output):
            raise ArithmeticError("graph Laplacian conservation failed")
        return {"state": output, "basis_dimension": 19200,
                "operator": "I32_TENSOR_L120CELL",
                "arithmetic": "EXACT_UNBOUNDED_INTEGER"}

    @staticmethod
    def _exact_involution(data: dict[str, Any]) -> dict[str, Any]:
        from turing.exact.geometry.hilbert import SignedInvolution, SparseState
        state, operator = data.get("state"), data.get("operator")
        turns = data.get("quarter_turns", 1)
        if (not isinstance(state, SparseState) or
                not isinstance(operator, SignedInvolution) or
                type(turns) is not int):
            raise TypeError("exact involution needs TURING state, operator, turns")
        evolved = operator.quarter_turn(state, turns)
        if evolved.norm2() != state.norm2():
            raise ArithmeticError("exact involution did not conserve norm")
        return {"state": evolved, "basis_dimension": state.space.dimension,
                "operator": "HERMITIAN_INVOLUTION_QUARTER_TURN",
                "arithmetic": "EXACT_GAUSSIAN_RATIONAL"}

    def _metal_matmul(self, data: dict[str, Any]) -> dict[str, Any]:
        import numpy as np
        left, right = data.get("left"), data.get("right")
        if (not isinstance(left, np.ndarray) or
                not isinstance(right, np.ndarray) or
                left.ndim != 2 or right.ndim != 2 or
                left.dtype != np.float32 or right.dtype != np.float32 or
                left.shape[1] != right.shape[0] or not left.size or not right.size):
            raise ValueError("Metal operands must be compatible nonempty float32 matrices")
        size = left.nbytes + right.nbytes + left.shape[0] * right.shape[1] * 4
        if size > self.max_buffer_bytes:
            raise ComputeUnavailable("estimated Metal buffers exceed memory guard")
        if not np.isfinite(left).all() or not np.isfinite(right).all():
            raise ValueError("nonfinite Metal input rejected")
        from chronus.tensor.metal_backend import MetalTensorBackend
        response = MetalTensorBackend().execute("matmul", left, right)
        output = np.asarray(response["output"])
        reference = left @ right
        if output.shape != reference.shape or not np.allclose(
                output, reference, atol=5e-5, rtol=5e-4):
            raise ArithmeticError("independent Metal/host f32 parity failed")
        return {
            "output": output,
            "input_sha256": sha256(left.tobytes() + right.tobytes()).hexdigest(),
            "output_sha256": sha256(output.tobytes()).hexdigest(),
            "device": response["device"],
            "arithmetic": "APPROXIMATE_FLOAT32",
            "host_parity": "PASS_WITH_EXPLICIT_TOLERANCE",
            "zero_copy_verified": False,
        }

    def _metal_dual_laplacian(self, data: dict[str, Any]) -> dict[str, Any]:
        import numpy as np
        state = data.get("state")
        if (not isinstance(state, np.ndarray) or state.shape != (32, 600)
                or state.dtype != np.float32 or not np.isfinite(state).all()):
            raise ValueError("Metal dual state requires finite float32 (32,600)")
        adjacency = self._dual_neighbors()
        matrix = np.zeros((600, 600), dtype=np.float32)
        for i, neighbors in enumerate(adjacency):
            matrix[i, i] = 4
            for j in neighbors:
                matrix[i, j] = -1
        result = self._metal_matmul({"left": matrix, "right": state.T.copy()})
        result["state"] = result.pop("output").T.copy()
        result["basis_dimension"] = 19200
        result["operator"] = "I32_TENSOR_L120CELL"
        return result

    def get_stats(self) -> dict[str, int]:
        with self._lock:
            return dict(self._stats)

    def memory_usage(self) -> dict[str, object]:
        return {
            "resident_device_bytes": "UNAVAILABLE",
            "zero_copy_verified": False,
            "host_input_buffer_estimates_only": True,
        }
