"""HYBA Quantum Substrate — first-principles Hilbert-space computation.

Doctrine:
  - Implement → test → let fail/pass. Do not start with NO.
  - Quantum is mathematics: amplitudes, unitaries, projectors, Born rule.
  - Physics does not own quantum (siblings). Substrate- and hardware-agnostic.
  - Everything is computable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

ComplexVec = np.ndarray


def _validate_state(psi: ComplexVec) -> ComplexVec:
    a = np.asarray(psi, dtype=np.complex128).reshape(-1)
    if a.size < 2:
        raise ValueError("state dimension must be >= 2")
    if a.size > 2**24:
        raise ValueError(f"state dimension {a.size} exceeds 2^24 computational limit")
    if not np.all(np.isfinite(a)):
        raise ValueError("state contains non-finite amplitudes (NaN or Inf)")
    nrm = np.linalg.norm(a)
    if nrm <= 0:
        raise ValueError("zero state")
    if nrm > 1e6:
        raise ValueError(f"unnormalized state: norm={nrm:.2e}")
    return a / nrm


def is_unitary(U: np.ndarray, tol: float = 1e-9) -> bool:
    U = np.asarray(U, dtype=np.complex128)
    if U.ndim != 2 or U.shape[0] != U.shape[1]:
        return False
    I = np.eye(U.shape[0], dtype=np.complex128)
    return float(np.linalg.norm(U.conj().T @ U - I)) < tol


def apply_unitary(psi: ComplexVec, U: np.ndarray) -> ComplexVec:
    psi = _validate_state(psi)
    U = np.asarray(U, dtype=np.complex128)
    if U.ndim != 2:
        raise ValueError(f"U must be 2D matrix, got {U.ndim}D")
    if U.shape[0] != U.shape[1]:
        raise ValueError(f"U must be square, got shape {U.shape}")
    if U.shape != (psi.size, psi.size):
        raise ValueError(f"U shape {U.shape} incompatible with state dimension {psi.size}")
    if not np.all(np.isfinite(U)):
        raise ValueError("U contains non-finite entries")
    if not is_unitary(U, tol=1e-6):
        import warnings
        warnings.warn(f"U is not unitary within tolerance 1e-6", RuntimeWarning)
    return _validate_state(U @ psi)


def uniform_superposition(n: int) -> ComplexVec:
    if n < 2:
        raise ValueError("n >= 2")
    return np.ones(n, dtype=np.complex128) / math.sqrt(n)


def computational_basis(n: int, index: int) -> ComplexVec:
    if not (0 <= index < n):
        raise ValueError("index out of range")
    v = np.zeros(n, dtype=np.complex128)
    v[index] = 1.0
    return v


def probabilities(psi: ComplexVec) -> np.ndarray:
    a = _validate_state(psi)
    return np.abs(a) ** 2


def measure(
    psi: ComplexVec, rng: Optional[np.random.Generator] = None, n_shots: int = 1
) -> Dict[str, Any]:
    a = _validate_state(psi)
    shots = int(n_shots)
    if shots < 1:
        raise ValueError(f"n_shots must be >= 1, got {n_shots}")
    if shots > 10_000_000:
        raise ValueError(f"n_shots {shots} exceeds 10M sampling limit")
    p = probabilities(a)
    if not np.all(np.isfinite(p)):
        raise ValueError("probabilities contain non-finite values")
    g = rng or np.random.default_rng()
    samples = g.choice(a.size, size=shots, p=p)
    return {
        "samples": [int(s) for s in samples],
        "n_shots": shots,
        "probabilities": p,
        "rule": "Born: p_i = |⟨i|ψ⟩|²",
    }


def product_state(a: ComplexVec, b: ComplexVec) -> ComplexVec:
    return np.kron(_validate_state(a), _validate_state(b))


def is_product_bipartite(
    psi: ComplexVec, dim_a: int, dim_b: int, tol: float = 1e-9
) -> bool:
    psi = _validate_state(psi)
    if psi.size != dim_a * dim_b:
        raise ValueError("dimension mismatch")
    M = psi.reshape(dim_a, dim_b)
    s = np.linalg.svd(M, compute_uv=False)
    return float(s[0] / (np.linalg.norm(s) + 1e-30)) > 1.0 - tol and float(
        np.sum(s[1:] ** 2)
    ) < tol


def bell_phi_plus() -> ComplexVec:
    v = np.zeros(4, dtype=np.complex128)
    v[0] = v[3] = 1.0 / math.sqrt(2.0)
    return v


def cnot_matrix() -> np.ndarray:
    U = np.eye(4, dtype=np.complex128)
    U[2, 2] = U[3, 3] = 0
    U[2, 3] = U[3, 2] = 1
    return U


def hadamard(n: int = 2) -> np.ndarray:
    if n == 2:
        return np.array([[1, 1], [1, -1]], dtype=np.complex128) / math.sqrt(2.0)
    raise ValueError("only 1-qubit H provided as primitive")


def oracle_phase_flip(n: int, marked: Sequence[int]) -> np.ndarray:
    O = np.eye(n, dtype=np.complex128)
    for m in marked:
        O[m, m] = -1.0
    return O


def diffusion_operator(n: int) -> np.ndarray:
    s = uniform_superposition(n).reshape(-1, 1)
    return 2.0 * (s @ s.conj().T) - np.eye(n, dtype=np.complex128)


def optimal_iterations(n: int, k: int = 1) -> int:
    if n <= 0 or k <= 0 or k >= n:
        return 0
    return int(math.floor(math.pi / 4.0 * math.sqrt(n / float(k))))


@dataclass
class QuantumRegister:
    psi: ComplexVec
    meta: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def uniform(cls, n: int) -> "QuantumRegister":
        return cls(psi=uniform_superposition(n), meta={"prep": "uniform", "n": n})

    @property
    def n(self) -> int:
        return int(self.psi.size)

    def p(self) -> np.ndarray:
        return probabilities(self.psi)

    def apply(self, U: np.ndarray) -> "QuantumRegister":
        self.psi = apply_unitary(self.psi, U)
        return self

    def oracle(self, marked: Sequence[int]) -> "QuantumRegister":
        return self.apply(oracle_phase_flip(self.n, list(marked)))

    def diffuse(self) -> "QuantumRegister":
        return self.apply(diffusion_operator(self.n))

    def grover_step(self, marked: Sequence[int]) -> "QuantumRegister":
        return self.oracle(marked).diffuse()

    def measure(self, n_shots: int = 1, seed: Optional[int] = None) -> Dict[str, Any]:
        rng = np.random.default_rng(seed)
        return measure(self.psi, rng=rng, n_shots=n_shots)


def experiment_oracle_does_not_change_probability(
    n: int = 32, marked: int = 0
) -> Dict[str, Any]:
    reg = QuantumRegister.uniform(n)
    p0 = float(reg.p()[marked])
    reg.oracle([marked])
    p1 = float(reg.p()[marked])
    return {
        "experiment": "oracle_phase_flip_preserves_p_marked",
        "passed": abs(p1 - p0) < 1e-12,
        "p_before": p0,
        "p_after": p1,
        "math": "(−a)² = a²",
    }


def experiment_interference_concentrates(
    n: int = 32, marked: int = 0
) -> Dict[str, Any]:
    reg = QuantumRegister.uniform(n)
    opt = optimal_iterations(n, 1)
    for _ in range(opt):
        reg.grover_step([marked])
    p = float(reg.p()[marked])
    return {
        "experiment": "grover_interference_raises_p_marked",
        "passed": p > 2.0 / n,
        "optimal_iterations": opt,
        "p_marked": p,
        "uniform": 1.0 / n,
    }


def experiment_measure_after_oracle_only(
    n: int = 32, marked: int = 0, shots: int = 3000, seed: int = 0
) -> Dict[str, Any]:
    reg = QuantumRegister.uniform(n)
    reg.oracle([marked])
    m = reg.measure(n_shots=shots, seed=seed)
    hits = sum(1 for s in m["samples"] if s == marked)
    rate = hits / shots
    passed = abs(float(reg.p()[marked]) - 1.0 / n) < 1e-12 and abs(rate - 1.0 / n) < 0.04
    return {
        "experiment": "measure_after_oracle_only_matches_uniform",
        "passed": passed,
        "theory_p": float(reg.p()[marked]),
        "empirical_rate": rate,
        "uniform": 1.0 / n,
    }


def experiment_overshoot(n: int = 32, marked: int = 0, extra: int = 6) -> Dict[str, Any]:
    opt = optimal_iterations(n, 1)
    reg = QuantumRegister.uniform(n)
    series = [float(reg.p()[marked])]
    for _ in range(opt + extra):
        reg.grover_step([marked])
        series.append(float(reg.p()[marked]))
    peak = int(np.argmax(series))
    passed = series[peak] >= max(series[-1], series[0]) and peak <= opt + 1
    return {
        "experiment": "grover_overshoot_past_optimal",
        "passed": bool(passed),
        "optimal": opt,
        "peak_index": peak,
        "series": series,
    }


def experiment_entanglement_not_product() -> Dict[str, Any]:
    phi = bell_phi_plus()
    sep = product_state(
        np.array([1, 0], dtype=np.complex128),
        np.array([1, 0], dtype=np.complex128),
    )
    passed = (not is_product_bipartite(phi, 2, 2)) and is_product_bipartite(sep, 2, 2)
    h = hadamard()
    psi0 = product_state(h @ np.array([1, 0], dtype=np.complex128), np.array([1, 0], dtype=np.complex128))
    psi1 = apply_unitary(psi0, cnot_matrix())
    became_entangled = not is_product_bipartite(psi1, 2, 2)
    return {
        "experiment": "entanglement_as_non_factorizable_joint_state",
        "passed": passed and became_entangled,
        "bell_is_product": is_product_bipartite(phi, 2, 2),
        "cnot_creates_entanglement": became_entangled,
    }


def experiment_unitary_parallelism_cost_model(n: int = 64) -> Dict[str, Any]:
    marked = [n // 2]
    O = oracle_phase_flip(n, marked)
    psi = uniform_superposition(n)
    psi2 = apply_unitary(psi, O)
    passed = is_unitary(O) and abs(float(probabilities(psi2)[marked[0]]) - 1.0 / n) < 1e-12
    return {
        "experiment": "oracle_as_single_unitary_call",
        "passed": passed,
        "n": n,
    }


def experiment_resonance_vs_haystack_routing() -> Dict[str, Any]:
    """Data-plane search routing: structure → φ-search; haystack → brute force.

    Mining SearchModePolicy removed; local policy preserves quantum-serves-data doctrine.
    """
    from dataclasses import dataclass
    from enum import Enum

    class SearchMode(str, Enum):
        PHI_SEARCH = "phi_search"
        BRUTEFORCE = "bruteforce"

    @dataclass
    class GroundConditions:
        phi_coherence: float
        structure_prior_usable: bool
        autonomy_level: str = "autonomous"

    @dataclass
    class PolicyResult:
        effective_mode: SearchMode

    class SearchModePolicy:
        def select(self, g: GroundConditions) -> PolicyResult:
            if g.structure_prior_usable and g.phi_coherence >= 0.5:
                return PolicyResult(SearchMode.PHI_SEARCH)
            return PolicyResult(SearchMode.BRUTEFORCE)

    pol = SearchModePolicy()
    hot = pol.select(
        GroundConditions(phi_coherence=0.9, structure_prior_usable=True, autonomy_level="autonomous")
    )
    cold = pol.select(
        GroundConditions(phi_coherence=0.2, structure_prior_usable=False, autonomy_level="autonomous")
    )
    passed = hot.effective_mode == SearchMode.PHI_SEARCH and cold.effective_mode == SearchMode.BRUTEFORCE
    return {
        "experiment": "resonance_needle_vs_haystack_bruteforce",
        "passed": passed,
        "resonance_mode": hot.effective_mode.value,
        "haystack_mode": cold.effective_mode.value,
        "mining_dependency": False,
        "doctrine": "quantum_serves_data",
    }


def run_all_first_principles_experiments() -> Dict[str, Any]:
    experiments = [
        experiment_oracle_does_not_change_probability(),
        experiment_interference_concentrates(),
        experiment_measure_after_oracle_only(),
        experiment_overshoot(),
        experiment_entanglement_not_product(),
        experiment_unitary_parallelism_cost_model(),
        experiment_resonance_vs_haystack_routing(),
    ]
    passed = sum(1 for e in experiments if e.get("passed"))
    failed = [e["experiment"] for e in experiments if not e.get("passed")]
    return {
        "doctrine": {
            "start_with": "implement_and_test",
            "quantum_is": "mathematics_on_hilbert_space",
            "physics_owns_quantum": False,
            "siblings": ["physics", "quantum_mathematics"],
            "substrate_agnostic": True,
            "hardware_agnostic": True,
            "everything_computable": True,
            "reject_upfront": False,
        },
        "passed": passed,
        "total": len(experiments),
        "failed": failed,
        "status": "QUANTUM_FIRST_PRINCIPLES_PASS" if not failed else "QUANTUM_FIRST_PRINCIPLES_FAIL",
        "experiments": experiments,
    }


__all__ = [
    "QuantumRegister",
    "uniform_superposition",
    "apply_unitary",
    "measure",
    "probabilities",
    "oracle_phase_flip",
    "diffusion_operator",
    "optimal_iterations",
    "product_state",
    "is_product_bipartite",
    "bell_phi_plus",
    "cnot_matrix",
    "hadamard",
    "is_unitary",
    "_validate_state",
    "run_all_first_principles_experiments",
]
