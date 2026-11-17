#!/usr/bin/env python3
"""Reconcile actual benchmark artifacts to exact source bytes and commit.

No substitute data, invented benchmark pass, stale-SHA promotion, physical
device claim or production qualification is generated.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess

SCHEMA = "chronus.benchmark.reconciliation-input/1"
OUTPUT_SCHEMA = "chronus.benchmark.reconciliation/1"
_SHA = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_MAX_BYTES = 32 * 1024 * 1024


def reconcile(root: Path, manifest: Path, expected_sha: str) -> dict:
    """Check every supplied artifact's file hash, embedded SHA and existence."""
    if not isinstance(expected_sha, str) or not _SHA.fullmatch(expected_sha):
        raise ValueError("exact 40-hex source SHA required")
    root = Path(root).resolve(strict=True)
    manifest = Path(manifest)
    if manifest.is_symlink():
        raise ValueError("manifest symlink refused")
    manifest = manifest.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("benchmark root must be a directory")
    doc = json.loads(manifest.read_text(encoding="utf-8"))
    if (not isinstance(doc, dict) or doc.get("schema") != SCHEMA
            or doc.get("source_commit") != expected_sha):
        raise ValueError("reconciliation manifest schema or source commit mismatch")
    entries = doc.get("artifacts")
    if not isinstance(entries, list) or not 1 <= len(entries) <= 64:
        raise ValueError("1..64 benchmark artifacts required")
    seen: set[str] = set()
    checked = []
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("artifact descriptor must be an object")
        relative, digest = item.get("path"), item.get("sha256")
        if (not isinstance(relative, str) or not relative
                or not isinstance(digest, str) or not _DIGEST.fullmatch(digest)):
            raise ValueError("each artifact requires a path and complete SHA-256")
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or relative in seen:
            raise ValueError("artifact paths must be distinct and relative to root")
        seen.add(relative)
        source = root / path
        if source.is_symlink() or not source.resolve().is_relative_to(root):
            raise ValueError("artifact cannot be a symlink or leave the root")
        record = {
            "path": relative, "expected_sha256": digest,
            "observed_sha256": None, "source_commit": None,
            "classification": "UNAVAILABLE", "verdict": "MISSING",
        }
        if not source.is_file():
            checked.append(record)
            continue
        if source.stat().st_size > _MAX_BYTES:
            record["verdict"] = "OVERSIZE"
            checked.append(record)
            continue
        raw = source.read_bytes()
        record["observed_sha256"] = sha256(raw).hexdigest()
        if record["observed_sha256"] != digest:
            record["verdict"] = "BYTE_HASH_MISMATCH"
            checked.append(record)
            continue
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            record["verdict"] = "INVALID_JSON"
            checked.append(record)
            continue
        if not isinstance(payload, dict):
            record["verdict"] = "INVALID_JSON"
            checked.append(record)
            continue
        source_sha = payload.get("source_commit", payload.get("git_commit"))
        record["source_commit"] = source_sha
        record["classification"] = str(
            payload.get("classification", payload.get("status", "UNAVAILABLE"))
        )
        if source_sha is None:
            record["verdict"] = "UNBOUND_HISTORICAL"
        elif source_sha != expected_sha:
            record["verdict"] = "COMMIT_MISMATCH"
        else:
            record["verdict"] = "EXACT_SOURCE_BOUND"
        checked.append(record)
    return {
        "schema": OUTPUT_SCHEMA,
        "source_commit": expected_sha,
        "all_source_bound": bool(checked) and all(
            r["verdict"] == "EXACT_SOURCE_BOUND" for r in checked
        ),
        "artifact_count": len(checked), "artifacts": checked,
        "production_qualified": False,
        "independently_attested": False,
        "hardware_qualified": False,
        "claim_promotion": "NONE",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    out = args.output.resolve()
    if out.exists() or out == args.manifest.resolve():
        raise SystemExit("output must be new and distinct from manifest")
    actual = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=args.root, text=True,
    ).strip()
    if actual != args.expected_sha:
        raise SystemExit("checked-out Git SHA does not match expected SHA")
    result = reconcile(args.root, args.manifest, args.expected_sha)
    protected = {(args.root / r["path"]).resolve() for r in result["artifacts"]}
    if out in protected:
        raise SystemExit("output must not overwrite a benchmark artifact")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({
        "source_bound": result["all_source_bound"],
        "count": result["artifact_count"], "output": str(out),
    }))
    return 0 if result["all_source_bound"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
