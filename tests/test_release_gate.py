"""Release publication must require exact-current CI and profile-scoped PASS."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chronus.core.claims import SOFTWARE_BASE_REQUIRED_CLAIMS
from chronus.core.qualification import MANDATORY
from scripts.ci.require_release_qualification import (
    ReleaseBlocked,
    check_verdict,
    select_run,
)


def valid_verdict(profile="software-base"):
    external = profile != "software-base"
    claims = {
        "CO-001": "supported",
        "CO-002": "supported",
        "RS-001": "supported",
        "RS-002": "supported",
        "FN-001": "supported" if external else "held",
    }
    return {
        "status": "PASS",
        "blockers": [],
        "attestation_verified": True,
        "test_evidence_attestation_verified": True,
        "gate_attestation_verified": True,
        "production_evidence_verified": True,
        "test_suite_pass": True,
        "product_gate_status": "PASS",
        "deployment_profile": profile,
        "product_facts": {
            "profile": {"name": profile, "verified": True},
            "post_quantum_signer": {
                "algorithm": "ML-DSA-65",
                "verified": True,
            },
            "custody": {
                "authority": "THESEUS",
                "mechanism": "sqlite-wal" if not external else "external-provider",
                "profile": profile,
                "verified": True,
                "external_customer_key_custody": external,
            },
        },
        "gates": {gate: "PASS" for gate in MANDATORY},
        "claims": claims,
    }


def test_software_base_release_does_not_promote_external_custody_claim():
    verdict = valid_verdict()
    check_verdict(verdict)
    assert verdict["claims"]["FN-001"] == "held"
    assert all(
        verdict["claims"][claim] == "supported"
        for claim in SOFTWARE_BASE_REQUIRED_CLAIMS
    )


@pytest.mark.parametrize(
    "change",
    [
        {"status": "UNQUALIFIED"},
        {"blockers": ["gate open"]},
        {"test_evidence_attestation_verified": False},
        {"gate_attestation_verified": False},
        {"production_evidence_verified": False},
        {"test_suite_pass": False},
        {"product_gate_status": "UNQUALIFIED"},
        {"deployment_profile": None},
        {"gates": {}},
        {"product_facts": {}},
    ],
)
def test_missing_release_evidence_fails_closed(change):
    with pytest.raises(ReleaseBlocked):
        check_verdict({**valid_verdict(), **change})


def test_external_profile_requires_external_custody_fact():
    verdict = valid_verdict("enterprise")
    check_verdict(verdict)
    verdict["product_facts"]["custody"]["external_customer_key_custody"] = False
    with pytest.raises(ReleaseBlocked):
        check_verdict(verdict)


def test_exact_main_push_success_required_for_workflow():
    sha = "a" * 40
    workflow = ".github/workflows/ci.yml"
    good = {
        "id": 123,
        "run_attempt": 1,
        "head_sha": sha,
        "event": "push",
        "head_branch": "main",
        "path": workflow,
        "status": "completed",
        "conclusion": "success",
    }
    assert select_run({"workflow_runs": [good]}, sha, workflow) == 123
    for change in (
        {"head_sha": "b" * 40},
        {"event": "pull_request"},
        {"head_branch": "feature"},
        {"conclusion": "failure"},
        {"status": "in_progress"},
        {"path": ".github/workflows/release.yml"},
    ):
        with pytest.raises(ReleaseBlocked):
            select_run({"workflow_runs": [{**good, **change}]}, sha, workflow)


def test_attestation_path_requires_ci_and_qualification_runs(tmp_path, monkeypatch):
    from scripts.ci import require_release_qualification as gate

    sha = "c" * 40
    ci_run = {
        "id": 100,
        "run_attempt": 1,
        "head_sha": sha,
        "event": "push",
        "head_branch": "main",
        "path": gate._CI_WORKFLOW,
        "status": "completed",
        "conclusion": "success",
    }
    qual_run = {
        "id": 200,
        "run_attempt": 2,
        "head_sha": sha,
        "event": "push",
        "head_branch": "main",
        "path": gate._QUAL_WORKFLOW,
        "status": "completed",
        "conclusion": "success",
    }

    def fake_call(*args):
        if args[:2] == ("gh", "--version"):
            return "gh version 2.102.0"
        if args[:2] == ("gh", "api"):
            path = args[2]
            if "ci.yml" in path:
                return json.dumps({"workflow_runs": [ci_run]})
            return json.dumps({"workflow_runs": [qual_run]})
        if args[:3] == ("gh", "run", "download"):
            Path(args[args.index("--dir") + 1], "ci-verdict.json").write_text(
                json.dumps(valid_verdict()),
                encoding="utf-8",
            )
            return ""
        if args[:3] == ("gh", "attestation", "verify"):
            return json.dumps(
                [
                    {
                        "verificationResult": {
                            "signature": {
                                "certificate": {
                                    "runInvocationURI": (
                                        "https://github.com/HYBAAIDATA/ChronusQiGPU/"
                                        "actions/runs/200/attempts/2"
                                    )
                                }
                            }
                        }
                    }
                ]
            )
        raise AssertionError(f"unexpected command {args!r}")

    monkeypatch.setattr(gate, "call", fake_call)
    verified = tmp_path / "qualification-evidence" / "ci-verdict.json"
    provenance = tmp_path / "qualification-evidence" / "receipt.json"
    assert gate.verify_release(
        "HYBAAIDATA/ChronusQiGPU",
        sha,
        verified_verdict_output=str(verified),
        provenance_output=str(provenance),
    ) == (100, 200)
    assert json.loads(verified.read_text())["status"] == "PASS"
    receipt = json.loads(provenance.read_text())
    assert receipt["ci_run_id"] == 100
    assert receipt["qualification_run_id"] == 200
    assert receipt["qualification_attestation_verified"] is True
