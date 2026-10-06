"""Mandatory SessionStart hook for Devin EUCLID aptitude.

Every session activates the complete private plugin skill set and the complete
repo-local Intelligence/skills library. Skills are session-wide capabilities,
not per-task options. Task-specific side effects remain conditional and bounded.
"""
from __future__ import annotations

import json
import sys

from plugin_status import (
    INTELLIGENCE_SKILLS_ROOT,
    PLUGIN_ROOT,
    build_status,
    write_runtime_receipt,
)


def _skill_bundle() -> str:
    blocks: list[str] = []
    roots = (
        ("PLUGIN", PLUGIN_ROOT / "skills"),
        ("EUCLID APTITUDE", INTELLIGENCE_SKILLS_ROOT),
    )
    for family, root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*/SKILL.md")):
            try:
                body = path.read_text(encoding="utf-8")
            except OSError:
                continue
            blocks.append(
                f"\n--- {family}: {path.parent.name} ---\n{body.strip()}\n"
            )
    return "".join(blocks)


def main() -> int:
    status = build_status(event="SessionStart", invoke_all=True)
    write_runtime_receipt(status)

    if not status.get("mandatory_skills_complete"):
        missing = ",".join(status.get("mandatory_skills_missing") or [])
        sys.stdout.write(
            json.dumps(
                {
                    "decision": "block",
                    "reason": "mandatory EUCLID aptitude invocation incomplete: " + missing,
                }
            )
        )
        return 2

    last = status.get("last_checkpoint")
    lines = [
        "EUCLID aptitude bootstrap COMPLETE.",
        "The complete plugin + Intelligence skill library is mandatory and active.",
        "Skills are session-wide capabilities; they are not task-scoped choices.",
        "Apply every skill as an aptitude. Execute task-specific actions only when relevant and authorised.",
        "plugin_version=%s" % status.get("plugin_version", "UNAVAILABLE"),
        "plugin_source_sha=%s" % status.get("plugin_source_sha", "UNAVAILABLE"),
        "aptitude_digest_sha256=%s"
        % status.get("aptitude_digest_sha256", "UNAVAILABLE"),
        "mandatory_skill_count=%s" % len(status.get("mandatory_skills") or []),
        "mandatory_skills_complete=true",
    ]
    if isinstance(last, dict):
        lines.append(
            "checkpoint goal=%s | done=%s | next=%s"
            % (last.get("goal", "?"), last.get("done", "?"), last.get("next", "?"))
        )
    else:
        lines.append("checkpoint=ABSENT; establish continuity before substantial mutation")

    lines.append(
        "\nACTIVE EUCLID APTITUDE INSTRUCTIONS (mandatory for this session):\n"
        + _skill_bundle()
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
