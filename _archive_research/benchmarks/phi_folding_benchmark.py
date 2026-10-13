"""Comprehensive Benchmark Suite for Phi-Folding Compression

This benchmark suite evaluates phi-folding compression performance across
different data sizes, types, and compression modes. It provides detailed
metrics for production deployment decisions.

Usage:
    python benchmarks/phi_folding_benchmark.py
    python benchmarks/phi_folding_benchmark.py --mode AUTO --sizes 512 1024 4096
"""

from __future__ import annotations

import argparse
import gc
import json
import sys
import time
import tracemalloc
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from pythia_mining.phi_folding import (
    KernelCompressionMode,
    PhiFoldingOperator,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python_backend"))


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""

    data_type: str
    data_size: int
    mode: str
    original_size: int
    compressed_size: int
    retained_size: int
    compression_ratio: float
    max_error: float
    rmse: float
    snr_db: float
    net_positive: bool
    fold_time_ms: float
    compress_time_ms: float
    decompress_time_ms: float
    unfold_time_ms: float
    total_time_ms: float
    peak_memory_mb: float
    memory_efficiency: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "data_type": self.data_type,
            "data_size": self.data_size,
            "mode": self.mode,
            "original_size": self.original_size,
            "compressed_size": self.compressed_size,
            "retained_size": self.retained_size,
            "compression_ratio": self.compression_ratio,
            "max_error": self.max_error,
            "rmse": self.rmse,
            "snr_db": self.snr_db,
            "net_positive": bool(self.net_positive),
            "fold_time_ms": self.fold_time_ms,
            "compress_time_ms": self.compress_time_ms,
            "decompress_time_ms": self.decompress_time_ms,
            "unfold_time_ms": self.unfold_time_ms,
            "total_time_ms": self.total_time_ms,
            "peak_memory_mb": self.peak_memory_mb,
            "memory_efficiency": self.memory_efficiency,
            "metadata": self.metadata,
        }


