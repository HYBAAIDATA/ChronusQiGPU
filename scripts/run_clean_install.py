#!/usr/bin/env python3
"""Build, resolve, install offline and verify the enterprise wheel outside the repo."""

from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import venv

REPO = Path(__file__).resolve().parent.parent


def run(command, *, cwd, log):
    print("$", " ".join(map(str, command)), flush=True)
    completed = subprocess.run(
        list(map(str, command)),
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    with log.open("a", encoding="utf-8") as handle:
        handle.write("$ " + " ".join(map(str, command)) + "\n" + completed.stdout + "\n")
    print(completed.stdout, end="", flush=True)
    if completed.returncode:
        raise subprocess.CalledProcessError(completed.returncode, command)
    return completed.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--required-ancestor", default="4226a3c93ca2e045976e0e648ec4a66db064d5a4")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--wheelhouse", type=Path)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output == REPO or REPO.is_relative_to(output):
        raise ValueError("output may not contain the source repository")
    output.mkdir(parents=True, exist_ok=True)
    log = output / "terminal.log"
    log.write_text("")
    record = {
        "schema": "euclid.enterprise-acceptance/1",
        "passed": False,
        "expected_commit": args.expected_commit,
        "required_ancestor": args.required_ancestor,
    }
    evidence = output / "verification.json"
    evidence.write_text(json.dumps(record, indent=2))
    try:
        run(
            ["git", "merge-base", "--is-ancestor", args.required_ancestor, "HEAD"],
            cwd=REPO,
            log=log,
        )
        build = [
            sys.executable,
            REPO / "scripts/build_standalone_wheel.py",
            "--expected-commit",
            args.expected_commit,
            "--output-dir",
            output,
        ]
        if args.offline:
            build += ["--offline"]
        if args.wheelhouse:
            build += ["--wheelhouse", args.wheelhouse.resolve()]
        run(build, cwd=REPO, log=log)
        manifest = json.loads((output / "build-manifest.json").read_text())
        record["build"] = manifest
        for filename, expected in manifest["dependency_wheels"].items():
            if hashlib.sha256((output / filename).read_bytes()).hexdigest() != expected:
                raise ValueError("wheelhouse changed since build")
        wheel = output / manifest["wheel"]
        if hashlib.sha256(wheel.read_bytes()).hexdigest() != manifest["wheel_sha256"]:
            raise ValueError("enterprise artifact hash mismatch")
        verifier = REPO / "scripts/verify_clean_install.py"
        if hashlib.sha256(verifier.read_bytes()).hexdigest() != manifest["verifier_sha256"]:
            raise ValueError("verifier changed since build")
        with tempfile.TemporaryDirectory(prefix="euclid-clean-") as tmp:
            work = Path(tmp).resolve()
            if work.is_relative_to(REPO):
                raise ValueError("temporary environment must be outside checkout")
            environment = work / "venv"
            venv.EnvBuilder(with_pip=True, system_site_packages=False).create(environment)
            python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            outside = work / "empty"
            outside.mkdir()
            script = work / "verify_clean_install.py"
            shutil.copy2(verifier, script)
            run(
                [python, "-I", "-m", "pip", "install", "--no-index", "--find-links", output, wheel],
                cwd=outside,
                log=log,
            )
            run([python, "-I", "-m", "pip", "check"], cwd=outside, log=log)
            scoped = work / "tests"
            scoped.mkdir()
            tests = (
                "tests/test_empirical_state_bridge_hardening.py",
                "tests/test_unified_intelligence_consolidation.py",
                "tests/intelligence_consolidation/test_canonical_bridge.py",
            )
            for relative in tests:
                shutil.copy2(REPO / relative, scoped / Path(relative).name)
            record["installed_regressions"] = []
            for flags in ([], ["-O"]):
                for relative in tests:
                    test = scoped / Path(relative).name
                    command = [
                        python,
                        "-I",
                        *flags,
                        "-c",
                        "import runpy,sys; p=sys.argv.pop(1); runpy.run_path(p,run_name='__main__')",
                        test,
                    ]
                    stdout = run(command, cwd=outside, log=log)
                    record["installed_regressions"].append(
                        {
                            "test": relative,
                            "optimized": bool(flags),
                            "returncode": 0,
                            "output_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
                        }
                    )
            results = []
            for flags in ([], ["-O"]):
                command = [
                    python,
                    "-I",
                    *flags,
                    "-c",
                    "import runpy,sys; p=sys.argv.pop(1); runpy.run_path(p,run_name='__main__')",
                    script,
                    "--expected-commit",
                    args.expected_commit,
                    "--repo-root",
                    REPO,
                ]
                stdout = run(command, cwd=outside, log=log)
                result = json.loads(stdout.strip().splitlines()[-1])
                if result.get("passed") is not True:
                    raise ValueError("installed verifier did not pass")
                results.append(result)
            record["installed_results"] = results
            record["passed"] = True
    except Exception as exc:
        record["error_type"] = type(exc).__name__
        raise
    finally:
        record["terminal_log_sha256"] = hashlib.sha256(log.read_bytes()).hexdigest()
        evidence.write_text(json.dumps(record, indent=2, sort_keys=True))
        print(f"EVIDENCE={evidence}")


if __name__ == "__main__":
    main()
