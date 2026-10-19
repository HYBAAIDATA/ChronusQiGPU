#!/usr/bin/env python3
"""Installed-wheel end-to-end gate (PR #69 / EQS-CAP-LEDGER-V2).

Closes the last PENDING row of the PR #69 verification hierarchy:

    [Local Hermetic Wheel Build]        PASSED  (site-packages disabled)
    [33 Scoped Capability Tests]        PASSED  (Normal & Python -O)
    [Credential Scrubbing in Evidence]  VERIFIED
    [Installed Wheel End-to-End Gate]   <-- this gate

The gate proves that the umbrella ``hyba-pythia-mining`` distribution is a
cohesive, hermetic runtime that *ships* ``Intelligence/`` (Slice A) and that
the empirical state controller (Slice B / Native Path #3) runs from the
installed artifact -- never from the source checkout.

Stages, every one fail-closed (a non-zero exit anywhere aborts the gate):

  1. Hermetic build -- build the wheel with ``python -m build`` in an isolated
     build environment (site-packages disabled). This is the definitive test
     that the distribution does not silently lean on ambient virtualenv
     artifacts.
  2. Inspect & secret-scan -- the wheel must contain ``Intelligence/`` and must
     not embed operator signing keys or credentials.
  3. Clean install -- provision a fresh venv *outside* the repository and
     install the freshly-built umbrella wheel beside the sibling product
     wheels (dependency resolution exercised exactly as a real install).
  4. Installed-copy import -- from outside the checkout, in an isolated
     interpreter (``python -I``), import ``Intelligence`` and
     ``Intelligence.empirical_state_controller`` and assert both resolve from
     site-packages, never from the repository tree.
  5. Scoped capability run -- run the empirical state controller scoped tests
     against the installed copy, in normal mode AND under ``python -O``,
     confirming authorization, durable pre-execution audit and reversible
     state rollback operate via unconditional runtime branches.

Writes a verification record with the wheel SHA-256 next to the wheel.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
DIST = REPO / "dist"
WHEEL_GLOB = "hyba_pythia_mining-*.whl"
SIBLING_WHEELS = (
    "hyba_chronos_one_igpu-*.whl",
    "hyba_kellogg_tensor-*.whl",
    "hyba_turing_vqc-*.whl",
)
# Native Path #3 / Slice B surface that must be present and executable from
# the installed artifact.
REQUIRED_WHEEL_MEMBERS = (
    "Intelligence/__init__.py",
    "Intelligence/empirical_state_controller.py",
)
INSTALLED_IMPORT_CHECK = (
    "import Intelligence, Intelligence.empirical_state_controller as esc\n"
    "assert 'site-packages' in Intelligence.__file__, Intelligence.__file__\n"
    "assert 'site-packages' in esc.__file__, esc.__file__\n"
)
# Empirical state controller scoped capability tests (Native Path #3). Copied
# to a temp dir OUTSIDE the checkout so the import resolves to the installed
# copy, never the source tree.
SCOPED_TESTS = ("test_empirical_state_controller.py",)
SCOPED_TEST_SOURCE = REPO / "legacy" / "tests"
SECRET_PATTERNS = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"ghp_[A-Za-z0-9]{30,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{40,}"),
    re.compile(rb"pypi-AgEI[A-Za-z0-9_-]{20,}"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
)


def sh(cmd: list, **kw) -> subprocess.CompletedProcess:
    print("$", " ".join(str(c) for c in cmd), flush=True)
    return subprocess.run([str(c) for c in cmd], check=True, text=True, **kw)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _python_in(env: Path) -> Path:
    return env / ("Scripts" if sys.platform == "win32" else "bin") / "python"


def _sibling(pattern: str) -> Path:
    matches = sorted(DIST.glob(pattern))
    if not matches:
        raise RuntimeError(f"sibling wheel {pattern!r} not found in {DIST}; build it first")
    return matches[0]


def inspect(wheel: Path) -> dict:
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        secrets = [n for n in names if any(p.search(archive.read(n)) for p in SECRET_PATTERNS)]
    missing = [m for m in REQUIRED_WHEEL_MEMBERS if m not in names]
    intelligence = [n for n in names if n.startswith("Intelligence/")]
    return {
        "files": len(names),
        "intelligence_members": len(intelligence),
        "missing_required": missing,
        "secret_hits": secrets,
        "passed": not (missing or secrets) and bool(intelligence),
    }


def run_scoped(python: Path, tests_dir: Path, optimized: bool) -> dict:
    cmd = [python, "-m", "pytest", *SCOPED_TESTS, "-q", "-p", "no:cacheprovider"]
    if optimized:
        cmd.insert(1, "-O")
    completed = subprocess.run(
        [str(c) for c in cmd], cwd=str(tests_dir), text=True, capture_output=True, check=False
    )
    tail = (completed.stdout or "").strip().splitlines()[-1:] or [""]
    return {
        "mode": "python -O" if optimized else "normal",
        "returncode": completed.returncode,
        "passed": completed.returncode == 0,
        "summary": tail[0],
    }


def main() -> int:
    DIST.mkdir(exist_ok=True)
    record: dict = {
        "product": "hyba-pythia-mining",
        "gate": "installed-wheel-end-to-end",
        "stages": {},
    }
    with tempfile.TemporaryDirectory(prefix="installed-wheel-e2e-") as tmp:
        tmp_path = Path(tmp)

        # 1. Hermetic build (site-packages disabled).
        build_out = tmp_path / "build"
        build_out.mkdir()
        sh([sys.executable, "-m", "build", "--wheel", "--outdir", build_out, REPO], cwd=tmp_path)
        wheel = next(build_out.glob(WHEEL_GLOB))
        record["wheel"] = wheel.name
        record["wheel_sha256"] = sha256(wheel)

        # 2. Inspect & secret-scan.
        record["inspection"] = inspect(wheel)
        if not record["inspection"]["passed"]:
            raise ValueError("wheel inspection failed (missing Intelligence/ or secret hit)")

        # 3. Clean install into a venv outside the repository.
        env_dir = tmp_path / "venv"
        venv.EnvBuilder(with_pip=True).create(env_dir)
        python = _python_in(env_dir)
        sh([python, "-m", "pip", "install", "-q", "--upgrade", "pip"], cwd=tmp_path)
        siblings = [_sibling(p) for p in SIBLING_WHEELS]
        sh([python, "-m", "pip", "install", "-q", wheel, *siblings], cwd=tmp_path)
        record["installed_outside_repository"] = str(REPO.resolve()) not in str(env_dir.resolve())

        # 4. Installed-copy import from outside the checkout, isolated interpreter.
        outside = tmp_path / "outside"
        outside.mkdir()
        completed = sh(
            [python, "-I", "-c", INSTALLED_IMPORT_CHECK], cwd=outside, capture_output=True
        )
        record["installed_copy_import"] = {
            "passed": completed.returncode == 0,
            "returncode": completed.returncode,
        }

        # 5. Scoped capability run against the installed copy (normal + -O).
        sh([python, "-m", "pip", "install", "-q", "pytest"], cwd=tmp_path)
        tests_dir = tmp_path / "scoped"
        tests_dir.mkdir()
        for name in SCOPED_TESTS:
            shutil.copy2(SCOPED_TEST_SOURCE / name, tests_dir / name)
        record["scoped_capability_tests"] = [
            run_scoped(python, tests_dir, optimized=False),
            run_scoped(python, tests_dir, optimized=True),
        ]

    record["passed"] = bool(
        record["inspection"]["passed"]
        and record["installed_outside_repository"]
        and record["installed_copy_import"]["passed"]
        and all(t["passed"] for t in record["scoped_capability_tests"])
    )
    evidence = DIST / "installed-wheel-e2e-gate.json"
    evidence.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(record, indent=2, sort_keys=True))
    print(f"EVIDENCE={evidence}")
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
