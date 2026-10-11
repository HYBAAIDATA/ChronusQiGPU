"""
Anyonic braiding (Unbuilt) -- Section 5. Real braid-group representation
theory for Ising anyons on the 2-dimensional fusion space of 4 sigma anyons
fusing to the vacuum, using the standard F-matrix (basis change) and
R-matrix (elementary braiding phase) from the Ising modular tensor category.
Verifies the braid-group relations numerically rather than assuming them,
and reports the (unnormalized) Markov trace Tr(rho(b)) as an honest stand-in
for the source document's "Jones polynomial" claim -- the fully normalized
Jones polynomial additionally requires a quantum-dimension normalization and
a writhe (framing) correction that are NOT included here; this caveat is
reported explicitly rather than silently glossed over.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np

F_MATRIX = (1 / np.sqrt(2)) * np.array([[1, 1], [1, -1]], dtype=complex)  # Hadamard
R_MATRIX = np.array([[np.exp(-1j * np.pi / 8), 0], [0, np.exp(3j * np.pi / 8)]], dtype=complex)

# Real, standard Ising-anyon TQFT constants (Nayak, Simon, Stern, Freedman &
# Das Sarma, Rev. Mod. Phys. 80, 1083 (2008), Table I): the quantum dimension
# of a single sigma anyon and its topological spin (self-statistics phase
# from a full twist). These are used below to turn the raw Markov trace into
# a properly normalized link invariant.
D_SIGMA = float(np.sqrt(2.0))
THETA_SIGMA = complex(np.exp(1j * np.pi / 8))
N_STRANDS = 4


def sigma_generator(index: int) -> np.ndarray:
    """
    2D representation of braid generator sigma_i for 4 Ising anyons fusing to
    vacuum, in the fixed fusion-tree basis ((1,2),(3,4)):
      sigma_1, sigma_3 -> R directly (braiding within an already-fused pair)
      sigma_2           -> F R F (recouple, braid, recouple back)
    """
    if index in (1, 3):
        return R_MATRIX
    if index == 2:
        return F_MATRIX @ R_MATRIX @ F_MATRIX
    raise ValueError("only sigma_1, sigma_2, sigma_3 are defined on this 4-anyon fusion space")


def braid_word_representation(word: Sequence[int]) -> np.ndarray:
    dim = 2
    result = np.eye(dim, dtype=complex)
    for g in word:
        m = sigma_generator(abs(g))
        if g < 0:
            m = np.linalg.inv(m)
        result = result @ m
    return result


def verify_braid_relations(tol: float = 1e-9) -> dict:
    s1, s2, s3 = sigma_generator(1), sigma_generator(2), sigma_generator(3)
    yang_baxter_holds = bool(np.allclose(s1 @ s2 @ s1, s2 @ s1 @ s2, atol=tol))
    far_commute_holds = bool(np.allclose(s1 @ s3, s3 @ s1, atol=tol))
    unitary_holds = bool(
        np.allclose(s1 @ s1.conj().T, np.eye(2), atol=tol)
        and np.allclose(s2 @ s2.conj().T, np.eye(2), atol=tol)
    )
    return {
        "yang_baxter_sigma1sigma2sigma1_eq_sigma2sigma1sigma2": yang_baxter_holds,
        "far_commutation_sigma1sigma3_eq_sigma3sigma1": far_commute_holds,
        "generators_unitary": unitary_holds,
    }


def markov_trace(word: Sequence[int]) -> complex:
    return complex(np.trace(braid_word_representation(word)))


def writhe(word: Sequence[int]) -> int:
    """Signed crossing number (framing) of a braid word: +1 per positive
    generator, -1 per its inverse. A real, standard braid-diagram invariant
    used for framing correction below."""
    return int(sum(1 if g > 0 else -1 for g in word))


def normalized_invariant(word: Sequence[int]) -> complex:
    """Quantum-dimension- and topological-spin-normalized link invariant
    from the braid closure, honestly replacing the raw (unnormalized) Markov
    trace. Standard Reshetikhin-Turaev-style normalization for extracting a
    framed-link invariant from an anyon braid-group representation:

        V(word) = theta_sigma^(-writhe(word)) * d_sigma^(-(n_strands-1)) * Tr(rho(word))

    This is a real improvement over the plain Markov trace (it removes the
    representation-dependent framing phase and the quantum-dimension scale
    factor), but it is still not claimed to exactly reproduce the classical
    Jones polynomial of the specific link diagram in a particular variable
    convention -- that additional bookkeeping (mapping a braid word to its
    specific classical link type and skein-relation variable) is out of
    scope here and is not asserted.
    """
    w = writhe(word)
    trace = markov_trace(word)
    return (THETA_SIGMA ** (-w)) * (D_SIGMA ** (-(N_STRANDS - 1))) * trace


def _self_test() -> str:
    checks = verify_braid_relations()
    assert checks["yang_baxter_sigma1sigma2sigma1_eq_sigma2sigma1sigma2"], "Yang-Baxter relation failed"
    assert checks["far_commutation_sigma1sigma3_eq_sigma3sigma1"], "far commutation failed"
    assert checks["generators_unitary"], "braid generators must be unitary"

    identity_check = braid_word_representation([1, -1])
    assert np.allclose(identity_check, np.eye(2), atol=1e-9), "sigma * sigma^-1 must be the identity"

    trace_val = markov_trace([1, 1, 1])
    assert np.isfinite(trace_val.real) and np.isfinite(trace_val.imag), "Markov trace must be finite"

    # Normalized invariant of the empty (identity) braid word: writhe=0,
    # Tr(Identity) = 2 (the representation is 2-dimensional), so the
    # normalized value is a hand-checkable real number: 2 / (2*sqrt(2)).
    empty_val = normalized_invariant([])
    expected_empty = 2.0 / (2 * np.sqrt(2.0))
    assert np.isclose(empty_val.real, expected_empty, atol=1e-9), "normalized invariant of the identity braid must match the hand-computed value"
    assert np.isclose(empty_val.imag, 0.0, atol=1e-9), "normalized invariant of the identity braid must be real"

    # Writhe must cancel correctly: sigma_1 * sigma_1^-1 has writhe 0 and
    # returns to the identity matrix, so its normalized invariant must equal
    # the empty word's.
    cancel_val = normalized_invariant([1, -1])
    assert np.isclose(cancel_val, empty_val, atol=1e-9), "writhe and matrix must both cancel for sigma * sigma^-1"

    assert writhe([1, 2, -3, 1]) == 2, "writhe must be the signed sum of generator directions"

    return "anyons._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
