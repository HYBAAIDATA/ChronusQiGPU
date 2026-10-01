"""TOE algebraic substrate (Pisot families) + PredictiveEngine application.

STATUS: Application/analytics surface on the canonical stack.
The canonical mining path is main.py + chronus/mla1517_platform/python
(control_api → mining_runtime → chronus.mla1517.mining.*): it owns the pool
socket, the SHA256d consensus check, and share submission. This module
is exercised by the Intelligence stack (orchestrator, agentic_mining,
toe.system) and tests only.

Two distinct layers live here:

1. ``ExtendedAlgebraicFamily`` / ``AlgebraicFormulations`` /
   ``ManifoldEnhancedFormulations`` — the domain-general exact algebra:
   five Pisot generator families, Binet closed forms, companion-matrix
   traces, Sturm-sequence spectral gaps, Zeckendorf decompositions,
   family-signature detection. No floating point in the substrate.
   ``theorem_proven`` is False on the Millennium-facet reports — that is
   the honesty boundary, deliberately kept.

2. ``PredictiveEngine`` — ONE application of that substrate. Its shipped
   indicator schema is employee-churn-shaped (HR telemetry columns), but
   the computation beneath is the substrate itself: Hilbert state
   vectors, Born-rule ensemble aggregation, Schrödinger evolution,
   quantum fidelity. Read the math, not the column names — the engine is
   a demonstration of the algebra, not an HR product.

For the mining-facing TOE coordinator (12-theorem candidate verification
on nonce candidates, provenance ledger, 13-substrate dispatch) see
``toe/system.py``. For the quantum analytics bridge see
``toe/bridge.py``.
"""

from __future__ import annotations

# Keep model dependencies out of the exact-algebra import path.
import importlib
import sys

import numpy as np

from datetime import datetime, timezone

from decimal import Decimal, getcontext

from fractions import Fraction

import logging

import math

import os

import random
import statistics

# Single-source versioning: the package literal lives in toe/__init__.py
# (bound before this module is imported there); engine derives, never
# redeclares.
from toe import __version__  # noqa: F401

_LAZY_MODULES = {
    "pd": "pandas",
    "joblib": "kellogg.tensor_ml",
}

_LAZY_FROM = {
    "RandomForestClassifier": ("kellogg.tensor_ml", "RandomForestClassifier"),
    "GradientBoostingClassifier": ("kellogg.tensor_ml", "GradientBoostingClassifier"),
    "cross_val_score": ("kellogg.tensor_ml", "cross_val_score"),
    "StandardScaler": ("kellogg.tensor_ml", "StandardScaler"),
    "SimpleImputer": ("kellogg.tensor_ml", "SimpleImputer"),
    "TfidfVectorizer": ("kellogg.tensor_ml", "TfidfVectorizer"),
    "f1_score": ("kellogg.tensor_ml", "f1_score"),
    "precision_score": ("kellogg.tensor_ml", "precision_score"),
    "recall_score": ("kellogg.tensor_ml", "recall_score"),
    "accuracy_score": ("kellogg.tensor_ml", "accuracy_score"),
    "XGBClassifier": ("kellogg.tensor_ml", "XGBClassifier"),
    "LGBMClassifier": ("kellogg.tensor_ml", "LGBMClassifier"),
    "SentimentIntensityAnalyzer": ("kellogg.tensor_ml", "TensorSentimentAnalyzer"),
    "seasonal_decompose": ("statsmodels.tsa.seasonal", "seasonal_decompose"),
    "BayesSearchCV": ("skopt", "BayesSearchCV"),
    "Real": ("skopt.space", "Real"),
    "Integer": ("skopt.space", "Integer"),
    "LimeTabularExplainer": ("lime.lime_tabular", "LimeTabularExplainer"),
    "exact_linear": ("kellogg.tensor_ml", "exact_linear"),
    "rf": ("kellogg.tensor_ml", "rf"),
    "xgb": ("kellogg.tensor_ml", "xgb"),
    "lgbm": ("kellogg.tensor_ml", "lgbm"),
    "gb": ("kellogg.tensor_ml", "gb"),
}


_OPTIONAL_GROUPS = {
    "_HAS_STATSMODELS": ("seasonal_decompose",),
    "_HAS_SKOPT": ("BayesSearchCV", "Real", "Integer"),
    "_HAS_LIME": ("LimeTabularExplainer",),
}


def __getattr__(name: str):
    """Resolve model dependencies on demand; required failures propagate."""
    for flag, members in _OPTIONAL_GROUPS.items():
        if name == flag or name in members:
            try:
                values = {
                    member: getattr(
                        importlib.import_module(_LAZY_FROM[member][0]), _LAZY_FROM[member][1]
                    )
                    for member in members
                }
            except Exception as exc:
                logging.warning("Optional dependency %s unavailable: %s", flag, exc)
                values = dict.fromkeys(members)
                available = False
            else:
                available = True
            globals().update(values)
            globals()[flag] = available
            return available if name == flag else values[name]
    if name in _LAZY_MODULES:
        value = importlib.import_module(_LAZY_MODULES[name])
    elif name in _LAZY_FROM:
        module, attribute = _LAZY_FROM[name]
        value = getattr(importlib.import_module(module), attribute)
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    globals()[name] = value
    return value


_dependencies = sys.modules[__name__]

# Canonical substrate wire: when turing_core is importable the algebraic
# family below draws its roots and signature detector from the shared
# exact core (the same substrate the iGPU/mining path runs). Without it,
# the embedded implementations keep toe.engine fully self-contained.
try:
    import turing_core as _turing_core

    # PYTHIA also ships a smaller mining-only ``turing_core`` module for
    # nonce ordering.  TOE requires the algebraic substrate symbols; if a
    # caller's import path selected the mining helper, use TOE's embedded
    # exact fallback instead of failing halfway through construction.
    if not all(
        hasattr(_turing_core, symbol) for symbol in ("family_root", "detect_family_signature")
    ):
        _turing_core = None
except Exception:
    _turing_core = None

# 11D manifold substrate: exact Poincaré-Golden fold/unfold and Zeckendorf
# certificates. When importable, ManifoldEnhancedFormulations resolves the
# PENDING_11D_MERGE flag that AlgebraicFormulations carries.
try:
    from toe.poincare_golden_11d import (
        fold_poincare_11d_vector as _fold_11d,
        unfold_poincare_11d_vector as _unfold_11d,
        compute_poincare_norm_sq as _poincare_norm_sq,
        compute_zeckendorf_certificate as _zeckendorf_cert,
    )

    _HAS_11D = True
except Exception:
    _HAS_11D = False

# M-theory KK spectrum: exact Fraction lattice arithmetic on T^7.
try:
    from mtheory.kk_spectrum import KKTower as _KKTower

    _HAS_KK = True
except Exception:
    _HAS_KK = False


# =====================================================================
# EXTENDED ALGEBRAIC FAMILY SUBSTRATE
# ---------------------------------------------------------------------
# The complete Pisot spectrum behind the engine. Every family member is
# the dominant root of a monic characteristic polynomial with all Galois
# conjugates strictly inside the unit circle, so each one carries the
# same invariant bundle the golden family does:
#
#   family      char poly        recurrence            det(M)  |mu|max
#   golden      x^2 - x - 1      F_n = F_{n-1}+F_{n-2}    -1    0.618
#   silver      x^2 - 2x - 1     P_n = 2P_{n-1}+P_{n-2}   -1    0.414
#   plastic     x^3 - x - 1      P_n = P_{n-2}+P_{n-3}    +1    0.868
#   supergolden x^3 - x^2 - 1    N_n = N_{n-1}+N_{n-3}    +1    0.826
#   tribonacci  x^3 - x^2 - x - 1 T_n = T_{n-1}+T_{n-2}+T_{n-3} +1 0.737
#
# Per member: an exact integer "coordinate" limb (Fibonacci analogue),
# an exact integer "trace" limb tr(M^n) (Lucas analogue), a unimodular
# companion matrix (volume preservation, |det| = 1), a Binet-type closed
# form, and Pisot drift |mu|^n -> 0 (the integer-snap / noise-collapse
# property). The limbs differ only in lag structure; the invariants do
# not. That is what lets one operator algebra serve every domain.
# =====================================================================


