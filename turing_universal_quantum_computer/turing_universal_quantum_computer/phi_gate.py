"""CLI production gate for the consolidated 1,000-qubit Turing phi machine."""
from __future__ import annotations

import argparse
import json

from .phi_verification import run_1000_qubit_verification


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shots", type=int, default=2, help="diagnostic GHZ samples; not evidence")
    parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = run_1000_qubit_verification(shots=args.shots)
    print(json.dumps(report, sort_keys=True, indent=None if args.compact else 2, default=str))
    return 0 if report.get("verification_pass") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
