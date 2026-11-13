r"""AL HARAS legacy "unification" module: exact self-checks, no unification claims.

Older notes presented these classes as bridges uniting the Millennium Prize
Problems. No Millennium Prize Problem is solved, verified or related to by this
code, and no such unification exists to verify. The class and method names are
kept for existing imports and the AL HARAS router. Each method returns what it
computes, exactly (``int`` / ``fractions.Fraction``), or ``NOT_IMPLEMENTED``:

* ``SpectralDualityBridge.verify_spectral_mass_gap``: exact spectral certificate
  of the Paley graph P(q) from ``expander.py`` (degree, eigenvalues, spectral gap,
  Ramanujan bound). It is a finite-graph spectrum computation.
  ``compute_gue_pair_correlation``: ``NOT_IMPLEMENTED`` (the pair-correlation
  function is transcendental); only the normalised spacings of the input are
  computed.
* ``HarmonicCohomologyBridge.compute_bsd_modular_eigenspace``: Frobenius trace
  a_p of the conductor-53 curve E: y^2 + xy + y = x^3 - x^2 by exact point
  counting, an independent second count, the Hasse bound and the discriminant /
  conductor computed from the Weierstrass coefficients.
  ``evaluate_p_vs_np_sheaf_obstruction``: exact coboundary (consistency) check of
  the supplied vectors on a ring (``sheaf.py``); it says nothing about
  computational complexity.
* ``ParabolicFlowSingularityBridge.verify_vorticity_dissipation_and_surgery``:
  ``NOT_IMPLEMENTED``; there is no fluid or geometric-flow model here.
* ``GrandMillenniumUnificationNexus.verify_grand_millennium_unification``:
  ``NOT_IMPLEMENTED`` for the requested unification, reported together with the
  results of the exact self-checks above.
"""

import time
from fractions import Fraction
from typing import Any, Dict, Optional, Sequence, Tuple

from chronus.security.al_haras import expander, fingerprint
from chronus.security.al_haras.exact import decimal_string, fraction_str, to_vector
from chronus.security.al_haras.sheaf import analyse_states

__all__ = [
    "SpectralDualityBridge",
    "HarmonicCohomologyBridge",
    "ParabolicFlowSingularityBridge",
    "GrandMillenniumUnificationNexus",
    "CURVE_A_INVARIANTS",
    "count_points",
    "count_points_exhaustive",
    "weierstrass_invariants",
]

NOT_IMPLEMENTED = "NOT_IMPLEMENTED"

# E: y^2 + a1 xy + a3 y = x^3 + a2 x^2 + a4 x + a6 with [a1, a2, a3, a4, a6] = [1, -1, 1, 0, 0].
CURVE_A_INVARIANTS: Tuple[int, int, int, int, int] = (1, -1, 1, 0, 0)
MAX_POINT_COUNT_PRIME = 65_537
MAX_SPACING_VALUES = 4096


def _elapsed_us(started_ns: int) -> str:
    return decimal_string(Fraction(time.perf_counter_ns() - started_ns, 1000), 3)


def _prime(p: Any, limit: int) -> int:
    if isinstance(p, bool) or not isinstance(p, int) or not expander.is_prime(p) or p > limit:
        raise ValueError(f"p must be a prime number not larger than {limit}")
    return p


def weierstrass_invariants(a: Sequence[int]) -> Dict[str, int]:
    """b2, b4, b6, b8, c4, c6 and the discriminant of a general Weierstrass equation (exact integers)."""
    a1, a2, a3, a4, a6 = a
    b2 = a1 * a1 + 4 * a2
    b4 = 2 * a4 + a1 * a3
    b6 = a3 * a3 + 4 * a6
    b8 = a1 * a1 * a6 + 4 * a2 * a6 - a1 * a3 * a4 + a2 * a3 * a3 - a4 * a4
    c4 = b2 * b2 - 24 * b4
    c6 = -(b2**3) + 36 * b2 * b4 - 216 * b6
    discriminant = -b2 * b2 * b8 - 8 * b4**3 - 27 * b6 * b6 + 9 * b2 * b4 * b6
    return {"b2": b2, "b4": b4, "b6": b6, "b8": b8, "c4": c4, "c6": c6, "discriminant": discriminant}


