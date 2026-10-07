"""Evidence-gated extension of the MLA1517 algebraic family.

This module separates verified algebraic identities from domain hypotheses.
It does not claim that a root alone proves drug affinity, forecast stability,
or power-grid anti-resonance.
"""
from __future__ import annotations
import math
from typing import Any
import numpy as np


def bisect_root(poly, lo: float, hi: float, iterations: int = 120) -> float:
    flo, fhi = poly(lo), poly(hi)
    if flo == 0: return lo
    if fhi == 0: return hi
    if flo * fhi > 0: raise ValueError("interval does not bracket a root")
    for _ in range(iterations):
        mid = (lo + hi) / 2.0
        fm = poly(mid)
        if fm == 0: return mid
        if flo * fm <= 0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    return (lo + hi) / 2.0


class ExtendedAlgebra:
    """Deterministic algebraic roots and recurrence families."""
    def __init__(self) -> None:
        self.phi = (1.0 + math.sqrt(5.0)) / 2.0
        self.silver = 1.0 + math.sqrt(2.0)
        self.plastic = bisect_root(lambda x: x**3 - x - 1.0, 1.0, 1.5)
        self.supergolden = bisect_root(lambda x: x**3 - x**2 - 1.0, 1.0, 2.0)
        self.tribonacci = bisect_root(lambda x: x**3 - x**2 - x - 1.0, 1.0, 2.0)

    def roots(self) -> dict[str, float]:
        return {
            "phi": self.phi,
            "silver": self.silver,
            "plastic": self.plastic,
            "supergolden": self.supergolden,
            "tribonacci": self.tribonacci,
        }

    @staticmethod
    def padovan_sequence(length: int) -> list[int]:
        seq = [1, 1, 1]
        for _ in range(max(0, length - 3)):
            seq.append(seq[-2] + seq[-3])
        return seq[:length]

    @staticmethod
    def narayana_sequence(length: int) -> list[int]:
        seq = [1, 1, 1]
        for _ in range(max(0, length - 3)):
            seq.append(seq[-1] + seq[-3])
        return seq[:length]

    @staticmethod
    def tribonacci_sequence(length: int) -> list[int]:
        seq = [0, 0, 1]
        for _ in range(max(0, length - 3)):
            seq.append(seq[-1] + seq[-2] + seq[-3])
        return seq[:length]

    @staticmethod
    def spectral_gap(adjacency: np.ndarray) -> dict[str, Any]:
        a = np.asarray(adjacency, dtype=float)
        if a.ndim != 2 or a.shape[0] != a.shape[1]:
            raise ValueError("adjacency must be square")
        lap = np.diag(a.sum(axis=1)) - a
        eigs = np.linalg.eigvalsh(lap)
        gap = float(eigs[1] - eigs[0]) if len(eigs) > 1 else 0.0
        return {
            "laplacian_gap": gap,
            "connected_by_gap": bool(gap > 1e-12),
            "interpretation": "graph connectivity/stability metric only",
        }

    def recurrence_roots(self, family: str) -> np.ndarray:
        if family == "padovan":
            # x^3 - x - 1
            return np.roots([1.0, 0.0, -1.0, -1.0])
        if family == "narayana":
            # x^3 - x^2 - 1
            return np.roots([1.0, -1.0, 0.0, -1.0])
        if family == "tribonacci":
            # x^3 - x^2 - x - 1
            return np.roots([1.0, -1.0, -1.0, -1.0])
        raise ValueError(family)

    def pisot_conjugate_moduli(self, family: str) -> list[float]:
        roots = self.recurrence_roots(family)
        dominant = max(roots, key=lambda z: abs(z))
        return sorted(float(abs(z)) for z in roots if abs(z - dominant) > 1e-8)

    def metallic_frequencies(self, base_freq: float = 50.0) -> np.ndarray:
        return base_freq * np.array([1.0, self.phi, self.silver, self.plastic, self.supergolden])


def run_extended_tests() -> dict[str, Any]:
    e = ExtendedAlgebra()
    r = e.roots()
    tests: list[dict[str, Any]] = []
    def check(name: str, passed: bool, details: Any) -> None:
        tests.append({"name": name, "status": "PASS" if passed else "FAIL", "details": details})
        if not passed:
            raise AssertionError(f"{name}: {details}")

    check("root_polynomials", 
          abs(r["plastic"]**3-r["plastic"]-1) < 1e-14 and
          abs(r["supergolden"]**3-r["supergolden"]**2-1) < 1e-14 and
          abs(r["tribonacci"]**3-r["tribonacci"]**2-r["tribonacci"]-1) < 1e-14,
          r)
    check("plastic_identity_rho5_corrected", abs(r["plastic"]**5-r["plastic"]**2-r["plastic"]-1) < 1e-13, r["plastic"])
    pad = e.padovan_sequence(30)
    nar = e.narayana_sequence(30)
    tri = e.tribonacci_sequence(30)
    check("padovan_recurrence", all(x == pad[i-2]+pad[i-3] for i, x in enumerate(pad) if i >= 3), pad[:12])
    check("narayana_recurrence", all(x == nar[i-1]+nar[i-3] for i, x in enumerate(nar) if i >= 3), nar[:12])
    check("tribonacci_recurrence", all(x == tri[i-1]+tri[i-2]+tri[i-3] for i, x in enumerate(tri) if i >= 3), tri[:12])
    moduli = {f: e.pisot_conjugate_moduli(f) for f in ("padovan", "narayana", "tribonacci")}
    check("conjugate_moduli_contract", all(max(v) < 1.0 for v in moduli.values()), moduli)
    a = np.array([[0,1,0],[1,0,1],[0,1,0]], float)
    gap = e.spectral_gap(a)
    check("spectral_gap_is_connectivity_metric", gap["connected_by_gap"], gap)

    # Hypotheses: intentionally not promoted to production capabilities.
    freq = e.metallic_frequencies()
    harmonic_matches = []
    for i in range(len(freq)):
        for j in range(i+1, len(freq)):
            for m in range(1, 21):
                for n in range(1, 21):
                    rel = abs(m*freq[i] - n*freq[j]) / max(m*freq[i], n*freq[j])
                    if rel < 1e-3:
                        harmonic_matches.append((i, j, m, n, float(rel)))
    hypotheses = [
        {"name": "claimed_plastic_identity_rho5_equals_rho2_plus_1", "status": "REFUTED", "reason": "correct identity is rho^5 = rho^2 + rho + 1"},
        {"name": "plastic_root_implies_3d_optimal_packing", "status": "UNTESTED", "reason": "requires geometric packing benchmark"},
        {"name": "spectral_gap_implies_drug_binding_affinity", "status": "REJECTED_AS_STATED", "reason": "gap establishes graph connectivity, not molecular binding energy"},
        {"name": "pisot_filter_eliminates_arbitrary_predictive_chaos", "status": "UNTESTED", "reason": "requires matched forecasting baselines and recurrence-specific assumptions"},
        {"name": "metallic_ratios_guarantee_zero_grid_harmonic_overlap", "status": "NOT_PROVEN", "reason": "finite harmonic scan found near matches; no zero-overlap guarantee", "near_matches": harmonic_matches[:10], "near_match_count": len(harmonic_matches)},
        {"name": "golden_log_spiral_eliminates_turbine_tip_stall", "status": "UNTESTED", "reason": "requires CFD/experimental fluid validation"},
    ]
    return {"roots": r, "tests": tests, "hypotheses": hypotheses}


if __name__ == "__main__":
    result = run_extended_tests()
    print(json_dumps := __import__("json").dumps(result, indent=2))
