#!/usr/bin/env python3
"""EUCLID-CORE benchmark harness.

Times the compute paths that matter for production:

  1. Exact Q[√5] arithmetic   — lucas(), zeckendorf_encode(), cassini_check()
  2. Double-SHA256 mining     — PythiaMiningEngine.scan_range() nonces/sec
  3. Quantum tensor substrate — ComplexMatrix matmul / unitary evolution
  4. Core self-verification   — turing_core.run_self_verification()

Usage:
    python scripts/benchmark.py              # default sizes
    python scripts/benchmark.py --nonces 50000 --json artifacts/benchmark.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Callable, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _time(label: str, fn: Callable[[], Any], repeat: int = 1) -> Dict[str, Any]:
    best = float("inf")
    result = None
    for _ in range(repeat):
        t0 = time.perf_counter()
        result = fn()
        best = min(best, time.perf_counter() - t0)
    return {"label": label, "seconds": best, "detail": result}


def bench_exact_math() -> Dict[str, Any]:
    import turing_core

    def lucas_work() -> int:
        return sum(turing_core.lucas(n) for n in range(1, 501)) % (1 << 64)

    def zeck_work() -> int:
        return sum(len(turing_core.zeckendorf_encode(v)) for v in range(1, 20001))

    def cassini_work() -> int:
        return sum(1 for n in range(1, 201) if turing_core.cassini_check(n))

    return {
        "lucas_1..500": _time("lucas(1..500) exact bigints", lucas_work),
        "zeckendorf_1..20000": _time("zeckendorf_encode(1..20000)", zeck_work),
        "cassini_1..200": _time("cassini_check(1..200)", cassini_work),
    }


def bench_mining(nonces: int) -> Dict[str, Any]:
    import turing_core

    engine = turing_core.PythiaMiningEngine()
    c1, c2 = engine.partition_header_for_midstate(1, b"\x00" * 32, b"\x00" * 32, 1000, 0x1D00FFFF)
    impossible_target = 0  # forces a full-range scan — measures raw throughput

    t0 = time.perf_counter()
    engine.scan_range(c1, c2, impossible_target, 0, nonces)
    elapsed = time.perf_counter() - t0
    return {
        "nonces": nonces,
        "seconds": elapsed,
        "hashes_per_second": round(nonces / elapsed, 1) if elapsed > 0 else None,
        "note": "double-SHA256 full-range scan, impossible target (raw throughput)",
    }


def bench_quantum_tensor(dim: int) -> Dict[str, Any]:
    from Intelligence.quantum_tensor import (
        ComplexMatrix,
        QuantumState,
        Observables,
    )

    H = Observables.harmonic_oscillator_hamiltonian(dim)
    U = ComplexMatrix.matrix_exp_unitary(H, 0.01)
    psi = QuantumState.from_basis(dim, 0)

    t0 = time.perf_counter()
    for _ in range(200):
        psi = psi.apply_unitary(U)
    elapsed = time.perf_counter() - t0
    return {
        "dim": dim,
        "steps": 200,
        "seconds": elapsed,
        "steps_per_second": round(200 / elapsed, 1) if elapsed > 0 else None,
        "note": f"{dim}x{dim} unitary application (Schrödinger step)",
    }


def bench_self_verification() -> Dict[str, Any]:
    import turing_core

    t0 = time.perf_counter()
    ok = turing_core.run_self_verification()
    elapsed = time.perf_counter() - t0
    return {"passed": ok, "seconds": elapsed}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="EUCLID-CORE benchmark harness")
    ap.add_argument("--nonces", type=int, default=100_000)
    ap.add_argument("--dim", type=int, default=32)
    ap.add_argument("--json", type=str, default=None, help="write report JSON to path")
    args = ap.parse_args()

    report: Dict[str, Any] = {"benchmark": "euclid-core", "results": {}}

    print("=" * 72)
    print("EUCLID-CORE BENCHMARK")
    print("=" * 72)

    for name, section in bench_exact_math().items():
        report["results"][name] = section
        print(f"  {section['label']:<44} {section['seconds']:8.3f}s")

    mining = bench_mining(args.nonces)
    report["results"]["mining_scan"] = mining
    print(
        f"  {'double-SHA256 scan_range(' + str(mining['nonces']) + ')':<44} "
        f"{mining['seconds']:8.3f}s  → {mining['hashes_per_second']:,.0f} H/s"
    )

    qt = bench_quantum_tensor(args.dim)
    report["results"]["quantum_tensor"] = qt
    print(
        f"  {'unitary evolution ' + str(qt['dim']) + 'x' + str(qt['dim']) + ' x200':<44} "
        f"{qt['seconds']:8.3f}s  → {qt['steps_per_second']:,.0f} steps/s"
    )

    sv = bench_self_verification()
    report["results"]["self_verification"] = sv
    print(
        f"  {'turing_core self-verification':<44} {sv['seconds']:8.3f}s  "
        f"({'PASS' if sv['passed'] else 'FAIL'})"
    )

    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        print(f"\nReport saved to {args.json}")

    return 0 if sv["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
