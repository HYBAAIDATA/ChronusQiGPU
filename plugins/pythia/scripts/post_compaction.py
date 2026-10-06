"""PostCompaction hook for PYTHIA checkpoint/provenance restoration."""
from __future__ import annotations

import json
import sys

from plugin_status import build_status, write_runtime_receipt


def main() -> int:
    status = build_status(event="PostCompaction")
    write_runtime_receipt(status)
    last = status.get("last_checkpoint")

    if isinstance(last, dict):
        summary = "goal=%s | done=%s | next=%s | files=%s" % (
            last.get("goal", "?"),
            last.get("done", "?"),
            last.get("next", "?"),
            last.get("files", "?"),
        )
    else:
        summary = "checkpoint=ABSENT; create a checkpoint before continuing"

    out = {
        "hookSpecificOutput": {
            "hookEventName": "PostCompaction",
            "additionalContext": (
                "PYTHIA restore | plugin_source_sha=%s | %s"
                % (status.get("plugin_source_sha", "UNAVAILABLE"), summary)
            ),
        }
    }
    sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
