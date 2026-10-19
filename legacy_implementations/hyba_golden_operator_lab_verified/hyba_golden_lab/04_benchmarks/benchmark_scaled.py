#!/usr/bin/env python3
"""
Comprehensive benchmarks: baseline vs golden-family scaled operators.
Reports measurements only. No O(I) claims. No hardware.
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "api"), str(ROOT / "01_mathematics"), str(ROOT / "02_quantum")]

from quantum_api import QuantumAPI, GoldenScale  # noqa: E402
from golden_transform import PHI, fib  # noqa: E402

OUT = Path(__file__).resolve().parent / "results"
OUT.mkdir(exist_ok=True)


def main() -> int:
    api = QuantumAPI()
    rows = []

    print("SCALED BENCHMARKS  (baseline vs golden-family in the operator)")
    print(f"identities frozen: {GoldenScale.identities_hold()}")

    # Grover unique target n=3..6
    print("\nGrover unique marked")
    for nq in (3, 4, 5, 6):
        tgt = (2 ** nq) - 1
        b = api.grover(nq, [tgt], scaled=False)
        a = api.grover(nq, [tgt], scaled=True)
        rec = {
            "exp": "grover_unique",
            "n_qubits": nq,
            "before": {"iters": b.data["iterations"], "P": b.data["marked_probability"],
                        "F": b.fidelity, "N_eff": b.data["n_eff"]},
            "after": {"iters": a.data["iterations"], "P": a.data["marked_probability"],
                       "F": a.fidelity, "N_eff": a.data["n_eff"]},
        }
        rows.append(rec)
        print(f"  n={nq}  BEFORE P={b.data['marked_probability']:.6f} it={b.data['iterations']}  "
              f"AFTER P={a.data['marked_probability']:.6f} it={a.data['iterations']}")

    # QAOA path Ising
    print("\nQAOA path-Ising")
    for n in (3, 4):
        J = np.zeros((n, n))
        for i in range(n - 1):
            J[i, i + 1] = J[i + 1, i] = 1.0
        b = api.qaoa(n, J, p=3, scaled=False)
        a = api.qaoa(n, J, p=3, scaled=True)
        rec = {
            "exp": "qaoa_path",
            "n": n,
            "exact_min": b.data["exact_min"],
            "before": {"E": b.data["energy"], "gap": b.data["gap"], "N_eff": b.data["n_eff"]},
            "after": {"E": a.data["energy"], "gap": a.data["gap"], "N_eff": a.data["n_eff"]},
        }
        rows.append(rec)
        print(f"  n={n}  E0={b.data['exact_min']:.4f}  BEFORE E={b.data['energy']:.4f}  "
              f"AFTER E={a.data['energy']:.4f}  Δ={a.data['energy']-b.data['energy']:+.4f}")

    # QFT inversion fidelity vs n
    print("\nQFT inversion fidelity")
    for nq in (2, 3, 4, 5):
        psi = api.basis(1, 2 ** nq)
        t0 = time.perf_counter()
        r = api.qft(psi)
        rec = {"exp": "qft_invert", "n_qubits": nq, "F": r.fidelity,
               "wall": time.perf_counter() - t0}
        rows.append(rec)
        print(f"  n={nq}  F={r.fidelity:.16f}")

    # Binet / Zeckendorf memory fold
    print("\nMemory folds")
    bf = api.fold_binet("F", 25)
    z = api.fold_zeckendorf([fib(k) for k in range(2, 16)] + [15, 50, 100, 144])
    rows.append({"exp": "binet_F25", **bf.data, "ok": bf.ok})
    rows.append({"exp": "zeckendorf", **{k: z.data[k] for k in z.data if k != "sample"}, "ok": z.ok})
    print(f"  Binet F_0..25 max|err|={bf.data['max_abs_error']:.3e}  26 terms → 2 amplitudes")
    print(f"  Zeckendorf unique={z.ok}  dense={z.data['dense_slots']} marks={z.data['sparse_marks']}")

    # MPS fidelity
    print("\nMPS")
    for n in (3, 4, 5):
        r = api.mps(api.ghz(n))
        rows.append({"exp": "mps_ghz", "n": n, "F": r.fidelity})
        print(f"  GHZ n={n}  F={r.fidelity:.16f}")

    # Born-pair coherence on Grover output
    print("\nBorn-pair M^n coherence")
    g = api.grover(5, [7], scaled=False)
    st = api.ket(np.sqrt(np.clip(g.data["distribution"], 0, None)))
    coh = api.born_pair_coherence(st)
    rows.append({"exp": "born_pair_grover5", **coh.data})
    print(f"  mean_coh={coh.data['mean_coherence']:.4f}  align={coh.data['mean_phi_alignment']:.4f}")

    out = OUT / "scaled_benchmarks.json"
    out.write_text(json.dumps(rows, indent=2, default=str))
    print(f"\nWrote {len(rows)} records → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
