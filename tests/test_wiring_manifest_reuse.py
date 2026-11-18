"""Manifest reuse never trusts stale source hashes or paths outside the bundle."""
import hashlib
import json
import os
from pathlib import Path

import pytest

from chronus.wiring import FileEntry, _already_wired, build_wiring_plan


def _entry(path: Path, rel: str = "module.py") -> FileEntry:
    data = path.read_bytes()
    return FileEntry(
        rel_path=Path(rel),
        abs_path=path,
        kind="py",
        size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        source_root="root",
    )


def _manifest(bundle: Path, rel: str, content: bytes) -> None:
    bundle.mkdir(exist_ok=True)
    (bundle / "__wiring_manifest.json").write_text(
        json.dumps({"files": {rel: {
            "size": len(content), "sha256": hashlib.sha256(content).hexdigest(),
        }}}), encoding="utf-8"
    )


def test_identical_source_and_bundle_are_reused(tmp_path):
    source = tmp_path / "source.py"
    source.write_bytes(b"same")
    bundle = tmp_path / "wired"
    bundle.mkdir()
    (bundle / "module.py").write_bytes(b"same")
    _manifest(bundle, "module.py", b"same")
    entry = _entry(source)
    assert _already_wired([entry], bundle) == ([entry], [])
    assert build_wiring_plan([entry], bundle).already_wired == [entry]


def test_stale_manifest_cannot_mark_changed_source_as_wired(tmp_path):
    source = tmp_path / "source.py"
    source.write_bytes(b"new-data")
    bundle = tmp_path / "wired"
    bundle.mkdir()
    (bundle / "module.py").write_bytes(b"old-data")
    _manifest(bundle, "module.py", b"old-data")
    entry = _entry(source)
    assert _already_wired([entry], bundle) == ([], [entry])
    assert build_wiring_plan([entry], bundle).canonical == [entry]


def test_manifest_parent_escape_is_never_trusted(tmp_path):
    source = tmp_path / "outside.py"
    source.write_bytes(b"escape")
    bundle = tmp_path / "wired"
    _manifest(bundle, "../outside.py", b"escape")
    entry = _entry(source, rel="../outside.py")
    assert _already_wired([entry], bundle) == ([], [entry])


def test_manifest_symlink_escape_is_never_trusted(tmp_path):
    if os.name == "nt":
        pytest.skip("Windows symlink creation requires SeCreateSymbolicLinkPrivilege")
    source = tmp_path / "source.py"
    source.write_bytes(b"escape")
    outside = tmp_path / "outside.py"
    outside.write_bytes(b"escape")
    bundle = tmp_path / "wired"
    bundle.mkdir()
    (bundle / "module.py").symlink_to(outside)
    _manifest(bundle, "module.py", b"escape")
    entry = _entry(source)
    assert _already_wired([entry], bundle) == ([], [entry])


def test_manifest_self_referencing_symlink_is_not_reused(tmp_path):
    if os.name == "nt":
        pytest.skip("Windows symlink creation requires SeCreateSymbolicLinkPrivilege")
    source = tmp_path / "source.py"
    source.write_bytes(b"self-loop")
    bundle = tmp_path / "wired"
    bundle.mkdir()
    (bundle / "module.py").symlink_to("module.py")
    _manifest(bundle, "module.py", b"self-loop")
    entry = _entry(source)
    assert _already_wired([entry], bundle) == ([], [entry])
    assert build_wiring_plan([entry], bundle).canonical == [entry]


def test_manifest_non_mapping_root_is_ignored(tmp_path):
    source = tmp_path / "source.py"
    source.write_bytes(b"source")
    bundle = tmp_path / "wired"
    bundle.mkdir()
    (bundle / "module.py").write_bytes(b"source")
    entry = _entry(source)
    for invalid_root in ("[]", "null", "42", '"string"'):
        (bundle / "__wiring_manifest.json").write_text(invalid_root, encoding="utf-8")
        assert _already_wired([entry], bundle) == ([], [entry])
        assert build_wiring_plan([entry], bundle).canonical == [entry]


def test_in_bundle_symlink_alias_is_rejected(tmp_path):
    if os.name == "nt":
        pytest.skip("Windows symlink creation requires SeCreateSymbolicLinkPrivilege")
    source = tmp_path / "source.py"
    source.write_bytes(b"matching")
    bundle = tmp_path / "wired"
    bundle.mkdir()
    (bundle / "other.py").write_bytes(b"matching")
    (bundle / "module.py").symlink_to("other.py")
    _manifest(bundle, "module.py", b"matching")
    entry = _entry(source)
    assert _already_wired([entry], bundle) == ([], [entry])


def test_symlinked_bundle_ancestor_is_rejected(tmp_path):
    if os.name == "nt":
        pytest.skip("Windows symlink creation requires SeCreateSymbolicLinkPrivilege")
    source = tmp_path / "source.py"
    source.write_bytes(b"matching")
    bundle = tmp_path / "wired"
    bundle.mkdir()
    real = bundle / "real"
    real.mkdir()
    (real / "module.py").write_bytes(b"matching")
    (bundle / "nested").symlink_to("real", target_is_directory=True)
    _manifest(bundle, "nested/module.py", b"matching")
    entry = _entry(source, rel="nested/module.py")
    assert _already_wired([entry], bundle) == ([], [entry])
