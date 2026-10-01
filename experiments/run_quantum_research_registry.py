#!/usr/bin/env python3
"""List or execute every source-linked quantum method check."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chronus.v33.research_registry import CASES, validate_registry


def run_case(test_node: str, timeout: int) -> dict[str, object]:
    command = [sys.executable, "-m", "pytest", "-q", test_node]
    try:
        result = subprocess.run(
            command, cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired as exc:
        return {"outcome": "timeout", "returncode": None, "stdout": exc.stdout or "", "stderr": exc.stderr or ""}
    return {
        "outcome": "pass" if result.returncode == 0 else "fail",
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    validate_registry()
    report = []
    exit_code = 0
    for case in CASES:
        row = case.as_dict()
        if args.execute:
            outcome = run_case(case.test_node, args.timeout)
            row["result"] = outcome
            exit_code |= int(outcome["outcome"] != "pass")
        report.append(row)
    print(json.dumps(report, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
