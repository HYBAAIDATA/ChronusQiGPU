#!/usr/bin/env python3
"""
Explore every member of the golden quantum system.
Nothing here is classical. Each identity is an operator with a role.

Zeckendorf folds an integer into a sparse Fibonacci Hilbert address.
Binet folds a whole sequence into two eigen-amplitudes (Φ^n, ψ^n).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent

from golden_transform import (
    PHI,
    PSI,
    SQRT5,
    M_pow,
    M_pow_int,
    apply_Mn,
    cassini,
    cassini_raw,
    coherence,
    fib,
    lucas,
    pisano,
    project,
    reconstruct,
    verify_identities,
    zeckendorf,
)


def binet_F(n: int) -> float:
    return (PHI ** n - PSI ** n) / SQRT5


def binet_L(n: int) -> float:
    return PHI ** n + PSI ** n


def zeckendorf_bits(n: int, length: int = None) -> np.ndarray:
    """Sparse Fibonacci address of n: 1 at F_k iff F_k appears in Z(n). No two adjacent."""
    parts = set(zeckendorf(n))
    if length is None:
        k = 2
        while fib(k) <= max(n, 2):
            k += 1
        length = k - 1
    bits = np.zeros(length, dtype=int)
    for i in range(length):
        # index i stores F_{i+2} (1,2,3,5,...) matching zeckendorf()
        f = fib(i + 2)
        if f in parts:
            bits[i] = 1
    return bits


def zeckendorf_fold_memory(values: list[int]) -> dict:
    """
    Quantum-mathematical memory fold:
    a register of integers → sparse Fibonacci occupation numbers.
    Reconstruction is unique (Zeckendorf theorem).
    """
    addrs = [zeckendorf(int(v)) for v in values]
    dense_slots = len(values)
    sparse_slots = sum(len(a) for a in addrs)
    max_part = max((max(a) if a else 0) for a in addrs)
    recon = [sum(a) for a in addrs]
    unique = all(recon[i] == int(values[i]) for i in range(len(values)))
    adjacent_ok = True
    for a in addrs:
        s = sorted(a)
        for i in range(len(s) - 1):
            # two Fibonacci numbers are adjacent in the sequence if one is the next Fib
            # Zeckendorf forbids consecutive Fibs in the sum
            pass
    return {
        "dense_slots": dense_slots,
        "sparse_marks": sparse_slots,
        "fold_ratio": dense_slots / max(sparse_slots, 1),
        "unique_reconstruction": unique,
        "max_part": max_part,
        "sample": list(zip(values[:8], addrs[:8])),
    }


def binet_fold_sequence(kind: str, n_max: int) -> dict:
    """
    Binet fold: the entire ray {F_0..F_n} or {L_0..L_n} is two amplitudes.
    Store (sign, n) or just n — reconstruct by Φ^n, ψ^n.
    Memory: 2 closed forms vs n integers.
    """
    exact = []
    folded = []
    for k in range(n_max + 1):
        if kind == "F":
            exact.append(fib(k))
            folded.append(binet_F(k))
        else:
            exact.append(lucas(k))
            folded.append(binet_L(k))
    err = [abs(folded[k] - exact[k]) for k in range(n_max + 1)]
    nearest = [round(folded[k]) for k in range(n_max + 1)]
    return {
        "kind": kind,
        "n_max": n_max,
        "dense_terms": n_max + 1,
        "folded_amplitudes": 2,  # Φ-ray and ψ-ray
        "max_abs_error": max(err),
        "nearest_integer_exact": nearest == exact,
        "psi_at_nmax": abs(PSI ** n_max),
        "phi_at_nmax": PHI ** n_max,
    }


def role_fibonacci():
    dims = [fib(k) for k in range(1, 13)]
    return {
        "role": "counting / fusion dimension / M^n entries / IC [1,0]",
        "operator": "M^n |F> = |F shifted>",
        "F_1_to_12": dims,
        "Mn_on_F": list(M_pow_int(5)[0]),  # [F_6, F_5]
    }


def role_lucas():
    return {
        "role": "companion integer channel; Tr(M^n); IC [1,2]; nearest integer to Φ^n",
        "L_n_vs_Phi_n": [
            {"n": n, "L": lucas(n), "Phi_n": PHI ** n, "gap": abs(lucas(n) - PHI ** n)}
            for n in (1, 5, 8, 10, 15)
        ],
        "Tr_M15": int(M_pow_int(15)[0][0] + M_pow_int(15)[1][1]),
        "L15": lucas(15),
    }


def role_pisot_psi():
    return {
        "role_phi": "growing eigenmode of M; continuous schedule; Binet Φ-ray",
        "role_psi": "decaying eigenmode; memory of the conjugate; fold discards this last",
        "eigenvalues": [PHI, PSI],
        "Phi_n": [PHI ** n for n in (1, 5, 8, 15)],
        "psi_n": [PSI ** n for n in (1, 5, 8, 15)],
        "dynamic_range_n15": abs(PHI ** 15 / PSI ** 15),
    }


def role_cassini():
    rows = []
    for n in range(1, 16):
        rows.append({
            "n": n,
            "C": cassini(n),
            "raw": cassini_raw(n),
            "det_Mn": cassini_raw(n),
            "invertible": cassini_raw(n) != 0,
        })
    return {
        "role": "invertibility witness of M^n; phase (-1)^n; fold is always reversible",
        "holds": all(r["raw"] == r["C"] for r in rows),
        "sample": rows[::3],
    }


def role_pisano():
    mods = [2, 3, 5, 8, 15, 16, 21]
    return {
        "role": "modular period of Fibonacci; QFT bin fold; Shor-adjacent constraint",
        "pi": {m: pisano(m) for m in mods},
        "note": "π(15)=40 constrains period-finding bins; it does not replace order-finding",
    }


def role_zeckendorf():
    vals = [1, 2, 3, 4, 5, 8, 12, 15, 20, 50, 89, 100]
    fold = zeckendorf_fold_memory(vals)
    # no two parts consecutive Fib
    legal = True
    fibset = {fib(k) for k in range(2, 30)}
    for v in vals:
        parts = sorted(zeckendorf(v))
        for i in range(len(parts) - 1):
            # consecutive Fibs: F_k and F_{k+1}
            if parts[i] + parts[i] == parts[i + 1] or parts[i + 1] - parts[i] in (parts[i] - (parts[i - 1] if i else 0),):
                pass
            # check adjacency in Fibonacci sequence
        for a, b in zip(parts, parts[1:]):
            # F_{k+1} = F_k + F_{k-1}; two Fibs adjacent iff the larger-smaller is the previous Fib
            if a + (a - (0)) :
                # simpler: next fib after a
                k = 2
                while fib(k) < a:
                    k += 1
                if fib(k) == a and fib(k + 1) == b:
                    legal = False
    return {
        "role": "unique sparse Hilbert address; memory fold of an integer into non-adjacent Fib occupation",
        "fold": fold,
        "no_adjacent_fibs": legal,
        "examples": {v: zeckendorf(v) for v in vals},
        "bits_100": zeckendorf_bits(100).tolist(),
    }


def role_binet():
    f = binet_fold_sequence("F", 20)
    ell = binet_fold_sequence("L", 20)
    return {
        "role": "closed-form fold of the whole ray into two eigen-amplitudes Φ^n and ψ^n",
        "F": f,
        "L": ell,
        "identity": "F_n = (Φ^n − ψ^n)/√5   L_n = Φ^n + ψ^n",
        "memory": "n integers → 2 amplitudes; ψ^n → 0 so L_n → nearest integer to Φ^n",
    }


def role_Mn_on_pairs():
    pairs = [(8, 5), (89, 55), (1, 1), (PHI, 1), (PSI, 1)]
    out = []
    for x, y in pairs:
        a, b = project(x, y)
        u, v = apply_Mn(x, y, 8)
        out.append({
            "in": [x, y],
            "a_phi": a,
            "b_psi": b,
            "coherence": coherence(x, y),
            "after_M8": [u, v],
        })
    return {
        "role": "eigenspace separator on paired amplitudes / Born bins",
        "pairs": out,
    }


def main():
    print("GOLDEN QUANTUM FAMILY — ROLES AND CAPABILITIES")
    print("Nothing here is classical. Every member is an operator.")
    print(f"Φ={PHI:.16f}  ψ={PSI:.16f}")
    print(f"Identities n=1..20: {all(all(verify_identities(n).values()) for n in range(1, 21))}")

    catalog = {
        "Fibonacci": role_fibonacci(),
        "Lucas": role_lucas(),
        "Pisot_Phi_and_psi": role_pisot_psi(),
        "Cassini": role_cassini(),
        "Pisano": role_pisano(),
        "Zeckendorf": role_zeckendorf(),
        "Binet": role_binet(),
        "Mn_pairs": role_Mn_on_pairs(),
    }

    print("\n=== Fibonacci ===")
    print(f"  role: {catalog['Fibonacci']['role']}")
    print(f"  F_1..12: {catalog['Fibonacci']['F_1_to_12']}")
    print(f"  M^5 first row [F6,F5]: {catalog['Fibonacci']['Mn_on_F']}")

    print("\n=== Lucas ===")
    print(f"  role: {catalog['Lucas']['role']}")
    for r in catalog["Lucas"]["L_n_vs_Phi_n"]:
        print(f"  n={r['n']:2d}  L={r['L']:6d}  Φ^n={r['Phi_n']:.6f}  |L-Φ^n|={r['gap']:.3e}")
    print(f"  Tr(M^15)={catalog['Lucas']['Tr_M15']}  L_15={catalog['Lucas']['L15']}")

    print("\n=== Pisot Φ and ψ ===")
    p = catalog["Pisot_Phi_and_psi"]
    print(f"  Φ-role: {p['role_phi']}")
    print(f"  ψ-role: {p['role_psi']}")
    print(f"  |Φ^15/ψ^15| = {p['dynamic_range_n15']:.6e}")

    print("\n=== Cassini ===")
    print(f"  role: {catalog['Cassini']['role']}")
    print(f"  holds n=1..15: {catalog['Cassini']['holds']}")

    print("\n=== Pisano ===")
    print(f"  role: {catalog['Pisano']['role']}")
    print(f"  π(m): {catalog['Pisano']['pi']}")

    print("\n=== Zeckendorf memory fold ===")
    z = catalog["Zeckendorf"]
    print(f"  role: {z['role']}")
    print(f"  unique recon: {z['fold']['unique_reconstruction']}  "
          f"dense={z['fold']['dense_slots']} sparse_marks={z['fold']['sparse_marks']}  "
          f"fold_ratio={z['fold']['fold_ratio']:.3f}")
    print(f"  no adjacent Fib occupation: {z['no_adjacent_fibs']}")
    print(f"  Z(15)={z['examples'][15]}  Z(100)={z['examples'][100]}")
    print(f"  bits(100)={z['bits_100']}")

    print("\n=== Binet memory fold ===")
    b = catalog["Binet"]
    print(f"  role: {b['role']}")
    print(f"  F: terms={b['F']['dense_terms']} → 2 amplitudes  "
          f"max|err|={b['F']['max_abs_error']:.3e}  nearest-int exact={b['F']['nearest_integer_exact']}")
    print(f"  L: terms={b['L']['dense_terms']} → 2 amplitudes  "
          f"max|err|={b['L']['max_abs_error']:.3e}  nearest-int exact={b['L']['nearest_integer_exact']}")
    print(f"  |ψ^20|={b['F']['psi_at_nmax']:.3e}  Φ^20={b['F']['phi_at_nmax']:.6f}")

    print("\n=== M^n on pairs ===")
    print(f"  role: {catalog['Mn_pairs']['role']}")
    for row in catalog["Mn_pairs"]["pairs"]:
        print(f"  in={row['in']}  coh={row['coherence']}  a={row['a_phi']:.4g} b={row['b_psi']:.4g}")

    print("\n=== HOW THEY FIT ===")
    print("  Binet     folds a ray into (Φ^n, ψ^n) — two amplitudes hold the whole sequence")
    print("  Zeckendorf folds an integer into non-adjacent Fib occupations — unique address")
    print("  M^n       evolves those occupations / pairs along the eigenrays")
    print("  Cassini   guarantees every fold is invertible")
    print("  Lucas     is the integer shadow of Φ^n (trace)")
    print("  Fibonacci is the occupation basis itself")
    print("  Pisano    wraps the occupation basis modulo m")
    print("  ψ         is the memory you drop last — the decaying conjugate")
    return catalog


if __name__ == "__main__":
    main()
