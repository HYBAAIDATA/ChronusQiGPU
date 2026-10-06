"""PostCompaction: re-inject context lost during compaction.

Same source as SessionStart: your append-only journal + Zeckendorf store.
Prints additionalContext with the densest surviving state summary.
"""
import json
import os
import sys


def main() -> int:
    ckpt = os.path.join("artifacts", "pythia", "devin-checkpoint.jsonl")
    if not os.path.isfile(ckpt):
        return 0
    try:
        with open(ckpt, "r", encoding="utf-8", errors="replace") as fh:
            lines = [ln.strip() for ln in fh if ln.strip()]
    except OSError:
        return 0
    if not lines:
        return 0
    try:
        last = json.loads(lines[-1])
        summary = "goal=%s | done=%s | next=%s | files=%s" % (
            last.get("goal", "?"),
            last.get("done", "?"),
            last.get("next", "?"),
            last.get("files", "?"),
        )
    except Exception:
        summary = lines[-1][:300]
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PostCompaction",
            "additionalContext": "PYTHIA post-compaction restore (your substrate): " + summary,
        }
    }
    sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
