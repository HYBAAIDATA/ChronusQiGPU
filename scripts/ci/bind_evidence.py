#!/usr/bin/env python3
"""Bind a smoke/order evidence artifact with separated run vs bind provenance.

Writes ``<artifact>.sidecar.json`` next to the artifact and appends a
``sha256  <name>`` line to ``INDEX.sha256``.

Execution fields (``execution_commit``, ``execution_started``, ``exit_code``,
``host``) come from the transcript when present. Bind-time fields
(``bound_commit``, ``bound_at``) record when this sidecar was written and must
not be mistaken for the smoke run's revision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
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


def _load_transcript(artifact: Path) -> dict:
    if artifact.suffix.lower() != ".json":
        return {}
    try:
        data = json.loads(artifact.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def bind(artifact: Path, *, exit_code: int | None = None, host: str | None = None) -> Path:
    artifact = artifact.resolve()
    if not artifact.is_file():
        raise FileNotFoundError(artifact)
    try:
        rel = artifact.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError(f"artifact must live under {ROOT}") from exc

    transcript = _load_transcript(artifact)
    execution_commit = transcript.get("git_commit")
    if not execution_commit:
        execution_commit = None  # do not invent a run commit at bind time
    execution_started = transcript.get("started")
    transcript_exit = transcript.get("exit_code")
    resolved_exit = (
        int(transcript_exit)
        if transcript_exit is not None
        else (int(exit_code) if exit_code is not None else None)
    )
    if resolved_exit is None:
        raise ValueError(
            "exit_code required via --exit-code or transcript['exit_code']"
        )

    sidecar = Path(str(artifact) + ".sidecar.json")
    payload = {
        "artifact": str(rel).replace("\\", "/"),
        "execution_commit": execution_commit,
        "execution_started": execution_started,
        "exit_code": resolved_exit,
        "host": host or transcript.get("host") or platform.node(),
        "sha256": _sha256(artifact),
        "bound_commit": _git_head(),
        "bound_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    sidecar.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    index = artifact.parent / "INDEX.sha256"
    line = f"{payload['sha256']}  {artifact.name}"
    existing = index.read_text(encoding="utf-8") if index.exists() else ""
    lines = [
        row
        for row in existing.splitlines()
        if row.strip() and not row.endswith(f"  {artifact.name}")
    ]
    lines.append(line)
    index.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return sidecar


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path, help="path to evidence file under the repo")
    parser.add_argument(
        "--exit-code",
        type=int,
        default=None,
        help="required when the transcript does not already record exit_code",
    )
    parser.add_argument("--host", default=None)
    args = parser.parse_args(argv)
    sidecar = bind(args.artifact, exit_code=args.exit_code, host=args.host)
    print(f"bound {args.artifact} → {sidecar}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
