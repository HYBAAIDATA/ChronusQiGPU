"""Independent local ARC-AGI-1 scorer.

This is our local experimental scorer; official conformance requires external
verification by the benchmark administrators.

The scorer reads withheld test outputs and compares candidate predictions.
Two metrics are computed, both with denominator = ALL tasks in the split:
- arc_prize_score: average fraction of test inputs solved per task (max 2 attempts)
- strict_task_accuracy: fraction of tasks where all test inputs were matched exactly
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from euclid.benchmarks.arc_agi_1.output_validation import score_grid

ROOT = Path(__file__).resolve().parent
MAX_ATTEMPTS = 2


def score(submission: dict[str, Any], split_dir: Path) -> dict[str, Any]:
    paths = sorted(split_dir.glob("*.json"))
    if not paths:
        raise ValueError(f"no tasks in {split_dir}")
    per_task: dict[str, dict[str, Any]] = {}
    prize_total = 0.0
    strict_total = 0
    for path in paths:
        task_id = path.stem
        targets = [t["output"] for t in json.loads(path.read_bytes())["test"]]
        entries = submission.get(task_id)
        hits = []
        for i, target in enumerate(targets):
            hit = False
            if isinstance(entries, list) and i < len(entries) and isinstance(entries[i], dict):
                attempts = [entries[i].get(f"attempt_{a + 1}") for a in range(MAX_ATTEMPTS)]
                hit = any(score_grid(a, target).exact_match for a in attempts if a is not None)
            hits.append(hit)
        frac = sum(hits) / len(hits)
        prize_total += frac
        strict_total += int(all(hits))
        per_task[task_id] = {
            "test_hits": hits,
            "fraction": frac,
            "submitted": entries is not None,
        }
    n = len(paths)
    return {
        "scorer_identity": "local_scorer_v1",
        "tasks_in_split": n,
        "tasks_submitted": sum(1 for v in per_task.values() if v["submitted"]),
        "arc_prize_score": prize_total / n,
        "arc_prize_tasks_equivalent": prize_total,
        "strict_task_accuracy": strict_total / n,
        "strict_tasks_solved": strict_total,
        "solved_task_ids": sorted(k for k, v in per_task.items() if all(v["test_hits"])),
        "denominator": "all tasks in split",
        "per_task": per_task,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local evaluation scorer for ARC-AGI-1")
    parser.add_argument("--split", choices=("training", "evaluation"), required=True)
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    result = score(json.loads(args.submission.read_text()), ROOT / "data" / args.split)
    out = args.out or args.submission.with_name("score.json")
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "per_task"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
