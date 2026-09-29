"""TensorCoreGPU_Context — compute context with hardened Cassini checks.

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


class TensorCoreGPU_Context:
    def __init__(self, punch_host=None, require_gpu: bool = False):
        self.cu_pool = ComputeUnitPool(n_sms=8, threads_per_sm=256)
        self.spmd = SPMDExecutor(n_lanes=32)
        self.microkernels = MicroKernelLibrary()
        self.cassini = CassiniVerifier()
        self.require_gpu = require_gpu
        self.punch_host = punch_host
        if self.punch_host is None:
            self.punch_host = resolve_punch_host()
        if require_gpu and not self.gpu_active:
            raise RuntimeError(
                "GPU execution required but no OpenCL device is available; "
                "refusing to run substrate projections on the CPU."
            )

    @property
    def gpu_active(self) -> bool:
        return self.punch_host is not None and getattr(self.punch_host, "use_opencl", False)

    @property
    def projection_backend(self) -> str:
        if self.gpu_active:
            return getattr(self.punch_host, "last_dispatch_backend", None) or getattr(
                self.punch_host, "backend", "cpu"
            )
        return "cpu"

    def project_and_collapse_pv(self, data_tensor: np.ndarray, pv_base: float = PHI) -> int:
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
            except NotImplementedError:
                # OpenClPunchHost supports only 0x02/0x1C; 0x15 falls back
                # to the exact CPU projection below instead of crashing.
                pass
            else:
                norm_sq = float(out["float"][0])
                if not np.isfinite(norm_sq) or norm_sq < 0:
                    return 0
                anchor = int(round(float(np.sqrt(norm_sq)))) % 90
                return max(0, anchor)
        norm_sq = float(
            sum((pv_base ** -(i + 1)) * (float(flat[i]) ** 2) for i in range(len(flat)))
        )
        if not np.isfinite(norm_sq) or norm_sq < 0:
            return 0
        sqrt_norm = float(np.sqrt(norm_sq))
        # Collapse to the canonical Fibonacci manifold basis index in [0, 89]
        anchor = int(round(sqrt_norm)) % 90
        return max(0, anchor)

    def verify_cassini_invariant(self, n: int) -> bool:
        """Rigorous Cassini verification: L_n^2 - 5 F_n^2 = 4 (-1)^n."""
        return self.cassini.verify(n)

    def shutdown(self) -> None:
        self.cu_pool.shutdown()
