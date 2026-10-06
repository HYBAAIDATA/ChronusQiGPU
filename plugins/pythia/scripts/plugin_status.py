"""Runtime provenance for the private repo-local PYTHIA Devin plugin.

The receipt is deliberately local under artifacts/ (gitignored). It proves that
the plugin code actually ran in a Devin workspace without committing session
scratch or secrets. Consumers can quote the receipt in PR evidence.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
PLUGIN_ROOT = ROOT / "plugins" / "pythia"
MANIFEST = PLUGIN_ROOT / ".devin-plugin" / "plugin.json"
JOURNAL = ROOT / "artifacts" / "pythia" / "devin-checkpoint.jsonl"
RECEIPT = ROOT / "artifacts" / "pythia" / "devin-plugin-runtime.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _git(*args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return "UNAVAILABLE"
    return proc.stdout.strip() or "UNAVAILABLE"


def _manifest() -> dict[str, Any]:
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _available_skills() -> list[str]:
    skills = PLUGIN_ROOT / "skills"
    if not skills.is_dir():
        return []
    return sorted(
        path.parent.name
        for path in skills.glob("*/SKILL.md")
        if path.is_file()
    )


def _journal_state() -> tuple[int, dict[str, Any] | None]:
    if not JOURNAL.is_file():
        return 0, None
    lines = [line.strip() for line in JOURNAL.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return 0, None
    try:
        last = json.loads(lines[-1])
    except json.JSONDecodeError:
        last = {"_malformed_tail": lines[-1][:400]}
    return len(lines), last


def _existing_receipt() -> dict[str, Any]:
    if not RECEIPT.is_file():
        return {}
    try:
        return json.loads(RECEIPT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def build_status(*, event: str | None = None, record_skill: str | None = None) -> dict[str, Any]:
    manifest = _manifest()
    count, last = _journal_state()
    previous = _existing_receipt()
    invoked = set(previous.get("skills_invoked") or [])
    if record_skill:
        invoked.add(record_skill)
    hook_events = list(previous.get("hook_events") or [])
    if event and event not in hook_events:
        hook_events.append(event)

    source_sha = _git(
        "log",
        "-1",
        "--format=%H",
        "--",
        "plugins/pythia",
        ".devin/config.json",
    )
    return {
        "schema": "pythia.devin-plugin-runtime/1",
        "plugin": manifest.get("name", "pythia"),
        "plugin_version": manifest.get("version", "UNAVAILABLE"),
        "plugin_source_sha": source_sha,
        "workspace_head_sha": _git("rev-parse", "HEAD"),
        "generated_at": _now(),
        "private_repo_local": True,
        "available_skills": _available_skills(),
        "skills_invoked": sorted(invoked),
        "hook_events": hook_events,
        "journal_present": JOURNAL.is_file(),
        "checkpoint_count": count,
        "last_checkpoint": last,
        "memory_mode": (
            "checkpoint-assisted continuity; full PYTHIA working/episodic/"
            "semantic/archival memory requires explicit repository calls"
        ),
    }


def write_runtime_receipt(status: dict[str, Any]) -> None:
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    tmp = RECEIPT.with_suffix(".tmp")
    tmp.write_text(json.dumps(status, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp.replace(RECEIPT)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-receipt", action="store_true")
    parser.add_argument("--event")
    parser.add_argument("--record-skill")
    args = parser.parse_args()

    status = build_status(event=args.event, record_skill=args.record_skill)
    if args.write_receipt or args.event or args.record_skill:
        write_runtime_receipt(status)
    print(json.dumps(status, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
