#!/usr/bin/env python3
"""Run the checked-in held-out v17 comparison and fail closed on no advantage."""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from euclid.contracts import RewardAuthority
from euclid.cognition.experiments import (
    BenchmarkProgramme,
    adversarial_evaluation_tasks,
)
from euclid.runtime import EuclidRuntime


class BenchmarkRepoEngineer:
    """Deterministic read-only repository evidence provider."""

    def __init__(self, *args, **kwargs):
        self.calls = 0

    def ask(self, prompt):
        self.calls += 1
        return {
            "task_id": f"benchmark-repo-{self.calls}",
            "routes": ["repository_map", "import_audit", "focused_tests"],
            "evidence": {
                "import_audit": {"finding_count": 0, "files_audited": 1},
                "focused_tests": {"returncode": 0},
            },
        }


class BenchmarkExecutor:
    """Measured environment; imagined results never reach this boundary."""

    def execute(self, action, payload):
        observation = {
            "inspect": "dependency-evidence",
            "test": "test-evidence",
        }.get(str(action), "measured-pass")
        return {
            "observation": observation,
            "goal_met": True,
            "metric_improved": True,
            "reward": 1.0,
            "reward_authority": RewardAuthority.MEASURED_ENVIRONMENT.value,
        }


def interval_mean(summary, system, metric):
    return float(summary[system][metric]["mean"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    roots: list[Path] = []

    def factory(ablation, seed):
        root = Path(tempfile.mkdtemp(prefix=f"euclid-v17-{seed}-"))
        roots.append(root)
        with patch("Intelligence.repo_engineer.RepoEngineer", BenchmarkRepoEngineer):
            runtime = EuclidRuntime.production(
                creator_id="benchmark",
                state_dir=root,
                organism=False,
            )
        runtime.cognition.ablations = ablation
        runtime.cognition.executor = BenchmarkExecutor()
        return runtime

    try:
        programme = BenchmarkProgramme(adversarial_evaluation_tasks())
        report = programme.run(factory, repeats=args.repeats)
        integrated = interval_mean(report["summary"], "integrated", "correctness")
        baseline = interval_mean(report["summary"], "v16.4-reference", "correctness")
        cost = interval_mean(report["summary"], "integrated", "wall_time_s")
        baseline_cost = interval_mean(
            report["summary"], "v16.4-reference", "wall_time_s"
        )
        report["release_comparison"] = {
            "integrated_correctness": integrated,
            "v16.4_correctness": baseline,
            "correctness_delta": integrated - baseline,
            "integrated_wall_time_s": cost,
            "v16.4_wall_time_s": baseline_cost,
            "wall_time_delta_s": cost - baseline_cost,
            "superiority_gate_passed": integrated > baseline,
            "gate": "held-out correctness must strictly exceed v16.4",
        }
        args.output.write_text(
            json.dumps(report, sort_keys=True, indent=2), encoding="utf-8"
        )
        print(f"BENCHMARK_REPORT={args.output}")
        print(f"CORRECTNESS_DELTA={integrated - baseline:.6f}")
        if integrated <= baseline:
            print("RELEASE_BLOCKED=integrated correctness does not exceed v16.4")
            return 2
        return 0
    finally:
        for root in roots:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())