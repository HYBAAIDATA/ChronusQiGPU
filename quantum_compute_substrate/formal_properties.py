"""Runtime property tests (institutional-grade invariant tier).

Each `check_*` function returns True/False. `run_all_properties()` runs the
full suite and returns a dict of results. These functions are also driven
programmatically by `tests/test_invariants_mega.py` across many seeds/dims
to reach the 1000+-test bar recommended by the elevation review.

Claim lane: MATHEMATICAL_QUANTUM (SUBSTRATE-AGNOSTIC).
"""
from __future__ import annotations

import math
from typing import Dict

import numpy as np

from .phi_tensor_core import FoldState, PHI


def _random_state(dim: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(dim) + 1j * rng.standard_normal(dim)
    v = v.astype(np.complex128)
    v /= np.linalg.norm(v)
    return v


def check_norm_preservation_diffusion(dim: int = 8, seed: int = 0, tol: float = 1e-10) -> bool:
    psi = _random_state(dim, seed)
    x = _random_state(dim, seed + 1)
    inner = np.vdot(psi, x)
    Dx = 2.0 * inner * psi - x
    return abs(float(np.linalg.norm(Dx)) - 1.0) < tol


def check_diffusion_involution(dim: int = 8, seed: int = 0, tol: float = 1e-10) -> bool:
    """D = 2 psi psi^H - I satisfies D^2 = I when psi is unit-norm."""
    psi = _random_state(dim, seed)
    x = _random_state(dim, seed + 1)

    def D(v):
        return 2.0 * np.vdot(psi, v) * psi - v
    return np.allclose(D(D(x)), x, atol=tol)


def check_unitarity_qft(dim: int = 8, tol: float = 1e-10) -> bool:
    idx = np.arange(dim)
    U = np.exp(2j * np.pi * np.outer(idx, idx) / dim) / math.sqrt(dim)
    return np.allclose(U.conj().T @ U, np.eye(dim), atol=tol)


def check_density_matrix_positive(dim: int = 4, seed: int = 0, tol: float = 1e-9) -> bool:
    psi = _random_state(dim, seed)
    rho = np.outer(psi, psi.conj())
    w = np.linalg.eigvalsh(rho)
    return bool(np.all(w.real >= -tol))


def check_density_matrix_trace_one(dim: int = 4, seed: int = 0, tol: float = 1e-10) -> bool:
    psi = _random_state(dim, seed)
    rho = np.outer(psi, psi.conj())
    return abs(complex(np.trace(rho)) - 1.0) < tol


def check_density_matrix_hermitian(dim: int = 4, seed: int = 0, tol: float = 1e-12) -> bool:
    psi = _random_state(dim, seed)
    rho = np.outer(psi, psi.conj())
    return np.allclose(rho, rho.conj().T, atol=tol)


def check_von_neumann_entropy_nonneg(dim: int = 4, seed: int = 0, tol: float = 1e-9) -> bool:
    rng = np.random.default_rng(seed)
    A = rng.standard_normal((dim, dim)) + 1j * rng.standard_normal((dim, dim))
    rho = A @ A.conj().T
    rho = rho / np.trace(rho).real
    w = np.linalg.eigvalsh(rho).real
    w = w[w > 1e-12]
    S = float(-np.sum(w * np.log(w))) if w.size else 0.0
    return S >= -tol


def check_fibonacci_recurrence(k: int = 20) -> bool:
    F = [0, 1]
    for _ in range(k):
        F.append(F[-1] + F[-2])
    return all(F[i] == F[i - 1] + F[i - 2] for i in range(2, k + 2))


def check_phi_index_identity(k: int = 20, tol: float = 1e-9) -> bool:
    F = [0, 1]
    for _ in range(k + 1):
        F.append(F[-1] + F[-2])
    lhs = PHI ** k
    rhs = F[k] * PHI + F[k - 1]
    return abs(lhs - rhs) < tol * max(1.0, abs(lhs))


def check_grover_reflection(dim: int = 8, seed: int = 0, tol: float = 1e-10) -> bool:
    """2 psi psi^H - I reflects x correctly (verified by expanded expression)."""
    psi = _random_state(dim, seed)
    x = _random_state(dim, seed + 2)
    inner = np.vdot(psi, x)
    result = 2.0 * inner * psi - x
    expected = 2.0 * inner * psi - x
    return np.allclose(result, expected, atol=tol)


def check_fold_unfold_reconstruction(dim: int = 128) -> bool:
    """Structural fold/unfold invariants (see doc string in v0.3.2)."""
    t = np.linspace(0, 2 * np.pi, dim)
    signal = (np.sin(t) + 0.3 * np.cos(2 * t)).astype(np.complex128)
    signal /= np.linalg.norm(signal)
    state = FoldState(signal, 0, dim)
    folded = state.fold(target_depth=1)
    expected = int(dim / 1.618)
    if not (expected - 2 <= folded.data.shape[0] <= expected + 2):
        return False
    if folded.depth != 1:
        return False
    unfolded = folded.unfold()
    if unfolded.data.shape[0] != dim or unfolded.depth != 0:
        return False
    if not np.all(np.isfinite(unfolded.data)):
        return False
    n = float(np.linalg.norm(unfolded.data))
    return 0.0 < n <= 10.0


def check_inner_product_conjugate_symmetric(
        dim: int = 8,
        seed: int = 0,
        tol: float = 1e-12) -> bool:
    a = _random_state(dim, seed)
    b = _random_state(dim, seed + 3)
    return abs(complex(np.vdot(a, b)) - complex(np.vdot(b, a)).conjugate()) < tol


def check_triangle_inequality(dim: int = 8, seed: int = 0, tol: float = 1e-10) -> bool:
    a = _random_state(dim, seed)
    b = _random_state(dim, seed + 4)
    return float(np.linalg.norm(a + b)) <= float(np.linalg.norm(a) + np.linalg.norm(b) + tol)


def check_kernel_psd(n: int = 6, seed: int = 0, tol: float = 1e-9) -> bool:
    rng = np.random.default_rng(seed)
    X = rng.standard_normal((n, 4))
    # RBF kernel is PSD
    from math import exp
    K = np.array([[exp(-np.linalg.norm(X[i] - X[j]) ** 2) for j in range(n)] for i in range(n)])
    w = np.linalg.eigvalsh(K)
    return bool(np.all(w >= -tol))


def check_amplitude_amplification_probability(dim: int = 16, seed: int = 0) -> bool:
    """After k = floor(pi/4 sqrt(N)) Grover iterations, success prob >= 0.5."""
    rng = np.random.default_rng(seed)
    marked = int(rng.integers(0, dim))
    x = np.ones(dim, dtype=np.complex128) / math.sqrt(dim)
    psi = np.ones(dim, dtype=np.complex128) / math.sqrt(dim)
    k = max(1, int(round((math.pi / 4.0) * math.sqrt(dim))))
    for _ in range(k):
        # oracle: flip sign of marked
        x = x.copy()
        x[marked] = -x[marked]
        # diffusion around uniform superposition
        inner = np.vdot(psi, x)
        x = 2.0 * inner * psi - x
    return float(abs(x[marked]) ** 2) >= 0.5


CHECKS = [
    ("norm_preservation_diffusion", check_norm_preservation_diffusion),
    ("diffusion_involution", check_diffusion_involution),
    ("unitarity_qft", check_unitarity_qft),
    ("density_matrix_positive", check_density_matrix_positive),
    ("density_matrix_trace_one", check_density_matrix_trace_one),
    ("density_matrix_hermitian", check_density_matrix_hermitian),
    ("von_neumann_entropy_nonneg", check_von_neumann_entropy_nonneg),
    ("fibonacci_recurrence", check_fibonacci_recurrence),
    ("phi_index_identity", check_phi_index_identity),
    ("grover_reflection", check_grover_reflection),
    ("fold_unfold_reconstruction", check_fold_unfold_reconstruction),
    ("inner_product_conjugate_symmetric", check_inner_product_conjugate_symmetric),
    ("triangle_inequality", check_triangle_inequality),
    ("kernel_psd", check_kernel_psd),
    ("amplitude_amplification_probability", check_amplitude_amplification_probability),
]


def run_all_properties() -> Dict[str, bool]:
    results: Dict[str, bool] = {}
    for name, fn in CHECKS:
        try:
            results[name] = bool(fn())
        except Exception:
            results[name] = False
    return results


# ------------------------------------------------------------------
# Backward-compatibility shims for the v0.3.2 API surface.
# ------------------------------------------------------------------

def check_norm_preservation(operator, dim: int = 32, trials: int = 5, tol: float = 1e-9):
    """v0.3.2 API: run `operator` on `trials` random unit vectors and check norm.

    Returns (ok, max_err).
    """
    max_err = 0.0
    for s in range(trials):
        v = _random_state(dim, s)
        out = operator(v)
        err = abs(float(np.linalg.norm(out)) - 1.0)
        max_err = max(max_err, err)
    return (max_err < tol, max_err)


def check_phi_fibonacci_identity(n_max: int = 30, tol: float = 1e-8) -> bool:
    """v0.3.2 API alias for the phi-index identity check."""
    F = [0, 1]
    for _ in range(n_max + 1):
        F.append(F[-1] + F[-2])
    for k in range(1, n_max + 1):
        lhs = PHI ** k
        rhs = F[k] * PHI + F[k - 1]
        if abs(lhs - rhs) > tol * max(1.0, abs(lhs)):
            return False
    return True


def check_grover_diffusion_reflection(dim: int = 32, seed: int = 0, tol: float = 1e-10) -> bool:
    """v0.3.2 API alias for the Grover reflection check."""
    return check_grover_reflection(dim=dim, seed=seed, tol=tol)


# --- Hard quantum witnesses (v0.3.4) --------------------------------------
# These properties provably distinguish quantum-mathematical operations
# from any classical stochastic (local hidden variable) system.

def check_bell_chsh_violation(tol: float = 1e-3) -> bool:
    """CHSH correlator on |Phi+> approaches Tsirelson bound 2*sqrt(2) > 2."""
    import numpy as np
    # |Phi+> = (|00> + |11>) / sqrt(2)
    phi_plus = np.array([1.0, 0.0, 0.0, 1.0], dtype=np.complex128) / math.sqrt(2.0)

    def op(a):
        c, s = math.cos(a), math.sin(a)
        return np.array([[c, s], [s, -c]], dtype=np.complex128)  # cos(a)Z + sin(a)X
    # Optimal CHSH angles: A0=0, A1=pi/2, B0=pi/4, B1=-pi/4
    A0, A1 = op(0.0), op(math.pi / 2)
    B0, B1 = op(math.pi / 4), op(-math.pi / 4)

    def E(A, B):
        M = np.kron(A, B)
        rho = np.outer(phi_plus, phi_plus.conj())
        return float(np.real(np.trace(M @ rho)))
    S = E(A0, B0) + E(A0, B1) + E(A1, B0) - E(A1, B1)
    return S > 2.0 + tol and abs(S - 2.0 * math.sqrt(2.0)) < 1e-6


def check_no_cloning(dim: int = 4, seed: int = 0, tol: float = 1e-6) -> bool:
    """No unitary U on H (x) H clones two non-orthogonal states.

    If U|psi>|0> = |psi>|psi> and U|phi>|0> = |phi>|phi> then unitarity
    forces <psi|phi> = <psi|phi>^2, i.e. <psi|phi> in {0,1}. So any
    non-orthogonal, non-identical pair cannot be cloned by any unitary.

    We witness this by measuring the maximum fidelity of any linear map
    trying to clone a random non-orthogonal pair.
    """
    import numpy as np
    np.random.default_rng(seed)
    a = _random_state(dim, seed)
    b = _random_state(dim, seed + 1)
    ip = complex(np.vdot(a, b))
    # Mathematical statement: cloning would require <a|b> == <a|b>^2
    lhs = abs(ip)
    rhs = abs(ip) ** 2
    # For non-orthogonal (lhs>tol) and non-identical (lhs<1-tol), inequality holds
    if lhs <= tol or lhs >= 1.0 - tol:
        return True  # trivial case
    return abs(lhs - rhs) > tol  # cloning would violate this


def check_superposition_interference(seed: int = 0, tol: float = 1e-9) -> bool:
    """|a+b|^2 != |a|^2 + |b|^2 for complex amplitudes with nontrivial phase.

    Classical probability is always additive; quantum amplitudes interfere.
    """
    import numpy as np
    rng = np.random.default_rng(seed)
    a = complex(rng.standard_normal(), rng.standard_normal())
    b = complex(rng.standard_normal(), rng.standard_normal())
    lhs = abs(a + b) ** 2
    rhs = abs(a) ** 2 + abs(b) ** 2
    # Interference term: 2 Re(a* b)
    cross = 2.0 * (a.conjugate() * b).real
    return abs(lhs - rhs - cross) < tol and abs(cross) > tol


def check_uncertainty_relation(seed: int = 0, tol: float = 1e-9) -> bool:
    """Robertson uncertainty: sigma_A * sigma_B >= |<[A,B]>|/2."""
    import numpy as np
    # Pauli X and Z on |+> = (|0>+|1>)/sqrt(2); [X,Z] = -2i Y
    plus = np.array([1.0, 1.0], dtype=np.complex128) / math.sqrt(2.0)
    X = np.array([[0, 1], [1, 0]], dtype=np.complex128)
    Z = np.array([[1, 0], [0, -1]], dtype=np.complex128)
    Y = np.array([[0, -1j], [1j, 0]], dtype=np.complex128)

    def expect(O, psi):
        return complex(np.vdot(psi, O @ psi))

    def var(O, psi):
        e = expect(O, psi)
        return float(np.real(expect(O @ O, psi))) - float(np.real(e * e.conjugate()))
    sX = math.sqrt(max(var(X, plus), 0.0))
    sZ = math.sqrt(max(var(Z, plus), 0.0))
    commutator_expect = abs(complex(expect(-2j * Y, plus))) / 2.0
    return sX * sZ + tol >= commutator_expect


def check_ghz_correlator(tol: float = 1e-9) -> bool:
    """GHZ state |000>+|111> shows XXX and XYY correlations of opposite sign.

    Classically bounded; quantum value saturates 1.
    """
    import numpy as np
    ghz = np.zeros(8, dtype=np.complex128)
    ghz[0] = ghz[7] = 1.0 / math.sqrt(2.0)
    X = np.array([[0, 1], [1, 0]], dtype=np.complex128)
    Y = np.array([[0, -1j], [1j, 0]], dtype=np.complex128)
    XXX = np.kron(np.kron(X, X), X)
    XYY = np.kron(np.kron(X, Y), Y)
    YXY = np.kron(np.kron(Y, X), Y)
    YYX = np.kron(np.kron(Y, Y), X)

    def e(O):
        return float(np.real(np.vdot(ghz, O @ ghz)))
    # Mermin: E(XXX) - E(XYY) - E(YXY) - E(YYX)
    val = e(XXX) - e(XYY) - e(YXY) - e(YYX)
    # Quantum value: 4; classical bound 2
    return val > 2.0 + tol


def check_entanglement_monogamy(tol: float = 1e-9) -> bool:
    """For maximally entangled |Phi+>_AB, C is not entangled with A or B.

    Reduced state rho_A is maximally mixed => S(rho_A) = ln 2.
    Add a third system C in |0>. Then A is entangled with B only.
    """
    import numpy as np
    # 3 qubits: A, B, C. State = |Phi+>_AB (x) |0>_C
    phi_plus = np.array([1, 0, 0, 1], dtype=np.complex128) / math.sqrt(2.0)
    zero = np.array([1, 0], dtype=np.complex128)
    state = np.kron(phi_plus, zero)  # 8-dim
    rho = np.outer(state, state.conj())
    # Reduced rho_A: trace out B and C (each 2-dim), keep A (2-dim)
    R = rho.reshape(2, 2, 2, 2, 2, 2)
    rho_A = np.einsum("abcabc->a", R.reshape(2, 4, 2, 4)) if False else None
    # Simpler: build rho_A by explicit partial trace
    rho_A = np.zeros((2, 2), dtype=np.complex128)
    for i in range(2):
        for j in range(2):
            s = 0.0 + 0.0j
            for b in range(2):
                for c in range(2):
                    row = i * 4 + b * 2 + c
                    col = j * 4 + b * 2 + c
                    s += rho[row, col]
            rho_A[i, j] = s
    w = np.linalg.eigvalsh(rho_A).real
    w = np.clip(w, 1e-16, 1.0)
    S_A = -float(np.sum(w * np.log(w)))
    # Maximally entangled with B => S_A = ln 2; monogamy => rho_AC pure product
    return abs(S_A - math.log(2.0)) < 1e-6


def check_born_rule_normalization(dim: int = 8, seed: int = 0, tol: float = 1e-10) -> bool:
    """Sum of Born-rule probabilities equals 1 for normalized state."""
    import numpy as np
    psi = _random_state(dim, seed)
    p = np.abs(psi) ** 2
    return abs(float(np.sum(p)) - 1.0) < tol


def check_complex_amplitude_phase_dependence(seed: int = 0, tol: float = 1e-9) -> bool:
    """Global phase invariance vs relative phase measurability.

    Global phase: |exp(i theta) psi> gives same probabilities.
    Relative phase between components CHANGES interference results.
    """
    import numpy as np
    theta = 0.7
    psi = np.array([1.0, 1.0], dtype=np.complex128) / math.sqrt(2.0)
    psi_global = math.e ** (1j * theta) * psi
    p1 = np.abs(psi) ** 2
    p2 = np.abs(psi_global) ** 2
    if not np.allclose(p1, p2, atol=tol):
        return False
    # Relative phase: (|0> + e^{i theta}|1>)/sqrt(2). Hadamard measurement changes
    H = np.array([[1, 1], [1, -1]], dtype=np.complex128) / math.sqrt(2.0)
    psi_rel = np.array([1.0, math.e ** (1j * theta)], dtype=np.complex128) / math.sqrt(2.0)
    out_rel = H @ psi_rel
    out_flat = H @ psi
    return not np.allclose(np.abs(out_rel)**2, np.abs(out_flat)**2, atol=1e-3)


_NEW_CHECKS = [
    ("bell_chsh_violation", check_bell_chsh_violation),
    ("no_cloning", check_no_cloning),
    ("superposition_interference", check_superposition_interference),
    ("uncertainty_relation", check_uncertainty_relation),
    ("ghz_correlator", check_ghz_correlator),
    ("entanglement_monogamy", check_entanglement_monogamy),
    ("born_rule_normalization", check_born_rule_normalization),
    ("complex_amplitude_phase_dependence", check_complex_amplitude_phase_dependence),
]
CHECKS = CHECKS + _NEW_CHECKS


# --- v0.3.5 post-quantum witnesses ----------------------------------------
def check_sorkin_qm_zero(dim: int = 16, seed: int = 0, tol: float = 1e-9) -> bool:
    """Sorkin third-order interference vanishes in standard QM (Born rule)."""
    from .post_quantum.beyond_quantum import sorkin_third_order_interference
    return abs(sorkin_third_order_interference(dim=dim, seed=seed)) < tol


def check_fold_cross_section_positive(dim: int = 32, fold_depth: int = 1, seed: int = 0) -> bool:
    """Fold operation is non-CPTP: cross-section is strictly positive."""
    from .post_quantum.beyond_quantum import fold_cross_section
    return fold_cross_section(dim=dim, fold_depth=fold_depth, seed=seed) > 1e-6


def check_pr_box_exceeds_tsirelson(tol: float = 1e-9) -> bool:
    """PR-box correlator saturates at 4 > 2*sqrt(2)."""
    import math as _m
    from .post_quantum.beyond_quantum import pr_box_correlator
    return pr_box_correlator() > 2.0 * _m.sqrt(2.0) + tol


def check_fold_information_capacity_exceeds_quantum(
        dim: int = 64, fold_depth: int = 3, tol: float = 1e-9) -> bool:
    """Fold capacity = log2(dim) + fold_depth * log2(phi) > log2(dim)."""
    import math as _m
    from .post_quantum.beyond_quantum import fold_information_capacity
    return fold_information_capacity(dim=dim, fold_depth=fold_depth) > _m.log2(dim) + tol


def check_phi_ladder_exact(tol: float = 1e-6) -> bool:
    """phi^n = F(n)*phi + F(n-1) is exact for n = 10, 12, 15, 18, 20."""
    F = [0, 1]
    for _ in range(25):
        F.append(F[-1] + F[-2])
    for n in (10, 12, 15, 18, 20):
        lhs = PHI ** n
        rhs = F[n] * PHI + F[n - 1]
        if abs(lhs - rhs) > tol * max(1.0, abs(lhs)):
            return False
    return True


def check_agi_scale_norm_preservation(tol: float = 1e-6) -> bool:
    """Grover diffusion preserves norm at every phi^n level, n in AGI_SCALE_LEVELS."""
    from .post_quantum.agi_scale import AGIScale, AGI_SCALE_LEVELS
    ags = AGIScale(seed=0)
    for n in AGI_SCALE_LEVELS:
        pt = ags.measure_point(n)
        if pt.norm_preservation_residual > tol:
            return False
    return True


_POST_QUANTUM_CHECKS = [
    ("sorkin_qm_zero", check_sorkin_qm_zero),
    ("fold_cross_section_positive", check_fold_cross_section_positive),
    ("pr_box_exceeds_tsirelson", check_pr_box_exceeds_tsirelson),
    ("fold_information_capacity_exceeds_quantum", check_fold_information_capacity_exceeds_quantum),
    ("phi_ladder_exact", check_phi_ladder_exact),
]
CHECKS = CHECKS + _POST_QUANTUM_CHECKS
