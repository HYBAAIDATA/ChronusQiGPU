#!/usr/bin/env python3
"""Digest-bound release manifest generator.

Walks the shared findlinks dir (and optional extra dirs), records every
wheel/sdist sha256, pulls any co-located artifact-verdict.json /
wheel-manifest.json evidence, and emits a single release manifest JSON.
This is the artifact identity record the RC freeze and CI dispatch bind to —
it never asserts publishability; that stays bound to executed CI verdicts.

Usage:
  python3 release_manifest.py --out artifacts/release-manifest.json \
      /tmp/pythia-dist packaging/*/dist packages/*/dist
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def git_sha(repo: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
        ).strip()
    except Exception:
        return "UNAVAILABLE"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+", help="directories to scan for artifacts")
    ap.add_argument("--out", required=True)
    ap.add_argument("--repo", default=".")
    args = ap.parse_args()

    artifacts = []
    seen = set()
    for d in args.dirs:
        d = Path(d)
        if not d.is_dir():
            continue
        for f in sorted(d.iterdir()):
            if f.suffix not in (".whl", ".gz") or f.name in seen:
                continue
            if f.suffix == ".gz" and not f.name.endswith(".tar.gz"):
                continue
            seen.add(f.name)
            artifacts.append({
                "file": str(f),
                "name": f.name,
                "sha256": sha256(f),
                "bytes": f.stat().st_size,
            })

    evidence = {}
    for d in args.dirs:
        for name in ("artifact-verdict.json", "wheel-manifest.json"):
            p = Path(d) / name
            if p.is_file():
                evidence[f"{d}/{name}"] = json.loads(p.read_text())

    manifest = {
        "schema": "hyba.release-manifest/1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_revision": git_sha(Path(args.repo)),
        "artifacts": artifacts,
        "artifact_count": len(artifacts),
        "evidence_files": evidence,
        "publishable": False,
        "note": "Identity record only. publishable flips per-distribution only "
                "via executed CI verdict bound to these exact sha256 digests.",
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    print(json.dumps({"artifacts": len(artifacts), "out": str(out)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
