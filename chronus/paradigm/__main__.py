"""CLI: python -m chronus.paradigm [--json] [--out PATH]"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from chronus.paradigm.thesis import thesis_text
from chronus.paradigm.triad import run_triad, write_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m chronus.paradigm",
        description="Run the fail-closed virtual accelerator paradigm triad.",
    )
    parser.add_argument("--json", action="store_true", help="print full JSON report")
    parser.add_argument(
        "--out",
        type=str,
        default="",
        help="optional path to write the triad report JSON",
    )
    parser.add_argument(
        "--no-honesty",
        action="store_true",
        help="skip honesty chaos leg (not recommended)",
    )
    args = parser.parse_args(argv)

    report = run_triad(include_honesty=not args.no_honesty)
    if args.out:
        write_report(args.out, report)

    if args.json:
        print(report.to_json())
    else:
        print("THESIS:", thesis_text())
        print("OK:" if report.ok else "FAIL:", report.ok)
        print("DIGEST:", report.artifact_digest)
        for leg in report.legs:
            mark = "PASS" if leg.ok else "FAIL"
            print(f"  [{mark}] {leg.name}")
        print("PENDING_EXTERNAL:")
        for p in report.pending_external:
            print(f"  - {p}")
        print("CLAIMS:", ", ".join(report.claim_ids))

    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
