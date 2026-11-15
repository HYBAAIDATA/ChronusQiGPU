"""Release publication must never infer qualification from CI green."""
import pytest

from chronus.core.qualification import MANDATORY
from scripts.ci.require_release_qualification import (
    ReleaseBlocked, check_verdict, select_run,
)


def valid_verdict():
    return {
        "status": "PASS", "blockers": [],
        "attestation_verified": True, "test_suite_pass": True,
        "gates": {gate: "PASS" for gate in MANDATORY},
        "claims": {"CO-001": "supported"},
    }


def test_mandatory_gates_are_enforced_without_waivers():
    check_verdict(valid_verdict())
    for change in (
        {"status": "UNQUALIFIED"},
        {"blockers": ["ML-DSA-65 unavailable"]},
        {"attestation_verified": False},
        {"test_suite_pass": False},
        {"gates": {}},
        {"claims": {"CO-001": "held"}},
    ):
        verdict = {**valid_verdict(), **change}
        with pytest.raises(ReleaseBlocked):
            check_verdict(verdict)


def test_missing_or_invalid_verdict_fails_closed():
    for verdict in (None, {}, [], {"status": "PASS"}):
        with pytest.raises(ReleaseBlocked):
            check_verdict(verdict)


def test_exact_push_main_commit_required_for_release():
    sha = "a" * 40
    good = {
        "id": 123, "head_sha": sha, "event": "push", "head_branch": "main",
        "path": ".github/workflows/chronus-evidence-qualification.yml",
        "status": "completed", "conclusion": "success",
    }
    assert select_run({"workflow_runs": [good]}, sha) == 123
    for alteration in (
        {"head_sha": "b" * 40}, {"event": "pull_request"},
        {"head_branch": "feature"}, {"conclusion": "failure"},
        {"path": ".github/workflows/ci.yml"}, {"status": "in_progress"},
    ):
        with pytest.raises(ReleaseBlocked):
            select_run({"workflow_runs": [{**good, **alteration}]}, sha)
