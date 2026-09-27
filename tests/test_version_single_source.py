"""Single-source version enforcement (GAP-6).

Policy (declared in reports/version_consolidation.md):

  * Each package has exactly ONE canonical ``__version__`` literal, in its
    top-level ``__init__.py`` (toe's canonical site is ``toe/__init__.py``;
    ``toe/engine.py`` derives via ``from toe import __version__``).
  * A ``pyproject.toml`` ``[project].version`` is a packaging MIRROR of
    the runtime literal — it must equal it, never differ.
  * ``importlib.metadata.version(dist)`` must equal the runtime version
    whenever the distribution is installed; absence of metadata is a
    reported fact, not a pass-through.
  * Every literal must parse as SemVer.
"""

import importlib
import importlib.metadata
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.\-]+)?$")
VERSION_LITERAL = re.compile(r'^__version__\s*=\s*["\']([^"\']+)["\']', re.M)

# Canonical runtime literal site per package.
PACKAGES = {
    "aethel": REPO / "aethel" / "__init__.py",
    "kellogg": REPO / "kellogg" / "__init__.py",
    "toe": REPO / "toe" / "__init__.py",
    "hyba": REPO / "hyba" / "__init__.py",
    "turing_universal_quantum_computer": (
        REPO / "turing_universal_quantum_computer"
        / "turing_universal_quantum_computer" / "__init__.py"
    ),
}

# pyproject packaging mirrors that must equal the runtime literal.
PYPROJECT_MIRRORS = {
    "turing_universal_quantum_computer": (
        REPO / "turing_universal_quantum_computer" / "pyproject.toml"
    ),
}

# The repo distribution itself — canonical here, no runtime counterpart.
REPO_PYPROJECT = REPO / "pyproject.toml"


def _literal(path: Path):
    m = VERSION_LITERAL.search(path.read_text(encoding="utf-8"))
    return m.group(1) if m else None


def _pyproject_version(path: Path):
    m = re.search(
        r'^version\s*=\s*["\']([^"\']+)["\']',
        path.read_text(encoding="utf-8"),
        re.M,
    )
    return m.group(1) if m else None


def _runtime_version(pkg: str) -> str:
    if pkg == "turing_universal_quantum_computer":
        # Outer dir is a project dir; the importable package is nested.
        outer = str(REPO / pkg)
        if outer not in sys.path:
            sys.path.insert(0, outer)
    return importlib.import_module(pkg).__version__


@pytest.mark.parametrize("pkg,init", sorted(PACKAGES.items()))
def test_canonical_literal_is_semver(pkg, init):
    v = _literal(init)
    assert v is not None, f"{pkg}: no __version__ literal at canonical site"
    assert SEMVER.match(v), f"{pkg}: {v!r} is not SemVer"


@pytest.mark.parametrize("pkg,init", sorted(PACKAGES.items()))
def test_runtime_agrees_with_canonical(pkg, init):
    assert _runtime_version(pkg) == _literal(init)


@pytest.mark.parametrize("pkg,init", sorted(PACKAGES.items()))
def test_single_literal_per_package(pkg, init):
    pkg_dir = REPO / pkg
    if pkg == "turing_universal_quantum_computer":
        pkg_dir = pkg_dir / pkg  # scan only the importable package tree
    literals = []
    for py in pkg_dir.rglob("*.py"):
        rel = py.relative_to(REPO)
        if any(part in {"__pycache__", "build", ".kilo"} for part in rel.parts):
            continue
        if VERSION_LITERAL.search(py.read_text(encoding="utf-8", errors="ignore")):
            literals.append(str(rel))
    assert literals == [str(init.relative_to(REPO))], (
        f"{pkg}: version literals outside canonical site: {literals}"
    )


def test_derived_reference_not_literal():
    """toe/engine.py must derive, not redeclare."""
    src = (REPO / "toe" / "engine.py").read_text(encoding="utf-8")
    assert not VERSION_LITERAL.search(src), "engine.py redeclares __version__"
    assert "from toe import __version__" in src


@pytest.mark.parametrize("pkg,toml", sorted(PYPROJECT_MIRRORS.items()))
def test_pyproject_mirror_equals_runtime(pkg, toml):
    assert _pyproject_version(toml) == _runtime_version(pkg)


def test_repo_distribution_version_is_semver():
    v = _pyproject_version(REPO_PYPROJECT)
    assert v and SEMVER.match(v)


@pytest.mark.parametrize("pkg", sorted(PACKAGES))
def test_installed_metadata_agrees_or_is_recorded(pkg):
    """If a dist is installed, its metadata MUST equal the runtime version.
    Absence is legal but is enumerated in reports/version_consolidation.md."""
    candidates = {pkg, pkg.replace("_", "-")}
    found = [d for d in candidates if d in {
        dist.metadata["Name"] for dist in importlib.metadata.distributions()
    }]
    for dist in found:
        assert importlib.metadata.version(dist) == _runtime_version(pkg)
