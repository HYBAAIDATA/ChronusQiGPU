#!/usr/bin/env python3
"""Train PYTHIA on the canonical real-nonce structural corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from Intelligence.orchestrator import IntelligenceOrchestrator
from Intelligence.mining_structure_training import train_pythia_structure

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "artifacts" / "pythia_training" / "real_nonces_200.csv"
DEFAULT_MANIFEST = ROOT / "artifacts" / "pythia_training" / "real_nonces_200.manifest.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--store-dir", type=Path, default=None)
    parser.add_argument("--holdout", type=float, default=0.20)
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="run training/evaluation without saving the PythiaStore snapshot",
    )
    args = parser.parse_args()

    orchestrator = IntelligenceOrchestrator(store_dir=args.store_dir)
    report = train_pythia_structure(
        orchestrator,
        args.csv,
        args.manifest,
        holdout_fraction=args.holdout,
        persist=not args.no_persist,
    )
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
