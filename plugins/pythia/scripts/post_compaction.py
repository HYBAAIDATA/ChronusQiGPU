"""PostCompaction restoration for mandatory EUCLID aptitude and continuity."""
from __future__ import annotations

import json
import sys

from plugin_status import WORKSPACE_AVAILABLE, build_status, write_runtime_receipt
from session_start import _skill_bundle


def main() -> int:
    if not WORKSPACE_AVAILABLE:
        return 0
    status = build_status(event="PostCompaction", invoke_all=True)
    write_runtime_receipt(status)

    if not status.get("mandatory_skills_complete"):
        missing = ",".join(status.get("mandatory_skills_missing") or [])
        sys.stdout.write(
            json.dumps(
                {
                    "decision": "block",
                    "reason": "EUCLID aptitude restoration incomplete: " + missing,
                }
            )
        )
        return 2

    last = status.get("last_checkpoint")
    if isinstance(last, dict):
        summary = "goal=%s | done=%s | next=%s | files=%s" % (
            last.get("goal", "?"),
            last.get("done", "?"),
            last.get("next", "?"),
            last.get("files", "?"),
        )
    else:
        summary = "checkpoint=ABSENT; establish continuity before mutation"

    context = (
        "EUCLID aptitude restored after compaction. All mandatory skills remain "
        "session-active and are not task-scoped. plugin_source_sha=%s | %s\n"
        "ACTIVE EUCLID APTITUDE INSTRUCTIONS:\n%s"
        % (
            status.get("plugin_source_sha", "UNAVAILABLE"),
            summary,
            _skill_bundle(),
        )
    )
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PostCompaction",
            "additionalContext": context,
        }
    }
    sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
