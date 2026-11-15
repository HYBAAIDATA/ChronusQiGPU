"""Fail-closed release promotion based on an exact-commit signed CI verdict.

A green Actions run only proves the evidence processing completed. Publication
requires a separately attested PASS verdict and every mandatory gate.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

from chronus.core.qualification import MANDATORY

_WORKFLOW = ".github/workflows/chronus-evidence-qualification.yml"


class ReleaseBlocked(RuntimeError):
    """Publication has not met the evidence gate."""


def check_verdict(verdict: dict) -> None:
    if not isinstance(verdict, dict) or verdict.get("status") != "PASS":
        raise ReleaseBlocked("qualification verdict is not PASS")
    if verdict.get("blockers") != []:
        raise ReleaseBlocked("qualification blockers remain or were not reported")
    if verdict.get("attestation_verified") is not True:
        raise ReleaseBlocked("qualification evidence attestation is unverified")
    if verdict.get("test_suite_pass") is not True:
        raise ReleaseBlocked("qualification test suite is not verified PASS")
    gates = verdict.get("gates")
    if not isinstance(gates, dict) or any(gates.get(gate) != "PASS" for gate in MANDATORY):
        raise ReleaseBlocked("mandatory qualification gate is missing or not PASS")
    claims = verdict.get("claims")
    if not isinstance(claims, dict) or not claims or any(
        value != "supported" for value in claims.values()
    ):
        raise ReleaseBlocked("qualification claims are not independently supported")


def select_run(data: dict, commit: str) -> int:
    runs = data.get("workflow_runs", [])
    eligible = [
        run for run in runs
        if run.get("head_sha") == commit
        and run.get("event") == "push"
        and run.get("head_branch") == "main"
        and run.get("path") == _WORKFLOW
        and run.get("status") == "completed"
        and run.get("conclusion") == "success"
        and isinstance(run.get("id"), int)
    ]
    if not eligible:
        raise ReleaseBlocked("no successful main-branch qualification run for release commit")
    return max(eligible, key=lambda run: (run.get("run_started_at") or "", run["id"]))["id"]


def call(*args: str) -> str:
    completed = subprocess.run(
        args, check=False, capture_output=True, text=True, timeout=120
    )
    if completed.returncode != 0:
        raise ReleaseBlocked(f"verification command failed: {args[1:3]!r}: {completed.stderr.strip()}")
    return completed.stdout


def require_gh_cli_patched() -> None:
    match = re.search(r"gh version (\d+)\.(\d+)\.(\d+)", call("gh", "--version"))
    if not match or tuple(map(int, match.groups())) < (2, 102, 0):
        raise ReleaseBlocked("gh CLI 2.102.0 or newer is required for exact workflow verification")


def verify_release(repository: str, commit: str) -> int:
    if not re.fullmatch(r"[0-9a-fA-F]{40}", commit):
        raise ReleaseBlocked("invalid release commit identity")
    if not re.fullmatch(r"[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+", repository):
        raise ReleaseBlocked("invalid repository identity")
    require_gh_cli_patched()
    api_path = (
        f"repos/{repository}/actions/workflows/chronus-evidence-qualification.yml/runs"
        f"?head_sha={commit}&event=push&status=success&per_page=100"
    )
    run_id = select_run(json.loads(call("gh", "api", api_path)), commit)
    with tempfile.TemporaryDirectory(prefix="chronus-release-gate-") as folder:
        call("gh", "run", "download", str(run_id), "--repo", repository,
             "--name", "chronus-qualification-verdict", "--dir", folder)
        files = list(Path(folder).rglob("ci-verdict.json"))
        if len(files) != 1:
            raise ReleaseBlocked("missing or duplicate qualification verdict artifact")
        verdict_file = files[0]
        # The attestation binds these bytes to the named workflow, repository,
        # exact source commit and main ref. A downloaded JSON alone is never proof.
        call("gh", "attestation", "verify", str(verdict_file), "--repo", repository,
             "--signer-workflow", f"{repository}/{_WORKFLOW}",
             "--source-digest", commit, "--source-ref", "refs/heads/main")
        check_verdict(json.loads(verdict_file.read_text(encoding="utf-8")))
    print(f"Commit-matched, attested PASS qualification verified: {commit}")
    return run_id


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    try:
        verify_release(args.repository, args.commit)
    except (ReleaseBlocked, ValueError, OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        print(f"RELEASE BLOCKED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