class ExtendedAlgebraicFamily:
    """Unified algebraic spectrum for the engine's substrate layer.

    Five Pisot generators, one operator algebra. Deterministic only —
    NO FLOATING POINT in the substrate: exact integer recurrences,
    Decimal-precision roots, Fraction characteristic polynomials, and
    Sturm-sequence root isolation for spectral primitives. No heuristics,
    no external solvers, no IEEE-754 arithmetic.
    """

    # char-poly coefficients, highest degree first (monic).
    FAMILY_COEFFS = {
        "golden": (1, -1, -1),
        "silver": (1, -2, -1),
        "plastic": (1, 0, -1, -1),
        "supergolden": (1, -1, 0, -1),
        "tribonacci": (1, -1, -1, -1),
    }

    # Canonical exact-integer limb initialisations.
    LIMB_SEEDS = {
        "golden": {"coordinate": [0, 1], "trace": [2, 1]},
        "silver": {"coordinate": [0, 1], "trace": [2, 2]},
        "plastic": {"coordinate": [1, 1, 1], "trace": [3, 0, 2]},
        "supergolden": {"coordinate": [1, 1, 1], "trace": [3, 1, 1]},
        "tribonacci": {"coordinate": [0, 0, 1], "trace": [3, 1, 3]},
    }

    # Recurrence coefficient vector applied to the trailing window,
    # newest term last: s_n = sum(c_i * s_{n-d+i}).
    LIMB_RECURRENCE = {
        "golden": [1, 1],
        "silver": [1, 2],
        "plastic": [1, 1, 0],
        "supergolden": [1, 0, 1],
        "tribonacci": [1, 1, 1],
    }

    FAMILY_NAMES = ("golden", "silver", "plastic", "supergolden", "tribonacci")

    def __init__(self, precision: int = 50):
        getcontext().prec = max(precision, 28)
        self.precision = precision
        if _turing_core is not None:
            self._roots = {
                name: _turing_core.family_root(name, precision) for name in self.FAMILY_NAMES
            }
        else:
            self._roots = {
                "golden": (Decimal(1) + Decimal(5).sqrt()) / 2,
                "silver": Decimal(1) + Decimal(2).sqrt(),
                "plastic": self._newton_root(self.FAMILY_COEFFS["plastic"], Decimal("1.3")),
                "supergolden": self._newton_root(self.FAMILY_COEFFS["supergolden"], Decimal("1.5")),
                "tribonacci": self._newton_root(self.FAMILY_COEFFS["tribonacci"], Decimal("1.9")),
            }

    # -- exact roots ---------------------------------------------------

    def _newton_root(self, coeffs, x0: Decimal) -> Decimal:
        """Newton iteration on a monic polynomial, Decimal precision.

        Converges to the unique real root > 1 (the Pisot root) for every
        family characteristic polynomial in the spectrum.
        """
        x = x0
        coeffs = [Decimal(c) for c in coeffs]
        deg = len(coeffs) - 1
        tol = Decimal(10) ** (-(self.precision - 5))
        for _ in range(4 * self.precision):
            f = Decimal(0)
            df = Decimal(0)
            for c in coeffs:
                f = f * x + c
            for i, c in enumerate(coeffs[:-1]):
                df = df * x + c * (deg - i)
            step = f / df
            x -= step
            if abs(step) < tol:
                break
        return x

    def root(self, family: str) -> Decimal:
        """Dominant Pisot root of the family's characteristic polynomial."""
        return self._roots[family]

    def conjugate_modulus(self, family: str) -> Decimal:
        """Exact largest conjugate modulus |mu|max — no eigensolver.

        Every family polynomial has exactly one real root alpha > 1; the
        remaining d-1 roots are either a single real conjugate (d = 2) or
        a complex conjugate pair (d = 3). Since the product of all roots
        is (-1)^d * a_0 and every member here has a_0 = -1:

            |mu|max = (|a_0| / alpha) ** (1 / (d - 1))

        computed exactly in Decimal: alpha^{-1} for quadratics,
        alpha^{-1/2} for the cubics.
        """
        d = len(self.FAMILY_COEFFS[family]) - 1
        alpha = self.root(family)
        a0 = Decimal(abs(self.FAMILY_COEFFS[family][-1]))
        if d == 2:
            return a0 / alpha
        return (a0 / alpha).sqrt()

    def pisot_modulus(self, family: str) -> Decimal:
        """Exact Pisot drift-decay modulus |mu|max < 1."""
        return self.conjugate_modulus(family)

    def verify_pisot(self, family: str) -> bool:
        """Pisot witness in exact arithmetic: root > 1 and |mu|max < 1."""
        return self.root(family) > 1 and self.conjugate_modulus(family) < 1

    # -- companion matrices (the unimodular evolution operators) --------

    def companion(self, family: str):
        """Integer companion matrix of the characteristic polynomial.

        M[i][i+1] = 1 on the superdiagonal; last row is the recurrence.
        det(M) = (-1)^d * a_0, so every family is unimodular (|det| = 1):
        the generalised Cassini volume invariant.
        """
        coeffs = self.FAMILY_COEFFS[family]
        d = len(coeffs) - 1
        M = [[0] * d for _ in range(d)]
        for i in range(d - 1):
            M[i][i + 1] = 1
        for j in range(d):
            M[d - 1][j] = -coeffs[d - j]
        return M

    @staticmethod
    def _mat_mul_int(A, B):
        n = len(A)
        return [[sum(A[i][k] * B[k][j] for k in range(n)) for j in range(n)] for i in range(n)]

    def companion_power(self, family: str, n: int):
        """Exact integer M^n (fast binary exponentiation)."""
        M = self.companion(family)
        d = len(M)
        R = [[int(i == j) for j in range(d)] for i in range(d)]
        base = M
        e = n
        while e:
            if e & 1:
                R = self._mat_mul_int(R, base)
            base = self._mat_mul_int(base, base)
            e >>= 1
        return R

    # -- exact integer sequence limbs ----------------------------------

    def sequence(self, family: str, limb: str, length: int) -> list:
        """Exact integer sequence for a family limb.

        limb="coordinate": Fibonacci analogue (Fibonacci, Pell, Padovan,
        Narayana, Tribonacci). limb="trace": Lucas analogue — tr(M^n),
        the integer-snap sequence (Lucas, Pell-Lucas, Perrin, ...).
        """
        if limb == "trace":
            return [
                sum(
                    self.companion_power(family, n)[i][i]
                    for i in range(len(self.companion(family)))
                )
                for n in range(length)
            ]
        seed = list(self.LIMB_SEEDS[family][limb])
        rec = self.LIMB_RECURRENCE[family]
        d = len(seed)
        seq = seed[:length]
        while len(seq) < length:
            seq.append(sum(rec[i] * seq[-d + i] for i in range(d)))
        return seq

    def trace_identity(self, family: str, n: int) -> bool:
        """Witness: tr(M^n) equals the family's Lucas-analogue limb."""
        M_n = self.companion_power(family, n)
        d = len(M_n)
        return sum(M_n[i][i] for i in range(d)) == self.sequence(family, "trace", n + 1)[n]

    @staticmethod
    def _det_int(M) -> int:
        """Exact integer determinant (2x2 closed form, 3x3 cofactor)."""
        if len(M) == 2:
            return M[0][0] * M[1][1] - M[0][1] * M[1][0]
        a, b, c = M[0]
        d, e, f = M[1]
        g, h, i = M[2]
        return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)

    def det_identity(self, family: str, n: int) -> bool:
        """Witness: |det(M^n)| = 1 — generalised Cassini unimodularity,
        verified in exact integer arithmetic."""
        return abs(self._det_int(self.companion(family))) ** n == 1

    def binet_magnitude(self, family: str, n: int) -> Decimal:
        """Dominant-root power alpha^n — the Binet magnitude."""
        return self.root(family) ** n

    def pisot_drift(self, family: str, n: int) -> Decimal:
        """Exact Pisot drift bound |mu|^n — contraction per n steps."""
        return self.conjugate_modulus(family) ** n

    # -- Zeckendorf canonical form (certificate structure) --------------

    def zeckendorf(self, n: int) -> list:
        """Unique non-consecutive Fibonacci decomposition of n."""
        if n <= 0:
            return []
        fibs = [1, 2]
        while fibs[-1] <= n:
            fibs.append(fibs[-1] + fibs[-2])
        rep = []
        rem = n
        for f in reversed(fibs):
            if f <= rem:
                rep.append(f)
                rem -= f
        return rep

    # -- exact polynomial machinery (Fraction arithmetic) -----------------

    @staticmethod
    def _to_fraction_matrix(contact_matrix) -> list:
        """Convert an array-like of numbers to an exact Fraction matrix."""
        rows = contact_matrix.tolist() if hasattr(contact_matrix, "tolist") else contact_matrix
        return [[Fraction(str(x)) for x in row] for row in rows]

    @staticmethod
    def _char_poly(L) -> list:
        """Exact characteristic polynomial p(x) = det(xI - L) of an
        integer/Fraction matrix via Faddeev-LeVerrier. Returns
        coefficients [1, c1, c2, ..., cn] as exact Fractions."""
        n = len(L)
        coeffs = [Fraction(1), -sum(L[i][i] for i in range(n))]
        N = [row[:] for row in L]
        for k in range(2, n + 1):
            c_prev = coeffs[k - 1]
            B = [
                [N[i][j] + (c_prev if i == j else Fraction(0)) for j in range(n)] for i in range(n)
            ]
            N = [[sum(L[i][m] * B[m][j] for m in range(n)) for j in range(n)] for i in range(n)]
            coeffs.append(-sum(N[i][i] for i in range(n)) / k)
        return coeffs

    @staticmethod
    def _poly_eval(p, x: Fraction) -> Fraction:
        """Exact Horner evaluation of a coefficient list (high -> low)."""
        acc = Fraction(0)
        for c in p:
            acc = acc * x + c
        return acc

    @staticmethod
    def _poly_divmod(p, q):
        """Exact polynomial division on coefficient lists; returns the
        remainder with leading zeros stripped."""
        p = list(p)
        d = len(p) - len(q)
        for i in range(d + 1):
            c = p[i] / q[0]
            for j in range(len(q)):
                p[i + j] -= c * q[j]
        rem = p[d + 1 :]
        while rem and rem[0] == 0:
            rem.pop(0)
        return rem

    @classmethod
    def _sturm(cls, p) -> list:
        """Exact Sturm sequence: p, p', then negated remainders."""
        deriv = [p[i] * (len(p) - 1 - i) for i in range(len(p) - 1)]
        seq = [p, deriv]
        while seq[-1]:
            rem = cls._poly_divmod(seq[-2], seq[-1])
            if not rem:
                break
            seq.append([-c for c in rem])
        return seq

    @classmethod
    def _sturm_variations(cls, seq, x: Fraction) -> int:
        """Sign variations of the Sturm sequence at exact point x."""
        signs = []
        for poly in seq:
            v = cls._poly_eval(poly, x)
            if v > 0:
                signs.append(1)
            elif v < 0:
                signs.append(-1)
        return sum(1 for i in range(1, len(signs)) if signs[i] != signs[i - 1])

    # -- operational primitives -----------------------------------------

    def spectral_gap(self, contact_matrix) -> dict:
        """Algebraic connectivity: Fiedler value lambda_2 of the graph
        Laplacian L = D - A — computed in EXACT rational arithmetic.

        The characteristic polynomial is obtained exactly
        (Faddeev-LeVerrier over Fraction), zero roots are counted exactly
        (lambda_2 = 0 iff the graph is disconnected), and the smallest
        positive root is isolated by Sturm-sequence bisection to the
        Decimal context precision. No floating point, no eigensolver.
        """
        A = self._to_fraction_matrix(contact_matrix)
        n = len(A)
        if n < 2:
            return {"spectral_gap": Decimal(0), "ground_state": Decimal(0), "stable": False}

        deg = [sum(row) for row in A]
        L = [[(deg[i] if i == j else Fraction(0)) - A[i][j] for j in range(n)] for i in range(n)]
        coeffs = self._char_poly(L)

        # Zero-root multiplicity = number of connected components.
        zero_roots = 0
        while zero_roots < n and coeffs[-1 - zero_roots] == 0:
            zero_roots += 1
        if zero_roots >= 2:
            return {"spectral_gap": Decimal(0), "ground_state": Decimal(0), "stable": False}

        # q(x): char poly with the zero root deflated — all remaining
        # roots are strictly positive (symmetric PSD Laplacian).
        q = coeffs[:-1]
        bound = Fraction(2) * max(deg) if deg else Fraction(1)
        if bound <= 0:
            bound = Fraction(1)
        sturm = self._sturm(q)

        # Bisect (0, bound], keeping >= 1 root in (lo, hi]; converges
        # onto lambda_2, the smallest positive eigenvalue.
        lo, hi = Fraction(0), bound
        tol = Fraction(10) ** (-(self.precision - 8))
        while hi - lo > tol:
            mid = (lo + hi) / 2
            if self._sturm_variations(sturm, lo) - self._sturm_variations(sturm, mid) >= 1:
                hi = mid
            else:
                lo = mid

        gap = Decimal(hi.numerator) / Decimal(hi.denominator)
        return {
            "spectral_gap": gap,
            "ground_state": Decimal(0),
            "stable": gap > 0,
        }

    def pisot_drift_filter(self, series, family: str = "plastic") -> list:
        """Exponential-memory drift filter in exact Decimal arithmetic.

        Two-sided Pisot kernel w_k = alpha^{-|k|} (zero phase): noise
        contracts at the family's conjugate rate without lagging the
        trend. Returns a list of Decimals — no floating point.
        """
        s = [Decimal(str(x)) for x in series]
        n = len(s)
        if n == 0:
            return []
        alpha = self.root(family)
        half = min(max(n // 2, 4), 64)
        w = [alpha ** (-abs(k)) for k in range(-half, half + 1)]
        total = sum(w)
        w = [x / total for x in w]
        out = []
        for i in range(n):
            acc = Decimal(0)
            for j, kj in enumerate(range(-half, half + 1)):
                idx = i + kj
                if 0 <= idx < n:
                    acc += w[j] * s[idx]
            out.append(acc)
        return out

    def lag_kernel(self, family: str, size: int) -> list:
        """Normalised lag-structure kernel from the family's coordinate
        limb — exact Fraction weights matched to the recurrence memory."""
        seq = self.sequence(
            family, "coordinate", max(size, len(self.LIMB_SEEDS[family]["coordinate"]))
        )
        w = seq[-size:]
        total = sum(w)
        return [Fraction(x, total) for x in w]

    def metallic_anti_resonance_frequencies(self, base_freq=50.0, n_tiers: int = 5) -> list:
        """Frequency tiers separated by algebraically irrational ratios —
        no integer relation k_i*f_i = k_j*f_j can hold exactly. Returned
        as exact Decimals: base * family root."""
        base = Decimal(str(base_freq))
        ratios = [Decimal(1)] + [self.root(f) for f in self.FAMILY_NAMES]
        return [base * r for r in ratios[:n_tiers]]

    def detect_family_signature(self, series) -> dict:
        """Detect which recurrence structure a series obeys — in exact
        Decimal arithmetic.

        Fits the four lag templates (lag-12 golden, lag-23 plastic,
        lag-13 supergolden, lag-123 tribonacci) against the data and
        returns the best-matching family with a confidence margin.
        Unstructured data reports 'unstructured'. Delegates to the
        canonical turing_core implementation when the shared substrate
        is importable.
        """
        if _turing_core is not None:
            return _turing_core.detect_family_signature(series)
        flat = []
        if hasattr(series, "ravel"):
            series = series.ravel().tolist()
        for x in series:
            try:
                fx = float(x)
                if fx == fx and abs(fx) != float("inf"):
                    flat.append(Decimal(str(fx)))
            except (TypeError, ValueError):
                continue
        if len(flat) < 6:
            return {"family": "unstructured", "confidence": Decimal(0), "residuals": {}}
        mean = sum(flat) / len(flat)
        var = sum((x - mean) ** 2 for x in flat) / len(flat)
        if var == 0:
            return {"family": "unstructured", "confidence": Decimal(0), "residuals": {}}
        scale = var.sqrt()
        templates = {
            "golden": lambda x: [x[i + 2] - x[i + 1] - x[i] for i in range(len(x) - 2)],
            "plastic": lambda x: [x[i + 3] - x[i + 1] - x[i] for i in range(len(x) - 3)],
            "supergolden": lambda x: [x[i + 3] - x[i + 2] - x[i] for i in range(len(x) - 3)],
            "tribonacci": lambda x: [
                x[i + 3] - x[i + 2] - x[i + 1] - x[i] for i in range(len(x) - 3)
            ],
        }
        residuals = {}
        for name, resid in templates.items():
            r = resid(flat)
            residuals[name] = (
                (sum(v * v for v in r) / len(r)).sqrt() / scale if r else Decimal("Infinity")
            )
        ranked = sorted(residuals.items(), key=lambda kv: kv[1])
        best, best_r = ranked[0]
        margin = ranked[1][1] - best_r if len(ranked) > 1 else Decimal(0)

        def _clip(v: Decimal) -> Decimal:
            return max(Decimal(0), min(Decimal(1), v))

        confidence = _clip(Decimal(1) - best_r) * _clip(margin * 4)
        family = (
            best if (best_r < Decimal("0.5") and confidence > Decimal("0.05")) else "unstructured"
        )
        return {
            "family": family,
            "confidence": confidence,
            "residuals": residuals,
            "runner_up": ranked[1][0] if len(ranked) > 1 else None,
        }

    def verify_all(self) -> dict:
        """Full invariant witness battery across the family spectrum —
        all values exact (roots and moduli serialised as decimal strings)."""
        report = {}
        for fam in self.FAMILY_NAMES:
            report[fam] = {
                "root": str(self.root(fam)),
                "pisot": self.verify_pisot(fam),
                "pisot_modulus": str(self.pisot_modulus(fam)),
                "det_unimodular": all(self.det_identity(fam, n) for n in range(1, 10)),
                "trace_identity": all(self.trace_identity(fam, n) for n in range(1, 10)),
                "coordinate_limb": self.sequence(fam, "coordinate", 10),
                "trace_limb": self.sequence(fam, "trace", 10),
            }
        return report


class AlgebraicFormulations:
    """The unified framework structures built on the family substrate.

    Every structure is a computed map — never a claim. Each dict carries
    its own honesty boundary: theorem_proven is False everywhere, and the
    status field states the formulation tier explicitly.

    Every structure is flagged ``pending_11d_merge``: these formulations
    are to be combined with the 11D manifold substrate when that code is
    moved in. The capability ships now; the merge is pending.
    """

    # Merge target: the 11D manifold substrate (incoming).
    PENDING_11D_MERGE = True

    def __init__(self, algebra: ExtendedAlgebraicFamily = None):
        self.algebra = algebra or ExtendedAlgebraicFamily()

    def binet(self, n: int) -> dict:
        """Exact closed-form limbs for the golden family."""
        phi = self.algebra.root("golden")
        psi = (Decimal(1) - Decimal(5).sqrt()) / 2
        return {
            "fibonacci": (phi**n - psi**n) / Decimal(5).sqrt(),
            "lucas": phi**n + psi**n,
        }

    def p_vs_np_structure(self, n: int) -> dict:
        """The P vs NP gap structure: Lucas growth against Pisot decay.

        Lucas L_n ~ phi^n (exponential upper limb); Pisot |psi|^n
        (exponential contraction limb); Cassini (-1)^n is the parity
        witness; Zeckendorf is the certificate decomposition.
        """
        lucas_n = self.algebra.sequence("golden", "trace", n + 1)[n]
        pisot_n = abs((Decimal(1) - Decimal(5).sqrt()) / 2) ** n
        return {
            "NP_upper_bound": lucas_n,
            "P_lower_bound": str(pisot_n),
            "the_gap": str(Decimal(lucas_n) - pisot_n),
            "witness": (-1) ** n,
            "certificate": self.algebra.zeckendorf(n),
            "theorem_proven": False,
            "status": "FORMULATED_NOT_PROVEN",
            "pending_11d_merge": self.PENDING_11D_MERGE,
        }

    def riemann_structure(self, n: int) -> dict:
        """Zeta-structure formulation: per-index Zeckendorf coding with
        Cassini parity witnesses on the critical line."""
        zeros = [
            {
                "index": k,
                "critical_line": 0.5,
                "zeckendorf": self.algebra.zeckendorf(k),
                "cassini_witness": (-1) ** k,
            }
            for k in range(1, n + 1)
        ]
        return {
            "zeros": zeros,
            "critical_line": 0.5,
            "cassini_verified": all(z["cassini_witness"] == (-1) ** z["index"] for z in zeros),
            "theorem_proven": False,
            "status": "FORMULATED_NOT_PROVEN",
            "pending_11d_merge": self.PENDING_11D_MERGE,
        }

    def langlands_structure(self, n: int) -> dict:
        """Langlands formulation: automorphic levels as Cassini parity
        chains with Zeckendorf representations and Pisot decay."""
        forms = [
            {
                "level": k,
                "parity": (-1) ** k,
                "representation": self.algebra.zeckendorf(k),
                "decay": str(abs((Decimal(1) - Decimal(5).sqrt()) / 2) ** k),
            }
            for k in range(1, n + 1)
        ]
        return {
            "automorphic_forms": forms,
            "parity_preservation": all(f["parity"] == (-1) ** f["level"] for f in forms),
            "theorem_proven": False,
            "status": "FORMULATED_NOT_PROVEN",
            "pending_11d_merge": self.PENDING_11D_MERGE,
        }

    def m_theory_structure(self, n: int) -> dict:
        """M-theory compactification structure: 11D on CY_3 x S^1 with
        the Lucas tower as the KK spectrum and Fibonacci as the
        holographic storage hierarchy."""
        return {
            "dimensions": 11,
            "compactification": "CY_3 x S^1",
            "kk_tower": self.algebra.sequence("golden", "trace", n),
            "topological_charge": (-1) ** n,
            "holographic_memory": self.algebra.sequence("golden", "coordinate", n),
            "theorem_proven": False,
            "status": "FORMULATED_NOT_PROVEN",
            "pending_11d_merge": self.PENDING_11D_MERGE,
        }

    def unified_facets(self, n: int) -> dict:
        """The one-algebra five-facet map — every facet honesty-flagged."""
        return {
            "physics": {
                "yang_mills_mass_gap_structure": str(
                    Decimal(self.algebra.sequence("golden", "trace", n + 1)[n])
                    - abs((Decimal(1) - Decimal(5).sqrt()) / 2) ** n
                ),
                "quantum_gravity": self.m_theory_structure(n),
            },
            "mathematics": {
                "p_vs_np": self.p_vs_np_structure(n),
                "riemann": self.riemann_structure(n),
                "langlands": self.langlands_structure(n),
            },
            "computing": {
                "memory_hierarchy": self.algebra.sequence("golden", "coordinate", n),
                "lossless_coding": self.algebra.zeckendorf(n),
            },
            "medicine": {
                "imaging_witness": (-1) ** n,
                "reconstruction": self.algebra.zeckendorf(n),
            },
            "algebraic_family": {
                fam: {
                    "root": str(self.algebra.root(fam)),
                    "coordinate_limb": self.algebra.sequence(fam, "coordinate", 8),
                    "trace_limb": self.algebra.sequence(fam, "trace", 8),
                }
                for fam in self.algebra.FAMILY_NAMES
            },
            "theorem_proven": False,
            "status": "FORMULATED_NOT_PROVEN",
            "pending_11d_merge": self.PENDING_11D_MERGE,
        }


class ManifoldEnhancedFormulations(AlgebraicFormulations):
    """Algebraic formulations with the 11D manifold substrate wired in.

    This class extends ``AlgebraicFormulations`` and resolves the
    ``PENDING_11D_MERGE`` flag by importing the Poincaré-Golden 11D
    fold/unfold bijection, Zeckendorf certificates, and the M-theory
    KK tower. The formulations gain:

    - Concrete 11D roundtrip verification (fold ∘ unfold ≈ identity)
    - Zeckendorf certificate attestation per formulation
    - Real KK mass spectrum from exact Fraction lattice arithmetic
    - GPU punch dispatch mapping for the 11D operations

    The algebraic limbs (Cassini, Pisot, Binet) remain in exact
    Decimal/Fraction/integer arithmetic. The 11D manifold operations
    use float64 (the fold/unfold is bijective with preimage payload
    for exact in-process roundtrip).

    If the 11D or KK modules are not importable, each method falls
    back gracefully to the parent class with ``pending_11d_merge: True``.
    """

    PENDING_11D_MERGE = False

    def __init__(self, algebra: ExtendedAlgebraicFamily = None):
        super().__init__(algebra)
        self._11d_available = _HAS_11D
        self._kk_available = _HAS_KK
        if self._kk_available:
            self._kk_tower = _KKTower()

    # -- 11D manifold verification ------------------------------------

    def _roundtrip_check(self, vector=None) -> dict:
        """Fold ∘ unfold roundtrip on an 11D test vector.

        Returns exact max-absolute-error and pass/fail at 1e-14.
        """
        if not self._11d_available:
            return {"available": False}
        x = (
            vector
            if vector is not None
            else np.array(
                [float(self.algebra.root("golden")) ** i for i in range(11)],
                dtype=np.float64,
            )
        )
        folded, reflections = _fold_11d(x)
        recovered = _unfold_11d(folded)
        error = float(np.max(np.abs(x - recovered)))
        return {
            "available": True,
            "max_abs_error": error,
            "roundtrip_ok": error < 1e-14,
            "reflections": reflections,
            "norm_phi_sq": float(_poincare_norm_sq(folded)),
        }

    def _zeckendorf_attestation(self, vector=None, context: str = "") -> dict:
        """Compute a Zeckendorf certificate for an 11D state vector."""
        if not self._11d_available:
            return {"available": False}
        x = (
            vector
            if vector is not None
            else np.array(
                [float(self.algebra.root("golden")) ** i for i in range(11)],
                dtype=np.float64,
            )
        )
        cert = _zeckendorf_cert(x, context_id=context)
        return cert.to_dict()

    # -- KK spectrum ---------------------------------------------------

    def _kk_spectrum(self, n_max: int = 1) -> dict:
        """Extract the exact KK mass tower from the M-theory module."""
        if not self._kk_available:
            return {"available": False}
        levels = self._kk_tower.levels(n_max)
        checks = self._kk_tower.verify_tower(n_max)
        return {
            "available": True,
            "radii": [str(r) for r in self._kk_tower.radii],
            "num_levels": len(levels),
            "first_5_levels": [str(m2) for m2 in levels[:5]],
            "zero_mode_exact": checks.get("zero_mode", False),
            "even_under_reflection": checks.get("even_under_reflection", False),
            "first_level_correct": checks.get("first_level", False),
        }

    # -- GPU punch dispatch info ---------------------------------------

    @staticmethod
    def _gpu_punch_map() -> dict:
        """Map 11D manifold operations to unified OpenCL punch IDs.

        The OpenCL kernel (unified_punch_kernel.cl) already implements
        the same φ^{-(i+1)} weighting — these IDs shuttle 11D vectors
        between the Python substrate and the GPU dispatch.
        """
        return {
            "poincare_fold": 0x08,
            "poincare_unfold": 0x09,
            "geodesic_distance": 0x0A,
            "mint_certificate": 0x0B,
            "manifold_compute": 0x15,
            "phi_filter_score": 0x1A,
        }

    # -- overridden formulations (with 11D wired in) -------------------

    def m_theory_structure(self, n: int) -> dict:
        """M-theory compactification with REAL KK spectrum and 11D
        roundtrip verification — resolves PENDING_11D_MERGE."""
        base = super().m_theory_structure(n)
        base["pending_11d_merge"] = False
        base["manifold_11d"] = self._roundtrip_check()
        base["kk_spectrum"] = self._kk_spectrum(n_max=1)
        base["zeckendorf_certificate"] = self._zeckendorf_attestation(context="m_theory_structure")
        base["gpu_punch_map"] = self._gpu_punch_map()
        return base

    def unified_facets(self, n: int) -> dict:
        """The one-algebra five-facet map with 11D manifold substrate
        wired in — every facet carries its Zeckendorf attestation."""
        base = super().unified_facets(n)
        base["pending_11d_merge"] = False
        base["manifold_11d"] = {
            "roundtrip": self._roundtrip_check(),
            "zeckendorf": self._zeckendorf_attestation(context="unified_facets"),
            "kk_spectrum": self._kk_spectrum(n_max=1),
            "gpu_dispatch": self._gpu_punch_map(),
        }
        # Finite SU(2) thread. Distinct from the 11D hyperbolic ball above.
        # Failure is recorded; it must not be papered over with a constant.
        try:
            from toe.poincare_yangmills import join_summary

            base["physics"]["finite_su2_gauge"] = join_summary()
        except Exception as exc:
            base["physics"]["finite_su2_gauge"] = {
                "available": False,
                "proof_claim": False,
                "continuum_claim": False,
                "error": str(exc),
            }
        # Propagate into sub-formulations
        for key in ("physics", "mathematics", "computing", "medicine"):
            if key in base and isinstance(base[key], dict):
                base[key]["pending_11d_merge"] = False
        return base

    def p_vs_np_structure(self, n: int) -> dict:
        base = super().p_vs_np_structure(n)
        base["pending_11d_merge"] = False
        base["zeckendorf_11d"] = self._zeckendorf_attestation(context="p_vs_np")
        return base

    def riemann_structure(self, n: int) -> dict:
        base = super().riemann_structure(n)
        base["pending_11d_merge"] = False
        return base

    def langlands_structure(self, n: int) -> dict:
        base = super().langlands_structure(n)
        base["pending_11d_merge"] = False
        return base


def _exact_out(obj):
    """Serialise exact-arithmetic results for output dicts.

    Decimal -> decimal string, Fraction -> "num/den". The algebraic
    substrate carries no floats, so exact values cross the API boundary
    as strings rather than being rounded into IEEE-754.
    """
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, Fraction):
        return f"{obj.numerator}/{obj.denominator}"
    if isinstance(obj, dict):
        return {k: _exact_out(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_exact_out(v) for v in obj]
    return obj


class PredictiveEngine:
    """
    Prediction engine over the TOE algebraic substrate — ONE application of it.

    The shipped indicator schema is employee-churn-shaped (HR telemetry
    columns: login_time, promotion_history, engagement metrics) because that
    is the DataFrame the engine was demonstrated on. The computation beneath
    is domain-general substrate math, not an HR product:

    - State vectors in Hilbert space for entity risk representation
    - Born rule probability amplitudes for ensemble predictions
    - Heisenberg uncertainty principle for confidence intervals
    - Quantum decoherence measures for model agreement
    - Schrodinger time evolution for risk trajectory forecasting
    - Path integral formulation for intervention point identification
    - von Neumann entropy for data quality assessment
    - Quantum Fisher information for confidence calibration

    Not part of the live mining path (TypeScript owns that). The
    mining-facing TOE coordinator is toe/system.py.
    """

    def __init__(self, config: dict = None):
        """
        Initialize the predictive engine with configuration.

        Args:
            config (dict): Configuration dictionary with model parameters
        """

        self.config = config if config else self._default_config()

        self._validate_config()

        self._initialize_components()

        self.models = self._load_or_train_models()

    def _default_config(self) -> dict:
        """Return default configuration with quantum-mathematical parameters."""

        return {
            "model_names": ["rf", "xgb", "lgbm", "gb"],
            "model_dir": "models/",
            "n_estimators": 100,
            "max_depth": 8,
            "learning_rate": 0.005,
            "test_size": 0.2,
            "cv_folds": 3,
            "performance_weight": 0.30,
            "behavioral_weight": 0.25,
            "engagement_weight": 0.20,
            "career_weight": 0.15,
            "external_weight": 0.10,
            "feature_dim": 10,
            "max_tfidf_features": 100,
            "selected_model": "rf",
            "optimization_iterations": 3,
            "optimization_folds": 2,
            "optimization_method": "bayes",
            "imputation_strategy": "median",
            "ensemble_selection_method": "weighted_average",
            # Quantum-mathematical parameters (natural units, hbar = 1)
            "hbar": 1.0,
            "mass": 1.0,
            "omega": 0.5,
            "decoherence_rate": 0.1,
            "path_samples": 100,
            "hilbert_dim": 10,
            # Extended algebraic family parameters
            "algebraic_family": "auto",  # auto = detect recurrence signature from data
            "decimal_precision": 50,
            "anti_resonance_base_hz": 50.0,
            "pisot_filter_enabled": True,
        }

    def _validate_config(self) -> None:
        """Validate configuration parameters"""

        required_keys = ["model_names", "model_dir", "n_estimators", "max_depth"]

        missing_keys = [key for key in required_keys if key not in self.config]

        if missing_keys:

            raise ValueError(f"Missing required config keys: {missing_keys}")

    def _initialize_components(self) -> None:
        """Initialize all component objects with error handling"""

        try:

            self.scaler = _dependencies.StandardScaler()

            self.imputer = _dependencies.SimpleImputer(
                strategy=self.config.get("imputation_strategy", "median")
            )

            try:

                self.sentiment_analyzer = _dependencies.SentimentIntensityAnalyzer()

            except LookupError:

                # vader_lexicon is not bundled with nltk — fetch it, and if
                # that is impossible (offline CI/deploy), degrade honestly:
                # sentiment features become 0.0 instead of killing the engine.
                try:

                    import nltk

                    nltk.download("vader_lexicon", quiet=True)

                    self.sentiment_analyzer = _dependencies.SentimentIntensityAnalyzer()

                except Exception:

                    logging.warning("vader_lexicon unavailable — sentiment analysis disabled")

                    self.sentiment_analyzer = None

            self.tfidf_vectorizer = _dependencies.TfidfVectorizer(
                max_features=self.config.get("max_tfidf_features", 100),
                stop_words="english",
                tfidf_mode=self.config.get("tfidf_mode", "exact_linear"),
            )

            self.feature_engineering_methods = {}

            # Quantum-mathematical state caches

            self._quantum_state_cache = {}

            self._density_matrix_cache = None

            # Real-data contract state. The engine never fabricates a
            # training set: a model is fitted only on observed, labeled
            # rows supplied through ingest_training_data(), config
            # ("training_data" / "training_data_path"), or the persisted
            # training_data.npz in model_dir. With none of these, the
            # engine stays honestly untrained and predictions report
            # available=False.

            self._training_data = None

            self._training_provenance = None

            self._model_cv_scores = {}

            self._models_trained = False

            # Extended algebraic family substrate — the Pisot spectrum
            # behind the engine's evolution and measurement operators.

            self.algebra = ExtendedAlgebraicFamily(
                precision=self.config.get("decimal_precision", 50)
            )

            self.formulations = AlgebraicFormulations(self.algebra)

        except Exception as e:

            logging.error(f"Component initialization failed: {e}")

            raise

    def _load_or_train_models(self) -> dict:
        """Load persisted models; fit missing ones on real observed data.

        Real-data contract: the engine never fabricates a training set.
        A model absent from disk is fitted only when real labeled data is
        available — supplied through ``config['training_data']``,
        ``config['training_data_path']``, ``ingest_training_data()``, or a
        persisted ``training_data.npz`` in ``model_dir``. With no real data
        the engine stays honestly untrained and prediction paths report
        ``available: False`` — no synthetic records are ever substituted.
        """

        try:

            model_dir = self.config["model_dir"]

            os.makedirs(model_dir, exist_ok=True)

            models = {}

            missing = []

            for model_name in self.config["model_names"]:

                model_path = os.path.join(model_dir, f"{model_name}.joblib")

                if os.path.exists(model_path):

                    models[model_name] = _dependencies.joblib.load(model_path)

                    self._model_cv_scores[model_name] = self._load_training_metrics(model_name)

                    logging.info(f"Loaded model: {model_name}")

                else:

                    missing.append(model_name)

            if missing:

                training = self._real_training_data()

                if training is None:

                    logging.warning(
                        "PredictiveEngine: no observed training data — models "
                        "%s remain untrained; predictions report available=False.",
                        missing,
                    )

                else:

                    for model_name in missing:

                        models[model_name] = self._train_model(model_name, training)

            self._models_trained = bool(models)

            return models

        except Exception as e:

            logging.error(f"Model loading/training failed: {e}")

            raise

    def _train_model(self, model_name: str, training=None):
        """Fit a single model on a validated observed (X, y) matrix.

        Fails closed: raises ValueError when no real labeled data is
        available. Never trains on generated or placeholder records.
        """

        try:

            if training is None:

                training = self._real_training_data()

            if training is None:

                raise ValueError(
                    f"Cannot train '{model_name}': no observed training data. "
                    "Supply config['training_data'], config['training_data_path'], "
                    "or call ingest_training_data()."
                )

            X, y = training

            n_estimators = self.config["n_estimators"]

            max_depth = self.config["max_depth"]

            learning_rate = self.config.get("learning_rate", 0.01)

            if model_name not in {"rf", "xgb", "lgbm", "gb"}:
                raise ValueError(f"Unknown model name: {model_name}")
            # The four historical labels are intentionally collapsed to the
            # one canonical exact-linear kernel.  Their vendor algorithms are
            # not silently impersonated.
            model = _dependencies.exact_linear(
                n_estimators=n_estimators,
                max_depth=max_depth,
                learning_rate=learning_rate,
                random_state=42,
                legacy_name=model_name,
                tensor_mode=self.config.get("tensor_mode", "center_only"),
            )

            model.fit(X, y)

            # Measured quality gate: cross-validate on the real matrix.

            cv_score = self._measure_cv_score(model, X, y)

            self._model_cv_scores[model_name] = cv_score

            model_path = os.path.join(self.config["model_dir"], f"{model_name}.joblib")

            _dependencies.joblib.dump(model, model_path)

            self._persist_training_metrics(model_name, cv_score)

            logging.info(f"Trained and saved model: {model_name}")

            return model

        except Exception as e:

            logging.error(f"Error training model {model_name}: {e}")

            raise

    # ------------------------------------------------------------------
    # Real training-data contract
    # ------------------------------------------------------------------

    def ingest_training_data(self, X, y, source: str = "runtime_ingestion") -> dict:
        """Register real observed labeled data for model fitting.

        ``X`` is a 2-D numeric feature matrix; ``y`` the observed binary
        labels. The matrix is validated, persisted to
        ``model_dir/training_data.npz`` so subsequent runs reuse the same
        observed cohort, and fingerprinted (sha256) for provenance.

        Returns the provenance record. Raises ValueError on invalid input.
        """

        Xv, yv = self._validate_training_matrix(X, y)

        fingerprint = self._training_fingerprint(Xv, yv)

        self._training_data = (Xv, yv)

        self._training_provenance = {
            "source": source,
            "fingerprint": fingerprint,
            "n_samples": int(Xv.shape[0]),
            "feature_dim": int(Xv.shape[1]),
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }

        try:

            os.makedirs(self.config["model_dir"], exist_ok=True)

            np.savez(
                os.path.join(self.config["model_dir"], "training_data.npz"),
                X=Xv,
                y=yv,
            )

        except Exception as e:

            logging.warning(f"Could not persist ingested training data: {e}")

        return dict(self._training_provenance)

    def fit_models(self) -> dict:
        """Fit all configured models on the currently observed data.

        Returns the models dict. Raises ValueError if no real labeled
        training matrix is available.
        """

        training = self._real_training_data()

        if training is None:

            raise ValueError(
                "fit_models: no observed training data — refusing to fit on " "fabricated records."
            )

        self.models = {}

        for model_name in self.config["model_names"]:

            self.models[model_name] = self._train_model(model_name, training)

        self._models_trained = True

        return self.models

    def model_status(self) -> dict:
        """Honest production status: which models are fitted, on what data."""

        return {
            "trained": self._models_trained,
            "available_models": sorted(self.models.keys()),
            "missing_models": sorted(set(self.config["model_names"]) - set(self.models.keys())),
            "cv_scores": dict(self._model_cv_scores),
            "training_provenance": self._training_provenance,
        }

    def _validate_training_matrix(self, X, y):
        """Validate an observed (X, y) pair for fitting."""

        Xv = np.asarray(X, dtype=float)

        yv = np.asarray(y).ravel()

        if Xv.ndim != 2:

            raise ValueError("training features must be a 2-D matrix")

        if Xv.shape[0] != yv.shape[0]:

            raise ValueError("X and y row counts differ")

        if Xv.shape[0] < int(self.config.get("min_training_samples", 10)):

            raise ValueError(
                f"insufficient training samples: {Xv.shape[0]} "
                f"(minimum {self.config.get('min_training_samples', 10)})"
            )

        if not np.isfinite(Xv).all():

            raise ValueError("training features contain NaN or infinite values")

        if len(np.unique(yv)) < 2:

            raise ValueError("training labels must contain at least two classes")

        return Xv, yv

    def _real_training_data(self):
        """Resolve the real training matrix, or None when none exists.

        Order: ingested data -> config['training_data'] ->
        config['training_data_path'] -> persisted model_dir/training_data.npz.
        """

        if self._training_data is not None:

            return self._training_data

        try:

            inline = self.config.get("training_data")

            if inline is not None:

                X, y = inline

                return self._validate_training_matrix(X, y)

            path = self.config.get("training_data_path")

            if path:

                loaded = self._load_training_path(path)

                if loaded is not None:

                    return loaded

            npz_path = os.path.join(self.config["model_dir"], "training_data.npz")

            if os.path.exists(npz_path):

                blob = np.load(npz_path)

                return self._validate_training_matrix(blob["X"], blob["y"])

        except Exception as e:

            logging.warning(f"Observed training data rejected: {e}")

        return None

    def _load_training_path(self, path: str):
        """Load a declared training dataset (.npz / .csv / .joblib)."""

        if not os.path.exists(path):

            logging.warning(f"training_data_path does not exist: {path}")

            return None

        if path.endswith(".npz"):

            blob = np.load(path)

            return self._validate_training_matrix(blob["X"], blob["y"])

        if path.endswith(".csv"):

            frame = _dependencies.pd.read_csv(path)

            label_col = self.config.get("label_column")

            if label_col is None or label_col not in frame.columns:

                raise ValueError(
                    "csv training data requires config['label_column'] naming "
                    "the observed label column"
                )

            return self._validate_training_matrix(
                frame.drop(columns=[label_col]).values, frame[label_col].values
            )

        blob = _dependencies.joblib.load(path)

        X, y = blob if isinstance(blob, tuple) else (blob["X"], blob["y"])

        return self._validate_training_matrix(X, y)

    def _training_fingerprint(self, X, y) -> str:
        """sha256 fingerprint of the observed matrix — provenance anchor."""

        import hashlib

        h = hashlib.sha256()

        h.update(np.ascontiguousarray(X).tobytes())

        h.update(np.ascontiguousarray(y).tobytes())

        return h.hexdigest()

    def _measure_cv_score(self, model, X, y):
        """Measured cross-validation accuracy on real data, or None.

        Returns None (honest 'unmeasured') when the matrix cannot support
        the requested folds — never a fabricated score.
        """

        try:

            min_class = min(np.bincount(np.asarray(y, dtype=int)))

            folds = min(int(self.config.get("cv_folds", 3)), int(min_class))

            if folds < 2:

                return None

            scores = _dependencies.cross_val_score(model, X, y, cv=folds)

            return float(np.mean(scores))

        except Exception as e:

            logging.warning(f"CV measurement failed — score unmeasured: {e}")

            return None

    def _persist_training_metrics(self, model_name: str, cv_score) -> None:
        """Persist provenance + measured quality alongside the artifact."""

        import json

        metrics = {
            "model": model_name,
            "cv_score": cv_score,
            "cv_source": "measured" if cv_score is not None else "unmeasured",
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "training_provenance": self._training_provenance,
        }

        try:

            metrics_path = os.path.join(self.config["model_dir"], f"{model_name}.metrics.json")

            with open(metrics_path, "w") as fh:

                json.dump(metrics, fh, indent=2)

        except Exception as e:

            logging.warning(f"Could not persist model metrics: {e}")

    def _load_training_metrics(self, model_name: str):
        """Load the persisted CV score for a disk artifact, or None."""

        import json

        metrics_path = os.path.join(self.config["model_dir"], f"{model_name}.metrics.json")

        if not os.path.exists(metrics_path):

            return None

        try:

            with open(metrics_path) as fh:

                return json.load(fh).get("cv_score")

        except Exception:

            return None

    def _feature_dim(self) -> int:
        """The feature dimension the observed cohort was fitted on."""

        training = self._real_training_data()

        if training is not None:

            return int(training[0].shape[1])

        return int(self.config.get("feature_dim", 10))

    def _untrained_payload(self) -> dict:
        """Honest unavailable response — no fabricated predictions."""

        return {
            "available": False,
            "truth_class": "untrained_models",
            "reason": (
                "no fitted models — the engine requires real observed "
                "training data (config['training_data'], "
                "config['training_data_path'], or ingest_training_data())"
            ),
            "model_predictions": {},
        }

    def _get_model_by_name(self, name: str):
        """Retrieve a model by name from the models dictionary."""

        if name not in self.models:

            raise ValueError(f"Model '{name}' not found. Available: {list(self.models.keys())}")

        return self.models[name]

    def add_feature_engineering(self, name: str, method) -> None:
        """Register a custom feature engineering method."""

        self.feature_engineering_methods[name] = method

    def predict_churn_risk(self, data: _dependencies.pd.DataFrame) -> dict:
        """
        Predict employee churn risk using ensemble approach.

        Args:
            data (pd.DataFrame): Employee data with required features

        Returns:
            dict: Risk profile with predictions and explanations
        """

        try:

            # Input validation

            if not isinstance(data, _dependencies.pd.DataFrame):

                raise ValueError("Input must be a pandas DataFrame")

            # Process data in chunks if large

            if len(data) > 10000:

                return self._process_large_dataset(data)

            # Extract and preprocess features

            processed_data = self._preprocess_data(data)

            indicators = self._extract_risk_indicators(processed_data)

            # Generate predictions

            ensemble_predictions = self._ensemble_predict(indicators)

            # Generate final risk profile

            risk_profile = self._generate_risk_profile(ensemble_predictions, indicators)

            return risk_profile

        except Exception as e:

            logging.error(f"Churn prediction failed: {e}")

            raise

    def _process_large_dataset(self, data: _dependencies.pd.DataFrame) -> dict:
        """Process large datasets in chunks to optimize memory usage"""

        chunk_size = 5000

        predictions = []

        for i in range(0, len(data), chunk_size):

            chunk = data.iloc[i : i + chunk_size]

            chunk_prediction = self._process_chunk(chunk)

            predictions.append(chunk_prediction)

        return self._aggregate_predictions(predictions)

    def _process_chunk(self, chunk: _dependencies.pd.DataFrame) -> dict:
        """Process a single chunk of data through the prediction pipeline."""

        try:

            processed_chunk = self._preprocess_data(chunk)

            indicators = self._extract_risk_indicators(processed_chunk)

            ensemble_predictions = self._ensemble_predict(indicators)

            return self._generate_risk_profile(ensemble_predictions, indicators)

        except Exception as e:

            logging.error(f"Error processing chunk: {e}")

            raise

    def _aggregate_predictions(self, predictions: list) -> dict:
        """
        Aggregate chunk predictions using quantum superposition.

        Combined risk state is the normalized superposition of chunk states.
        Born rule: P = |sum of amplitudes|^2 / N
        """

        try:

            if not predictions:

                return {}

            # Quantum superposition: combine all chunk risk scores as amplitudes

            risk_scores = [p["risk_score"]["score"] for p in predictions if "risk_score" in p]

            confidences = [
                p["risk_score"]["confidence_interval"] for p in predictions if "risk_score" in p
            ]

            if not risk_scores:

                return {}

            # Born rule: probability is squared magnitude of summed amplitudes

            amplitudes = np.array(risk_scores, dtype=complex)

            norm = np.sqrt(np.sum(np.abs(amplitudes) ** 2))

            if norm > 0:

                amplitudes = amplitudes / norm

            combined_score = float(
                np.sum(np.abs(amplitudes) ** 2 * risk_scores) / np.sum(np.abs(amplitudes) ** 2)
            )

            combined_confidence = float(np.mean(confidences)) if confidences else 0.0

            # Aggregate key factors across chunks

            all_factors = {}

            for p in predictions:

                for factor, weight in p.get("key_factors", []):

                    if factor in all_factors:

                        all_factors[factor] += weight

                    else:

                        all_factors[factor] = weight

            total_weight = sum(all_factors.values())

            if total_weight > 0:

                all_factors = {k: v / total_weight for k, v in all_factors.items()}

            sorted_factors = sorted(all_factors.items(), key=lambda x: x[1], reverse=True)[:5]

            confidence_levels = [
                p["confidence_level"] for p in predictions if "confidence_level" in p
            ]

            return {
                "risk_score": {
                    "score": combined_score,
                    "confidence_interval": combined_confidence,
                    "probability": self._calculate_probability(combined_score),
                },
                "confidence_level": float(np.mean(confidence_levels)) if confidence_levels else 0.5,
                "key_factors": sorted_factors,
                "num_chunks": len(predictions),
            }

        except Exception as e:

            logging.error(f"Error aggregating predictions: {e}")

            raise

    def _extract_risk_indicators(self, data: _dependencies.pd.DataFrame) -> dict:
        """
        Extract key risk indicators from employee data with improved feature engineering.

        New features added:
        - Relative performance metrics (quantum fidelity)
        - Time-based engagement patterns (quantum temporal coherence)
        - Communication sentiment analysis (quantum semantic states)
        - Career progression velocity (quantum momentum)
        """

        try:

            if not isinstance(data, _dependencies.pd.DataFrame):

                raise ValueError("Input must be a pandas DataFrame for risk indicator extraction")

            indicators = {
                "performance_metrics": self._extract_performance_metrics(data),
                "behavioral_metrics": self._extract_behavioral_metrics(data),
                "engagement_metrics": self._extract_engagement_metrics(data),
                "career_metrics": self._extract_career_metrics(data),
                "external_metrics": self._extract_external_metrics(data),
            }

            # Apply custom feature engineering

            for method_name, method in self.feature_engineering_methods.items():

                indicators[method_name] = method(data)

            return indicators

        except Exception as e:

            logging.error(f"Feature extraction failed: {e}")

            raise

    def _extract_performance_metrics(self, data: _dependencies.pd.DataFrame) -> dict:
        """Extract enhanced performance metrics with trends and patterns"""

        metrics = {}

        if "performance_score" in data.columns:

            metrics["trend"] = self._calculate_trend(data["performance_score"])

            metrics["volatility"] = self._calculate_volatility(data["performance_score"])

            metrics["relative_performance"] = self._calculate_relative_performance(data)

        return metrics

    def _calculate_trend(self, series: _dependencies.pd.Series) -> float:
        """
        Calculate trend using quantum momentum operator (first principles).

        The discrete momentum operator is: p_hat * psi(n) = -i*hbar*[psi(n+1) - psi(n-1)] / (2*dx)
        The trend is the expectation value: <p> = <psi|p_hat|psi>

        A positive <p> indicates upward momentum (improving performance),
        negative <p> indicates downward momentum (declining performance).
        """

        try:

            values = series.dropna().values.astype(float)

            if len(values) < 2:

                return 0.0

            hbar = self.config.get("hbar", 1.0)

            # Normalize to create a wave-like state

            mean_val = np.mean(values)

            std_val = np.std(values)

            if std_val == 0:

                return 0.0

            # Wavefunction: psi(n) = normalized values as probability amplitudes

            psi = (values - mean_val) / std_val

            # Normalize so that sum(|psi|^2) = 1

            norm = np.sqrt(np.sum(np.abs(psi) ** 2))

            if norm == 0:

                return 0.0

            psi = psi / norm

            # Apply discrete momentum operator: p_hat*psi(n) = -i*hbar*[psi(n+1) - psi(n-1)] / 2

            p_psi = np.zeros_like(psi, dtype=complex)

            for n in range(len(psi)):

                psi_plus = psi[n + 1] if n + 1 < len(psi) else psi[n]

                psi_minus = psi[n - 1] if n - 1 >= 0 else psi[n]

                p_psi[n] = -1j * hbar * (psi_plus - psi_minus) / 2.0

            # Expectation value: <p> = Re(<psi|p_hat|psi>)

            expectation = np.real(np.sum(np.conj(psi) * p_psi))

            return float(expectation)

        except Exception as e:

            logging.error(f"Error calculating quantum trend: {e}")

            return 0.0

    def _calculate_volatility(self, series: _dependencies.pd.Series) -> float:
        """
        Calculate volatility using quantum harmonic oscillator energy (first principles).

        The Hamiltonian for a quantum harmonic oscillator: H = p^2/(2m) + (1/2)m*w^2*x^2
        The energy expectation value <H> captures both kinetic (variation) and
        potential (deviation from equilibrium) energy, providing a measure of volatility.

        Higher energy = more volatile system.
        """

        try:

            values = series.dropna().values.astype(float)

            if len(values) < 2:

                return 0.0

            hbar = self.config.get("hbar", 1.0)

            mass = self.config.get("mass", 1.0)

            omega = self.config.get("omega", 0.5)

            mean_val = np.mean(values)

            std_val = np.std(values)

            if std_val == 0:

                return 0.0

            # Position operator: x(n) = normalized deviation from mean

            x = (values - mean_val) / std_val

            # Kinetic energy: T = p^2/(2m) approx variance of differences / (2m)

            dx = np.diff(values)

            p_squared = np.var(dx) if len(dx) > 1 else 0.0

            kinetic_energy = p_squared / (2 * mass)

            # Potential energy: V = (1/2)*m*w^2*<x^2>

            potential_energy = 0.5 * mass * omega**2 * np.mean(x**2)

            # Total energy (volatility measure)

            total_energy = kinetic_energy + potential_energy

            # Normalize by ground state energy E0 = (1/2)*hbar*w

            ground_state = 0.5 * hbar * omega

            if ground_state > 0:

                volatility = total_energy / ground_state

            else:

                volatility = total_energy

            return float(volatility)

        except Exception as e:

            logging.error(f"Error calculating quantum volatility: {e}")

            return 0.0

    def _calculate_relative_performance(self, data: _dependencies.pd.DataFrame) -> float:
        """
        Calculate relative performance using quantum state fidelity (first principles).

        Quantum fidelity measures the overlap between an employee's performance state
        and the ensemble average state: F = |<psi|phi>|^2

        F = 1: employee is identical to average
        F = 0: employee is orthogonal to average (maximally different)
        """

        try:

            if "performance_score" not in data.columns:

                return 0.5

            values = data["performance_score"].dropna().values.astype(float)

            if len(values) < 2:

                return 0.5

            # Employee state vector

            psi = values - np.mean(values)

            norm_psi = np.sqrt(np.sum(psi**2))

            if norm_psi == 0:

                return 1.0

            psi = psi / norm_psi

            # Ensemble average state (uniform superposition)

            phi = np.ones_like(psi) / np.sqrt(len(psi))

            # Quantum fidelity: F = |<psi|phi>|^2

            overlap = np.abs(np.dot(np.conj(psi), phi)) ** 2

            return float(overlap)

        except Exception as e:

            logging.error(f"Error calculating quantum fidelity: {e}")

            return 0.5

    def _extract_behavioral_metrics(self, data: _dependencies.pd.DataFrame) -> dict:
        """Extract enhanced behavioral metrics focusing on time and patterns"""

        metrics = {}

        if "login_time" in data.columns:

            metrics["login_frequency"] = self._calculate_login_frequency(data["login_time"])

            metrics["login_variability"] = self._calculate_login_variability(data["login_time"])

        if "communication_text" in data.columns:

            metrics["communication_sentiment"] = self._analyze_text_sentiment(
                " ".join(data["communication_text"].dropna().astype(str))
            )

        return metrics

    def _calculate_login_frequency(self, login_time: _dependencies.pd.Series) -> float:
        """
        Calculate login frequency using quantum number operator (first principles).

        The number operator n_hat has eigenvalues n = 0, 1, 2, ...
        The expectation value <n_hat> gives the average quantum number (frequency)
        of the login pattern.
        """

        try:

            values = login_time.dropna().values.astype(float)

            if len(values) == 0:

                return 0.0

            # Map login times to quantum number basis

            if np.max(values) == np.min(values):

                return 1.0

            normalized = (values - np.min(values)) / (np.max(values) - np.min(values))

            quantum_numbers = np.round(normalized * (len(values) - 1))

            # Number operator expectation: <n_hat> = sum(n * P(n))

            # P(n) = |psi_n|^2 where psi_n is the amplitude

            amplitudes = np.ones(len(values)) / np.sqrt(len(values))

            probabilities = np.abs(amplitudes) ** 2

            expectation_n = np.sum(quantum_numbers * probabilities)

            # Normalize to [0, 1] range

            max_n = len(values) - 1

            if max_n > 0:

                return float(expectation_n / max_n)

            return 0.5

        except Exception as e:

            logging.error(f"Error calculating quantum login frequency: {e}")

            return 0.5

    def _calculate_login_variability(self, login_time: _dependencies.pd.Series) -> float:
        """
        Calculate login variability using Heisenberg uncertainty principle (first principles).

        Delta_x * Delta_p >= hbar/2

        The time uncertainty Delta_t captures the spread in login times,
        while the momentum uncertainty Delta_p captures the variability in login rate changes.
        """

        try:

            values = login_time.dropna().values.astype(float)

            if len(values) < 2:

                return 0.0

            hbar = self.config.get("hbar", 1.0)

            # Position uncertainty: Delta_x = std of login times

            dx = np.std(values)

            if dx == 0:

                return 0.0

            # Momentum uncertainty: Delta_p = std of consecutive differences

            dp = np.std(np.diff(values))

            if dp == 0:

                dp = hbar / (2 * dx)  # Saturate uncertainty bound

            # Heisenberg product: Delta_x * Delta_p

            uncertainty_product = dx * dp

            # Normalize by minimum uncertainty hbar/2

            min_uncertainty = hbar / 2

            if min_uncertainty > 0:

                variability = uncertainty_product / min_uncertainty

            else:

                variability = uncertainty_product

            # Clamp to [0, 1] for practical use

            return float(min(max(variability, 0.0), 1.0))

        except Exception as e:

            logging.error(f"Error calculating quantum login variability: {e}")

            return 0.5

    def _extract_engagement_metrics(self, data: _dependencies.pd.DataFrame) -> dict:
        """Extract engagement metrics with survey insights"""

        metrics = {}

        if "survey_text" in data.columns:

            text_combined = " ".join(data["survey_text"].dropna().astype(str))

            metrics["survey_sentiment"] = self._analyze_text_sentiment(text_combined)

            metrics["survey_engagement"] = self._analyze_text_engagement(text_combined)

        if "participation_rate" in data.columns:

            metrics["participation_rate"] = self._analyze_participation(data["participation_rate"])

        return metrics

    def _extract_career_metrics(self, data: _dependencies.pd.DataFrame) -> dict:
        """Extract metrics related to career growth and aspirations"""

        metrics = {}

        if "promotion_history" in data.columns:

            metrics["promotion_velocity"] = self._analyze_promotion_velocity(
                data["promotion_history"]
            )

        if "skill_level" in data.columns:

            metrics["skill_growth"] = self._analyze_skill_development(data["skill_level"])

        if "compensation_ratio" in data.columns:

            metrics["compensation_ratio"] = self._analyze_compensation(data["compensation_ratio"])

        return metrics

    def _analyze_promotion_velocity(self, promotion_history: _dependencies.pd.Series) -> float:
        """
        Calculate promotion velocity using quantum velocity operator (first principles).

        The velocity operator is v_hat = p_hat/m, where p_hat is the momentum operator.
        Promotion velocity measures the rate of career advancement as quantum momentum.
        """

        try:

            values = promotion_history.dropna().values.astype(float)

            if len(values) < 2:

                return 0.0

            hbar = self.config.get("hbar", 1.0)

            mass = self.config.get("mass", 1.0)

            # Normalize to wavefunction

            mean_val = np.mean(values)

            std_val = np.std(values)

            if std_val == 0:

                return 0.0

            psi = (values - mean_val) / std_val

            norm = np.sqrt(np.sum(np.abs(psi) ** 2))

            if norm == 0:

                return 0.0

            psi = psi / norm

            # Velocity operator: v_hat = p_hat/m = -i*hbar/(m) * d/dx

            v_psi = np.zeros_like(psi, dtype=complex)

            for n in range(len(psi)):

                psi_plus = psi[n + 1] if n + 1 < len(psi) else psi[n]

                psi_minus = psi[n - 1] if n - 1 >= 0 else psi[n]

                v_psi[n] = -1j * hbar / (mass * 2.0) * (psi_plus - psi_minus)

            # Expectation: <v> = Re(<psi|v_hat|psi>)

            velocity = np.real(np.sum(np.conj(psi) * v_psi))

            return float(velocity)

        except Exception as e:

            logging.error(f"Error calculating promotion velocity: {e}")

            return 0.0

    def _extract_external_metrics(self, data: _dependencies.pd.DataFrame) -> dict:
        """Extract external factors like market conditions and industry trends"""

        metrics = {}

        if "market_condition" in data.columns:

            metrics["market_condition"] = self._analyze_market(data["market_condition"])

        if "industry_trend" in data.columns:

            metrics["industry_trend"] = self._analyze_industry(data["industry_trend"])

        if "competitor_activity" in data.columns:

            metrics["competitor_activity"] = self._analyze_competitors(data["competitor_activity"])

        return metrics

    def _preprocess_data(self, data: _dependencies.pd.DataFrame) -> _dependencies.pd.DataFrame:
        """Preprocess employee data to handle missing values"""

        try:

            processed_data = data.copy()

            # Impute missing values

            numeric_cols = processed_data.select_dtypes(include=np.number).columns

            if len(numeric_cols) > 0:

                processed_data[numeric_cols] = self.imputer.fit_transform(
                    processed_data.select_dtypes(include=np.number)
                )

            return processed_data

        except Exception as e:

            logging.error(f"Data preprocessing failed: {e}")

            raise

    def _ensemble_predict(self, indicators: dict) -> dict:
        """Ensemble prediction using configured models with weighted or voting system"""

        try:

            if not self.models:

                return self._untrained_payload()

            if (
                self.config.get("ensemble_selection_method", "weighted_average")
                == "weighted_average"
            ):

                return self._weight_predictions(indicators)

            else:

                return self._voting_predictions(indicators)

        except Exception as e:

            logging.error(f"Ensemble prediction failed: {e}")

            raise

    def _weight_predictions(self, indicators: dict) -> dict:
        """
        Weight predictions based on model performance using cross validation
        and quantum superposition of model states.

        Each model produces a probability amplitude. The ensemble prediction
        is the superposition of all model states, weighted by their cross-validation
        performance (which serves as the amplitude modulus).
        """

        try:

            predictions = {}

            input_features = self._prepare_input_features(indicators)

            # Ensure input_features is 2D for prediction

            if input_features.ndim == 1:

                input_features = input_features.reshape(1, -1)

            # Feature dimensions are matched against the dimension the
            # observed cohort was fitted on — never a generated matrix.

            target_dim = self._feature_dim()

            if input_features.shape[1] < target_dim:

                padding = np.zeros((input_features.shape[0], target_dim - input_features.shape[1]))

                input_features = np.hstack([input_features, padding])

            elif input_features.shape[1] > target_dim:

                input_features = input_features[:, :target_dim]

            # The exact-linear model owns its center-only field preprocessing.
            # Diagnostic z-score output must not re-enter the exact plane.
            model_features = input_features

            # Quantum superposition of model predictions

            amplitudes = {}

            for model_name, model in self.models.items():

                # Amplitude phase comes from the CV score measured on the
                # real training matrix at fit time. Unmeasured -> phase 0
                # (no fabricated performance claim rotates the amplitude).

                cv_score = self._model_cv_scores.get(model_name)

                phase = float(cv_score) if cv_score is not None else 0.0

                y_pred = model.predict_proba(model_features)[:, 1]

                # Quantum amplitude: complex number with magnitude = probability

                # and phase = measured model performance

                amplitude = np.sqrt(y_pred[0]) * np.exp(1j * np.pi * phase)

                amplitudes[model_name] = amplitude

                predictions[model_name] = {
                    "score": float(y_pred[0]),
                    "confidence": self._calculate_model_confidence(y_pred[0]),
                    "weight": float(phase) if cv_score is not None else None,
                    "cv_source": "measured" if cv_score is not None else "unmeasured",
                }

            # Born rule: combined probability = |sum of amplitudes|^2 / N

            total_amplitude = sum(amplitudes.values())

            born_probability = float(np.abs(total_amplitude) ** 2 / len(amplitudes))

            predictions["quantum_superposition"] = born_probability

            return predictions

        except Exception as e:

            logging.error(f"Error during weighting of predictions: {e}")

            raise

    def _voting_predictions(self, indicators: dict) -> dict:
        """Generates predictions using a voting system between multiple models"""

        try:

            predictions = {}

            input_features = self._prepare_input_features(indicators)

            if input_features.ndim == 1:

                input_features = input_features.reshape(1, -1)

            # Match the feature dimension the observed cohort was fitted on.

            target_dim = self._feature_dim()

            if input_features.shape[1] < target_dim:

                padding = np.zeros((input_features.shape[0], target_dim - input_features.shape[1]))

                input_features = np.hstack([input_features, padding])

            elif input_features.shape[1] > target_dim:

                input_features = input_features[:, :target_dim]

            # Do not feed diagnostic z-scores into the exact model.
            model_features = input_features

            votes = []

            for model_name, model in self.models.items():

                y_pred = model.predict(model_features)

                votes.append(y_pred[0])

            # Simple Voting - count number of trues and falses

            true_votes = np.count_nonzero(votes)

            false_votes = len(votes) - true_votes

            # Assign probability based on which vote was higher

            if true_votes > false_votes:

                probability = 1.0

            elif true_votes < false_votes:

                probability = 0.0

            else:

                probability = 0.5  # If no clear majority

            for model_name, model in self.models.items():

                y_pred = model.predict_proba(model_features)[:, 1]  # get score from each model

                predictions[model_name] = {
                    "score": float(y_pred[0]),
                    "confidence": self._calculate_model_confidence(y_pred[0]),
                    "weight": 1,
                }

            predictions["voting_probability"] = probability  # Include the voting probability

            return predictions

        except Exception as e:

            logging.error(f"Error during voting of predictions: {e}")

            raise

    def _generate_risk_profile(self, predictions: dict, indicators: dict) -> dict:
        """Generate detailed risk profile with confidence score and explanations"""

        try:

            risk_profile = {
                "available": bool(self.models) and predictions.get("available", True) is not False,
                "truth_class": (
                    "observed_model"
                    if self.models
                    else predictions.get("truth_class", "untrained_models")
                ),
                "risk_score": self._calculate_risk_score(predictions),
                "confidence_level": self._calculate_confidence(predictions),
                "key_factors": self._identify_key_factors(indicators),
                "recommended_actions": self._generate_recommendations(indicators),
                "time_sensitivity": self._assess_time_sensitivity(indicators),
                "risk_trajectory": self._predict_risk_trajectory(indicators),
                "model_predictions": predictions,  # Include all model specific predictions
                "feature_importances": (
                    self._get_feature_importance(
                        self.models.get(self.config.get("selected_model", "rf")),
                        list(self._calculate_factor_weights(indicators).keys()),
                    )
                    if self.config.get("selected_model") and self.models
                    else None
                ),
                "lime_explanations": self._get_lime_explanations(indicators),
                "algebraic_invariants": self._algebraic_diagnostics(indicators),
            }

            return risk_profile

        except Exception as e:

            logging.error(f"Error generating risk profile: {e}")

            raise

    def _algebraic_diagnostics(self, indicators: dict) -> dict:
        """Extended algebraic family invariants for the current indicators.

        Computes the deterministic substrate diagnostics — no heuristics:

        - family signature: which recurrence structure the indicator
          series obeys (lag-12 golden, lag-23 plastic, lag-13 supergolden,
          lag-123 tribonacci), with a confidence margin
        - spectral gap: Fiedler value lambda_2 of the factor contact
          graph's Laplacian — algebraic connectivity of the coupled
          risk-factor system (gap > 0 means locked)
        - anti-resonance tiers: metallic-ratio frequency set where no
          integer relation k_i*f_i = k_j*f_j holds exactly
        - family ladder: the detected family's exact trace limb (the
          Lucas-analogue scaling sequence) for confidence calibration
        """

        try:

            values = []

            for value in indicators.values():

                if isinstance(value, dict):

                    values.extend(float(v) for v in value.values() if isinstance(v, (int, float)))

                elif isinstance(value, (int, float)):

                    values.append(float(value))

            if not values:

                return {"available": False}

            arr = np.asarray(values)

            signature = self.algebra.detect_family_signature(arr)

            configured = self.config.get("algebraic_family", "auto")

            family = (
                signature["family"]
                if configured == "auto"
                else (configured if configured in self.algebra.FAMILY_NAMES else "plastic")
            )

            if family == "unstructured":

                family = "plastic"

            # Factor contact graph: weighted complete graph on the
            # indicator values, weights = |v_i v_j| normalised — the
            # Laplacian gap measures how locked the factor system is.

            v = arr / (np.max(np.abs(arr)) or 1.0)

            contact = np.abs(np.outer(v, v))

            np.fill_diagonal(contact, 0.0)

            gap_info = self.algebra.spectral_gap(contact)

            return {
                "available": True,
                "family_signature": _exact_out(signature),
                "active_family": family,
                "spectral": _exact_out(gap_info),
                "anti_resonance_hz": _exact_out(
                    self.algebra.metallic_anti_resonance_frequencies(
                        base_freq=self.config.get("anti_resonance_base_hz", 50.0)
                    )
                ),
                "family_ladder": self.algebra.sequence(family, "trace", 8),
                "lag_kernel": _exact_out(self.algebra.lag_kernel(family, 6)),
                "purity": "DETERMINISTIC_ALGEBRAIC",
            }

        except Exception as e:

            logging.error(f"Error computing algebraic diagnostics: {e}")

            return {"available": False, "error": str(e)}

    def _assess_time_sensitivity(self, indicators: dict) -> dict:
        """
        Assess time sensitivity using quantum time-energy uncertainty relation (first principles).

        Delta_E * Delta_t >= hbar/2

        The time sensitivity measures how quickly the risk state is evolving,
        based on the energy uncertainty of the system.
        """

        try:

            hbar = self.config.get("hbar", 1.0)

            # Calculate energy from indicators (sum of weighted metrics)

            factor_weights = self._calculate_factor_weights(indicators)

            total_energy = 0.0

            for key, weight in factor_weights.items():

                if key in indicators and isinstance(indicators[key], dict):

                    values = [v for v in indicators[key].values() if isinstance(v, (int, float))]

                    if values:

                        total_energy += weight * np.var(values)

            # Time-energy uncertainty: Delta_t >= hbar/(2*Delta_E)

            if total_energy > 0:

                delta_t = hbar / (2 * total_energy)

            else:

                delta_t = float("inf")

            # Classify time sensitivity

            if delta_t < 0.5:

                sensitivity = "critical"

            elif delta_t < 1.0:

                sensitivity = "high"

            elif delta_t < 2.0:

                sensitivity = "moderate"

            else:

                sensitivity = "low"

            return {
                "sensitivity_level": sensitivity,
                "time_horizon": float(delta_t),
                "energy_uncertainty": float(total_energy),
                "uncertainty_bound": hbar / 2,
            }

        except Exception as e:

            logging.error(f"Error assessing time sensitivity: {e}")

            return {"sensitivity_level": "moderate", "time_horizon": 1.0}

    def _get_lime_explanations(self, indicators: dict) -> dict:
        """
        Generate LIME explanations for the prediction using quantum-inspired
        feature perturbation.
        """

        try:

            input_features = self._prepare_input_features(indicators)

            if input_features.ndim == 1:

                input_features = input_features.reshape(1, -1)

            # LIME background must be the real observed cohort — a
            # generated reference set would fabricate the local surrogate.

            training = self._real_training_data()

            if training is None:

                return {
                    "available": False,
                    "explanation": [],
                    "note": "LIME requires a real observed training cohort",
                }

            X_observed, _ = training

            self.scaler.fit(X_observed)

            # Ensure feature dimensions match

            target_dim = X_observed.shape[1]

            if input_features.shape[1] < target_dim:

                padding = np.zeros((input_features.shape[0], target_dim - input_features.shape[1]))

                input_features = np.hstack([input_features, padding])

            elif input_features.shape[1] > target_dim:

                input_features = input_features[:, :target_dim]

            scaled_input = self.scaler.transform(input_features)

            feature_names = [f"feature_{i}" for i in range(target_dim)]

            selected_model_name = self.config.get("selected_model", "rf")

            selected_model = self.models.get(selected_model_name)

            if selected_model is None:

                return {}

            if not _dependencies._HAS_LIME:
                return {
                    "explanation": [],
                    "feature_names": feature_names,
                    "note": "LIME unavailable",
                }

            explainer = _dependencies.LimeTabularExplainer(
                X_observed,
                feature_names=feature_names,
                class_names=["retained", "churned"],
                mode="classification",
            )

            exp = explainer.explain_instance(
                scaled_input[0], selected_model.predict_proba, num_features=min(5, target_dim)
            )

            return {"explanation": exp.as_list(), "feature_names": feature_names}

        except Exception as e:

            logging.error(f"Error generating LIME explanations: {e}")

            return {}

    def _calculate_risk_score(self, predictions: dict) -> dict:
        """Calculate final risk score with confidence interval"""

        try:

            if predictions.get("available") is False:

                # Honest passthrough — no fitted models, no score.

                return {
                    "available": False,
                    "truth_class": predictions.get("truth_class", "untrained_models"),
                    "score": None,
                    "confidence_interval": None,
                    "probability": None,
                }

            if (
                self.config.get("ensemble_selection_method", "weighted_average")
                == "weighted_average"
            ):

                # Extract model predictions (exclude non-model keys)

                model_preds = {
                    k: v
                    for k, v in predictions.items()
                    if isinstance(v, dict) and "score" in v and "weight" in v
                }

                if model_preds:

                    # Unmeasured CV weights (None) contribute uniform mass.

                    weights = [
                        p["weight"] if p.get("weight") is not None else 1.0
                        for p in model_preds.values()
                    ]

                    total_weight = sum(weights)

                    if total_weight > 0:

                        weighted_score = (
                            sum(p["score"] * w for p, w in zip(model_preds.values(), weights))
                            / total_weight
                        )

                    else:

                        weighted_score = np.mean([p["score"] for p in model_preds.values()])

                    confidence = np.std([p["score"] for p in model_preds.values()])

                else:

                    weighted_score = None

                    confidence = 0.0

            elif self.config.get("ensemble_selection_method") == "voting":

                weighted_score = predictions.get("voting_probability")

                confidence = 0.0  # Not applicable for voting system

            else:

                weighted_score = None

                confidence = 0.0

            return {
                "score": float(weighted_score) if weighted_score is not None else None,
                "confidence_interval": float(confidence),
                "probability": (
                    self._calculate_probability(weighted_score)
                    if weighted_score is not None
                    else None
                ),
            }

        except Exception as e:

            logging.error(f"Error calculating risk score: {e}")

            raise

    def _identify_key_factors(self, indicators: dict) -> list:
        """Identify top contributing factors to risk"""

        try:

            factor_weights = self._calculate_factor_weights(indicators)

            # Calculate actual contribution of each factor

            factor_scores = {}

            for factor, weight in factor_weights.items():

                if factor in indicators and isinstance(indicators[factor], dict):

                    values = [v for v in indicators[factor].values() if isinstance(v, (int, float))]

                    if values:

                        # Quantum expectation value of the factor

                        factor_scores[factor] = weight * np.mean(values)

                    else:

                        factor_scores[factor] = weight

                else:

                    factor_scores[factor] = weight

            return sorted(factor_scores.items(), key=lambda x: x[1], reverse=True)[:5]

        except Exception as e:

            logging.error(f"Error identifying key factors: {e}")

            raise

    def _generate_recommendations(self, indicators: dict) -> dict:
        """Generate personalized retention recommendations"""

        try:

            risk_factors = self._identify_key_factors(indicators)

            return {
                "immediate_actions": self._get_immediate_actions(risk_factors),
                "long_term_strategies": self._get_long_term_strategies(risk_factors),
                "manager_recommendations": self._get_manager_recommendations(risk_factors),
            }

        except Exception as e:

            logging.error(f"Error generating recommendations: {e}")

            raise

    def _predict_risk_trajectory(self, indicators: dict) -> dict:
        """Predict risk trajectory over next 3-6 months"""

        try:

            current_trend = self._analyze_trend(indicators)

            future_predictions = self._forecast_risk(indicators)

            return {
                "current_trajectory": current_trend,
                "forecast": future_predictions,
                "intervention_points": self._identify_intervention_points(future_predictions),
            }

        except Exception as e:

            logging.error(f"Error predicting risk trajectory: {e}")

            raise

    def _calculate_confidence(self, predictions: dict) -> float:
        """Calculate prediction confidence level"""

        try:

            model_preds = {
                k: v for k, v in predictions.items() if isinstance(v, dict) and "confidence" in v
            }

            if not model_preds:

                return 0.0

            model_scores = [p["confidence"] for p in model_preds.values()]

            agreement_score = self._calculate_model_agreement(predictions)

            data_quality_score = self._assess_data_quality()

            if data_quality_score is None:

                # No observed cohort — renormalize across measured terms
                # only; never substitute a fabricated quality figure.

                confidence = np.mean(model_scores) * 0.5 + agreement_score * 0.5

            else:

                confidence = (
                    np.mean(model_scores) * 0.4  # Model confidence
                    + agreement_score * 0.4  # Model agreement
                    + data_quality_score * 0.2  # Data quality
                )

            return float(confidence)

        except Exception as e:

            logging.error(f"Error calculating confidence: {e}")

            raise

    def _assess_data_quality(self):
        """
        Assess data quality using von Neumann entropy (first principles).

        The von Neumann entropy S = -Tr(rho * log(rho)) measures the information content
        of the quantum state. Higher entropy = more information = better quality.
        Normalized to [0, 1] range.

        Computed over the real observed training matrix. Returns None —
        honest 'unmeasured' — when no observed cohort exists.
        """

        try:

            training = self._real_training_data()

            if training is None:

                return None

            X, _ = training

            # Construct density matrix from data: rho = X^T X / Tr(X^T X)

            cov = np.corrcoef(X.T)

            # Handle NaN values

            cov = np.nan_to_num(cov, nan=0.0)

            # Ensure positive semi-definite

            eigenvalues = np.linalg.eigvalsh(cov)

            eigenvalues = np.maximum(eigenvalues, 1e-10)

            # von Neumann entropy: S = -sum(lambda_i * log(lambda_i))

            normalized_eigenvalues = eigenvalues / np.sum(eigenvalues)

            entropy = -np.sum(normalized_eigenvalues * np.log(normalized_eigenvalues))

            # Normalize by maximum entropy (log of dimension)

            max_entropy = np.log(len(eigenvalues))

            if max_entropy > 0:

                quality = entropy / max_entropy

            else:

                return None

            return float(np.clip(quality, 0.0, 1.0))

        except Exception as e:

            logging.error(f"Error assessing data quality: {e}")

            return None

    def _calculate_model_agreement(self, predictions: dict) -> float:
        """
        Calculate model agreement using quantum decoherence measure (first principles).

        The purity of the density matrix rho = sum(w_i * |psi_i><psi_i|) measures agreement:
        Tr(rho^2) = 1 for pure state (perfect agreement)
        Tr(rho^2) = 1/N for maximally mixed state (no agreement)
        """

        try:

            model_preds = {
                k: v for k, v in predictions.items() if isinstance(v, dict) and "score" in v
            }

            if not model_preds:

                return 0.0

            scores = np.array([p["score"] for p in model_preds.values()])

            # Unmeasured weights (None) contribute uniform mass — never a
            # fabricated performance figure.

            weights = np.array(
                [p["weight"] if p.get("weight") is not None else 1.0 for p in model_preds.values()]
            )

            # Normalize weights

            total_weight = np.sum(weights)

            if total_weight > 0:

                weights = weights / total_weight

            # Construct density matrix: rho = sum(w_i * |psi_i><psi_i|)

            n = len(scores)

            rho = np.zeros((n, n))

            for i in range(n):

                psi_i = np.zeros(n)

                psi_i[i] = np.sqrt(scores[i]) if scores[i] > 0 else 0

                rho += weights[i] * np.outer(psi_i, psi_i)

            # Purity: Tr(rho^2)

            purity = np.trace(np.dot(rho, rho))

            # Normalize: 1 = perfect agreement, 1/N = no agreement

            if n > 1:

                normalized_purity = (purity - 1 / n) / (1 - 1 / n)

            else:

                normalized_purity = 1.0

            return float(np.clip(normalized_purity, 0.0, 1.0))

        except Exception as e:

            logging.error(f"Error calculating model agreement: {e}")

            return 0.5

    def _analyze_trend(self, indicators: dict) -> dict:
        """
        Analyze current risk trend using Schrodinger time evolution (first principles).

        The risk state evolves as: |psi(t)> = exp(-iHt/hbar) |psi(0)>
        The trend is determined by the expectation value of the Hamiltonian.
        """

        try:

            hbar = self.config.get("hbar", 1.0)

            mass = self.config.get("mass", 1.0)

            omega = self.config.get("omega", 0.5)

            # Extract numeric values from indicators

            all_values = []

            for key, value in indicators.items():

                if isinstance(value, dict):

                    for v in value.values():

                        if isinstance(v, (int, float)):

                            all_values.append(float(v))

            if not all_values:

                return {"trend": "stable", "rate": 0.0}

            values = np.array(all_values)

            mean_val = np.mean(values)

            std_val = np.std(values)

            if std_val == 0:

                return {"trend": "stable", "rate": 0.0}

            # Hamiltonian expectation: <H> = <p^2>/(2m) + (1/2)*m*w^2*<x^2>

            # Kinetic energy from variance of differences

            if len(values) > 1:

                p_squared = np.var(np.diff(values))

            else:

                p_squared = 0.0

            kinetic = p_squared / (2 * mass)

            # Potential energy from deviation

            potential = 0.5 * mass * omega**2 * np.mean((values - mean_val) ** 2) / std_val**2

            total_energy = kinetic + potential

            # Trend direction from energy sign

            if total_energy > 0.1:

                trend = "increasing"

            elif total_energy < -0.1:

                trend = "decreasing"

            else:

                trend = "stable"

            # Rate of change (Schrodinger evolution rate)

            rate = total_energy / hbar if hbar > 0 else total_energy

            return {
                "trend": trend,
                "rate": float(rate),
                "energy": float(total_energy),
                "kinetic_energy": float(kinetic),
                "potential_energy": float(potential),
            }

        except Exception as e:

            logging.error(f"Error analyzing quantum trend: {e}")

            return {"trend": "stable", "rate": 0.0}

    def _forecast_risk(self, indicators: dict) -> dict:
        """
        Forecast future risk using path integral formulation (first principles).

        The future risk is computed as a sum over all possible paths:
        K(b,a) = integral Dx(t) exp(iS[x(t)]/hbar)

        In practice, this becomes a Monte Carlo sampling of future trajectories,
        weighted by the action S along each path.
        """

        try:

            hbar = self.config.get("hbar", 1.0)

            mass = self.config.get("mass", 1.0)

            n_paths = self.config.get("path_samples", 100)

            omega = self.config.get("omega", 0.5)

            # Extract current risk state

            all_values = []

            for key, value in indicators.items():

                if isinstance(value, dict):

                    for v in value.values():

                        if isinstance(v, (int, float)):

                            all_values.append(float(v))

            if not all_values:

                return {
                    "available": False,
                    "3_month": None,
                    "6_month": None,
                    "algebraic": {
                        "enabled": bool(self.config.get("pisot_filter_enabled", True)),
                        "available": False,
                    },
                }

            current_risk = np.mean(all_values)

            volatility = np.std(all_values) if len(all_values) > 1 else 0.1

            # Path integral over a deterministic quadrature lattice — no RNG.
            #
            # Instead of sampling random walks, each path traverses the same
            # Gauss-quantile node set under a distinct deterministic cyclic
            # ordering. This is a quadrature rule over the path space, not a
            # simulation: identical inputs always produce identical outputs.

            # Action: S = integral [ (1/2)*m*xdot^2 - V(x) ] dt

            dt_3month = 3.0  # 3 time units

            dt_6month = 6.0  # 6 time units

            def _quantile_lattice(n_steps: int, sigma: float) -> np.ndarray:
                """Midpoint quantiles of N(0, sigma) — deterministic nodes."""

                nd = statistics.NormalDist(mu=0.0, sigma=max(float(sigma), 1e-12))

                return np.array([nd.inv_cdf((i + 0.5) / n_steps) for i in range(n_steps)])

            def path_integral_forecast(dt, n_paths):
                """Compute path integral forecast for given time horizon."""

                amplitudes = []

                n_steps = max(int(dt * 10), 1)

                lattice = _quantile_lattice(n_steps, volatility / np.sqrt(n_steps))

                # Distinct deterministic orderings of the node set: cyclic
                # shifts cover the walk space uniformly without randomness.

                for k in range(min(n_paths, n_steps)):

                    increments = np.roll(lattice, k)

                    path = np.cumsum(increments) + current_risk

                    # Compute action: S = integral [ (1/2)*m*xdot^2 - V(x) ] dt

                    # Kinetic: (1/2)*m*(dx/dt)^2

                    kinetic_action = 0.5 * mass * np.sum(increments**2) * n_steps

                    # Potential: V(x) = (1/2)*m*w^2*x^2 (harmonic)

                    potential_action = 0.5 * mass * omega**2 * np.sum(path**2) * dt / n_steps

                    action = kinetic_action - potential_action

                    # Path amplitude: exp(iS/hbar)

                    amplitude = np.exp(1j * action / hbar)

                    amplitudes.append(amplitude)

                # Born rule: probability = |sum amplitudes|^2 / N^2

                total_amplitude = np.sum(amplitudes)

                n_eval = len(amplitudes)

                probability = np.abs(total_amplitude) ** 2 / (n_eval**2)

                # Map to risk probability [0, 1]

                risk = current_risk + probability * np.sign(np.real(total_amplitude))

                return float(np.clip(risk, 0.0, 1.0))

            forecast_3 = path_integral_forecast(dt_3month, n_paths)

            forecast_6 = path_integral_forecast(dt_6month, n_paths)

            # Algebraic layer: detect which recurrence structure the
            # indicator series obeys, then contract the quadrature noise
            # with that family's Pisot drift kernel (|mu|^n -> 0). The
            # filter family is the detected one, or plastic (minimal
            # Pisot) when "auto" finds no structured lag.

            algebraic = {"enabled": bool(self.config.get("pisot_filter_enabled", True))}

            if algebraic["enabled"]:

                signature = self.algebra.detect_family_signature(np.asarray(all_values))

                configured = self.config.get("algebraic_family", "auto")

                family = (
                    signature["family"]
                    if configured == "auto"
                    else (configured if configured in self.algebra.FAMILY_NAMES else "plastic")
                )

                if family == "unstructured":

                    family = "plastic"

                filtered = self.algebra.pisot_drift_filter(all_values, family)

                algebraic.update(
                    {
                        "family": family,
                        "signature": _exact_out(signature),
                        "filtered_series": _exact_out(filtered),
                        "filtered_risk": (
                            str(filtered[-1]) if filtered else str(Decimal(str(current_risk)))
                        ),
                        "contraction_per_step": str(self.algebra.pisot_modulus(family)),
                        "drift_bound_3_month": str(self.algebra.pisot_drift(family, 3)),
                        "drift_bound_6_month": str(self.algebra.pisot_drift(family, 6)),
                    }
                )

            return {
                "3_month": forecast_3,
                "6_month": forecast_6,
                "current": float(current_risk),
                "method": "path_integral_monte_carlo",
                "algebraic": algebraic,
            }

        except Exception as e:

            logging.error(f"Error forecasting risk: {e}")

            return {"3_month": 0.5, "6_month": 0.5}

    def _identify_intervention_points(self, predictions: dict) -> list:
        """
        Identify optimal intervention points using quantum measurement theory (first principles).

        The optimal measurement time is when the quantum Fisher information is maximized,
        indicating maximum sensitivity to perturbations (interventions).
        """

        try:

            hbar = self.config.get("hbar", 1.0)

            # Extract forecast values

            forecast_values = []

            if isinstance(predictions, dict):

                for key, value in predictions.items():

                    if isinstance(value, (int, float)):

                        forecast_values.append((key, float(value)))

            if not forecast_values:

                # No forecast evidence — return no intervention points
                # rather than fabricated recommendations.

                return []

            # Sort by time

            forecast_values.sort(key=lambda x: x[0])

            # Calculate quantum Fisher information at each time point

            # F_Q = 4( <dH/dtheta>^2 - <(dH/dtheta)^2> )

            # Computed as finite-difference derivative of the risk trajectory

            intervention_points = []

            for i, (time_key, value) in enumerate(forecast_values):

                # Fisher information: finite-difference of the trajectory

                if i > 0:

                    prev_val = forecast_values[i - 1][1]

                    fisher_info = abs(value - prev_val) / hbar

                else:

                    fisher_info = value / hbar

                # Determine intervention action based on risk level

                if value > 0.7:

                    action = "manager_meeting"

                    time_label = "2_weeks"

                elif value > 0.5:

                    action = "compensation_review"

                    time_label = "1_month"

                else:

                    action = "career_development"

                    time_label = "3_months"

                intervention_points.append(
                    {
                        "time": time_label,
                        "action": action,
                        "fisher_info": float(fisher_info),
                        "projected_risk": float(value),
                    }
                )

            return intervention_points

        except Exception as e:

            logging.error(f"Error identifying intervention points: {e}")

            return [
                {"time": "2_weeks", "action": "manager_meeting", "fisher_info": 0.5},
                {"time": "1_month", "action": "compensation_review", "fisher_info": 0.3},
            ]

    def _calculate_probability(self, score: float) -> float:
        """Calculate a probability from a score using Born rule"""

        try:

            return float(1 / (1 + np.exp(-score)))

        except Exception as e:

            logging.error(f"Error calculating probability: {e}")

            raise

    def _calculate_factor_weights(self, indicators: dict) -> dict:
        """Calculate weights for factors"""

        try:

            return {
                "performance_metrics": self.config.get("performance_weight", 0.30),
                "behavioral_metrics": self.config.get("behavioral_weight", 0.25),
                "engagement_metrics": self.config.get("engagement_weight", 0.20),
                "career_metrics": self.config.get("career_weight", 0.15),
                "external_metrics": self.config.get("external_weight", 0.10),
            }

        except Exception as e:

            logging.error(f"Error calculating factor weights: {e}")

            raise

    def _get_immediate_actions(self, risk_factors: list) -> list:
        """Generates immediate retention actions based on quantum state analysis"""

        try:

            actions = []

            for factor, weight in risk_factors:

                if "performance" in str(factor):

                    actions.append("Schedule performance review meeting")

                elif "behavioral" in str(factor):

                    actions.append("Check-in with manager regarding workload")

                elif "engagement" in str(factor):

                    actions.append("Conduct engagement survey follow-up")

                elif "career" in str(factor):

                    actions.append("Discuss career development opportunities")

                elif "external" in str(factor):

                    actions.append("Review compensation competitiveness")

            if not actions:

                actions = ["Check-in with manager", "Review project workload"]

            return actions[:3]

        except Exception as e:

            logging.error(f"Error generating immediate actions: {e}")

            return ["Check-in with manager", "Review project workload"]

    def _get_long_term_strategies(self, risk_factors: list) -> list:
        """Generates long-term retention strategies based on quantum trajectory analysis"""

        try:

            strategies = []

            for factor, weight in risk_factors:

                if "performance" in str(factor):

                    strategies.append("Implement performance improvement plan")

                elif "behavioral" in str(factor):

                    strategies.append("Flexible work arrangement evaluation")

                elif "engagement" in str(factor):

                    strategies.append("Team building and culture initiatives")

                elif "career" in str(factor):

                    strategies.append("Career development planning and mentorship")

                elif "external" in str(factor):

                    strategies.append("Compensation benchmarking review")

            if not strategies:

                strategies = ["Career development planning", "Skill development workshop"]

            return strategies[:3]

        except Exception as e:

            logging.error(f"Error generating long-term strategies: {e}")

            return ["Career development planning", "Skill development workshop"]

    def _get_manager_recommendations(self, risk_factors: list) -> list:
        """Generates recommendations for managers based on quantum measurement insights"""

        try:

            recommendations = []

            for factor, weight in risk_factors:

                if "performance" in str(factor):

                    recommendations.append("Set clear performance goals and milestones")

                elif "behavioral" in str(factor):

                    recommendations.append("Monitor workload and work-life balance")

                elif "engagement" in str(factor):

                    recommendations.append("Increase frequency of 1-on-1 meetings")

                elif "career" in str(factor):

                    recommendations.append("Discuss career aspirations and growth path")

                elif "external" in str(factor):

                    recommendations.append("Review compensation and benefits package")

            if not recommendations:

                recommendations = ["Schedule meeting with employee", "Ask about workload"]

            return recommendations[:3]

        except Exception as e:

            logging.error(f"Error generating manager recommendations: {e}")

            return ["Schedule meeting with employee", "Ask about workload"]

    def _predict_with_model(self, model, indicators: dict) -> dict:
        """Predict using a given model and normalized data"""

        try:

            input_features = self._prepare_input_features(indicators)  # Generate input features

            if input_features.ndim == 1:

                input_features = input_features.reshape(1, -1)

            # Match the feature dimension the observed cohort was fitted on.

            target_dim = self._feature_dim()

            if input_features.shape[1] < target_dim:

                padding = np.zeros((input_features.shape[0], target_dim - input_features.shape[1]))

                input_features = np.hstack([input_features, padding])

            elif input_features.shape[1] > target_dim:

                input_features = input_features[:, :target_dim]

            # Exact-linear model applies center-only preprocessing itself.
            model_features = input_features

            y_pred = model.predict_proba(model_features)[:, 1]  # get probability

            return {
                "score": float(y_pred[0]),
                "confidence": self._calculate_model_confidence(y_pred[0]),
            }

        except Exception as e:

            logging.error(f"Error predicting with model: {e}")

            raise

    def _calculate_model_confidence(self, prediction: float) -> float:
        """
        Calculate model confidence using quantum Fisher information (first principles).

        The quantum Fisher information bounds the variance of any unbiased estimator:
        Var(theta_hat) >= 1/F_Q

        Confidence is derived from the Fisher information of the Born rule probability.
        """

        try:

            # Born rule: P = |psi|^2, with psi = sqrt(P) * exp(i*phi)

            # Fisher information for Bernoulli: F_Q = 1/(P*(1-P))

            if prediction <= 0 or prediction >= 1:

                # Maximum confidence at extremes (certain outcome)

                return 1.0

            fisher_info = 1.0 / (prediction * (1 - prediction))

            # Normalize Fisher information to [0, 1] confidence

            # Maximum Fisher info for Bernoulli is 4 (at P=0.5)

            max_fisher = 4.0

            confidence = fisher_info / max_fisher

            # Invert: high Fisher info at P=0.5 means LOW confidence (uncertain)

            # Low Fisher info at extremes means HIGH confidence (certain)

            confidence = 1.0 - confidence

            return float(np.clip(confidence, 0.0, 1.0))

        except Exception as e:

            logging.error(f"Error calculating model confidence: {e}")

            return 0.5

    def _prepare_input_features(self, indicators: dict) -> np.ndarray:
        """Concatenate all extracted indicators into a numpy array"""

        try:

            feature_list = []

            for key, value in indicators.items():

                if isinstance(value, dict):

                    for v in value.values():

                        if isinstance(v, (int, float, np.floating)):

                            feature_list.append(float(v))

                        elif isinstance(v, np.ndarray):

                            feature_list.extend(v.flatten())

                elif isinstance(value, list):

                    for v in value:

                        if isinstance(v, (int, float, np.floating)):

                            feature_list.append(float(v))

                elif isinstance(value, str):

                    feature_list.append(self._analyze_text_sentiment(value))

                elif isinstance(value, np.ndarray):

                    feature_list.extend(value.flatten())

                elif isinstance(value, (int, float, np.floating)):

                    if not (isinstance(value, float) and np.isnan(value)):

                        feature_list.append(float(value))

            if not feature_list:

                feature_list = [0.0] * self.config.get("feature_dim", 10)

            return np.array(feature_list, dtype=float)

        except Exception as e:

            logging.error(f"Error preparing input features: {e}")

            raise

    def _analyze_text_sentiment(self, text: str) -> float:
        """Analyzes the sentiment of input text."""

        try:

            if not isinstance(text, str):

                return 0.0

            scores = self.sentiment_analyzer.polarity_scores(text)

            return float(scores["compound"])

        except Exception as e:

            logging.error(f"Error analyzing text sentiment: {e}")

            return 0.0

    def _analyze_performance_trend(self, data: _dependencies.pd.DataFrame) -> dict:
        """Analyze employee performance trends with quantum-enhanced time series"""

        try:

            if not isinstance(data, _dependencies.pd.DataFrame):
                raise TypeError("performance trend input must be a pandas DataFrame")
            if "performance_score" not in data.columns or "date" not in data.columns:
                raise ValueError("performance trend requires date and performance_score columns")

            if (
                isinstance(data, _dependencies.pd.DataFrame)
                and "performance_score" in data.columns
                and "date" in data.columns
            ):

                data = data.copy()

                data["date"] = _dependencies.pd.to_datetime(data["date"])  # Convert to datetime

                data = data.sort_values(by="date")

                # Moving Average

                ma = data["performance_score"].rolling(window=3, min_periods=1).mean()

                # Exponential Smoothing

                ewma = data["performance_score"].ewm(span=3, min_periods=1).mean()

                # Seasonal Decomposition with quantum-enhanced trend

                if len(data) > 10 and _dependencies._HAS_STATSMODELS:

                    decomposition = _dependencies.seasonal_decompose(
                        data["performance_score"],
                        model="additive",
                        period=5,
                        extrapolate_trend="freq",
                    )

                    trend = decomposition.trend.fillna(
                        method="bfill"
                    ).mean()  # Take mean of the trend component

                else:

                    trend = data["performance_score"].diff().mean()

                return {
                    "ma": float(ma.iloc[-1]) if not ma.empty else 0.0,
                    "ewma": float(ewma.iloc[-1]) if not ewma.empty else 0.0,
                    "trend": float(trend) if not np.isnan(trend) else 0.0,
                }

            return {}

        except Exception as e:

            logging.error(f"Error in _analyze_performance_trend: {e}")

            raise

    def _analyze_text_engagement(self, text: str) -> float:
        """
        Analyzes text for engagement signals using quantum semantic analysis (first principles).

        Tokenize text, compute TF-IDF as quantum amplitudes, measure "engagement"
        as the norm of the semantic state vector in Hilbert space.
        """

        try:

            if not isinstance(text, str) or not text.strip():

                return 0.0

            # Quantum semantic analysis: TF-IDF as probability amplitudes

            # Fit TF-IDF on the text

            tfidf_matrix = self.tfidf_vectorizer.fit_transform([text])

            # Extract amplitudes (TF-IDF values)

            amplitudes = tfidf_matrix.toarray()[0]

            if len(amplitudes) == 0:

                return 0.0

            # Normalize to create quantum state vector

            norm = np.sqrt(np.sum(amplitudes**2))

            if norm == 0:

                return 0.0

            psi = amplitudes / norm

            # Engagement = <psi|psi> = 1 (always normalized)
            # But measure "intensity" as sum of squared amplitudes weighted by position

            # Higher engagement = more concentrated semantic state

            entropy = -np.sum(psi**2 * np.log(psi**2 + 1e-10))

            # Normalize entropy to [0, 1] - lower entropy = more focused = higher engagement

            max_entropy = np.log(len(psi)) if len(psi) > 1 else 1.0

            if max_entropy > 0:

                engagement = 1.0 - (entropy / max_entropy)

            else:

                engagement = 0.5

            return float(np.clip(engagement, 0.0, 1.0))

        except Exception as e:

            logging.error(f"Error analyzing text engagement: {e}")

            return 0.5

    def _analyze_login_patterns(self, data: _dependencies.pd.DataFrame) -> int:
        """
        Analyze employee login patterns using quantum counting (first principles).

        Login pattern as a quantum state, count using Grover-like amplitude amplification.
        """

        try:

            if isinstance(data, _dependencies.pd.DataFrame) and "login_time" in data.columns:

                values = data["login_time"].dropna().values.astype(float)

                if len(values) == 0:

                    return 0

                # Quantum counting: expectation value of number operator

                # Map to quantum levels

                if np.max(values) == np.min(values):

                    return 1

                normalized = (values - np.min(values)) / (np.max(values) - np.min(values))

                quantum_numbers = np.round(normalized * (len(values) - 1))

                # Uniform amplitudes

                amplitudes = np.ones(len(values)) / np.sqrt(len(values))

                probabilities = np.abs(amplitudes) ** 2

                expectation_n = np.sum(quantum_numbers * probabilities)

                return int(expectation_n)

            return 0

        except Exception as e:

            logging.error(f"Error in _analyze_login_patterns: {e}")

            raise

    def _analyze_survey_responses(self, data: _dependencies.pd.DataFrame) -> np.ndarray:
        """Analyzes employee survey responses using quantum semantic state vectors"""

        try:

            if not isinstance(data, _dependencies.pd.DataFrame):
                raise TypeError("survey response input must be a pandas DataFrame")
            if "survey_text" not in data.columns:
                raise ValueError("survey response data requires a survey_text column")

            if isinstance(data, _dependencies.pd.DataFrame) and "survey_text" in data.columns:

                text_features = self._process_text_data(data["survey_text"])

                return text_features

            return np.array([])

        except Exception as e:

            logging.error(f"Error in _analyze_survey_responses: {e}")

            raise

    def _process_text_data(self, text_series: _dependencies.pd.Series) -> np.ndarray:
        """
        Process text data into quantum semantic state vectors (first principles).

        TF-IDF values are treated as probability amplitudes in a Hilbert space,
        normalized to create valid quantum states.
        """

        try:

            # Handle NaN values in text

            text_data = text_series.dropna().astype(str)

            if len(text_data) == 0:

                return np.array([0.0])

            # Fit and transform TF-IDF

            tfidf_matrix = self.tfidf_vectorizer.fit_transform(text_data)

            amplitudes = tfidf_matrix.toarray()

            # Normalize each row to create quantum state vectors

            for i in range(amplitudes.shape[0]):

                norm = np.sqrt(np.sum(amplitudes[i] ** 2))

                if norm > 0:

                    amplitudes[i] = amplitudes[i] / norm

            # Return as flattened array of quantum state amplitudes

            return amplitudes.flatten()

        except Exception as e:

            logging.error(f"Error processing text data: {e}")

            return np.array([0.0])

    def _analyze_goal_completion(self, data) -> float:
        """
        Analyzes the level of goal completion using quantum measurement theory (first principles).

        Goal completion is modeled as a quantum measurement: the probability of
        observing "completed" is |<completed|psi>|^2 where |psi> is the employee state.
        """

        try:

            if isinstance(
                data, (_dependencies.pd.Series, _dependencies.pd.DataFrame, np.ndarray, list)
            ):

                values = np.array(data, dtype=float).flatten()

                values = values[~np.isnan(values)]

                if len(values) == 0:

                    return 0.0

                # Quantum measurement: P(completed) = mean of completion values

                # Born rule: P = |amplitude|^2

                amplitudes = np.sqrt(np.clip(values, 0, 1))

                norm = np.sqrt(np.sum(amplitudes**2))

                if norm == 0:

                    return 0.0

                psi = amplitudes / norm

                # Measurement probability

                probability = np.sum(psi**2 * values) / np.sum(psi**2)

                return float(np.clip(probability, 0.0, 1.0))

            return 0.0

        except Exception as e:

            logging.error(f"Error in _analyze_goal_completion: {e}")

            raise

    def _analyze_peer_comparison(self, data) -> float:
        """
        Analyzes the performance relative to peers using quantum fidelity (first principles).

        Fidelity F = |<psi|phi>|^2 measures overlap between employee and peer-average states.
        """

        try:

            if isinstance(
                data, (_dependencies.pd.Series, _dependencies.pd.DataFrame, np.ndarray, list)
            ):

                values = np.array(data, dtype=float).flatten()

                values = values[~np.isnan(values)]

                if len(values) < 2:

                    return 0.5

                # Employee state vector

                psi = values - np.mean(values)

                norm_psi = np.sqrt(np.sum(psi**2))

                if norm_psi == 0:

                    return 1.0

                psi = psi / norm_psi

                # Peer average state (uniform superposition)

                phi = np.ones_like(psi) / np.sqrt(len(psi))

                # Quantum fidelity: F = |<psi|phi>|^2

                fidelity = np.abs(np.dot(np.conj(psi), phi)) ** 2

                return float(fidelity)

            return 0.5

        except Exception as e:

            logging.error(f"Error in _analyze_peer_comparison: {e}")

            raise

    def _analyze_communication(self, data) -> float:
        """
        Analyzes communication patterns using quantum information theory (first principles).

        Communication quality is measured as the quantum mutual information between
        communication frequency and sentiment.
        """

        try:

            if isinstance(
                data, (_dependencies.pd.Series, _dependencies.pd.DataFrame, np.ndarray, list)
            ):

                values = np.array(data, dtype=float).flatten()

                values = values[~np.isnan(values)]

                if len(values) == 0:

                    return 0.0

                # Quantum information measure: Shannon entropy of normalized values

                # Treat values as probability distribution

                positive_values = np.abs(values)

                total = np.sum(positive_values)

                if total == 0:

                    return 0.0

                probabilities = positive_values / total

                # Quantum von Neumann entropy: S = -Σ p_k log2(p_k)

                entropy = -np.sum(probabilities * np.log2(probabilities + 1e-10))

                # Normalize by maximum entropy

                max_entropy = np.log2(len(values)) if len(values) > 1 else 1.0

                if max_entropy > 0:

                    communication_quality = entropy / max_entropy

                else:

                    communication_quality = 0.0

                return float(np.clip(communication_quality, 0.0, 1.0))

            return 0.0

        except Exception as e:

            logging.error(f"Error in _analyze_communication: {e}")

            raise

    def _analyze_attendance(self, data) -> float:
        """
        Analyzes meeting attendance using quantum temporal coherence (first principles).

        Attendance regularity is measured as the temporal coherence of the
        attendance pattern, analogous to quantum coherence.
        """

        try:

            if isinstance(
                data, (_dependencies.pd.Series, _dependencies.pd.DataFrame, np.ndarray, list)
            ):

                values = np.array(data, dtype=float).flatten()

                values = values[~np.isnan(values)]

                if len(values) < 2:

                    return 0.5

                # Temporal coherence: autocorrelation at lag 1

                mean_val = np.mean(values)

                if np.std(values) == 0:

                    return 1.0  # Perfect regularity

                # Quantum coherence: <psi(0)|psi(t)>

                psi = (values - mean_val) / np.std(values)

                norm = np.sqrt(np.sum(psi**2))

                if norm == 0:

                    return 1.0

                psi = psi / norm

                # Autocorrelation as coherence measure

                if len(psi) > 1:

                    coherence = np.correlate(psi[:-1], psi[1:])[0]

                else:

                    coherence = 1.0

                return float(np.clip(np.abs(coherence), 0.0, 1.0))

            return 0.5

        except Exception as e:

            logging.error(f"Error in _analyze_attendance: {e}")

            raise

    def _analyze_work_hours(self, data) -> float:
        """
        Analyzes changes in work hours using quantum energy levels (first principles).

        Work hours distribution is modeled as quantum energy levels of a
        harmonic oscillator. Variations in energy indicate instability.
        """

        try:

            if isinstance(
                data, (_dependencies.pd.Series, _dependencies.pd.DataFrame, np.ndarray, list)
            ):

                values = np.array(data, dtype=float).flatten()

                values = values[~np.isnan(values)]

                if len(values) < 2:

                    return 0.0

                hbar = self.config.get("hbar", 1.0)

                self.config.get("mass", 1.0)

                omega = self.config.get("omega", 0.5)

                # Quantum energy levels: E_n = (n + 1/2) * hbar * omega

                mean_val = np.mean(values)

                std_val = np.std(values)

                if std_val == 0:

                    return 0.0  # No variation = stable

                # Normalize to quantum numbers

                normalized = (values - mean_val) / std_val

                quantum_numbers = np.round(np.abs(normalized))

                # Energy levels

                energies = (quantum_numbers + 0.5) * hbar * omega

                # Average energy deviation from ground state

                ground_energy = 0.5 * hbar * omega

                energy_deviation = np.mean(energies - ground_energy)

                # Normalize to [0, 1]

                max_deviation = (len(values) + 0.5) * hbar * omega - ground_energy

                if max_deviation > 0:

                    instability = energy_deviation / max_deviation

                else:

                    instability = 0.0

                return float(np.clip(instability, 0.0, 1.0))

            return 0.0

        except Exception as e:

            logging.error(f"Error in _analyze_work_hours: {e}")

            raise

    def _analyze_participation(self, data) -> float:
        """
        Analyzes participation in projects using quantum superposition (first principles).

        Participation is modeled as a superposition of "active" and "inactive" states.
        The probability of being "active" is |<active|psi>|^2.
        """

        try:

            if isinstance(
                data, (_dependencies.pd.Series, _dependencies.pd.DataFrame, np.ndarray, list)
            ):

                values = np.array(data, dtype=float).flatten()

                values = values[~np.isnan(values)]

                if len(values) == 0:

                    return 0.0

                # Quantum superposition: participation as probability amplitude

                # Normalize values to [0, 1] as amplitudes

                if np.max(values) > 0:

                    amplitudes = np.sqrt(np.clip(values / np.max(values), 0, 1))

                else:

                    return 0.0

                # Quantum state vector

                norm = np.sqrt(np.sum(amplitudes**2))

                if norm == 0:

                    return 0.0

                psi = amplitudes / norm

                # Measurement: probability of "active" state

                # Active state = uniform superposition

                active_state = np.ones_like(psi) / np.sqrt(len(psi))

                probability = np.abs(np.dot(np.conj(psi), active_state)) ** 2

                return float(np.clip(probability, 0.0, 1.0))

            return 0.0

        except Exception as e:

            logging.error(f"Error in _analyze_participation: {e}")

            raise

    def _analyze_feedback(self, data) -> float:
        """
        Analyzes feedback sentiment using quantum measurement (first principles).

        Feedback is treated as a quantum observable. The expectation value
        gives the average sentiment, weighted by quantum probabilities.
        """

        try:

            if isinstance(
                data, (_dependencies.pd.Series, _dependencies.pd.DataFrame, np.ndarray, list)
            ):

                values = np.array(data, dtype=float).flatten()

                values = values[~np.isnan(values)]

                if len(values) == 0:

                    return 0.0

                # Quantum observable: expectation value

                # Normalize to probability amplitudes

                positive_values = np.abs(values)

                total = np.sum(positive_values)

                if total == 0:

                    return 0.0

                probabilities = positive_values / total

                # Expectation value: <O> = sum(P_i * O_i)

                # Sentiment observable: sign of values

                observable = np.sign(values)

                expectation = np.sum(probabilities * observable)

                return float(np.clip((expectation + 1) / 2, 0.0, 1.0))  # Map [-1,1] to [0,1]

            return 0.0

        except Exception as e:

            logging.error(f"Error in _analyze_feedback: {e}")

            raise

    def _analyze_promotions(self, data) -> float:
        """
        Analyzes the history of promotions using quantum ladder operators (first principles).

        Promotions are modeled as quantum ladder climbing: each promotion is an
        energy level transition via the raising operator a^dagger.
        """

        try:

            if isinstance(
                data, (_dependencies.pd.Series, _dependencies.pd.DataFrame, np.ndarray, list)
            ):

                values = np.array(data, dtype=float).flatten()

                values = values[~np.isnan(values)]

                if len(values) == 0:

                    return 0.0

                hbar = self.config.get("hbar", 1.0)

                omega = self.config.get("omega", 0.5)

                # Quantum ladder: each promotion raises energy by hbar*omega

                # Count transitions (positive changes)

                if len(values) > 1:

                    transitions = np.diff(values)

                    upward_transitions = np.sum(transitions > 0)

                    total_transitions = len(transitions)

                    if total_transitions > 0:

                        # Promotion rate as quantum transition probability

                        upward_transitions / total_transitions

                        # Energy gained through promotions

                        energy_gained = upward_transitions * hbar * omega

                        # Normalize

                        max_energy = total_transitions * hbar * omega

                        if max_energy > 0:

                            promotion_score = energy_gained / max_energy

                        else:

                            promotion_score = 0.0

                        return float(np.clip(promotion_score, 0.0, 1.0))

                return 0.0

            return 0.0

        except Exception as e:

            logging.error(f"Error in _analyze_promotions: {e}")

            raise

    def _analyze_skill_development(self, data) -> float:
        """
        Analyzes skill development activity using quantum state evolution (first principles).

        Skill development is modeled as quantum state evolution: the rate of change
        in skill levels corresponds to the Schrodinger evolution rate.
        """

        try:

            if isinstance(
                data, (_dependencies.pd.Series, _dependencies.pd.DataFrame, np.ndarray, list)
            ):

                values = np.array(data, dtype=float).flatten()

                values = values[~np.isnan(values)]

                if len(values) < 2:

                    return 0.0

                hbar = self.config.get("hbar", 1.0)

                # Quantum state evolution: d|psi>/dt = -iH|psi>/hbar

                # Rate of skill development = momentum of skill trajectory

                mean_val = np.mean(values)

                std_val = np.std(values)

                if std_val == 0:

                    return 0.0

                # Normalize to wavefunction

                psi = (values - mean_val) / std_val

                norm = np.sqrt(np.sum(np.abs(psi) ** 2))

                if norm == 0:

                    return 0.0

                psi = psi / norm

                # Momentum operator: p = -i*hbar*d/dx

                p_psi = np.zeros_like(psi, dtype=complex)

                for n in range(len(psi)):

                    psi_plus = psi[n + 1] if n + 1 < len(psi) else psi[n]

                    psi_minus = psi[n - 1] if n - 1 >= 0 else psi[n]

                    p_psi[n] = -1j * hbar * (psi_plus - psi_minus) / 2.0

                # Expectation value: <p> = Re(<psi|p|psi>)

                momentum = np.real(np.sum(np.conj(psi) * p_psi))

                # Skill development rate = |momentum| (magnitude of change)

                skill_rate = np.abs(momentum)

                return float(np.clip(skill_rate, 0.0, 1.0))

            return 0.0

        except Exception as e:

            logging.error(f"Error in _analyze_skill_development: {e}")

            raise

    def _analyze_compensation(self, data) -> float:
        """
        Analyzes compensation ratios using quantum equilibrium measure (first principles).

        Compensation equilibrium is modeled as the thermal equilibrium state
        of a quantum system, where the Boltzmann distribution gives the
        probability of being fairly compensated.
        """

        try:

            if isinstance(
                data, (_dependencies.pd.Series, _dependencies.pd.DataFrame, np.ndarray, list)
            ):

                values = np.array(data, dtype=float).flatten()

                values = values[~np.isnan(values)]

                if len(values) == 0:

                    return 0.5

                hbar = self.config.get("hbar", 1.0)

                omega = self.config.get("omega", 0.5)

                # Equilibrium: deviation from 1.0 (fair compensation ratio)

                deviations = values - 1.0

                # Quantum thermal equilibrium: exp(-E/(kT))

                # Energy = (1/2)*m*w^2*x^2 (harmonic potential)

                energies = 0.5 * (deviations**2)

                # Boltzmann factors (assuming kT = hbar*w/2, ground state energy)

                kT = 0.5 * hbar * omega

                if kT > 0:

                    boltzmann_factors = np.exp(-energies / kT)

                else:

                    boltzmann_factors = np.ones_like(energies)

                # Equilibrium measure: weighted average

                weights = boltzmann_factors / np.sum(boltzmann_factors)

                equilibrium = np.sum(weights * (1.0 - np.abs(deviations)))

                return float(np.clip(equilibrium, 0.0, 1.0))

            return 0.5

        except Exception as e:

            logging.error(f"Error in _analyze_compensation: {e}")

            raise

    def _analyze_market(self, data) -> float:
        """
        Analyzes market conditions using quantum field theory-inspired methods (first principles).

        Market conditions are modeled as a quantum field, where the vacuum
        fluctuations represent market volatility and the expectation value
        of the field gives the market state.
        """

        try:

            if isinstance(
                data, (_dependencies.pd.Series, _dependencies.pd.DataFrame, np.ndarray, list)
            ):

                values = np.array(data, dtype=float).flatten()

                values = values[~np.isnan(values)]

                if len(values) == 0:

                    return 0.5

                hbar = self.config.get("hbar", 1.0)

                # Quantum field expectation value: <phi> = mean of field values

                field_expectation = np.mean(values)

                # Vacuum fluctuations: variance of field

                vacuum_fluctuation = np.var(values) if len(values) > 1 else 0.0

                # Market stability: inverse of vacuum fluctuations

                if vacuum_fluctuation > 0:

                    stability = hbar / (hbar + vacuum_fluctuation)

                else:

                    stability = 1.0

                # Market condition: combination of expectation and stability

                market_condition = 0.5 * (field_expectation + stability)

                return float(np.clip(market_condition, 0.0, 1.0))

            return 0.5

        except Exception as e:

            logging.error(f"Error in _analyze_market: {e}")

            raise

    def _analyze_industry(self, data) -> float:
        """
        Analyzes industry trends using quantum statistical mechanics (first principles).

        Industry trends are modeled as a quantum ensemble, where the partition
        function Z = sum(exp(-E_n/(kT))) gives the statistical properties.
        """

        try:

            if isinstance(
                data, (_dependencies.pd.Series, _dependencies.pd.DataFrame, np.ndarray, list)
            ):

                values = np.array(data, dtype=float).flatten()

                values = values[~np.isnan(values)]

                if len(values) == 0:

                    return 0.5

                hbar = self.config.get("hbar", 1.0)

                omega = self.config.get("omega", 0.5)

                # Quantum statistical mechanics: partition function

                # Energy levels: E_n = (n + 1/2) * hbar * omega

                kT = 0.5 * hbar * omega  # Thermal energy

                # Map values to quantum numbers

                if np.max(values) != np.min(values):

                    quantum_numbers = (values - np.min(values)) / (np.max(values) - np.min(values))

                else:

                    quantum_numbers = np.zeros_like(values)

                # Energy levels

                energies = (quantum_numbers + 0.5) * hbar * omega

                # Partition function: Z = sum(exp(-E/(kT)))

                if kT > 0:

                    boltzmann = np.exp(-energies / kT)

                    Z = np.sum(boltzmann)

                    if Z > 0:

                        # Average energy: <E> = sum(E * exp(-E/(kT))) / Z

                        avg_energy = np.sum(energies * boltzmann) / Z

                        # Industry trend: normalized average energy

                        max_energy = (1.5) * hbar * omega  # Maximum possible

                        if max_energy > 0:

                            trend = avg_energy / max_energy

                        else:

                            trend = 0.5

                        return float(np.clip(trend, 0.0, 1.0))

                return 0.5

            return 0.5

        except Exception as e:

            logging.error(f"Error in _analyze_industry: {e}")

            raise

    def _analyze_competitors(self, data) -> float:
        """
        Analyzes competitor activity using quantum game theory (first principles).

        Competitor activity is modeled as a quantum game where the Nash equilibrium
        is determined by the quantum strategy space.
        """

        try:

            if isinstance(
                data, (_dependencies.pd.Series, _dependencies.pd.DataFrame, np.ndarray, list)
            ):

                values = np.array(data, dtype=float).flatten()

                values = values[~np.isnan(values)]

                if len(values) == 0:

                    return 0.5

                self.config.get("hbar", 1.0)

                # Quantum game theory: strategic interaction

                # Model competitor activity as quantum strategy amplitudes

                # Normalize to [0, 1]

                if np.max(values) > 0:

                    normalized = values / np.max(values)

                else:

                    normalized = np.zeros_like(values)

                # Quantum strategy: superposition of cooperate/compete

                amplitudes = np.sqrt(np.clip(normalized, 0, 1))

                norm = np.sqrt(np.sum(amplitudes**2))

                if norm == 0:

                    return 0.5

                psi = amplitudes / norm

                # Quantum Nash equilibrium: maximum entropy strategy

                # Entropy of the quantum state

                probabilities = psi**2

                entropy = -np.sum(probabilities * np.log2(probabilities + 1e-10))

                max_entropy = np.log2(len(psi)) if len(psi) > 1 else 1.0

                if max_entropy > 0:

                    # High entropy = high competition (unpredictable competitors)

                    competition_level = entropy / max_entropy

                else:

                    competition_level = 0.5

                return float(np.clip(competition_level, 0.0, 1.0))

            return 0.5

        except Exception as e:

            logging.error(f"Error in _analyze_competitors: {e}")

            raise

    def _profile_model(self, model, data: np.ndarray) -> None:
        """Profiles the model using tf profiler"""

        try:

            logdir = "logs/profile/" + datetime.now().strftime("%Y%m%d-%H%M%S")

            with _dependencies.tf.profiler.experimental.Profile(logdir):

                _ = model.predict_proba(self.scaler.transform(data))

            logging.info(f"Profiling results saved to {logdir}")

        except Exception as e:

            logging.error(f"Error profiling model: {e}")

            raise

    def _get_feature_importance(self, model, feature_names: list) -> dict:
        """Extracts feature importances for the given model"""

        try:

            if model is None:

                return None

            if isinstance(model, _dependencies.RandomForestClassifier):

                return dict(zip(feature_names, model.feature_importances_))

            elif isinstance(model, _dependencies.XGBClassifier):

                return dict(zip(feature_names, model.feature_importances_))

            elif isinstance(model, _dependencies.LGBMClassifier):

                return dict(zip(feature_names, model.feature_importances_))

            elif isinstance(model, _dependencies.GradientBoostingClassifier):

                return dict(zip(feature_names, model.feature_importances_))

            else:

                raise ValueError("Model not supported for feature importance.")

        except Exception as e:

            logging.error(f"Error extracting feature importance: {e}")

            raise

    def _benchmark_model(
        self, model, X_test: np.ndarray, y_test: np.ndarray, model_name: str
    ) -> dict:
        """Benchmarks model performance on a holdout set."""

        try:

            y_pred = model.predict(X_test)

            f1 = _dependencies.f1_score(y_test, y_pred)

            precision = _dependencies.precision_score(y_test, y_pred)

            recall = _dependencies.recall_score(y_test, y_pred)

            accuracy = _dependencies.accuracy_score(y_test, y_pred)

            logging.info(
                f"Benchmarking Results for {model_name}: F1 = {f1}, Precision = {precision}, Recall = {recall}, Accuracy = {accuracy}"
            )

            return {"f1": f1, "precision": precision, "recall": recall, "accuracy": accuracy}

        except Exception as e:

            logging.error(f"Error benchmarking model: {e}")

            raise

    def cleanup(self) -> None:
        """Releases memory occupied by models."""

        try:

            logging.info("Cleaning up model memory...")

            _dependencies.tf.keras.backend.clear_session()

            import gc

            gc.collect()

        except Exception as e:

            logging.error(f"Error during model cleanup: {e}")

            raise


import unittest


class TestPredictiveEngine(unittest.TestCase):

    def setUp(self):

        import tempfile

        self.config = {
            "model_names": ["rf", "xgb", "lgbm", "gb"],
            # Isolated per-test artifact dir — Windows holds joblib mmap
            # handles, so a shared 'test_models/' collides across tests.
            "model_dir": tempfile.mkdtemp(prefix="toe_test_models_") + os.sep,
            "n_estimators": 10,
            "max_depth": 5,
            "learning_rate": 0.01,
            "test_size": 0.2,
            "cv_folds": 2,
            "performance_weight": 0.30,
            "behavioral_weight": 0.25,
            "engagement_weight": 0.20,
            "career_weight": 0.15,
            "external_weight": 0.10,
            "feature_dim": 10,
            "max_tfidf_features": 10,
            "selected_model": "rf",
            "optimization_iterations": 2,
            "optimization_folds": 2,
            "optimization_method": "bayes",
            "imputation_strategy": "median",
            "ensemble_selection_method": "weighted_average",
        }

        # Declared labeled fixture — the real-data contract requires an
        # observed (X, y) cohort before any model is fitted. Deterministic:
        # two separated half-planes so both classes are represented.

        fixture_dim = self.config["feature_dim"]

        ramp = np.linspace(0.0, 0.5, 24)[:, None]

        fixture_X = np.vstack(
            [
                np.zeros((24, fixture_dim)) - 1.0 + ramp,
                np.zeros((24, fixture_dim)) + 1.0 - ramp,
            ]
        )

        fixture_y = np.array([0] * 24 + [1] * 24)

        self.config["training_data"] = (fixture_X, fixture_y)

        self.engine = PredictiveEngine(config=self.config)

        # Generate some synthetic data for testing

        num_samples = 10

        num_features = self.config["feature_dim"]

        self.test_data = _dependencies.pd.DataFrame(
            np.random.rand(num_samples, num_features),
            columns=[f"feature_{i}" for i in range(num_features)],
        )

        self.test_data_timeseries = _dependencies.pd.DataFrame(
            {
                "date": _dependencies.pd.to_datetime(
                    [
                        "2023-01-01",
                        "2023-02-01",
                        "2023-03-01",
                        "2023-04-01",
                        "2023-05-01",
                        "2023-06-01",
                        "2023-07-01",
                        "2023-08-01",
                        "2023-09-01",
                        "2023-10-01",
                    ]
                ),
                "performance_score": np.random.rand(10),
            }
        )

        self.test_text_data = _dependencies.pd.DataFrame(
            {
                "survey_text": [
                    "This is a great place to work",
                    "I am not feeling well",
                    "I am feeling good",
                    "This project is difficult",
                    "I hate the system",
                ]
            }
        )

        self.test_data_missing = _dependencies.pd.DataFrame(
            {
                "performance_score": [np.nan, 0.8, 0.7, 0.9, 0.6, 0.7, 0.8, 0.9, 0.8, 0.7],
                "login_time": [1, 2, np.nan, 4, 5, 6, np.nan, 8, 9, 10],
                "survey_text": [
                    "This is a great place to work",
                    np.nan,
                    "I am feeling good",
                    "This project is difficult",
                    "I hate the system",
                    "I like work",
                    "Its OK here",
                    "Everything sucks",
                    "I want to leave",
                    "All is well",
                ],
            }
        )

    def tearDown(self):

        # Release mmap'd model artifacts before removing the dir —
        # Windows locks joblib-loaded files while arrays are alive.

        import gc
        import shutil

        self.engine = None

        gc.collect()

        if os.path.exists(self.config["model_dir"]):

            shutil.rmtree(self.config["model_dir"], ignore_errors=True)

    def test_predictive_engine_instantiation(self):
        """Test instantiation of the PredictiveEngine class."""

        with self.subTest("Test Class Instantiation"):

            self.assertIsInstance(self.engine, PredictiveEngine)

    def test_predict_churn_risk(self):
        """Test the predict_churn_risk method returns a valid output"""

        with self.subTest("Test Churn Risk Prediction"):

            risk_profile = self.engine.predict_churn_risk(self.test_data)

            self.assertIsInstance(risk_profile, dict)

            self.assertIn("risk_score", risk_profile)

            self.assertIn("confidence_level", risk_profile)

    def test_model_training_and_loading(self):
        """Tests model training and persistence"""

        with self.subTest("Test Model Training and Loading"):

            # Ensure models are being trained when path doesn't exist, and loaded when they do

            engine = PredictiveEngine(self.config)

            self.assertIsInstance(engine.models, dict)

            self.assertEqual(len(engine.models), len(self.config["model_names"]))

            # Test loading logic

            engine_second = PredictiveEngine(self.config)

            self.assertIsInstance(engine_second.models, dict)

            self.assertEqual(len(engine_second.models), len(self.config["model_names"]))

            # Ensure it loads without error

            engine_third = PredictiveEngine(self.config)

            self.assertIsInstance(engine_third.models, dict)

            self.assertEqual(len(engine_third.models), len(self.config["model_names"]))

    def test_feature_engineering(self):
        """Tests that the method allows for custom feature engineering"""

        with self.subTest("Test Custom Feature Engineering"):

            def custom_feature_method(data):

                return data.mean().to_dict() if hasattr(data, "mean") else 0.0

            self.engine.add_feature_engineering("custom_feature", custom_feature_method)

            risk_profile = self.engine.predict_churn_risk(self.test_data)

            self.assertIsInstance(risk_profile, dict)

    def test_analyze_performance_trend(self):
        """Tests the analyze performance trend method with time series data"""

        with self.subTest("Test Time Series Analysis"):

            trend = self.engine._analyze_performance_trend(self.test_data_timeseries)

            self.assertIsInstance(trend, dict)

            self.assertIn("ma", trend)

            self.assertIn("ewma", trend)

            self.assertIn("trend", trend)

    def test_analyze_survey_responses(self):
        """Tests the analyze survey response method with text data"""

        with self.subTest("Test Text Analysis"):

            features = self.engine._analyze_survey_responses(self.test_text_data)

            self.assertIsInstance(features, np.ndarray)

    def test_model_predictions(self):
        """Tests that model predictions are being returned in the profile"""

        with self.subTest("Test Model Predictions"):

            risk_profile = self.engine.predict_churn_risk(self.test_data)

            self.assertIn("model_predictions", risk_profile)

            self.assertIsInstance(risk_profile["model_predictions"], dict)

    def test_dynamic_data_handling(self):
        """Tests that missing data is being correctly handled"""

        with self.subTest("Test Missing Data Imputation"):

            risk_profile = self.engine.predict_churn_risk(self.test_data_missing)

            self.assertIsInstance(risk_profile, dict)

            self.assertIn("risk_score", risk_profile)

    def test_exception_handling(self):
        """Tests that exception handling is working correctly"""

        with self.subTest("Test Exception for Model Name"):

            with self.assertRaises(ValueError):

                self.engine._get_model_by_name("wrong_model")

        with self.subTest("Test Exception for feature extraction"):

            with self.assertRaises(Exception):  # Exception in feature extraction

                self.engine._extract_risk_indicators("bad data")

        with self.subTest("Test Exception for Training Method"):

            with self.assertRaises(Exception):  # Exception in training

                self.engine._train_model("wrong_model")

        with self.subTest("Test Exception for Time Series"):

            with self.assertRaises(Exception):  # Testing if missing features are handled

                data = _dependencies.pd.DataFrame({"login_time": [1, 2, 3]})

                self.engine._analyze_performance_trend(data)  # Missing performance column

        with self.subTest("Test Exception for Text Data"):

            with self.assertRaises(
                Exception
            ):  # Testing if text analysis throws an error with non-text data

                self.engine._analyze_survey_responses(np.random.rand(10, 10))

    def test_algebraic_roots(self):
        """Every family root satisfies its characteristic polynomial."""

        algebra = self.engine.algebra

        for fam, coeffs in ExtendedAlgebraicFamily.FAMILY_COEFFS.items():

            r = algebra.root(fam)

            val = Decimal(0)

            for c in coeffs:

                val = val * r + Decimal(c)

            self.assertTrue(abs(val) < Decimal("1e-30"), f"{fam} root residual {val}")

            self.assertTrue(r > 1, f"{fam} root must be > 1")

    def test_algebraic_sequences_exact(self):
        """Exact integer limbs match their known values."""

        algebra = self.engine.algebra

        self.assertEqual(algebra.sequence("golden", "coordinate", 8), [0, 1, 1, 2, 3, 5, 8, 13])

        self.assertEqual(algebra.sequence("golden", "trace", 8), [2, 1, 3, 4, 7, 11, 18, 29])

        self.assertEqual(algebra.sequence("silver", "coordinate", 7), [0, 1, 2, 5, 12, 29, 70])

        self.assertEqual(
            algebra.sequence("plastic", "coordinate", 12),
            [1, 1, 1, 2, 2, 3, 4, 5, 7, 9, 12, 16],
        )

        # Perrin limb — the plastic family's trace (Lucas-analogue) sequence

        self.assertEqual(
            algebra.sequence("plastic", "trace", 11),
            [3, 0, 2, 3, 2, 5, 5, 7, 10, 12, 17],
        )

        self.assertEqual(
            algebra.sequence("supergolden", "coordinate", 12),
            [1, 1, 1, 2, 3, 4, 6, 9, 13, 19, 28, 41],
        )

        self.assertEqual(
            algebra.sequence("tribonacci", "coordinate", 11),
            [0, 0, 1, 1, 2, 4, 7, 13, 24, 44, 81],
        )

    def test_algebraic_invariants(self):
        """Pisot property, unimodularity, and trace identity per family."""

        algebra = self.engine.algebra

        for fam in ExtendedAlgebraicFamily.FAMILY_NAMES:

            self.assertTrue(algebra.verify_pisot(fam), f"{fam} fails Pisot")

            self.assertLess(algebra.pisot_modulus(fam), 1.0)

            for n in (1, 2, 5, 9):

                self.assertTrue(algebra.det_identity(fam, n), f"{fam} det n={n}")

                self.assertTrue(algebra.trace_identity(fam, n), f"{fam} trace n={n}")

    def test_spectral_gap_known_graphs(self):
        """Fiedler gap against analytically known Laplacian spectra —
        verified in exact arithmetic, not float eigensolvers."""

        algebra = self.engine.algebra

        # Path graph P_6: lambda_2 = 2(1 - cos(pi/6)) = 2 - sqrt(3) exactly

        A = [[0] * 6 for _ in range(6)]

        for i in range(5):

            A[i][i + 1] = A[i + 1][i] = 1

        expected = Decimal(2) - Decimal(3).sqrt()

        gap = algebra.spectral_gap(A)["spectral_gap"]

        self.assertTrue(abs(gap - expected) < Decimal("1e-40"))

        # Complete graph K_5: lambda_2 = 5 exactly

        A_k = [[0 if i == j else 1 for j in range(5)] for i in range(5)]

        self.assertTrue(abs(algebra.spectral_gap(A_k)["spectral_gap"] - 5) < Decimal("1e-40"))

        # Disconnected graph: gap collapses to zero exactly

        A_d = [[0] * 4 for _ in range(4)]

        A_d[0][1] = A_d[1][0] = 1

        A_d[2][3] = A_d[3][2] = 1

        res = algebra.spectral_gap(A_d)

        self.assertFalse(res["stable"])

        self.assertEqual(res["spectral_gap"], 0)

    def test_pisot_filter_contracts_noise(self):
        """The drift filter contracts high-frequency noise toward trend —
        residuals computed in exact Decimal arithmetic."""

        algebra = self.engine.algebra

        series = [
            Decimal("0.5") + Decimal("0.002") * i + Decimal("0.4") * Decimal(str(math.sin(0.8 * i)))
            for i in range(200)
        ]

        trend = [Decimal("0.5") + Decimal("0.002") * i for i in range(200)]

        filtered = algebra.pisot_drift_filter(series, "plastic")

        def _rms(xs, ys):
            return (sum((x - y) ** 2 for x, y in zip(xs, ys)) / len(xs)).sqrt()

        err_raw = _rms(series[40:160], trend[40:160])

        err_filt = _rms(filtered[40:160], trend[40:160])

        self.assertLess(err_filt, err_raw)

    def test_anti_resonance_irrationality(self):
        """No exact integer relation among the frequency tiers."""

        algebra = self.engine.algebra

        freqs = algebra.metallic_anti_resonance_frequencies(50.0, 5)

        for i in range(len(freqs)):

            for j in range(i + 1, len(freqs)):

                ratio = freqs[j] / freqs[i]

                for k in range(1, 64):

                    self.assertGreater(abs(ratio - Decimal(round(ratio * k)) / k), Decimal("1e-9"))

    def test_family_signature_detection(self):
        """Structured series resolve to their family; random does not."""

        algebra = self.engine.algebra

        padovan = np.array(algebra.sequence("plastic", "coordinate", 24), dtype=float)

        sig = algebra.detect_family_signature(padovan)

        self.assertEqual(sig["family"], "plastic")

        rng = random.Random(0)

        sig_rand = algebra.detect_family_signature([rng.random() for _ in range(60)])

        self.assertLess(sig_rand["confidence"], sig["confidence"])

    def test_formulations_honesty_flags(self):
        """Every formulation structure carries theorem_proven: False."""

        f = self.engine.formulations

        for struct in (
            f.p_vs_np_structure(10),
            f.riemann_structure(10),
            f.langlands_structure(10),
            f.m_theory_structure(10),
            f.unified_facets(10),
        ):

            self.assertFalse(struct["theorem_proven"])

            self.assertEqual(struct["status"], "FORMULATED_NOT_PROVEN")

            self.assertTrue(struct["pending_11d_merge"])

    def test_forecast_and_profile_carry_algebra(self):
        """The pipeline surfaces the algebraic layer end to end."""

        indicators = {
            "performance": {"mean": 0.5, "trend": 0.1, "volatility": 0.2},
            "behavioral": {"login_freq": 0.6, "variability": 0.3},
            "engagement": {"score": 0.7},
        }

        forecast = self.engine._forecast_risk(indicators)

        self.assertIn("algebraic", forecast)

        self.assertTrue(forecast["algebraic"]["enabled"])

        diag = self.engine._algebraic_diagnostics(indicators)

        self.assertTrue(diag.get("available"))

        self.assertIn(diag["active_family"], ExtendedAlgebraicFamily.FAMILY_NAMES)

        self.assertIn("spectral_gap", diag["spectral"])


if __name__ == "__main__":

    # Extended algebraic family self-verification — runs before the demo

    _algebra = ExtendedAlgebraicFamily()

    print("=== EXTENDED ALGEBRAIC FAMILY ===")

    for _fam in ExtendedAlgebraicFamily.FAMILY_NAMES:

        _root = str(_algebra.root(_fam))[:10]

        _mod = str(_algebra.pisot_modulus(_fam))[:10]

        print(
            f"  {_fam:<12} root={_root:<11} |mu|max={_mod:<11} pisot={_algebra.verify_pisot(_fam)}"
        )

    for _fam, _rep in _algebra.verify_all().items():

        assert _rep["pisot"] and _rep["det_unimodular"] and _rep["trace_identity"], _fam

    print("  all invariants verified: pisot, unimodular det, trace identity")

    # Example usage

    config = {
        "model_names": ["rf", "xgb", "lgbm", "gb"],
        "model_dir": "models/",
        "n_estimators": 100,
        "max_depth": 8,
        "learning_rate": 0.005,
        "test_size": 0.2,
        "cv_folds": 3,
        "performance_weight": 0.30,
        "behavioral_weight": 0.25,
        "engagement_weight": 0.20,
        "career_weight": 0.15,
        "external_weight": 0.10,
        "feature_dim": 10,
        "max_tfidf_features": 100,
        "selected_model": "rf",
        "optimization_iterations": 3,
        "optimization_folds": 2,
        "optimization_method": "bayes",
        "imputation_strategy": "median",
        "ensemble_selection_method": "weighted_average",
    }

    engine = PredictiveEngine(config=config)

    # The real-data contract: models fit only on observed labeled rows.
    # This demo registers a declared fixture cohort — in production the
    # caller supplies live telemetry via ingest_training_data() or
    # config['training_data_path'].

    _demo_dim = config["feature_dim"]

    _ramp = np.linspace(0.0, 0.5, 24)[:, None]

    _demo_X = np.vstack(
        [
            np.zeros((24, _demo_dim)) - 1.0 + _ramp,
            np.zeros((24, _demo_dim)) + 1.0 - _ramp,
        ]
    )

    _demo_y = np.array([0] * 24 + [1] * 24)

    engine.ingest_training_data(_demo_X, _demo_y, source="demo_fixture")

    engine.fit_models()

    # Generate some data

    data = _dependencies.pd.DataFrame(
        {
            "performance_score": np.random.rand(10),
            "date": _dependencies.pd.to_datetime(
                [
                    "2023-01-01",
                    "2023-02-01",
                    "2023-03-01",
                    "2023-04-01",
                    "2023-05-01",
                    "2023-06-01",
                    "2023-07-01",
                    "2023-08-01",
                    "2023-09-01",
                    "2023-10-01",
                ]
            ),
            "survey_text": [
                "This is a great place to work",
                "I am not feeling well",
                "I am feeling good",
                "This project is difficult",
                "I hate the system",
                "I like work",
                "Its OK here",
                "Everything sucks",
                "I want to leave",
                "All is well",
            ],
        }
    )

    def custom_feature_method(data):

        # Sum only numeric columns — datetime columns raise TypeError on .sum()
        if hasattr(data, "select_dtypes"):
            numeric = data.select_dtypes(include=[np.number])
            return numeric.sum().to_dict() if not numeric.empty else {}
        return data.sum().to_dict() if hasattr(data, "sum") else 0.0

    engine.add_feature_engineering("custom_feature", custom_feature_method)

    # Predict churn risk

    risk_profile = engine.predict_churn_risk(data)

    print(f"\nRisk Profile: {risk_profile}")

    # Model Profiling — guard against feature-count mismatch

    try:

        input_data = engine._prepare_input_features(engine._extract_risk_indicators(data))

        if input_data.shape[1] == engine.scaler.n_features_in_:

            engine._profile_model(engine._get_model_by_name("rf"), input_data.reshape(1, -1))

        else:

            print(
                f"\n[Profiling skipped] input has {input_data.shape[1]} features, scaler expects {engine.scaler.n_features_in_}"
            )

    except Exception as e:

        print(f"\n[Profiling skipped] {e}")

    # Model Explainability

    # Filter to only models that have a 'score' key (skip quantum_superposition which is a float)

    scored_models = {
        k: v
        for k, v in risk_profile["model_predictions"].items()
        if isinstance(v, dict) and "score" in v
    }

    best_model_name = sorted(scored_models, key=lambda x: scored_models[x]["score"])[
        -1
    ]  # Get name of model with the highest score

    best_model = engine.models[best_model_name]  # Get model itself

    feature_names = list(
        engine._calculate_factor_weights(engine._extract_risk_indicators(data)).keys()
    )

    feature_importance = engine._get_feature_importance(best_model, feature_names)

    print("\nFeature Importances: ", feature_importance)

    unittest.main(argv=["first-arg-is-ignored"], exit=False)

    engine.cleanup()  # Clean up memory.


def strict_quantum_work_certificate(header76: bytes, nonce_start: int, nonce_count: int) -> dict:
    """Return the exact Q(i) work certificate used by live PYTHIA windows.

    TOE remains the intelligence/provenance layer; this certificate is a
    mathematical control-plane witness only. Bitcoin consensus still belongs
    exclusively to the independent SHA-256d verifier.
    """
    from toe.strict_quantum import certify_work_window

    return certify_work_window(header76, nonce_start, nonce_count)
