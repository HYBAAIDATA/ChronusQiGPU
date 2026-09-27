#!/usr/bin/env python3
"""Static import-direction checks for the canonical mining boundary."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "python"


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    return modules


def main() -> int:
    checks: list[tuple[str, bool]] = []
    controller = imported_modules(PYTHON / "mla1517/mining/intelligence_controller.py")
    solver = imported_modules(PYTHON / "mla1517/mining/solver.py")
    verifier = imported_modules(PYTHON / "mla1517/mining/verification.py")
    lane = imported_modules(PYTHON / "mla1517/mining/lane.py")

    checks.append(("lane uses only standard-library imports", not (lane & {"mla1517", "toe", "Intelligence"})))
    checks.append(("solver has no TOE/controller dependency", not (solver & {"toe_context", "toe_adapter", "intelligence_controller", "Intelligence"})))
    checks.append(("verifier has no scheduler/controller dependency", not (verifier & {"lane", "chooser", "intelligence_controller", "Intelligence"})))
    checks.append(("controller has no solver/verifier dependency", not (controller & {"solver", "verification", "pow", "opencl_driver"})))

    failed = [name for name, passed in checks if not passed]
    for name, passed in checks:
        print(("PASS" if passed else "FAIL") + " — " + name)
    if failed:
        raise SystemExit("import-use audit failed: " + ", ".join(failed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
