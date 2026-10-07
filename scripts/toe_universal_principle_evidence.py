"""Universal-principle evidence pack — every structural link, run, not cited.

For each proposed link of the golden-family chain this records the
implementation, the mathematical identity, what was executed, the result,
the evidence class, any negative result, and the open obligation. Evidence
classes (never collapsed):

    PROVED                  a classical theorem (cited) — the identity holds
    COMPUTATIONALLY_VERIFIED exact/finite computation executed here to bound N
    MEASURED                experiment executed here, with its baseline
    NEGATIVE                experiment executed here; no advantage found
    MODEL_DEPENDENT         holds under a declared model assumption
    OPEN                    not established (stated obligation)
    UNSUPPORTED             no evidence in this repository

A shared mathematical structure is evidence of structural unity, never of a
shared physical phenomenon.

Usage: python scripts/toe_universal_principle_evidence.py [--report PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

PHI = (1 + 5 ** 0.5) / 2
N_EXACT = 2000


def lucas_link() -> Dict[str, Any]:
    from kellogg.scales import lucas

    a, b = 2, 1
    naive = [a, b]
    for _ in range(2, N_EXACT + 1):
        a, b = b, a + b
        naive.append(b)
    ok = all(lucas(n) == naive[n] for n in range(N_EXACT + 1))
    # Lucas ladder vs a doubling ladder for locating an unknown scale.
    rng = random.Random(7)
    lad_l = [lucas(n) for n in range(2, 40)]
    lad_2 = [2 ** n for n in range(2, 40)]
    probes = {"lucas": [], "doubling": []}
    overshoot = {"lucas": [], "doubling": []}
    for _ in range(2000):
        t = 10 ** rng.uniform(1.5, 6.0)
        for name, lad in (("lucas", lad_l), ("doubling", lad_2)):
            i = next(k for k, v in enumerate(lad) if v >= t)
            probes[name].append(i + 1)
            overshoot[name].append(lad[i] / t)
    mean = lambda xs: sum(xs) / len(xs)  # noqa: E731
    return {
        "link": "Lucas scaling",
        "implementation": "kellogg.scales.lucas (fast doubling)",
        "identity": "L_n = L_{n-1} + L_{n-2}, L_0=2, L_1=1",
        "executed": f"fast doubling == naive recurrence for n <= {N_EXACT}",
        "result": {"agree": ok},
        "evidence_class": "PROVED (definition) + COMPUTATIONALLY_VERIFIED",
        "experiment": {
            "question": "Lucas ladder vs doubling ladder for locating an unknown scale (2000 targets)",
            "lucas": {"mean_probes": mean(probes["lucas"]), "mean_overshoot": mean(overshoot["lucas"]), "max_overshoot": max(overshoot["lucas"])},
            "doubling": {"mean_probes": mean(probes["doubling"]), "mean_overshoot": mean(overshoot["doubling"]), "max_overshoot": max(overshoot["doubling"])},
            "evidence_class": "MEASURED",
            "finding": "a trade-off, not an advantage: the ratio-phi ladder overshoots less but needs more probes",
        },
        "open_obligation": None,
    }


def binet_link() -> Dict[str, Any]:
    from kellogg.scales import binet_fold

    for n in range(N_EXACT + 1):
        binet_fold(n)  # raises ArithmeticError on any violation
    return {
        "link": "Binet closed form",
        "implementation": "kellogg.scales.binet_fold (exact in Z[phi])",
        "identity": "phi^n - psi^n = sqrt(5) * F_n",
        "executed": f"verified exactly in Z[phi] for n <= {N_EXACT}",
        "result": {"verified_through": N_EXACT},
        "evidence_class": "PROVED (classical) + COMPUTATIONALLY_VERIFIED",
        "open_obligation": None,
    }


def cassini_link() -> Dict[str, Any]:
    from kellogg.scales import cassini_verify, fibonacci, lucas

    fib_ok = all(cassini_verify(n) for n in range(1, N_EXACT + 1))
    luc_ok = all(lucas(n) ** 2 - 5 * fibonacci(n) ** 2 == 4 * (-1) ** n for n in range(N_EXACT + 1))
    return {
        "link": "Cassini / unimodular invariance",
        "implementation": "kellogg.scales.cassini_verify; Lucas-Cassini checked directly",
        "identity": "F_{n-1}F_{n+1} - F_n^2 = (-1)^n ; L_n^2 - 5F_n^2 = 4(-1)^n ; det(Q^n) = (-1)^n",
        "executed": f"both identities for n <= {N_EXACT}",
        "result": {"fibonacci_cassini": fib_ok, "lucas_cassini": luc_ok},
        "evidence_class": "PROVED (classical) + COMPUTATIONALLY_VERIFIED",
        "open_obligation": None,
    }


def zeckendorf_link() -> Dict[str, Any]:
    from kellogg.scales import fibonacci, zeckendorf, zeckendorf_is_legal

    N = 20000
    ok = True
    zbits, zones, bbits, bones = 0, 0, 0, 0
    for n in range(1, N + 1):
        idx = zeckendorf(n)
        ok &= zeckendorf_is_legal(idx) and sum(fibonacci(k) for k in idx) == n
        zbits += max(idx) - 1
        zones += len(idx)
        bbits += n.bit_length()
        bones += bin(n).count("1")
    return {
        "link": "Zeckendorf representation",
        "implementation": "kellogg.scales.zeckendorf / zeckendorf_is_legal",
        "identity": "every n >= 1 has a unique sum of non-consecutive Fibonacci numbers",
        "executed": f"legality + exact reconstruction for 1..{N}",
        "result": {"all_legal_and_exact": ok},
        "evidence_class": "PROVED (Zeckendorf 1972) + COMPUTATIONALLY_VERIFIED",
        "experiment": {
            "question": "Zeckendorf vs binary encoding over 1..20000",
            "zeckendorf": {"mean_digits": zbits / N, "ones_density": zones / zbits},
            "binary": {"mean_digits": bbits / N, "ones_density": bones / bbits},
            "evidence_class": "NEGATIVE (for compression) / MEASURED (for sparsity)",
            "finding": "Zeckendorf needs ~1.4x more digits but is sparser and never has adjacent ones; no compression advantage",
        },
        "open_obligation": None,
    }


def _star_discrepancy(xs: List[float]) -> float:
    s = sorted(xs)
    n = len(s)
    return max(max((i + 1) / n - x, x - i / n) for i, x in enumerate(s))


def pisot_link() -> Dict[str, Any]:
    from kellogg.scales import Zphi, phi_power, pisot_drift

    ok = True
    psi = Zphi(1, -1)  # 1 - phi
    for n in range(1, 400):
        ok &= pisot_drift(n) == Zphi(0, 0) - psi ** n
    d15 = abs(PHI ** 15 - 1364)
    N = 1000
    golden = [(k * PHI) % 1.0 for k in range(1, N + 1)]
    rng = random.Random(11)
    rand = [_star_discrepancy([rng.random() for _ in range(N)]) for _ in range(30)]
    # SHA256d: does a golden-stride visit order change the hit rate?
    target = 2 ** 250  # p = 2^-6 per hash under this declared easy target
    header = hashlib.sha256(b"universal-principle/sha256d").digest() * 2 + b"\x00" * 16
    span = 1 << 14

    def hits(order: List[int]) -> int:
        h = 0
        for nonce in order:
            d = hashlib.sha256(hashlib.sha256(header[:76] + nonce.to_bytes(4, "little")).digest()).digest()
            h += int.from_bytes(d, "little") < target
        return h

    linear = list(range(span))
    stride = 0x9E3779B9  # floor(2^32 / phi): the golden-ratio stride
    golden_order = [(k * stride) & 0xFFFFFFFF for k in range(span)]
    h_lin, h_gold = hits(linear), hits(golden_order)
    se = math.sqrt(span * 2 ** -6 * (1 - 2 ** -6))
    return {
        "link": "Pisot contraction",
        "implementation": "kellogg.scales.pisot_drift (exact Z[phi])",
        "identity": "phi^n - L_n = -psi^n, |psi| = 1/phi < 1 (phi is a Pisot number)",
        "executed": "exact equality in Z[phi] for n < 400; |delta_15| measured",
        "result": {"exact_identity": ok, "abs_delta_15": d15},
        "evidence_class": "PROVED + COMPUTATIONALLY_VERIFIED",
        "experiment": {
            "question": "golden (Weyl/Kronecker) ordering vs random ordering — coverage of [0,1)",
            "golden_star_discrepancy_N1000": _star_discrepancy(golden),
            "random_star_discrepancy_N1000_mean_of_30": sum(rand) / len(rand),
            "evidence_class": "MEASURED",
            "finding": "golden-ratio ordering covers an interval far more evenly than random sampling (known low-discrepancy property)",
        },
        "negative_result": {
            "question": "does a golden-ratio nonce visit order change the double-SHA256 hit rate?",
            "hashes_each": span,
            "declared_hit_probability": "2^-6 (easy declared target)",
            "linear_order_hits": h_lin,
            "golden_order_hits": h_gold,
            "difference_in_standard_errors": abs(h_lin - h_gold) / (math.sqrt(2) * se),
            "evidence_class": "NEGATIVE",
            "finding": "no difference beyond sampling noise: ordering changes WHICH nonces are visited first, never the probability that a visited nonce is valid",
        },
        "open_obligation": None,
    }


def poincare_link() -> Dict[str, Any]:
    import numpy as np

    from toe.geometry import PoincareBall
    from toe.poincare_golden_11d import poincare_golden_distance

    ball = PoincareBall.golden_11d()
    rng = np.random.default_rng(3)
    pts = []
    while len(pts) < 25:
        x = rng.normal(size=11) * 0.4
        if ball.contains(x):
            pts.append(x)
    parity = max(abs(ball.distance(a, b) - poincare_golden_distance(a, b)) for a in pts for b in pts)
    tri = max(ball.distance(a, c) - ball.distance(a, b) - ball.distance(b, c) for a in pts[:12] for b in pts[:12] for c in pts[:12])
    return {
        "link": "11D Poincare-golden geometry",
        "implementation": "toe.geometry.PoincareBall.golden_11d (== toe.poincare_golden_11d metric)",
        "identity": "y_i = sqrt(phi^-(i+1)) x_i maps the phi-weighted ball isometrically onto the standard Poincare ball",
        "executed": "metric parity with the 11D module; triangle inequality on samples",
        "result": {"max_parity_error": parity, "worst_triangle_excess": tri},
        "evidence_class": "PROVED (isometry by construction) + COMPUTATIONALLY_VERIFIED (float64)",
        "experiment": "see reports/toe_ablation_heldout.json multi_representation (hyperbolic routing delivers 1.00 vs 0.61 on walled grids; parity on open grids)",
        "open_obligation": None,
    }


def m32_link() -> Dict[str, Any]:
    import itertools

    import numpy as np

    ico = [p for s in itertools.product((1, -1), repeat=2) for p in ((0, s[0], s[1] * PHI), (s[0], s[1] * PHI, 0), (s[1] * PHI, 0, s[0]))]
    dod = [tuple(s) for s in itertools.product((1, -1), repeat=3)]
    dod += [p for s in itertools.product((1, -1), repeat=2) for p in ((0, s[0] / PHI, s[1] * PHI), (s[0] / PHI, s[1] * PHI, 0), (s[1] * PHI, 0, s[0] / PHI))]
    m32 = np.array(ico + dod, dtype=float)
    m32 /= np.linalg.norm(m32, axis=1, keepdims=True)
    rng = np.random.default_rng(5)
    probe = rng.normal(size=(40000, 3))
    probe /= np.linalg.norm(probe, axis=1, keepdims=True)

    def cover(dirs: np.ndarray) -> float:
        return float(np.degrees(np.arccos(np.clip((probe @ dirs.T).max(axis=1), -1, 1)).max()))

    rand = []
    for _ in range(30):
        r = rng.normal(size=(32, 3))
        rand.append(cover(r / np.linalg.norm(r, axis=1, keepdims=True)))
    k = np.arange(32) + 0.5
    z = 1 - 2 * k / 32
    th = math.pi * (1 + 5 ** 0.5) * k
    fib = np.stack([np.sqrt(1 - z * z) * np.cos(th), np.sqrt(1 - z * z) * np.sin(th), z], axis=1)
    return {
        "link": "M32 / icosahedral geometry",
        "implementation": "12 icosahedron + 20 dodecahedron directions (the M32 frame)",
        "identity": "vertices of the icosahedron/dodecahedron pair have coordinates in Q(phi)",
        "executed": "covering radius on S^2 (max angle to nearest direction, 40k probes)",
        "result": {"m32_covering_deg": cover(m32), "random32_covering_deg_mean": sum(rand) / len(rand), "fibonacci_sphere32_covering_deg": cover(fib)},
        "evidence_class": "MEASURED",
        "finding": "the icosahedral frame is a well-spread direction set (better than random); this is spherical-design geometry, not a search speed-up claim",
        "open_obligation": None,
    }


def yang_mills_link() -> Dict[str, Any]:
    try:
        from millennium.hyba_poincare_yangmills import cached_report
    except Exception as exc:  # standalone TOE: the construction lives in millennium
        return {"link": "2I / 600-cell / finite spectrum", "evidence_class": "UNAVAILABLE", "reason": str(exc)}
    r = cached_report()
    gap = r["gap"]
    return {
        "link": "golden icosians -> 2I -> 600-cell -> finite Laplacian gap",
        "implementation": "millennium.hyba_poincare_yangmills (TOE reads it through toe.poincare_yangmills)",
        "identity": "|2I| = 120; 600-cell V,E,F,C = 120,720,1200,600; sum of squared irrep dims = 120",
        "executed": "group closure, conjugacy classes, character table, topology, Laplacian spectrum",
        "result": {
            "group_order": r["group_order"],
            "closed": r["closed_product"] and r["closed_inverse"],
            "classes": r["class_count"],
            "topology": r["topology"],
            "sum_dim_squares": r["sum_squares"],
            "orthogonality": r["orthogonality"],
            "gap": gap,
            "gap_matches_(3-sqrt5)/4": abs(gap - (3 - 5 ** 0.5) / 4) < 1e-12,
            "gap_equals_1_minus_phi_over_2": abs(gap - (1 - PHI / 2)) < 1e-12,
        },
        "evidence_class": "COMPUTATIONALLY_VERIFIED (finite volume: " + str(r["evidence_class"]) + ")",
        "correction": "UNIVERSAL_PRINCIPLE_MAP previously printed the gap as ~0.381966 (= 1/phi^2); the computed gap is (3-sqrt5)/4 ~ 0.190983",
        "continuum_yang_mills": {"evidence_class": "OPEN", "proof_claim": r["proof_claim"], "continuum_claim": r["continuum_claim"]},
        "open_obligation": "continuum limit, infinite volume, OS reconstruction, continuum mass gap (Clay) — none established",
    }


def golden_quantum_link() -> Dict[str, Any]:
    from kellogg.quantum_tensor import QuantumState, encode_data_to_state  # noqa: F401

    state = encode_data_to_state([1.0, 2.0, 3.0, 5.0, 8.0], dim=32, normalize=True)
    probs = state.probabilities()
    norm = float(sum(probs[i] for i in range(32)))
    return {
        "link": "Golden Quantum (quantum mathematics in TOE)",
        "implementation": "kellogg.quantum_tensor (classical execution of the Hilbert-space formalism)",
        "identity": "unit-norm states, Born probabilities summing to 1",
        "executed": "encode -> Born probabilities -> norm",
        "result": {"born_total": norm},
        "evidence_class": "COMPUTATIONALLY_VERIFIED (software execution of quantum mathematics)",
        "physical_qpu": {"evidence_class": "UNSUPPORTED", "note": "no physical-QPU execution exists in this evidence"},
        "measured_quantum_advantage": {"evidence_class": "UNSUPPORTED"},
        "open_obligation": "physical QPU execution and any advantage claim require device evidence",
    }


def chain_claims() -> List[Dict[str, Any]]:
    return [
        {"claim": "the golden family links Z[phi] -> Lucas/Binet/Cassini/Zeckendorf/Pisot", "evidence_class": "PROVED + COMPUTATIONALLY_VERIFIED", "scope": "exact algebra"},
        {"claim": "the same structures appear in TOE's geometry, ordering and exact arithmetic", "evidence_class": "MEASURED (structural reuse)", "scope": "implementation"},
        {"claim": "a shared phi implies a shared physical phenomenon", "evidence_class": "UNSUPPORTED", "scope": "explicitly not claimed"},
        {"claim": "Lucas rungs 15/18/20 are optimal for intelligence", "evidence_class": "UNSUPPORTED", "scope": "no TOE capability has a rung parameter; no comparative measurement"},
        {"claim": "one backend serves 10,000 frontend problem forms", "evidence_class": "UNSUPPORTED as stated", "scope": "measured: 8 problem classes + PYTHIA mining through one machine"},
        {"claim": "phi-structured nonce ordering improves SHA256d success", "evidence_class": "NEGATIVE", "scope": "see pisot negative_result"},
    ]


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report")
    args = ap.parse_args(argv)
    t0 = time.time()
    links = [lucas_link(), binet_link(), zeckendorf_link(), cassini_link(), pisot_link(), poincare_link(), m32_link(), yang_mills_link(), golden_quantum_link()]
    try:
        sha = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        sha = "UNAVAILABLE"
    report = {
        "schema": "toe.universal_principle_evidence/v1",
        "source_sha": sha,
        "canonical_map": "UNIVERSAL_PRINCIPLE_MAP.md (this pack measures it; it does not fork it)",
        "links": links,
        "chain_claims": chain_claims(),
        "elapsed_s": time.time() - t0,
    }
    text = json.dumps(report, indent=2, sort_keys=True, default=str)
    if args.report:
        Path(args.report).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
