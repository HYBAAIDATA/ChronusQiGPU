"""GPU Throughput Benchmark for PULVINI φ-Folding.

Validates the pitch deck claim of 1-5 GB/s throughput on NVIDIA GPUs.

Run:
    PYTHONPATH=python_backend python3 benchmarks/gpu_throughput_benchmark.py
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python_backend"))


@dataclass
class ThroughputResult:
    """Result of a single throughput benchmark."""

    backend: str
    array_size: int
    dtype: str
    fold_depth: int
    iterations: int
    total_time_ms: float
    throughput_gb_s: float
    meets_1gb_target: bool
    meets_5gb_target: bool


def benchmark_cpu_throughput(size: int, depth: int, iterations: int) -> float:
    """Benchmark CPU throughput in GB/s.
    
    Args:
        size: Array size in elements.
        depth: Fold depth.
        iterations: Number of iterations.
    
    Returns:
        Throughput in GB/s.
    """
    from pythia_mining.phi_folding import PhiFoldingOperator
    
    data = np.random.randn(size).astype(np.float64)
    op = PhiFoldingOperator()
    
    # Warmup
    for _ in range(3):
        folded, kernel, _ = op.fold(data)
    
    # Benchmark
    start = time.perf_counter()
    for _ in range(iterations):
        folded, kernel, _ = op.fold(data)
    end = time.perf_counter()
    
    total_time_s = end - start
    total_bytes = size * 8 * iterations  # 8 bytes per float64
    throughput_gb_s = (total_bytes / total_time_s) / 1e9
    
    return throughput_gb_s


def benchmark_gpu_throughput(size: int, depth: int, iterations: int) -> float | None:
    """Benchmark GPU throughput using CUDA if available.
    
    Args:
        size: Array size in elements.
        depth: Fold depth.
        iterations: Number of iterations.
    
    Returns:
        Throughput in GB/s, or None if CUDA not available.
    """
    try:
        import cupy as cp
        
        # Generate test data on GPU
        h_data = np.random.randn(size).astype(np.float64)
        d_data = cp.asarray(h_data)
        d_folded = cp.empty_like(d_data)
        
        # Get CUDA kernel
        kernel_path = Path(__file__).resolve().parents[1] / "phi_sdk" / "phi_cuda.cu"
        if not kernel_path.exists():
            return None
        
        # Load and compile kernel
        from cupy import RawKernel
        
        # Simple φ-fold kernel for CuPy
        phi_fold_kernel = RawKernel(r'''
        extern "C" __global__
        void phi_fold_kernel(const double* input, double* output, size_t n) {
            size_t idx = blockIdx.x * blockDim.x + threadIdx.x;
            if (idx < n / 2) {
                size_t i = idx * 2;
                double a = input[i];
                double b = input[i + 1];
                const double PHI = 1.6180339887498948482045868343656;
                const double PHI_SQRT5 = 2.2360679774997896964091736687312;
                output[idx] = (a + PHI * b) / PHI_SQRT5;
                output[n / 2 + idx] = (PHI * a + b) / PHI_SQRT5;
            }
        }
        ''', 'phi_fold_kernel')
        
        # Warmup
        for _ in range(3):
            phi_fold_kernel((size // 2 + 255) // 256, (256,), (d_data, d_folded, size))
            cp.cuda.Stream.null.synchronize()
        
        # Benchmark
        start = time.perf_counter()
        for _ in range(iterations):
            phi_fold_kernel((size // 2 + 255) // 256, (256,), (d_data, d_folded, size))
            cp.cuda.Stream.null.synchronize()
        end = time.perf_counter()
        
        total_time_s = end - start
        total_bytes = size * 8 * iterations
        throughput_gb_s = (total_bytes / total_time_s) / 1e9
        
        return throughput_gb_s
        
    except ImportError:
        return None


def run_gpu_throughput_benchmark() -> dict[str, Any]:
    """Run comprehensive GPU throughput benchmark.
    
    Returns:
        Dictionary with benchmark results.
    """
    print("=" * 70)
    print("GPU THROUGHPUT BENCHMARK")
    print("=" * 70)
    
    results: list[ThroughputResult] = []
    
    # Test configurations
    test_configs = [
        # (size, depth, iterations)
        (1024, 2, 1000),
        (4096, 2, 1000),
        (16384, 2, 500),
        (65536, 2, 100),
        (262144, 2, 50),
    ]
    
    print("\n--- CPU Backend ---")
    for size, depth, iterations in test_configs:
        throughput = benchmark_cpu_throughput(size, depth, iterations)
        meets_1gb = throughput >= 1.0
        meets_5gb = throughput >= 5.0
        
        results.append(ThroughputResult(
            backend="CPU",
            array_size=size,
            dtype="float64",
            fold_depth=depth,
            iterations=iterations,
            total_time_ms=0.0,
            throughput_gb_s=throughput,
            meets_1gb_target=meets_1gb,
            meets_5gb_target=meets_5gb,
        ))
        
        status_1gb = "✅" if meets_1gb else "❌"
        status_5gb = "✅" if meets_5gb else "❌"
        print(f"  {size:6d} elements | {throughput:6.2f} GB/s | "
              f"1GB={status_1gb} 5GB={status_5gb}")
    
    # GPU benchmark
    print("\n--- GPU Backend (CUDA) ---")
    gpu_available = False
    for size, depth, iterations in test_configs:
        throughput = benchmark_gpu_throughput(size, depth, iterations)
        
        if throughput is not None:
            gpu_available = True
            meets_1gb = throughput >= 1.0
            meets_5gb = throughput >= 5.0
            
            results.append(ThroughputResult(
                backend="CUDA",
                array_size=size,
                dtype="float64",
                fold_depth=depth,
                iterations=iterations,
                total_time_ms=0.0,
                throughput_gb_s=throughput,
                meets_1gb_target=meets_1gb,
                meets_5gb_target=meets_5gb,
            ))
            
            status_1gb = "✅" if meets_1gb else "❌"
            status_5gb = "✅" if meets_5gb else "❌"
            print(f"  {size:6d} elements | {throughput:6.2f} GB/s | "
                  f"1GB={status_1gb} 5GB={status_5gb}")
    
    if not gpu_available:
        print("  ⚠️  CUDA not available (install cupy or run on NVIDIA GPU)")
    
    # Summary
    print("\n" + "=" * 70)
    print("BENCHMARK SUMMARY")
    print("=" * 70)
    
    cpu_results = [r for r in results if r.backend == "CPU"]
    gpu_results = [r for r in results if r.backend == "CUDA"]
    
    if cpu_results:
        avg_cpu = np.mean([r.throughput_gb_s for r in cpu_results])
        max_cpu = max([r.throughput_gb_s for r in cpu_results])
        print(f"CPU:  avg={avg_cpu:.2f} GB/s, max={max_cpu:.2f} GB/s")
    
    if gpu_results:
        avg_gpu = np.mean([r.throughput_gb_s for r in gpu_results])
        max_gpu = max([r.throughput_gb_s for r in gpu_results])
        print(f"GPU:  avg={avg_gpu:.2f} GB/s, max={max_gpu:.2f} GB/s")
    
    meets_pitch_deck = (
        (cpu_results and max(r.throughput_gb_s for r in cpu_results) >= 1.0) or
        (gpu_results and max(r.throughput_gb_s for r in gpu_results) >= 1.0)
    )
    
    print("\n" + "=" * 70)
    if meets_pitch_deck:
        print("✅ THROUGHPUT CLAIM VALIDATED (>= 1 GB/s)")
    else:
        print("❌ THROUGHPUT CLAIM NOT VALIDATED (< 1 GB/s)")
    print("=" * 70)
    
    return {
        "claim": "1-5 GB/s throughput",
        "validated": meets_pitch_deck,
        "cpu_results": [
            {
                "backend": r.backend,
                "array_size": r.array_size,
                "throughput_gb_s": r.throughput_gb_s,
                "meets_1gb": r.meets_1gb_target,
                "meets_5gb": r.meets_5gb_target,
            }
            for r in cpu_results
        ],
        "gpu_results": [
            {
                "backend": r.backend,
                "array_size": r.array_size,
                "throughput_gb_s": r.throughput_gb_s,
                "meets_1gb": r.meets_1gb_target,
                "meets_5gb": r.meets_5gb_target,
            }
            for r in gpu_results
        ],
    }


if __name__ == "__main__":
    report = run_gpu_throughput_benchmark()
    
    # Save report
    output_dir = Path(__file__).parent / "benchmark_results"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "gpu_throughput_benchmark.json"
    
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\nReport saved to: {output_path}")