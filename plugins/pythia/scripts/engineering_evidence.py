"""Tamper-evident engineering evidence for the private PYTHIA Devin plugin.

The local ledger records what the augmentation actually did. Sealed packs may
be published under evidence/devin/ and committed with the PR so the proof is
bound to repository history. A successful pack proves observed use and the
recorded engineering outcome; it does not by itself prove causal improvement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from plugin_status import ROOT, build_status, write_runtime_receipt

ARTIFACT_ROOT = ROOT / "artifacts" / "pythia"
EVENT_LOG = ARTIFACT_ROOT / "devin-engineering-evidence.jsonl"
DEFAULT_PUBLISH_ROOT = ROOT / "evidence" / "devin"
SCHEMA_EVENT = "pythia.devin-engineering-event/1"
SCHEMA_PACK = "pythia.devin-engineering-pack/1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _safe_task_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-")
    if not cleaned:
        raise ValueError("task_id must contain at least one safe character")
    return cleaned[:120]


def _read_events(path: Path = EVENT_LOG) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    events: list[dict[str, Any]] = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed evidence line {number}") from exc
        if not isinstance(event, dict):
            raise ValueError(f"evidence line {number} is not an object")
        events.append(event)
    return events


def verify_chain(events: Iterable[dict[str, Any]]) -> tuple[bool, str | None]:
    previous = "GENESIS"
    for index, event in enumerate(events, 1):
        if event.get("schema") != SCHEMA_EVENT:
            return False, f"event {index} has wrong schema"
        if event.get("sequence") != index:
            return False, f"event {index} has wrong sequence"
        if event.get("prev_event_sha256") != previous:
            return False, f"event {index} has wrong previous hash"
        claimed = event.get("event_sha256")
        unsigned = dict(event)
        unsigned.pop("event_sha256", None)
        actual = _sha256(_canonical(unsigned))
        if claimed != actual:
            return False, f"event {index} hash mismatch"
        previous = str(claimed)
    return True, None


def record_event(
    event_type: str,
    *,
    task_id: str,
    payload: dict[str, Any] | None = None,
    skill: str | None = None,
    path: Path = EVENT_LOG,
) -> dict[str, Any]:
    task_id = _safe_task_id(task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    events = _read_events(path)
    ok, reason = verify_chain(events)
    if not ok:
        raise ValueError(f"existing evidence ledger failed verification: {reason}")

    status = build_status()
    write_runtime_receipt(status)
    previous = events[-1]["event_sha256"] if events else "GENESIS"
    event: dict[str, Any] = {
        "schema": SCHEMA_EVENT,
        "sequence": len(events) + 1,
        "at": _now(),
        "event_type": event_type,
        "task_id": task_id,
        "plugin_version": status.get("plugin_version", "UNAVAILABLE"),
        "plugin_source_sha": status.get("plugin_source_sha", "UNAVAILABLE"),
        "workspace_head_sha": status.get("workspace_head_sha", "UNAVAILABLE"),
        "skill": skill,
        "payload": payload or {},
        "prev_event_sha256": previous,
    }
    event["event_sha256"] = _sha256(_canonical(event))
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")
    return event


def run_verification(task_id: str, command: list[str]) -> int:
    if not command:
        raise ValueError("verification command is required")
    started = _now()
    proc = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    payload = {
        "command": command,
        "started_at": started,
        "finished_at": _now(),
        "exit_code": proc.returncode,
        "stdout_sha256": _sha256(stdout.encode("utf-8", errors="replace")),
        "stderr_sha256": _sha256(stderr.encode("utf-8", errors="replace")),
        "stdout_tail": stdout[-4000:],
        "stderr_tail": stderr[-4000:],
        "passed": proc.returncode == 0,
    }
    record_event("VERIFICATION", task_id=task_id, payload=payload)
    print(stdout, end="")
    if stderr:
        print(stderr, end="", file=os.sys.stderr)
    return proc.returncode


def _task_events(task_id: str, path: Path = EVENT_LOG) -> list[dict[str, Any]]:
    safe = _safe_task_id(task_id)
    return [event for event in _read_events(path) if event.get("task_id") == safe]


def build_pack(task_id: str, path: Path = EVENT_LOG) -> dict[str, Any]:
    events = _read_events(path)
    ok, reason = verify_chain(events)
    if not ok:
        raise ValueError(f"evidence ledger failed verification: {reason}")
    selected = _task_events(task_id, path)
    if not selected:
        raise ValueError(f"no evidence for task {task_id!r}")

    verification = [e for e in selected if e.get("event_type") == "VERIFICATION"]
    skills = sorted(
        {
            str(e.get("skill"))
            for e in selected
            if e.get("skill") and e.get("event_type") == "SKILL_INVOKED"
        }
    )
    completion = [e for e in selected if e.get("event_type") == "COMPLETION_GATE"]
    workspace_shas = [
        str(e.get("workspace_head_sha"))
        for e in selected
        if e.get("workspace_head_sha")
    ]
    plugin_shas = sorted(
        {
            str(e.get("plugin_source_sha"))
            for e in selected
            if e.get("plugin_source_sha")
        }
    )
    pack: dict[str, Any] = {
        "schema": SCHEMA_PACK,
        "task_id": _safe_task_id(task_id),
        "sealed_at": _now(),
        "plugin_source_shas": plugin_shas,
        "workspace_start_sha": workspace_shas[0] if workspace_shas else "UNAVAILABLE",
        "workspace_end_sha": workspace_shas[-1] if workspace_shas else "UNAVAILABLE",
        "skills_invoked": skills,
        "event_count": len(selected),
        "event_hashes": [e["event_sha256"] for e in selected],
        "verification": {
            "runs": len(verification),
            "passed": sum(bool(e.get("payload", {}).get("passed")) for e in verification),
            "failed": sum(not bool(e.get("payload", {}).get("passed")) for e in verification),
        },
        "completion_gate": completion[-1].get("payload") if completion else None,
        "ledger_tip_sha256": events[-1]["event_sha256"] if events else "GENESIS",
        "claim_boundary": (
            "This pack proves observed plugin/task events and recorded verification "
            "outcomes. It does not by itself establish causal performance uplift."
        ),
    }
    pack["pack_sha256"] = _sha256(_canonical(pack))
    return pack


def seal_pack(task_id: str, output_root: Path) -> Path:
    pack = build_pack(task_id)
    task = _safe_task_id(task_id)
    digest = str(pack["pack_sha256"])
    destination = output_root / task / f"{digest}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        existing = json.loads(destination.read_text(encoding="utf-8"))
        if existing != pack:
            raise ValueError("content-addressed evidence collision")
        return destination
    destination.write_text(
        json.dumps(pack, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return destination


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    record = sub.add_parser("record")
    record.add_argument("--task-id", required=True)
    record.add_argument("--event", required=True)
    record.add_argument("--skill")
    record.add_argument("--payload-json", default="{}")

    verify = sub.add_parser("verify")
    verify.add_argument("--task-id", required=True)
    verify.add_argument("argv", nargs=argparse.REMAINDER)

    seal = sub.add_parser("seal")
    seal.add_argument("--task-id", required=True)
    seal.add_argument("--publish", action="store_true")
    seal.add_argument("--output")

    check = sub.add_parser("check")
    check.add_argument("--task-id")

    args = parser.parse_args()

    if args.command == "record":
        payload = json.loads(args.payload_json)
        event = record_event(
            args.event,
            task_id=args.task_id,
            skill=args.skill,
            payload=payload,
        )
        print(json.dumps(event, sort_keys=True))
        return 0

    if args.command == "verify":
        command = list(args.argv)
        if command and command[0] == "--":
            command = command[1:]
        return run_verification(args.task_id, command)

    if args.command == "seal":
        if args.output:
            output = Path(args.output)
        elif args.publish:
            output = DEFAULT_PUBLISH_ROOT
        else:
            output = ARTIFACT_ROOT / "devin-evidence-packs"
        path = seal_pack(args.task_id, output)
        print(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path)
        return 0

    events = _read_events()
    ok, reason = verify_chain(events)
    if not ok:
        print(json.dumps({"ok": False, "reason": reason}))
        return 2
    selected = _task_events(args.task_id) if args.task_id else events
    print(
        json.dumps(
            {
                "ok": True,
                "events": len(selected),
                "ledger_events": len(events),
                "tip": events[-1]["event_sha256"] if events else "GENESIS",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
