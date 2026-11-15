"""Manifest reuse never trusts stale source hashes or paths outside the bundle."""
import hashlib
import json
from pathlib import Path

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
    source = tmp_path / "source.py"
    source.write_bytes(b"self-loop")
    bundle = tmp_path / "wired"
    bundle.mkdir()
    (bundle / "module.py").symlink_to("module.py")
    _manifest(bundle, "module.py", b"self-loop")
    entry = _entry(source)
    assert _already_wired([entry], bundle) == ([], [entry])
    assert build_wiring_plan([entry], bundle).canonical == [entry]
