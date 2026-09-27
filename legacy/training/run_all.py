"""Run all six mining-agent contract verifiers and emit a JSON report.

Exit policy:
  - default: exit 1 iff any rule status is "fail" (code exists and violates
    its contract). ``not_implemented`` and ``not_checkable`` are reported but
    non-blocking — they are honest limits, not violations.
  - --strict: exit 1 on any non-pass status.

Usage:
    python -m training.run_all [--strict] [--json]
    python training/run_all.py [--strict] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow `python training/run_all.py` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from training.verifiers import (  # noqa: E402
    coordinator,
    hash_agent,
    nonce_agent,
    payout_agent,
    pool_agent,
    share_agent,
)
from training.verifiers.common import (  # noqa: E402
    STATUS_FAIL,
    STATUS_NOT_CHECKABLE,
    STATUS_NOT_IMPLEMENTED,
    STATUS_PASS,
)

VERIFIERS = [
    ("pool_agent", pool_agent),
    ("nonce_agent", nonce_agent),
    ("hash_agent", hash_agent),
    ("share_agent", share_agent),
    ("payout_agent", payout_agent),
    ("coordinator", coordinator),
]


def run() -> dict:
    report = {"agents": {}, "summary": {}}
    total = {STATUS_PASS: 0, STATUS_FAIL: 0, STATUS_NOT_IMPLEMENTED: 0, STATUS_NOT_CHECKABLE: 0}
    for name, mod in VERIFIERS:
        results = mod.verify()
        report["agents"][name] = [r.to_dict() for r in results]
        for r in results:
            total[r.status] = total.get(r.status, 0) + 1
    report["summary"] = {
        "rules_total": sum(total.values()),
        **total,
    }
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Mining-agent contract verifiers")
    ap.add_argument("--strict", action="store_true", help="fail on any non-pass status")
    ap.add_argument("--json", action="store_true", help="print raw JSON only")
    args = ap.parse_args()

    report = run()

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(json.dumps(report, indent=2))
        s = report["summary"]
        print(
            f"\n{summary_line(s)}",
            file=sys.stderr,
        )

    s = report["summary"]
    if args.strict:
        blocking = s["rules_total"] - s.get(STATUS_PASS, 0)
    else:
        blocking = s.get(STATUS_FAIL, 0)
    return 1 if blocking > 0 else 0


def summary_line(s: dict) -> str:
    return (
        f"contract verification: {s.get(STATUS_PASS, 0)} pass / "
        f"{s.get(STATUS_FAIL, 0)} fail / "
        f"{s.get(STATUS_NOT_IMPLEMENTED, 0)} not_implemented / "
        f"{s.get(STATUS_NOT_CHECKABLE, 0)} not_checkable "
        f"of {s['rules_total']} rules"
    )


if __name__ == "__main__":
    raise SystemExit(main())
