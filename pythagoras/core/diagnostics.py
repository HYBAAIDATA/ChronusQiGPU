"""
ENH-02 φ-Sensitivity Diagnostic
================================
Answers the March 2026 question for a stalled file: is it a search problem or a
metric problem?

It builds a neighbourhood of structurally distinct, behaviour-preserving variants of
the file (every registry operator across several seeds, plus generic rewrites that a
human refactor might make) and scores each with the metric under test.

    plateau_fraction  share of distinct variants scoring exactly the original φ
    improving         variants scoring higher than the original

Verdict:
    "metric_plateau"   ≥ 80 % of distinct variants score identically: the measurement is
                       flat here, so no search strategy can get a gradient signal
    "search_problem"   improving variants exist in the neighbourhood
    "local_optimum"    the neighbourhood moves the score, but only downward
"""
import ast
import argparse
import copy
import json
import pathlib
from typing import Any, Callable, Dict, List

from pythagoras.core.primitives import BEHAVIOUR_CHANGING, OPERATOR_REGISTRY


def _rewrite(code: str, fn: Callable[[ast.Module], bool]) -> List[str]:
    """Applies a rewrite at each applicable site independently; returns unparsed variants."""
    out = []
    try:
        base = ast.parse(code)
    except (SyntaxError, ValueError):
        return out
    site = 0
    while True:
        tree = copy.deepcopy(base)
        counter = {"seen": 0, "target": site, "done": False}
        if not fn(tree, counter):
            break
        ast.fix_missing_locations(tree)
        out.append(ast.unparse(tree))
        site += 1
        if site > 25:
            break
    return out


def _introduce_temp(tree, c) -> bool:
    for n in ast.walk(tree):
        for fld in ("body", "orelse"):
            body = getattr(n, fld, None)
            if not isinstance(body, list):
                continue
            for i, s in enumerate(body):
                if isinstance(s, ast.Return) and s.value is not None and not isinstance(s.value, ast.Name):
                    if c["seen"] == c["target"]:
                        tmp = ast.Name(id="_pythagoras_tmp", ctx=ast.Store())
                        body[i:i + 1] = [ast.Assign(targets=[tmp], value=s.value),
                                         ast.Return(value=ast.Name(id="_pythagoras_tmp", ctx=ast.Load()))]
                        return True
                    c["seen"] += 1
    return False


def _split_binop(tree, c) -> bool:
    for n in ast.walk(tree):
        body = getattr(n, "body", None)
        if not isinstance(body, list):
            continue
        for i, s in enumerate(body):
            if isinstance(s, ast.Assign) and isinstance(s.value, ast.BinOp) and isinstance(s.value.left, ast.BinOp):
                if c["seen"] == c["target"]:
                    tmp = f"_pythagoras_part{i}"
                    inner = s.value.left
                    s.value.left = ast.Name(id=tmp, ctx=ast.Load())
                    body.insert(i, ast.Assign(targets=[ast.Name(id=tmp, ctx=ast.Store())], value=inner))
                    return True
                c["seen"] += 1
    return False


def _swap_independent(tree, c) -> bool:
    for n in ast.walk(tree):
        body = getattr(n, "body", None)
        if not isinstance(body, list):
            continue
        for i in range(len(body) - 1):
            a, b = body[i], body[i + 1]
            if not (isinstance(a, ast.Assign) and isinstance(b, ast.Assign)):
                continue
            a_t = {x.id for x in ast.walk(a) if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store)}
            b_t = {x.id for x in ast.walk(b) if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store)}
            a_l = {x.id for x in ast.walk(a) if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load)}
            b_l = {x.id for x in ast.walk(b) if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load)}
            if a_t & (b_t | b_l) or b_t & a_l:
                continue
            if any(isinstance(x, ast.Call) for x in ast.walk(a)) or any(isinstance(x, ast.Call) for x in ast.walk(b)):
                continue  # calls may have ordering side effects
            if c["seen"] == c["target"]:
                body[i], body[i + 1] = b, a
                return True
            c["seen"] += 1
    return False


