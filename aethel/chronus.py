"""Aethel Chronus context — compute-unit orchestration over the Chronus offering.

Turing remains the compute substrate. This context owns Aethel's execution
resources and projects tensors through Chronus when a measured OpenCL punch host
is active; otherwise the identical numerical projection executes on CPU and the
backend provenance says so.
"""

from __future__ import annotations

import numpy as np

from .cassini import CassiniVerifier
from .compute import ComputeUnitPool, MicroKernelLibrary, SPMDExecutor
from .constants import DIM, PHI
from .punch import resolve_punch_host
from .zeckendorf import PUNCH_MANIFOLD_COMPUTE


class ChronusContext:
    """Aethel execution context bound to Chronus when hardware is available."""

    def __init__(self, punch_host=None, require_gpu: bool = False):
        self.cu_pool = ComputeUnitPool(n_sms=8, threads_per_sm=256)
        self.spmd = SPMDExecutor(n_lanes=32)
        self.microkernels = MicroKernelLibrary()
        self.cassini = CassiniVerifier()
        self.require_gpu = require_gpu
        self.punch_host = punch_host
        self._last_projection_backend = None
        if self.punch_host is None:
            self.punch_host = resolve_punch_host()
        if require_gpu and not self.gpu_active:
            raise RuntimeError(
                "Chronus GPU execution required but no OpenCL device is available; "
                "refusing to run substrate projections on the CPU."
            )

    @property
    def gpu_active(self) -> bool:
        """Whether Chronus is currently dispatching through a physical GPU."""
        return self.punch_host is not None and getattr(
            self.punch_host,
            "use_opencl",
            False,
        )

    @property
    def projection_backend(self) -> str:
        if self._last_projection_backend is not None:
            return self._last_projection_backend
        if self.gpu_active:
            return getattr(
                self.punch_host,
                "last_dispatch_backend",
                None,
            ) or getattr(self.punch_host, "backend", "cpu")
        return "cpu"

    def project_and_collapse_pv(
        self,
        data_tensor: np.ndarray,
        pv_base: float = PHI,
    ) -> int:
        flat = np.nan_to_num(
            data_tensor.flatten()[:DIM],
            nan=0.0,
            posinf=1.0,
            neginf=-1.0,
        )
        if len(flat) == 0:
            return 0
        if self.gpu_active and pv_base == PHI:
            vector = np.zeros(DIM, dtype=np.float32)
            vector[: len(flat)] = flat
            try:
                output = self.punch_host.run_punch_batch(
                    PUNCH_MANIFOLD_COMPUTE,
                    n=1,
                    in_float=vector,
                )
            except NotImplementedError:
                self._last_projection_backend = "cpu"
            else:
                self._last_projection_backend = getattr(
                    self.punch_host,
                    "last_dispatch_backend",
                    None,
                ) or getattr(self.punch_host, "backend", "cpu")
                norm_sq = float(output["float"][0])
                if not np.isfinite(norm_sq) or norm_sq < 0:
                    return 0
                anchor = int(round(float(np.sqrt(norm_sq)))) % 90
                return max(0, anchor)
        else:
            self._last_projection_backend = "cpu"

        norm_sq = float(
            sum(
                (pv_base ** -(index + 1)) * (float(flat[index]) ** 2)
                for index in range(len(flat))
            )
        )
        if not np.isfinite(norm_sq) or norm_sq < 0:
            return 0
        anchor = int(round(float(np.sqrt(norm_sq)))) % 90
        return max(0, anchor)

    def verify_cassini_invariant(self, n: int) -> bool:
        """Rigorous Cassini verification: L_n^2 - 5 F_n^2 = 4 (-1)^n."""
        return self.cassini.verify(n)

    def shutdown(self) -> None:
        self.cu_pool.shutdown()


__all__ = ["ChronusContext"]
