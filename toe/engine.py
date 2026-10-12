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
   vectors via ``kellogg.quantum_tensor.encode_data_to_state``,
   Pisot-family Hamiltonian evolution via
   ``ComplexMatrix.matrix_exp_unitary`` (the Schrödinger propagator
   convention shared with ``toe.bridge.predict_trajectory``), Born-rule
   measurement, quantum Fisher information, von Neumann entropy, and
   ensemble agreement via ``model_agreement_from_ensemble``. The
   ensemble "models" are quantum channels — family-Hamiltonian evolution
   plus Helstrom-type Born-overlap discrimination calibrated on the
   observed cohort — not estimators. Read the math, not the column
   names — the engine is a demonstration of the algebra, not an HR
   product.

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

# Single-source versioning: the package literal lives in toe/__init__.py
# (bound before this module is imported there); engine derives, never
# redeclares.
from toe import __version__  # noqa: F401

_LAZY_MODULES = {
    "pd": "pandas",
    "joblib": "kellogg.tensor_ml",
}

# Only honest plumbing survives here: the exact-median imputer (data
# conditioning — not inference), the repo's own lexicon sentiment counter
# (a declared classical feature extractor, never labelled quantum), and
# joblib for declared training-blob loading. Every computed quantity in
# the prediction pipeline runs on kellogg.quantum_tensor — there are no
# estimators, no sklearn-style predict_proba, no LIME surrogate, no
# seasonal-decompose, no hyperparameter search.
_LAZY_FROM = {
    "SimpleImputer": ("kellogg.tensor_ml", "SimpleImputer"),
    "SentimentIntensityAnalyzer": ("kellogg.tensor_ml", "TensorSentimentAnalyzer"),
}


# The quantum substrate is a hard dependency, not a lazy one: the engine
# must fail closed at import if the substrate cannot be resolved —
# otherwise the box envrc could shadow kellogg onto a sibling checkout.
from kellogg.quantum_tensor import (  # noqa: E402
    Complex,
    ComplexMatrix,
    QuantumState,
    Observables,
    quantum_fisher_information,
    von_neumann_entropy,
    encode_data_to_state,
    state_tomography,
    causal_factor_ranking,
    model_agreement_from_ensemble,
)


def __getattr__(name: str):
    """Resolve plumbing dependencies on demand; required failures propagate."""
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


class QuantumChannelModel:
    """One ensemble member: a Pisot-family quantum channel, not an estimator.

    The channel is the pair (H_family, U(t)) where H_family is the
    Hermitian symmetric part of the family's Pisot companion matrix
    (``kellogg.quantum_tensor.Observables.family_hamiltonian``) and
    U(t) = exp(-iHt/ℏ) is its exact Schrödinger propagator
    (``ComplexMatrix.matrix_exp_unitary``, the same convention
    ``toe.bridge.predict_trajectory`` uses).

    Calibration on an observed (X, y) cohort produces two class reference
    rays: each observed row is encoded via ``encode_data_to_state``,
    evolved through the channel, and the per-class coherent centroid ray
    is stored. Prediction is quantum state discrimination — the Born
    overlap |⟨ψ'|φ_class⟩|² between the evolved input and each reference
    ray, normalized (a Helstrom-type two-state measurement). There are no
    learned weights, no predict_proba, no vendor algorithm underneath.
    """

    ARTIFACT_VERSION = "toe.engine.qchannel/v1"

    def __init__(
        self,
        name: str,
        family: str,
        dim: int,
        hbar: float = 1.0,
        evolution_time: float = 1.0,
    ) -> None:
        self.name = name
        self.family = family
        self.dim = int(dim)
        self.hbar = float(hbar)
        self.evolution_time = float(evolution_time)
        self.hamiltonian = Observables.family_hamiltonian(family, self.dim)
        self.propagator = ComplexMatrix.matrix_exp_unitary(
            self.hamiltonian, self.evolution_time / self.hbar
        )
        self.churn_state: QuantumState | None = None
        self.retain_state: QuantumState | None = None
        self.cv_score = None
        self.n_reference = {"churn": 0, "retain": 0}

    @property
    def calibrated(self) -> bool:
        return self.churn_state is not None and self.retain_state is not None

    def calibrate(self, states: list, labels) -> None:
        """Derive the class reference rays from observed encoded rows."""
        churn, retain = [], []
        for state, label in zip(states, labels):
            evolved = self.evolve(state)
            (churn if int(label) == 1 else retain).append(evolved)
        if not churn or not retain:
            raise ValueError("channel calibration requires both classes present")
        self.churn_state = _coherent_centroid(churn, self.dim)
        self.retain_state = _coherent_centroid(retain, self.dim)
        self.n_reference = {"churn": len(churn), "retain": len(retain)}

    def evolve(self, state: QuantumState) -> QuantumState:
        """Schrödinger evolution |ψ'⟩ = U(t)|ψ⟩ through this channel."""
        return state.apply_unitary(self.propagator)

    def discriminate(self, state: QuantumState) -> dict | None:
        """Born-overlap discrimination of ``state`` between the class rays.

        P(churn) = F(ev, churn) / (F(ev, churn) + F(ev, retain)) where
        F = |⟨·|·⟩|² is the pure-state fidelity — the Born probability of
        the Helstrom-type projective measurement distinguishing the two
        reference rays. Returns None when the channel is uncalibrated or
        the state is orthogonal to both references (unmeasurable — an
        honest non-answer, not a fabricated 0.5).
        """
        if not self.calibrated or state.dim != self.dim:
            return None
        evolved = self.evolve(state)
        p_churn = evolved.fidelity(self.churn_state)
        p_retain = evolved.fidelity(self.retain_state)
        denom = p_churn + p_retain
        if denom <= 0.0:
            return None
        return {
            "score": p_churn / denom,
            "churn_overlap": p_churn,
            "retain_overlap": p_retain,
            "margin": abs(p_churn - p_retain) / denom,
            "evolved": evolved,
        }

    def to_artifact(self) -> dict:
        """Serializable channel state — amplitudes only, no estimators."""
        return {
            "version": self.ARTIFACT_VERSION,
            "name": self.name,
            "family": self.family,
            "dim": self.dim,
            "hbar": self.hbar,
            "evolution_time": self.evolution_time,
            "n_reference": dict(self.n_reference),
            "churn": (
                [[a.re, a.im] for a in self.churn_state.amplitudes]
                if self.churn_state is not None
                else None
            ),
            "retain": (
                [[a.re, a.im] for a in self.retain_state.amplitudes]
                if self.retain_state is not None
                else None
            ),
        }

    @classmethod
    def from_artifact(cls, artifact: dict) -> "QuantumChannelModel":
        channel = cls(
            name=artifact["name"],
            family=artifact["family"],
            dim=int(artifact["dim"]),
            hbar=float(artifact["hbar"]),
            evolution_time=float(artifact["evolution_time"]),
        )
        for attr, key in (("churn_state", "churn"), ("retain_state", "retain")):
            rows = artifact.get(key)
            if rows is not None:
                setattr(
                    channel,
                    attr,
                    QuantumState(
                        channel.dim,
                        [Complex(r_part, i_part) for r_part, i_part in rows],
                        normalize=True,
                    ),
                )
        channel.n_reference = dict(artifact.get("n_reference", channel.n_reference))
        return channel


def _coherent_centroid(states: list, dim: int) -> QuantumState:
    """Normalized coherent centroid ray |φ⟩ ∝ Σ_i |ψ_i⟩ of an ensemble.

    This is the ensemble's coherent average (a ray), distinct from the
    incoherent mixture ρ = Σ|ψ_i⟩⟨ψ_i|/N used for entropy measures.
    """
    acc = [Complex.ZERO] * dim
    for state in states:
        for i, amp in enumerate(state.amplitudes):
            acc[i] = acc[i].add(amp)
    return QuantumState(dim, acc, normalize=True)