def count_points(a: Sequence[int], p: int) -> int:
    """#E(F_p) for a general Weierstrass equation, including the point at infinity.

    For odd p, the number of y with y^2 + (a1 x + a3) y = x^3 + a2 x^2 + a4 x + a6 is
    1 + chi(D), D = (a1 x + a3)^2 + 4 (x^3 + a2 x^2 + a4 x + a6), chi the Legendre
    symbol (Euler's criterion). For p = 2, y^2 + b y = c has one solution when b = 0
    (squaring is a bijection of F_2) and, when b = 1, two solutions if c = 0 and none
    otherwise (y^2 + y vanishes on F_2). At a prime of bad reduction the singular
    point is counted, so p + 1 - #E(F_p) is still a_p.
    """
    a1, a2, a3, a4, a6 = (int(c) % p for c in a)
    if p == 2:
        total = 1
        for x in range(2):
            linear = (a1 * x + a3) % 2
            rhs = (x * x * x + a2 * x * x + a4 * x + a6) % 2
            total += 1 if linear == 0 else (2 if rhs == 0 else 0)
        return total
    total = 1
    for x in range(p):
        rhs = (x * x * x + a2 * x * x + a4 * x + a6) % p
        linear = (a1 * x + a3) % p
        disc = (linear * linear + 4 * rhs) % p
        if disc == 0:
            total += 1
        elif pow(disc, (p - 1) // 2, p) == 1:
            total += 2
    return total


def count_points_exhaustive(a: Sequence[int], p: int) -> int:
    """#E(F_p) by testing every pair (x, y) in F_p x F_p (O(p^2); independent of ``count_points``)."""
    a1, a2, a3, a4, a6 = (int(c) % p for c in a)
    affine = 0
    for x in range(p):
        rhs = (x * x * x + a2 * x * x + a4 * x + a6) % p
        for y in range(p):
            if (y * y + a1 * x * y + a3 * y - rhs) % p == 0:
                affine += 1
    return affine + 1


def _factor(n: int) -> Dict[int, int]:
    factors: Dict[int, int] = {}
    d = 2
    while d * d <= n:
        while n % d == 0:
            factors[d] = factors.get(d, 0) + 1
            n //= d
        d += 1
    if n > 1:
        factors[n] = factors.get(n, 0) + 1
    return factors


# ==============================================================================
# 1. SPECTRAL COMPUTATIONS (PALEY GRAPH CERTIFICATE)
# ==============================================================================


class SpectralDualityBridge:
    """Exact graph-spectrum computations; name kept for existing imports.

    ``verify_spectral_mass_gap`` returns the exact certificate of the Paley graph
    P(q) (``expander.certify_paley``). The Paley graph has degree (q - 1) / 2, so a
    different requested degree is reported as unavailable rather than simulated.
    ``compute_gue_pair_correlation`` is not implemented.
    """

    @classmethod
    def compute_gue_pair_correlation(cls, s_values: Sequence[Any]) -> Dict[str, Any]:
        """NOT_IMPLEMENTED; computes only the normalised nearest-neighbour spacings (exact)."""
        values = sorted(to_vector(list(s_values)))
        if len(values) > MAX_SPACING_VALUES:
            raise ValueError(f"at most {MAX_SPACING_VALUES} values are supported")
        spacings = [b - a for a, b in zip(values, values[1:])]
        mean = sum(spacings, Fraction(0)) / len(spacings) if spacings else Fraction(0)
        normalised = [s / mean for s in spacings] if mean else []
        return {
            "status": NOT_IMPLEMENTED,
            "requested_operation": "pair-correlation statistic 1 - (sin(pi x) / (pi x))^2",
            "reason": "the statistic is transcendental and is not evaluated in this exact-arithmetic package",
            "computed": "nearest-neighbour spacings of the sorted input divided by their mean (exact)",
            "value_count": len(values),
            "normalised_spacings": [fraction_str(s) for s in normalised],
        }

    @classmethod
    def verify_spectral_mass_gap(cls, degree: Optional[int] = None, prime_p: int = 257) -> Dict[str, Any]:
        """Exact spectral certificate of the Paley graph P(prime_p); name kept for existing callers."""
        cert = expander.certify_paley(prime_p)
        public = {k: v for k, v in cert.items() if k != "walk_contraction_upper_bound"}
        return {
            "computation": "exact spectral certificate of the Paley graph P(q) (strong regularity checked pair by pair)",
            "certificate": public,
            "requested_degree": degree,
            "degree_used": cert["degree"],
            "requested_degree_available": degree is None or degree == cert["degree"],
            "spectral_gap_exact": cert["spectral_gap_exact"],
            "spectral_gap_decimal": cert["spectral_gap_decimal"],
            "is_ramanujan": cert["is_ramanujan"],
            "status": "RAMANUJAN_BOUND_MET" if cert["is_ramanujan"] else "RAMANUJAN_BOUND_NOT_MET",
            "scope": "spectrum of one finite graph; it does not address any Millennium Prize Problem",
        }


# ==============================================================================
# 2. ELLIPTIC-CURVE POINT COUNT AND SHEAF CONSISTENCY
# ==============================================================================


class HarmonicCohomologyBridge:
    """Exact elliptic-curve point counting and sheaf consistency; name kept for existing imports."""

    @classmethod
    def compute_bsd_modular_eigenspace(cls, p: int = 257) -> Dict[str, Any]:
        """Frobenius trace a_p of E: y^2 + xy + y = x^3 - x^2 over F_p (name kept for existing callers).

        Two independent counts (Legendre-symbol count of the general equation, and the
        short model y^2 = x^3 - 27 c4 x - 54 c6 counted by ``fingerprint.count_points``,
        or exhaustive search for p < 5) must agree. The bound is |a_p| <= 2 sqrt(p)
        (checked as a_p^2 <= 4p) at good primes and |a_p| = 1 at multiplicative primes.
        """
        p = _prime(p, MAX_POINT_COUNT_PRIME)
        inv = weierstrass_invariants(CURVE_A_INVARIANTS)
        disc, c4, c6 = inv["discriminant"], inv["c4"], inv["c6"]
        identity_holds = 1728 * disc == c4**3 - c6 * c6
        factors = _factor(abs(disc))
        squarefree = disc != 0 and all(e == 1 for e in factors.values())
        conductor = abs(disc) if squarefree else None
        points = count_points(CURVE_A_INVARIANTS, p)
        a_p = p + 1 - points
        if p >= 5:
            independent = fingerprint.count_points((-27 * c4) % p, (-54 * c6) % p, p)
            independent_method = "short Weierstrass model y^2 = x^3 - 27 c4 x - 54 c6 over F_p"
        else:
            independent = count_points_exhaustive(CURVE_A_INVARIANTS, p)
            independent_method = "exhaustive search over F_p x F_p"
        if disc % p:
            reduction = "good"
            bound = "a_p^2 <= 4p (Hasse)"
            bound_ok = a_p * a_p <= 4 * p
        elif c4 % p:
            reduction = "multiplicative"
            bound = "|a_p| = 1 (multiplicative reduction)"
            bound_ok = abs(a_p) == 1
        else:
            reduction = "additive"
            bound = "a_p = 0 (additive reduction)"
            bound_ok = a_p == 0
        agree = independent == points
        return {
            "computation": "Frobenius trace a_p = p + 1 - #E(F_p) by exact point counting",
            "curve": "E: y^2 + xy + y = x^3 - x^2",
            "a_invariants": list(CURVE_A_INVARIANTS),
            "discriminant": disc,
            "c4": c4,
            "c6": c6,
            "identity_1728_disc_equals_c4_cubed_minus_c6_squared": identity_holds,
            "conductor": conductor,
            "conductor_method": (
                "|discriminant| is squarefree, so every bad prime has v_p(disc) = 1: multiplicative reduction "
                "with conductor exponent 1 (Ogg's formula), and the conductor is |discriminant|"
                if squarefree
                else "not computed (discriminant is not squarefree)"
            ),
            "prime_p": p,
            "reduction_at_p": reduction,
            "point_count": points,
            "frobenius_trace_ap": a_p,
            "independent_point_count": independent,
            "independent_method": independent_method,
            "independent_count_agrees": agree,
            "bound": bound,
            "bound_satisfied": bound_ok,
            "status": "COMPUTED" if agree and bound_ok and identity_holds else "CHECK_FAILED",
            "scope": (
                "a point count of one curve at one prime. By the modularity theorem a_p is also the p-th "
                "Hecke eigenvalue of the level-53 newform (a known theorem, not checked here). The Birch and "
                "Swinnerton-Dyer conjecture concerns L(E, s) at s = 1 and is not addressed."
            ),
        }

    @classmethod
    def evaluate_p_vs_np_sheaf_obstruction(cls, stalks: Sequence[Sequence[Any]]) -> Dict[str, Any]:
        """Exact consistency of the supplied vectors on the ring n0 -> n1 -> ... -> n0 (name kept).

        Uses the constant sheaf of ``sheaf.analyse_states``: the vectors agree iff the
        coboundary delta^0 s is zero. It has no bearing on computational complexity.
        """
        vectors = [list(s) for s in stalks]
        if not vectors:
            return {
                "evaluated": False,
                "status": "NO_STATE_SUPPLIED",
                "scope": "no vectors supplied; nothing was compared",
            }
        result = analyse_states({f"n{i}": v for i, v in enumerate(vectors)})
        return {
            "evaluated": True,
            "computation": "exact coboundary of the constant sheaf on the ring n0 -> n1 -> ... -> n0",
            "stalk_count": len(vectors),
            "consistent": result["consistent"],
            "coboundary_max_edge_norm_sq": fraction_str(result["max_edge_norm_sq"]),
            "coboundary_total_norm_sq": fraction_str(result["total_norm_sq"]),
            "worst_edge": result["worst_edge"],
            "cohomology_dimensions": result["dimensions"],
            "status": "CONSISTENT" if result["consistent"] else "INCONSISTENT",
            "scope": "agreement of the supplied vectors; no statement about computational complexity classes",
        }


# ==============================================================================
# 3. FLOW MODEL: NOT IMPLEMENTED
# ==============================================================================


class ParabolicFlowSingularityBridge:
    """Not implemented: there is no fluid or geometric-flow model in this package.

    Name kept for existing imports. The previous code iterated an ad-hoc scalar
    recurrence and reset it at a fixed cap; that was not a model of any flow, so it
    was removed.
    """

    @classmethod
    def verify_vorticity_dissipation_and_surgery(
        cls,
        initial_enstrophy: Any = None,
        viscosity_nu: Any = None,
        timesteps: Any = None,
    ) -> Dict[str, Any]:
        return {
            "status": NOT_IMPLEMENTED,
            "requested_operation": "enstrophy dissipation with surgery for a fluid or geometric flow",
            "reason": "no fluid or geometric-flow model is implemented; nothing is simulated or verified",
            "inputs_used": False,
        }


# ==============================================================================
# 4. LEGACY "UNIFICATION" ENTRY POINT
# ==============================================================================


class GrandMillenniumUnificationNexus:
    """Legacy entry point; reports NOT_IMPLEMENTED plus exact self-checks (name kept for callers)."""

    @classmethod
    def verify_grand_millennium_unification(cls) -> Dict[str, Any]:
        """There is no unification to verify; returns NOT_IMPLEMENTED and the computed self-checks."""
        started = time.perf_counter_ns()
        spectral = SpectralDualityBridge.verify_spectral_mass_gap(prime_p=257)
        curve = HarmonicCohomologyBridge.compute_bsd_modular_eigenspace(p=257)
        agreeing = HarmonicCohomologyBridge.evaluate_p_vs_np_sheaf_obstruction([(1, 0, 0, 0)] * 3)
        disagreeing = HarmonicCohomologyBridge.evaluate_p_vs_np_sheaf_obstruction(
            [(1, 0, 0, 0), (1, 0, 0, 0), (2, 0, 0, 0)]
        )
        checks = {
            "paley_257_ramanujan_certificate": bool(
                spectral["is_ramanujan"] and spectral["certificate"]["strongly_regular"]
            ),
            "curve_point_counts_agree_at_257": curve["independent_count_agrees"],
            "curve_bound_at_257": curve["bound_satisfied"],
            "sheaf_check_separates_agreeing_and_disagreeing_states": bool(
                agreeing["consistent"] and not disagreeing["consistent"]
            ),
        }
        certificate = spectral["certificate"]
        return {
            "system": "AL HARAS exact-mathematics self-checks (legacy name: Grand Millennium Unification Nexus)",
            "status": NOT_IMPLEMENTED,
            "requested_operation": "verification of a unification of the Millennium Prize Problems",
            "reason": (
                "no such unification is known or implemented; no Millennium Prize Problem is solved, verified "
                "or related to by this code. The checks below are self-tests of exact AL HARAS computations."
            ),
            "computed_checks": checks,
            "computed_checks_passed": all(checks.values()),
            "check_details": {
                "paley_graph": {
                    "graph": certificate["graph"],
                    "degree": certificate["degree"],
                    "srg_parameters": certificate["srg_parameters"],
                    "spectral_gap_exact": certificate["spectral_gap_exact"],
                    "is_ramanujan": certificate["is_ramanujan"],
                },
                "elliptic_curve": {
                    key: curve[key]
                    for key in (
                        "curve",
                        "prime_p",
                        "point_count",
                        "frobenius_trace_ap",
                        "independent_point_count",
                        "bound",
                        "bound_satisfied",
                    )
                },
                "sheaf_consistency": {
                    "agreeing_states": agreeing["status"],
                    "disagreeing_states": disagreeing["status"],
                    "disagreement_max_edge_norm_sq": disagreeing["coboundary_max_edge_norm_sq"],
                },
            },
            "not_implemented": [
                "any statement about a Millennium Prize Problem",
                "pair-correlation statistic of spectra",
                "fluid or geometric-flow model",
            ],
            "compute_time_us_measured": _elapsed_us(started),
        }
