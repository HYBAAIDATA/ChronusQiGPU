"""Qualify the existing local capability distribution set, without publishing.

Reject overlapping wheel ownership, install into an independent environment and
run supplied real-owner consumers without source path injection. This does not
certify remote service security or approve a production release.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from time import perf_counter
import zipfile


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def verify_wheel_ownership(wheels) -> None:
    owners = {}
    for wheel in wheels:
        with zipfile.ZipFile(wheel) as archive:
            for name in archive.namelist():
                if name.endswith("/"):
                    continue
                if name in owners:
                    raise ValueError(f"wheel ownership overlap: {name}")
                owners[name] = wheel.name


def qualify(args) -> int:
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    from run_experiment import source_identity

    source = source_identity(Path(__file__).resolve().parents[2])
    report = {
        "schema": "turing.capability_installation.v1",
        "status": "running",
        "release_approved": False,
        "source": source,
        "evidence_scope": "commit_bound_candidate"
        if source["state"] == "clean"
        else "development_only",
        "python": sys.version,
        "steps": [],
        "inputs": {},
    }
    env = dict(os.environ)
    for name in ("PYTHONPATH", "PYTHONHOME", "PYTEST_ADDOPTS"):
        env.pop(name, None)

    def run(label, command, cwd):
        start = perf_counter()
        result = subprocess.run(
            list(map(str, command)),
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=240,
        )
        report["steps"].append(
            {
                "name": label,
                "exit_code": result.returncode,
                "duration_seconds": perf_counter() - start,
            }
        )
        # Never persist arbitrary installer/provider output; it may contain
        # private index credentials or customer payloads. Keep reviewed JUnit.
        if result.returncode:
            raise RuntimeError(f"{label} failed (exit {result.returncode}); inspect privately")

    try:
        paths = [
            args.platform_wheel,
            args.turing_wheel,
            args.kellogg_wheel,
            args.research_requirements,
            args.platform_requirements,
            args.consumer_tests,
        ]
        for path in paths:
            if not path.is_file():
                raise ValueError("required input file missing")
            report["inputs"][path.name] = digest(path)
        verify_wheel_ownership(paths[:3])
        report["wheel_ownership_overlap"] = 0
        uv = shutil.which("uv")
        if not uv:
            raise RuntimeError("pinned uv build tool must be available on PATH")
        with tempfile.TemporaryDirectory(prefix="turing-capability-install-") as workdir:
            work = Path(workdir)
            venv = work / "environment"
            python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            run("independent environment", [uv, "venv", "--python", sys.executable, venv], work)
            run(
                "hashed qualification dependencies",
                [
                    uv,
                    "pip",
                    "install",
                    "--python",
                    python,
                    "--require-hashes",
                    "-r",
                    args.research_requirements,
                    "-r",
                    args.platform_requirements,
                ],
                work,
            )
            run(
                "install actual wheels",
                [uv, "pip", "install", "--python", python, "--no-deps", *paths[:3]],
                work,
            )
            run("dependency consistency", [uv, "pip", "check", "--python", python], work)
            consumers = work / "consumers"
            consumers.mkdir()
            shutil.copy2(args.consumer_tests, consumers / "test_capability.py")
            origin = (
                "import importlib,sys; from pathlib import Path; "
                "modules=[importlib.import_module(n) for n in "
                "['aethel.enterprise.production_organism','euclid.runtime',"
                "'euclid.organ_adapters.specialists','al_haras.guardian',"
                "'salamander.authority','kellogg','turing_universal_quantum_computer']]; "
                "assert all(Path(m.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()) "
                "for m in modules), 'foreign/source import detected'"
            )
            run("installed module origins", [python, "-I", "-c", origin], consumers)
            junit = output / "installed-capability.xml"
            run(
                "real installed capability consumers",
                [
                    python,
                    "-I",
                    "-m",
                    "pytest",
                    "-c",
                    os.devnull,
                    "--confcutdir=" + str(consumers),
                    "-q",
                    consumers,
                    "--junitxml=" + str(junit),
                ],
                consumers,
            )
            report["junit_sha256"] = digest(junit)
        report["status"] = "passed"
    except Exception as exc:
        report["status"] = "failed"
        report["failure"] = {"type": type(exc).__name__, "reason": str(exc)}
    (output / "capability-installation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "release_approved": False}))
    return 0 if report["status"] == "passed" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "platform-wheel",
        "turing-wheel",
        "kellogg-wheel",
        "research-requirements",
        "platform-requirements",
        "consumer-tests",
        "output",
    ):
        parser.add_argument("--" + name, type=lambda p: Path(p).resolve(), required=True)
    return qualify(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
