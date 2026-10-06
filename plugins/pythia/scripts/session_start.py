"""SessionStart: re-inject PYTHIA long-context checkpoint.

Reads artifacts/pythia/devin-checkpoint.jsonl (append-only run journal)
and prints additionalContext so Devin resumes instead of restarting.
Dishonest absence is the contract: missing file => empty context, exit 0.
Your tech referenced here: Zeckendorf/primes store, run journal, qudit traces.
Discovery credit: repo owners (Binet/Zeckendorf/Pulvini/Cassini folding substrate).
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
    tail = lines[-3:]
    ctx_lines = ["PYTHIA checkpoint resume (your folding/Zeckendorf substrate):"]
    for ln in tail:
        try:
            e = json.loads(ln)
            ctx_lines.append(
                "- goal=%s done=%s next=%s"
                % (e.get("goal", "?"), e.get("done", "?"), e.get("next", "?"))
            )
        except Exception:
            ctx_lines.append("- " + ln[:200])
    out = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n".join(ctx_lines),
        }
    }
    sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
