# LUCAS WIRING: mtheory
# Substrate route: mtheory
"""Exact duality-group arithmetic connecting the five 10D string limits
and the 11D origin.

What is implemented here is the *exact transformation law* of each
duality on the objects it acts on — nothing more:

* **T-duality** on the momentum+winding spectrum of a bosonic circle:
  ``E^2(n, w; R) = (n/R)^2 + (w R / alpha')^2`` is invariant under
  ``R -> alpha'/R, n <-> w``.  ``verify_t_duality`` proves the *entire*
  truncated spectrum multiset is preserved, by exact ``Counter``
  equality — this is the real T-duality statement.

* **S-duality**: ``g -> 1/g`` and the ``SL(2, Z)`` action on the
  axiodilaton ``tau = chi + i/g``, implemented exactly on Gaussian
  rationals (``tau`` is a pair ``(Re, Im)`` of ``Fraction``).
  ``FIVE_LIMITS`` is the exact symbolic permutation table of the five
  10D limits plus the 11D origin under the duality group.

* **IIA <-> 11D**: ``R_11 = g_s * l_p`` and its inverse, exact.

* **U-duality**: the joint ``T x S`` action on
  ``(n_vec, w_vec, R_vec, g)``; T and S act on disjoint factors and
  commute exactly.

All arithmetic is ``int``/``Fraction`` — no floats, no approximation,
no simulation.  These are exact group actions on truncated spectra, not
a claim of physical string dynamics.
"""

from __future__ import annotations

from collections import Counter
from fractions import Fraction
from typing import Dict, Iterable, Tuple

ONE = Fraction(1)


# ---------------------------------------------------------------------------
# T-duality on the circle spectrum
# ---------------------------------------------------------------------------

def bosonic_spectrum(
    n: int,
    w: int,
    R: Fraction,
    alpha_prime: Fraction = ONE,
) -> Fraction:
    """Exact E^2 = (n/R)^2 + (w R / alpha')^2 for one circle.

    ``n`` momentum number, ``w`` winding number (ints); ``R`` the circle
    radius and ``alpha_prime`` the Regge slope as Fractions.
    """
    n, w = int(n), int(w)
    R = Fraction(R)
    alpha_prime = Fraction(alpha_prime)
    if R <= 0 or alpha_prime <= 0:
        raise ValueError("R and alpha_prime must be positive")
    mom = Fraction(n) / R
    wind = Fraction(w) * R / alpha_prime
    return mom * mom + wind * wind


def t_dualize(
    n: int,
    w: int,
    R: Fraction,
    alpha_prime: Fraction = ONE,
) -> Tuple[int, int, Fraction]:
    """T-dual circle data: ``(n, w, R) -> (w, n, alpha'/R)``.

    Returns ``(n', w', R')``; ``alpha_prime`` is unchanged (the dual
    radius already encodes it).  Applying twice returns the input.
    """
    alpha_prime = Fraction(alpha_prime)
    R = Fraction(R)
    return (int(w), int(n), alpha_prime / R)


def circle_spectrum(n_max: int, R: Fraction, alpha_prime: Fraction = ONE) -> Counter:
    """Exact multiset of E^2 over the truncated lattice ``|n|,|w| <= n_max``."""
    if n_max < 0:
        raise ValueError("n_max must be non-negative")
    return Counter(
        bosonic_spectrum(n, w, R, alpha_prime)
        for n in range(-n_max, n_max + 1)
        for w in range(-n_max, n_max + 1)
    )


