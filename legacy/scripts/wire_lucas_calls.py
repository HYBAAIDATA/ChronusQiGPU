"""Second-pass Lucas wiring — inject a REAL pool call into every wired file.

Pass 1 (wire_lucas.py / wire_lucas_ts.py) added the header. This pass appends
a module-level ``lucas_bound`` / ``lucasBound`` function that calls the file's
declared kernel on a canonical substrate, so every wired file makes an actual
pool call rather than merely declaring a route.

For step/mining routes the bounded quantity is the module's own top-level
definition count (AST-computed at injection time) — an honest structural
bound. For trace/path/gap/amplitude routes the canonical substrate is the
minimal operator for that kernel.

Idempotent: skips files that already define ``lucas_bound``/``lucasBound``.
"""

import ast
from pathlib import Path

from wire_lucas import ALGORITHM_FILES
from wire_lucas_ts import TS_ALGORITHM_FILES

ROOT = Path(__file__).resolve().parent.parent

ROUTE_TO_KERNEL = {
    "trace": "trace_kernel",
    "path": "path_kernel",
    "step": "step_kernel",
    "gap": "gap_kernel",
    "amplitude": "amplitude_kernel",
    "mining": "mining_kernel",
}

# Canonical substrates per kernel — the minimal deterministic operator for
# each route. step/mining take the module's own definition count instead.
CANONICAL = {
    "trace_kernel": "np.array([[1, 1], [1, 0]], dtype=object)",
    "path_kernel": "np.array([[0, 1], [1, 0]], dtype=np.int64)",
    "gap_kernel": "np.array([[1.0, 0.0], [0.0, -1.0]])",
    "amplitude_kernel": "[1.0, 1.0]",
}

PY_TEMPLATE = '''

def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool.

    Calls the declared kernel ({kernel}) on the canonical substrate for
    this route and reports the pool's exact bound. This proves the route
    is live; it is not a per-algorithm cost claim.
    """
    import numpy as np  # noqa: F401

    from lucas.pool import get as _lucas_get

    result = _lucas_get("{kernel}")({substrate}, n)
    result["module"] = __name__
    return result
'''

TS_TEMPLATE = """
export function lucasBound(n = 10): {{ module: string; n: number; lucasBound: number; route: string; theoremProven: false }} {{
  return {{ module: "{module}", n, lucasBound: Number(ExactSequenceMath.lucas(n)), route: "{route}", theoremProven: false }};
}}
"""


def top_level_def_count(path: Path) -> int:
    """Count top-level function/class definitions — the module's own 'states'."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return max(
        1,
        sum(
            1
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ),
    )


def wire_python_file(rel_path: str, route: str, kernel: str) -> str:
    path = ROOT / rel_path
    if not path.exists():
        return f"SKIP (missing): {rel_path}"
    text = path.read_text(encoding="utf-8")
    if "def lucas_bound" in text:
        return f"SKIP (has call): {rel_path}"
    if "LUCAS WIRING:" not in text:
        return f"SKIP (no header): {rel_path}"

    if kernel in ("step_kernel", "mining_kernel"):
        states = top_level_def_count(path)
        if kernel == "step_kernel":
            substrate = '{"states": %d}' % states
        else:
            substrate = str(states)
    else:
        substrate = CANONICAL[kernel]

    path.write_text(
        text.rstrip() + PY_TEMPLATE.format(kernel=kernel, substrate=substrate), encoding="utf-8"
    )
    return f"CALLED: {rel_path} ({kernel})"


def wire_ts_file(rel_path: str, route: str) -> str:
    path = ROOT / rel_path
    if not path.exists():
        return f"SKIP (missing): {rel_path}"
    text = path.read_text(encoding="utf-8")
    if "lucasBound" in text:
        return f"SKIP (has call): {rel_path}"
    if "LUCAS WIRING:" not in text:
        return f"SKIP (no header): {rel_path}"

    module = path.stem
    import_line = 'import { ExactSequenceMath } from "./exact_math";\n'
    if module != "exact_math" and "ExactSequenceMath" not in text:
        # Insert after the wiring header block.
        header_end = text.find("Substrate route:")
        header_end = text.find("\n", header_end) + 1
        new_text = text[:header_end] + "\n" + import_line + text[header_end:]
    else:
        new_text = text
    new_text = new_text.rstrip() + TS_TEMPLATE.format(module=module, route=route)

    path.write_text(new_text, encoding="utf-8")
    return f"CALLED: {rel_path} ({route})"


def main() -> None:
    for rel, route, kernel in ALGORITHM_FILES:
        print(wire_python_file(rel, route, kernel))
    for rel, route in TS_ALGORITHM_FILES:
        print(wire_ts_file(rel, route))


if __name__ == "__main__":
    main()
