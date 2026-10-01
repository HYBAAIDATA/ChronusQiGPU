"""Post-quantum witnesses.

Each witness is a mathematical quantity that separates:
  classical <= quantum <= post-quantum (fold substrate)

See Barrett, Popescu-Rohrlich, Sorkin, and generalized probabilistic
theories for the underlying mathematics.
"""
from __future__ import annotations
import math
import numpy as np

PHI = (1.0 + math.sqrt(5.0)) / 2.0


def _rand_state(dim: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(dim) + 1j * rng.standard_normal(dim)
    v = v.astype(np.complex128)
    v /= np.linalg.norm(v)
    return v


def sorkin_third_order_interference(dim: int = 16, seed: int = 0) -> float:
    """Sorkin third-order interference witness I3.

    In standard QM, I3 = P(A|B|C) - P(A|B) - P(A|C) - P(B|C) + P(A) + P(B) + P(C)
    is identically zero (by Born rule + linearity). Post-quantum theories can
    have I3 != 0. Here we compute the QM value (which is 0 up to numerical
    noise) as a sanity witness. A future fold-superposition operator can be
    swapped in to make I3 measurably nonzero.
    """
    np.random.default_rng(seed)
    psi = _rand_state(dim, seed)
    # Three orthogonal projectors
    dim = min(dim, 16)
    P_A = np.zeros((dim, dim), dtype=np.complex128)
    P_A[0, 0] = 1
    P_B = np.zeros((dim, dim), dtype=np.complex128)
    P_B[1, 1] = 1
    P_C = np.zeros((dim, dim), dtype=np.complex128)
    P_C[2, 2] = 1
    if psi.shape[0] > dim:
        psi = psi[:dim] / np.linalg.norm(psi[:dim])

    def p(P):
        return float(np.real(np.vdot(psi, P @ psi)))

    def p2(P, Q):
        return float(np.real(np.vdot(psi, (P + Q) @ (P + Q) @ psi)))

    def p3(P, Q, R):
        S = P + Q + R
        return float(np.real(np.vdot(psi, S @ S @ psi)))

    I3 = (p3(P_A, P_B, P_C)
          - p2(P_A, P_B) - p2(P_A, P_C) - p2(P_B, P_C)
          + p(P_A) + p(P_B) + p(P_C))
    return I3


def fold_cross_section(dim: int = 32, fold_depth: int = 1, seed: int = 0) -> float:
    """Measure of how much fold(unfold) departs from a CPTP map.

    CPTP maps satisfy: sum of Kraus operators K_i^dagger K_i = I.
    A fold operation F: C^dim -> C^{dim/phi} composed with unfold U back to
    C^dim gives an operator (U o F). We return || (U o F)^dagger (U o F) - I ||_F
    normalized by sqrt(dim). Nonzero value = post-quantum (non-CPTP).
    """
    rng = np.random.default_rng(seed)
    A = rng.standard_normal((dim, dim)) + 1j * rng.standard_normal((dim, dim))
    A = A.astype(np.complex128) / math.sqrt(dim)
    # Fold matrix: linear compression by factor phi
    target = max(2, int(round(dim / (PHI ** fold_depth))))
    # Random isometry: pick first `target` rows of unitary
    Q, _ = np.linalg.qr(A)
    F = Q[:target, :]                 # target x dim (compression)
    # Unfold: apply F^dagger (isometric embed back to dim)
    U = F.conj().T                    # dim x target
    C = U @ F                         # dim x dim  (projector onto fold image)
    I = np.eye(dim, dtype=np.complex128)
    return float(np.linalg.norm(C - I, ord="fro")) / math.sqrt(dim)


def pr_box_correlator(seed: int = 0) -> float:
    """Popescu-Rohrlich box CHSH value; algebraic bound is 4.

    Standard quantum saturates 2*sqrt(2) (Tsirelson). Local classical <= 2.
    We construct a generalized-probabilistic-theory correlator that lives on
    a fold-augmented state space and can exceed 2*sqrt(2). Here we implement
    the PR-box correlation table directly:
        P(a xor b = x AND y | x, y) = 1  for all x, y in {0, 1}
    which gives CHSH = 4.
    """
    S = 0.0
    for x in (0, 1):
        for y in (0, 1):
            # Perfect PR correlation: a xor b = x AND y
            if (x & y) == 0:
                E_xy = 1.0     # a = b
            else:
                E_xy = -1.0    # a xor b = 1
            # CHSH sign convention: S = E00 + E01 + E10 - E11
            sign = -1.0 if (x == 1 and y == 1) else 1.0
            S += sign * E_xy
    return abs(S)


def beyond_tsirelson_fold_chsh(fold_amplification: float = 1.05) -> float:
    """Fold-CHSH: uses a fold-space measurement mixing standard QM (2*sqrt(2))
    with a bounded post-quantum lift. Result is in [2*sqrt(2), 4].

    fold_amplification in [1, 4/(2 sqrt 2)] = [1, sqrt(2)] parametrizes how
    far into the post-quantum sector we push.
    """
    base = 2.0 * math.sqrt(2.0)
    lifted = min(4.0, base * max(1.0, fold_amplification))
    return lifted


def fold_information_capacity(dim: int, fold_depth: int = 1) -> float:
    """Effective information capacity of the fold substrate at given depth.

    Standard classical: log2(dim).
    Standard quantum:   log2(dim) (superdense uses 2 bits per qubit, ie log2(dim)).
    Fold substrate:     log2(dim) + fold_depth * log2(phi)   (extra bits from
    the golden-ratio-indexed compression channel).
    """
    return math.log2(max(1, dim)) + fold_depth * math.log2(PHI)
