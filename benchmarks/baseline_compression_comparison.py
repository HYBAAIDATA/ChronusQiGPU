"""Baseline compression benchmark: φ-fold+zlib vs plain compression.

This benchmark compares the actual net compression achieved by:
1. φ-fold + zlib on kernel (the PULVINI approach)
2. Plain zlib on raw array (baseline)
3. Plain gzip on raw array (baseline)

The goal is to determine whether the φ-fold step provides any benefit
over standard compression algorithms alone.
"""

import gzip
import sys
import time
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import numpy as np

# Add python_backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "python_backend"))

from pythia_mining.pulvini_phi_memory import PulviniPhiMemoryCompressionEngine


@dataclass
class BenchmarkResult:
    """Result of a single compression benchmark run."""
    method: str
    original_bytes: int
    compressed_bytes: int
    compression_ratio: float
    compress_time_ms: float
    decompress_time_ms: float
    reconstruction_error: float | None = None


def compress_plain_zlib(data: np.ndarray, level: int = 9) -> BenchmarkResult:
    """Compress array using plain zlib."""
    original_bytes = data.nbytes
    
    start = time.perf_counter()
    compressed = zlib.compress(data.tobytes(), level=level)
    compress_time = (time.perf_counter() - start) * 1000
    
    start = time.perf_counter()
    decompressed_bytes = zlib.decompress(compressed)
    decompress_time = (time.perf_counter() - start) * 1000
    
    decompressed = np.frombuffer(decompressed_bytes, dtype=data.dtype).reshape(data.shape)
    error = float(np.linalg.norm(data - decompressed)) if data.dtype != np.float16 else 0.0
    
    return BenchmarkResult(
        method="plain_zlib",
        original_bytes=original_bytes,
        compressed_bytes=len(compressed),
        compression_ratio=original_bytes / max(1, len(compressed)),
        compress_time_ms=compress_time,
        decompress_time_ms=decompress_time,
        reconstruction_error=error,
    )


def compress_plain_gzip(data: np.ndarray, level: int = 9) -> BenchmarkResult:
    """Compress array using plain gzip."""
    original_bytes = data.nbytes
    
    start = time.perf_counter()
    compressed = gzip.compress(data.tobytes(), compresslevel=level)
    compress_time = (time.perf_counter() - start) * 1000
    
    start = time.perf_counter()
    decompressed_bytes = gzip.decompress(compressed)
    decompress_time = (time.perf_counter() - start) * 1000
    
    decompressed = np.frombuffer(decompressed_bytes, dtype=data.dtype).reshape(data.shape)
    error = float(np.linalg.norm(data - decompressed)) if data.dtype != np.float16 else 0.0
    
    return BenchmarkResult(
        method="plain_gzip",
        original_bytes=original_bytes,
        compressed_bytes=len(compressed),
        compression_ratio=original_bytes / max(1, len(compressed)),
        compress_time_ms=compress_time,
        decompress_time_ms=decompress_time,
        reconstruction_error=error,
    )


def compress_phi_fold_zlib(data: np.ndarray, fold_depth: int = 2) -> BenchmarkResult:
    """Compress array using φ-fold + zlib on kernel (PULVINI approach)."""
    original_bytes = data.nbytes
    
    engine = PulviniPhiMemoryCompressionEngine(
        fold_depth=fold_depth,
        enforce_production_cap=False,
    )
    
    start = time.perf_counter()
    result = engine.compress(data)
    compress_time = (time.perf_counter() - start) * 1000
    
    start = time.perf_counter()
    reconstructed = engine.decompress(result)
    decompress_time = (time.perf_counter() - start) * 1000
    
    # Net compression includes both folded working set AND compressed kernels
    net_compressed_bytes = result.folded_working_set_bytes + result.retained_kernel_bytes
    
    return BenchmarkResult(
        method="phi_fold_zlib",
        original_bytes=original_bytes,
        compressed_bytes=net_compressed_bytes,
        compression_ratio=original_bytes / max(1, net_compressed_bytes),
        compress_time_ms=compress_time,
        decompress_time_ms=decompress_time,
        reconstruction_error=result.reconstruction_error,
    )


