"""Contract tests for an offline, non-certifying evidence collection archive."""
from hashlib import sha256
import json
from zipfile import ZipFile
import pytest
from scripts.generate_evidence_bundle import build_bundle

pytestmark = pytest.mark.real

SHA = "a" * 40


def prep(tmp_path, raw=b"actual file content"):
    folder = tmp_path / "inputs"
    folder.mkdir()
    (folder / "evidence.bin").write_bytes(raw)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "schema": "chronus.evidence-input-manifest/1",
        "source_commit": SHA,
        "artifacts": [{
            "path": "evidence.bin",
            "sha256": sha256(raw).hexdigest(),
            "classification": "RESEARCH_REFERENCE",
        }],
    }))
    return folder, manifest


def test_bundle_consistency_and_no_qualification(tmp_path):
    root, manifest = prep(tmp_path)
    out = tmp_path / "bundle.zip"
    report = build_bundle(root, manifest, out, SHA)
    assert not report["production_qualified"]
    assert report["bundle_sha256"] == sha256(out.read_bytes()).hexdigest()
    with ZipFile(out) as archive:
        assert archive.read("artifacts/evidence.bin") == b"actual file content"
        meta = json.loads(archive.read("evidence-manifest.json"))
        assert meta["source_commit"] == SHA and meta["signed_or_attested"] is False
    with pytest.raises(ValueError, match="already exists"):
        build_bundle(root, manifest, out, SHA)


def test_bad_hash_fails_before_bundle_creation(tmp_path):
    root, manifest = prep(tmp_path)
    (root / "evidence.bin").write_bytes(b"mutated")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        build_bundle(root, manifest, tmp_path / "out.zip", SHA)
    assert not (tmp_path / "out.zip").exists()


def test_bad_commit_fails_before_bundle_creation(tmp_path):
    root, manifest = prep(tmp_path)
    with pytest.raises(ValueError, match="source commit mismatch"):
        build_bundle(root, manifest, tmp_path / "out.zip", "b" * 40)


def test_path_escape_rejected(tmp_path):
    root, manifest = prep(tmp_path)
    data = json.loads(manifest.read_text())
    data["artifacts"][0]["path"] = "../manifest.json"
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="escape"):
        build_bundle(root, manifest, tmp_path / "out.zip", SHA)
