"""Held-out validation of φ changes against independent code measures.

Expected directions are declared before execution:
- Δφ versus Δ maintainability index: positive.
- Δφ versus improvement in cyclomatic complexity: positive.
- Δφ versus reduction in mypy errors: positive.
- Δφ versus Δ AST node count: control; no quality interpretation.

The held-out corpus excludes the ``stdlib4`` modules used by the A/B harness.
No metric weights or search parameters are tuned from these results.

Reproduce:
    python -m pythagoras.experiments.phi_validation \
      --seeds 3 --generations 4 --bootstrap 2000 \
      --out-json pythagoras/experiments/phi_validation_v12_2.json \
      --out-md pythagoras/experiments/PHI_VALIDATION_v12_2.md
"""

import argparse
import ast
import json
import statistics
import subprocess
import sys
import sysconfig
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np
from radon.complexity import cc_visit
from radon.metrics import mi_visit

from pythagoras.engine.v6_5_manifold_escape import V65ManifoldEscapeEngine


HELD_OUT = ("bisect.py", "heapq.py", "fractions.py", "tokenize.py")
EXCLUDED = {"colorsys.py", "fnmatch.py", "graphlib.py", "textwrap.py"}


def _metrics(source: str) -> Dict[str, float]:
    complexity = float(sum(block.complexity for block in cc_visit(source)))
    maintainability = float(mi_visit(source, multi=True))
    nodes = float(sum(1 for _ in ast.walk(ast.parse(source))))
    with tempfile.TemporaryDirectory(prefix="phi_validation_") as td:
        path = Path(td) / "candidate.py"
        path.write_text(source, encoding="utf-8")
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "mypy",
                "--no-incremental",
                "--ignore-missing-imports",
                "--follow-imports=skip",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    errors = float(sum(": error:" in line for line in proc.stdout.splitlines()))
    return {
        "cyclomatic_complexity": complexity,
        "maintainability_index": maintainability,
        "mypy_errors": errors,
        "ast_nodes": nodes,
    }


def _rho_ci(
    x: Iterable[float],
    y: Iterable[float],
    bootstrap: int,
    rng: np.random.Generator,
) -> Dict[str, Any]:
    xa, ya = np.asarray(list(x), dtype=float), np.asarray(list(y), dtype=float)
    if len(xa) < 3 or np.all(xa == xa[0]) or np.all(ya == ya[0]):
        return {"rho": None, "ci95": [None, None], "n": int(len(xa))}
    rho = _spearman(xa, ya)
    samples = []
    for _ in range(bootstrap):
        idx = rng.integers(0, len(xa), len(xa))
        if np.all(xa[idx] == xa[idx][0]) or np.all(ya[idx] == ya[idx][0]):
            continue
        samples.append(_spearman(xa[idx], ya[idx]))
    ci = np.percentile(samples, [2.5, 97.5]).tolist() if samples else [None, None]
    return {"rho": rho, "ci95": ci, "n": int(len(xa))}


def _spearman(x: np.ndarray, y: np.ndarray) -> float:
    def ranks(values: np.ndarray) -> np.ndarray:
        order = np.argsort(values, kind="mergesort")
        ranked = np.empty(len(values), dtype=float)
        start = 0
        while start < len(values):
            end = start + 1
            while end < len(values) and values[order[end]] == values[order[start]]:
                end += 1
            ranked[order[start:end]] = (start + end - 1) / 2.0 + 1.0
            start = end
        return ranked

    return float(np.corrcoef(ranks(x), ranks(y))[0, 1])


