"""
M^n on paired measurement statistics — not on state vectors.

Pairs come from exact Born distributions of quantum algorithms.
No np.random. No sampled collapse. Integer M^n from the frozen core.
"""
from __future__ import annotations

import math
from typing import Dict, List, Sequence, Tuple

import numpy as np
import sys
from pathlib import Path

from golden_transform import PHI, PSI, M_pow, apply_Mn, coherence, fib, project


def pair_born(p: np.ndarray) -> List[Tuple[float, float]]:
    p = np.asarray(p, dtype=float).reshape(-1)
    if p.size % 2:
        p = np.append(p, 0.0)
    return [(float(p[i]), float(p[i + 1])) for i in range(0, p.size, 2)]


def mn_ratio(x: float, y: float, n: int) -> float:
    u, v = apply_Mn(x, y, n)
    if abs(v) < 1e-15:
        return float("inf")
    return u / v


def phi_alignment(x: float, y: float) -> float:
    if abs(y) < 1e-15:
        return 0.0
    r = abs(x / y)
    a = min(r / PHI, PHI / max(r, 1e-15))
    return float(math.exp(-abs(math.log(max(a, 1e-15)))))


def pair_entropy(x: float, y: float) -> float:
    s = abs(x) + abs(y)
    if s <= 0:
        return 0.0
    p1, p2 = abs(x) / s, abs(y) / s
    h = 0.0
    for q in (p1, p2):
        if q > 1e-15:
            h -= q * math.log(q)
    return h


def score_pairs(pairs: Sequence[Tuple[float, float]], ns: Sequence[int] = (1, 2, 3, 5, 8, 13)) -> Dict:
    dist = []
    applied = []
    for x, y in pairs:
        dist.append(coherence(x, y))
        for n in ns:
            u, v = apply_Mn(x, y, n)
            applied.append({
                "n": n,
                "input": [x, y],
                "output": [u, v],
                "ratio": (u / v) if abs(v) > 1e-15 else float("inf"),
            })
    finite = [c for c in dist if math.isfinite(c)]
    amps = []
    for item in applied:
        if item["n"] in (5, 8, 13) and math.isfinite(item["ratio"]) and item["ratio"] > 0:
            amps.append(item["ratio"])
    amp_factors = []
    for i in range(len(amps) - 1):
        if amps[i] > 0:
            amp_factors.append(amps[i + 1] / amps[i])
    mean_c = float(np.mean(finite)) if finite else 0.0
    std_c = float(np.std(finite)) if finite else 0.0
    return {
        "n_pairs": len(pairs),
        "mean_coherence": mean_c,
        "std_coherence": std_c,
        "mean_phi_alignment": float(np.mean([phi_alignment(x, y) for x, y in pairs])) if pairs else 0.0,
        "mean_pair_entropy": float(np.mean([pair_entropy(x, y) for x, y in pairs])) if pairs else 0.0,
        "phi_amplification_factor": float(np.mean(amp_factors)) if amp_factors else 0.0,
        "applied_count": len(applied),
    }


def verify_fib_amplification() -> List[Dict]:
    """Identity check: M^n [F_{k+1}, F_k] stays on the Fibonacci ray."""
    rows = []
    for k, n in ((5, 5), (5, 8), (10, 5), (10, 8), (15, 5)):
        x, y = float(fib(k + 1)), float(fib(k))
        u, v = apply_Mn(x, y, n)
        # Exact: M^n [F_{k+1}, F_k]^T = [F_{k+n+1}, F_{k+n}]^T
        expect_u, expect_v = float(fib(k + n + 1)), float(fib(k + n))
        rows.append({
            "k": k, "n": n,
            "input": [x, y],
            "output": [u, v],
            "expected": [expect_u, expect_v],
            "match": abs(u - expect_u) < 1e-6 and abs(v - expect_v) < 1e-6,
        })
    return rows
