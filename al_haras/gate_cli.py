"""CLI for evaluating a repository's declared subsystem promotion states."""

from __future__ import annotations
import argparse
import json
from pathlib import Path
from .promotion_gates import PromotionState, evaluate_gate


def evaluate_manifest(data: dict) -> dict:
    evidence = data.get("evidence", {})
    rollbacks = data.get("rollback_evidence", {})
    results = {}
    for subsystem, target_name in data["targets"].items():
        result = evaluate_gate(
            subsystem,
            PromotionState[target_name],
            evidence,
            rollback_evidence=rollbacks.get(subsystem, ()),
        )
        results[subsystem] = {
            "target": result.target.name,
            "achieved": result.achieved.name,
            "passed": result.passed,
            "missing": list(result.missing),
            "promoted_claims": list(result.promoted_claims),
            "refuted_claims": list(result.refuted_claims),
        }
    return {"passed": all(r["passed"] for r in results.values()), "results": results}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args(argv)
    report = evaluate_manifest(json.loads(args.manifest.read_text()))
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
