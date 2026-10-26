r"""First-principles quantum walks — exact amplitudes, no approximation.

Two constructions:

1. ``CoinedCycleWalk`` — discrete-time coined walk on a cycle of N
   vertices.  Implemented directly on the sparse exact register:
   position lives in ceil(log2 N) qubits plus one coin qubit.  The coin is
   the exact Hadamard; the shift is an exact index permutation (a
   permutation of basis states IS the shift unitary — this is the
   mathematical operator, not a shortcut).  Reachable support is bounded
   by 2*min(N, steps+1) amplitudes, so it stays exact and sparse.

2. ``HypercubeWalk`` — continuous-time walk on the n-dimensional
   hypercube Q_n.  The adjacency matrix is A = sum_j X_j (all terms
   commute), so the propagator factorises EXACTLY:

       U(t) = e^{-iAt} = tensor_j e^{-it X_j}
       amp(x | 0) = (cos t)^{n-w(x)} (-i sin t)^{w(x)}

   The Hamming-weight distribution is therefore exactly binomial:

       P(w) = C(n,w) cos(t)^{2(n-w)} sin(t)^{2w}

   Closed form, exact sympy arithmetic, valid at n = 10_000 — no state
   materialisation, no truncation.  This is the first-principles answer,
   not a numerical shortcut.

All distributions return exact values (sympy / Fraction / QSqrt2).  Where
a quantity is intrinsically transcendental it is kept symbolic; float
conversion happens only on explicit request (``.to_float``), matching the
package's exact-then-export boundary convention.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import sympy as sp

from .hilbert import QuantumRegister


# ---------------------------------------------------------------------------
# Coined discrete-time walk on a cycle — sparse exact register
# ---------------------------------------------------------------------------


class CoinedCycleWalk:
    """Hadamard-coin walk on a cycle of ``num_positions`` vertices.

    Encoding: qubit ``pos_bits`` is the coin; qubits 0..pos_bits-1 hold the
    vertex index (little-endian).  Vertices >= num_positions are never
    reached because the shift permutation maps the cycle onto itself.
    """

    def __init__(self, num_positions: int, start: Optional[int] = None):
        if num_positions < 2:
            raise ValueError("cycle needs at least 2 positions")
        self.num_positions = int(num_positions)
        self.pos_bits = (self.num_positions - 1).bit_length()
        self.coin_q = self.pos_bits
        self.n_qubits = self.pos_bits + 1
        center = self.num_positions // 2 if start is None else int(start) % num_positions
        self.center = center
        self.register = QuantumRegister(self.n_qubits)
        # Initial state |x=center>|coin> = (|0> + i|1>)/sqrt(2) — the
        # symmetric unbiased coin sector (standard Hadamard-walk initial).
        reg = self.register
        reg.apply_h(self.coin_q)
        reg.apply_s(self.coin_q)
        # move position to center: flip position bits of |0>
        for q in range(self.pos_bits):
            if (center >> q) & 1:
                reg.apply_x(q)

    def step(self) -> None:
        """One walk step: coin unitary then conditional shift — both exact."""
        reg = self.register
        reg.apply_h(self.coin_q)
        # Shift: |c=0>|x> -> |x-1>, |c=1>|x> -> |x+1>  (mod num_positions).
        # Exact basis permutation applied to the sparse amplitude dict.
        new: Dict[int, Any] = {}
        for idx, amp in reg.amplitudes.items():
            x = idx & ((1 << self.pos_bits) - 1)
            c = (idx >> self.coin_q) & 1
            x2 = (x + 1) % self.num_positions if c else (x - 1) % self.num_positions
            new_idx = x2 | (c << self.coin_q)
            prev = new.get(new_idx)
            new[new_idx] = amp if prev is None else prev + amp
        reg.amplitudes = new

    def run(self, steps: int) -> "CoinedCycleWalk":
        for _ in range(int(steps)):
            self.step()
        return self

    def position_distribution(self) -> Dict[int, Any]:
        """Exact Born distribution over vertices (coin traced out)."""
        dist: Dict[int, Any] = {}
        for idx, amp in self.register.amplitudes.items():
            x = idx & ((1 << self.pos_bits) - 1)
            p = amp.abs2() if hasattr(amp, "abs2") else amp * sp.conjugate(amp)
            dist[x] = dist.get(x, 0) + p
        return dist

    def variance(self) -> Any:
        """Exact variance of position (walked distance from center)."""
        dist = self.position_distribution()
        n = self.num_positions
        center = self.center
        mean = sp.Integer(0)
        for x, p in dist.items():
            d = min((x - center) % n, (center - x) % n)
            pv = p.to_sympy() if hasattr(p, "to_sympy") else sp.sympify(p)
            mean += sp.sympify(d) * pv
        var = sp.Integer(0)
        for x, p in dist.items():
            d = min((x - center) % n, (center - x) % n)
            pv = p.to_sympy() if hasattr(p, "to_sympy") else sp.sympify(p)
            var += pv * (sp.sympify(d) - mean) ** 2
        return sp.simplify(var)


# ---------------------------------------------------------------------------
# Continuous-time walk on the hypercube — closed form
# ---------------------------------------------------------------------------


class HypercubeWalk:
    """Exact continuous-time quantum walk on the n-cube, H = -sum_j X_j.

    Because every term of the adjacency operator commutes, the propagator
    is a tensor product of single-qubit rotations; amplitudes and
    probabilities are closed-form exact for any n — including n = 10_000.
    """

    def __init__(self, n_qubits: int):
        if n_qubits < 1:
            raise ValueError("n_qubits must be >= 1")
        self.n_qubits = int(n_qubits)

    def vertex_amplitude(self, vertex: int, t) -> Any:
        """Exact amplitude <x|e^{-iAt}|0>:  cos^{n-w}(t) (-i sin t)^{w(x)}."""
        if not 0 <= vertex < (1 << self.n_qubits):
            raise ValueError("vertex out of range")
        w = bin(vertex).count("1")
        t = sp.sympify(t)
        return sp.cos(t) ** (self.n_qubits - w) * (-sp.I * sp.sin(t)) ** w

    def hamming_distribution(self, t) -> Dict[int, Any]:
        """Exact P(Hamming weight = w) = C(n,w) cos^{2(n-w)} t sin^{2w} t."""
        t = sp.sympify(t)
        n = self.n_qubits
        c2, s2 = sp.cos(t) ** 2, sp.sin(t) ** 2
        if c2 == 0:
            return {w: sp.Integer(w == n) for w in range(n + 1)}
        if s2 == 0:
            return {w: sp.Integer(w == 0) for w in range(n + 1)}
        if c2.is_Rational and s2.is_Rational:
            probability = c2 ** n
            ratio = s2 / c2
            distribution = {}
            for w in range(n + 1):
                distribution[w] = probability
                if w < n:
                    probability *= sp.Rational(n - w, w + 1) * ratio
            return distribution
        # Exact symbolic form, with an integer binomial recurrence rather than
        # recomputing all factorial products independently at every weight.
        coefficient = 1
        distribution = {}
        for w in range(n + 1):
            distribution[w] = sp.Mul(coefficient, c2 ** (n - w), s2 ** w, evaluate=False)
            if w < n:
                coefficient = coefficient * (n - w) // (w + 1)
        return distribution

    def expected_hamming_weight(self, t) -> Any:
        """E[w] = n sin^2 t — exact closed form."""
        return sp.sympify(self.n_qubits) * sp.sin(sp.sympify(t)) ** 2

    def hamming_variance(self, t) -> Any:
        """Var[w] = n sin^2 t cos^2 t — binomial variance, exact."""
        t = sp.sympify(t)
        return sp.sympify(self.n_qubits) * sp.sin(t) ** 2 * sp.cos(t) ** 2

    def vertex_probability(self, vertex: int, t) -> Any:
        """Exact Born probability of a single vertex: cos^{2(n-w)} sin^{2w}."""
        w = bin(int(vertex)).count("1")
        t = sp.sympify(t)
        return sp.cos(t) ** (2 * (self.n_qubits - w)) * sp.sin(t) ** (2 * w)


__all__ = [
    "CoinedCycleWalk",
    "HypercubeWalk",
]
