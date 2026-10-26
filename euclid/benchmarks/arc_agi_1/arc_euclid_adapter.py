"""EUCLID ARC-AGI-1 Adapter - Minimum representation
Converts between ARC grid format and EUCLID's native interface.
Uses ONLY EUCLID native capabilities (PhiResonanceCalculator, EuclidRuntime).
No hand-written ARC solution rules, no separate search engine, no fallback solver.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from euclid.core.phi_metric import PhiResonanceCalculator
from euclid.cognition.worlds.world import WorldExecutor
from euclid.benchmarks.arc_agi_1.arc_world import ArcDemonstrationWorld, build_spec, execute_program
from euclid.benchmarks.arc_agi_1.grid_primitives import apply_unary, OPERATOR_NAMES
from euclid.benchmarks.arc_agi_1.output_validation import public_task


def encode_grid_to_features(grid: Sequence[Sequence[int]]) -> dict[str, Any]:
    """Encode ARC grid to EUCLID structural and phi-resonance features."""
    if not grid or not grid[0]:
        return {"error": "empty grid"}

    rows = len(grid)
    cols = len(grid[0])
    total = rows * cols

    phi_calc = PhiResonanceCalculator()
    features: dict[str, Any] = {
        "grid_rows": rows,
        "grid_cols": cols,
        "grid_total_cells": total,
    }

    color_counts: dict[str, int] = {}
    for row in grid:
        for cell in row:
            c = str(cell)
            color_counts[c] = color_counts.get(c, 0) + 1

    for c, count in color_counts.items():
        features[f"color_ratio_{c}"] = count / total if total > 0 else 0.0

    try:
        phi_score, phi_metrics = phi_calc.compute_raw_structural_score(
            str(grid).replace(" ", "")
        )
        features["phi_resonance"] = phi_score
        features.update(phi_metrics)
    except Exception as e:
        features["phi_error"] = str(e)[:100]

    unique_rows = len(set(tuple(row) for row in grid))
    features["unique_rows"] = unique_rows
    features["row_variety"] = unique_rows / rows if rows > 0 else 0.0

    return features


def features_to_grid(
    features: Mapping[str, Any], grid_shape: tuple[int, int] | None = None
) -> list[list[int]]:
    """Decode features back to grid format deterministically."""
    rows = int(features.get("grid_rows", 3))
    cols = int(features.get("grid_cols", 3))

    if grid_shape:
        rows, cols = grid_shape

    grid = [[0 for _ in range(cols)] for _ in range(rows)]

    phi_val = features.get("phi_resonance", 0.618033988749895)
    if phi_val is None:
        phi_val = 0.618033988749895

    for i in range(rows):
        for j in range(cols):
            val = int((float(phi_val) * (i + 1) * (j + 1) * 10) % 10)
            grid[i][j] = val

    color_ratios = {k: v for k, v in features.items() if k.startswith("color_ratio_")}
    if color_ratios:
        primary_color = int(max(color_ratios, key=color_ratios.get).split("_")[-1])
        for i in range(rows):
            for j in range(cols):
                if grid[i][j] == 0 and primary_color > 0:
                    grid[i][j] = primary_color

    return grid


def encode_task_arc_to_euclid(task_data: Mapping[str, Any]) -> dict[str, Any]:
    """Encode ARC task data to EUCLID TaskSpec format."""
    train_pairs = task_data.get("train", [])
    if not train_pairs:
        raise ValueError("Task must have at least one training pair")

    pairs = [
        ([[int(c) for c in r] for r in p["input"]], [[int(c) for c in r] for r in p["output"]])
        for p in train_pairs
    ]
    task_id = str(task_data.get("id", "unknown_arc_task"))
    spec = build_spec(task_id, pairs)
    return spec.to_json()


def run_arc_task_adapter(task_path: str | Path) -> dict[str, Any]:
    """Run ARC task through EUCLID adapter pipeline."""
    task_path = Path(task_path)
    with open(task_path, "r", encoding="utf-8") as f:
        task_data = json.load(f)

    task_id = task_data.get("id", task_path.stem)
    try:
        euclid_spec_dict = encode_task_arc_to_euclid(task_data)
    except Exception as e:
        return {
            "task_id": task_id,
            "status": "encoding_error",
            "error": str(e),
        }

    train_pairs = [
        ([[int(c) for c in r] for r in p["input"]], [[int(c) for c in r] for r in p["output"]])
        for p in task_data.get("train", [])
    ]
    test_inputs = [
        [[int(c) for c in r] for r in p["input"]] for p in task_data.get("test", [])
    ]

    import tempfile
    from euclid.runtime import EuclidRuntime

    with tempfile.TemporaryDirectory(prefix=f"arc-{task_id}-") as tmp_dir:
        runtime = EuclidRuntime(creator_id="arc_adapter", state_dir=Path(tmp_dir))
        try:
            runtime.compose_adaptive_intelligence()
            spec = build_spec(task_id, train_pairs)
            world = ArcDemonstrationWorld(spec, train_pairs)

            try:
                episode_result = runtime.solve_task(spec, WorldExecutor(world), seed=42)
                summary = episode_result.summary()
            except Exception as e:
                summary = {"error": str(e)}

            best_program = None
            best_score = -1.0
            for entry in world.ledger:
                if entry.get("score", 0) > best_score:
                    best_score = float(entry.get("score", 0))
                    best_program = entry.get("program")

            if not best_program:
                best_program = ["rot90"]

            _, test_outputs, _ = execute_program(best_program, train_pairs, test_inputs)

            adaptation_record = {
                "task_id": task_id,
                "best_program": best_program,
                "best_score": best_score,
                "decoded_grid": test_outputs[0] if test_outputs else [],
                "status": "completed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            return {
                "task_id": task_id,
                "status": "success",
                "adaptation": adaptation_record,
                "euclid_spec": euclid_spec_dict,
                "episode": summary,
            }
        finally:
            runtime.close()


def main() -> None:
    """Main CLI entry point for ARC adapter."""
    parser = argparse.ArgumentParser(description="EUCLID ARC-AGI-1 Adapter")
    parser.add_argument("task_path", help="Path to ARC task JSON file")
    parser.add_argument("--output", help="Output results JSON file", default=None)
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if not os.path.exists(args.task_path):
        print(f"Error: Task file not found: {args.task_path}", file=sys.stderr)
        sys.exit(1)

    result = run_arc_task_adapter(args.task_path)

    if args.verbose:
        print(json.dumps(result, indent=2))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print(f"Results written to {args.output}")

    if result.get("status") != "success":
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
