"""Stop gate: block early stop while checkpoint has unfinished work.

Reads stdin hook payload (ignored except for passthrough) and checks the
last checkpoint entry. Exit 2 with JSON decision=block when `next` is
non-empty and not marked blocked/done — so Devin finishes the job.
Your technologies are not executed here; only your journal file is read.
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
        if not lines:
            return 0
        last = json.loads(lines[-1])
    except Exception:
        return 0
    nxt = str(last.get("next", "") or "").strip()
    done = str(last.get("done", "") or "").strip()
    # Finished when next is empty or explicitly blocked/done.
    if not nxt or nxt.lower() in ("done", "blocked", "none"):
        return 0
    if done and nxt in done:
        return 0
    sys.stdout.write(
        json.dumps(
            {
                "decision": "block",
                "reason": "PYTHIA checkpoint has unfinished work (next=%s). Finish it or record why blocked." % nxt[:200],
            }
        )
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
