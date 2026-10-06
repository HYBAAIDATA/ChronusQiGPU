"""SessionStart hook for the private PYTHIA Devin plugin.

Writes a local runtime receipt proving which plugin revision actually executed,
then re-injects the latest append-only checkpoint when present.
"""
from __future__ import annotations

import json
import sys

from plugin_status import build_status, write_runtime_receipt


def main() -> int:
    status = build_status(event="SessionStart")
    write_runtime_receipt(status)

    last = status.get("last_checkpoint")
    lines = [
        "PYTHIA private plugin runtime observed.",
        "plugin_version=%s" % status.get("plugin_version", "UNAVAILABLE"),
        "plugin_source_sha=%s" % status.get("plugin_source_sha", "UNAVAILABLE"),
        "available_skills=%s" % ",".join(status.get("available_skills") or []),
    ]
    if isinstance(last, dict):
        lines.append(
            "checkpoint goal=%s | done=%s | next=%s"
            % (last.get("goal", "?"), last.get("done", "?"), last.get("next", "?"))
        )
    else:
        lines.append(
            "checkpoint=ABSENT; fresh session must create an opening checkpoint "
            "before task work"
        )

    out = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n".join(lines),
        }
    }
    sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
