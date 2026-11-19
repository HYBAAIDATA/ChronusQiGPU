"""Reproducible benchmark for tensor experiment E3 (1,000-site critical TFIM, Z2 DMRG).

Method: one in-process call of ``E3_honest_1000_node_claim()`` with its fixed
contract (n=1000, chi_max=512, 2 sweeps, P=+1 sector), timed with
``time.perf_counter``. The output records the commit, interpreter, NumPy and CPU
so that a result can be matched to the exact environment that produced it.

The acceptance is numerical: relative energy error <= 1e-6 against the
closed-form Jordan-Wigner energy in float64. Meeting it is not exact
mathematical equivalence. Wall time is CPU reference evidence for this machine
only, not a GPU or hardware performance claim.

    PYTHONPATH=src python benchmarks/benchmark_tensor_e3.py [--out FILE]
"""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def run() -> dict:
    import numpy as np

    from chronus.tensor.experiments import E3_honest_1000_node_claim

    started = time.perf_counter()
    result = E3_honest_1000_node_claim()
    wall = time.perf_counter() - started
    t = result.telemetry
    keys = ("nodes", "chi_max", "sweeps", "group", "parity_sector", "max_bond_dimension_used",
            "ground_state_energy_1000", "exact_open_chain_energy", "variational_energy_error",
            "relative_energy_error", "global_error_bound", "claim_bound", "cross_check_diff")
    return {
        "experiment": "E3",
        "method": "single in-process E3_honest_1000_node_claim() call, time.perf_counter wall clock",
        "status": result.status,
        "acceptance": t["acceptance"],
        "result": {k: t[k] for k in keys},
        "wall_seconds": round(wall, 2),
        "environment": {
            "commit": _commit(),
            "python": platform.python_version(),
            "numpy": np.__version__,
            "machine": platform.machine(),
            "processor": platform.processor() or "unknown",
            "system": platform.system(),
        },
        "scope": "CPU reference evidence for this machine only; not a GPU or hardware claim",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    record = run()
    text = json.dumps(record, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
