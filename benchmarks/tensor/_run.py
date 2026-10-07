"""Run one or all Kellogg tensor benchmarks and write TensorBenchmark artifacts.

Single benchmark: results/<id>.json and results/archive/<commit>/<id>.json.
Whole suite: results/latest.json and results/archive/<commit>.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional, Sequence

RESULTS = Path(__file__).resolve().parent / "results"


def main(benchmark_id: Optional[str] = None, argv: Optional[Sequence[str]] = None) -> int:
    from kellogg import benchmark

    args = list(sys.argv[1:] if argv is None else argv)
    quick = "--quick" in args
    if benchmark_id is None:
        ids = [a for a in args if not a.startswith("--")] or None
        return benchmark.main(([*ids] if ids else []) + (["--quick"] if quick else []) + ["--out", str(RESULTS)])
    art = benchmark.run(benchmark_id, quick=quick)
    RESULTS.mkdir(parents=True, exist_ok=True)
    text = json.dumps(art, indent=1, sort_keys=True, default=str)
    (RESULTS / f"{benchmark_id}.json").write_text(text, encoding="utf-8")
    archive = RESULTS / "archive" / art["commit"].replace("/", "_")
    archive.mkdir(parents=True, exist_ok=True)
    (archive / f"{benchmark_id}{'-quick' if quick else ''}.json").write_text(text, encoding="utf-8")
    state = {True: "PASS", False: "FAIL", None: "INCOMPLETE"}[art["passed"]]
    print(f"{benchmark_id}: {state} ({art['measurement']['wall_ns'] / 1e9:.2f}s) digest {art['digest'][:16]}")
    if art["error"]:
        print(art["error"])
    return 1 if art["passed"] is False else 0
