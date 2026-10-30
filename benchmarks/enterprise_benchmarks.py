"""Enterprise benchmark suite — registry and runner.

This file centralizes the benchmark registry and the master runner so that
run_all.py can import from it without each benchmark file needing to re-declare
all the other modules.  It pulls the per‑benchmark functions from the individual
benchmarks/*_bench.py modules.
"""

from __future__ import annotations

import json
import os
import sys
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

# Add this directory and parent paths so sub-modules are importable
BENCHMARKS_DIR = Path(__file__).resolve().parent
ROOT = BENCHMARKS_DIR.parent
for _extra in (
    str(ROOT),
    str(ROOT / "turing_universal_quantum_computer"),
    str(ROOT / "chronus/mla1517_platform" / "python"),
):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

from benchmarks.common import rng_for, summarize, SEED, sha256d, env_fingerprint, bootstrap_ci, quantile, loglog_slope, poisson, uniform_winners, synthetic_header, real_winners, write_report as common_write_report

# Dynamically import each benchmark module and extract the benchmark function
BENCHMARK_MODULE_NAMES = [
    "grover_bench",
    "hash_pipeline_bench",
    "traversal_bench",
    "lucas_bench",
    "toe_bench",
    "intelligence_bench",
    "kellogg_bench",
    "poincare_bench",
    "substrate_bench",
    "mining_bench",
]

BENCHMARK_REGISTRY: Dict[str, callable] = {}

for mod_name in BENCHMARK_MODULE_NAMES:
    try:
        mod = import_module(f"benchmarks.{mod_name}")
        # Find the bench_* function in the module
        for attr_name in dir(mod):
            if attr_name.startswith("bench_") and callable(getattr(mod, attr_name)):
                # Derive the key name from the function name
                key = attr_name.replace("bench_", "").lower()
                BENCHMARK_REGISTRY[key] = getattr(mod, attr_name)
                break
    except ImportError as e:
        print(f"Warning: Could not import benchmarks.{mod_name}: {e}")


def run_all_benchmarks(trials: int = 20) -> Dict[str, Any]:
    """Run the full enterprise benchmark suite across every module.

    Returns a consolidated results dictionary with:
      - Per-benmark results
      - Aggregate scaling laws
      - Cross-module reproducibility summary
      - Environment fingerprint
    """
    from benchmarks.common import env_fingerprint

    fingerprint = env_fingerprint()
    all_results: Dict[str, Any] = {}

    for name, benchmark_fn in BENCHMARK_REGISTRY.items():
        print(f"Running benchmark: {name} (trials={trials}...")
        try:
            result = benchmark_fn(trials=trials)
            all_results[name] = result
        except Exception as e:
            all_results[name] = {
                "name": name,
                "error": str(e),
                "trials": trials,
                "seed": SEED,
            }
            print(f"  ERROR in {name}: {e}")

    # Compute aggregate reproducibility
    reproducible_count = sum(
        1 for r in all_results.values()
        if isinstance(r, dict) and r.get("seed") == SEED and "error" not in r
    )
    reproducibility_rate = reproducible_count / len(BENCHMARK_REGISTRY) if BENCHMARK_REGISTRY else 0

    report = {
        "fingerprint": fingerprint,
        "seed": SEED,
        "trials_per_benchmark": trials,
        "total_benchmarks": len(BENCHMARK_REGISTRY),
        "successful_benchmarks": reproducible_count,
        "reproducibility_rate": reproducibility_rate,
        "per_benchmark": all_results,
    }

    return report


def write_report(name: str, results: dict) -> Path:
    """Write a benchmark report to the reports directory."""
    REPORTS = ROOT / "reports"
    DATA = REPORTS / "data"
    REPORTS.mkdir(exist_ok=True)
    DATA.mkdir(exist_ok=True)
    path = REPORTS / f"{name}.md"
    path.write_text(
        json.dumps(results, indent=2, default=str), encoding="utf-8"
    )
    data_path = DATA / f"{name}.json"
    data_path.write_text(
        json.dumps(results, indent=2, default=str), encoding="utf-8"
    )
    return path