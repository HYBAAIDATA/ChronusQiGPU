"""Withdrawn legacy benchmark; retained import boundary, not evidence.

The former runner compared different work, silently truncated data when its
mining-only dependency was absent, and used a speed threshold as significance.
Those results must not be used for product, valuation, or publication claims.
Use ``python -m scripts.benchmark_data_region`` for an equivalent-output data
workload through the current Aethel region-decode implementation instead.
Historical result schemas remain importable for reading old reports only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

@dataclass
class BenchmarkResult:
    """Result from a single benchmark run."""

    benchmark_name: str
    workload_type: str
    variant: str
    iterations: int
    total_time_seconds: float
    mean_time_per_iteration: float
    std_time_per_iteration: float
    throughput_operations_per_second: float
    memory_peak_mb: float
    energy_joules: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "benchmark_name": self.benchmark_name,
            "workload_type": self.workload_type,
            "variant": self.variant,
            "iterations": self.iterations,
            "total_time_seconds": self.total_time_seconds,
            "mean_time_per_iteration": self.mean_time_per_iteration,
            "std_time_per_iteration": self.std_time_per_iteration,
            "throughput_operations_per_second": self.throughput_operations_per_second,
            "memory_peak_mb": self.memory_peak_mb,
            "energy_joules": self.energy_joules,
            "metadata": self.metadata,
        }


@dataclass
class BenchmarkComparison:
    """Comparison between traditional and φ-optimized variants."""

    benchmark_name: str
    workload_type: str
    traditional_result: BenchmarkResult
    phi_optimized_result: BenchmarkResult
    speedup_factor: float
    memory_reduction_percent: float
    energy_reduction_percent: Optional[float] = None
    statistical_significance: bool = False
    p_value: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "benchmark_name": self.benchmark_name,
            "workload_type": self.workload_type,
            "traditional_result": self.traditional_result.to_dict(),
            "phi_optimized_result": self.phi_optimized_result.to_dict(),
            "speedup_factor": self.speedup_factor,
            "memory_reduction_percent": self.memory_reduction_percent,
            "energy_reduction_percent": self.energy_reduction_percent,
            "statistical_significance": self.statistical_significance,
            "p_value": self.p_value,
        }


class LegacyBenchmarkUnavailable(RuntimeError):
    """Withdrawn methodology cannot produce new qualification evidence."""


class ProductionWorkloadBenchmark:
    """Compatibility tombstone: deliberately cannot run the withdrawn suite."""

    def __init__(self, warmup_iterations: int = 10, seed: int = 42):
        raise LegacyBenchmarkUnavailable(
            "Legacy production benchmark withdrawn: unequal workloads and "
            "truncating fallback. Run python -m scripts.benchmark_data_region; "
            "it measures region retrieval, not LLM or matrix-compute performance."
        )


__all__ = [
    "ProductionWorkloadBenchmark", "BenchmarkResult", "BenchmarkComparison",
    "LegacyBenchmarkUnavailable",
]