def verify_t_duality(n_max: int, R: Fraction, alpha_prime: Fraction = ONE) -> bool:
    """Exact multiset invariance of the truncated circle spectrum.

    Asserts ``Counter{E^2(n,w;R)} == Counter{E^2(n,w;alpha'/R)}`` over
    the whole truncated lattice — the spectrum is identical before and
    after ``R -> alpha'/R`` because the map ``(n,w) -> (w,n)`` is an
    exact bijection of the lattice carrying each level to an equal one.
    """
    R = Fraction(R)
    alpha_prime = Fraction(alpha_prime)
    before = circle_spectrum(n_max, R, alpha_prime)
    _, _, R_dual = t_dualize(0, 0, R, alpha_prime)
    after = circle_spectrum(n_max, R_dual, alpha_prime)
    assert before == after, (
        f"T-duality spectrum mismatch at R={R}: {before - after} / {after - before}"
    )
    # Pointwise shadow: every mode's energy equals its dual's exactly.
    for n in range(-n_max, n_max + 1):
        for w in range(-n_max, n_max + 1):
            n2, w2, R2 = t_dualize(n, w, R, alpha_prime)
            assert bosonic_spectrum(n, w, R, alpha_prime) == bosonic_spectrum(
                n2, w2, R2, alpha_prime
            )
    # Involution: T applied twice is the identity on (n, w, R).
    for n in range(-n_max, n_max + 1):
        for w in range(-n_max, n_max + 1):
            n2, w2, R2 = t_dualize(n, w, R, alpha_prime)
            assert t_dualize(n2, w2, R2, alpha_prime) == (n, w, R)
    return True


# ---------------------------------------------------------------------------
# S-duality and SL(2, Z) on the axiodilaton
# ---------------------------------------------------------------------------

# tau is represented exactly as a pair (Re, Im) of Fractions — a Gaussian
# rational.  Convention: tau = chi + i/g_s  =>  g_s = 1 / Im(tau).
Tau = Tuple[Fraction, Fraction]

# SL(2, Z) elements as (a, b, c, d) integer tuples with ad - bc = 1.
SL2Z = Tuple[int, int, int, int]

S_ELEMENT: SL2Z = (0, -1, 1, 0)   # tau -> -1/tau   (S-duality)
T_ELEMENT: SL2Z = (1, 1, 0, 1)    # tau -> tau + 1  (axion shift)
IDENTITY: SL2Z = (1, 0, 0, 1)


def sl2z_compose(m1: SL2Z, m2: SL2Z) -> SL2Z:
    """Exact integer matrix product ``m1 * m2`` of two SL(2,Z) elements."""
    a1, b1, c1, d1 = m1
    a2, b2, c2, d2 = m2
    return (
        a1 * a2 + b1 * c2,
        a1 * b2 + b1 * d2,
        c1 * a2 + d1 * c2,
        c1 * b2 + d1 * d2,
    )


def sl2z_act(m: SL2Z, tau: Tau) -> Tau:
    """Exact Mobius action ``tau -> (a tau + b)/(c tau + d)`` on Gaussian
    rationals, computed without complex floats.

    For ``tau = x + i y``:

        Re tau' = ((a x + b)(c x + d) + a c y^2) / D
        Im tau' = (ad - bc) y / D
        D       = (c x + d)^2 + (c y)^2
    """
    a, b, c, d = m
    if a * d - b * c != 1:
        raise ValueError("not an SL(2,Z) element: determinant must be exactly 1")
    x, y = Fraction(tau[0]), Fraction(tau[1])
    if y <= 0:
        raise ValueError("tau must lie in the upper half-plane (Im > 0)")
    p = a * x + b
    q = a * y
    r = c * x + d
    s = c * y
    D = r * r + s * s
    return ((p * r + q * s) / D, y / D)  # (ad - bc) == 1


def s_dualize(g: Fraction) -> Fraction:
    """Exact S-dual coupling ``g -> 1/g``."""
    g = Fraction(g)
    if g <= 0:
        raise ValueError("coupling must be positive")
    return 1 / g


def tau_from_coupling(g: Fraction, chi: Fraction = Fraction(0)) -> Tau:
    """Exact axiodilaton ``tau = chi + i/g`` from the string coupling."""
    g = Fraction(g)
    if g <= 0:
        raise ValueError("coupling must be positive")
    return (Fraction(chi), 1 / g)


def coupling_from_tau(tau: Tau) -> Fraction:
    """Exact ``g_s = 1 / Im(tau)``."""
    return 1 / Fraction(tau[1])


# The exact duality permutation on the five 10D limits + 11D origin.
# Each entry maps a limit label to its strong/weak (or geometrised)
# partner; the map is a genuine involution on every label it exchanges.
FIVE_LIMITS: Dict[str, str] = {
    # Type IIA at strong coupling grows the 11th circle -> 11D origin.
    "IIA": "M11",
    "M11": "IIA",
    # Type IIB is self-dual under the full SL(2,Z).
    "IIB": "IIB",
    # Type I <-> Heterotic SO(32) under S (g -> 1/g).
    "I": "HET_SO32",
    "HET_SO32": "I",
    # Heterotic E8 x E8 <-> 11D on the interval S^1/Z_2.
    "HET_E8E8": "M11_Z2",
    "M11_Z2": "HET_E8E8",
}


