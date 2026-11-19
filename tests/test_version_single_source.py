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
         "src/chronus/execution/authority.py", "src/chronus/core/facade.py")
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


def _declared() -> str:
    import chronus
    return chronus.__version__


def test_deployment_manifests_pin_one_published_image_version():
    """Kubernetes manifests describe what is deployed: the last published images.

    Their `version` labels must equal their image tags, so a label never claims a
    version the pod does not run. They move to chronus.__version__ only when a
    release publishes images at that tag (no image is built for a dev version).
    """
    offenders = []
    for rel in ("infra/k8s/deployment.yaml", "infra/k8s/chronus-k8s-deployment.yaml", "chronus-k8s-deployment.yaml"):
        path = ROOT / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        labels = set(re.findall(r'^\s*version:\s*"([^"]+)"', text, re.M))
        tags = set(re.findall(r"registry\.chronus\.dev/chronus/[a-z-]+:v?([^\s\"']+)", text))
        if len(labels | tags) > 1:
            offenders.append(f"{rel}: labels {sorted(labels)} vs image tags {sorted(tags)}")
    assert offenders == []


def test_native_library_reads_the_single_version():
    """cpp/CMakeLists.txt derives its version from src/chronus/__init__.py; c_api.cpp has no literal."""
    cmake = (ROOT / "cpp" / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "src/chronus/__init__.py" in cmake
    assert re.search(r"project\(chronus_igpu_native VERSION \$\{CHRONUS_VERSION_NUMERIC\}", cmake)
    assert 'CHRONUS_VERSION_STRING="${CHRONUS_VERSION}"' in cmake
    c_api = (ROOT / "cpp" / "src" / "c_api.cpp").read_text(encoding="utf-8")
    assert "CHRONUS_VERSION_STRING" in c_api
    assert not re.search(r'"\d+\.\d+\.\d+', c_api)
    makefile = (ROOT / "cpp" / "Makefile").read_text(encoding="utf-8")
    assert "../src/chronus/__init__.py" in makefile and "-DCHRONUS_VERSION_STRING=" in makefile
    assert "CMAKE_CONFIGURE_DEPENDS" in cmake


def test_test_package_and_facade_use_the_single_version():
    import tests
    from chronus.core.facade import ChronusVerificationOrchestrator  # noqa: F401  (import-time check)
    assert tests.__version__ == _declared()
    facade = (SRC / "core" / "facade.py").read_text(encoding="utf-8")
    assert "chronus_gpiu-v36" not in facade
    from chronus.core import facade as facade_mod
    assert facade_mod.LEGACY_MANIFEST_FILENAME == "qualification_manifest_v36.json"  # format id, not release


def test_release_tag_must_carry_the_single_version(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("check_release_version", ROOT / "scripts" / "ci" / "check_release_version.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    version = _declared()
    assert mod.declared_version() == version
    assert mod.check(f"v{version}", version) == []
    assert mod.check(f"v{version}-internal", version) == []
    assert mod.check(f"refs/tags/v{version}", version) == []
    assert mod.check("v36.0.0", version)  # a stale tag is refused
    assert mod.check(f"v{version}9", version)  # no prefix collisions
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / f"hyba_chronus-{version}-py3-none-any.whl").write_bytes(b"")
    assert mod.check(f"v{version}", version, dist)  # sdist missing
    (dist / f"hyba_chronus-{version}.tar.gz").write_bytes(b"")
    assert mod.check(f"v{version}", version, dist) == []
    (dist / f"hyba_chronus-{version}1-py3-none-any.whl").write_bytes(b"")  # prefix-sharing version
    assert mod.check(f"v{version}", version, dist)
    (dist / f"hyba_chronus-{version}1-py3-none-any.whl").unlink()
    (dist / "other-1.0.tar.gz").write_bytes(b"")  # unexpected artifact
    assert mod.check(f"v{version}", version, dist)
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert release.count("scripts/ci/check_release_version.py") == 2


def test_operator_docs_state_the_single_version():
    doc = (ROOT / "docs" / "HYPERSCALER_DATA_CONNECTOR_AND_USER_JOURNEYS.md").read_text(encoding="utf-8")
    m = re.search(r"\*\*Substrate Version:\*\* (\S+)", doc)
    assert m and m.group(1) == _declared()
