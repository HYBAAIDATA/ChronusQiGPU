"""Build deterministic recovery ZIPs without importing recovered application code."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import tempfile
import zipfile


def safe_path(name):
    """Accept only canonical relative POSIX paths rooted under hyba_data."""
    if not isinstance(name, str) or not name or "\\" in name or "\x00" in name:
        raise ValueError("Invalid artifact path")
    parts = name.split("/")
    if parts[0] != "hyba_data" or any(p in ("", ".", "..") or ":" in p for p in parts):
        raise ValueError("Unsafe artifact path: " + name)
    return PurePosixPath(name)


def build(manifest_path, source_root, output, allow_partial=False):
    """Package only indexed files; require explicit permission for incomplete recovery.

    source_root contains hyba_data/, not its contents. Unknown files are excluded.
    Existing recorded hashes are immutable recovery anchors, not signatures.
    New source bytes require separate review/secret scanning before publication.
    """
    manifest_path, source_root, output = map(Path, (manifest_path, source_root, output))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest["files"]
    if not isinstance(entries, list) or not entries:
        raise ValueError("Empty or invalid inventory")
    if manifest["expected_files"] != len(entries):
        raise ValueError("Inventory count mismatch")
    root = source_root.resolve(strict=True)
    output_resolved = output.resolve()
    seen, recovered, missing, payloads = set(), [], [], {}
    for entry in sorted(entries, key=lambda item: item["path"]):
        name = str(safe_path(entry["path"]))
        if name in seen:
            raise ValueError("Duplicate artifact path: " + name)
        seen.add(name)
        candidate = root.joinpath(*PurePosixPath(name).parts)
        relative = candidate.relative_to(root)
        cursor = root
        for part in relative.parts:
            cursor = cursor / part
            if cursor.is_symlink():
                raise ValueError("Symlink artifact refused: " + name)
        if candidate.resolve() == output_resolved:
            raise ValueError("Output would overwrite a source artifact")
        if not candidate.exists():
            missing.append(name)
            continue
        if not candidate.is_file():
            raise ValueError("Artifact is not a regular file: " + name)
        data = candidate.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if entry.get("sha256") and entry["sha256"] != digest:
            raise ValueError("Source hash mismatch: " + name)
        payloads[name] = data
        recovered.append({"path": name, "sha256": digest, "size_bytes": len(data),
                          "source_page": entry.get("source_page")})
    if missing and not allow_partial:
        raise ValueError(f"Incomplete recovery: {len(missing)} artifacts missing")
    report = {"schema_version": 1, "complete": not missing,
              "expected_files": len(entries), "included_files": len(recovered),
              "missing_files": missing, "files": recovered,
              "qualification": "Byte inventory only; not runtime or security qualification."}
    payloads["RECOVERY_MANIFEST.json"] = (
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replacement: failed validation or writing does not replace an existing ZIP.
    with tempfile.NamedTemporaryFile(dir=output.parent, delete=False) as handle:
        temporary = Path(handle.name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as archive:
            for name, data in sorted(payloads.items()):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                archive.writestr(info, data)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path,
                        default=Path(__file__).with_name("manifest.json"))
    parser.add_argument("--source-root", type=Path,
                        default=Path(__file__).with_name("source"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    try:
        report = build(args.manifest, args.source_root, args.output, args.allow_partial)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"Recovery refused: {error}\n")
    print(json.dumps({key: report[key] for key in
                      ("complete", "expected_files", "included_files")}))


if __name__ == "__main__":
    main()