def verify_s_duality(taus: Iterable[Tau] = ()) -> Dict[str, bool]:
    """Exact S-duality checks.

    (a) ``S`` is an involution: ``S^2 = id`` on every tested ``tau``
        (matrix identity *and* the Mobius action itself).
    (b) On a vanishing-axion ``tau = i/g``, S sends ``Im(tau)`` from
        ``1/g`` to ``g``, i.e. ``g -> 1/g`` exactly, matching
        ``s_dualize``.
    (c) ``FIVE_LIMITS`` is an exact involution: applying the map twice
        returns every label; the map is a bijection on its label set.
    """
    taus = list(taus) or [
        (Fraction(1, 3), Fraction(2, 5)),
        (Fraction(0), Fraction(1)),
        (Fraction(-2, 7), Fraction(5, 3)),
    ]
    checks: Dict[str, bool] = {}

    # (a) S^2 = -I in SL(2,Z), which is the identity as a Mobius map.
    checks["S_squared_matrix"] = sl2z_compose(S_ELEMENT, S_ELEMENT) == (-1, 0, 0, -1)
    checks["S_involution_on_tau"] = all(
        sl2z_act(S_ELEMENT, sl2z_act(S_ELEMENT, tau)) == tau for tau in taus
    )

    # (b) Im(tau): 1/g -> g exactly  <=>  g -> 1/g.
    g = Fraction(2, 5)
    tau0 = tau_from_coupling(g)
    tau1 = sl2z_act(S_ELEMENT, tau0)
    checks["im_tau_inverts"] = (
        tau0[1] == 1 / g and tau1[1] == g and coupling_from_tau(tau1) == s_dualize(g)
    )
    checks["s_dualize_involution"] = s_dualize(s_dualize(g)) == g

    # (c) Five-limit permutation laws.
    labels = set(FIVE_LIMITS)
    checks["limits_bijection"] = set(FIVE_LIMITS.values()) == labels
    checks["limits_involution"] = all(
        FIVE_LIMITS[FIVE_LIMITS[label]] == label for label in labels
    )
    checks["type_i_het_pair"] = (
        FIVE_LIMITS["I"] == "HET_SO32" and FIVE_LIMITS["HET_SO32"] == "I"
    )
    checks["iib_self_dual"] = FIVE_LIMITS["IIB"] == "IIB"
    checks["iia_m11_pair"] = FIVE_LIMITS["IIA"] == "M11" and FIVE_LIMITS["M11"] == "IIA"
    return checks


# ---------------------------------------------------------------------------
# Type IIA <-> 11D circle
# ---------------------------------------------------------------------------

def iia_to_11d(g_s: Fraction, l_p: Fraction) -> Fraction:
    """Exact 11th-circle radius ``R_11 = g_s * l_p``."""
    g_s = Fraction(g_s)
    l_p = Fraction(l_p)
    if g_s <= 0 or l_p <= 0:
        raise ValueError("g_s and l_p must be positive")
    return g_s * l_p


def eleven_d_coupling(R: Fraction, l_p: Fraction) -> Fraction:
    """Exact inverse: the IIA coupling ``g_s = R_11 / l_p`` of an 11D
    circle compactification."""
    R = Fraction(R)
    l_p = Fraction(l_p)
    if R <= 0 or l_p <= 0:
        raise ValueError("R and l_p must be positive")
    return R / l_p


def verify_iia_11d(
    g_s: Fraction = Fraction(2, 5),
    l_p: Fraction = Fraction(1),
    lam: Fraction = Fraction(7, 3),
) -> Dict[str, bool]:
    """Exact checks for the IIA <-> 11D-circle duality.

    * roundtrip: ``g_s -> R_11 -> g_s`` and ``R_11 -> g_s -> R_11`` are
      exact identities;
    * growth law: scaling ``g_s -> lam * g_s`` scales
      ``R_11 -> lam * R_11`` exactly (strong coupling grows the
      11th dimension).
    """
    g_s, l_p, lam = Fraction(g_s), Fraction(l_p), Fraction(lam)
    R11 = iia_to_11d(g_s, l_p)
    return {
        "roundtrip_g": eleven_d_coupling(iia_to_11d(g_s, l_p), l_p) == g_s,
        "roundtrip_R": iia_to_11d(eleven_d_coupling(R11, l_p), l_p) == R11,
        "growth_exact": iia_to_11d(lam * g_s, l_p) == lam * R11,
    }


