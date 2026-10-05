#!/usr/bin/env python3
"""Release-adjacent gate: paradigm triad must be green.

Exit 0 on pass, 1 on fail. Writes docs/evidence/paradigm_triad_latest.json
when the evidence directory is writable.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from chronus.paradigm.triad import run_triad, write_report

    report = run_triad(include_honesty=True)
    out = ROOT / "docs" / "evidence" / "paradigm_triad_latest.json"
    try:
        write_report(out, report)
        print(f"wrote {out}")
    except OSError as exc:
        print(f"warn: could not write evidence artifact: {exc}")

    print("thesis:", report.thesis)
    print("ok:", report.ok)
    print("digest:", report.artifact_digest)
    for leg in report.legs:
        print(f"  [{'PASS' if leg.ok else 'FAIL'}] {leg.name}")
    if not report.ok:
        for leg in report.legs:
            if not leg.ok:
                print("FAIL_DETAIL", leg.name, leg.detail)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
