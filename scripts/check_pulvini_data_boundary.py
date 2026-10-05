"""Fail-closed architecture gate for the canonical PULVINI data boundary.

The doctrine enforced here is structural, not advisory:

* active PULVINI/data modules may not import mining, Stratum, share-submission,
  or hash-pipeline modules;
* active mining modules may not import the PULVINI data package or its exact
  data bridges, including through literal ``import_module``/``__import__``;
* production code may not import or reference the historical
  ``PythagorasOrchestrator`` compatibility facade;
* owner-specified historical HYBA Data paths that are absent on main may not
  acquire active callers until they are intentionally restored.

This is intentionally a static dependency gate. Runtime importer-stack checks
are brittle in Python and can be bypassed by import indirection; CI instead
rejects the dependency edge before code is admitted to the repository.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]

PULVINI_DATA_MODULES = (
    "quantum_compute_substrate.pulvini",
    "tensor.pulvini_bridge",
    "python_backend.core_modules.math_folding",
    "python_backend.core_modules.geodesic_tensor_engine",
)

MINING_IMPORT_FRAGMENTS = (
    "pythia_mining",
    "mining.stratum",
    "mining.hash_pipeline",
    "mining.production_miner",
    "mining.bitcoin_hasher",
    "stratum_client",
    "mining.submit",
)

HISTORICAL_ABSENT_MODULES = (
    "python_backend.phi_folding_engine",
    "python_backend.hyba_data.phi1_runtime",
    "python_backend.hyba_data.quantum_honest",
    "python_backend.hyba_data.sealed_claims",
)

# The definition/export sites are allowed to mention the historical facade.
PYTHAGORAS_COMPAT_DEFINITION_PATHS = {
    Path("quantum_compute_substrate/pulvini/orchestrator.py"),
    Path("quantum_compute_substrate/pulvini/__init__.py"),
}

# Historical, tests, generated reports, and vendored/build directories do not
# create active runtime dependency edges.
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


def _is_test_path(relative: Path) -> bool:
    return "tests" in relative.parts or relative.name.startswith("test_")


def _is_mining_path(relative: Path) -> bool:
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
            imports.add(node.module)
            imports.update(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    imports.update(_literal_dynamic_imports(tree))
    return imports, names


def check_repository(root: Path = REPO_ROOT) -> list[BoundaryViolation]:
    violations: list[BoundaryViolation] = []
    active_pulvini_paths = {
        *(root / "quantum_compute_substrate" / "pulvini").rglob("*.py"),
        root / "tensor" / "pulvini_bridge.py",
        root / "python_backend" / "core_modules" / "math_folding.py",
        root / "python_backend" / "core_modules" / "geodesic_tensor_engine.py",
    }

    for path in _iter_active_python(root):
        relative = path.relative_to(root)
        try:
            imports, names = _imports_and_names(path)
        except (OSError, SyntaxError) as exc:
            violations.append(
                BoundaryViolation(str(relative), "parse-failure", f"{type(exc).__name__}: {exc}")
            )
            continue

        if path in active_pulvini_paths:
            for module in sorted(imports):
                if any(fragment in module for fragment in MINING_IMPORT_FRAGMENTS):
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
            and "PythagorasOrchestrator" in names
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
