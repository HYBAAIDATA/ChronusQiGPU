"""Stamp begin/end markers for an order run (evidence/order/preflight.jsonl)."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parents[2] / "evidence" / "order" / "preflight.jsonl"


def main() -> int:
    parser = argparse.ArgumentParser(prog="preflight")
    parser.add_argument("--begin", action="store_true")
    parser.add_argument("--end", action="store_true")
    parser.add_argument("--order", default="seed-publish-followup")
    args = parser.parse_args()
    if args.begin == args.end:
        parser.error("pass exactly one of --begin or --end")
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "order": args.order,
        "phase": "begin" if args.begin else "end",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with EVIDENCE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")
    print(json.dumps(event))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
