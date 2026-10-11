"""Reproducible benchmark harness for the quantum_library exact lanes.

Contract per the benchmark-audit suite:

* Correctness is verified OUTSIDE the timing loop (an assertion on the
  mathematical result runs before any timing repetition).
* Warm-up runs are excluded from statistics and the policy is declared.
* Statistics are median / min / max / p90 over the declared repetition
  count — no single cherry-picked run.
* Peak RSS is reported as a process-cumulative upper bound (getrusage),
  explicitly labelled; per-operation allocation attribution is a
  documented limitation, not hidden.
* Environment (host, OS, Python, dependency versions) is recorded.
* Every benchmark declares ``claim_scope`` — what the number may and
  may not be taken to mean.

Run:  PYTHONPATH=. python bench/quantum_library_lanes.py > report.json
"""

from __future__ import annotations

import json
import platform
import resource
import statistics
import sys
import time
from fractions import Fraction
from typing import Any, Callable, Dict, List

import sympy as sp

from turing_universal_quantum_computer.quantum_library import (
    QuantumLibrary as Q,
)

WARMUP = 2
REPS = 9


def _env() -> Dict[str, Any]:
    import subprocess

    model = "unknown"
    try:
        model = (
            subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                timeout=5,
            ).stdout.strip()
            or "unknown"
        )
    except Exception:
        pass
    return {
        "host_model": model,
        "machine": platform.machine(),
        "os": f"{platform.system()} {platform.release()}",
        "python": sys.version.split()[0],
        "sympy": sp.__version__,
    }


def _rss_bytes() -> int:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss


def _bench(name: str, claim_scope: str, correctness: Callable[[], bool], call):
    ok = correctness()
    samples: List[float] = []
    lane = owner = domain = None
    for i in range(WARMUP + REPS):
        t0 = time.perf_counter()
        res = call()
        ms = (time.perf_counter() - t0) * 1e3
        if i >= WARMUP:
            samples.append(ms)
        lane, owner, domain = res.lane, res.lane_owner, res.arithmetic_domain
    return {
        "benchmark": name,
        "claim_scope": claim_scope,
        "correctness_verified_outside_timing": bool(ok),
        "lane": lane,
        "lane_owner": owner,
        "arithmetic_domain": domain,
        "warmup_reps_excluded": WARMUP,
        "timed_reps": REPS,
        "wall_ms": {
            "min": min(samples),
            "median": statistics.median(samples),
            "p90": sorted(samples)[int(0.9 * (len(samples) - 1))],
            "max": max(samples),
        },
    }


def main() -> None:
    report: Dict[str, Any] = {
        "benchmark_contract": {
            "warmup_policy": f"{WARMUP} unmeasured-then-discarded runs",
            "timing_boundary": "facade call, payload construction included",
            "memory_accounting": (
                "process-cumulative peak RSS via getrusage; per-operation "
                "allocation is NOT separately attributed (documented limitation)"
            ),
        },
        "environment": _env(),
        "benchmarks": [],
    }

    # GHZ entanglement entropy — the named case: tableau lane at n=10_000.
    report["benchmarks"].append(
        _bench(
            "ghz_entropy_n10000",
            "tableau entropy for GHZ-class stabilizer states at n=10000; "
            "says nothing about generic deep circuits",
            lambda: Q.ghz(10_000, subset={0}).payload["entropy_ebits"] == 1,
            lambda: Q.ghz(10_000, subset={0}),
        )
    )

    # QPE at the dyadic point: readout must concentrate with probability 1.
    report["benchmarks"].append(
        _bench(
            "qpe_T_phase_3q",
            "exact cyclotomic phase estimation at 3 counting qubits",
            lambda: (
                Q.qpe(Fraction(1, 8), 3).payload["estimated_phase"] == "1/8"
            ),
            lambda: Q.qpe(Fraction(1, 8), 3),
        )
    )

    # QAOA triangle at the measured optimum angles.
    def _tri() -> Any:
        return Q.qaoa_maxcut(
            [(0, 1), (1, 2), (0, 2)], [(Fraction(3, 8), Fraction(1, 8))]
        )

    report["benchmarks"].append(
        _bench(
            "qaoa_triangle_p1",
            "exact QAOA expected cut on K3 at declared rational-turn angles",
            lambda: _tri().payload["expected_cut"] == "15/8",
            _tri,
        )
    )

    # Registry dispatch: 100-qubit GHZ circuit on the stabilizer lane.
    report["benchmarks"].append(
        _bench(
            "execute_ghz100_registry",
            "certified lane selection + exact execution for a 100-qubit "
            "Clifford program",
            lambda: Q.execute_ops(
                100, [("h", 0)] + [("cx", 0, k) for k in range(1, 100)]
            ).payload["truth_class"]
            == "exact",
            lambda: Q.execute_ops(
                100, [("h", 0)] + [("cx", 0, k) for k in range(1, 100)]
            ),
        )
    )

    report["peak_rss_bytes_cumulative"] = _rss_bytes()
    print(json.dumps(report, indent=1, default=str))


if __name__ == "__main__":
    main()
