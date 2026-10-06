"""Aggregate sealed PYTHIA Devin engineering packs without overclaiming causality."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean


def _packs(root: Path) -> list[dict]:
    packs = []
    for path in root.rglob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("schema") == "pythia.devin-engineering-pack/1":
            packs.append(data)
    return packs


def summarize(root: Path) -> dict:
    packs = _packs(root)
    verification_runs = [p.get("verification", {}).get("runs", 0) for p in packs]
    verification_failed = [p.get("verification", {}).get("failed", 0) for p in packs]
    completed = [
        p for p in packs
        if isinstance(p.get("completion_gate"), dict)
        and p["completion_gate"].get("decision") == "pass"
    ]
    return {
        "schema": "pythia.devin-engineering-evaluation/1",
        "packs": len(packs),
        "completion_gate_pass_rate": (
            len(completed) / len(packs) if packs else None
        ),
        "mean_verification_runs": mean(verification_runs) if verification_runs else None,
        "mean_failed_verifications": (
            mean(verification_failed) if verification_failed else None
        ),
        "plugin_source_shas": sorted(
            {
                sha
                for pack in packs
                for sha in pack.get("plugin_source_shas", [])
            }
        ),
        "claim_boundary": (
            "Observed outcome summary only. Demonstrating uplift requires comparable "
            "baseline and augmented task cohorts with the same acceptance criteria."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default="evidence/devin")
    args = parser.parse_args()
    print(json.dumps(summarize(Path(args.root)), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
