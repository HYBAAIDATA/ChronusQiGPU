"""Exact folded Grover + Lucas-Pisot scaling — verification gates.

Pure linear algebra over C: the folded 2D state must match the dense-matrix
reference bit-for-bit, the Cassini conservation witness must hold, Binet's
residual must equal the Pisot drift, Zeckendorf(L_n) must be the Fibonacci
pair certificate, and the lucas pool kernels must bound the folded cost.
"""

import math
import os
import struct
import sys

import pytest

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS_DIR)
for _p in (_ROOT,):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from Intelligence import grover_exact_scale as ges  # noqa: E402
from lucas import cassini as lucas_cassini  # noqa: E402
from lucas import core as lucas_core  # noqa: E402


def test_fold_matches_dense_matrix_bit_for_bit():
    for n_qubits, marked in ((2, [3]), (4, [15])):
        c = ges.verify_against_matrix(n_qubits, marked)
        assert c["match"], f"folded {c['folded']} vs matrix {c['matrix']}"
        assert c["abs_delta"] < 1e-12


def test_cassini_witness_conserved_over_full_iteration():
    N, M = 1024, 1
    r = ges.run_folded(N, M)
    assert r["cassini_drift"] < 1e-12
    # analytic closed form and measured folded value agree
    assert abs(r["P_marked"] - r["P_analytic_full"]) < 1e-9


def test_pisot_damp_one_recovers_canonical_grover():
    N, M = 4096, 1
    k = ges.optimal_iterations(N, M)
    r = ges.run_folded(N, M, iterations=k, damp=1.0)
    assert abs(r["P_marked"] - ges.analytical_success(N, M, k)) < 1e-9


def test_pisot_phases_are_refused_by_the_exact_fold():
    """1-|psi|^n is exact in Q(sqrt(5)) but is not a +/-1 Grover phase."""
    N, k = 4096, ges.optimal_iterations(4096, 1)
    # Canonical run still works (damp=1).
    r = ges.run_folded(N, 1, iterations=k, damp=1.0)
    assert r["P_marked"] == r["P_analytic_full"]
    assert r["cassini_drift"] == 0
    with pytest.raises(ValueError, match="not used"):
        ges.run_folded(N, 1, iterations=k, damp=ges.pisot_damp(6))


def test_binet_residual_equals_pisot_drift():
    """|phi^n - L_n| = |psi|^n exactly; float64 evaluates phi^n to ~ULP(n),
    so the verification tolerance scales with phi^n."""
    for n in range(10, 26):
        tol = ges.PHI**n * 1e-12
        assert abs(ges.binet_residual(n) - abs(ges.PSI) ** n) < tol


def test_cassini_lucas_identity_exact():
    assert lucas_cassini.verify_range(max_n=30)


def test_zeckendorf_of_lucas_is_fibonacci_pair():
    """L_n = F_{n-1} + F_{n+1}, and that pair IS the Zeckendorf certificate.

    Holds for every n >= 3 (indices n-1, n+1 skip F_n: non-consecutive).
    L_0=2, L_1=1, L_2=3 are themselves Fibonacci (F ∩ L = {1,2,3}), so the
    greedy certificate collapses to the single Fibonacci number — checked
    explicitly for the L_2 = 3 = F_4 case.
    """
    assert ges.zeckendorf(lucas_core.lucas(2)) == [3]
    for n in range(3, 21):
        L_n = lucas_core.lucas(n)
        expected = [lucas_core.fibonacci(n + 1), lucas_core.fibonacci(n - 1)]
        assert ges.zeckendorf(L_n) == expected


def test_optimal_iterations_scales_as_pi4_sqrt():
    # Stepping the exact recurrence is O(k) with rationals of growing height,
    # so this stays at sizes where k is a few thousand at most.
    for power in (2, 4, 6):
        N, M = 10**power, 1
        k = ges.optimal_iterations(N, M)
        ratio = k / math.sqrt(N)
        assert 0.5 < ratio < 1.0  # pi/4 ~ 0.785, the exact peak sits near that


def test_pool_kernel_score_bounded_canonical():
    score = ges.pool_kernel_score(4, 1)
    assert score["is_lucas_bounded"] is True
    assert score["step_bounded"] and score["fold_bounded"]
    assert score["amplitude_bounded"]


def test_pool_kernel_score_bounded_at_lucas_scale():
    N_eff = 64 * lucas_core.lucas(15)  # 64 * 1364 = 87296
    score = ges.pool_kernel_score(N_eff, 1)
    assert score["is_lucas_bounded"] is True
    assert score["k"] <= score["L_n"]


def test_folded_state_is_two_amplitudes_not_n():
    """The fold: state memory is O(1) regardless of N (10**100 included)."""
    N = 10**100
    state = ges.FoldedGrover.uniform(N, 1)
    witness = state.cassini_witness()
    assert witness == 1
    from fractions import Fraction
    assert isinstance(state.a, (int, Fraction)) and state.a == 1
    k = ges.optimal_iterations(N, 1)
    # Too many steps to materialise; the sentinel marks that case.
    from python_backend.exact_folded_grover import ITERATION_CAP
    assert k == ITERATION_CAP + 1


def test_sha256_compress_matches_hashlib_full_digest():
    from mining.bitcoin_hasher import sha256_compress, sha256_midstate

    import hashlib

    block = bytes(range(64))
    # finalize the midstate with SHA-256 length padding for a 64-byte message
    state = struct.unpack(">8I", sha256_midstate(block))
    pad = struct.pack(">16I", 0x80000000, *([0] * 14), 512)
    digest = struct.pack(">8I", *sha256_compress(state, pad))
    assert digest == hashlib.sha256(block).digest()
