"""Solovay-Kitaev boundary scope — Clifford+T approximation of U(t).

This module quantifies the exact/continuous duality boundary that
``toe.expansion`` attests as ``theorem_proven: False``. On one side sits
``kellogg.exact_tensor``: state vectors over F4 = Q(sqrt(2)) + iQ(sqrt(2))
= Q(zeta_8), where every Clifford+T gate is exact. On the other sits
``toe.bridge``: the continuous propagator U(t) = exp(-iHt/hbar) in
IEEE-754. The gap between them is the Solovay-Kitaev question: how many
Clifford+T gates are needed to approximate a target unitary within a
certified epsilon?

What is implemented here — and what is not:

* ``phase_snap`` — nearest exactly-representable diagonal phase
  (zeta_8^k) to a continuous angle, with certified |theta - k*pi/4|.
* ``synthesize`` — beam search over the declared Clifford+T alphabet
  {H, S, T, Sdg, Tdg} on the *exact* substrate. Dedup is on exact F4
  equality, so reported gate counts are exact word lengths, and epsilon
  is measured mod global phase in the Frobenius norm.
* ``forecast_propagator_report`` — the feasibility data the F2 finding
  calls for: for each of the six forecast times, the epsilon-vs-depth
  frontier for the dim-2 version of the bridge's default Hamiltonian.

Scope boundary (honest): general synthesis of the 32-dimensional bridge
propagator requires a U(32) -> 1- and 2-qubit decomposition (KAK/CSD)
that this substrate does not declare. The single-qubit frontier measured
here is the load-bearing datum: it shows the per-phase resolution limit
of Q(zeta_8) and the empirical gate-count growth needed to beat it.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    from kellogg.exact_tensor import ExactGate, F4, GATES, ONE, ZERO
    from kellogg.quantum_tensor import ComplexMatrix, Observables
except ImportError:  # direct execution fallback
    import os
    import sys

    _PKG_DIR = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.dirname(_PKG_DIR))
    from kellogg.exact_tensor import ExactGate, F4, GATES, ONE, ZERO
    from kellogg.quantum_tensor import ComplexMatrix, Observables

# Generating alphabet: the universal Clifford+T set. I/X/Y/Z are omitted —
# X and Z are reachable as Clifford words (X ~ HSS H, Z = SS) and identity
# adds no reach — so they only cost branching factor in the search.
DEFAULT_ALPHABET: Tuple[str, ...] = ("H", "S", "T", "Sdg", "Tdg")

_ZETA8_FLOAT = complex(math.sqrt(0.5), math.sqrt(0.5))


def _gate_mul(g: ExactGate, m: ExactGate) -> ExactGate:
    """Exact 2x2 matrix product g·m over F4."""
    return (
        (
            g[0][0] * m[0][0] + g[0][1] * m[1][0],
            g[0][0] * m[0][1] + g[0][1] * m[1][1],
        ),
        (
            g[1][0] * m[0][0] + g[1][1] * m[1][0],
            g[1][0] * m[0][1] + g[1][1] * m[1][1],
        ),
    )


def _gate_key(m: ExactGate) -> tuple:
    """Exact dedup key: the sixteen Fraction coefficients of the matrix."""
    return tuple(v for row in m for z in row for v in (z.a, z.b, z.c, z.d))


def _f4_complex(z: F4) -> complex:
    return complex(z.real.to_float(), z.imag.to_float())


def _mod_phase_frobenius(m: ExactGate, target: Tuple[Tuple[complex, complex], ...]) -> float:
    """min over global phase phi in {zeta_8^k} of ||phi*m - target||_F.

    Global phase is physically meaningless, so the approximation error is
    the distance to the target's projective orbit — not to one phase lift.
    """
    entries = [_f4_complex(z) for row in m for z in row]
    flat = [target[0][0], target[0][1], target[1][0], target[1][1]]
    best = math.inf
    for k in range(8):
        phase = _ZETA8_FLOAT**k
        err = 0.0
        for w, t in zip(entries, flat):
            err += abs(phase * w - t) ** 2
        best = min(best, err)
    return math.sqrt(best)


def phase_snap(theta: float) -> Dict[str, Any]:
    """Nearest exactly-representable zeta_8 phase to a continuous angle.

    Returns the eighth-turn index k, the exact phase zeta_8^k, and the
    certified angular residual |theta - k*pi/4| (bounded above by pi/8).
    This is the finest phase grid Clifford+T diagonal gates express.
    """
    eighths = theta / (math.pi / 4.0)
    k = int(round(eighths)) % 8
    residual = abs(theta - (round(eighths) * math.pi / 4.0))
    return {
        "eighth_turns": k,
        "phase": "zeta_8^%d" % k,
        "angular_residual": residual,
        "residual_bound": math.pi / 8.0,
    }


def synthesize(
    target: Tuple[Tuple[complex, complex], ...],
    *,
    alphabet: Sequence[str] = DEFAULT_ALPHABET,
    max_depth: int = 12,
    beam_width: int = 512,
) -> List[Dict[str, Any]]:
    """Beam-search Clifford+T synthesis of a 2x2 target unitary.

    Enumerates words over ``alphabet`` as exact F4 matrices, deduplicated
    on exact equality (a repeated matrix can only reappear at greater
    depth, which is dominated). Each depth keeps the ``beam_width``
    closest survivors by mod-phase Frobenius distance to ``target``.

    Returns the epsilon-vs-depth frontier: one record per depth holding
    the best word found at exactly that depth.
    """
    gates = {name: GATES[name] for name in alphabet}
    identity: ExactGate = ((ONE, ZERO), (ZERO, ONE))
    frontier: List[Tuple[ExactGate, Tuple[str, ...]]] = [(identity, ())]
    seen = {_gate_key(identity)}
    records: List[Dict[str, Any]] = []
    for depth in range(max_depth + 1):
        if not frontier:
            break
        best_word: Optional[Tuple[str, ...]] = None
        best_eps = math.inf
        expanded: List[Tuple[ExactGate, Tuple[str, ...]]] = []
        for mat, word in frontier:
            eps = _mod_phase_frobenius(mat, target)
            if eps < best_eps:
                best_eps, best_word = eps, word
            for name, gate in gates.items():
                cand = _gate_mul(gate, mat)
                key = _gate_key(cand)
                if key in seen:
                    continue
                seen.add(key)
                expanded.append((cand, word + (name,)))
        records.append(
            {
                "depth": depth,
                "word": list(best_word or ()),
                "gate_count": len(best_word or ()),
                "epsilon_frobenius": best_eps,
            }
        )
        expanded.sort(key=lambda item: _mod_phase_frobenius(item[0], target))
        frontier = expanded[:beam_width]
    return records


def sk_length_bound(epsilon: float) -> float:
    """Solovay-Kitaev reference gate-count bound O(log^c(1/eps)), c ~= 3.97.

    Dawson-Nielsen constant; the leading constant is implementation-set
    dependent, so this is an order-of-growth curve, not a hard bound.
    """
    if epsilon <= 0.0:
        return math.inf
    return math.log(1.0 / epsilon) ** 3.97


def forecast_propagator_report(
    times: Sequence[float],
    *,
    hbar: float = 1.0,
    mass: float = 1.0,
    omega: float = 0.5,
    max_depth: int = 12,
    beam_width: int = 512,
) -> Dict[str, Any]:
    """Epsilon-vs-gate-count data for the six forecast propagators.

    Synthesizes the dim-2 oscillator propagator U_2(t) = exp(-iH_2 t/hbar)
    — the same Hamiltonian family as the bridge's default (dim 32) — on
    the exact Clifford+T substrate, and reports the best certified
    Frobenius error achievable at each depth. This is the feasibility
    measurement for the Q(zeta_8) <-> continuous U(t) boundary.
    """
    H = Observables.harmonic_oscillator_hamiltonian(2, hbar, mass, omega)
    per_time: List[Dict[str, Any]] = []
    for t in times:
        U = ComplexMatrix.matrix_exp_unitary(H, round(t / hbar, 12))
        target = tuple(
            tuple(complex(U.data[r][c].re, U.data[r][c].im) for c in range(2))
            for r in range(2)
        )
        frontier = synthesize(target, max_depth=max_depth, beam_width=beam_width)
        best = min(frontier, key=lambda r: r["epsilon_frobenius"])
        per_time.append(
            {
                "time": float(t),
                "best_word": best["word"],
                "gate_count": best["gate_count"],
                "epsilon_frobenius": best["epsilon_frobenius"],
                "frontier": frontier,
            }
        )
    return {
        "available": True,
        "synthesis_scope": "single_qubit",
        "hamiltonian": {"dim": 2, "hbar": hbar, "mass": mass, "omega": omega},
        "alphabet": list(DEFAULT_ALPHABET),
        "max_depth": max_depth,
        "beam_width": beam_width,
        "propagators": per_time,
        "scope_boundary": (
            "general U(32) Clifford+T synthesis requires a KAK/CSD "
            "decomposition into 1- and 2-qubit factors that this "
            "substrate does not declare; the frontier above is the "
            "certified single-qubit datum"
        ),
        "consumer": (
            "F2 feasibility evidence — documentation only; no runtime "
            "consumer is declared, so this report does not feed any "
            "production decision path"
        ),
        "sk_length_bound_reference": "O(log^3.97(1/eps)) (Dawson-Nielsen)",
    }


__all__ = [
    "DEFAULT_ALPHABET",
    "phase_snap",
    "synthesize",
    "sk_length_bound",
    "forecast_propagator_report",
]
