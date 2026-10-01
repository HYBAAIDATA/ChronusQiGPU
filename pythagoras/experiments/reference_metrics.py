"""
Reference metrics for replication experiments only (not used by the engine).

phi_v12_0: the φ formula exactly as shipped in v12.0, kept so results can be compared
across metric definitions.
"""
import ast
import math


def _depth(node, d=0):
    ch = list(ast.iter_child_nodes(node))
    return d if not ch else max(_depth(c, d + 1) for c in ch)


def phi_v12_0(code_str: str) -> float:
    try:
        tree = ast.parse(code_str)
    except Exception:
        return 0.1000
    depth = _depth(tree)
    node_count = sum(1 for _ in ast.walk(tree))
    ann = sum(1 for n in ast.walk(tree) if isinstance(n, ast.AnnAssign))
    funcs = sum(1 for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
    raw = 0.35 + 0.25 * (ann / max(node_count, 1)) + 0.20 * (1.0 / (1.0 + abs(depth - 8))) \
        + 0.10 * min(node_count / 50.0, 1.0) + 0.10 * min(funcs / 5.0, 1.0)
    g = (1.0 + math.sqrt(5)) / 2.0
    score = raw + 0.05 * (1.0 - abs((raw % g) - (1.0 / g)))
    return round(min(0.9900, max(0.1000, score)), 6)