def run_validation(
    modules: Tuple[str, ...] = HELD_OUT,
    seeds: int = 3,
    generations: int = 4,
    bootstrap: int = 2000,
) -> Dict[str, Any]:
    if EXCLUDED.intersection(modules):
        raise ValueError("validation corpus overlaps stdlib4 tuning corpus")
    stdlib = Path(sysconfig.get_paths()["stdlib"])
    rows: List[Dict[str, Any]] = []
    annotation_steps: List[float] = []
    for module in modules:
        source = (stdlib / module).read_text(encoding="utf-8")
        baseline = _metrics(source)
        for seed in range(seeds):
            engine = V65ManifoldEscapeEngine(seed=seed)
            result = engine.run_optimization(module, source, generations)
            final = _metrics(result["final_code"])
            operators = [s["winning_operator"] for s in result["accepted_steps"]]
            annotation_steps.extend(
                s["delta_phi"]
                for s in result["accepted_steps"]
                if s["winning_operator"] == "ADD:AnnAssign"
            )
            rows.append(
                {
                    "module": module,
                    "seed": seed,
                    "delta_phi": result["total_delta_phi"],
                    "delta_maintainability_index": (
                        final["maintainability_index"]
                        - baseline["maintainability_index"]
                    ),
                    "complexity_improvement": (
                        baseline["cyclomatic_complexity"]
                        - final["cyclomatic_complexity"]
                    ),
                    "mypy_error_reduction": (
                        baseline["mypy_errors"] - final["mypy_errors"]
                    ),
                    "delta_ast_nodes": final["ast_nodes"] - baseline["ast_nodes"],
                    "operators": operators,
                    "contains_annassign": "ADD:AnnAssign" in operators,
                }
            )

    rng = np.random.default_rng(20261001)
    outcomes = (
        "delta_maintainability_index",
        "complexity_improvement",
        "mypy_error_reduction",
        "delta_ast_nodes",
    )

    def correlations(subset: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            outcome: _rho_ci(
                (row["delta_phi"] for row in subset),
                (row[outcome] for row in subset),
                bootstrap,
                rng,
            )
            for outcome in outcomes
        }

    annotation_rows = [row for row in rows if row["contains_annassign"]]
    return {
        "protocol": {
            "modules": list(modules),
            "excluded_tuning_modules": sorted(EXCLUDED),
            "seeds": seeds,
            "generations": generations,
            "bootstrap_samples": bootstrap,
            "expected_directions": {
                "delta_maintainability_index": "positive",
                "complexity_improvement": "positive",
                "mypy_error_reduction": "positive",
                "delta_ast_nodes": "control_only",
            },
        },
        "rows": rows,
        "correlations_all": correlations(rows),
        "correlations_annassign_variants": correlations(annotation_rows),
        "annassign_steps": {
            "count": len(annotation_steps),
            "mean_delta_phi": (
                statistics.mean(annotation_steps) if annotation_steps else None
            ),
            "min_delta_phi": min(annotation_steps) if annotation_steps else None,
            "max_delta_phi": max(annotation_steps) if annotation_steps else None,
        },
    }


def _fmt(value: Any) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def render_markdown(result: Dict[str, Any], command: str) -> str:
    lines = [
        "# φ validation — PYTHAGORAS v12.2",
        "",
        f"Reproduce: `{command}`",
        "",
        "Expected before running: positive association with maintainability change, "
        "complexity improvement, and mypy-error reduction. AST-node change is a "
        "control and is not treated as quality evidence.",
        "",
        "| Outcome | All ρ (95% CI) | ADD:AnnAssign variants ρ (95% CI) |",
        "|---|---:|---:|",
    ]
    for key, label in (
        ("delta_maintainability_index", "Δ maintainability index"),
        ("complexity_improvement", "Cyclomatic-complexity improvement"),
        ("mypy_error_reduction", "Mypy-error reduction"),
        ("delta_ast_nodes", "Δ AST nodes (control)"),
    ):
        all_c = result["correlations_all"][key]
        ann_c = result["correlations_annassign_variants"][key]
        lines.append(
            f"| {label} | {_fmt(all_c['rho'])} "
            f"({_fmt(all_c['ci95'][0])}, {_fmt(all_c['ci95'][1])}) | "
            f"{_fmt(ann_c['rho'])} "
            f"({_fmt(ann_c['ci95'][0])}, {_fmt(ann_c['ci95'][1])}) |"
        )
    ann = result["annassign_steps"]
    lines += [
        "",
        "## ADD:AnnAssign",
        "",
        f"- Steps: {ann['count']}",
        f"- Mean Δφ: {_fmt(ann['mean_delta_phi'])}",
        f"- Range: {_fmt(ann['min_delta_phi'])} to {_fmt(ann['max_delta_phi'])}",
        "",
        "Interpret correlations against the committed output; do not infer quality "
        "validation when the confidence interval crosses zero or when Δφ tracks the "
        "AST-node control more strongly than independent measures.",
        "",
        "## Result",
        "",
        "This run does **not** validate the expected quality directions. Overall Δφ "
        "is negatively associated with maintainability-index change, cyclomatic "
        "complexity shows no monotonic association, and mypy error count does not "
        "vary. In the ADD:AnnAssign subset, complexity improvement is positively "
        "associated with Δφ, but maintainability remains inconclusive and the AST-node "
        "control is also strong. The annotation-driven φ gain therefore cannot yet be "
        "separated from structural-size effects or treated as independent code-quality "
        "evidence.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modules", nargs="+", default=list(HELD_OUT))
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--generations", type=int, default=4)
    ap.add_argument("--bootstrap", type=int, default=2000)
    ap.add_argument("--out-json", default=None)
    ap.add_argument("--out-md", default=None)
    args = ap.parse_args()
    result = run_validation(
        tuple(args.modules),
        args.seeds,
        args.generations,
        args.bootstrap,
    )
    command = (
        "python -m pythagoras.experiments.phi_validation "
        f"--seeds {args.seeds} --generations {args.generations} "
        f"--bootstrap {args.bootstrap}"
    )
    if args.out_json:
        Path(args.out_json).write_text(json.dumps(result, indent=2), encoding="utf-8")
    markdown = render_markdown(result, command)
    if args.out_md:
        Path(args.out_md).write_text(markdown, encoding="utf-8")
    print(markdown)


if __name__ == "__main__":
    main()