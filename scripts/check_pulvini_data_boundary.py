"""Fail-closed architecture gate for the canonical PULVINI data boundary.

The doctrine enforced here is structural, not advisory:

* active PULVINI/data modules may not import mining, Stratum, share-submission,
  hash-pipeline, miner, or mining-runtime modules;
* active mining modules may not import, directly or transitively, the PULVINI
  data package, data bridges, geodesic tensor engine, fold pipeline, or any
  shared exact-math edge that exposes PULVINI fold authority;
* mining may import explicitly named substrate-neutral Fibonacci/Binet/Cassini/
  Zeckendorf helpers from shared exact math;
* literal ``import_module``/``__import__`` dependency edges are inspected,
  including ordinary import aliases;
* production code may not use the historical ``PythagorasOrchestrator``
  compatibility facade, including aliased direct imports;
* absent owner-specified HYBA Data paths may not acquire active callers until
  they are intentionally restored.

The transitive check resolves repository-local imports (including relative
imports) into an internal module graph. A mining module therefore cannot hide
a PULVINI dependency behind an apparently neutral helper. Symbol-sensitive
handling of ``math_folding`` preserves the approved neutral exact algebra:
explicit Fibonacci/Binet/Cassini/Zeckendorf imports do not become PULVINI
authority, while ``PulviniFold`` / ``pulvini_fold`` or the complete mixed
namespace do.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

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

# Explicitly classify production mining surfaces whose path/name does not carry
# the generic "mining" token. These files are part of the canonical production
# pool/coordinator route and must receive the same PULVINI boundary checks as
# chronus.mla1517.mining.* modules.
EXPLICIT_MINING_PATHS = {
    Path("chronus/mla1517/math_folding.py"),
    Path("chronus/mla1517_platform/python/coordinator.py"),
    Path("chronus/mla1517_platform/python/manifold_pool_coordinator.py"),
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


def _module_name(root: Path, path: Path) -> tuple[str, bool]:
    relative = path.relative_to(root)
    if relative.name == "__init__.py":
        return ".".join(relative.parent.parts), True
    return ".".join(relative.with_suffix("").parts), False


def _resolve_relative_module(
    module: str | None,
    *,
    level: int,
    current_module: str,
    is_package: bool,
) -> str:
    if level <= 0:
        return module or ""
    package = current_module if is_package else current_module.rpartition(".")[0]
    parts = [part for part in package.split(".") if part]
    ascend = max(0, level - 1)
    if ascend > len(parts):
        return module or ""
    if ascend:
        parts = parts[:-ascend]
    if module:
        parts.extend(part for part in module.split(".") if part)
    return ".".join(parts)


def _literal_dynamic_imports(tree: ast.AST) -> set[str]:
    """Return literal dynamic-import targets for normal importlib spellings."""
    importlib_module_aliases = {"importlib"}
    import_module_aliases: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "importlib":
                    importlib_module_aliases.add(alias.asname or "importlib")
        elif isinstance(node, ast.ImportFrom) and node.module == "importlib":
            for alias in node.names:
                if alias.name == "import_module":
                    import_module_aliases.add(alias.asname or "import_module")

    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        target = node.func
        is_import = False
        if isinstance(target, ast.Name):
            is_import = target.id == "__import__" or target.id in import_module_aliases
        elif (
            isinstance(target, ast.Attribute)
            and target.attr == "import_module"
            and isinstance(target.value, ast.Name)
            and target.value.id in importlib_module_aliases
        ):
            is_import = True
        if is_import and isinstance(node.args[0], ast.Constant):
            value = node.args[0].value
            if isinstance(value, str):
                found.add(value)
    return found


def _imports_and_names(
    path: Path,
    *,
    current_module: str = "",
    is_package: bool = False,
) -> tuple[set[str], set[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            parent = _resolve_relative_module(
                node.module,
                level=node.level,
                current_module=current_module,
                is_package=is_package,
            )
            if parent:
                imports.update(f"{parent}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    imports.update(_literal_dynamic_imports(tree))
    return imports, names


def _forbidden_pulvini_fold_import(imports: Iterable[str]) -> str | None:
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


def _resolve_internal_import(imported: str, modules: set[str]) -> str | None:
    candidate = imported
    while candidate:
        if candidate in modules:
            return candidate
        candidate, dot, _tail = candidate.rpartition(".")
        if not dot:
            break
    return None


def _direct_pulvini_authority(imports: Iterable[str]) -> str | None:
    for module in sorted(imports):
        if _module_matches(module, PULVINI_DATA_MODULES):
            return module
    return _forbidden_pulvini_fold_import(imports)


def _transitive_pulvini_violations(
    root: Path,
    parsed: Mapping[str, tuple[Path, set[str]]],
) -> list[BoundaryViolation]:
    modules = set(parsed)
    dependencies: dict[str, set[str]] = {module: set() for module in modules}
    direct_authority: dict[str, str] = {}

    for module, (_path, imports) in parsed.items():
        authority = _direct_pulvini_authority(imports)
        if authority is not None:
            direct_authority[module] = authority
        for imported in imports:
            resolved = _resolve_internal_import(imported, modules)
            if resolved is not None and resolved != module:
                dependencies[module].add(resolved)

    memo: dict[str, tuple[str, ...] | None] = {}

    def path_to_authority(module: str, visiting: set[str]) -> tuple[str, ...] | None:
        if module in memo:
            return memo[module]
        if module in direct_authority:
            result = (module, direct_authority[module])
            memo[module] = result
            return result
        if module in visiting:
            return None
        visiting.add(module)
        try:
            for dependency in sorted(dependencies[module]):
                downstream = path_to_authority(dependency, visiting)
                if downstream is not None:
                    result = (module, *downstream)
                    memo[module] = result
                    return result
        finally:
            visiting.remove(module)
        memo[module] = None
        return None

    violations: list[BoundaryViolation] = []
    for module, (path, _imports) in parsed.items():
        relative = path.relative_to(root)
        if _is_test_path(relative) or not _is_mining_path(relative):
            continue
        route = path_to_authority(module, set())
        if route is None:
            continue
        # Direct edges already receive their more specific violation above.
        if module in direct_authority:
            continue
        violations.append(
            BoundaryViolation(
                str(relative),
                "mining-transitively-reaches-pulvini-data",
                " -> ".join(route),
            )
        )
    return violations


def check_repository(root: Path = REPO_ROOT) -> list[BoundaryViolation]:
    violations: list[BoundaryViolation] = []
    active_pulvini_paths = {
        *(root / "quantum_compute_substrate" / "pulvini").rglob("*.py"),
        root / "tensor" / "pulvini_bridge.py",
        root / "python_backend" / "core_modules" / "math_folding.py",
        root / "python_backend" / "core_modules" / "fold_pipeline.py",
        root / "python_backend" / "core_modules" / "geodesic_tensor_engine.py",
    }
    parsed: dict[str, tuple[Path, set[str]]] = {}

    for path in _iter_active_python(root):
        relative = path.relative_to(root)
        module_name, is_package = _module_name(root, path)
        try:
            imports, names = _imports_and_names(
                path,
                current_module=module_name,
                is_package=is_package,
            )
        except (OSError, SyntaxError) as exc:
            violations.append(
                BoundaryViolation(
                    str(relative),
                    "parse-failure",
                    f"{type(exc).__name__}: {exc}",
                )
            )
            continue
        parsed[module_name] = (path, imports)

        if path in active_pulvini_paths:
            for module in sorted(imports):
                if _is_mining_import(module):
                    violations.append(
                        BoundaryViolation(str(relative), "pulvini-imports-mining", module)
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

    violations.extend(_transitive_pulvini_violations(root, parsed))
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
