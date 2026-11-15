"""Fail-closed release promotion from exact-commit CI and qualification evidence."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

from chronus.core.claims import required_claims_for_profile
from chronus.core.qualification import MANDATORY

_QUAL_WORKFLOW = ".github/workflows/chronus-evidence-qualification.yml"
_CI_WORKFLOW = ".github/workflows/ci.yml"


class ReleaseBlocked(RuntimeError):
    """Publication has not met the release evidence contract."""


def check_verdict(verdict: dict) -> None:
    if not isinstance(verdict, dict) or verdict.get("status") != "PASS":
        raise ReleaseBlocked("qualification verdict is not PASS")
    if verdict.get("blockers") != []:
        raise ReleaseBlocked("qualification blockers remain or were not reported")
    if verdict.get("test_evidence_attestation_verified") is not True:
        raise ReleaseBlocked("test-evidence attestation is unverified")
    if verdict.get("gate_attestation_verified") is not True:
        raise ReleaseBlocked("product-gate attestation is unverified")
    if verdict.get("production_evidence_verified") is not True:
        raise ReleaseBlocked("combined production evidence is unverified")
    if verdict.get("test_suite_pass") is not True:
        raise ReleaseBlocked("bounded qualification test suite is not PASS")
    if verdict.get("product_gate_status") != "PASS":
        raise ReleaseBlocked("executable product gates are not PASS")

    gates = verdict.get("gates")
    if not isinstance(gates, dict) or any(
        gates.get(gate) != "PASS" for gate in MANDATORY
    ):
        raise ReleaseBlocked("mandatory product gate is missing or not PASS")

    profile = verdict.get("deployment_profile")
    if not isinstance(profile, str) or not profile:
        raise ReleaseBlocked("qualified deployment profile is absent")

    facts = verdict.get("product_facts")
    if not isinstance(facts, dict):
        raise ReleaseBlocked("attested product facts are absent")
    profile_fact = facts.get("profile")
    if (
        not isinstance(profile_fact, dict)
        or profile_fact.get("name") != profile
        or profile_fact.get("verified") is not True
    ):
        raise ReleaseBlocked("profile fact is absent or unverified")

    signer = facts.get("post_quantum_signer")
    if (
        not isinstance(signer, dict)
        or signer.get("algorithm") != "ML-DSA-65"
        or signer.get("verified") is not True
    ):
        raise ReleaseBlocked("ML-DSA-65 software signing evidence is unavailable")

    custody = facts.get("custody")
    if (
        not isinstance(custody, dict)
        or custody.get("authority") != "THESEUS"
        or custody.get("profile") != profile
        or custody.get("verified") is not True
    ):
        raise ReleaseBlocked("qualified THESEUS custody fact is absent or unverified")
    if profile != "software-base" and custody.get("external_customer_key_custody") is not True:
        raise ReleaseBlocked(
            "deployment profile requires verified external customer-held custody"
        )

    claims = verdict.get("claims")
    if not isinstance(claims, dict):
        raise ReleaseBlocked("claim dispositions are absent")
    for claim in required_claims_for_profile(profile):
        if claims.get(claim) != "supported":
            raise ReleaseBlocked(f"required claim {claim} is not supported")


def _select_run_record(data: dict, commit: str, workflow: str) -> dict:
    eligible = [
        run
        for run in data.get("workflow_runs", [])
        if run.get("head_sha") == commit
        and run.get("event") == "push"
        and run.get("head_branch") == "main"
        and run.get("path")
        in {
            workflow,
            f"{workflow}@main",
            f"{workflow}@refs/heads/main",
        }
        and run.get("status") == "completed"
        and run.get("conclusion") == "success"
        and isinstance(run.get("id"), int)
        and isinstance(run.get("run_attempt"), int)
        and run["run_attempt"] >= 1
    ]
    if not eligible:
        raise ReleaseBlocked(
            f"no successful main-branch {workflow} run for release commit"
        )
    return max(
        eligible,
        key=lambda run: (run.get("run_started_at") or "", run["id"]),
    )


def select_run(data: dict, commit: str, workflow: str = _QUAL_WORKFLOW) -> int:
    return _select_run_record(data, commit, workflow)["id"]


def call(*args: str) -> str:
    completed = subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if completed.returncode != 0:
        raise ReleaseBlocked(
            f"verification command failed: {args[1:3]!r}: "
            f"{completed.stderr.strip()}"
        )
    return completed.stdout


def require_gh_cli_patched() -> None:
    match = re.search(r"gh version (\d+)\.(\d+)\.(\d+)", call("gh", "--version"))
    if not match or tuple(map(int, match.groups())) < (2, 102, 0):
        raise ReleaseBlocked(
            "gh CLI 2.102.0 or newer is required for exact workflow verification"
        )


def _successful_run(repository: str, commit: str, workflow: str) -> dict:
    api_path = (
        f"repos/{repository}/actions/workflows/{Path(workflow).name}/runs"
        f"?head_sha={commit}&event=push&status=success&per_page=100"
    )
    return _select_run_record(
        json.loads(call("gh", "api", api_path)),
        commit,
        workflow,
    )


def verify_release(
    repository: str,
    commit: str,
    *,
    verified_verdict_output: str | None = None,
    provenance_output: str | None = None,
) -> tuple[int, int]:
    if not re.fullmatch(r"[0-9a-fA-F]{40}", commit):
        raise ReleaseBlocked("invalid release commit identity")
    if not re.fullmatch(r"[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+", repository):
        raise ReleaseBlocked("invalid repository identity")

    require_gh_cli_patched()
    ci_run = _successful_run(repository, commit, _CI_WORKFLOW)
    qualification_run = _successful_run(repository, commit, _QUAL_WORKFLOW)

    run_id = qualification_run["id"]
    run_attempt = qualification_run["run_attempt"]
    expected_invocation = (
        f"https://github.com/{repository}/actions/runs/{run_id}"
        f"/attempts/{run_attempt}"
    )

    with tempfile.TemporaryDirectory(prefix="chronus-release-gate-") as folder:
        call(
            "gh",
            "run",
            "download",
            str(run_id),
            "--repo",
            repository,
            "--name",
            "chronus-qualification-verdict",
            "--dir",
            folder,
        )
        files = list(Path(folder).rglob("ci-verdict.json"))
        if len(files) != 1:
            raise ReleaseBlocked(
                "missing or duplicate qualification verdict artifact"
            )
        verdict_file = files[0]

        verification_output = call(
            "gh",
            "attestation",
            "verify",
            str(verdict_file),
            "--repo",
            repository,
            "--signer-workflow",
            f"{repository}/{_QUAL_WORKFLOW}",
            "--source-digest",
            commit,
            "--source-ref",
            "refs/heads/main",
            "--format",
            "json",
        )
        attestations = json.loads(verification_output)
        if not isinstance(attestations, list) or not any(
            isinstance(item, dict)
            and item.get("verificationResult", {})
            .get("signature", {})
            .get("certificate", {})
            .get("runInvocationURI")
            == expected_invocation
            for item in attestations
        ):
            raise ReleaseBlocked(
                "qualification verdict attestation does not match selected run"
            )

        verified_bytes = verdict_file.read_bytes()
        check_verdict(json.loads(verified_bytes))

        if verified_verdict_output is not None:
            destination = Path(verified_verdict_output)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(verified_bytes)

        if provenance_output is not None:
            destination = Path(provenance_output)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(
                json.dumps(
                    {
                        "repository": repository,
                        "source_commit": commit,
                        "source_ref": "refs/heads/main",
                        "ci_workflow": _CI_WORKFLOW,
                        "ci_run_id": ci_run["id"],
                        "ci_run_attempt": ci_run["run_attempt"],
                        "qualification_workflow": _QUAL_WORKFLOW,
                        "qualification_run_id": run_id,
                        "qualification_run_attempt": run_attempt,
                        "verified_run_invocation": expected_invocation,
                        "qualification_attestation_verified": True,
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

    print(
        "Exact-commit CI and attested PASS qualification verified: "
        f"{commit}"
    )
    return ci_run["id"], run_id


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--verified-verdict-output")
    parser.add_argument("--provenance-output")
    args = parser.parse_args()
    try:
        verify_release(
            args.repository,
            args.commit,
            verified_verdict_output=args.verified_verdict_output,
            provenance_output=args.provenance_output,
        )
    except (
        ReleaseBlocked,
        ValueError,
        OSError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
    ) as exc:
        print(f"RELEASE BLOCKED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
