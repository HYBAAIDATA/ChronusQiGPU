"""
Golden Quantum Framework — Test Runner.

Runs all 9 family test suites (8 ontology + 1 runtime infrastructure) and reports results.

Usage:
    python -m golden_quantum.runner
    python -m golden_quantum.runner --json
    python -m golden_quantum.runner --max-n 10000 --bases 2,10,12,15,18,20
    gqf --json
"""

import argparse
import json
import sys
from .results import CheckRegistry
from .families import (
    scaling, folding, storing, signal, transform, sampling, layout, stability, runtime, hyba_math,
)
from .registry import FAMILY_REGISTRY


def run_all(max_n: int = 10000, bases: list[int] = None) -> CheckRegistry:
    """Run all 8 family test suites and return collected results."""
    registry = CheckRegistry()

    if bases is None:
        from .constants import INTEGER_BASES
        bases = INTEGER_BASES

    # Run each family
    scaling.run(registry, max_n=max_n, bases=bases)
    folding.run(registry, max_n=max_n)
    storing.run(registry, max_n=max_n)
    signal.run(registry, max_n=max_n)
    transform.run(registry, max_n=max_n)
    sampling.run(registry, max_n=max_n)
    layout.run(registry, max_n=max_n)
    stability.run(registry, max_n=max_n)
    runtime.run(registry, max_n=max_n)
    hyba_math.run(registry, max_n=max_n)

    return registry


def format_report(registry: CheckRegistry) -> str:
    """Format the full report as a string."""
    lines = []
    width = 100

    lines.append("=" * width)
    lines.append("  THE GOLDEN QUANTUM FRAMEWORK — FAMILY ONTOLOGY TEST")
    lines.append("  9 families, 9 purposes — 8 ontology + 1 runtime infrastructure + 1 mathematical identities")
    lines.append("  Integer bases: 2, 10, 12, 15, 18, 20 | Decimal high-precision")
    lines.append("=" * width)
    lines.append("")

    families = registry.by_family()

    for info in FAMILY_REGISTRY:
        num = info["num"]
        name = info["name"]
        purpose = info["purpose"]
        family_key = f"FAMILY {num}: {name}"

        lines.append("╔" + "═" * (width - 2) + "╗")
        lines.append(f"║  FAMILY {num}: {name}".ljust(width - 1) + "║")
        lines.append(f"║  Purpose: {purpose}".ljust(width - 1) + "║")
        lines.append("╚" + "═" * (width - 2) + "╝")
        lines.append("")

        results = families.get(family_key, [])
        for r in results:
            status = "PASS" if r.passed else "FAIL"
            kind_tag = f"[{r.kind}]"
            line = f"  [{status}] {kind_tag} {r.name}"
            if r.detail:
                line += f" — {r.detail}"
            lines.append(line)

        lines.append("")

    # Summary
    lines.append("=" * width)
    lines.append("  SUMMARY")
    lines.append("=" * width)
    lines.append(f"  Total checks:       {registry.total}")
    lines.append(f"  Passed:             {registry.passed_count}")
    lines.append(f"  Failed:             {registry.failed_count}")
    lines.append(f"  Theorems:           {registry.theorem_count}")
    lines.append(f"  Invariants:         {registry.invariant_count}")
    lines.append(f"  Demonstrations:     {registry.demonstration_count}")
    lines.append("")

    if registry.all_passed:
        lines.append("  ✓ ALL THEOREMS AND INVARIANTS PASSED")
    else:
        lines.append("  ✗ SOME THEOREMS OR INVARIANTS FAILED:")
        for f in registry.failures():
            if f.kind in ("theorem", "invariant"):
                lines.append(f"    - [{f.kind}] {f.name}")
    lines.append("")
    lines.append("=" * width)

    return "\n".join(lines)


def format_json(registry: CheckRegistry) -> str:
    """Format results as JSON."""
    data = {
        "summary": {
            "total": registry.total,
            "passed": registry.passed_count,
            "failed": registry.failed_count,
            "theorems": registry.theorem_count,
            "invariants": registry.invariant_count,
            "demonstrations": registry.demonstration_count,
            "all_theorems_invariants_passed": registry.all_passed,
        },
        "families": [
            {
                "num": info["num"],
                "name": info["name"],
                "purpose": info["purpose"],
                "checks": [
                    {
                        "name": r.name,
                        "passed": r.passed,
                        "kind": r.kind,
                        "detail": r.detail,
                    }
                    for r in registry.results
                    if r.family == f"FAMILY {info['num']}: {info['name']}"
                ],
            }
            for info in FAMILY_REGISTRY
        ],
    }
    return json.dumps(data, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="The Golden Quantum Framework — Family Ontology Test"
    )
    parser.add_argument("--max-n", type=int, default=5000,
                        help="Maximum n for tests (default: 5000)")
    parser.add_argument("--bases", type=str, default=None,
                        help="Comma-separated list of bases (default: 2,10,12,15,18,20)")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")
    args = parser.parse_args()

    bases = None
    if args.bases:
        bases = [int(b.strip()) for b in args.bases.split(",")]

    registry = run_all(max_n=args.max_n, bases=bases)

    if args.json:
        print(format_json(registry))
    else:
        print(format_report(registry))

    # Exit code: 0 if all theorems/invariants pass, 1 otherwise
    sys.exit(0 if registry.all_passed else 1)


if __name__ == "__main__":
    main()
