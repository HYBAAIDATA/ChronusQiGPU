"""Enterprise benchmark suite runner — runs all module benchmarks.

Usage:
    python -m benchmarks.run_all [trials=20]

Runs the full suite across every module and writes a comprehensive report.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Add benchmarks directory to path
BENCHMARKS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCHMARKS_DIR))

from enterprise_benchmarks import BENCHMARK_REGISTRY, run_all_benchmarks, write_report


def main():
    trials = 20
    if len(sys.argv) > 1:
        try:
            trials = int(sys.argv[1])
        except ValueError:
            print(f"Invalid trials value: {sys.argv[1]}, using default 20")
            trials = 20

    print(f"\n=== Enterprise Benchmark Suite ===")
    print(f"Trials per benchmark: {trials}")
    print(f"Number of benchmarks: {len(BENCHMARK_REGISTRY)}")
    print()

    report = run_all_benchmarks(trials=trials)

    written_path = write_report("enterprise_benchmarks", report)
    print(f"\nBenchmark report written to: {written_path}")
    print(f"\nSummary:")
    print(f"  Reproducibility rate: {report['reproducibility_rate']:.1%}")
    if "aggregate_scaling_exponent" in report:
        print(f"  Aggregate scaling exponent: {report['aggregate_scaling_exponent']:.4f}")
    else:
        print("  Aggregate scaling exponent: N/A")
    print(f"  Successful benchmarks: {report['successful_benchmarks']}/{report['total_benchmarks']}")
    print()

    # Print per-benchmark results
    for name, result in report["per_benchmark"].items():
        if "error" in result:
            print(f"  {name}: ERROR - {result['error']}")
        else:
            summary = None
            for v in result.values():
                if isinstance(v, dict) and "mean" in v and "p95" in v:
                    summary = v
                    break
            if summary:
                print(
                    f"  {name}: mean={summary['mean']:.6f}s, "
                    f"p95={summary['p95']:.6f}s, "
                    f"trials={result.get('trials', '?')}"
                )
            else:
                print(f"  {name}: SUCCESS (trials={result.get('trials', '?')})")

    return 0


if __name__ == "__main__":
    sys.exit(main())