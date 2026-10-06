"""Runtime provenance for the private Devin EUCLID-aptitude plugin.

The plugin identity/path remains pythia for installation compatibility.
The augmentation delivered to Devin is EUCLID-derived aptitude: the complete
repo-local plugin skill set plus the Intelligence/skills library is invoked at
SessionStart and remains active for the session.

Skill activation is session-scoped. Task evidence is separate.
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
INTELLIGENCE_SKILLS_ROOT = ROOT / "Intelligence" / "skills"
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


def _skill_names(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    return sorted(
        path.parent.name
        for path in root.glob("*/SKILL.md")
        if path.is_file()
    )


def plugin_skills() -> list[str]:
    return _skill_names(PLUGIN_ROOT / "skills")


def euclid_aptitude_skills() -> list[str]:
    return _skill_names(INTELLIGENCE_SKILLS_ROOT)


def mandatory_skills() -> list[str]:
    return sorted(
        {f"plugin:{name}" for name in plugin_skills()}
        | {f"euclid:{name}" for name in euclid_aptitude_skills()}
    )


def _journal_state() -> tuple[int, dict[str, Any] | None]:
    if not JOURNAL.is_file():
        return 0, None
    lines = [
        line.strip()
        for line in JOURNAL.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
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
        value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _normalise_skill(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("skill name is empty")
    if ":" in cleaned:
        return cleaned
    return f"plugin:{cleaned}"


def build_status(
    *,
    event: str | None = None,
    record_skill: str | None = None,
    invoke_all: bool = False,
) -> dict[str, Any]:
    manifest = _manifest()
    count, last = _journal_state()
    previous = _existing_receipt()
    mandatory = mandatory_skills()
    invoked = set(previous.get("skills_invoked") or [])

    if invoke_all:
        invoked.update(mandatory)
    if record_skill:
        invoked.add(_normalise_skill(record_skill))

    hook_events = list(previous.get("hook_events") or [])
    if event and event not in hook_events:
        hook_events.append(event)

    source_sha = _git(
        "log",
        "-1",
        "--format=%H",
        "--",
        "plugins/pythia",
        "Intelligence/skills",
        ".devin/config.json",
    )
    mandatory_set = set(mandatory)
    return {
        "schema": "euclid.devin-aptitude-runtime/1",
        "plugin": manifest.get("name", "pythia"),
        "plugin_version": manifest.get("version", "UNAVAILABLE"),
        "augmentation": "EUCLID_APTITUDE",
        "plugin_source_sha": source_sha,
        "workspace_head_sha": _git("rev-parse", "HEAD"),
        "generated_at": _now(),
        "private_repo_local": True,
        "plugin_skills": plugin_skills(),
        "euclid_aptitude_skills": euclid_aptitude_skills(),
        "mandatory_skills": mandatory,
        "skills_invoked": sorted(invoked),
        "mandatory_skills_complete": mandatory_set.issubset(invoked),
        "mandatory_skills_missing": sorted(mandatory_set - invoked),
        "hook_events": hook_events,
        "journal_present": JOURNAL.is_file(),
        "checkpoint_count": count,
        "last_checkpoint": last,
        "memory_mode": (
            "EUCLID aptitude and continuity are active session-wide; task-specific "
            "side effects remain bounded by the task and canonical authority."
        ),
    }


def write_runtime_receipt(status: dict[str, Any]) -> None:
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    tmp = RECEIPT.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(status, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp.replace(RECEIPT)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-receipt", action="store_true")
    parser.add_argument("--event")
    parser.add_argument("--record-skill")
    parser.add_argument("--invoke-all", action="store_true")
    args = parser.parse_args()

    status = build_status(
        event=args.event,
        record_skill=args.record_skill,
        invoke_all=args.invoke_all,
    )
    if args.write_receipt or args.event or args.record_skill or args.invoke_all:
        write_runtime_receipt(status)
    print(json.dumps(status, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
