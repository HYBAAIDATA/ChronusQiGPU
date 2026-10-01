from __future__ import annotations

from pathlib import Path
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
    offenders = []
    forbidden = (
        "from igpu",
        "import igpu",
        "igpu.",
        "igpu/",
        "IGPUOpenCL",
        "IgpuTelemetry",
        "ResidentIGPU",
        "IGpuSku",
    )
    for path in ROOT.rglob("*"):
        if not path.is_file() or not _active(path) or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(token in text for token in forbidden):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_mla1517_is_folded_under_chronus():
    assert not (ROOT / "mla1517_platform_v3.4").exists()
    assert (ROOT / "chronus" / "mla1517_platform").is_dir()
    assert chronus.mla1517.__name__ == "chronus.mla1517"
    assert chronus.mla1517.fib(10) == 55
    offenders = []
    forbidden = (
        "from mla1517 ",
        "from mla1517.",
        "import mla1517 ",
        "import mla1517.",
        "mla1517_platform_v3.4",
    )
    for path in ROOT.rglob("*"):
        if not path.is_file() or not _active(path) or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(token in text for token in forbidden):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


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