# ---------------------------------------------------------------------------
# U-duality: joint T x S action on (n_vec, w_vec, R_vec, g)
# ---------------------------------------------------------------------------

# A U-state on k circles: (n_vec, w_vec, R_vec, g, alpha_prime), all exact.
UState = Tuple[Tuple[int, ...], Tuple[int, ...], Tuple[Fraction, ...], Fraction, Fraction]

# Elements: ("T", i) T-dualises circle i;  ("S",) S-dualises the coupling.
UElement = Tuple


def u_dualize(element: Iterable[UElement], state: UState) -> UState:
    """Apply a U-duality word (sequence of T and S factors) to ``state``.

    ``("T", i)`` swaps ``n_i <-> w_i`` and sends ``R_i -> alpha'/R_i``;
    ``("S",)`` sends ``g -> 1/g``.  Factors on disjoint circles/coupling
    commute exactly — see ``verify_u_duality``.
    """
    n, w, R, g, alpha_prime = state
    n = list(int(k) for k in n)
    w = list(int(k) for k in w)
    R = list(Fraction(r) for r in R)
    g = Fraction(g)
    alpha_prime = Fraction(alpha_prime)
    for factor in element:
        if factor[0] == "T":
            i = int(factor[1])
            n[i], w[i] = w[i], n[i]
            R[i] = alpha_prime / R[i]
        elif factor[0] == "S":
            g = 1 / g
        else:
            raise ValueError(f"unknown U-duality factor {factor!r}")
    return (tuple(n), tuple(w), tuple(R), g, alpha_prime)


def verify_u_duality(
    state: UState = (
        (1, -2, 0),
        (0, 3, -1),
        (Fraction(2), Fraction(3, 5), Fraction(7)),
        Fraction(2, 5),
        Fraction(1),
    ),
) -> Dict[str, bool]:
    """Exact U-duality checks.

    T on circle i and S on g act on disjoint factors, so they commute:
    ``[("T", i), ("S",)]`` and ``[("S",), ("T", i)]`` give identical
    states.  T factors on *different* circles also commute.  Each factor
    is an involution on its factor.
    """
    k = len(state[0])
    checks: Dict[str, bool] = {}
    for i in range(k):
        ts = u_dualize([("T", i), ("S",)], state)
        st = u_dualize([("S",), ("T", i)], state)
        checks[f"T{i}_commutes_S"] = ts == st
        checks[f"T{i}_involution"] = u_dualize([("T", i), ("T", i)], state) == state
    for i in range(k):
        for j in range(i + 1, k):
            checks[f"T{i}_commutes_T{j}"] = u_dualize(
                [("T", i), ("T", j)], state
            ) == u_dualize([("T", j), ("T", i)], state)
    checks["S_involution"] = u_dualize([("S",), ("S",)], state) == state
    return checks


def to_float(x):
    """Derived display helper only — converts an exact value for humans.

    Not used anywhere in the computation or verification paths.
    """
    if isinstance(x, Fraction):
        return float(x)
    if isinstance(x, (tuple, list)):
        return type(x)(to_float(v) for v in x)
    return x


__all__ = [
    "bosonic_spectrum",
    "circle_spectrum",
    "t_dualize",
    "verify_t_duality",
    "s_dualize",
    "sl2z_act",
    "sl2z_compose",
    "tau_from_coupling",
    "coupling_from_tau",
    "verify_s_duality",
    "S_ELEMENT",
    "T_ELEMENT",
    "IDENTITY",
    "SL2Z",
    "Tau",
    "FIVE_LIMITS",
    "iia_to_11d",
    "eleven_d_coupling",
    "verify_iia_11d",
    "u_dualize",
    "verify_u_duality",
    "UState",
    "to_float",
]
