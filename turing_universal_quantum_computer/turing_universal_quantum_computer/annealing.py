"""Exact quantum annealing and tunnelling — first principles, symbolic.

Quantum annealing evolves a register under
    H(s) = (1 - s) H_driver + s H_problem
with the transverse-field Ising model as the canonical driver/problem
pair:

    H_TFIM(g) = -J sum_i Z_i Z_{i+1}  -  h sum_i X_i,   g = h / J.

This module does NOT simulate annealing — it uses the exact closed-form
solution of the model (Jordan-Wigner -> free fermions -> Bogoliubov).
The free-fermion reduction is the first-principles analytical answer and
is valid for ANY chain length, including n = 10_000:

    single-mode energies:  eps_k(g) = 2J sqrt(1 + g^2 - 2 g cos k)
    momenta (even sector): k_m = (2m+1) pi / n,  m = 0..n-1
    ground energy:         E_0(g) = -1/2 sum_k eps_k(g)
    excitation gap:        Delta(g) = 2J sqrt((1-g)^2 + 4g sin^2(pi/2n))
    critical point:        g = 1,  Delta -> 4J sin(pi/2n) ~ pi J / n
    Landau-Zener:          P_diabatic = 1 - exp(-pi Delta^2 / (2 v))

All outputs are exact sympy expressions — algebraic numbers where the
answer is algebraic, symbolic transcendentals where it is not.  Nothing
is numerically approximated; ``sp.N``/float conversion is a caller's
explicit choice.  Observables that have no closed form (non-integrable
Hamiltonians) fail closed with ``NotImplementedError`` rather than
silently switching to a Trotter approximation.
"""

from __future__ import annotations

from typing import Any, Dict, List

import sympy as sp


class TransverseFieldIsing:
    """Exact spectrum of the 1-D transverse-field Ising chain, any n."""

    def __init__(self, n_spins: int, coupling=sp.Integer(1), field=sp.Integer(1)):
        if n_spins < 2:
            raise ValueError("n_spins must be >= 2")
        self.n = int(n_spins)
        self.J = sp.sympify(coupling)
        self.h = sp.sympify(field)

    def _g(self, field=None):
        h = self.h if field is None else sp.sympify(field)
        return sp.simplify(h / self.J)

    def momenta(self) -> List[Any]:
        """Anti-periodic Jordan-Wigner momenta k_m = (2m+1) pi / n."""
        return [sp.pi * (2 * m + 1) / self.n for m in range(self.n)]

    def mode_energy(self, k, field=None) -> Any:
        """eps_k = 2J sqrt(1 + g^2 - 2 g cos k) — exact algebraic."""
        g = self._g(field)
        return 2 * self.J * sp.sqrt(1 + g**2 - 2 * g * sp.cos(sp.sympify(k)))

    def ground_energy(self, field=None) -> Any:
        """E_0 = -1/2 sum_k eps_k — exact symbolic sum over all modes."""
        return -sp.Rational(1, 2) * sp.Add(
            *[self.mode_energy(k, field) for k in self.momenta()]
        )

    def gap(self, field=None) -> Any:
        """Smallest excitation energy — attained at the boundary mode pi/n.

        Delta = 2J sqrt((1-g)^2 + 4g sin^2(pi/2n)).
        """
        g = self._g(field)
        return sp.simplify(
            2 * self.J
            * sp.sqrt((1 - g) ** 2 + 4 * g * sp.sin(sp.pi / (2 * self.n)) ** 2)
        )

    def critical_gap(self) -> Any:
        """Gap exactly at the critical point g=1:  4J sin(pi/2n)."""
        return sp.simplify(4 * self.J * sp.sin(sp.pi / (2 * self.n)))

    def gap_asymptotic(self) -> Any:
        """2 pi J / n — leading large-n critical gap (exact limit).

        Convention note: for H = -J ZZ - h X the JW momenta start at
        k = pi/n and eps_k(g=1) = 4J sin(k/2), giving Delta ~ 2 pi J / n.
        """
        return 2 * sp.pi * self.J / self.n

    def mode_spectrum(self, field=None) -> Dict[str, Any]:
        """Exact per-mode spectrum: {k_m: eps_k} as symbolic entries."""
        return {sp.simplify(k): self.mode_energy(k, field) for k in self.momenta()}

    def adiabatic_path(self, s_values) -> Dict[str, Any]:
        """Gap along a linear anneal g(s) = s/(1-s) for 0<=s<1.

        s=1 (pure problem Hamiltonian) is the Ising ground state; the
        paramagnet driver dominates at s=0.  Returns exact gap(s) at each
        schedule point — the true bottleneck is at g=1 i.e. s=1/2.
        """
        out = []
        for s in s_values:
            s = sp.sympify(s)
            if not (sp.Integer(0) <= s < sp.Integer(1)):
                raise ValueError("anneal parameter s must lie in [0,1)")
            g = sp.simplify(s / (1 - s))
            out.append({"s": s, "g": g, "gap": self.gap(field=g * self.J)})
        return {"points": out, "minimum_at": "g=1 (s=1/2)", "n_spins": self.n}


def landau_zener(gap_min, sweep_rate) -> Any:
    """Exact Landau-Zener tunnel probability (symbolic).

    For a two-level avoided crossing H(t) = vt/2 * Z + Delta/2 * X, the
    probability of a diabatic (tunnelling) transition is

        P = 1 - exp(-pi Delta^2 / (2 hbar v))

    returned as an exact sympy expression (hbar = 1 units).
    """
    d = sp.sympify(gap_min)
    v = sp.sympify(sweep_rate)
    if d == 0:
        raise ValueError("gap_min = 0 is a level crossing, not an avoided crossing")
    return sp.simplify(1 - sp.exp(-sp.pi * d**2 / (2 * v)))


def adiabatic_condition(gap_min, sweep_rate) -> Any:
    """Exact adiabatic criterion: v << Delta^2 (returns Delta^2/v > 1 check)."""
    d = sp.sympify(gap_min)
    v = sp.sympify(sweep_rate)
    return sp.simplify(d**2 / v)


__all__ = [
    "TransverseFieldIsing",
    "landau_zener",
    "adiabatic_condition",
]
