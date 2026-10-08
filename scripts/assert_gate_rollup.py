#!/usr/bin/env python3
"""Fail-closed rollup for file-backed assurance-gate evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

REQUIRED_GATES = (
    "rule7-no-float",
    "abi-check",
    "refuted-claims",
    "import-audit",
    "claim-register",
    "envelope-verify",
    "conformance-vectors",
    "resilience-suite",
    "schema-freeze",
    "promotion-manifest",
    "privileged-path-audit",
    "repo-ownership",
)
VALID_STATUSES = {"PASS", "FAIL", "SKIP", "ERROR"}


def evaluate(results_dir: Path, *, require_no_skip: bool = False) -> dict:
    gate_results: dict[str, dict] = {}
    malformed: list[str] = []
    duplicates: list[str] = []
    ignored: list[str] = []

    paths = sorted(results_dir.glob("*.json")) if results_dir.exists() else []
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            malformed.append(f"{path.name}: {type(exc).__name__}")
            continue
        if not isinstance(payload, dict) or "gate" not in payload or "status" not in payload:
            ignored.append(path.name)
            continue
        gate = str(payload["gate"])
        status = str(payload["status"])
        if gate in gate_results:
            duplicates.append(gate)
            continue
        if status not in VALID_STATUSES:
            malformed.append(f"{path.name}: invalid status {status!r}")
            continue
        gate_results[gate] = payload

    required = set(REQUIRED_GATES)
    missing = sorted(required - set(gate_results))
    failed = sorted(
        gate for gate, payload in gate_results.items() if payload["status"] in {"FAIL", "ERROR"}
    )
    skipped = sorted(gate for gate, payload in gate_results.items() if payload["status"] == "SKIP")
    fatal_skips = skipped if require_no_skip else []

    return {
        "required": list(REQUIRED_GATES),
        "observed": sorted(gate_results),
        "missing": missing,
        "failed": failed,
        "skipped": skipped,
        "fatal_skips": fatal_skips,
        "duplicates": sorted(set(duplicates)),
        "malformed": malformed,
        "ignored_files": ignored,
        "passed": not (missing or failed or fatal_skips or duplicates or malformed),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", default="results")
    parser.add_argument(
        "--require-no-skip",
        action="store_true",
        help="treat SKIP as a release-blocking absence of evidence",
    )
    args = parser.parse_args(argv)
    report = evaluate(Path(args.results_dir), require_no_skip=args.require_no_skip)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