def _hoist_constant(tree, c) -> bool:
    consts = [n for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, float)]
    if c["target"] >= len(consts) or c["target"] > 0:
        return False
    val = consts[0].value
    for n in ast.walk(tree):
        for ch in ast.iter_child_nodes(n):
            for fld, v in ast.iter_fields(n):
                if v is ch and isinstance(ch, ast.Constant) and ch.value == val and isinstance(ch.value, float):
                    setattr(n, fld, ast.Name(id="_PYTHAGORAS_K", ctx=ast.Load()))
                elif isinstance(v, list):
                    for k, item in enumerate(v):
                        if item is ch and isinstance(ch, ast.Constant) and ch.value == val and isinstance(ch.value, float):
                            v[k] = ast.Name(id="_PYTHAGORAS_K", ctx=ast.Load())
    tree.body.insert(0, ast.Assign(targets=[ast.Name(id="_PYTHAGORAS_K", ctx=ast.Store())], value=ast.Constant(val)))
    return True


GENERIC_REWRITES = {
    "introduce_temporary": _introduce_temp,
    "split_binary_expression": _split_binop,
    "swap_independent_assignments": _swap_independent,
    "hoist_float_constant": _hoist_constant,
}


def neighbourhood(code: str, seeds=range(8)) -> Dict[str, str]:
    """Structurally distinct, behaviour-preserving variants keyed by provenance."""
    variants: Dict[str, str] = {}
    seen = set()
    try:
        seen.add(ast.dump(ast.parse(code)))
    except (SyntaxError, ValueError):
        return variants
    for name, op in OPERATOR_REGISTRY.items():
        if name in BEHAVIOUR_CHANGING:
            continue
        for sd in seeds:
            out, _ = op(code, sd)
            key = ast.dump(ast.parse(out))
            if key not in seen:
                seen.add(key)
                variants[f"{name}@{sd}"] = out
    for name, fn in GENERIC_REWRITES.items():
        for k, out in enumerate(_rewrite(code, fn)):
            key = ast.dump(ast.parse(out))
            if key not in seen:
                seen.add(key)
                variants[f"{name}#{k}"] = out
    return variants


def phi_sensitivity(code: str, score_fn: Callable[[str], float], seeds=range(8)) -> Dict[str, Any]:
    base = score_fn(code)
    variants = neighbourhood(code, seeds)
    scores = {k: score_fn(v) for k, v in variants.items()}
    same = [k for k, v in scores.items() if abs(v - base) < 1e-9]
    up = {k: v for k, v in scores.items() if v > base + 1e-9}
    n = len(scores)
    plateau = len(same) / n if n else 1.0
    if n == 0 or plateau >= 0.8:
        verdict = "metric_plateau"
    elif up:
        verdict = "search_problem"
    else:
        verdict = "local_optimum"
    return {
        "phi": base,
        "distinct_variants": n,
        "distinct_scores": len({round(v, 9) for v in scores.values()}),
        "plateau_fraction": round(plateau, 4),
        "improving_variants": sorted(up, key=up.get, reverse=True),
        "best_neighbour_phi": max(scores.values()) if scores else base,
        "verdict": verdict,
        "scores": scores,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Measure local φ sensitivity for a Python source file.")
    ap.add_argument("path")
    ap.add_argument("--metric", choices=("v12_1", "v12_0"), default="v12_1")
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args()
    code = pathlib.Path(args.path).read_text(encoding="utf-8")
    if args.metric == "v12_0":
        from pythagoras.experiments.reference_metrics import phi_v12_0
        score_fn = phi_v12_0
    else:
        from pythagoras.core.phi_metric import PhiResonanceCalculator
        score_fn = PhiResonanceCalculator().compute_phi
    result = phi_sensitivity(code, score_fn, range(args.seeds))
    if args.as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"{args.path}: {result['verdict']}")
        print(f"φ={result['phi']} variants={result['distinct_variants']} "
              f"plateau={result['plateau_fraction']:.1%} best={result['best_neighbour_phi']}")


if __name__ == "__main__":
    main()
