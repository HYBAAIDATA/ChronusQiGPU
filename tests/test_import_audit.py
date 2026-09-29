"""The import audit finds the broken wires a swallowed ImportError hides."""

from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.import_audit import Auditor, live_files


def _repo(tmp_path: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    return tmp_path


def _codes(root: Path) -> list[tuple[str, str, bool]]:
    return [
        (f.code, f"{f.module}.{f.name}" if f.name else f.module, f.swallowed)
        for f in Auditor(root).audit(live_files(root))
    ]


def test_the_salamander_bug_is_found_even_though_it_was_swallowed(tmp_path):
    root = _repo(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/skill_loader.py": "def discover_skills():\n    return []\n",
            "pkg/salamander.py": (
                "try:\n"
                "    from .skill_loader import load_skills\n"
                "except Exception:\n"
                "    pass\n"
                "from .skill_loader import discover_skills\n"
            ),
        },
    )
    assert _codes(root) == [("IA02", ".skill_loader.load_skills", True)]


def test_missing_modules_names_and_escaping_relatives(tmp_path):
    root = _repo(
        tmp_path,
        {
            "pkg/__init__.py": "from .sub import *\n",
            "pkg/sub.py": "X = 1\n",
            "pkg/lazy.py": "def __getattr__(name):\n    return name\n",
            "pkg/user.py": (
                "import pkg.gone\n"
                "from pkg import anything_star_exported\n"  # open-ended: star import
                "from pkg.lazy import whatever\n"  # open-ended: module __getattr__
                "from pkg.sub import X, Y\n"
                "from ... import far\n"
                "import importlib\n"
                "importlib.import_module('pkg.vanished')\n"
                "import numpy\n"  # third party: not this audit's concern
            ),
        },
    )
    assert _codes(root) == [
        ("IA01", "pkg.gone", False),
        ("IA02", "pkg.sub.Y", False),
        ("IA03", "...", False),
        ("IA04", "pkg.vanished", False),
    ]


def test_roots_follow_how_python_finds_modules(tmp_path):
    root = _repo(
        tmp_path,
        {
            "helper.py": "OTHER = 1\n",
            # A script's own folder comes first on sys.path: this is tools/helper.
            "tools/helper.py": "VALUE = 1\n",
            "tools/run.py": "from helper import VALUE\n",
            # A package module's folder is not on sys.path: this is ./helper.py.
            "pkg/__init__.py": "",
            "pkg/helper.py": "VALUE = 1\n",
            "pkg/mod.py": "from helper import VALUE\n",
            # An in-tree distribution keeps its package one level down.
            "dist/pyproject.toml": "[project]\nname = 'dist'\n",
            "dist/vqc/__init__.py": "",
            "dist/vqc/hilbert.py": "class QuantumRegister:\n    pass\n",
            "user.py": "from vqc.hilbert import QuantumRegister\n",
        },
    )
    assert _codes(root) == [("IA02", "helper.VALUE", False)]  # pkg/mod.py only


def test_the_repository_has_no_broken_imports():
    root = Path(__file__).resolve().parents[1]
    findings = Auditor(root).audit(live_files(root))
    assert findings == [], "\n".join(f.render() for f in findings)


def test_salamander_reports_broken_imports_as_critical(tmp_path):
    from Intelligence.salamander_agentic import CodebaseIssueType, SalamanderCodebaseScanner

    root = _repo(tmp_path, {"pkg/__init__.py": "", "pkg/a.py": "from pkg.b import c\n"})
    diagnostics = SalamanderCodebaseScanner(root).audit_imports()
    assert [(d.issue_type, d.severity, d.pattern) for d in diagnostics] == [
        (CodebaseIssueType.BROKEN_IMPORT, "CRITICAL", "IA01")
    ]
