#!/usr/bin/env python3
"""Regression tests for the gaps closed in review: anyon braid group, VR homology."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "hyba_golden_lab" / "02_quantum")]

from quantum_first_principles import (  # noqa: E402
    FibonacciAnyonAlgebra,
    QuantumState,
    QuantumStateType,
)
from pure_math import vietoris_rips_betti  # noqa: E402


def check(name: str, cond: bool, detail: str = "") -> bool:
    print(f"  [{'OK' if cond else 'FAIL'}] {name}  {detail}")
    return cond


def main() -> int:
    failed = 0
    A = FibonacciAnyonAlgebra()

    print("ANYON BRAID GROUP REGRESSION")
    for n in (2, 3, 4, 5, 6):
        gens = A.compute_braid_generators(n)
        max_err = max(float(np.linalg.norm(g.conj().T @ g - np.eye(len(g)))) for g in gens)
        failed += not check(f"unitarity n={n} dim={len(gens[0])}", max_err < 1e-9, f"err={max_err:.1e}")

    for n in (3, 4, 5):
        gens = A.compute_braid_generators(n)
        for i in range(n - 2):
            rel = float(np.linalg.norm(
                gens[i] @ gens[i + 1] @ gens[i] - gens[i + 1] @ gens[i] @ gens[i + 1]
            ))
            failed += not check(f"braid relation n={n} s{i}", rel < 1e-9, f"err={rel:.1e}")
        for i in range(len(gens)):
            for j in range(i + 2, len(gens)):
                rel = float(np.linalg.norm(gens[i] @ gens[j] - gens[j] @ gens[i]))
                failed += not check(f"far commutation n={n} s{i},s{j}", rel < 1e-9, f"err={rel:.1e}")

    for n, word in [(3, [0, 1, 0]), (4, [0, 1, 2, 1, 0]), (5, [0, 1, 2, 3, 2, 1])]:
        basis = A.generate_fusion_basis(n)
        s = QuantumState(
            amplitudes=np.ones(len(basis), dtype=complex) / np.sqrt(len(basis)),
            basis=[str(b) for b in basis],
            state_type=QuantumStateType.ANYON,
            anyon_charges=["tau"] * n,
        )
        f = A.braid_group_action(s, word)
        nm = float(np.linalg.norm(f.amplitudes))
        failed += not check(f"norm preserved n={n} {word}", abs(nm - 1) < 1e-9, f"norm={nm:.10f}")

    print("\nVR HOMOLOGY REGRESSION")
    t = np.linspace(0, 2 * np.pi, 12, endpoint=False)
    circle = np.stack([np.cos(t), np.sin(t)], axis=1)
    blobs = np.vstack([circle * 0.1, circle * 0.1 + [3.0, 0.0]])

    b = vietoris_rips_betti(circle, 0.7)
    failed += not check("circle beta=(1,1,0,0)", (b[0], b[1], b[2], b[3]) == (1, 1, 0, 0), str(b))
    b = vietoris_rips_betti(blobs, 0.4)
    failed += not check("two blobs beta=(2,0,0,0)", (b[0], b[1], b[2], b[3]) == (2, 0, 0, 0), str(b))
    b = vietoris_rips_betti(circle, 3.0)
    failed += not check("filled disk beta=(1,0,0,0)", (b[0], b[1], b[2], b[3]) == (1, 0, 0, 0), str(b))

    print(f"\n{'PASS' if failed == 0 else 'FAIL'}  failures={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