def generate_test_data(size: int, distribution: str = "normal") -> np.ndarray:
    """Generate test array of specified size and distribution."""
    rng = np.random.default_rng(seed=42)
    
    if distribution == "normal":
        return rng.standard_normal(size).astype(np.float64)
    elif distribution == "uniform":
        return rng.uniform(-1, 1, size).astype(np.float64)
    elif distribution == "sparse":
        data = np.zeros(size, dtype=np.float64)
        num_nonzero = max(1, size // 10)
        indices = rng.choice(size, num_nonzero, replace=False)
        data[indices] = rng.standard_normal(num_nonzero)
        return data
    elif distribution == "constant":
        return np.full(size, 1.0, dtype=np.float64)
    else:
        raise ValueError(f"Unknown distribution: {distribution}")


def run_benchmark_suite() -> Dict[str, List[BenchmarkResult]]:
    """Run full benchmark suite across various array sizes and distributions."""
    sizes = [100, 1000, 10000, 50000]
    distributions = ["normal", "uniform", "sparse"]
    
    results: Dict[str, List[BenchmarkResult]] = {
        "plain_zlib": [],
        "plain_gzip": [],
        "phi_fold_zlib": [],
    }
    
    for size in sizes:
        for dist in distributions:
            data = generate_test_data(size, dist)
            
            # Run each method
            results["plain_zlib"].append(compress_plain_zlib(data))
            results["plain_gzip"].append(compress_plain_gzip(data))
            results["phi_fold_zlib"].append(compress_phi_fold_zlib(data))
    
    return results


def print_results(results: Dict[str, List[BenchmarkResult]]) -> None:
    """Print benchmark results in a readable format."""
    print("\n" + "=" * 100)
    print("BASELINE COMPRESSION COMPARISON")
    print("=" * 100)
    print("\nComparing φ-fold+zlib vs plain zlib/gzip on raw arrays")
    print("Net compression includes ALL retained bytes (folded + kernels)\n")
    
    for method, method_results in results.items():
        print(f"\n{method.upper()}")
        print("-" * 100)
        
        avg_ratio = np.mean([r.compression_ratio for r in method_results])
        avg_compress = np.mean([r.compress_time_ms for r in method_results])
        avg_decompress = np.mean([r.decompress_time_ms for r in method_results])
        
        print(f"Average compression ratio: {avg_ratio:.3f}x")
        print(f"Average compress time: {avg_compress:.2f}ms")
        print(f"Average decompress time: {avg_decompress:.2f}ms")
        
        # Show individual results
        print("\nIndividual runs:")
        for i, r in enumerate(method_results):
            size_idx = i // 3
            dist_idx = i % 3
            size = [100, 1000, 10000, 50000][size_idx]
            dist = ["normal", "uniform", "sparse"][dist_idx]
            print(
                f"  size={size:6d} dist={dist:8s} | "
                f"ratio={r.compression_ratio:6.3f}x | "
                f"compress={r.compress_time_ms:6.2f}ms | "
                f"decompress={r.decompress_time_ms:6.2f}ms"
            )
    
    print("\n" + "=" * 100)
    print("CONCLUSION")
    print("=" * 100)
    
    phi_ratios = [r.compression_ratio for r in results["phi_fold_zlib"]]
    zlib_ratios = [r.compression_ratio for r in results["plain_zlib"]]
    
    avg_phi = np.mean(phi_ratios)
    avg_zlib = np.mean(zlib_ratios)
    
    print(f"\nAverage φ-fold+zlib compression ratio: {avg_phi:.3f}x")
    print(f"Average plain zlib compression ratio: {avg_zlib:.3f}x")
    
    if avg_phi > avg_zlib:
        improvement = ((avg_phi - avg_zlib) / avg_zlib) * 100
        print(f"φ-fold+zlib outperforms plain zlib by {improvement:.1f}%")
    else:
        degradation = ((avg_zlib - avg_phi) / avg_zlib) * 100
        print(f"Plain zlib outperforms φ-fold+zlib by {degradation:.1f}%")
        print("\n⚠️  The φ-fold step adds overhead without compression benefit.")
        print("   Net compression comes entirely from standard zlib on the kernel.")
    
    print("\n" + "=" * 100)


if __name__ == "__main__":
    results = run_benchmark_suite()
    print_results(results)
