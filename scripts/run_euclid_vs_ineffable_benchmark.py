"""Execute the Elevated EUCLID vs. Ineffable Superlearner Benchmark Suite."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from euclid.cognition.research.ineffable_benchmark import (
    render_markdown_report,
    run_ineffable_vs_euclid_benchmark,
)

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


def main() -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    json_path = REPORTS / "euclid_vs_ineffable_benchmark.json"
    md_path = REPORTS / "EUCLID_VS_INEFFABLE_BENCHMARK_REPORT.md"

    print("=" * 80)
    print("STARTING ELEVATED EUCLID vs. INEFFABLE SUPERLEARNER BENCHMARK")
    print("=" * 80)

    start_time = time.time()
    # Execute benchmark across train/eval/held-out/adversarial/analogy regimes
    results = run_ineffable_vs_euclid_benchmark(
        seed=2026,
        train_per_family=3,
        evaluation_per_family=3,
        held_out_per_family=3,
        adversarial_per_tag=2,
        analogy_pairs=3,
    )
    elapsed = time.time() - start_time
    results["total_wall_clock_s"] = elapsed

    # Write machine-readable JSON
    json_path.write_text(json.dumps(results, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(f"\n[Artifact] Benchmark JSON written to {json_path}")

    # Render and write comprehensive markdown report
    markdown = render_markdown_report(results)
    md_path.write_text(markdown, encoding="utf-8")
    print(f"[Artifact] Benchmark Report written to {md_path}")
    print("=" * 80)
    print("BENCHMARK COMPLETED SUCCESSFULLY in {:.1f}s".format(elapsed))
    print("=" * 80)


if __name__ == "__main__":
    main()
