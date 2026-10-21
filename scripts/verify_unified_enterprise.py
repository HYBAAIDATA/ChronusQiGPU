"""Execute the unified suites and retain source-bound evidence, including failures.

This is test evidence, never an enterprise production certification.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/unified-enterprise")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    junit = output / "junit.xml"
    # A failed invocation must never reuse an older passing XML file.
    junit.unlink(missing_ok=True)
    (output / "evidence.json").unlink(missing_ok=True)
    tests = sorted(ROOT.glob("tests/test_toe_unified*.py"))
    command = [sys.executable, "-m", "pytest", "-q", "--junitxml", str(junit)]
    command.extend(str(path.relative_to(ROOT)) for path in tests)
    started = datetime.now(timezone.utc).isoformat()
    try:
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        dirty = subprocess.run(["git", "diff", "--quiet", "HEAD", "--"], cwd=ROOT).returncode != 0
    except (OSError, subprocess.CalledProcessError):
        sha, dirty = None, True
    paths = sorted(
        {
            path
            for pattern in (
                "toe/**/*.py",
                "kellogg/**/*.py",
                "tests/test_toe_unified*.py",
                "tests/fixtures/toe_unified/**/*",
                "scripts/verify_unified_enterprise.py",
                ".github/workflows/unified-enterprise-contract.yml",
                "pyproject.toml",
            )
            for path in ROOT.glob(pattern)
            if path.is_file()
        }
    )
    manifest = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths
    }
    manifest_path = output / "source-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    with (output / "pytest.log").open("w") as log:
        completed = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    counts = {name: 0 for name in ("tests", "failures", "errors", "skipped")}
    if junit.exists():
        try:
            suites = ET.parse(junit).getroot()
            for suite in ([suites] if suites.tag == "testsuite" else suites.findall("testsuite")):
                for name in counts:
                    counts[name] += int(suite.get(name, "0"))
        except (ET.ParseError, ValueError):
            counts["errors"] += 1
    passed = (
        bool(tests)
        and completed.returncode == 0
        and counts["tests"] > 0
        and not any(counts[name] for name in ("failures", "errors", "skipped"))
    )
    evidence = {
        "schema": "hyba.unified.test-evidence/v1",
        "scope": "in-process unified enterprise contract",
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": sha,
        "tracked_worktree_dirty": dirty,
        "python": platform.python_version(),
        "command": command,
        "test_files": [str(p.relative_to(ROOT)) for p in tests],
        "pytest_exit_code": completed.returncode,
        "counts": counts,
        "test_verdict": "passed" if passed else "failed_or_incomplete",
        "production_certification": "not_assessed",
        "ci_run_url": (
            f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}"
            f"/actions/runs/{os.environ['GITHUB_RUN_ID']}"
            if all(
                os.environ.get(k)
                for k in ("GITHUB_SERVER_URL", "GITHUB_REPOSITORY", "GITHUB_RUN_ID")
            )
            else None
        ),
        "artifacts": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (manifest_path, output / "pytest.log", junit)
            if p.exists()
        },
        "limitations": [
            "Fixture and in-process scope; no live vendor certification.",
            "No production SLA, durability, external identity or business-outcome certification.",
            "Freshness and review must be checked for the release being promoted.",
        ],
    }
    (output / "evidence.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verdict": evidence["test_verdict"], "counts": counts, "git_sha": sha}))
    if not passed:
        print((output / "pytest.log").read_text()[-12000:])
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
