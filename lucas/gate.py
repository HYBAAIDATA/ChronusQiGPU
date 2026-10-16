"""Purity gate — AST checks that algorithm files do not import siblings.

Allowed shared imports:
  - built-ins
  - standard library
  - numpy
  - lucas.*
  - non-algorithm substrate modules declared by the project (e.g. quantum_tensor)

Algorithm-to-algorithm imports are rejected.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable


def _extract_imports(source: str) -> list[str]:
    """Return top-level module names imported by source.

    Relative imports (``from .x import y``) are intra-package by
    definition and are not reported — they can never reach a sibling
    top-level package.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            if node.module:
                modules.add(node.module.split(".")[0])
    return sorted(modules)


def purity_check(
    file_path: str | Path,
    allowed_modules: Iterable[str] | None = None,
) -> dict[str, object]:
    """Check one file for forbidden sibling algorithm imports.

    Bare ``import x`` / ``from x import y`` where ``x.py`` sits in the
    same package directory is resolved to ``<pkg>.x`` — files that lift
    their own directory onto sys.path cannot disguise an import's real
    target from the gate.
    """
    path = Path(file_path)
    source = path.read_text(encoding="utf-8")
    imports = _extract_imports(source)
    pkg = path.parent.name
    resolved = [
        f"{pkg}.{m}" if "." not in m and (path.parent / f"{m}.py").exists() else m for m in imports
    ]
    allowed = set(allowed_modules or [])
    forbidden = [m for m in resolved if m and m not in allowed and m.split(".")[0] not in allowed]
    return {
        "file": str(path),
        "imports": resolved,
        "forbidden": forbidden,
        "passed": not forbidden,
    }


def verify_directory(
    directory: str | Path,
    allowed_modules: Iterable[str],
    glob: str = "*.py",
) -> list[dict[str, object]]:
    """Run purity gate on every file matching glob under directory."""
    results = []
    for file in Path(directory).rglob(glob):
        results.append(purity_check(file, allowed_modules))
    return results


_DEFAULT_ALLOWED_EXTRA = {"lucas", "turing_core", "numpy"}


def assert_pure(
    directory: str | Path,
    extra_allowed: Iterable[str] | None = None,
) -> list[dict[str, object]]:
    """Assert every .py file under directory imports only allowed modules.

    Allowed by default: stdlib, numpy, lucas, turing_core. Any other
    top-level import — including sibling subsystem packages — fails the
    gate. Returns the per-file results on success; raises AssertionError
    listing every violation on failure.
    """
    import sys

    allowed = set(sys.stdlib_module_names) | _DEFAULT_ALLOWED_EXTRA | set(extra_allowed or ())
    results = verify_directory(directory, allowed)
    failures = [r for r in results if not r["passed"]]
    if failures:
        detail = "; ".join(f"{r['file']}: {r['forbidden']}" for r in failures)
        raise AssertionError(f"Purity gate failed for {directory}: {detail}")
    return results
