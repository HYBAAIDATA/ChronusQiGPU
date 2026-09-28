"""The deploy sentry catches each wiring pitfall it was built for, and passes this repo."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

from scripts import deploy_sentry as sentry

PYPROJECT = """
[project]
name = "fixture"
dependencies = ["numpy>=1.26"]

[project.optional-dependencies]
ml = ["xgboost>=1.7"]
dev = ["pytest>=7"]
"""


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")


def _repo(tmp_path: Path) -> Path:
    _write(tmp_path, "pyproject.toml", PYPROJECT)
    _write(
        tmp_path, "main.py", "import numpy\nimport os\n\nPORT = os.getenv('PYTHIA_PORT', '3000')\n"
    )
    return tmp_path


def _messages(findings, check):
    return [(f.severity, f.path, f.message) for f in findings if f.check == check]


def test_dead_config_is_an_error_on_the_deploy_path_and_a_warning_elsewhere(tmp_path):
    root = _repo(tmp_path)
    _write(
        root,
        "deploy/azure/Dockerfile",
        "FROM x\nENV PYTHIA_PORT=3000 \\\n    PYTHIA_LIVE_SUBMIT=0\n",
    )
    _write(
        root,
        "docker-compose.yml",
        "services:\n  app:\n    environment:\n      PYTHIA_STOP_FILE: /tmp/stop\n",
    )
    _write(root, ".env.example", "MLA1517_STRATUM_USER=x\n# PYTHIA_PORT=3000\n")
    findings = _messages(sentry.check_dead_config(root), "DS01")
    assert (
        "error",
        "deploy/azure/Dockerfile",
        "sets PYTHIA_LIVE_SUBMIT, which no code reads",
    ) in findings
    assert ("error", ".env.example", "sets MLA1517_STRATUM_USER, which no code reads") in findings
    assert (
        "warning",
        "docker-compose.yml",
        "sets PYTHIA_STOP_FILE, which no code reads",
    ) in findings
    assert not any("PYTHIA_PORT" in message for _, _, message in findings)


def test_templated_reads_count_but_bare_placeholders_do_not(tmp_path):
    root = _repo(tmp_path)
    _write(
        root,
        "pools.py",
        """
        import os

        def settings(name, key):
            prefix = f"MLA1517_{name.upper()}"
            anything = f"{name}"
            return os.getenv(f"{prefix}_{key}") or os.getenv(f"MLA1517_STRATUM_{key}"), anything

        KEYS = ("ENDPOINT", "USER")
        """,
    )
    _write(
        root, ".env.example", "MLA1517_VIABTC_USER=a\nMLA1517_STRATUM_ENDPOINT=b\nPYTHIA_DEAD=c\n"
    )
    dead = {m for _, _, m in _messages(sentry.check_dead_config(root), "DS01")}
    assert dead == {"sets PYTHIA_DEAD, which no code reads"}


def test_python_dependencies_declared_and_imported(tmp_path):
    root = _repo(tmp_path)
    _write(root, ".dockerignore", "data\n")
    _write(root, "data/__init__.py", "")
    _write(root, "data/helpers.py", "")
    _write(
        root,
        "main.py",
        "import numpy\nimport requests\nimport data.helpers\ntry:\n    import torch\nexcept ImportError:\n    torch = None\n",
    )
    findings = _messages(sentry.check_python_deps(root), "DS02")
    messages = {m for _, _, m in findings}
    assert "runtime imports 'requests' unguarded, but it is not a core dependency" in messages
    assert "runtime optionally imports 'torch', which no extra declares" in messages
    assert "declares 'xgboost', which nothing imports" in messages
    assert any("excluded from the image by .dockerignore" in m for m in messages)
    assert not any("numpy" in m or "pytest" in m for m in messages)


def test_native_build_needs_a_makefile_and_the_image_needs_the_library(tmp_path):
    root = _repo(tmp_path)
    _write(root, "platform/host/driver.c", "int x;\n")
    _write(root, "main.py", "import hardware\n")
    _write(root, "hardware.py", "LIB = 'libdriver.so'\n")
    _write(
        root,
        "deploy/azure/Dockerfile",
        "FROM x AS native\nCOPY platform/host /src/host\nRUN make -C /src/host\nFROM y\n",
    )
    messages = {m for _, _, m in _messages(sentry.check_native_build(root), "DS03")}
    assert "runs make -C /src/host, but there is no Makefile there" in messages
    assert any("loads libdriver.so" in m for m in messages)
    _write(root, "platform/host/Makefile", "all:\n")
    _write(
        root,
        "deploy/azure/Dockerfile",
        "FROM x AS native\nCOPY platform/host /src/host\nRUN make -C /src/host\n"
        "FROM y\nCOPY --from=native /src/host/libdriver.so /usr/local/lib/\n",
    )
    assert _messages(sentry.check_native_build(root), "DS03") == []


def test_boot_requirements_must_be_set_by_the_deploy_manifest(tmp_path):
    root = _repo(tmp_path)
    _write(root, "main.py", "import contract\n")
    _write(
        root,
        "contract.py",
        """
        import os

        def identity():
            if not os.getenv("MLA1517_STRATUM_USER"):
                raise RuntimeError("MLA1517_STRATUM_USER is required")
        """,
    )
    _write(root, "deploy/azure/main.bicep", "env: [\n  { name: 'PYTHIA_PORT', value: '3000' }\n]\n")
    findings = _messages(sentry.check_boot_requirements(root), "DS06")
    assert findings and "MLA1517_STRATUM_USER" in findings[0][2]
    _write(
        root,
        "deploy/azure/main.bicep",
        "env: [\n  { name: 'MLA1517_STRATUM_USER', value: user }\n]\n",
    )
    assert _messages(sentry.check_boot_requirements(root), "DS06") == []


def test_ci_triggers_double_runs_and_stale_branches(tmp_path):
    root = _repo(tmp_path)
    _write(root, ".github/workflows/ci.yml", "on:\n  push:\n  pull_request:\njobs: {}\n")
    _write(
        root,
        ".github/workflows/gate.yml",
        "on:\n  push:\n    branches: [main, feature/gone]\n  pull_request:\n    branches: [main]\njobs: {}\n",
    )
    findings = _messages(sentry.check_ci_triggers(root, branches={"main"}), "DS04")
    assert (
        "error",
        ".github/workflows/ci.yml",
        "runs on push to every branch and on pull_request: every PR commit runs it twice",
    ) in findings
    assert (
        "warning",
        ".github/workflows/gate.yml",
        "push filters on branch 'feature/gone', which does not exist on origin",
    ) in findings
    assert len(findings) == 2


def test_frontend_dependencies_referenced_and_script_binaries_declared(tmp_path):
    root = _repo(tmp_path)
    manifest = {
        "scripts": {"build": "vite build", "format": "prettier --write ."},
        "dependencies": {"react": "^19", "firebase": "^11"},
        "devDependencies": {"vite": "^6", "@types/react": "^19", "@types/d3": "^7"},
    }
    _write(root, "frontend/package.json", json.dumps(manifest))
    _write(root, "frontend/src/main.tsx", "import React from 'react';\n")
    messages = {m for _, _, m in _messages(sentry.check_frontend_deps(root), "DS05")}
    assert messages == {
        "declares 'firebase', which nothing references",
        "declares '@types/d3', which nothing references",
        "a script runs 'prettier', which is not a declared dependency",
    }


def test_script_binaries_resolve_without_node_modules(tmp_path):
    # CI scans a bare checkout: no node_modules to read package bin maps from.
    root = _repo(tmp_path)
    manifest = {
        "scripts": {"lint": "tsc --noEmit", "test": "vitest run", "clean": "rimraf dist"},
        "devDependencies": {"typescript": "^5", "vitest": "^3", "rimraf": "^6"},
    }
    _write(root, "frontend/package.json", json.dumps(manifest))
    assert sentry.check_frontend_deps(root) == []


def test_this_repository_has_no_deploy_path_errors():
    findings = sentry.scan(sentry.ROOT, ("DS01", "DS02", "DS03", "DS05", "DS06"))
    errors = [f.line() for f in findings if f.severity == "error"]
    assert errors == []


def test_a_variable_the_container_shell_reads_is_not_dead_config(tmp_path):
    root = _repo(tmp_path)
    _write(
        root,
        "docker-compose.live.yml",
        """
        services:
          app:
            environment:
              PYTHIA_POOL: both
              PYTHIA_UNUSED: x
            command: ["sh", "-c", "python3 main.py --pool $${PYTHIA_POOL}"]
        """,
    )
    findings = _messages(sentry.check_dead_config(root), "DS01")
    assert findings == [
        ("warning", "docker-compose.live.yml", "sets PYTHIA_UNUSED, which no code reads")
    ]


def test_entry_points_must_exist(tmp_path):
    root = _repo(tmp_path)
    _write(root, "mining/__init__.py", "")
    _write(root, "mining/live.py", "")
    _write(root, "scripts/bench.py", "")
    _write(
        root,
        "docker-compose.pools.yml",
        """
        services:
          gone:
            command: ["python3", "-m", "mining.production_miner", "--dry-run"]
          here:
            command: ["python3", "-m", "mining.live"]
          tool:
            command: ["python", "-m", "pip", "list"]
        """,
    )
    _write(
        root,
        "deploy/azure/Dockerfile",
        'FROM x\nENTRYPOINT ["python3", "scripts/benchmark.py"]\nCMD ["python3", "scripts/bench.py"]\n',
    )
    assert sorted(_messages(sentry.check_entry_points(root), "DS07")) == [
        ("error", "deploy/azure/Dockerfile", "runs scripts/benchmark.py, which does not exist"),
        (
            "warning",
            "docker-compose.pools.yml",
            "runs python -m mining.production_miner, which does not exist",
        ),
    ]
