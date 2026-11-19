"""The Chronus version is declared once (chronus.__version__) and read everywhere else."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest


pytestmark = pytest.mark.real

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "chronus"
LITERAL = re.compile(
    r"""(__version__\s*=\s*["']|SDK_VERSION\s*=\s*["']|version\s*[:=]\s*(str\s*=\s*)?["']3\d\.\d|"""
    r"""["']version["']\s*:\s*["']3\d\.\d|producer_version["']\s*:\s*["']3\d\.)"""
)


def test_pyproject_reads_the_single_declaration():
    meta = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert "version" not in meta["project"]
    assert "version" in meta["project"]["dynamic"]
    assert meta["tool"]["setuptools"]["dynamic"]["version"] == {"attr": "chronus.__version__"}


def test_no_second_version_literal_in_service_surfaces():
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        if path == SRC / "__init__.py":
            continue
        rel = path.relative_to(ROOT).as_posix()
        if not rel.startswith(("src/chronus/service/", "src/chronus/sdk/", "src/chronus/security/__init__",
                               "src/chronus/database/__init__", "src/chronus/distributed/__init__",
                               "src/chronus/execution/authority")):
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if LITERAL.search(line):
                offenders.append(f"{rel}:{number}: {line.strip()}")
    assert offenders == []


def test_runtime_surfaces_report_the_same_version():
    from chronus.sdk.client import ChronusAPISDK
    from chronus.service.app import create_app
    from chronus.service.models import HealthResponse
    import chronus.database, chronus.distributed, chronus.sdk, chronus.security, chronus.service

    assert create_app().version == chronus.__version__
    assert ChronusAPISDK.SDK_VERSION == chronus.__version__
    assert HealthResponse.model_fields["version"].default == chronus.__version__
    for module in (chronus.database, chronus.distributed, chronus.sdk, chronus.security, chronus.service):
        assert module.__version__ == chronus.__version__
