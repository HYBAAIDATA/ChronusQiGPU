from __future__ import annotations

from pathlib import Path
import ast
import subprocess
import sys

import chronus
import chronus.mla1517
from chronus import Chronus, ChronusFabric, ChronusOpenCLEngine, ChronusTelemetry

ROOT = Path(__file__).resolve().parents[1]
SKIP = {"legacy", ".git", "node_modules", ".venv", "venv", "dist", "build"}
TEXT_SUFFIXES = {".py", ".md", ".toml", ".yml", ".yaml", ".json", ".ts", ".tsx", ".js", ".cl"}


def _active(path: Path) -> bool:
    if path.resolve() == Path(__file__).resolve():
        # This test's own source necessarily names the retired tokens.
        return False
    rel = path.relative_to(ROOT)
    return not any(part in SKIP for part in rel.parts)


def test_chronus_is_real_public_namespace():
    assert Chronus.__module__ == "chronus.device"
    assert ChronusFabric.__module__ == "chronus.fabric"
    assert ChronusOpenCLEngine.__module__ == "chronus.engine"
    assert ChronusTelemetry.__module__ == "chronus.telemetry"
    assert chronus.__name__ == "chronus"


def test_no_active_igpu_namespace_or_compatibility_shim():
    assert not (ROOT / "igpu").exists()
    assert _retired_imports("igpu") == []


def _retired_imports(namespace):
    offenders = []
    # Import syntax, not historical prose, vendor names or string literals,
    # determines whether the retired top-level Python namespace is active.
    for path in ROOT.rglob("*.py"):
        if not _active(path):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeError):
            continue
        for node in ast.walk(tree):
            modules = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                       else [node.module] if isinstance(node, ast.ImportFrom) and node.level == 0
                       else [])
            if any(m and (m == namespace or m.startswith(namespace + ".")) for m in modules):
                offenders.append(str(path.relative_to(ROOT)))
                break
    return offenders


def test_mla1517_is_folded_under_chronus():
    assert not (ROOT / "mla1517_platform_v3.4").exists()
    assert (ROOT / "chronus" / "mla1517_platform").is_dir()
    assert chronus.mla1517.__name__ == "chronus.mla1517"
    assert chronus.mla1517.fib(10) == 55
    assert _retired_imports("mla1517") == []


def test_turing_remains_separate_compute_substrate():
    import turing_core

    assert turing_core is not chronus


def test_chronus_import_contract_in_fresh_interpreter():
    code = "import chronus, chronus.mla1517; assert chronus.mla1517.fib(10) == 55"
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
