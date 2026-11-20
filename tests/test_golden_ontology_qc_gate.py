"""Exercise the QC decision with a synthetic authenticated review and checkout."""
import hashlib
import json
from subprocess import CompletedProcess

import pytest

from governance import gate

pytestmark = pytest.mark.simulated


@pytest.fixture
def approval(tmp_path, monkeypatch):
    commit = "1" * 40
    evidence = f"https://github.com/{gate.REPO}/actions/runs/456"
    spec = b"reviewed specification\n"
    vectors = b'{"vectors": []}\n'
    (tmp_path / "spec").mkdir()
    (tmp_path / "spec/GOLDEN_ONTOLOGY.md").write_bytes(spec)
    (tmp_path / "spec/test_vectors.json").write_bytes(vectors)
    record = {
        "id": "QC-001",
        "title": "Independent QC",
        "status": "CLOSED",
        "owner": "release",
        "reviewer": "independent",
        "reviewed_commit": commit,
        "review_id": 123,
        "spec_sha256": hashlib.sha256(spec).hexdigest(),
        "vectors_sha256": hashlib.sha256(vectors).hexdigest(),
        "mismatch_count": 0,
        "evidence_url": evidence,
    }
    findings = {"package": "golden_ontology", "version": "2.0.0", "findings": [record]}
    responses = {
        "/pulls/207": {"user": {"login": "author"}},
        "/pulls/207/reviews/123": {
            "user": {"login": "Independent"},
            "state": "APPROVED",
            "commit_id": commit,
            "body": f"{evidence}\n{record['spec_sha256']}\n{record['vectors_sha256']}",
        },
    }
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setenv("GOLDEN_QC_REVIEWER", "independent")
    monkeypatch.setattr(gate, "_github", responses.__getitem__)
    monkeypatch.setattr(
        gate.subprocess, "run", lambda args, **kwargs: CompletedProcess(args, 0)
    )
    return findings, responses


def test_qc_accepts_matching_independent_approval(approval, capsys):
    findings, _ = approval
    (gate.ROOT / "FINDINGS.json").write_text(json.dumps(findings), encoding="utf-8")
    assert gate.main() == 0
    assert "QC gate passed" in capsys.readouterr().out


@pytest.mark.parametrize(
    "path, field, value",
    [
        ("/pulls/207", "user", {"login": "INDEPENDENT"}),
        ("/pulls/207/reviews/123", "user", {"login": "someone-else"}),
        ("/pulls/207/reviews/123", "commit_id", "2" * 40),
        ("/pulls/207/reviews/123", "state", "COMMENTED"),
    ],
)
def test_qc_rejects_nonmatching_approval(approval, path, field, value):
    findings, responses = approval
    responses[path][field] = value
    with pytest.raises(ValueError, match="no matching independent"):
        gate.validate(findings)


@pytest.mark.parametrize("missing_line", range(3), ids=["evidence", "spec", "vectors"])
def test_qc_approval_must_attest_each_piece_of_evidence(approval, missing_line):
    findings, responses = approval
    review = responses["/pulls/207/reviews/123"]
    lines = review["body"].splitlines()
    del lines[missing_line]
    review["body"] = "\n".join(lines)
    with pytest.raises(ValueError, match="review does not attest"):
        gate.validate(findings)


@pytest.mark.parametrize("path", ["spec/GOLDEN_ONTOLOGY.md", "spec/test_vectors.json"])
def test_qc_rechecks_file_digests_before_requesting_approval(approval, path):
    findings, responses = approval
    (gate.ROOT / path).write_bytes(b"changed after review")
    responses.clear()
    with pytest.raises(ValueError, match="review digest mismatch"):
        gate.validate(findings)


def test_qc_rejects_changes_to_reviewed_scope(approval, monkeypatch):
    findings, responses = approval
    responses.clear()

    def changed_scope(args, *, cwd, capture_output, check):
        assert cwd == gate.ROOT
        assert args[:5] == ["git", "diff", "--exit-code", "1" * 40, "--"]
        assert "golden_ontology" in args[5:]
        assert "src/chronus/research/golden_nature_reference.py" in args[5:]
        assert capture_output and not check
        return CompletedProcess(args, 1)

    monkeypatch.setattr(gate.subprocess, "run", changed_scope)
    with pytest.raises(ValueError, match="reviewed scope changed"):
        gate.validate(findings)


@pytest.mark.parametrize(
    "field, value, message",
    [
        ("review_id", True, "missing immutable review reference"),
        ("mismatch_count", False, "missing zero-mismatch reconstruction"),
        ("reviewer", "unprovisioned", "authorized independent reviewer not provisioned"),
    ],
)
def test_qc_rejects_invalid_register_even_with_valid_review(approval, field, value, message):
    findings, _ = approval
    findings["findings"][0][field] = value
    with pytest.raises(ValueError, match=message):
        gate.validate(findings)
