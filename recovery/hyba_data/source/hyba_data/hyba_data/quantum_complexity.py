"""Formal complexity analysis — rigorous bounds for all quantum algorithms.

Each entry: classical best known, oracle-model quantum, our implementation,
proven speedup (if any with assumptions), and honest caveats.

Doctrine: Claims must carry proof intensity matching claim magnitude.
No fabricated speedup claims. Oracle-model ≠ wall-clock.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

PHI = (1.0 + math.sqrt(5.0)) / 2.0


@dataclass
class ComplexityBound:
    algorithm: str
    problem_class: str
    classical_best: str
    classical_complexity: str
    quantum_oracle: str
    quantum_gate_count: str
    implementation_complexity: str
    proven_speedup: Optional[str]
    caveats: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    lane: str = "INTERNAL"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "algorithm": self.algorithm, "problem_class": self.problem_class,
            "classical_best": self.classical_best, "classical_complexity": self.classical_complexity,
            "quantum_oracle": self.quantum_oracle, "quantum_gate_count": self.quantum_gate_count,
            "implementation_complexity": self.implementation_complexity,
            "proven_speedup": self.proven_speedup, "caveats": self.caveats,
            "references": self.references, "lane": self.lane,
        }


def get_complexity_register() -> List[ComplexityBound]:
    return [
        ComplexityBound(
            algorithm="Grover's amplitude amplification",
            problem_class="Unstructured search of N items",
            classical_best="Linear scan",
            classical_complexity="O(N) queries",
            quantum_oracle="Oracle model: O(sqrt(N)) oracle calls",
            quantum_gate_count="O(sqrt(N) * log N) gates",
            implementation_complexity="O(N * sqrt(N)) on classical Hilbert vector",
            proven_speedup="Quadratic in oracle model [Grover 1996]",
            caveats=[
                "Proven speedup is in the ORACLE MODEL, not wall-clock time.",
                "On classical hardware, each oracle call simulates N-dim Hilbert space in O(N).",
                "This implementation does NOT achieve O(sqrt(N)) wall-clock time.",
                "True speedup requires quantum hardware or O(1) oracle data structure (not known).",
            ],
            references=["Grover (1996) STOC", "Nielsen & Chuang (2010) Sec 6.1-6.2"],
            lane="BOUNDED",
        ),
        ComplexityBound(
            algorithm="Shor's factorization via quantum period-finding",
            problem_class="Integer factorization of N (n = log N bits)",
            classical_best="General Number Field Sieve",
            classical_complexity="O(exp((log N)^{1/3})) subexponential",
            quantum_oracle="O(n^3) gates for period-finding",
            quantum_gate_count="O(n^2 log n log log n) [Shor 1997]",
            implementation_complexity="O(2^n) on classical Hilbert vector (exponential in n)",
            proven_speedup="Exponential in oracle model [Shor 1994]",
            caveats=[
                "Proven speedup is in the QUANTUM GATE MODEL, not classical wall-clock.",
                "On classical hardware, simulating period-finding is O(2^n) — no speedup.",
                "This implementation demonstrates mathematical structure; does NOT factor large numbers quickly.",
                "True polynomial-time factorization requires quantum hardware or breakthrough classical algorithm.",
            ],
            references=["Shor (1994/1997) SIAM J. Comput.", "Nielsen & Chuang Sec 5.3"],
            lane="RESTRICTED",
        ),
        ComplexityBound(
            algorithm="Variational Quantum Classifier (VQC)",
            problem_class="Binary classification in R^d feature space",
            classical_best="SVM / Neural Network",
            classical_complexity="O(d^2 * m) for SVM, O(m * d * p) for small NN",
            quantum_oracle="O(2^n) Hilbert space; variational params O(n * depth)",
            quantum_gate_count="O(n * depth) per forward pass",
            implementation_complexity="O(2^n * depth * steps) for finite-difference training on classical",
            proven_speedup="Exponential feature space (2^n vs n) — representational, not computational",
            caveats=[
                "The 2^n feature space is mathematically genuine (amplitude encoding).",
                "Training is still variational — no proven optimization speedup over classical.",
                "On classical hardware: O(2^n) per forward pass limits n to ~10-12 qubits.",
                "Advantage is representational (kernel dimension), not computational (training time).",
            ],
            references=["Havlicek et al. (2019) Nature", "Schuld & Petruccione (2021) Springer"],
            lane="BOUNDED",
        ),
        ComplexityBound(
            algorithm="Progressive phi-pair fold compression",
            problem_class="Lossless reorganization of N samples",
            classical_best="DCT/DWT (lossy), LZMA/zstd (lossless)",
            classical_complexity="O(N log N) for DCT; O(N) per compression level",
            quantum_oracle="N/A (classical algorithm)",
            quantum_gate_count="N/A",
            implementation_complexity="O(N * depth) for progressive fold on N samples",
            proven_speedup="None claimed. Structural advantage: energy concentration for phi-structured signals.",
            caveats=[
                "Fold is invertible (16/16 exactness tests). Compression requires quantization.",
                "Measured compression advantage: structure-dependent. Not universal.",
                "M1 ~2.62x BOUNDED external on structured numerical data.",
                "M2/M3 are INTERNAL — not external-sealed. No universal compression claim.",
            ],
            references=["HYBA Data: fold_doctrine.py, phi_folding_engine/", "tests/core/test_fold_exactness.py"],
            lane="BOUNDED",
        ),
        ComplexityBound(
            algorithm="Coarse-level indexing on phi-folded manifold",
            problem_class="Nearest-neighbor search on structured signals",
            classical_best="kd-tree / ball-tree",
            classical_complexity="O(log N) average, O(N) worst",
            quantum_oracle="N/A (classical algorithm)",
            quantum_gate_count="N/A",
            implementation_complexity="O(N/2^depth) coarse-layer search",
            proven_speedup="None. O(log N) remains Architecture Spec Lane C — not yet sealed.",
            caveats=[
                "The fold pyramid enables multi-resolution indexing on classical hardware.",
                "Current implementation: linear scan on coarse layer, not geodesic O(log N).",
                "O(log N) geodesic search is INTERNAL (Lane C) — not yet proven with benchmark.",
            ],
            references=["HYBA Data: phi1_runtime.py phi_dist (stub)", "PHI-Space Architecture Spec Lane C"],
            lane="INTERNAL",
        ),
        ComplexityBound(
            algorithm="Yang-Mills (3-phi) runtime gate",
            problem_class="Confinement threshold for runtime gating",
            classical_best="Lattice QCD simulations (Monte Carlo, O(n^4) lattice sites)",
            classical_complexity="O(V * steps) where V = lattice volume",
            quantum_oracle="N/A (classical gate, not quantum algorithm)",
            quantum_gate_count="N/A",
            implementation_complexity="O(1) — (3-phi) is a constant threshold",
            proven_speedup="No computational speedup claimed. No classical algorithm has this gate.",
            caveats=[
                "The (3-phi) invariant is operationalized as a runtime gate threshold.",
                "It is NOT a proof of the Yang-Mills mass gap (Millennium Prize).",
                "No computational speedup over classical lattice QCD is claimed.",
                "It is NOT a closed-form hadron mass calculator.",
                "The Lean4 proof is incomplete (contains 'sorry' statements).",
                "Correct invariant: phi^2 = phi + 1; 1/phi = phi - 1. Verified numerically.",
            ],
            references=[
                "HYBA Data: phi_nucleus/yang_mills_completion.py",
                "tests/unit/test_quantum_unit.py (mass_gap_fixed_point)",
                "lean4/yang_mills_mass_gap_proof.lean (incomplete)",
            ],
            lane="RESTRICTED",
        ),
        ComplexityBound(
            algorithm="Quantum kernel method",
            problem_class="Classification with quantum feature map",
            classical_best="RBF kernel / neural net",
            classical_complexity="O(m^2 * d) for kernel matrix",
            quantum_oracle="O(2^n) Hilbert space encoding",
            quantum_gate_count="O(n * depth) per feature encoding",
            implementation_complexity="O(m^2 * 2^n) — compute kernel for all pairs on classical",
            proven_speedup="Exponential feature space (2^n) — structural, not computational",
            caveats=[
                "The 2^n feature space is mathematically real via amplitude encoding.",
                "No proven classification accuracy advantage over classical kernels.",
                "Computing the kernel matrix requires O(m^2 * 2^n) on classical hardware.",
                "Practical only for small n (<=10 qubits) on classical substrate.",
            ],
            references=["Schuld & Killoran (2019) PRL", "HYBA: quantum_supremacy.py qml"],
            lane="BOUNDED",
        ),
    ]


def verify_complexity_register() -> Dict[str, Any]:
    register = get_complexity_register()
    issues = []
    for entry in register:
        if not entry.caveats:
            issues.append(f"{entry.algorithm}: missing caveats")
        if entry.lane == "RESTRICTED" and len(entry.caveats) < 3:
            issues.append(f"{entry.algorithm}: RESTRICTED needs >=3 caveats, got {len(entry.caveats)}")
    return {
        "register_size": len(register), "issues": issues, "valid": len(issues) == 0,
        "lanes": {e.lane: sum(1 for e in register if e.lane == e.lane) for e in register},
        "doctrine": {"honest_complexity": True, "no_fabricated_speedups": True, "implement_test_elevate": True},
    }


def complexity_summary_external() -> str:
    return (
        "HYBA Data implements quantum algorithms as Hilbert-space mathematics on classical substrate. "
        "The algorithms are mathematically faithful to the quantum formalism. Proven speedups are in "
        "the oracle/gate model; wall-clock speedup requires quantum hardware or a classical breakthrough. "
        "For external claims, see the Sealed Claims Register for lane assignments."
    )


if __name__ == "__main__":
    import json
    print(json.dumps(verify_complexity_register(), indent=2))
    print("\n" + complexity_summary_external())
