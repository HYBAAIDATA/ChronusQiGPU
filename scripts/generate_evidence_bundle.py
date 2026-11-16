"""Build an immutable, checksum-verified research evidence bundle.

This is collection of independently supplied evidence, not certification.
No synthetic measurement, auto-promotion or production-ready flag is created.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from zipfile import ZIP_STORED, ZipFile, ZipInfo

_SHA = re.compile(r"^[0-9a-f]{40}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_MAX_FILE = 32 * 1024 * 1024
_MAX_TOTAL = 128 * 1024 * 1024
_CLASSIFICATIONS = frozenset({"SOFTWARE_MEASUREMENT", "HISTORICAL_EVIDENCE", "RESEARCH_REFERENCE", "DEVICE_OPERATOR_DECLARED", "TEST_FIXTURE"})


def _read_git_sha(root: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()


def _archive_entry(name: str, data: bytes, archive: ZipFile) -> None:
    item = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    item.compress_type = ZIP_STORED
    item.external_attr = 0o600 << 16
    archive.writestr(item, data)


def build_bundle(root: Path, manifest: Path, output: Path, commit: str) -> dict:
    if not isinstance(commit, str) or not _SHA.fullmatch(commit):
        raise ValueError("exact 40-hex source commit required")
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("root must be a directory")
    manifest = manifest.resolve(strict=True)
    output = output.absolute()
    if output.exists():
        raise ValueError("output already exists")
    descriptor = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(descriptor, dict) or descriptor.get("schema") != "chronus.evidence-input-manifest/1" or descriptor.get("source_commit") != commit:
        raise ValueError("manifest source commit mismatch or unsupported schema")
    entries = descriptor.get("artifacts")
    if not isinstance(entries, list) or not 1 <= len(entries) <= 32:
        raise ValueError("1..32 evidence artifacts required")
    files = []
    seen = set()
    total = 0
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("artifact descriptor must be an object")
        relative, expected, kind = entry.get("path"), entry.get("sha256"), entry.get("classification")
        if (not isinstance(relative, str) or not relative or relative.startswith("/")
                or not isinstance(expected, str) or not _HASH.fullmatch(expected)
                or kind not in _CLASSIFICATIONS):
            raise ValueError("invalid path, digest or classification")
        parts = Path(relative).parts
        if ".." in parts or "" in parts or relative.startswith("\\"):
            raise ValueError("relative paths cannot escape the evidence root")
        source = root.joinpath(*parts)
        if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(root):
            raise ValueError("artifact must be a regular in-root file")
        if relative in seen or source.resolve() == manifest or source.resolve() == output:
            raise ValueError("duplicate or protected artifact")
        seen.add(relative)
        size = source.stat().st_size
        total += size
        if not 0 < size <= _MAX_FILE or total > _MAX_TOTAL:
            raise ValueError("evidence data exceeds policy")
        content = source.read_bytes()
        if len(content) != size or sha256(content).hexdigest() != expected:
            raise ValueError("evidence artifact SHA-256 mismatch")
        files.append((relative, content, expected, kind))
    records = [{"path": name, "sha256": digest, "size_bytes": len(data), "classification": kind}
               for name, data, digest, kind in sorted(files)]
    internal = {
        "schema": "chronus.evidence-collection/1",
        "source_commit": commit,
        "artifact_count": len(records),
        "artifacts": records,
        "production_qualified": False,
        "signed_or_attested": False,
        "limitations": "Byte-integrity collection only; no device authenticity, production or scientific claim promoted.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, mode="x", compression=ZIP_STORED) as zipf:
        for name, data, _, _ in sorted(files):
            _archive_entry("artifacts/" + name, data, zipf)
        _archive_entry("evidence-manifest.json", (json.dumps(internal, sort_keys=True, indent=2) + "\n").encode(), zipf)
    digest = sha256(output.read_bytes()).hexdigest()
    return {"bundle_sha256": digest, "output": str(output), **internal}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        actual = _read_git_sha(args.root)
        if actual != args.sha:
            raise ValueError("checked-out git SHA does not equal requested evidence SHA")
        report = build_bundle(args.root, args.manifest, args.output, args.sha)
        print(json.dumps({"output": report["output"], "bundle_sha256": report["bundle_sha256"], "production_qualified": False}))
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(json.dumps({"result":"INVALID_EVIDENCE", "error":str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
