"""The Chronus version is declared once (chronus.__version__) and read everywhere else."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest


pytestmark = pytest.mark.real

tomllib = pytest.importorskip("tomllib")  # stdlib from Python 3.11; pyproject check skipped on 3.10

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "chronus"
VERSION_SHAPE = re.compile(r"^v?\d+\.\d+\.\d+([.-]?(dev|rc|a|b)\d+)?$")
SCOPE = ("src/chronus/service/", "src/chronus/sdk/", "src/chronus/security/__init__.py",
         "src/chronus/database/__init__.py", "src/chronus/distributed/__init__.py",
         "src/chronus/execution/authority.py")
# Reviewed literals that are not the Chronus release version.
ALLOWED = {
    ("src/chronus/service/api/app.py", "1.0.0"): "OpenAPI contract version of the public /v1 Compute API",
}
EMBEDDED = re.compile(r"Chronus-Python-SDK/v?\d")  # SDK User-Agent must carry chronus.__version__


def test_pyproject_reads_the_single_declaration():
    meta = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert "version" not in meta["project"]
    assert "version" in meta["project"]["dynamic"]
    assert meta["tool"]["setuptools"]["dynamic"]["version"] == {"attr": "chronus.__version__"}


def test_no_second_version_literal_in_service_surfaces():
    """Any version-shaped string constant (including positional ones) in scope is a second declaration."""
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        if path == SRC / "__init__.py" or not rel.startswith(SCOPE):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                value = node.value.strip()
                if (VERSION_SHAPE.match(value) and (rel, value) not in ALLOWED) or EMBEDDED.search(value):
                    offenders.append(f"{rel}:{node.lineno}: {value!r}")
    assert offenders == []


def test_runtime_surfaces_report_the_same_version():
    from chronus.sdk.client import ChronusAPISDK
    from chronus.service.app import create_app
    from chronus.service.models import HealthResponse
    import chronus.database, chronus.distributed, chronus.sdk, chronus.security, chronus.service

    assert create_app().version == chronus.__version__
    assert ChronusAPISDK.SDK_VERSION == chronus.__version__
    assert HealthResponse.model_fields["version"].default == chronus.__version__
    from chronus.sdk.standalone import ChronusClient
    assert ChronusClient()._headers["User-Agent"] == f"Chronus-Python-SDK/{chronus.__version__}"
    for module in (chronus.database, chronus.distributed, chronus.sdk, chronus.security, chronus.service):
        assert module.__version__ == chronus.__version__
