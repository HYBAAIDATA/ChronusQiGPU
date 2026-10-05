"""Fail-closed architecture gate for the canonical PULVINI data boundary.

The doctrine enforced here is structural, not advisory:

* active PULVINI/data modules may not import mining, Stratum, share-submission,
  hash-pipeline, miner, or mining-runtime modules;
* active mining modules may not import the PULVINI data package, data bridges,
  geodesic tensor engine, fold pipeline, or any shared exact-math namespace that
  exposes PULVINI fold authority;
* mining may import explicitly named substrate-neutral Fibonacci/Binet/Cassini/
  Zeckendorf helpers from shared exact math;
* literal ``import_module``/``__import__`` dependency edges are inspected;
* production code may not use the historical ``PythagorasOrchestrator``
  compatibility facade, including aliased direct imports;
* absent owner-specified HYBA Data paths may not acquire active callers until
  they are intentionally restored.

This is intentionally a static dependency gate. Runtime importer-stack checks
are brittle in Python and can be bypassed by indirection; CI rejects forbidden
repository dependency edges before code is admitted. Importing the complete
shared exact-math namespace from mining is also rejected because that namespace
contains PULVINI fold symbols even if a particular caller currently uses only a
neutral helper.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]

PULVINI_DATA_MODULES = (
    "quantum_compute_substrate.pulvini",
    "tensor.pulvini_bridge",
    "python_backend.core_modules.geodesic_tensor_engine",
    "python_backend.core_modules.fold_pipeline",
)
SHARED_EXACT_MATH_MODULE = "python_backend.core_modules.math_folding"
PULVINI_FOLD_SYMBOLS = frozenset({"PulviniFold", "pulvini_fold"})
PYTHAGORAS_COMPAT_SYMBOL = "PythagorasOrchestrator"

MINING_MODULE_PARTS = frozenset(
    {
        "mining",
        "pythia_mining",
        "stratum_client",
        "hash_pipeline",
        "bitcoin_hasher",
        "production_miner",
        "headless_miner",
        "mining_runtime",
    }
)

HISTORICAL_ABSENT_MODULES = (
    "python_backend.phi_folding_engine",
    "python_backend.hyba_data.phi1_runtime",
    "python_backend.hyba_data.quantum_honest",
    "python_backend.hyba_data.sealed_claims",
)

PYTHAGORAS_COMPAT_DEFINITION_PATHS = {
    Path("quantum_compute_substrate/pulvini/orchestrator.py"),
    Path("quantum_compute_substrate/pulvini/__init__.py"),
}

# This compatibility module historically called itself a mining import even
# though "mining" is not in its path. Keep it explicitly on the mining side of
# the boundary so a future wildcard or PULVINI fold re-export fails the gate.
EXPLICIT_MINING_PATHS = {
    Path("chronus/mla1517/math_folding.py"),
}

SKIP_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "legacy",
    "node_modules",
    "reports",
}


@dataclass(frozen=True)
class BoundaryViolation:
    path: str
    rule: str
    detail: str

    def render(self) -> str:
        return f"{self.path}: {self.rule}: {self.detail}"


def _module_matches(module: str, prefixes: Iterable[str]) -> bool:
    return any(module == prefix or module.startswith(prefix + ".") for prefix in prefixes)


def _is_mining_import(module: str) -> bool:
    parts = {part.lower() for part in module.split(".") if part}
    return bool(parts & MINING_MODULE_PARTS)


def _is_test_path(relative: Path) -> bool:
    return "tests" in relative.parts or relative.name.startswith("test_")


def _is_mining_path(relative: Path) -> bool:
    if relative in EXPLICIT_MINING_PATHS:
        return True
    parts = {part.lower() for part in relative.parts}
    stem = relative.stem.lower()
    return (
        "mining" in parts
        or "pythia_mining" in parts
        or stem.endswith("miner")
        or "mining" in stem
        or stem in {"headless_miner", "production_miner"}
    )


def _iter_active_python(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        relative = path.relative_to(root)
        if any(part in SKIP_PARTS for part in relative.parts):
            continue
        yield path


def _literal_dynamic_imports(tree: ast.AST) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        target = node.func
        is_import = False
        if isinstance(target, ast.Name) and target.id == "__import__":
            is_import = True
        elif (
            isinstance(target, ast.Attribute)
            and target.attr == "import_module"
            and isinstance(target.value, ast.Name)
            and target.value.id == "importlib"
        ):
            is_import = True
        if is_import and isinstance(node.args[0], ast.Constant):
            value = node.args[0].value
            if isinstance(value, str):
                found.add(value)
    return found


def _imports_and_names(path: Path) -> tuple[set[str], set[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            # Record the imported targets, not the parent module itself. This
            # distinction lets mining import a named substrate-neutral helper
            # without treating it as a whole-namespace import that would also
            # expose PULVINI fold authority.
            imports.update(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    imports.update(_literal_dynamic_imports(tree))
    return imports, names


def _forbidden_pulvini_fold_import(imports: Iterable[str]) -> str | None:
    """Return the first mining import that exposes PULVINI fold authority.

    Direct symbol/wildcard imports are forbidden. Importing the whole shared
    exact-math module is also forbidden on the mining side: that namespace
    itself exposes ``PulviniFold`` and ``pulvini_fold``. Neutral exact helpers
    remain available through explicit named imports.
    """

    prefix = SHARED_EXACT_MATH_MODULE + "."
    for module in sorted(imports):
        if module == SHARED_EXACT_MATH_MODULE:
            return module
        if module == SHARED_EXACT_MATH_MODULE + ".*":
            return module
        if module.startswith(prefix):
            symbol = module[len(prefix) :].split(".", 1)[0]
            if symbol in PULVINI_FOLD_SYMBOLS:
                return module
    return None


def _uses_pythagoras_compatibility(imports: Iterable[str], names: Iterable[str]) -> bool:
    if PYTHAGORAS_COMPAT_SYMBOL in names:
        return True
    return any(
        module == PYTHAGORAS_COMPAT_SYMBOL
        or module.endswith("." + PYTHAGORAS_COMPAT_SYMBOL)
        for module in imports
    )


def check_repository(root: Path = REPO_ROOT) -> list[BoundaryViolation]:
    violations: list[BoundaryViolation] = []
    active_pulvini_paths = {
        *(root / "quantum_compute_substrate" / "pulvini").rglob("*.py"),
        root / "tensor" / "pulvini_bridge.py",
        root / "python_backend" / "core_modules" / "math_folding.py",
        root / "python_backend" / "core_modules" / "fold_pipeline.py",
        root / "python_backend" / "core_modules" / "geodesic_tensor_engine.py",
    }

    for path in _iter_active_python(root):
        relative = path.relative_to(root)
        try:
            imports, names = _imports_and_names(path)
        except (OSError, SyntaxError) as exc:
            violations.append(
                BoundaryViolation(
                    str(relative),
                    "parse-failure",
                    f"{type(exc).__name__}: {exc}",
                )
            )
            continue

        if path in active_pulvini_paths:
            for module in sorted(imports):
                if _is_mining_import(module):
                    violations.append(
                        BoundaryViolation(
                            str(relative),
                            "pulvini-imports-mining",
                            module,
                        )
                    )

        if _is_mining_path(relative) and not _is_test_path(relative):
            for module in sorted(imports):
                if _module_matches(module, PULVINI_DATA_MODULES):
                    violations.append(
                        BoundaryViolation(
                            str(relative),
                            "mining-imports-pulvini-data",
                            module,
                        )
                    )
            fold_import = _forbidden_pulvini_fold_import(imports)
            if fold_import is not None:
                violations.append(
                    BoundaryViolation(
                        str(relative),
                        "mining-imports-pulvini-fold-authority",
                        fold_import,
                    )
                )

        if not _is_test_path(relative):
            for module in sorted(imports):
                if _module_matches(module, HISTORICAL_ABSENT_MODULES):
                    violations.append(
                        BoundaryViolation(
                            str(relative),
                            "active-caller-of-absent-historical-path",
                            module,
                        )
                    )

        if (
            not _is_test_path(relative)
            and relative not in PYTHAGORAS_COMPAT_DEFINITION_PATHS
            and _uses_pythagoras_compatibility(imports, names)
        ):
            violations.append(
                BoundaryViolation(
                    str(relative),
                    "production-uses-pythagoras-compatibility",
                    "use PulviniDataOrchestrator under authority=pulvini.data",
                )
            )

    return violations


def main() -> int:
    violations = check_repository()
    if violations:
        print("PULVINI_DATA_BOUNDARY=FAIL")
        for violation in violations:
            print(violation.render())
        return 1
    print("PULVINI_DATA_BOUNDARY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
