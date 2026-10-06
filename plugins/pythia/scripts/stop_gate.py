"""Fail-closed Stop hook for PYTHIA Devin Engineering Intelligence v0.3.

A completion claim requires:
- a valid final checkpoint;
- stable task id;
- checkpoint bound to the executing plugin source SHA;
- required skills runtime-observed;
- fresh verification evidence;
- a valid content-addressed evidence pack for the same task/plugin revision.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from plugin_status import JOURNAL, ROOT, build_status, write_runtime_receipt

_REQUIRED_SKILLS = {
    "pythia-plugin-status",
    "pythia-long-context",
    "pythia-engineering-quality",
    "pythia-evidence-pack",
    "pythia-finish-the-job",
}


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")


def _block(reason: str) -> int:
    sys.stdout.write(json.dumps({"decision": "block", "reason": reason}))
    return 2


def _verification_present(value: Any) -> bool:
    if isinstance(value, str):
        cleaned = value.strip()
        return bool(cleaned) and cleaned.lower() not in {
            "pending",
            "none",
            "unverified",
        }
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return bool(cleaned) and not all(
            item.lower() in {"pending", "none", "unverified"} for item in cleaned
        )
    return False


def _terminal_next(value: Any) -> bool:
    nxt = str(value or "").strip().lower()
    return nxt in {"done", "none"} or nxt.startswith("blocked:")


def _load_last_checkpoint(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        lines = [
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if not lines:
            return None
        last = json.loads(lines[-1])
    except (OSError, json.JSONDecodeError):
        return {"_malformed": True}
    return last if isinstance(last, dict) else {"_malformed": True}


def _resolve_pack(value: Any) -> Path | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    try:
        resolved = candidate.resolve(strict=True)
        root = ROOT.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError):
        return None
    return resolved


def _verify_pack(path: Path, *, task_id: str, plugin_source_sha: str) -> tuple[bool, str]:
    try:
        pack = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, "evidence pack is unreadable or malformed"

    if not isinstance(pack, dict):
        return False, "evidence pack is not an object"
    if pack.get("schema") != "pythia.devin-engineering-pack/1":
        return False, "evidence pack schema mismatch"
    if str(pack.get("task_id") or "") != task_id:
        return False, "evidence pack task_id mismatch"

    claimed = str(pack.get("pack_sha256") or "")
    unsigned = dict(pack)
    unsigned.pop("pack_sha256", None)
    actual = hashlib.sha256(_canonical(unsigned)).hexdigest()
    if claimed != actual:
        return False, "evidence pack SHA256 mismatch"
    if path.stem != claimed:
        return False, "evidence pack filename is not content-addressed by pack SHA256"

    plugin_shas = set(str(x) for x in pack.get("plugin_source_shas") or [])
    if plugin_source_sha not in plugin_shas:
        return False, "evidence pack does not contain current plugin source SHA"

    skills = set(str(x) for x in pack.get("skills_invoked") or [])
    missing = sorted(_REQUIRED_SKILLS - skills)
    if missing:
        return False, "evidence pack is missing required skill events: " + ", ".join(missing)

    verification = pack.get("verification")
    if not isinstance(verification, dict) or int(verification.get("runs", 0)) < 1:
        return False, "evidence pack has no recorded verification run"

    completion = pack.get("completion_gate")
    if not isinstance(completion, dict):
        return False, "evidence pack lacks a completion gate"
    if completion.get("decision") != "pass":
        return False, "evidence pack completion gate is not pass"

    return True, "ok"


def main() -> int:
    status = build_status(event="Stop")
    write_runtime_receipt(status)

    last = _load_last_checkpoint(JOURNAL)
    if last is None:
        return _block(
            "PYTHIA checkpoint is missing. Create the final append-only checkpoint "
            "before ending the job."
        )
    if last.get("_malformed"):
        return _block(
            "PYTHIA checkpoint tail is malformed JSON; append a valid checkpoint."
        )

    task_id = str(last.get("task_id") or "").strip()
    if not task_id:
        return _block("Final checkpoint is missing task_id.")

    source_sha = str(status.get("plugin_source_sha") or "")
    checkpoint_sha = str(last.get("plugin_source_sha") or "")
    if not source_sha or source_sha == "UNAVAILABLE":
        return _block(
            "Current PYTHIA plugin source SHA is unavailable; completion "
            "provenance is unproven."
        )
    if checkpoint_sha != source_sha:
        return _block(
            "Final checkpoint is not bound to the current PYTHIA plugin revision "
            f"(checkpoint={checkpoint_sha or 'missing'}, current={source_sha})."
        )

    invoked = set(status.get("skills_invoked") or [])
    missing = sorted(_REQUIRED_SKILLS - invoked)
    if missing:
        return _block(
            "Required PYTHIA skills were not runtime-observed in this workspace: "
            + ", ".join(missing)
        )

    if not _terminal_next(last.get("next")):
        return _block(
            "PYTHIA checkpoint has unfinished work. Set next to done, none, or "
            "blocked: <reason> after resolving/recording the task."
        )

    if not _verification_present(last.get("verification")):
        return _block(
            "Final checkpoint lacks fresh verification evidence from this session."
        )

    pack_path = _resolve_pack(last.get("evidence_pack"))
    if pack_path is None:
        return _block(
            "Final checkpoint evidence_pack is missing, outside the repository, "
            "or does not exist."
        )
    ok, reason = _verify_pack(
        pack_path,
        task_id=task_id,
        plugin_source_sha=source_sha,
    )
    if not ok:
        return _block(reason)

    sys.stdout.write(
        json.dumps(
            {
                "decision": "pass",
                "task_id": task_id,
                "plugin_source_sha": source_sha,
                "evidence_pack": str(pack_path.relative_to(ROOT)),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
