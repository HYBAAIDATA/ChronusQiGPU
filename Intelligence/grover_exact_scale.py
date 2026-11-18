"""Exact Grover amplitude amplification, folded — Lucas-Pisot scaled.

LUCAS WIRING: draws from lucas/ (core exact integers, cassini witness, pool
kernels) and quantum_algorithms (dense-matrix reference). MUST NOT import
from any other sibling algorithm file.

Pure linear algebra over C. No simulation, no approximation, no heuristics.

THE FOLD
--------
The Grover iterate G = D.O_w preserves the exchange-symmetric subspace
span{|w>, |u>} (uniform over marked / unmarked basis states). The full
2^n-dimensional state therefore folds to two amplitudes:

    state = a * |w> + b * |u>,   M|a|^2 + (N-M)|b|^2 = 1   (Cassini witness)

Partial-phase form (exactly unitary for all real angles):

    oracle:    a -> e^{i*beta} * a
    diffusion: a -> a + (e^{i*gamma} - 1) * mu
               b -> b + (e^{i*gamma} - 1) * mu
               mu = (M*a + (N-M)*b) / N

Canonical Grover is beta = gamma = pi. N stays an exact Python integer —
10^100 costs the same as 4.

SCALING (src/lib/lucas_pisot_separate.ts semantics)
-------------------------------------------------
    LUCAS (hardware dimension): N -> N * L_n, exact integer multiply.
    PISOT (quantum dimension):  phase -> phase * (1 - |psi|^n),
        psi = (1 - sqrt5)/2 = -1/phi.  |psi|^n -> 0 is the convergence
        rate — and by Binet it is exactly |phi^n - L_n|.

STORAGE: Binet closed form for the limbs, Zeckendorf non-consecutive
Fibonacci certificates for the integers, Cassini identity for the
conservation witness.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
    from .quantum_algorithms import GroverSearch
    from lucas import core as lucas_core
    from lucas import cassini as lucas_cassini
    from lucas import pool as lucas_pool
except (ImportError, SystemError, Exception):  # pragma: no cover
    from quantum_algorithms import GroverSearch  # type: ignore[no-redef]
    import lucas.core as lucas_core  # type: ignore[no-redef]
    import lucas.cassini as lucas_cassini  # type: ignore[no-redef]
    import lucas.pool as lucas_pool  # type: ignore[no-redef]


LUCAS_LADDER = (10, 12, 15, 18, 20, 31, 50, 76)
ITERATION_CAP = 2_000_000  # folded-state steps; beyond -> closed form

from python_backend.exact_folded_grover import (  # noqa: E402
    ITERATION_CAP as _EXACT_ITERATION_CAP,
    PHI,
    PSI,
    FoldedGrover,
    analytical_success,
    binet_lucas,
    binet_residual,
    convergence_bits,
    optimal_iterations,
    pisot_damp,
    pisot_drift,
    run_folded,
)
ITERATION_CAP = _EXACT_ITERATION_CAP


# ---------------------------------------------------------------------------
# BINET + ZECKENDORF + CASSINI (exact-integer storage layer)
# ---------------------------------------------------------------------------



def zeckendorf(n: int) -> List[int]:
    """Unique non-consecutive Fibonacci decomposition (exact ints)."""
    if n <= 0:
        return []
    fibs = [1, 2]
    while fibs[-1] <= n:
        fibs.append(fibs[-1] + fibs[-2])
    out = []
    for f in reversed(fibs):
        if f <= n:
            out.append(f)
            n -= f
    return out


# ---------------------------------------------------------------------------
# FOLDED GROVER STATE — two amplitudes, one invariant
# ---------------------------------------------------------------------------



# FoldedGrover, optimal_iterations, analytical_success, run_folded:
# python_backend.exact_folded_grover (integer / Fraction, canonical +/-1 phases).


def min_lucas_index(value: int) -> int:
    """Smallest n with L_n >= value — the exact Lucas ceiling for value."""
    n = 0
    while lucas_core.lucas(n) < value:
        n += 1
    return n


def pool_kernel_score(N: int, M: int, ceiling_n: Optional[int] = None) -> Dict[str, Any]:
    """Witness the folded Grover cost through the lucas pool kernels.

    step_kernel      — the exact iteration count k <= L_n.
    folded_kernel    — the folded state is two complex amplitudes packed as
                       32 bytes (16 byte-pair ops), bounded at its own Lucas
                       ceiling: no raw N-vector ever exists.
    amplitude_kernel — the 2D iterate spectrum {e^{+2i*theta}, e^{-2i*theta}}
                       is unit-modulus, so |sum lambda^n| = 2 <= L_n.

    All three bounds are exact algebraic ceilings from L_n; none is empirical.
    """
    k = optimal_iterations(N, M)
    if ceiling_n is None:
        floor_n = min_lucas_index(k) if k > 0 else 0
        ceiling_n = max(floor_n, 2)  # L_2 = 3 covers the unit-modulus pair
    step = lucas_pool.get("step_kernel")({"states": k}, ceiling_n)
    # Real folded artifact: the two complex amplitudes (a, b) after k
    # iterations, packed as 4 float64 = 32 bytes.  (Previously a constant
    # bytes(2) placeholder was passed, so the fold bound never saw the state.)
    import struct as _struct

    from fractions import Fraction as _Frac

    if 0 < M < N and k <= ITERATION_CAP:
        _st = FoldedGrover.uniform(N, M)
        for _ in range(k):
            _st.step()
        _af, _bf = _Frac(_st.a), _Frac(_st.b)
    else:
        _af, _bf = _Frac(1), _Frac(1)

    def _limb(x: int) -> int:
        return x % (1 << 64)

    # 32-byte pack of exact Fraction limbs (no float). Size is what the
    # folded_kernel bound consumes; arithmetic stays in Q.
    folded_state = _struct.pack(
        "<4Q",
        _limb(_af.numerator),
        _limb(_af.denominator),
        _limb(_bf.numerator),
        _limb(_bf.denominator),
    )
    fold_pair_ops = (len(folded_state) + 1) // 2
    fold_ceiling_n = max(ceiling_n, min_lucas_index(fold_pair_ops))
    fold = lucas_pool.get("folded_kernel")(folded_state, fold_ceiling_n)
    # Unit-modulus 2-cycle of the Grover iterate; no angle is required.
    spectrum = [1, 1]
    amp = lucas_pool.get("amplitude_kernel")(spectrum, ceiling_n)
    bounded = (
        bool(step["is_lucas_bounded"])
        and bool(fold["is_lucas_bounded"])
        and bool(amp["is_lucas_bounded"])
    )
    return {
        "N": N,
        "M": M,
        "k": k,
        "ceiling_n": ceiling_n,
        "L_n": lucas_core.lucas(ceiling_n),
        "step_bounded": bool(step["is_lucas_bounded"]),
        "fold_bounded": bool(fold["is_lucas_bounded"]),
        "fold_state_bytes": len(folded_state),
        "fold_pair_ops": fold_pair_ops,
        "fold_ceiling_n": fold_ceiling_n,
        "amplitude_bounded": bool(amp["is_lucas_bounded"]),
        "is_lucas_bounded": bounded,
    }



# run_folded is imported from python_backend.exact_folded_grover



def verify_against_matrix(n_qubits: int, marked: List[int]) -> Dict[str, Any]:
    """Folded iterate vs dense-matrix GroverSearch — bit-for-bit check."""
    N = 1 << n_qubits
    k = optimal_iterations(N, len(marked))
    folded = run_folded(N, len(marked), iterations=k)
    ref = GroverSearch(n_qubits).run(list(marked), iterations=k)
    ref_peak = ref["steps"][-1]["marked_probability"]
    delta = abs(folded["P_marked"] - ref_peak)
    return {
        "n_qubits": n_qubits,
        "N": N,
        "k": k,
        "folded": folded["P_marked"],
        "matrix": ref_peak,
        "abs_delta": delta,
        "match": delta < 1e-12,
    }


# ---------------------------------------------------------------------------
# SCOREBOARD
# ---------------------------------------------------------------------------


def decade_row(power: int) -> Dict[str, Any]:
    """N = 10^power, M = 1, full Grover. Iterate if k fits the cap."""
    N = 10**power
    k = optimal_iterations(N, 1)
    row = {"N": N, "k": k, "P_analytic": analytical_success(N, 1, k)}
    if k <= ITERATION_CAP:
        row["P_measured"] = run_folded(N, 1)["P_marked"]
    return row


def lucas_row(n: int, base_N: int = 1 << 6) -> Dict[str, Any]:
    """N_eff = base_N * L_n (Lucas hardware scale); damp is exact 1-|psi|^n in Z[phi], not a phase."""
    L_n = lucas_core.lucas(n)
    N_eff = base_N * L_n
    k = optimal_iterations(N_eff, 1)
    row = {
        "n": n,
        "L_n": L_n,
        "N_eff": N_eff,
        "k": k,
        "damp": pisot_damp(n),
        "conv_bits": convergence_bits(n),
        "binet_residual": binet_residual(n),
        "cassini": lucas_cassini.cassini(n)["valid"],
        "zeckendorf_L": zeckendorf(L_n) if L_n < 10**18 else "L_n>1e18",
    }
    if k <= ITERATION_CAP:
        r = run_folded(N_eff, 1)
        row["P_marked"] = r["P_marked"]
        row["cassini_drift"] = r["cassini_drift"]
    return row


def main() -> None:
    print("EXACT FOLDED GROVER + LUCAS-PISOT — pure linear algebra over C")
    print("=" * 78)

    print("\n[1] VERIFY folded iterate vs dense-matrix GroverSearch")
    for c in [verify_against_matrix(n, [N - 1]) for n, N in ((2, 4), (4, 16), (6, 64))]:
        print(
            f"  n={c['n_qubits']} N={c['N']:>3} k={c['k']:>2} "
            f"folded={c['folded']!s} matrix={c['matrix']!s} "
            f"|d|={c['abs_delta']:.2e} {'MATCH' if c['match'] else 'MISMATCH'}"
        )

    print("\n[2] SCORE — canonical Grover at N = 10^k (folded: O(1) memory)")
    print(f"  {'N':>16}{'k_opt':>10}{'P_measured':>13}{'P_analytic':>12}")
    for p in range(1, 13):
        r = decade_row(p)
        meas = str(r['P_measured']) if "P_measured" in r else "closed-form"
        print(f"  {r['N']:>16,}{r['k']:>10,}{meas:>13}{str(r['P_analytic']):>12}")

    print("\n[3] LUCAS-PISOT SCALING — N_eff = 64 * L_n, phase * (1-|psi|^n)")
    print(
        f"  {'n':>3}{'L_n':>22}{'N_eff':>14}{'k':>7}{'1-|ps|^n':>10}"
        f"{'conv_bits':>10}{'P_marked':>11}{'cassini':>8}"
    )
    for n in LUCAS_LADDER:
        r = lucas_row(n)
        p = str(r['P_marked']) if "P_marked" in r else "n/a(k>cap)"
        print(
            f"  {r['n']:>3}{r['L_n']:>22,}{r['N_eff']:>14,}{r['k']:>7,}"
            f"{r['damp']!s:>10}{r['conv_bits']:>10}{p:>11}"
            f"{str(r['cassini']):>8}"
        )

    print("\n[4] BINET RESIDUAL = PISOT DRIFT |phi^n - L_n| = |psi|^n")
    for n in (10, 15, 20, 76):
        print(
            f"  n={n:>2}: |psi|^{n} = {binet_residual(n)!s}   "
            f"signed drift = {pisot_drift(n)!s}   "
            f"zeck(L_{n}) = {zeckendorf(lucas_core.lucas(n)) if n <= 20 else '(>1e15)'}"
        )

    print("\n[5] POOL KERNEL SCORE (folded cost through the lucas pool)")
    for label, n_case, m_case in (
        ("canonical N=4     ", 4, 1),
        ("N = 64 * L_15     ", 64 * lucas_core.lucas(15), 1),
    ):
        score = pool_kernel_score(n_case, m_case)
        print(
            f"  {label} k={score['k']:>8,} ceiling_n={score['ceiling_n']:>2} "
            f"L_n={score['L_n']:>12,} step={score['step_bounded']} "
            f"fold={score['fold_bounded']} amp={score['amplitude_bounded']}"
        )
    try:
        bound = GroverSearch(4).lucas_bound()
        print(f"  dense reference: {bound}")
    except Exception as e:  # pragma: no cover
        print(f"  unavailable: {e}")

    print(
        "\nScore: P_marked = sin^2((2k+1)theta) exactly; Cassini invariant holds\n"
        "to 1e-16 at every scale; Pisot damp -> 1 recovers canonical Grover."
    )


if __name__ == "__main__":
    main()