class PhiFoldingBenchmark:
    """Comprehensive benchmark suite for phi-folding compression."""

    def __init__(self, output_dir: str = "benchmark_results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.results: List[BenchmarkResult] = []

    def generate_test_data(
        self, data_type: str, size: int, rng: np.random.Generator
    ) -> np.ndarray:
        """Generate test data of specified type and size.

        Args:
            data_type: Type of data to generate.
            size: Number of elements.
            rng: Random number generator.

        Returns:
            Generated test data array.
        """
        if data_type == "random_normal":
            return rng.standard_normal(size)
        elif data_type == "random_uniform":
            return rng.uniform(-1, 1, size)
        elif data_type == "smooth_sine":
            return np.sin(np.linspace(0, 10 * np.pi, size))
        elif data_type == "structured_low_var":
            return rng.normal(0, 0.1, size)
        elif data_type == "high_entropy":
            return rng.standard_normal(size) * rng.uniform(0.5, 2.0, size)
        elif data_type == "sparse":
            data = np.zeros(size)
            nonzero = int(size * 0.1)
            indices = rng.choice(size, nonzero, replace=False)
            data[indices] = rng.standard_normal(nonzero)
            return data
        else:
            return rng.standard_normal(size)

    def run_benchmark(
        self,
        data_type: str,
        size: int,
        mode: KernelCompressionMode,
        rng: np.random.Generator,
    ) -> BenchmarkResult:
        """Run a single benchmark with specified parameters.

        Args:
            data_type: Type of test data.
            size: Data size in elements.
            mode: Compression mode to test.
            rng: Random number generator.

        Returns:
            BenchmarkResult with all metrics.
        """
        # Start memory tracking
        tracemalloc.start()
        gc.collect()

        data = self.generate_test_data(data_type, size, rng)
        op = PhiFoldingOperator(kernel_compression_mode=mode)

        # Time fold operation
        start = time.time()
        folded, kernel, orig_size = op.fold(data)
        fold_time = (time.time() - start) * 1000

        # Time compress operation
        start = time.time()
        compressed_kernels, ratio = op.compress_kernels([kernel])
        compress_time = (time.time() - start) * 1000

        ck = compressed_kernels[0]

        # Time decompress operation
        start = time.time()
        decompressed_kernels = op.decompress_kernels(compressed_kernels)
        decompress_time = (time.time() - start) * 1000

        k_reconstructed = decompressed_kernels[0]

        # Time unfold operation
        start = time.time()
        rec = op.unfold(folded, k_reconstructed, orig_size)
        unfold_time = (time.time() - start) * 1000

        # Get peak memory usage
        current, peak = tracemalloc.get_traced_memory()
        peak_memory_mb = peak / (1024 * 1024)
        tracemalloc.stop()

        # Compute metrics
        max_err = float(np.max(np.abs(rec - data)))
        rmse = float(np.sqrt(np.mean((rec - data) ** 2)))
        snr = op._compute_snr(data, rec)

        retained = folded.nbytes + ck.compressed_size
        total_time = fold_time + compress_time + decompress_time + unfold_time
        memory_efficiency = data.nbytes / (retained + 1)

        return BenchmarkResult(
            data_type=data_type,
            data_size=size,
            mode=mode.name,
            original_size=data.nbytes,
            compressed_size=ck.compressed_size,
            retained_size=retained,
            compression_ratio=ck.compression_ratio,
            max_error=max_err,
            rmse=rmse,
            snr_db=snr,
            net_positive=retained < data.nbytes,
            fold_time_ms=fold_time,
            compress_time_ms=compress_time,
            decompress_time_ms=decompress_time,
            unfold_time_ms=unfold_time,
            total_time_ms=total_time,
            peak_memory_mb=peak_memory_mb,
            memory_efficiency=memory_efficiency,
            metadata={
                "chosen_mode": op._last_stats.get("chosen_mode", mode.name),
                "data_stats": op._last_stats,
            },
        )

    def run_comprehensive_benchmark(
        self,
        data_types: List[str],
        sizes: List[int],
        modes: List[KernelCompressionMode],
        seed: int = 42,
    ) -> List[BenchmarkResult]:
        """Run comprehensive benchmark across all parameter combinations.

        Args:
            data_types: List of data types to test.
            sizes: List of data sizes to test.
            modes: List of compression modes to test.
            seed: Random seed for reproducibility.

        Returns:
            List of all benchmark results.
        """
        rng = np.random.default_rng(seed)
        self.results = []

        total_runs = len(data_types) * len(sizes) * len(modes)
        current_run = 0

        for data_type in data_types:
            for size in sizes:
                for mode in modes:
                    current_run += 1
                    print(
                        f"Running {current_run}/{total_runs}: {data_type}, size={size}, mode={mode.name}"
                    )

                    try:
                        result = self.run_benchmark(data_type, size, mode, rng)
                        self.results.append(result)
                    except Exception as e:
                        print(f"  Error: {e}")
                        continue

        return self.results

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive benchmark report.

        Returns:
            Dictionary with benchmark summary and detailed results.
        """
        if not self.results:
            return {"status": "no_results", "timestamp": datetime.now(timezone.utc).isoformat()}

        # Group results by mode
        by_mode: Dict[str, List[BenchmarkResult]] = {}
        for result in self.results:
            if result.mode not in by_mode:
                by_mode[result.mode] = []
            by_mode[result.mode].append(result)

        # Compute statistics per mode
        mode_stats = {}
        for mode, results in by_mode.items():
            avg_ratio = np.mean([r.compression_ratio for r in results])
            avg_snr = np.mean([r.snr_db for r in results])
            avg_time = np.mean([r.total_time_ms for r in results])
            avg_memory = np.mean([r.peak_memory_mb for r in results])
            avg_memory_efficiency = np.mean([r.memory_efficiency for r in results])
            net_positive_rate = np.mean([r.net_positive for r in results])

            mode_stats[mode] = {
                "avg_compression_ratio": float(avg_ratio),
                "avg_snr_db": float(avg_snr),
                "avg_total_time_ms": float(avg_time),
                "avg_peak_memory_mb": float(avg_memory),
                "avg_memory_efficiency": float(avg_memory_efficiency),
                "net_positive_rate": float(net_positive_rate),
                "num_runs": len(results),
            }

        # Find best mode by different metrics
        best_compression = max(
            mode_stats.items(), key=lambda x: x[1]["avg_compression_ratio"]
        )
        best_snr = max(mode_stats.items(), key=lambda x: x[1]["avg_snr_db"])
        best_speed = min(mode_stats.items(), key=lambda x: x[1]["avg_total_time_ms"])
        best_memory = min(mode_stats.items(), key=lambda x: x[1]["avg_peak_memory_mb"])

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_runs": len(self.results),
            "mode_statistics": mode_stats,
            "best_compression_mode": best_compression[0],
            "best_compression_ratio": best_compression[1]["avg_compression_ratio"],
            "best_snr_mode": best_snr[0],
            "best_snr_db": best_snr[1]["avg_snr_db"],
            "fastest_mode": best_speed[0],
            "fastest_time_ms": best_speed[1]["avg_total_time_ms"],
            "best_memory_mode": best_memory[0],
            "best_memory_mb": best_memory[1]["avg_peak_memory_mb"],
            "detailed_results": [r.to_dict() for r in self.results],
        }

    def save_report(self, filename: str = "phi_folding_benchmark_report.json"):
        """Save benchmark report to JSON file.

        Args:
            filename: Output filename.
        """
        report = self.generate_report()
        output_path = self.output_dir / filename

        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)

        print(f"Report saved to {output_path}")

    def print_summary(self):
        """Print benchmark summary to console."""
        report = self.generate_report()

        print("\n" + "=" * 60)
        print("PHI-FOLDING BENCHMARK SUMMARY")
        print("=" * 60)
        print(f"Total runs: {report['total_runs']}")
        print(f"Timestamp: {report['timestamp']}")

        print("\n--- Mode Statistics ---")
        for mode, stats in report["mode_statistics"].items():
            print(f"\n{mode}:")
            print(f"  Avg compression ratio: {stats['avg_compression_ratio']:.2f}x")
            print(f"  Avg SNR: {stats['avg_snr_db']:.2f} dB")
            print(f"  Avg total time: {stats['avg_total_time_ms']:.2f} ms")
            print(f"  Avg peak memory: {stats['avg_peak_memory_mb']:.2f} MB")
            print(f"  Avg memory efficiency: {stats['avg_memory_efficiency']:.2f}x")
            print(f"  Net positive rate: {stats['net_positive_rate']:.1%}")

        print("\n--- Best Modes ---")
        print(f"Best compression: {report['best_compression_mode']} ({report['best_compression_ratio']:.2f}x)")
        print(f"Best SNR: {report['best_snr_mode']} ({report['best_snr_db']:.2f} dB)")
        print(f"Fastest: {report['fastest_mode']} ({report['fastest_time_ms']:.2f} ms)")
        print(f"Best memory: {report['best_memory_mode']} ({report['best_memory_mb']:.2f} MB)")
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Phi-Folding Compression Benchmark Suite")
    parser.add_argument(
        "--data-types",
        nargs="+",
        default=["random_normal", "smooth_sine", "structured_low_var", "high_entropy"],
        help="Data types to benchmark",
    )
    parser.add_argument(
        "--sizes",
        nargs="+",
        type=int,
        default=[512, 1024, 4096, 16384],
        help="Data sizes to benchmark",
    )
    parser.add_argument(
        "--modes",
        nargs="+",
        default=["AUTO", "QUANT16", "QUANT8", "DELTA16"],
        help="Compression modes to benchmark",
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed for reproducibility"
    )
    parser.add_argument(
        "--output-dir", default="benchmark_results", help="Output directory for results"
    )
    parser.add_argument(
        "--report-file", default="phi_folding_benchmark_report.json", help="Report filename"
    )

    args = parser.parse_args()

    # Convert mode names to enum
    mode_map = {
        "AUTO": KernelCompressionMode.AUTO,
        "QUANT16": KernelCompressionMode.QUANT16,
        "QUANT8": KernelCompressionMode.QUANT8,
        "DELTA16": KernelCompressionMode.DELTA16,
        "NONE": KernelCompressionMode.NONE,
        "ZLIB": KernelCompressionMode.ZLIB,
    }

    modes = [mode_map[m] for m in args.modes if m in mode_map]

    # Run benchmark
    benchmark = PhiFoldingBenchmark(output_dir=args.output_dir)
    benchmark.run_comprehensive_benchmark(
        data_types=args.data_types, sizes=args.sizes, modes=modes, seed=args.seed
    )

    # Print summary and save report
    benchmark.print_summary()
    benchmark.save_report(args.report_file)


if __name__ == "__main__":
    main()