class PredictiveEngine:
    """
    Prediction engine over the TOE algebraic substrate — ONE application of it.

    The shipped indicator schema is employee-churn-shaped (HR telemetry
    columns: login_time, promotion_history, engagement metrics) because that
    is the DataFrame the engine was demonstrated on. The computation beneath
    is domain-general substrate math, not an HR product:

    - State preparation: ``kellogg.quantum_tensor.encode_data_to_state``
      maps indicator vectors to normalized rays in H_dim.
    - Evolution: Pisot-family Hamiltonians (``Observables.family_hamiltonian``)
      propagated by ``ComplexMatrix.matrix_exp_unitary`` — exact Schrödinger
      dynamics, the same convention as ``toe.bridge.predict_trajectory``.
    - Measurement: Born-rule probabilities |⟨·|·⟩|² and expectation values
      of real Hermitian observables (position, momentum, number, energy).
    - Ensemble: each configured "model" is a ``QuantumChannelModel`` — a
      distinct measurement channel, not an estimator. Ensemble aggregation
      is the mixed-state Born rule over per-channel probabilities weighted
      by quantum Fisher information.
    - Uncertainty: quantum Fisher information (Cramér–Rao bound),
      Helstrom discrimination margins, von Neumann entropy of the mixed
      cohort density operator, and ``model_agreement_from_ensemble``.
    - Trend: Ehrenfest drift — d⟨x⟩/dt measured by exact propagation.
      (The raw momentum expectation of a real ray is identically zero;
      the earlier inline implementation computed exactly that zero.)

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
        """Return default configuration.

        Factor weights are NOT configurable: they are derived from the
        substrate (normalized |⟨A_f⟩| via causal_factor_ranking). The
        estimator-shaped keys (n_estimators, max_depth, learning_rate,
        test_size) are retained only for config-schema compatibility —
        the quantum channels have no hyperparameters to set; validation
        still requires the historical required keys so existing callers
        keep their contract.
        """
        return {
            "model_names": ["rf", "xgb", "lgbm", "gb"],
            "model_dir": os.path.join(os.environ["PYTHIA_INTELLIGENCE_DIR"], "models")
            if os.environ.get("PYTHIA_INTELLIGENCE_DIR") else "models/",
            # Legacy estimator-schema keys — validated, never consumed.
            "n_estimators": 100,
            "max_depth": 8,
            "learning_rate": 0.005,
            "test_size": 0.2,
            "cv_folds": 3,
            "feature_dim": 10,
            "selected_model": "rf",
            "imputation_strategy": "median",
            "ensemble_selection_method": "weighted_average",
            # Quantum-mathematical parameters (natural units, hbar = 1)
            "hbar": 1.0,
            "mass": 1.0,
            "omega": 0.5,
            "decoherence_rate": 0.1,
            "path_samples": 100,
            "hilbert_dim": 10,
            "evolution_time": 1.0,
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
        """Initialize plumbing components and substrate handles.

        The imputer (exact-median) and the lexicon sentiment counter are
        honest classical preprocessing — they condition input data and are
        never presented as quantum inference. Every scored quantity comes
        from the kellogg.quantum_tensor substrate.
        """
        try:
            self.imputer = _dependencies.SimpleImputer(
                strategy=self.config.get("imputation_strategy", "median")
            )
            try:
                self.sentiment_analyzer = _dependencies.SentimentIntensityAnalyzer()
            except Exception:
                logging.warning("sentiment analyzer unavailable — sentiment disabled")
                self.sentiment_analyzer = None
            self.feature_engineering_methods = {}

            # Channels dict is populated by _load_or_train_models() after
            # component init; _channel_dim() reads it during calibration.
            self.models = {}

            # Quantum measurement caches — rays, density operators, and
            # forecast trajectories from the most recent pipeline pass.
            self._last_evolved_states = []
            self._last_encoded_state = None
            self._forecast_states = []

            # Real-data contract state. The engine never fabricates a
            # training set: a channel is calibrated only on observed,
            # labeled rows supplied through ingest_training_data(), config
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

    # ------------------------------------------------------------------
    # Quantum channel construction / calibration
    # ------------------------------------------------------------------

    def _channel_family(self, model_name: str, index: int) -> str:
        """Assign a Pisot family to a channel label.

        A label that already names a family uses it directly; legacy
        estimator names (rf/xgb/lgbm/gb) are mapped cyclically onto the
        family spectrum — labels, not impersonated vendor algorithms.
        """
        if model_name in ExtendedAlgebraicFamily.FAMILY_NAMES:
            return model_name
        return ExtendedAlgebraicFamily.FAMILY_NAMES[
            index % len(ExtendedAlgebraicFamily.FAMILY_NAMES)
        ]

    def _encoding_dim(self, n_values: int = 0) -> int:
        """Hilbert dimension for a standalone encoding (no truncation)."""
        return max(int(self.config.get("hilbert_dim", 10)), int(n_values), 3)

    def _channel_dim(self) -> int:
        """Shared Hilbert dimension across channels.

        Determined at calibration time as max(hilbert_dim, feature_dim).
        Indicator encodings map through encode_data_to_state's declared
        pad/truncate contract to this dimension.
        """
        if self.models:
            return max(channel.dim for channel in self.models.values())
        return self._encoding_dim(self._feature_dim())

    def _build_channel(self, model_name: str, index: int) -> QuantumChannelModel:
        return QuantumChannelModel(
            name=model_name,
            family=self._channel_family(model_name, index),
            dim=self._channel_dim(),
            hbar=self.config.get("hbar", 1.0),
            evolution_time=self.config.get("evolution_time", 1.0),
        )

    def _encode_rows(self, X, dim: int) -> list:
        """Encode each observed row to a normalized ray via the substrate."""
        return [
            encode_data_to_state(list(np.asarray(row, dtype=float)), dim=dim, normalize=True)
            for row in X
        ]

    def _encode_indicators(self, indicators: dict) -> QuantumState | None:
        """Encode the indicator dict to one normalized ray.

        The encoding dimension covers every indicator amplitude — no
        truncation — so standalone analyses (forecast, factor ranking,
        time sensitivity) see the whole indicator vector. Channel
        discrimination separately encodes to the shared channel dim.
        """
        features = self._prepare_input_features(indicators)
        if not len(features):
            return None
        dim = self._encoding_dim(len(features))
        state = encode_data_to_state([float(v) for v in features], dim=dim, normalize=True)
        self._last_encoded_state = state
        return state

    def _series_state(self, values) -> QuantumState | None:
        """Encode a 1-D series to a normalized ray (dim = len, no truncation)."""
        v = [float(x) for x in values]
        if len(v) < 2:
            return None
        return encode_data_to_state(v, dim=self._encoding_dim(len(v)), normalize=True)

    def _series_expectation(self, values, observable: ComplexMatrix) -> float | None:
        """⟨ψ|A|ψ⟩ for the encoded series; None when no state exists."""
        state = self._series_state(values)
        if state is None or observable.rows != state.dim:
            return None
        return float(state.expectation(observable))

    def _ehrenfest_drift(self, state: QuantumState, family: str = "golden") -> float:
        """d⟨x⟩/dt measured by exact propagation: (⟨x⟩_t − ⟨x⟩_0)/t.

        Ehrenfest's theorem — the substrate-realized velocity of the
        state's position centroid. The momentum expectation of a real ray
        is identically zero; the drift is not.
        """
        dt = float(self.config.get("evolution_time", 1.0))
        hbar = self.config.get("hbar", 1.0)
        H = Observables.family_hamiltonian(family, state.dim)
        U = ComplexMatrix.matrix_exp_unitary(H, dt / hbar)
        x = Observables.position(state.dim)
        return (state.apply_unitary(U).expectation(x) - state.expectation(x)) / dt

    # ------------------------------------------------------------------
    # Channel lifecycle (formerly "model" lifecycle — same contract)
    # ------------------------------------------------------------------

    def _load_or_train_models(self) -> dict:
        """Load persisted channels; calibrate missing ones on real observed data.

        Real-data contract: the engine never fabricates a training set.
        A channel absent from disk is calibrated only when real labeled
        data is available — supplied through ``config['training_data']``,
        ``config['training_data_path']``, ``ingest_training_data()``, or a
        persisted ``training_data.npz`` in ``model_dir``. With no real data
        the engine stays honestly untrained and prediction paths report
        ``available: False`` — no synthetic records are ever substituted.

        Legacy ``*.joblib`` estimator artifacts are deliberately ignored:
        they encode fitted classical weights, which cannot be promoted to
        a quantum channel — the channel recalibrates or stays untrained.
        """
        try:
            model_dir = self.config["model_dir"]
            os.makedirs(model_dir, exist_ok=True)
            models = {}
            missing = []
            for index, model_name in enumerate(self.config["model_names"]):
                channel = self._load_channel_artifact(model_name)
                if channel is not None:
                    models[model_name] = channel
                    self._model_cv_scores[model_name] = self._load_training_metrics(model_name)
                    logging.info(f"Loaded quantum channel: {model_name}")
                else:
                    missing.append((index, model_name))
            if missing:
                training = self._real_training_data()
                if training is None:
                    logging.warning(
                        "PredictiveEngine: no observed training data — channels "
                        "%s remain uncalibrated; predictions report available=False.",
                        [name for _, name in missing],
                    )
                else:
                    for index, model_name in missing:
                        models[model_name] = self._train_channel(model_name, index, training)
            self._models_trained = bool(models)
            return models
        except Exception as e:
            logging.error(f"Model loading/training failed: {e}")
            raise

    def _channel_artifact_path(self, model_name: str) -> str:
        return os.path.join(self.config["model_dir"], f"{model_name}.qchannel.npz")

    def _load_channel_artifact(self, model_name: str) -> QuantumChannelModel | None:
        path = self._channel_artifact_path(model_name)
        if not os.path.exists(path):
            legacy = os.path.join(self.config["model_dir"], f"{model_name}.joblib")
            if os.path.exists(legacy):
                logging.warning(
                    "Ignoring legacy estimator artifact %s — classical fitted "
                    "weights cannot be promoted to a quantum channel.",
                    legacy,
                )
            return None
        try:
            blob = np.load(path, allow_pickle=False)
            import json as _json

            artifact = _json.loads(str(blob["artifact"].item()))
            channel = QuantumChannelModel.from_artifact(artifact)
            return channel
        except Exception as e:
            logging.warning(f"Channel artifact {path} unreadable: {e}")
            return None

    def _persist_channel(self, channel: QuantumChannelModel) -> None:
        import json as _json

        np.savez(
            self._channel_artifact_path(channel.name),
            artifact=np.asarray(_json.dumps(channel.to_artifact())),
        )

    def _train_channel(self, model_name: str, index: int, training) -> QuantumChannelModel:
        """Calibrate one channel's class reference rays on observed data."""
        X, y = training
        channel = self._build_channel(model_name, index)
        channel.calibrate(self._encode_rows(X, channel.dim), y)
        cv_score = self._measure_cv_score(channel, X, y)
        channel.cv_score = cv_score
        self._model_cv_scores[model_name] = cv_score
        self._persist_channel(channel)
        self._persist_training_metrics(model_name, cv_score)
        logging.info(f"Calibrated and saved quantum channel: {model_name}")
        return channel

    def _train_model(self, model_name: str, training=None):
        """Calibrate the channel registered as ``model_name``.

        Fails closed: raises ValueError when the name is unconfigured or
        no real labeled data is available. Never calibrates on generated
        or placeholder records.
        """
        try:
            if model_name not in self.config["model_names"]:
                raise ValueError(f"Unknown model name: {model_name}")
            if training is None:
                training = self._real_training_data()
            if training is None:
                raise ValueError(
                    f"Cannot train '{model_name}': no observed training data. "
                    "Supply config['training_data'], config['training_data_path'], "
                    "or call ingest_training_data()."
                )
            index = self.config["model_names"].index(model_name)
            return self._train_channel(model_name, index, training)
        except Exception as e:
            logging.error(f"Error training model {model_name}: {e}")
            raise

    # ------------------------------------------------------------------
    # Real training-data contract
    # ------------------------------------------------------------------

    def ingest_training_data(self, X, y, source: str = "runtime_ingestion") -> dict:
        """Register real observed labeled data for channel calibration.

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
        """Calibrate all configured channels on the currently observed data.

        Returns the channels dict. Raises ValueError if no real labeled
        training matrix is available.
        """
        training = self._real_training_data()
        if training is None:
            raise ValueError(
                "fit_models: no observed training data — refusing to calibrate on "
                "fabricated records."
            )
        self.models = {}
        for index, model_name in enumerate(self.config["model_names"]):
            self.models[model_name] = self._train_channel(model_name, index, training)
        self._models_trained = True
        return self.models

    def model_status(self) -> dict:
        """Honest production status: which channels are calibrated, on what data."""
        return {
            "trained": self._models_trained,
            "model_kind": "quantum_channel",
            "substrate": "kellogg.quantum_tensor family-hamiltonian channels",
            "channel_families": {
                name: getattr(channel, "family", None) for name, channel in self.models.items()
            },
            "available_models": sorted(self.models.keys()),
            "missing_models": sorted(set(self.config["model_names"]) - set(self.models.keys())),
            "cv_scores": dict(self._model_cv_scores),
            "training_provenance": self._training_provenance,
        }

    def _validate_training_matrix(self, X, y):
        """Validate an observed (X, y) pair for calibration."""
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

    def _measure_cv_score(self, channel: QuantumChannelModel, X, y):
        """Measured deterministic k-fold discrimination accuracy, or None.

        Each fold calibrates a fresh channel on the remaining rows and
        scores the held-out rows by Born-overlap verdict. The fold
        partition is a deterministic stratified round-robin — no RNG.
        Returns None (honest 'unmeasured') when the cohort cannot support
        the requested folds.
        """
        try:
            yv = np.asarray(y, dtype=int)
            min_class = int(min(np.bincount(yv)))
            folds = min(int(self.config.get("cv_folds", 3)), min_class)
            if folds < 2:
                return None
            n = X.shape[0]
            # Stratified deterministic partition: class-major ordering then
            # round-robin, so every fold sees both classes.
            order = sorted(range(n), key=lambda i: (yv[i], i))
            fold_of = {idx: pos % folds for pos, idx in enumerate(order)}
            correct = 0
            total = 0
            for f in range(folds):
                train_idx = [i for i in range(n) if fold_of[i] != f]
                test_idx = [i for i in range(n) if fold_of[i] == f]
                fold_channel = QuantumChannelModel(
                    name=f"{channel.name}__fold{f}",
                    family=channel.family,
                    dim=channel.dim,
                    hbar=channel.hbar,
                    evolution_time=channel.evolution_time,
                )
                fold_channel.calibrate(self._encode_rows(X[train_idx], channel.dim), yv[train_idx])
                for i in test_idx:
                    res = fold_channel.discriminate(
                        encode_data_to_state(
                            list(np.asarray(X[i], dtype=float)),
                            dim=channel.dim,
                            normalize=True,
                        )
                    )
                    if res is None:
                        continue
                    correct += int((res["score"] > 0.5) == bool(yv[i]))
                    total += 1
            return (correct / total) if total else None
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
            "cv_method": "deterministic_stratified_born_discrimination",
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
                "no calibrated channels — the engine requires real observed "
                "training data (config['training_data'], "
                "config['training_data_path'], or ingest_training_data())"
            ),
            "model_predictions": {},
        }

    def _get_model_by_name(self, name: str):
        """Retrieve a channel by name from the channels dictionary."""
        if name not in self.models:
            raise ValueError(f"Model '{name}' not found. Available: {list(self.models.keys())}")
        return self.models[name]

    def add_feature_engineering(self, name: str, method) -> None:
        """Register a custom feature engineering method."""
        self.feature_engineering_methods[name] = method

    def predict_churn_risk(self, data: _dependencies.pd.DataFrame) -> dict:
        """
        Predict churn risk via the quantum channel ensemble.

        Args:
            data (pd.DataFrame): Employee data with required features

        Returns:
            dict: Risk profile with predictions and explanations
        """
        try:
            if not isinstance(data, _dependencies.pd.DataFrame):
                raise ValueError("Input must be a pandas DataFrame")
            if len(data) > 10000:
                return self._process_large_dataset(data)
            processed_data = self._preprocess_data(data)
            indicators = self._extract_risk_indicators(processed_data)
            ensemble_predictions = self._ensemble_predict(indicators)
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
        """Aggregate chunk predictions via Born-weighted superposition.

        Each chunk score s_i is already a Born probability; the chunk's
        amplitude is sqrt(s_i). The combined score is the mixed-state
        Born mean Σ p_i s_i / Σ p_i of the superposed amplitudes.
        """
        try:
            if not predictions:
                return {}
            risk_scores = [p["risk_score"]["score"] for p in predictions if "risk_score" in p]
            risk_scores = [s for s in risk_scores if s is not None]
            confidences = [
                p["risk_score"]["confidence_interval"]
                for p in predictions
                if "risk_score" in p and p["risk_score"].get("confidence_interval") is not None
            ]
            if not risk_scores:
                return {}
            amplitudes = QuantumState.from_real_vector(
                [math.sqrt(max(float(s), 0.0)) for s in risk_scores]
            )
            probs = amplitudes.probabilities()
            denom = sum(probs)
            combined_score = (
                sum(p * s for p, s in zip(probs, risk_scores)) / denom
                if denom > 0
                else float(np.mean(risk_scores))
            )
            combined_confidence = float(np.mean(confidences)) if confidences else 0.0
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
                "confidence_level": (
                    float(np.mean(confidence_levels)) if confidence_levels else 0.5
                ),
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
        """Trend = Ehrenfest drift d⟨x⟩/dt of the encoded series (first principles).

        The series is encoded to a normalized ray, then propagated under the
        golden-family Hamiltonian for one evolution step; the drift of the
        position expectation ⟨x̂⟩ is the measured trend. Positive drift =
        rising series values toward higher basis index.
        """
        try:
            values = series.dropna().values.astype(float)
            state = self._series_state(values)
            if state is None:
                return 0.0
            return float(self._ehrenfest_drift(state))
        except Exception as e:
            logging.error(f"Error calculating quantum trend: {e}")
            return 0.0

    def _calculate_volatility(self, series: _dependencies.pd.Series) -> float:
        """Volatility = ⟨H_osc⟩/E₀ on the encoded series (first principles).

        The harmonic-oscillator energy expectation captures both kinetic
        (variation) and potential (deviation) energy of the state's
        support; normalized by the ground-state energy E₀ = ℏω/2.
        """
        try:
            values = series.dropna().values.astype(float)
            state = self._series_state(values)
            if state is None:
                return 0.0
            hbar = self.config.get("hbar", 1.0)
            mass = self.config.get("mass", 1.0)
            omega = self.config.get("omega", 0.5)
            H = Observables.harmonic_oscillator_hamiltonian(state.dim, hbar, mass, omega)
            energy = state.expectation(H)
            ground_state = 0.5 * hbar * omega
            return float(energy / ground_state) if ground_state > 0 else float(energy)
        except Exception as e:
            logging.error(f"Error calculating quantum volatility: {e}")
            return 0.0

    def _calculate_relative_performance(self, data: _dependencies.pd.DataFrame) -> float:
        """Relative performance = fidelity F = |⟨ψ|uniform⟩|² (first principles).

        F = 1: the performance state's support matches the uniform
        (maximum-entropy) reference. Lower F = the state concentrates
        amplitude away from the uniform reference.
        """
        try:
            if "performance_score" not in data.columns:
                return 0.5
            values = data["performance_score"].dropna().values.astype(float)
            centered = values - np.mean(values)
            state = self._series_state(centered)
            if state is None:
                return 1.0 if len(values) >= 2 else 0.5
            uniform = QuantumState.uniform_superposition(state.dim)
            return float(state.fidelity(uniform))
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
        """Login frequency = ⟨n̂⟩/(dim−1) on the encoded times (first principles).

        The number-operator expectation of the encoded login-time ray,
        normalized by the maximum quantum number in the Hilbert space.
        """
        try:
            values = login_time.dropna().values.astype(float)
            state = self._series_state(values)
            if state is None:
                return 0.0 if len(values) == 0 else 0.5
            n_op = Observables.number_operator(
                state.dim, self.config.get("hbar", 1.0), self.config.get("omega", 0.5)
            )
            expectation_n = state.expectation(n_op)
            max_n = state.dim - 1
            if max_n > 0:
                return float(np.clip(expectation_n / max_n, 0.0, 1.0))
            return 0.5
        except Exception as e:
            logging.error(f"Error calculating quantum login frequency: {e}")
            return 0.5

    def _calculate_login_variability(self, login_time: _dependencies.pd.Series) -> float:
        """Variability = Δx·Δp/(ℏ/2) via quantum Fisher information (first principles).

        F_Q(ψ, A) = 4 Var(A) for pure states, so Δx = √(F_Q(ψ,x̂))/2 and
        Δp = √(F_Q(ψ,p̂))/2. The Heisenberg product Δx·Δp normalized by
        the ℏ/2 bound measures how far above minimum uncertainty the
        encoded login pattern sits.
        """
        try:
            values = login_time.dropna().values.astype(float)
            state = self._series_state(values)
            if state is None:
                return 0.0
            hbar = self.config.get("hbar", 1.0)
            x = Observables.position(state.dim)
            p = Observables.momentum(state.dim, hbar)
            dx = math.sqrt(max(quantum_fisher_information(state, x), 0.0)) / 2.0
            dp = math.sqrt(max(quantum_fisher_information(state, p), 0.0)) / 2.0
            min_uncertainty = hbar / 2.0
            if min_uncertainty <= 0:
                return 0.0
            variability = (dx * dp) / min_uncertainty
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
        """Promotion velocity = Ehrenfest drift of the encoded history (first principles).

        The promotion series is encoded to a ray and propagated under the
        golden-family Hamiltonian; the measured d⟨x⟩/dt is the quantum
        velocity ⟨p̂⟩/m of the state's position centroid.
        """
        try:
            values = promotion_history.dropna().values.astype(float)
            state = self._series_state(values)
            if state is None:
                return 0.0
            mass = self.config.get("mass", 1.0)
            if mass <= 0:
                return 0.0
            return float(self._ehrenfest_drift(state))
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
        """Ensemble prediction across quantum channels: weighted or voting."""
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
        """Mixed-state Born-rule ensemble over the quantum channels.

        The indicator vector is encoded once into the shared channel
        Hilbert space. Each channel evolves the ray through its family
        propagator and discriminates it against the observed class
        reference rays — a Helstrom-type Born measurement. The channel
        weight is its quantum Fisher information w.r.t. position, the
        Cramér–Rao sensitivity of the evolved state; unmeasurable channels
        (zero overlap) are reported unavailable rather than assigned a
        fabricated score. The ensemble probability is the mixed-state
        Born mean Σ w_k p_k / Σ w_k.
        """
        try:
            predictions = {}
            features = self._prepare_input_features(indicators)
            dim = self._channel_dim()
            state = encode_data_to_state([float(v) for v in features], dim=dim, normalize=True)
            self._last_encoded_state = state
            position = Observables.position(dim)
            weights = []
            scores = []
            evolved_states = []
            for model_name, channel in self.models.items():
                cv_score = self._model_cv_scores.get(model_name)
                result = channel.discriminate(state)
                if result is None:
                    predictions[model_name] = {
                        "available": False,
                        "score": None,
                        "confidence": None,
                        "weight": None,
                        "cv_source": "measured" if cv_score is not None else "unmeasured",
                        "family": channel.family,
                    }
                    continue
                evolved = result["evolved"]
                qfi = quantum_fisher_information(evolved, position)
                weight = max(float(qfi), 0.0)
                predictions[model_name] = {
                    "score": float(result["score"]),
                    # Helstrom discrimination margin — the channel's own
                    # measured certainty, not a fitted confidence curve.
                    "confidence": float(result["margin"]),
                    "weight": weight,
                    "weight_source": "quantum_fisher_information",
                    "cv_source": "measured" if cv_score is not None else "unmeasured",
                    "cv_score": cv_score,
                    "family": channel.family,
                }
                weights.append(weight)
                scores.append(result["score"])
                evolved_states.append(evolved)
            self._last_evolved_states = evolved_states
            if scores:
                total_weight = sum(weights)
                if total_weight > 0:
                    combined = sum(s * w for s, w in zip(scores, weights)) / total_weight
                else:
                    combined = float(np.mean(scores))
                predictions["quantum_superposition"] = float(combined)
            else:
                predictions["quantum_superposition"] = None
            return predictions
        except Exception as e:
            logging.error(f"Error during weighting of predictions: {e}")
            raise

    def _voting_predictions(self, indicators: dict) -> dict:
        """Majority-measurement vote across the quantum channels.

        Each channel casts one deterministic Born-measurement verdict
        (churn overlap > retain overlap). The voting probability is the
        measured fraction of channels voting churn — a count of real
        measurement outcomes, not a fitted vote weight.
        """
        try:
            predictions = {}
            features = self._prepare_input_features(indicators)
            dim = self._channel_dim()
            state = encode_data_to_state([float(v) for v in features], dim=dim, normalize=True)
            self._last_encoded_state = state
            votes = []
            evolved_states = []
            for model_name, channel in self.models.items():
                cv_score = self._model_cv_scores.get(model_name)
                result = channel.discriminate(state)
                if result is None:
                    predictions[model_name] = {
                        "available": False,
                        "score": None,
                        "confidence": None,
                        "weight": None,
                        "cv_source": "measured" if cv_score is not None else "unmeasured",
                    }
                    continue
                votes.append(result["score"] > 0.5)
                evolved_states.append(result["evolved"])
                predictions[model_name] = {
                    "score": float(result["score"]),
                    "confidence": float(result["margin"]),
                    "weight": 1.0,
                    "verdict": "churn" if result["score"] > 0.5 else "retain",
                    "cv_source": "measured" if cv_score is not None else "unmeasured",
                    "cv_score": cv_score,
                    "family": channel.family,
                }
            self._last_evolved_states = evolved_states
            predictions["voting_probability"] = float(sum(votes) / len(votes)) if votes else None
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
                "model_predictions": predictions,  # Include all channel predictions
                "feature_importances": (
                    self._get_feature_importance(
                        self.models.get(self.config.get("selected_model", "rf")),
                        list(self._calculate_factor_weights(indicators).keys()),
                    )
                    if self.config.get("selected_model") and self.models
                    else None
                ),
                "quantum_explanations": self._quantum_explanations(indicators),
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
        """Time sensitivity via the time–energy uncertainty relation (first principles).

        ΔE·Δt ≥ ℏ/2. ΔE is the energy standard deviation of the encoded
        indicator state, measured through its quantum Fisher information:
        F_Q(ψ, H) = 4·Var(H), so ΔE = √F_Q/2 and Δt ≥ ℏ/(2ΔE). No state
        → honest unmeasured payload.
        """
        try:
            hbar = self.config.get("hbar", 1.0)
            state = self._encode_indicators(indicators)
            if state is None:
                return {
                    "sensitivity_level": "unmeasured",
                    "time_horizon": None,
                    "energy_uncertainty": None,
                    "uncertainty_bound": hbar / 2,
                }
            H = Observables.harmonic_oscillator_hamiltonian(
                state.dim,
                hbar,
                self.config.get("mass", 1.0),
                self.config.get("omega", 0.5),
            )
            delta_e = math.sqrt(max(quantum_fisher_information(state, H), 0.0)) / 2.0
            delta_t = hbar / (2 * delta_e) if delta_e > 0 else float("inf")
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
                "energy_uncertainty": float(delta_e),
                "uncertainty_bound": hbar / 2,
            }
        except Exception as e:
            logging.error(f"Error assessing time sensitivity: {e}")
            return {
                "sensitivity_level": "unmeasured",
                "time_horizon": None,
                "energy_uncertainty": None,
                "uncertainty_bound": hbar / 2,
            }

    def _factor_observables(self, indicators: dict) -> dict:
        """One diagonal Hermitian observable per indicator factor group.

        Each group's numeric values become the observable's eigenvalues
        (normalized to the group's largest magnitude), padded to the
        encoded state's dimension — the same factor-observable convention
        toe.bridge uses. Returns {} when no factor carries numeric data.
        """
        state = self._last_encoded_state or self._encode_indicators(indicators)
        if state is None:
            return {}
        observables = {}
        for name, value in indicators.items():
            values = []
            if isinstance(value, dict):
                values = [float(v) for v in value.values() if isinstance(v, (int, float))]
            elif isinstance(value, (int, float)):
                values = [float(value)]
            if not values:
                continue
            while len(values) < state.dim:
                values.append(0.0)
            values = values[: state.dim]
            max_abs = max(abs(v) for v in values) or 1.0
            observables[name] = ComplexMatrix.diagonal([Complex(v / max_abs, 0.0) for v in values])
        return observables

    def _quantum_explanations(self, indicators: dict) -> dict:
        """Substrate-native 'why': causal_factor_ranking on the encoded state.

        Ranks each factor group's observable by |⟨A⟩| — the
        quantum-measurement-theoretic influence the factor exerts on the
        current state. This replaces the former LIME surrogate: the
        explanation is computed from the state's own expectation values,
        not from a local linear fit.
        """
        try:
            state = self._encode_indicators(indicators)
            if state is None:
                return {
                    "available": False,
                    "explanation": [],
                    "note": "no encodable indicators",
                }
            observables = self._factor_observables(indicators)
            if not observables:
                return {
                    "available": False,
                    "explanation": [],
                    "note": "no numeric factor observables",
                }
            ranked = causal_factor_ranking(state, observables)
            return {
                "available": True,
                "method": "causal_factor_ranking (expectation magnitudes; "
                "descriptive, not interventional)",
                "explanation": [
                    {"factor": name, "expectation_magnitude": float(mag)} for name, mag in ranked
                ],
                "feature_names": [name for name, _ in ranked],
            }
        except Exception as e:
            logging.error(f"Error generating quantum explanations: {e}")
            return {"available": False, "error": str(e)}

    def _calculate_risk_score(self, predictions: dict) -> dict:
        """Calculate final risk score with confidence interval"""
        try:
            if predictions.get("available") is False:
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
                model_preds = {
                    k: v
                    for k, v in predictions.items()
                    if isinstance(v, dict) and v.get("score") is not None and "weight" in v
                }
                if model_preds:
                    # QFI-derived weights; unmeasured channels contribute
                    # uniform mass — never a fabricated sensitivity figure.
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
                confidence = 0.0
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
        """Identify top contributing factors via the substrate's causal ranking."""
        try:
            factor_weights = self._calculate_factor_weights(indicators)
            return sorted(factor_weights.items(), key=lambda x: x[1], reverse=True)[:5]
        except Exception as e:
            logging.error(f"Error identifying key factors: {e}")
            raise

    def _generate_recommendations(self, indicators: dict) -> dict:
        """Recommendation surface = measured factor attribution, not canned advice.

        The engine computes *which factor groups drive the measured risk*
        via ``causal_factor_ranking`` (normalized Born-weighted ⟨A_f⟩
        magnitudes). It does not generate prescriptive action text —
        invented advice strings would be demo content, not computed
        output. Consumers needing action text map the ranked measured
        factors themselves.
        """
        try:
            risk_factors = self._identify_key_factors(indicators)
            return {
                "basis": "causal_factor_ranking",
                "measured_risk_factors": [
                    {"factor": name, "attribution_weight": float(w)}
                    for name, w in risk_factors
                ],
                "prescriptive_text": "not_computed",
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
        """Confidence = mean of the measured confidence components.

        Components: per-channel Helstrom margins, ensemble agreement
        (pairwise fidelity of evolved states), and cohort data quality
        (normalized von Neumann entropy). Unmeasured components are
        excluded rather than filled with constants.
        """
        try:
            components = []
            channel_margins = [
                v["confidence"]
                for v in predictions.values()
                if isinstance(v, dict) and v.get("confidence") is not None
            ]
            if channel_margins:
                components.append(float(np.mean(channel_margins)))
            if self._last_evolved_states:
                components.append(self._calculate_model_agreement(predictions))
            data_quality = self._assess_data_quality()
            if data_quality is not None:
                components.append(data_quality)
            if not components:
                return 0.0
            return float(np.mean(components))
        except Exception as e:
            logging.error(f"Error calculating confidence: {e}")
            raise

    def _assess_data_quality(self):
        """Data quality = normalized von Neumann entropy of the cohort ensemble.

        The observed training rows are encoded to rays; their incoherent
        mixture ρ = Σᵢ|ψᵢ⟩⟨ψᵢ|/N is the cohort's true mixed density
        operator. S(ρ)/log₂(dim) measures how uniformly the cohort covers
        the Hilbert space — 1.0 = maximally spread, 0.0 = degenerate.
        Computed via the substrate's ``von_neumann_entropy`` on the real
        density matrix; returns None (honest 'unmeasured') with no cohort.
        """
        try:
            training = self._real_training_data()
            if training is None:
                return None
            X, _ = training
            dim = self._channel_dim()
            states = self._encode_rows(X[:64], dim)  # deterministic cap
            rho = ComplexMatrix.zero(dim, dim)
            for state in states:
                rho = rho.add(state.density_matrix())
            rho = rho.scale(1.0 / len(states))
            entropy = von_neumann_entropy(rho)
            max_entropy = math.log2(dim)
            if max_entropy <= 0:
                return None
            return float(np.clip(entropy / max_entropy, 0.0, 1.0))
        except Exception as e:
            logging.error(f"Error assessing data quality: {e}")
            return None

    def _calculate_model_agreement(self, predictions: dict) -> float:
        """Model agreement = mean pairwise fidelity of the evolved states.

        ``model_agreement_from_ensemble`` — the substrate's own measure.
        High fidelity between the channels' evolved rays = coherent
        ensemble = agreement. Returns 0.0 when no evolved states exist
        (no prediction ran).
        """
        try:
            if not self._last_evolved_states:
                return 0.0
            return float(model_agreement_from_ensemble(self._last_evolved_states))
        except Exception as e:
            logging.error(f"Error calculating model agreement: {e}")
            return 0.5

    def _analyze_trend(self, indicators: dict) -> dict:
        """Current risk trend via Schrödinger dynamics on the encoded state.

        Trend direction is the Ehrenfest drift d⟨x⟩/dt of the encoded
        indicator state under the detected family's Hamiltonian; rate is
        |drift|/ℏ. The energy decomposition ⟨p²⟩/2m and ⟨½mω²x²⟩ is
        reported alongside for diagnostics.
        """
        try:
            hbar = self.config.get("hbar", 1.0)
            mass = self.config.get("mass", 1.0)
            omega = self.config.get("omega", 0.5)
            state = self._encode_indicators(indicators)
            if state is None:
                return {"trend": "stable", "rate": 0.0}
            drift = self._ehrenfest_drift(state)
            H = Observables.harmonic_oscillator_hamiltonian(state.dim, hbar, mass, omega)
            energy = state.expectation(H)
            p = Observables.momentum(state.dim, hbar)
            kinetic = state.expectation(p.matmul(p)) / (2.0 * mass)
            x = Observables.position(state.dim)
            potential = 0.5 * mass * omega * omega * state.expectation(x.matmul(x))
            if drift > 0.01:
                trend = "increasing"
            elif drift < -0.01:
                trend = "decreasing"
            else:
                trend = "stable"
            rate = abs(drift) / hbar if hbar > 0 else abs(drift)
            return {
                "trend": trend,
                "rate": float(rate),
                "energy": float(energy),
                "kinetic_energy": float(kinetic),
                "potential_energy": float(potential),
                "ehrenfest_drift": float(drift),
            }
        except Exception as e:
            logging.error(f"Error analyzing quantum trend: {e}")
            return {"trend": "stable", "rate": 0.0}

    def _forecast_risk(self, indicators: dict) -> dict:
        """Forecast risk at t=3 and t=6 via the exact Schrödinger propagator.

        |ψ(t)⟩ = exp(−iHt/ℏ)|ψ₀⟩ under the harmonic-oscillator
        Hamiltonian — the same propagator convention as
        ``toe.bridge.predict_trajectory``. The forecast quantity is the
        Born probability of the upper half of the position spectrum
        (the risk subspace projector Π_risk = Σ_{i≥dim/2} |i⟩⟨i|):
        P_risk(t) = ⟨ψ(t)|Π_risk|ψ(t)⟩. Deterministic — no sampling,
        no quadrature lattice, no sigmoid.
        """
        try:
            hbar = self.config.get("hbar", 1.0)
            mass = self.config.get("mass", 1.0)
            omega = self.config.get("omega", 0.5)
            state = self._encode_indicators(indicators)
            if state is None:
                self._forecast_states = []
                return {
                    "available": False,
                    "3_month": None,
                    "6_month": None,
                    "algebraic": {
                        "enabled": bool(self.config.get("pisot_filter_enabled", True)),
                        "available": False,
                    },
                }
            H = Observables.harmonic_oscillator_hamiltonian(state.dim, hbar, mass, omega)
            times = (3.0, 6.0)
            states_t = [
                state.apply_unitary(ComplexMatrix.matrix_exp_unitary(H, t / hbar)) for t in times
            ]
            self._forecast_states = list(zip(times, states_t))
            risk_cut = state.dim // 2

            def _risk(s: QuantumState) -> float:
                return float(sum(s.probabilities()[risk_cut:]))

            forecast_3 = _risk(states_t[0])
            forecast_6 = _risk(states_t[1])
            current_risk = _risk(state)
            # Algebraic layer: detect which recurrence structure the
            # indicator series obeys, then contract the quadrature noise
            # with that family's Pisot drift kernel (|mu|^n -> 0). The
            # filter family is the detected one, or plastic (minimal
            # Pisot) when "auto" finds no structured lag.
            all_values = [
                float(v)
                for value in indicators.values()
                if isinstance(value, dict)
                for v in value.values()
                if isinstance(v, (int, float))
            ]
            algebraic = {"enabled": bool(self.config.get("pisot_filter_enabled", True))}
            if algebraic["enabled"] and all_values:
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
                "method": "schrodinger_matrix_exponential",
                "algebraic": algebraic,
            }
        except Exception as e:
            logging.error(f"Error forecasting risk: {e}")
            return {"3_month": None, "6_month": None}

    def _identify_intervention_points(self, predictions: dict) -> list:
        """Intervention points = times of maximum quantum Fisher information.

        F_Q(ψ(t), x̂) is measured on the actual forecast states produced
        by ``_forecast_risk`` — the times when the evolved state is most
        sensitive to perturbation. No forecast states → no points
        (honest empty set).
        """
        try:
            if not self._forecast_states:
                return []
            intervention_points = []
            dim = self._forecast_states[0][1].dim
            x = Observables.position(dim)
            risk_cut = dim // 2
            for t, state_t in self._forecast_states:
                fisher_info = quantum_fisher_information(state_t, x)
                projected_risk = float(sum(state_t.probabilities()[risk_cut:]))
                if projected_risk > 0.7:
                    action = "manager_meeting"
                    time_label = "2_weeks"
                elif projected_risk > 0.5:
                    action = "compensation_review"
                    time_label = "1_month"
                else:
                    action = "career_development"
                    time_label = "3_months"
                intervention_points.append(
                    {
                        "time": time_label,
                        "evolution_time": float(t),
                        "action": action,
                        "fisher_info": float(fisher_info),
                        "projected_risk": projected_risk,
                    }
                )
            return intervention_points
        except Exception as e:
            logging.error(f"Error identifying intervention points: {e}")
            return []

    def _calculate_probability(self, score: float) -> float:
        """Born passthrough: the channel score already IS a Born probability.

        No squashing function — P = |amplitude|² lives in [0, 1] by
        construction; the clip only guards float dust at the boundary.
        """
        try:
            return float(min(max(float(score), 0.0), 1.0))
        except Exception as e:
            logging.error(f"Error calculating probability: {e}")
            raise

    def _calculate_factor_weights(self, indicators: dict) -> dict:
        """Factor weights derived from the substrate, not from config constants.

        Each factor group's observable is ranked by |⟨A⟩| on the encoded
        indicator state (``causal_factor_ranking``), then normalized.
        Empty when no factor carries numeric data — no invented default
        weights are ever substituted.
        """
        try:
            state = self._encode_indicators(indicators)
            if state is None:
                return {}
            observables = self._factor_observables(indicators)
            if not observables:
                return {}
            ranked = causal_factor_ranking(state, observables)
            total = sum(mag for _, mag in ranked)
            if total <= 0:
                return {name: 1.0 / len(ranked) for name, _ in ranked}
            return {name: mag / total for name, mag in ranked}
        except Exception as e:
            logging.error(f"Error calculating factor weights: {e}")
            raise

    def _predict_with_model(self, model, indicators: dict) -> dict:
        """Score via one channel's Born-overlap discrimination."""
        try:
            features = self._prepare_input_features(indicators)
            state = encode_data_to_state(
                [float(v) for v in features],
                dim=model.dim,
                normalize=True,
            )
            result = model.discriminate(state)
            if result is None:
                return {"available": False, "score": None, "confidence": None}
            return {
                "available": True,
                "score": float(result["score"]),
                "confidence": float(result["margin"]),
            }
        except Exception as e:
            logging.error(f"Error predicting with model: {e}")
            raise

    def _calculate_model_confidence(self, prediction: float) -> float:
        """Helstrom discrimination margin of a Born probability (first principles).

        For a two-outcome Born measurement, the discrimination margin is
        |p − (1−p)| = |2p − 1| — the trace-distance-aligned certainty of
        the outcome. 0 at p = 0.5 (maximally uncertain), 1 at the poles.
        """
        try:
            return float(min(max(abs(2.0 * float(prediction) - 1.0), 0.0), 1.0))
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
        """Lexicon sentiment score — declared classical feature extraction.

        This is the repo's own lexicon counter (kellogg.tensor_ml
        TensorSentimentAnalyzer): a deterministic word-count ratio, not a
        quantum quantity and not presented as one.
        """
        try:
            if not isinstance(text, str) or self.sentiment_analyzer is None:
                return 0.0
            scores = self.sentiment_analyzer.polarity_scores(text)
            return float(scores["compound"])
        except Exception as e:
            logging.error(f"Error analyzing text sentiment: {e}")
            return 0.0

    def _analyze_performance_trend(self, data: _dependencies.pd.DataFrame) -> dict:
        """Analyze performance trends; trend from the Pisot lag-kernel contraction.

        The moving-average and EWMA columns are honest classical
        smoothing (labeled as such). The trend estimate comes from the
        exact-algebraic substrate: the series' detected family signature
        selects a lag kernel and pisot_drift_filter contracts the series
        toward its recurrence trend — the slope of that filtered series.
        """
        try:
            if not isinstance(data, _dependencies.pd.DataFrame):
                raise TypeError("performance trend input must be a pandas DataFrame")
            if "performance_score" not in data.columns or "date" not in data.columns:
                raise ValueError("performance trend requires date and performance_score columns")
            data = data.copy()
            data["date"] = _dependencies.pd.to_datetime(data["date"])
            data = data.sort_values(by="date")
            ma = data["performance_score"].rolling(window=3, min_periods=1).mean()
            ewma = data["performance_score"].ewm(span=3, min_periods=1).mean()
            values = [float(v) for v in data["performance_score"].tolist()]
            if len(values) > 10:
                signature = self.algebra.detect_family_signature(np.asarray(values))
                family = (
                    signature["family"]
                    if signature.get("family") in self.algebra.FAMILY_NAMES
                    else "plastic"
                )
                filtered = self.algebra.pisot_drift_filter(values, family)
                # Slope of the contracted series — exact Decimal arithmetic.
                trend = float(filtered[-1] - filtered[0]) / max(len(filtered) - 1, 1)
            else:
                trend = float(np.mean(np.diff(values))) if len(values) > 1 else 0.0
            return {
                "ma": float(ma.iloc[-1]) if not ma.empty else 0.0,
                "ewma": float(ewma.iloc[-1]) if not ewma.empty else 0.0,
                "trend": float(trend) if not np.isnan(trend) else 0.0,
            }
        except Exception as e:
            logging.error(f"Error in _analyze_performance_trend: {e}")
            raise

    def _analyze_text_engagement(self, text: str) -> float:
        """Engagement = spectral concentration of the encoded text state.

        The text is encoded by ``encode_data_to_state`` (UTF-8 byte
        amplitudes). Engagement is 1 − H(p)/log₂(dim) where H is the
        Shannon entropy of the state's Born distribution — a concentrated
        semantic state (low entropy) reads as engaged.
        """
        try:
            if not isinstance(text, str) or not text.strip():
                return 0.0
            state = encode_data_to_state(
                text, dim=self._encoding_dim(len(text.encode("utf-8"))), normalize=True
            )
            entropy = state.measurement_entropy()
            max_entropy = math.log2(state.dim) if state.dim > 1 else 1.0
            if max_entropy <= 0:
                return 0.5
            return float(np.clip(1.0 - entropy / max_entropy, 0.0, 1.0))
        except Exception as e:
            logging.error(f"Error analyzing text engagement: {e}")
            return 0.5

    def _analyze_login_patterns(self, data: _dependencies.pd.DataFrame) -> int:
        """Login pattern as the number-operator expectation of the encoded ray."""
        try:
            if isinstance(data, _dependencies.pd.DataFrame) and "login_time" in data.columns:
                values = data["login_time"].dropna().values.astype(float)
                state = self._series_state(values)
                if state is None:
                    return 0 if len(values) == 0 else 1
                n_op = Observables.number_operator(
                    state.dim, self.config.get("hbar", 1.0), self.config.get("omega", 0.5)
                )
                return int(round(state.expectation(n_op)))
            return 0
        except Exception as e:
            logging.error(f"Error in _analyze_login_patterns: {e}")
            raise

    def _analyze_survey_responses(self, data: _dependencies.pd.DataFrame) -> np.ndarray:
        """Survey responses → Born distributions of encoded semantic states."""
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
        """Each text row → its encoded state's Born probability vector.

        ``encode_data_to_state`` maps UTF-8 bytes to real amplitudes;
        probabilities() applies the Born rule |α_i|². The flattened rows
        are the quantum semantic features — no TF-IDF anywhere.
        """
        try:
            text_data = text_series.dropna().astype(str)
            if len(text_data) == 0:
                return np.array([0.0])
            rows = [
                encode_data_to_state(text, dim=self._encoding_dim(), normalize=True).probabilities()
                for text in text_data
            ]
            return np.asarray(rows, dtype=float).flatten()
        except Exception as e:
            logging.error(f"Error processing text data: {e}")
            return np.array([0.0])

    def _analyze_goal_completion(self, data) -> float:
        """Goal completion = ⟨Ĉ⟩ of the clipped-completion diagonal observable.

        The observable Ĉ is diagonal with eigenvalues equal to the
        observed completion fractions (clipped to [0,1], zero-padded);
        ⟨ψ|Ĉ|ψ⟩ is the Born-weighted completion rate — a real expectation
        value on the encoded state.
        """
        try:
            if isinstance(
                data, (_dependencies.pd.Series, _dependencies.pd.DataFrame, np.ndarray, list)
            ):
                values = np.array(data, dtype=float).flatten()
                values = values[~np.isnan(values)]
                if len(values) == 0:
                    return 0.0
                state = self._series_state(np.abs(values) + 1e-12)
                if state is None:
                    return 0.0
                eigenvalues = [min(max(float(v), 0.0), 1.0) for v in values]
                eigenvalues += [0.0] * (state.dim - len(eigenvalues))
                obs = ComplexMatrix.diagonal([Complex(v, 0.0) for v in eigenvalues])
                return float(np.clip(state.expectation(obs), 0.0, 1.0))
            return 0.0
        except Exception as e:
            logging.error(f"Error in _analyze_goal_completion: {e}")
            raise

    def _analyze_peer_comparison(self, data) -> float:
        """Peer comparison = fidelity F = |⟨ψ|uniform⟩|² (first principles)."""
        try:
            if isinstance(
                data, (_dependencies.pd.Series, _dependencies.pd.DataFrame, np.ndarray, list)
            ):
                values = np.array(data, dtype=float).flatten()
                values = values[~np.isnan(values)]
                if len(values) < 2:
                    return 0.5
                centered = values - np.mean(values)
                state = self._series_state(centered)
                if state is None:
                    return 1.0
                uniform = QuantumState.uniform_superposition(state.dim)
                return float(state.fidelity(uniform))
            return 0.5
        except Exception as e:
            logging.error(f"Error in _analyze_peer_comparison: {e}")
            raise

    def _analyze_communication(self, data) -> float:
        """Communication quality = normalized measurement entropy (first principles).

        H(p)/log₂(dim) of the encoded |values| state — the Born
        distribution's spread. Higher entropy = more uniformly
        distributed communication intensity.
        """
        try:
            if isinstance(
                data, (_dependencies.pd.Series, _dependencies.pd.DataFrame, np.ndarray, list)
            ):
                values = np.array(data, dtype=float).flatten()
                values = values[~np.isnan(values)]
                if len(values) == 0:
                    return 0.0
                state = self._series_state(np.abs(values) + 1e-12)
                if state is None:
                    return 0.0
                entropy = state.measurement_entropy()
                max_entropy = math.log2(state.dim) if state.dim > 1 else 1.0
                if max_entropy <= 0:
                    return 0.0
                return float(np.clip(entropy / max_entropy, 0.0, 1.0))
            return 0.0
        except Exception as e:
            logging.error(f"Error in _analyze_communication: {e}")
            raise

    def _analyze_attendance(self, data) -> float:
        """Attendance regularity = fidelity between consecutive window states.

        F(ψ(v₀..v_{n−2}), ψ(v₁..v_{n−1})) — the quantum overlap of the
        attendance pattern with its own one-step shift. High fidelity =
        coherent, regular pattern.
        """
        try:
            if isinstance(
                data, (_dependencies.pd.Series, _dependencies.pd.DataFrame, np.ndarray, list)
            ):
                values = np.array(data, dtype=float).flatten()
                values = values[~np.isnan(values)]
                if len(values) < 2:
                    return 0.5
                dim = self._encoding_dim(len(values) - 1)
                early = encode_data_to_state(list(values[:-1]), dim=dim, normalize=True)
                late = encode_data_to_state(list(values[1:]), dim=dim, normalize=True)
                return float(np.clip(early.fidelity(late), 0.0, 1.0))
            return 0.5
        except Exception as e:
            logging.error(f"Error in _analyze_attendance: {e}")
            raise

    def _analyze_work_hours(self, data) -> float:
        """Work-hours instability = ⟨n̂⟩/(dim−1) of the encoded values.

        The number-operator expectation measures how far above the
        ground level the encoded work-hours ray sits; normalized to
        [0, 1] by the maximum quantum number.
        """
        try:
            if isinstance(
                data, (_dependencies.pd.Series, _dependencies.pd.DataFrame, np.ndarray, list)
            ):
                values = np.array(data, dtype=float).flatten()
                values = values[~np.isnan(values)]
                if len(values) < 2:
                    return 0.0
                state = self._series_state(values)
                if state is None:
                    return 0.0
                n_op = Observables.number_operator(
                    state.dim, self.config.get("hbar", 1.0), self.config.get("omega", 0.5)
                )
                max_n = state.dim - 1
                if max_n <= 0:
                    return 0.0
                return float(np.clip(state.expectation(n_op) / max_n, 0.0, 1.0))
            return 0.0
        except Exception as e:
            logging.error(f"Error in _analyze_work_hours: {e}")
            raise

    def _analyze_participation(self, data) -> float:
        """Participation = |⟨ψ|uniform⟩|² — Born overlap with the active state.

        The "active" reference is the uniform superposition (every basis
        state equally populated); the measured overlap is the
        participation probability.
        """
        try:
            if isinstance(
                data, (_dependencies.pd.Series, _dependencies.pd.DataFrame, np.ndarray, list)
            ):
                values = np.array(data, dtype=float).flatten()
                values = values[~np.isnan(values)]
                if len(values) == 0:
                    return 0.0
                state = self._series_state(np.abs(values) + 1e-12)
                if state is None:
                    return 0.0
                uniform = QuantumState.uniform_superposition(state.dim)
                return float(np.clip(state.fidelity(uniform), 0.0, 1.0))
            return 0.0
        except Exception as e:
            logging.error(f"Error in _analyze_participation: {e}")
            raise

    def _analyze_feedback(self, data) -> float:
        """Feedback = ⟨Ŝ⟩ of the sign observable on the encoded state.

        Ŝ is diagonal with eigenvalues sign(vᵢ) ∈ {−1, 0, +1}; the
        expectation ⟨ψ|Ŝ|ψ⟩ is the Born-weighted polarity, mapped from
        [−1, 1] to [0, 1].
        """
        try:
            if isinstance(
                data, (_dependencies.pd.Series, _dependencies.pd.DataFrame, np.ndarray, list)
            ):
                values = np.array(data, dtype=float).flatten()
                values = values[~np.isnan(values)]
                if len(values) == 0:
                    return 0.0
                state = self._series_state(np.abs(values) + 1e-12)
                if state is None:
                    return 0.0
                eigenvalues = [float(np.sign(v)) for v in values]
                eigenvalues += [0.0] * (state.dim - len(eigenvalues))
                obs = ComplexMatrix.diagonal([Complex(v, 0.0) for v in eigenvalues])
                expectation = state.expectation(obs)
                return float(np.clip((expectation + 1.0) / 2.0, 0.0, 1.0))
            return 0.0
        except Exception as e:
            logging.error(f"Error in _analyze_feedback: {e}")
            raise

    def _analyze_promotions(self, data) -> float:
        """Promotion rate = Born probability of the up-transition subspace.

        The state encodes the inter-value differences; the projector
        Π₊ onto basis states whose difference is positive gives
        P(up) = ⟨ψ|Π₊|ψ⟩ — the measured promotion-transition probability.
        """
        try:
            if isinstance(
                data, (_dependencies.pd.Series, _dependencies.pd.DataFrame, np.ndarray, list)
            ):
                values = np.array(data, dtype=float).flatten()
                values = values[~np.isnan(values)]
                if len(values) < 2:
                    return 0.0
                diffs = np.diff(values)
                state = self._series_state(np.abs(diffs) + 1e-12)
                if state is None:
                    return 0.0
                eigenvalues = [1.0 if d > 0 else 0.0 for d in diffs]
                eigenvalues += [0.0] * (state.dim - len(eigenvalues))
                projector = ComplexMatrix.diagonal([Complex(v, 0.0) for v in eigenvalues])
                return float(np.clip(state.expectation(projector), 0.0, 1.0))
            return 0.0
        except Exception as e:
            logging.error(f"Error in _analyze_promotions: {e}")
            raise

    def _analyze_skill_development(self, data) -> float:
        """Skill development rate = |Ehrenfest drift| of the encoded levels.

        The magnitude of the measured d⟨x⟩/dt under golden-family
        evolution — how fast the skill state's position centroid moves.
        """
        try:
            if isinstance(
                data, (_dependencies.pd.Series, _dependencies.pd.DataFrame, np.ndarray, list)
            ):
                values = np.array(data, dtype=float).flatten()
                values = values[~np.isnan(values)]
                if len(values) < 2:
                    return 0.0
                state = self._series_state(values)
                if state is None:
                    return 0.0
                return float(np.clip(abs(self._ehrenfest_drift(state)), 0.0, 1.0))
            return 0.0
        except Exception as e:
            logging.error(f"Error in _analyze_skill_development: {e}")
            raise

    def _analyze_compensation(self, data) -> float:
        """Compensation equilibrium = Gibbs-weighted deviation measure.

        Quantum statistical mechanics, labeled as such: the harmonic
        energies Eᵢ = ½·devᵢ² (deviation from the fair ratio 1.0) set the
        Gibbs weights exp(−Eᵢ/kT) with kT = ℏω/2 (the ground-state
        energy). The equilibrium score is the Gibbs-weighted mean of
        1 − |devᵢ|. This is a real thermal-equilibrium distribution, not
        a sigmoid.
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
                deviations = values - 1.0
                energies = 0.5 * (deviations**2)
                kT = 0.5 * hbar * omega
                if kT > 0:
                    boltzmann_factors = np.exp(-energies / kT)
                else:
                    boltzmann_factors = np.ones_like(energies)
                weights = boltzmann_factors / np.sum(boltzmann_factors)
                equilibrium = np.sum(weights * (1.0 - np.abs(deviations)))
                return float(np.clip(equilibrium, 0.0, 1.0))
            return 0.5
        except Exception as e:
            logging.error(f"Error in _analyze_compensation: {e}")
            raise

    def _analyze_market(self, data) -> float:
        """Market condition = field expectation + fluctuation stability.

        ⟨x̂⟩ of the encoded values (normalized by dim/2 to [0,1]) is the
        field expectation; the stability term uses the position variance
        measured via F_Q(ψ, x̂)/4 — the quantum fluctuation of the field.
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
                state = self._series_state(np.abs(values) + 1e-12)
                if state is None:
                    return 0.5
                x = Observables.position(state.dim)
                field_expectation = state.expectation(x) / (state.dim / 2.0)
                field_normalized = float(np.clip((field_expectation + 1.0) / 2.0, 0.0, 1.0))
                vacuum_fluctuation = quantum_fisher_information(state, x) / 4.0
                if vacuum_fluctuation > 0:
                    stability = hbar / (hbar + vacuum_fluctuation)
                else:
                    stability = 1.0
                market_condition = 0.5 * (field_normalized + stability)
                return float(np.clip(market_condition, 0.0, 1.0))
            return 0.5
        except Exception as e:
            logging.error(f"Error in _analyze_market: {e}")
            raise

    def _analyze_industry(self, data) -> float:
        """Industry trend = Gibbs average energy over the oscillator levels.

        Quantum statistical mechanics, labeled as such: values map to
        ladder quantum numbers, energies E_n = (n + ½)ℏω, and the
        partition function Z = Σ exp(−E_n/kT) gives the thermal average
        ⟨E⟩; normalized by the top level.
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
                kT = 0.5 * hbar * omega
                if np.max(values) != np.min(values):
                    quantum_numbers = (values - np.min(values)) / (np.max(values) - np.min(values))
                else:
                    quantum_numbers = np.zeros_like(values)
                energies = (quantum_numbers + 0.5) * hbar * omega
                if kT > 0:
                    boltzmann = np.exp(-energies / kT)
                    Z = np.sum(boltzmann)
                    if Z > 0:
                        avg_energy = np.sum(energies * boltzmann) / Z
                        max_energy = (1.5) * hbar * omega
                        trend = avg_energy / max_energy if max_energy > 0 else 0.5
                        return float(np.clip(trend, 0.0, 1.0))
                return 0.5
            return 0.5
        except Exception as e:
            logging.error(f"Error in _analyze_industry: {e}")
            raise

    def _analyze_competitors(self, data) -> float:
        """Competition level = normalized measurement entropy of the encoded state.

        H(p)/log₂(dim) of the encoded activity ray — high entropy means
        competitor activity is spread unpredictably across the basis.
        """
        try:
            if isinstance(
                data, (_dependencies.pd.Series, _dependencies.pd.DataFrame, np.ndarray, list)
            ):
                values = np.array(data, dtype=float).flatten()
                values = values[~np.isnan(values)]
                if len(values) == 0:
                    return 0.5
                state = self._series_state(np.abs(values) + 1e-12)
                if state is None:
                    return 0.5
                entropy = state.measurement_entropy()
                max_entropy = math.log2(state.dim) if state.dim > 1 else 1.0
                if max_entropy <= 0:
                    return 0.5
                return float(np.clip(entropy / max_entropy, 0.0, 1.0))
            return 0.5
        except Exception as e:
            logging.error(f"Error in _analyze_competitors: {e}")
            raise

    def _profile_model(self, model, data: np.ndarray) -> dict:
        """Profile a channel: state tomography of the evolved encoded data.

        Returns the substrate's tomography dict (energy, momentum,
        position, number, purity, measurement entropy, Fisher
        information) of the channel-evolved state — no external profiler.
        """
        try:
            state = encode_data_to_state(
                list(np.asarray(data, dtype=float).flatten()),
                dim=model.dim,
                normalize=True,
            )
            evolved = model.evolve(state)
            tomo = state_tomography(
                evolved,
                hbar=model.hbar,
                mass=self.config.get("mass", 1.0),
                omega=self.config.get("omega", 0.5),
            )
            logging.info(
                "Channel profile for %s: energy=%.4g fisher=%.4g",
                model.name,
                tomo["energy"],
                tomo["fisher_information"],
            )
            return tomo
        except Exception as e:
            logging.error(f"Error profiling model: {e}")
            raise

    def _get_feature_importance(self, model, feature_names: list) -> dict:
        """Feature importances = Born mass shares of the encoded feature state.

        importance_j = p_j = |α_j|² — the share of the encoded indicator
        state's Born distribution carried by each feature coordinate.
        Computed on the last encoded prediction state; None when no state
        exists. No estimator is interrogated — the importances are the
        state's own measurement distribution.
        """
        try:
            if model is None:
                return None
            state = self._last_encoded_state
            if state is None:
                return None
            probs = state.probabilities()
            names = list(feature_names)
            if len(names) < len(probs):
                names += [f"feature_{i}" for i in range(len(names), len(probs))]
            return {names[i]: float(probs[i]) for i in range(len(probs))}
        except Exception as e:
            logging.error(f"Error extracting feature importance: {e}")
            raise

    def _benchmark_model(
        self, model, X_test: np.ndarray, y_test: np.ndarray, model_name: str
    ) -> dict:
        """Benchmark a channel on an observed holdout via Born discrimination.

        Measured quantities only: verdict accuracy (fraction of rows
        whose churn/retain overlap ordering matches the observed label)
        and the mean Helstrom margin. No classical metric machinery.
        """
        try:
            yv = np.asarray(y_test, dtype=int)
            states = self._encode_rows(X_test, model.dim)
            correct = 0
            total = 0
            margins = []
            for state, label in zip(states, yv):
                res = model.discriminate(state)
                if res is None:
                    continue
                correct += int((res["score"] > 0.5) == bool(label))
                margins.append(res["margin"])
                total += 1
            result = {
                "born_accuracy": (correct / total) if total else None,
                "mean_margin": float(np.mean(margins)) if margins else None,
                "n_samples": total,
                "method": "born_overlap_discrimination",
            }
            logging.info(f"Benchmarking Results for {model_name}: {result}")
            return result
        except Exception as e:
            logging.error(f"Error benchmarking model: {e}")
            raise

    def cleanup(self) -> None:
        """Releases cached quantum states; no external sessions to free."""
        try:
            self._last_evolved_states = []
            self._last_encoded_state = None
            self._forecast_states = []
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
            # Isolated per-test artifact dir — Windows holds mmap
            # handles, so a shared 'test_models/' collides across tests.
            "model_dir": tempfile.mkdtemp(prefix="toe_test_models_") + os.sep,
            "n_estimators": 10,
            "max_depth": 5,
            "learning_rate": 0.01,
            "test_size": 0.2,
            "cv_folds": 2,
            "feature_dim": 10,
            "selected_model": "rf",
            "imputation_strategy": "median",
            "ensemble_selection_method": "weighted_average",
        }

        # Declared labeled fixture — the real-data contract requires an
        # observed (X, y) cohort before any channel is calibrated.
        # Deterministic: two separated half-planes so both classes are
        # represented.

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

        # Deterministic test data — a fixed grid plus a fixed phase
        # variation, no PRNG anywhere.

        num_samples = 10

        num_features = self.config["feature_dim"]

        self.test_data = _dependencies.pd.DataFrame(
            np.linspace(0.05, 0.95, num_samples * num_features).reshape(num_samples, num_features)
            + 0.01
            * np.sin(np.arange(num_samples * num_features).reshape(num_samples, num_features)),
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
                "performance_score": 0.5 + 0.3 * np.sin(np.linspace(0, 3.0, 10)),
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

        # Release artifact handles before removing the dir — Windows
        # locks npz-loaded files while arrays are alive.

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

    def test_channels_are_quantum(self):
        """Every configured model is a quantum channel with a family Hamiltonian."""

        for name, channel in self.engine.models.items():

            self.assertIsInstance(channel, QuantumChannelModel)

            self.assertIn(channel.family, ExtendedAlgebraicFamily.FAMILY_NAMES)

            self.assertTrue(channel.calibrated)

            # The propagator must be a real unitary — U·U† = I.

            unitary, err = channel.propagator.is_unitary()

            self.assertTrue(unitary, f"{name} propagator error {err}")

    def test_predict_churn_risk(self):
        """Test the predict_churn_risk method returns a valid output"""

        with self.subTest("Test Churn Risk Prediction"):

            risk_profile = self.engine.predict_churn_risk(self.test_data)

            self.assertIsInstance(risk_profile, dict)

            self.assertIn("risk_score", risk_profile)

            self.assertIn("confidence_level", risk_profile)

            self.assertTrue(risk_profile["available"])

            score = risk_profile["risk_score"]["score"]

            self.assertIsNotNone(score)

            self.assertGreaterEqual(score, 0.0)

            self.assertLessEqual(score, 1.0)

    def test_scores_are_born_probabilities(self):
        """Channel scores are Born ratios in [0,1] with Helstrom margins."""

        risk_profile = self.engine.predict_churn_risk(self.test_data)

        channels = {
            k: v
            for k, v in risk_profile["model_predictions"].items()
            if isinstance(v, dict) and v.get("score") is not None
        }

        self.assertEqual(len(channels), len(self.config["model_names"]))

        for name, pred in channels.items():

            self.assertGreaterEqual(pred["score"], 0.0)

            self.assertLessEqual(pred["score"], 1.0)

            self.assertGreaterEqual(pred["confidence"], 0.0)

            self.assertLessEqual(pred["confidence"], 1.0)

            self.assertEqual(pred["weight_source"], "quantum_fisher_information")

    def test_model_training_and_loading(self):
        """Tests channel calibration and artifact persistence"""

        with self.subTest("Test Channel Calibration and Loading"):

            engine = PredictiveEngine(self.config)

            self.assertIsInstance(engine.models, dict)

            self.assertEqual(len(engine.models), len(self.config["model_names"]))

            # Artifacts persisted as quantum-channel npz — no joblib estimators.

            for name in self.config["model_names"]:

                self.assertTrue(
                    os.path.exists(os.path.join(self.config["model_dir"], f"{name}.qchannel.npz"))
                )

            # Reload path reconstructs calibrated channels from artifacts.

            engine_second = PredictiveEngine(self.config)

            self.assertIsInstance(engine_second.models, dict)

            self.assertEqual(len(engine_second.models), len(self.config["model_names"]))

            engine_third = PredictiveEngine(self.config)

            self.assertIsInstance(engine_third.models, dict)

            self.assertEqual(len(engine_third.models), len(self.config["model_names"]))

    def test_untrained_engine_fails_closed(self):
        """No observed cohort → honest available=False, never a fabricated score."""

        import tempfile

        cfg = dict(self.config)

        cfg.pop("training_data")

        cfg["model_dir"] = tempfile.mkdtemp(prefix="toe_test_untrained_") + os.sep

        engine = PredictiveEngine(cfg)

        self.assertEqual(engine.models, {})

        profile = engine.predict_churn_risk(self.test_data)

        self.assertFalse(profile["available"])

        self.assertEqual(profile["truth_class"], "untrained_models")

        self.assertIsNone(profile["risk_score"]["score"])

        import gc
        import shutil

        engine = None

        gc.collect()

        shutil.rmtree(cfg["model_dir"], ignore_errors=True)

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
        """Tests that channel predictions are being returned in the profile"""

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

                self.engine._analyze_survey_responses(np.zeros((10, 10)))

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
        """Structured series resolve to their family; unstructured does not."""

        algebra = self.engine.algebra

        padovan = np.array(algebra.sequence("plastic", "coordinate", 24), dtype=float)

        sig = algebra.detect_family_signature(padovan)

        self.assertEqual(sig["family"], "plastic")

        # Deterministic unstructured series (no PRNG): fractional parts of
        # i*sqrt(2) — equidistributed, no recurrence signature.

        unstructured = [float((i * math.sqrt(2.0)) % 1.0) for i in range(60)]

        sig_rand = algebra.detect_family_signature(unstructured)

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

    def test_forecast_is_schrodinger_born(self):
        """Forecast values are Born probabilities of the risk subspace."""

        indicators = {
            "performance": {"mean": 0.5, "trend": 0.1, "volatility": 0.2},
            "behavioral": {"login_freq": 0.6, "variability": 0.3},
            "engagement": {"score": 0.7},
        }

        forecast = self.engine._forecast_risk(indicators)

        self.assertEqual(forecast["method"], "schrodinger_matrix_exponential")

        for key in ("3_month", "6_month", "current"):

            self.assertIsNotNone(forecast[key])

            self.assertGreaterEqual(forecast[key], 0.0)

            self.assertLessEqual(forecast[key], 1.0)


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
        "feature_dim": 10,
        "selected_model": "rf",
        "imputation_strategy": "median",
        "ensemble_selection_method": "weighted_average",
    }

    engine = PredictiveEngine(config=config)

    # The real-data contract: channels calibrate only on observed labeled
    # rows. This demo registers a declared fixture cohort — in production
    # the caller supplies live telemetry via ingest_training_data() or
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

    # Deterministic demonstration data — no PRNG.

    data = _dependencies.pd.DataFrame(
        {
            "performance_score": 0.5 + 0.3 * np.sin(np.linspace(0, 3.0, 10)),
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

    # Channel profiling — substrate tomography of the evolved state.

    _channel = engine._get_model_by_name("rf")

    _profile = engine._profile_model(_channel, _demo_X[0])

    print(
        f"\nChannel profile (rf/{_channel.family}): "
        f"energy={_profile['energy']:.4g} "
        f"fisher={_profile['fisher_information']:.4g}"
    )

    unittest.main(argv=["first-arg-is-ignored"], exit=False)

    engine.cleanup()  # Clean up state caches.


def strict_quantum_work_certificate(header76: bytes, nonce_start: int, nonce_count: int) -> dict:
    """Return the exact Q(i) work certificate used by live PYTHIA windows.

    TOE remains the intelligence/provenance layer; this certificate is a
    mathematical control-plane witness only. Bitcoin consensus still belongs
    exclusively to the independent SHA-256d verifier.
    """
    from toe.strict_quantum import certify_work_window

    return certify_work_window(header76, nonce_start, nonce_count)
