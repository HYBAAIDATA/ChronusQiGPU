"""Canonical MLA1517 execution boundary.

All exact quantum workloads enter through this module.  The CPU exact backend
is an auditable reference path; a hardware backend must advertise an exact
arithmetic kernel and is rejected when absent.  There is no silent fallback
from a requested hardware backend to approximation or simulation.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Iterable
from .quantum import ExactStateVector, ExactResourceError
from .scaling import _select_device as _select_opencl_device


class AcceleratorUnavailable(RuntimeError):
    """Requested accelerator is not present or lacks an exact kernel."""


@dataclass(frozen=True)
class ExecutionReceipt:
    backend: str
    exact: bool
    amplitudes: int
    transformations: int


class CanonicalAccelerator:
    """Single-pane execution API for exact state-vector workloads."""

    def __init__(self, backend: str = "exact_cpu_reference") -> None:
        if backend not in {"exact_cpu_reference", "mla1517_igpu"}:
            raise ValueError("unsupported canonical backend")
        self.backend = backend
        if backend == "mla1517_igpu":
            raise AcceleratorUnavailable(
                "MLA1517 exact-arithmetic quantum kernel is not installed; refusing approximation or CPU fallback"
            )

    def execute(
        self,
        state: ExactStateVector,
        operations: Iterable[Callable[[ExactStateVector], ExactStateVector]],
    ) -> tuple[ExactStateVector, ExecutionReceipt]:
        current = state
        count = 0
        for operation in operations:
            candidate = operation(current)
            if (
                not isinstance(candidate, ExactStateVector)
                or candidate.num_qubits != current.num_qubits
                or not candidate.normalized_exact()
            ):
                raise ValueError("operation violated exact normalized state contract")
            current = candidate
            count += 1
        return current, ExecutionReceipt(self.backend, True, len(current.amplitudes), count)


class ExactOpenCLAccelerator:
    """Exact long4 OpenCL backend; no CPU fallback and checked overflow."""

    def __init__(self, kernel_path: str | None = None):
        try:
            import pyopencl as cl
        except ImportError as exc:
            raise AcceleratorUnavailable("pyopencl is not installed") from exc
        self.cl = cl
        platforms = cl.get_platforms()
        devices = [d for p in platforms for d in p.get_devices()]
        if not devices:
            raise AcceleratorUnavailable("no OpenCL device discovered")
        try:
            device = _select_opencl_device(cl, devices)
        except RuntimeError as exc:
            raise AcceleratorUnavailable(str(exc)) from exc
        self.context = cl.Context(devices=[device])
        self.queue = cl.CommandQueue(self.context)
        source_path = kernel_path or str(
            __import__("pathlib").Path(__file__).parents[2] / "kernels/exact_quantum_kernel.cl"
        )
        self.program = cl.Program(self.context, open(source_path).read()).build()

    def apply_hadamard_ladder(
        self, state_buffer, target: int, rung: int, denominator_pow2: int = 0
    ) -> int:
        import numpy as np
        from .scaling import LUCAS_PISOT_LADDER

        if rung not in LUCAS_PISOT_LADDER:
            raise ValueError("strict scale violation")
        if rung >= 63:
            raise ExactResourceError("state-vector dimension cannot be represented safely")
        dimension = 1 << rung
        if target < 0 or target >= rung:
            raise ValueError("target qubit out of range")
        if int(state_buffer.size) < dimension * 32:
            raise ExactResourceError("device buffer is smaller than exact state vector")
        overflow = self.cl.Buffer(
            self.context,
            self.cl.mem_flags.READ_WRITE | self.cl.mem_flags.COPY_HOST_PTR,
            hostbuf=np.zeros(1, dtype=np.uint32),
        )
        self.program.exact_hadamard_lucas_pisot_scale(
            self.queue,
            (dimension,),
            None,
            state_buffer,
            np.uint32(target),
            np.uint64(dimension),
            overflow,
        )
        self.queue.finish()
        flag = np.zeros(1, dtype=np.uint32)
        self.cl.enqueue_copy(self.queue, flag, overflow).wait()
        if int(flag[0]):
            raise ExactResourceError("exact long4 coefficient overflow on device")
        return denominator_pow2 + 1
