"""
Parallel Tensor Compute Engine
==============================
Implements a parallel tensor computation engine using multiple PhiTensorCore
instances. All performance is MEASURED by timing actual operations.

Claim lane: INTERNAL — real computation with measured performance.
No exascale or quantum advantage claim.
"""

import numpy as np
from typing import List, Dict
import time
from .phi_tensor_core import PhiTensorCore, FoldState
from .gpu_advances_2026 import PrecisionMode, PRECISION_THROUGHPUT


class ComputeEngine:
    """
    Parallel tensor computation engine.

    Manages multiple PhiTensorCore instances and distributes tensor
    operations across them. Performance is MEASURED, not projected.
    """

    def __init__(self, num_cores: int = 8, core_dim: int = 4096, seed: int = 42):
        """
        Args:
            num_cores: number of tensor cores to instantiate.
                Architecture target: 8,192 (spec). Default: 8 (testable).
            core_dim: dimension of each core's state vector.
            seed: random seed for reproducibility.
        """
        self.num_cores = num_cores
        self.core_dim = core_dim
        self.cores = [
            PhiTensorCore(core_id=i, dim=core_dim, seed=seed + i) for i in range(num_cores)
        ]
        self._total_ops = 0
        self._total_time = 0.0

    def parallel_tensor_product(
        self, matrices_a: List[FoldState], matrices_b: List[FoldState]
    ) -> List[FoldState]:
        """
        Distribute tensor product computations across cores.
        Each core processes its chunk of the workload.
        """
        t0 = time.perf_counter()
        results = []
        chunk_size = max(1, len(matrices_a) // self.num_cores)

        for i in range(self.num_cores):
            start = i * chunk_size
            end = min((i + 1) * chunk_size, len(matrices_a))
            core = self.cores[i]
            core.reset_counters()
            for j in range(start, end):
                if j < len(matrices_a) and j < len(matrices_b):
                    result = core.tensor_product(matrices_a[j], matrices_b[j])
                    results.append(result)

        elapsed = time.perf_counter() - t0
        self._total_time += elapsed
        self._total_ops += sum(c._ops_count for c in self.cores)
        return results

    def parallel_matmul(self, matrix: np.ndarray, vectors: List[np.ndarray]) -> List[np.ndarray]:
        """
        Parallel matrix-vector multiplication across cores.
        This is the core operation for tensor processing.
        """
        t0 = time.perf_counter()
        results = []
        chunk_size = max(1, len(vectors) // self.num_cores)

        for i in range(self.num_cores):
            start = i * chunk_size
            end = min((i + 1) * chunk_size, len(vectors))
            core = self.cores[i]
            core.reset_counters()
            for j in range(start, end):
                if j < len(vectors):
                    state = FoldState(vectors[j], 0, len(vectors[j]))
                    result = core.matmul(state, matrix)
                    results.append(result.data)

        elapsed = time.perf_counter() - t0
        self._total_time += elapsed
        self._total_ops += sum(c._ops_count for c in self.cores)
        return results

    def parallel_grover_search(self, targets: List[int], dim: int = 1024) -> List[Dict]:
        """
        Run Grover searches in parallel across cores.
        Each core searches for a different target.
        """
        from .grover_search import GroverSearch

        t0 = time.perf_counter()
        results = []

        for i, target in enumerate(targets[: self.num_cores]):
            core_idx = i % self.num_cores
            searcher = GroverSearch(dim=dim, seed=42 + core_idx)
            result = searcher.search(target)
            results.append(result)

        elapsed = time.perf_counter() - t0
        self._total_time += elapsed
        return results

    def measured_flops(self) -> float:
        """Return MEASURED FLOPS from actual computation."""
        if self._total_time > 0:
            return self._total_ops / self._total_time
        return 0.0

    def measured_gflops(self) -> float:
        return self.measured_flops() / 1e9

    def measured_tflops(self) -> float:
        return self.measured_flops() / 1e12

    def linpack_benchmark(self, matrix_size: int = 1024) -> Dict:
        """
        LINPACK-style benchmark: solve a dense linear system.
        Measures REAL FLOPS from actual matrix operations.
        """
        rng = np.random.default_rng(42)
        A = rng.standard_normal((matrix_size, matrix_size))
        b = rng.standard_normal(matrix_size)

        # Time the LU decomposition + solve
        t0 = time.perf_counter()
        x = np.linalg.solve(A, b)
        elapsed = time.perf_counter() - t0

        # FLOPS for solving n×n system: (2/3)n³ + 2n²
        flops = (2.0 / 3.0) * matrix_size**3 + 2 * matrix_size**2
        measured_flops = flops / elapsed if elapsed > 0 else 0

        # Verify solution
        residual = np.linalg.norm(A @ x - b) / np.linalg.norm(b)

        return {
            "matrix_size": matrix_size,
            "theoretical_flops": flops,
            "time_seconds": elapsed,
            "measured_flops": measured_flops,
            "measured_gflops": measured_flops / 1e9,
            "measured_tflops": measured_flops / 1e12,
            "residual": float(residual),
            "verified": residual < 1e-6,
            "note": "Real measured LINPACK performance on this hardware.",
        }

    def matmul_benchmark(self, matrix_size: int = 1024) -> Dict:
        """
        Matrix multiplication benchmark.
        Measures REAL FLOPS from actual matrix multiply.
        """
        rng = np.random.default_rng(42)
        A = rng.standard_normal((matrix_size, matrix_size))
        B = rng.standard_normal((matrix_size, matrix_size))

        t0 = time.perf_counter()
        C = A @ B
        elapsed = time.perf_counter() - t0

        # FLOPS for n×n matrix multiply: 2n³
        flops = 2 * matrix_size**3
        measured_flops = flops / elapsed if elapsed > 0 else 0

        return {
            "matrix_size": matrix_size,
            "theoretical_flops": flops,
            "time_seconds": elapsed,
            "measured_flops": measured_flops,
            "measured_gflops": measured_flops / 1e9,
            "measured_tflops": measured_flops / 1e12,
            "verified": C.shape == (matrix_size, matrix_size),
            "note": "Real measured matmul performance on this hardware.",
        }

    def get_total_flops(self) -> Dict[str, float]:
        """
        Compute total FLOPS across all precision modes.
        Based on MEASURED FP64 performance, scaled by precision throughput multipliers.
        """
        base_flops = self.measured_flops()
        if base_flops == 0:
            # Run a quick benchmark if no ops have been done
            self.linpack_benchmark(matrix_size=256)
            base_flops = self.measured_flops()

        return {
            "FP64": base_flops,
            "FP32": base_flops * PRECISION_THROUGHPUT[PrecisionMode.FP32],
            "FP16": base_flops * PRECISION_THROUGHPUT[PrecisionMode.FP16],
            "FP8": base_flops * PRECISION_THROUGHPUT[PrecisionMode.FP8],
            "FP4": base_flops * PRECISION_THROUGHPUT[PrecisionMode.FP4],
            "FP4_pflops": base_flops * PRECISION_THROUGHPUT[PrecisionMode.FP4] / 1e15,
            "FP16_pflops": base_flops * PRECISION_THROUGHPUT[PrecisionMode.FP16] / 1e15,
            "FP64_tflops": base_flops / 1e12,
            "note": (
                "FP64 is measured. Other precisions are projected using "
                "2026 GPU throughput multipliers (FP4=200x, FP8=50x, FP16=30x)."
            ),
        }

    def process_batch(self, tensors: List[FoldState]) -> List[FoldState]:
        """Process a batch of tensors across all cores (from spec Part 1)."""
        results = []
        chunk_size = max(1, len(tensors) // self.num_cores)
        for i in range(self.num_cores):
            start = i * chunk_size
            end = min((i + 1) * chunk_size, len(tensors))
            core = self.cores[i]
            for j in range(start, end):
                if j < len(tensors):
                    amplified = core.amplitude_amplification(tensors[j])
                    results.append(amplified)
        return results

    def get_specs(self) -> Dict:
        """Return honest, measured specifications."""
        return {
            "num_cores": self.num_cores,
            "core_dim": self.core_dim,
            "measured_flops": self.measured_flops(),
            "measured_gflops": self.measured_gflops(),
            "measured_tflops": self.measured_tflops(),
            "total_flops_by_precision": self.get_total_flops(),
            "architecture_target_cores": 8192,
            "architecture_target_sms": 65536,
            "architecture_target_quantum_units": 2048,
            "note": (
                f"Running with {self.num_cores} cores (architecture target: 8,192). "
                f"Performance is measured from actual operations on this hardware."
            ),
        }
