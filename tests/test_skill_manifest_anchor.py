"""Graft manifests must be anchored outside the editable imported bundle."""

import hashlib
import json
from dataclasses import replace

import pytest

from Intelligence.skill_graft import Graft, verify_one


def manifest_digest(files):
    return hashlib.sha256(
        json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@pytest.fixture
def bundle(tmp_path):
    folder = tmp_path / "alpha"
    folder.mkdir()
    files = {"SKILL.md": b"approved guidance\n", "LICENSE": b"approved license\n"}
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    extras = (
        {"manifest_sha256": manifest_digest(hashes)}
        if "manifest_sha256" in Graft.__dataclass_fields__
        else {}
    )
    spec = Graft(
        "alpha",
        "https://example.invalid/reviewed",
        "a" * 40,
        "skills/alpha",
        "MIT",
        "LICENSE",
        ("repair",),
        **extras
    )
    for name, data in files.items():
        (folder / name).write_bytes(data)
    record = {
        "schema": "pythia.skill-graft/1",
        "name": "alpha",
        "repo": spec.repo,
        "commit": spec.commit,
        "path": spec.path,
        "licence": "MIT",
        "licence_file": "LICENSE",
        "applies_to": ["repair"],
        "files": hashes,
    }
    path = folder / "PROVENANCE.json"
    path.write_text(json.dumps(record))
    return folder, spec, record, path


def test_content_and_provenance_rewrite_cannot_forge_approval(bundle):
    folder, spec, record, path = bundle
    data = b"unreviewed replacement guidance\n"
    (folder / "SKILL.md").write_bytes(data)
    record["files"]["SKILL.md"] = hashlib.sha256(data).hexdigest()
    path.write_text(json.dumps(record))
    assert verify_one(folder, spec)


def test_missing_anchor_cannot_equip(bundle):
    folder, spec, _, _ = bundle
    assert verify_one(folder, replace(spec, manifest_sha256=""))


def test_routing_metadata_is_not_imported_authority(bundle):
    folder, spec, record, path = bundle
    record["applies_to"] = ["production-release"]
    path.write_text(json.dumps(record))
    assert verify_one(folder, spec)


@pytest.mark.parametrize("relative", ["../outside", "/outside", "a/../b", "a\\b", "a//b"])
def test_malformed_manifest_paths_rejected_before_read(bundle, relative):
    folder, spec, record, path = bundle
    record["files"][relative] = "0" * 64
    path.write_text(json.dumps(record))
    assert verify_one(folder, spec)


def test_non_object_provenance_is_rejected(bundle):
    folder, spec, _, path = bundle
    path.write_text("[]")
    assert verify_one(folder, spec)


def test_approved_content_is_accepted(bundle):
    folder, spec, _, _ = bundle
    assert verify_one(folder, spec) == []


@pytest.mark.parametrize("licence", [[], "SKILL.md"])
def test_license_pointer_cannot_be_rewritten(bundle, licence):
    folder, spec, record, path = bundle
    record["licence_file"] = licence
    path.write_text(json.dumps(record))
    assert verify_one(folder, spec)
