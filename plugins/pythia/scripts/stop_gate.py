"""Fail-closed Stop hook for the private PYTHIA Devin plugin.

Completion requires:
- a valid append-only checkpoint;
- the checkpoint bound to the currently executing plugin source SHA;
- runtime receipts for the core continuity/completion skills;
- terminal next state;
- fresh verification evidence recorded in the final checkpoint.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from plugin_status import JOURNAL, build_status, write_runtime_receipt

_REQUIRED_SKILLS = {
    "pythia-plugin-status",
    "pythia-long-context",
    "pythia-finish-the-job",
}


def _block(reason: str) -> int:
    sys.stdout.write(json.dumps({"decision": "block", "reason": reason}))
    return 2


def _verification_present(value: Any) -> bool:
    if isinstance(value, str):
        cleaned = value.strip()
        return bool(cleaned) and cleaned.lower() not in {"pending", "none", "unverified"}
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
        lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not lines:
            return None
        last = json.loads(lines[-1])
    except (OSError, json.JSONDecodeError):
        return {"_malformed": True}
    return last if isinstance(last, dict) else {"_malformed": True}


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
        return _block("PYTHIA checkpoint tail is malformed JSON; repair by appending a valid checkpoint.")

    source_sha = str(status.get("plugin_source_sha") or "")
    checkpoint_sha = str(last.get("plugin_source_sha") or "")
    if not source_sha or source_sha == "UNAVAILABLE":
        return _block("Current PYTHIA plugin source SHA is unavailable; completion provenance is unproven.")
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
            "Final checkpoint lacks fresh verification evidence. Record the command/"
            "inspection and observed result from this session."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
