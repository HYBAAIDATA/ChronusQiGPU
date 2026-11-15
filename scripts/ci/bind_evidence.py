#!/usr/bin/env python3
"""Bind a smoke/order evidence artifact to commit, host, timestamp, exit code.

Writes ``<artifact>.sidecar.json`` next to the artifact and appends a
``sha256  <relative-path>`` line to ``evidence/<area>/INDEX.sha256``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _git_head() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip()
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bind(artifact: Path, *, exit_code: int, host: str | None = None) -> Path:
    artifact = artifact.resolve()
    if not artifact.is_file():
        raise FileNotFoundError(artifact)
    try:
        rel = artifact.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError(f"artifact must live under {ROOT}") from exc

    sidecar = artifact.with_suffix(artifact.suffix + ".sidecar.json")
    if artifact.suffix == ".json":
        sidecar = Path(str(artifact) + ".sidecar.json")
    payload = {
        "artifact": str(rel).replace("\\", "/"),
        "commit": _git_head(),
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "host": host or platform.node(),
        "exit_code": int(exit_code),
        "sha256": _sha256(artifact),
    }
    sidecar.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    index = artifact.parent / "INDEX.sha256"
    line = f"{payload['sha256']}  {artifact.name}\n"
    existing = index.read_text(encoding="utf-8") if index.exists() else ""
    lines = [row for row in existing.splitlines() if row.strip() and not row.endswith(f"  {artifact.name}")]
    lines.append(line.rstrip("\n"))
    index.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return sidecar


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path, help="path to evidence file under the repo")
    parser.add_argument("--exit-code", type=int, required=True)
    parser.add_argument("--host", default=None)
    args = parser.parse_args(argv)
    sidecar = bind(args.artifact, exit_code=args.exit_code, host=args.host)
    print(f"bound {args.artifact} → {sidecar}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
