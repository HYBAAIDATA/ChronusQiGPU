#!/usr/bin/env python3
"""Authoritative acceptance command for the intelligence-elevation mutation."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts" / "intelligence-elevation-evidence.json"


def run(label: str, command: list[str]) -> dict[str, object]:
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "label": label,
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout[-8000:],
        "stderr": completed.stderr[-8000:],
        "passed": completed.returncode == 0,
    }


def main() -> int:
    checks = [
        run("compile", [sys.executable, "-m", "compileall", "-q",
                        "euclid/cognition", "euclid/search/deep_mcts.py",
                        "euclid/capability_matrix.py",
                        "euclid/benchmarks/intelligence_elevation.py"]),
        run("euclid-suite-full", [
            sys.executable, "-m", "unittest", "discover", "-s", "euclid/tests",
            "-p", "test_*.py",
        ]),
        run("benchmark-smoke", [
            sys.executable, "-c",
            "import json;"
            "from euclid.benchmarks.intelligence_elevation import run_benchmark;"
            "r = run_benchmark(smoke=True);"
            "assert r['summary'];"
            "print(json.dumps(r['summary'], sort_keys=True))",
        ]),
        run("capability-matrix", [
            sys.executable, "-c",
            "from euclid.capability_matrix import generate_matrix, STAGES;"
            "m = generate_matrix();"
            "c = m['capabilities'];"
            "assert STAGES.index(c['cognition-loop']['stage']) >= STAGES.index('PERSISTED');"
            "assert c['cross-problem-transfer']['stage'] == 'HELD_OUT_TESTED';"
            "print({k: v['stage'] for k, v in c.items()})",
        ]),
    ]
    payload = {
        "schema": "euclid.intelligence-elevation.acceptance/1",
        "base_sha": "bf6972f928b38f3a3f9c5ff2618970ef913e3e15",
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
        "claim_boundary": {
            "internal_measured_improvement_only": True,
            "agi_or_asi": False,
            "consciousness": False,
            "quantum_advantage": False,
            "external_superiority": False,
            "phi_is_diagnostic_not_objective": True,
            "production_mining_authority": False,
        },
        "known_negative_results": [
            "On the v1 saturating task family, the elevated loop matches but "
            "does not exceed the greedy evolutionary route; transfer gain over "
            "the cold-repository ablation measured 0.0. Harder held-out task "
            "families are required before any transfer advantage can be claimed.",
            "The merged v16 root-level MCTS underperformed both the random "
            "baseline and the elevated deep MCTS on held-out tasks in this "
            "benchmark configuration.",
        ],
        "remaining_gates": [
            "CI/check runs",
            "installable-wheel test in CI",
            "harder held-out task families (program repair, causal, planning)",
            "TOE/PYTHIA organ adapter evidence",
            "independent external validation",
        ],
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))
    print("INTELLIGENCE_ELEVATION=PASS" if payload["passed"] else "INTELLIGENCE_ELEVATION=FAIL")
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
