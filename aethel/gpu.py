"""ChronusContext — compute context with hardened Cassini checks.

Wraps the compute-unit pool, SPMD executor and micro-kernel library, and
projects data tensors onto pv-lattice anchors.  When a punch host is bound
and reports ``use_opencl``, manifold projection dispatches punch 0x15 to
the device; otherwise the identical NumPy computation runs on the CPU.
"""

from __future__ import annotations

import numpy as np

from .cassini import CassiniVerifier
from .compute import ComputeUnitPool, MicroKernelLibrary, SPMDExecutor
from .constants import DIM, PHI
from .punch import resolve_punch_host
from .zeckendorf import PUNCH_MANIFOLD_COMPUTE


class ChronusContext:
    def __init__(
        self,
        punch_host=None,
        require_gpu: bool = False,
        allow_cpu_fallback: bool = True,
    ):
        self.cu_pool = ComputeUnitPool(n_sms=8, threads_per_sm=256)
        self.spmd = SPMDExecutor(n_lanes=32)
        self.microkernels = MicroKernelLibrary()
        self.cassini = CassiniVerifier()
        self.require_gpu = require_gpu
        self.allow_cpu_fallback = allow_cpu_fallback
        self.punch_host = punch_host
        # Backend that physically ran the last projection; None until one has.
        self._last_projection_backend = None
        self.fallback_reason = None
        if self.punch_host is None:
            self.punch_host = resolve_punch_host()
        if (require_gpu or not allow_cpu_fallback) and not self.gpu_active:
            raise RuntimeError(
                "OpenCL device required by execution policy but none is available"
            )

    @property
    def gpu_active(self) -> bool:
        return self.punch_host is not None and getattr(self.punch_host, "use_opencl", False)

    @property
    def projection_backend(self) -> str:
        if self._last_projection_backend is not None:
            return self._last_projection_backend
        if self.gpu_active:
            return getattr(self.punch_host, "last_dispatch_backend", None) or getattr(
                self.punch_host, "backend", "cpu"
            )
        return "cpu"

    def _record_backend(self, backend: str, stage: str) -> None:
        self._last_projection_backend = backend
        used_cpu = not str(backend).startswith("opencl:")
        if used_cpu and (self.require_gpu or not self.allow_cpu_fallback):
            raise RuntimeError(
                f"{stage} used {backend!r} while CPU fallback is disabled"
            )

    def project_and_collapse_pv(self, data_tensor: np.ndarray, pv_base: float = PHI) -> int:
        self.fallback_reason = None
        flat = np.nan_to_num(
            data_tensor.flatten()[:DIM], nan=0.0, posinf=1.0, neginf=-1.0
        )
        if len(flat) == 0:
            return 0
        if self.gpu_active and pv_base == PHI:
            vec = np.zeros(DIM, dtype=np.float32)
            vec[: len(flat)] = flat
            try:
                out = self.punch_host.run_punch_batch(
                    PUNCH_MANIFOLD_COMPUTE,
                    n=1,
                    in_float=vec,
                )
            except Exception as exc:
                self._cpu_fallback_or_raise(
                    "opcode_0x15_unsupported"
                    if isinstance(exc, NotImplementedError)
                    else f"opencl_error:{type(exc).__name__}"
                )
            else:
                self._record_backend(
                    getattr(self.punch_host, "last_dispatch_backend", None)
                    or getattr(self.punch_host, "backend", "cpu"),
                    "manifold projection",
                )
                norm_sq = float(out["float"][0])
                if (
                    not np.isfinite(norm_sq)
                    or norm_sq < 0
                    or (
                        self.require_gpu
                        and "gpu" not in str(self._last_projection_backend).lower()
                    )
                ):
                    self._cpu_fallback_or_raise("invalid_or_non_gpu_result")
                else:
                    return int(round(float(np.sqrt(norm_sq)))) % 90
        else:
            self._cpu_fallback_or_raise("opencl_unavailable_or_not_selected")
        if self._last_projection_backend is None:
            self._last_projection_backend = "cpu"
        norm_sq = float(
            sum((pv_base ** -(i + 1)) * (float(flat[i]) ** 2) for i in range(len(flat)))
        )
        if not np.isfinite(norm_sq) or norm_sq < 0:
            raise RuntimeError("CPU projection produced a non-finite result")
        sqrt_norm = float(np.sqrt(norm_sq))
        # Collapse to the canonical Fibonacci manifold basis index in [0, 89]
        anchor = int(round(sqrt_norm)) % 90
        return max(0, anchor)

    def _cpu_fallback_or_raise(self, reason: str) -> None:
        if self.require_gpu or not self.allow_cpu_fallback:
            raise RuntimeError(f"CPU fallback denied by execution policy ({reason})")
        self._last_projection_backend = "cpu"
        self.fallback_reason = reason

    def verify_cassini_invariant(self, n: int) -> bool:
        """Rigorous Cassini verification: L_n^2 - 5 F_n^2 = 4 (-1)^n."""
        return self.cassini.verify(n)

    def shutdown(self) -> None:
        self.cu_pool.shutdown()


TensorCoreGPU_Context = ChronusContext
