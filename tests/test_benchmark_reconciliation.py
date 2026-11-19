"""Benchmark reconciliation: actual byte integrity, exact SHA and fail-closed."""
import hashlib
import json
import pytest
from scripts.reconcile_benchmarks import reconcile

pytestmark = pytest.mark.real

SHA = "a" * 40


def case(tmp_path, artifact_sha=SHA, content=None):
    root = tmp_path / "root"
    root.mkdir(parents=True)
    artifact = root / "result.json"
    if content is None:
        content = {
            "schema": "chronus.reference/1",
            "source_commit": artifact_sha,
            "classification": "LOCAL_REFERENCE",
        }
    artifact.write_text(json.dumps(content), encoding="utf-8")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "schema": "chronus.benchmark.reconciliation-input/1",
        "source_commit": SHA,
        "artifacts": [{"path": "result.json", "sha256": digest}],
    }), encoding="utf-8")
    return root, manifest, artifact


def test_exact_file_and_commit_bound_without_production_promotion(tmp_path):
    root, manifest, _ = case(tmp_path)
    report = reconcile(root, manifest, SHA)
    assert report["all_source_bound"]
    assert report["artifacts"][0]["verdict"] == "EXACT_SOURCE_BOUND"
    assert not report["production_qualified"] and not report["independently_attested"]


def test_file_mutation_is_detected(tmp_path):
    root, manifest, artifact = case(tmp_path)
    artifact.write_text('{"injected":true}', encoding="utf-8")
    report = reconcile(root, manifest, SHA)
    assert not report["all_source_bound"]
    assert report["artifacts"][0]["verdict"] == "BYTE_HASH_MISMATCH"


def test_stale_embedded_commit_is_rejected(tmp_path):
    root, manifest, _ = case(tmp_path, artifact_sha="b" * 40)
    assert reconcile(root, manifest, SHA)["artifacts"][0]["verdict"] == "COMMIT_MISMATCH"


def test_missing_and_historical_unbound_never_count_as_pass(tmp_path):
    root, manifest, artifact = case(tmp_path)
    artifact.unlink()
    assert reconcile(root, manifest, SHA)["artifacts"][0]["verdict"] == "MISSING"
    root, manifest, _ = case(tmp_path / "other", content={"classification": "OLD"})
    assert reconcile(root, manifest, SHA)["artifacts"][0]["verdict"] == "UNBOUND_HISTORICAL"


def test_traversal_denied(tmp_path):
    root, manifest, _ = case(tmp_path)
    doc = json.loads(manifest.read_text())
    doc["artifacts"][0]["path"] = "../other"
    manifest.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="relative"):
        reconcile(root, manifest, SHA)
