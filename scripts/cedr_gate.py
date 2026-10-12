"""Validate the CEDR contract or enforce evidence-qualified promotion."""

import argparse
import json
import subprocess
from pathlib import Path

from al_haras.cedr import evaluate, read_json, validate_registry


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=Path("governance/cedr.json"))
    parser.add_argument(
        "--validate", action="store_true", help="contract validation only; not readiness"
    )
    parser.add_argument("--profile")
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--output", type=Path, default=Path("results/cedr-decision.json"))
    args = parser.parse_args(argv)
    try:
        document = read_json(args.registry)
        if args.validate:
            errors = validate_registry(document)
            print(json.dumps({"scope": "contract_validation_only_not_readiness", "errors": errors}))
            return 1 if errors else 0
        if not args.profile or not args.artifact:
            parser.error("promotion requires --profile and --artifact")
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        ).stdout.strip()
        report = evaluate(
            document,
            root=Path.cwd(),
            profile_name=args.profile,
            commit=commit,
            artifact=args.artifact,
        )
    except (OSError, ValueError, TypeError, KeyError, subprocess.CalledProcessError):
        report = {"eligible": False, "errors": ["CEDR execution failed closed"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    return 0 if report["eligible"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
