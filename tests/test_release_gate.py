"""Release publication must never infer qualification from CI green."""
import pytest

from chronus.core.qualification import MANDATORY
from chronus.core.claims import CLAIM_GATES
from scripts.ci.require_release_qualification import (
    ReleaseBlocked, check_verdict, select_run,
)


def valid_verdict():
    return {
        "status": "PASS", "blockers": [],
        "attestation_verified": True, "test_suite_pass": True,
        "gates": {gate: "PASS" for gate in MANDATORY},
        "claims": {claim: "supported" for claim in CLAIM_GATES},
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
        {"claims": {"CO-001": "supported"}},
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
        "id": 123, "run_attempt": 1, "head_sha": sha, "event": "push", "head_branch": "main",
        "path": ".github/workflows/chronus-evidence-qualification.yml",
        "status": "completed", "conclusion": "success",
    }
    assert select_run({"workflow_runs": [good]}, sha) == 123
    assert select_run(
        {"workflow_runs": [{**good, "path": good["path"] + "@main"}]}, sha
    ) == 123
    assert select_run(
        {"workflow_runs": [{**good, "path": good["path"] + "@refs/heads/main"}]},
        sha,
    ) == 123
    for alteration in (
        {"head_sha": "b" * 40}, {"event": "pull_request"},
        {"head_branch": "feature"}, {"conclusion": "failure"},
        {"path": ".github/workflows/ci.yml"}, {"status": "in_progress"},
    ):
        with pytest.raises(ReleaseBlocked):
            select_run({"workflow_runs": [{**good, **alteration}]}, sha)


def test_attestation_path_enforces_exact_identity(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    from scripts.ci import require_release_qualification as gate

    sha = "a" * 40
    calls = []
    run = {
        "id": 123, "run_attempt": 1, "head_sha": sha, "event": "push",
        "head_branch": "main", "status": "completed",
        "conclusion": "success",
        "path": gate._WORKFLOW + "@main",
    }

    def fake_call(*args):
        calls.append(args)
        if args[:2] == ("gh", "--version"):
            return "gh version 2.102.0"
        if args[:2] == ("gh", "api"):
            return json.dumps({"workflow_runs": [run]})
        if args[:3] == ("gh", "run", "download"):
            Path(args[args.index("--dir") + 1], "ci-verdict.json").write_text(
                json.dumps(valid_verdict()), encoding="utf-8"
            )
            return ""
        if args[:3] == ("gh", "attestation", "verify"):
            assert "--signer-workflow" in args
            assert "--source-digest" in args
            assert args[args.index("--source-digest") + 1] == sha
            assert args[args.index("--source-ref") + 1] == "refs/heads/main"
            assert args[args.index("--format") + 1] == "json"
            return json.dumps([{"verificationResult": {"signature": {"certificate": {
                "runInvocationURI": "https://github.com/HYBAAIDATA/ChronusQiGPU/actions/runs/123/attempts/1",
            }}}}])
        raise AssertionError(f"unexpected command {args!r}")

    monkeypatch.setattr(gate, "call", fake_call)
    saved = tmp_path / "qualification-evidence" / "ci-verdict.json"
    provenance = tmp_path / "qualification-evidence" / "attestation-verification-receipt.json"
    assert gate.verify_release(
        "HYBAAIDATA/ChronusQiGPU", sha,
        verified_verdict_output=str(saved), provenance_output=str(provenance),
    ) == 123
    assert json.loads(saved.read_bytes()) == valid_verdict()
    receipt = json.loads(provenance.read_text(encoding="utf-8"))
    assert receipt["source_commit"] == sha
    assert receipt["qualifying_run_id"] == 123
    assert receipt["repository"] == "HYBAAIDATA/ChronusQiGPU"
    assert receipt["attestation_verified"] is True
    assert any(args[:3] == ("gh", "attestation", "verify") for args in calls)


def test_missing_or_rejected_attestation_fails_closed(monkeypatch):
    import json
    from pathlib import Path
    from scripts.ci import require_release_qualification as gate

    sha = "b" * 40
    run = {
        "id": 234, "run_attempt": 1, "head_sha": sha, "event": "push",
        "head_branch": "main", "status": "completed",
        "conclusion": "success", "path": gate._WORKFLOW + "@main",
    }

    for variant in ("missing", "rejected", "tampered", "other-run"):
        def fake_call(*args):
            if args[:2] == ("gh", "--version"):
                return "gh version 2.102.0"
            if args[:2] == ("gh", "api"):
                return json.dumps({"workflow_runs": [run]})
            if args[:3] == ("gh", "run", "download"):
                if variant != "missing":
                    verdict = valid_verdict()
                    if variant == "tampered":
                        verdict["status"] = "UNQUALIFIED"
                    Path(args[args.index("--dir") + 1], "ci-verdict.json").write_text(
                        json.dumps(verdict), encoding="utf-8"
                    )
                return ""
            if args[:3] == ("gh", "attestation", "verify"):
                if variant in ("rejected", "tampered"):
                    raise ReleaseBlocked("missing or invalid attestation")
                return json.dumps([{"verificationResult": {"signature": {"certificate": {
                    "runInvocationURI": (
                        "https://github.com/HYBAAIDATA/ChronusQiGPU/actions/runs/"
                        + ("999" if variant == "other-run" else "234")
                        + "/attempts/1"
                    ),
                }}}}])
            raise AssertionError(f"unexpected command {args!r}")

        monkeypatch.setattr(gate, "call", fake_call)
        with pytest.raises(ReleaseBlocked):
            gate.verify_release("HYBAAIDATA/ChronusQiGPU", sha)


def test_manual_release_workflow_is_guarded():
    from pathlib import Path
    workflow = Path(__file__).resolve().parents[1] / ".github/workflows/release.yml"
    content = workflow.read_text(encoding="utf-8")
    assert "github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')" in content
