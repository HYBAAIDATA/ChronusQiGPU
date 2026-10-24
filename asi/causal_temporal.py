"""Temporal causal discovery — Granger causality over VAR models.

``toe.causal_ladder`` and ``toe.causal_stack`` answer causal questions over a
STATIC graph on i.i.d. samples: d-separation, backdoor/frontdoor adjustment,
PC-style skeleton learning, intervention and counterfactual propagation.  None
of them can answer the temporal question "does the past of X improve the
prediction of Y beyond Y's own past?"  The repository's only prior attempt,
``Intelligence.discovery._granger_causality_simplified``, blends
``0.5 * y_pred1 + 0.5 * x_lagged`` and returns a relative-MSE ratio; it fits no
regression, computes no test statistic and no p-value, so it cannot separate
signal from noise.  This module is the missing capability.

What it implements, from first principles and with no statistics dependency:

* :func:`select_lag` — order selection for a bivariate VAR by AIC / BIC /
  Hannan-Quinn, so the test does not silently depend on a hand-picked lag.
* :func:`granger_causality` — the Wald F-test of the null hypothesis "lagged X
  coefficients are jointly zero in the model for Y", i.e. the restricted model
  ``Y_t = c + sum_i a_i Y_(t-i)`` against the unrestricted
  ``Y_t = c + sum_i a_i Y_(t-i) + sum_i b_i X_(t-i)``::

      F = ((RSS_r - RSS_u) / q) / (RSS_u / (n - k_u))

  The p-value is the F survival function evaluated through the regularized
  incomplete beta, exact to machine precision — not a simulation and not a
  heuristic (OWNER_DECLARATIONS D6: exact mathematics).
* :func:`discover_temporal_causality` — every ordered pair tested, with
  Holm-Bonferroni family-wise correction, returning a DIRECTED graph of the
  edges that survive.

Authority boundary: this module reports *predictive precedence* between
observed series.  Granger causality is not interventional causality; a
significant edge means "X's past carries unique information about Y's future",
and :class:`GrangerResult` records that limit explicitly rather than letting a
caller promote the edge to a do-calculus claim.  When the evidence is
insufficient — too few observations for the requested lag, a degenerate
(zero-variance) series, non-finite data, or a perfect fit — the verdict is
UNAVAILABLE with a reason.  Refusal is a capability; a fabricated edge is a
defect.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Mapping, Sequence, Tuple

import numpy as np

GRANGER_VERSION = "asi.causal_temporal/v1"

GRANGER_CAUSES = "GRANGER_CAUSES"
NOT_GRANGER_CAUSAL = "NOT_GRANGER_CAUSAL"
UNAVAILABLE = "UNAVAILABLE"

CLAIM_BOUNDARY = "PREDICTIVE_PRECEDENCE_NOT_INTERVENTIONAL_CAUSALITY"
"""Granger edges are a claim about conditional predictability only."""

_FPMIN = 1e-300


class LagCriterion(str, Enum):
    """Order-selection criterion for the underlying bivariate VAR."""

    AIC = "aic"
    BIC = "bic"
    HQIC = "hqic"
    FIXED = "fixed"


@dataclass(frozen=True)
class GrangerResult:
    """One directed Granger test ``cause -> effect``.

    ``p_value`` is the probability of observing an F-statistic at least this
    large when the lagged ``cause`` coefficients are genuinely zero.  A small
    ``p_value`` therefore rejects "cause carries no unique predictive
    information about effect" — nothing more, and :attr:`claim_boundary`
    records that limit so the result cannot be silently over-read.
    """

    cause: str
    effect: str
    lag_order: int
    n_observations: int
    degrees_of_freedom: Tuple[int, int]
    f_statistic: float
    p_value: float
    verdict: str
    alpha: float
    rss_restricted: float
    rss_unrestricted: float
    log_likelihood_gain: float
    aic_restricted: float
    aic_unrestricted: float
    lag_criterion: str
    adjusted_p_value: float | None = None
    reason: str | None = None
    claim_boundary: str = CLAIM_BOUNDARY

    @property
    def significant(self) -> bool | None:
        """``True``/``False`` when the test ran, ``None`` when it could not."""
        if self.verdict == UNAVAILABLE:
            return None
        return self.verdict == GRANGER_CAUSES

    def as_dict(self) -> dict:
        return {
            "cause": self.cause,
            "effect": self.effect,
            "lag_order": self.lag_order,
            "n_observations": self.n_observations,
            "degrees_of_freedom": list(self.degrees_of_freedom),
            "f_statistic": self.f_statistic,
            "p_value": self.p_value,
            "verdict": self.verdict,
            "alpha": self.alpha,
            "rss_restricted": self.rss_restricted,
            "rss_unrestricted": self.rss_unrestricted,
            "log_likelihood_gain": self.log_likelihood_gain,
            "aic_restricted": self.aic_restricted,
            "aic_unrestricted": self.aic_unrestricted,
            "lag_criterion": self.lag_criterion,
            "adjusted_p_value": self.adjusted_p_value,
            "significant": self.significant,
            "reason": self.reason,
            "claim_boundary": self.claim_boundary,
        }


@dataclass(frozen=True)
class TemporalCausalGraph:
    """Directed graph of the pairwise Granger tests that survived correction."""

    results: Tuple[GrangerResult, ...]
    alpha: float
    correction: str
    edges: Tuple[Tuple[str, str], ...] = field(default=())
    adjacency: Dict[str, Tuple[str, ...]] = field(default_factory=dict)

    @classmethod
    def from_results(
        cls, results: Sequence[GrangerResult], alpha: float, correction: str
    ) -> "TemporalCausalGraph":
        accepted = tuple(r for r in results if _kept(r, alpha))
        adjacency: Dict[str, List[str]] = {}
        for result in results:
            adjacency.setdefault(result.cause, [])
            adjacency.setdefault(result.effect, [])
        for cause, effect in ((r.cause, r.effect) for r in accepted):
            adjacency[cause].append(effect)
        return cls(
            results=tuple(results),
            alpha=alpha,
            correction=correction,
            edges=tuple((r.cause, r.effect) for r in accepted),
            adjacency={node: tuple(sorted(set(children))) for node, children in adjacency.items()},
        )

    def causes(self, node: str) -> Tuple[str, ...]:
        """Series that Granger-cause ``node`` after family-wise correction."""
        return tuple(sorted({r.cause for r in self.results if r.effect == node and _kept(r, self.alpha)}))

    def effects_of(self, node: str) -> Tuple[str, ...]:
        """Series that ``node`` Granger-causes after family-wise correction."""
        return tuple(sorted({r.effect for r in self.results if r.cause == node and _kept(r, self.alpha)}))

    def unavailable(self) -> Tuple[GrangerResult, ...]:
        """Tests that could not be evaluated — reported, never dropped."""
        return tuple(r for r in self.results if r.verdict == UNAVAILABLE)


def _kept(result: GrangerResult, alpha: float) -> bool:
    if result.verdict != GRANGER_CAUSES:
        return False
    return result.adjusted_p_value is None or result.adjusted_p_value <= alpha


# ---------------------------------------------------------------------------
# Exact special functions — F survival function via the incomplete beta
# ---------------------------------------------------------------------------


def _beta_continued_fraction(a: float, b: float, x: float, max_iter: int = 300) -> float:
    """Continued-fraction expansion of the incomplete beta (Lentz's method)."""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < _FPMIN:
        d = _FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < _FPMIN:
            d = _FPMIN
        c = 1.0 + aa / c
        if abs(c) < _FPMIN:
            c = _FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < _FPMIN:
            d = _FPMIN
        c = 1.0 + aa / c
        if abs(c) < _FPMIN:
            c = _FPMIN
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) <= 1e-15:
            break
    return h


def regularized_incomplete_beta(x: float, a: float, b: float) -> float:
    """``I_x(a, b)`` to machine precision.

    A closed-form special function, not a Monte-Carlo estimate: this is what
    keeps the p-values reproducible on any substrate.
    """
    if a <= 0.0 or b <= 0.0:
        raise ValueError(f"incomplete beta requires positive parameters, got a={a} b={b}")
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_bt = (
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    )
    bt = math.exp(log_bt)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _beta_continued_fraction(a, b, x) / a
    return 1.0 - bt * _beta_continued_fraction(b, a, 1.0 - x) / b


def f_survival(f_statistic: float, df1: int, df2: int) -> float:
    """Exact ``P(F_(df1, df2) > f_statistic)``."""
    if df1 <= 0 or df2 <= 0:
        raise ValueError(f"invalid F degrees of freedom: ({df1}, {df2})")
    if f_statistic <= 0.0:
        return 1.0
    return regularized_incomplete_beta(df2 / (df2 + df1 * f_statistic), df2 / 2.0, df1 / 2.0)


# ---------------------------------------------------------------------------
# Input validation and VAR fitting
# ---------------------------------------------------------------------------


def _as_series(values: Sequence[float], name: str) -> np.ndarray:
    try:
        array = np.asarray(values, dtype=np.float64).reshape(-1)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} is not a numeric sequence: {exc}") from exc
    if array.size == 0:
        raise ValueError(f"{name} is empty")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} contains non-finite values (NaN or inf)")
    return array


def _resolve_max_lag(total: int, max_lag: int | None) -> int:
    """Largest lag order for which the unrestricted model keeps a positive df.

    The unrestricted model has ``n = T - p`` rows and ``k = 2p + 1`` parameters
    (constant + ``p`` own lags + ``p`` foreign lags), so a usable order needs
    ``T - p - (2p + 1) > 0``.  Capped at 10 in line with standard practice.
    """
    if max_lag is not None:
        if max_lag < 1:
            raise ValueError(f"max_lag must be >= 1, got {max_lag}")
        return int(max_lag)
    resolved = 0
    for p in range(1, max(total, 2)):
        if total - p - (2 * p + 1) > 0:
            resolved = p
        else:
            break
    return min(resolved, 10)


def _unavailable(
    cause: str, effect: str, lag: int, n: int, alpha: float, criterion: str, reason: str
) -> GrangerResult:
    nan = float("nan")
    return GrangerResult(
        cause=cause,
        effect=effect,
        lag_order=lag,
        n_observations=n,
        degrees_of_freedom=(0, 0),
        f_statistic=nan,
        p_value=nan,
        verdict=UNAVAILABLE,
        alpha=alpha,
        rss_restricted=nan,
        rss_unrestricted=nan,
        log_likelihood_gain=nan,
        aic_restricted=nan,
        aic_unrestricted=nan,
        lag_criterion=criterion,
        reason=reason,
    )


def _lagged_block(series: np.ndarray, p: int, n: int, origin: int) -> np.ndarray:
    """Columns ``series[t-1], ..., series[t-p]`` for ``t`` in ``origin..+n-1``."""
    return np.column_stack([series[origin - j : origin - j + n] for j in range(1, p + 1)])


def _fit_rss(design: np.ndarray, target: np.ndarray) -> Tuple[float, float]:
    """Least-squares RSS and log-likelihood for ``target ~ design``.

    ``np.linalg.lstsq`` (SVD) rather than the normal equations, so a
    rank-deficient design degrades to the minimum-norm fit instead of
    inverting a singular Gram matrix.
    """
    coefficients, _residuals, _rank, _singular = np.linalg.lstsq(design, target, rcond=None)
    residuals = target - design @ coefficients
    rss = float(residuals @ residuals)
    n = target.shape[0]
    if rss <= 0.0:
        return 0.0, 0.0
    return rss, -0.5 * n * math.log(rss / n)


def _info_criterion(log_likelihood: float, k: int, n: int) -> Tuple[float, float, float]:
    """AIC / BIC / Hannan-Quinn for a Gaussian likelihood of size ``n``.

    ``k`` counts every estimated coefficient including the constant.  BIC's
    ``ln(n) * k`` penalty is what makes it prefer parsimony over AIC, which is
    the point of offering both: AIC over-fits long series, BIC under-fits short
    ones, and the caller chooses rather than inheriting a hidden default.
    """
    aic = 2.0 * k - 2.0 * log_likelihood
    bic = math.log(n) * k - 2.0 * log_likelihood
    hqic = 2.0 * math.log(math.log(n)) * k - 2.0 * log_likelihood
    return aic, bic, hqic


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def select_lag(
    x: Sequence[float],
    y: Sequence[float],
    max_lag: int | None = None,
    criterion: LagCriterion | str = LagCriterion.AIC,
) -> int:
    """Pick a VAR order for the bivariate ``(x, y)`` system.

    Returns the order minimising ``criterion`` over ``1..max_lag``.  By default
    ``max_lag`` is derived from the sample length via :func:`_resolve_max_lag`,
    so the caller gets a defensible order without inventing one.
    """
    xs, ys = _as_series(x, "x"), _as_series(y, "y")
    if xs.shape[0] != ys.shape[0]:
        raise ValueError("x and y must have equal length")
    total = xs.shape[0]
    resolved = _resolve_max_lag(total, max_lag)
    if resolved < 1:
        raise ValueError(f"series of length {total} cannot support any VAR lag order >= 1")
    target = criterion if isinstance(criterion, LagCriterion) else LagCriterion(criterion)
    if target is LagCriterion.FIXED:
        return resolved
    best_lag, best_value = 1, math.inf
    for p in range(1, resolved + 1):
        n = total - p
        design = np.column_stack(
            [np.ones(n), _lagged_block(ys, p, n, p), _lagged_block(xs, p, n, p)]
        )
        rss, log_likelihood = _fit_rss(design, ys[p:])
        aic, bic, hqic = _info_criterion(log_likelihood, k=2 * p + 1, n=n)
        value = {"aic": aic, "bic": bic, "hqic": hqic}[target.value]
        if value < best_value:
            best_lag, best_value = p, value
    return best_lag


def granger_causality(
    cause: Sequence[float],
    effect: Sequence[float],
    *,
    lag: int | None = None,
    lag_criterion: LagCriterion | str = LagCriterion.AIC,
    max_lag: int | None = None,
    alpha: float = 0.05,
    cause_name: str = "cause",
    effect_name: str = "effect",
) -> GrangerResult:
    """Test whether ``cause`` Granger-causes ``effect``.

    The Wald F-test of ``H0: b_1 = ... = b_p = 0`` in
    ``effect_t = c + sum a_i effect_(t-i) + sum b_i cause_(t-i)``.  Rejecting
    H0 means the past of ``cause`` carries predictive information about
    ``effect`` that ``effect``'s own past does not already contain.

    Raises :class:`ValueError` only for caller errors — non-numeric or ragged
    input, ``alpha`` outside ``(0, 1)``, non-positive ``lag``.  Evidential
    insufficiency never raises: it returns ``verdict=UNAVAILABLE`` with a
    reason, so a pipeline cannot mistake a failed test for a negative result.
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError(f"alpha must lie in (0, 1), got {alpha}")
    xs, ys = _as_series(cause, "cause"), _as_series(effect, "effect")
    if xs.shape[0] != ys.shape[0]:
        raise ValueError("cause and effect must have equal length")
    total = xs.shape[0]
    criterion = lag_criterion if isinstance(lag_criterion, LagCriterion) else LagCriterion(lag_criterion)
    resolved = _resolve_max_lag(total, max_lag)

    if lag is None:
        if resolved < 1:
            return _unavailable(
                cause_name,
                effect_name,
                0,
                total,
                alpha,
                criterion.value,
                f"series of length {total} cannot support the unrestricted VAR "
                "(need T > 3*lag + 1)",
            )
        p = select_lag(xs, ys, max_lag=resolved, criterion=criterion)
    else:
        if lag < 1:
            raise ValueError(f"lag must be >= 1, got {lag}")
        p = int(lag)

    n = total - p
    k_u = 2 * p + 1  # constant + p own lags + p cause lags
    q = p
    if n - k_u <= 0:
        return _unavailable(
            cause_name,
            effect_name,
            p,
            n,
            alpha,
            criterion.value,
            f"lag {p} leaves {n} rows for {k_u} parameters; the F-test has no degrees of freedom",
        )

    if float(np.ptp(ys)) <= 0.0:
        return _unavailable(
            cause_name,
            effect_name,
            p,
            n,
            alpha,
            criterion.value,
            "effect series is constant (zero variance); predictability is undefined",
        )
    if float(np.ptp(xs)) <= 0.0:
        return _unavailable(
            cause_name,
            effect_name,
            p,
            n,
            alpha,
            criterion.value,
            "cause series is constant (zero variance); it carries no predictive information",
        )

    ones = np.ones((n, 1))
    target = ys[p:]
    design_u = np.column_stack([ones, _lagged_block(ys, p, n, p), _lagged_block(xs, p, n, p)])
    design_r = np.column_stack([ones, _lagged_block(ys, p, n, p)])
    rss_u, ll_u = _fit_rss(design_u, target)
    rss_r, ll_r = _fit_rss(design_r, target)

    aic_r, _bic_r, _hq_r = _info_criterion(ll_r, k=p + 1, n=n)
    aic_u, _bic_u, _hq_u = _info_criterion(ll_u, k=k_u, n=n)

    if rss_u <= 0.0:
        return _unavailable(
            cause_name,
            effect_name,
            p,
            total,
            alpha,
            criterion.value,
            "unrestricted model fits the effect exactly (zero residual variance); "
            "the F-ratio is undefined",
        )

    f_statistic = ((rss_r - rss_u) / q) / (rss_u / (n - k_u))
    if f_statistic < 0.0:
        # Reachable only through floating-point noise: the unrestricted model
        # nests the restricted one, so it can never fit worse in exact arithmetic.
        f_statistic = 0.0
    p_value = f_survival(f_statistic, q, n - k_u)
    verdict = GRANGER_CAUSES if p_value <= alpha else NOT_GRANGER_CAUSAL

    return GrangerResult(
        cause=cause_name,
        effect=effect_name,
        lag_order=p,
        n_observations=n,
        degrees_of_freedom=(q, n - k_u),
        f_statistic=float(f_statistic),
        p_value=float(p_value),
        verdict=verdict,
        alpha=alpha,
        rss_restricted=float(rss_r),
        rss_unrestricted=float(rss_u),
        log_likelihood_gain=float(ll_u - ll_r),
        aic_restricted=float(aic_r),
        aic_unrestricted=float(aic_u),
        lag_criterion=criterion.value,
    )


# ---------------------------------------------------------------------------
# Family-wise corrected multi-series discovery
# ---------------------------------------------------------------------------


def _holm_bonferroni(p_values: Sequence[float]) -> List[float]:
    """Step-down Holm-Bonferroni adjusted p-values, returned in input order.

    Stricter than Bonferroni without losing the family-wise guarantee: sort
    ascending, multiply by the number of hypotheses remaining, and keep the
    running maximum so the sequence stays monotone.
    """
    m = len(p_values)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, (m - rank) * p_values[index])
        adjusted[index] = min(1.0, running)
    return adjusted


def discover_temporal_causality(
    series: Mapping[str, Sequence[float]],
    *,
    lag: int | None = None,
    lag_criterion: LagCriterion | str = LagCriterion.AIC,
    max_lag: int | None = None,
    alpha: float = 0.05,
    correction: str = "holm",
) -> TemporalCausalGraph:
    """Test every ordered pair and return the graph of surviving edges.

    With ``m`` series there are ``m * (m - 1)`` directed hypotheses, so a raw
    per-pair ``alpha`` would inflate the family-wise error rate to roughly
    ``m * (m - 1) * alpha``.  ``correction="holm"`` (default) applies the
    Holm-Bonferroni step-down procedure across that family;
    ``correction="none"`` opts out explicitly and is recorded in the result so
    an uncorrected graph can never be mistaken for a corrected one.
    """
    if not series:
        raise ValueError("series mapping is empty")
    if correction not in ("holm", "none"):
        raise ValueError(f"unsupported correction: {correction!r} (expected 'holm' or 'none')")
    names = list(series.keys())
    if len(names) < 2:
        raise ValueError("temporal discovery needs at least two series")
    lengths = {name: len(series[name]) for name in names}
    if len(set(lengths.values())) > 1:
        raise ValueError(f"all series must have equal length, got {lengths}")

    results: List[GrangerResult] = []
    for cause_name in names:
        for effect_name in names:
            if cause_name == effect_name:
                continue
            results.append(
                granger_causality(
                    series[cause_name],
                    series[effect_name],
                    lag=lag,
                    lag_criterion=lag_criterion,
                    max_lag=max_lag,
                    alpha=alpha,
                    cause_name=cause_name,
                    effect_name=effect_name,
                )
            )

    if correction == "holm":
        testable = [i for i, r in enumerate(results) if r.verdict != UNAVAILABLE]
        if testable:
            adjusted = _holm_bonferroni([results[i].p_value for i in testable])
            for index, value in zip(testable, adjusted):
                original = results[index]
                results[index] = GrangerResult(
                    cause=original.cause,
                    effect=original.effect,
                    lag_order=original.lag_order,
                    n_observations=original.n_observations,
                    degrees_of_freedom=original.degrees_of_freedom,
                    f_statistic=original.f_statistic,
                    p_value=original.p_value,
                    verdict=original.verdict,
                    alpha=original.alpha,
                    rss_restricted=original.rss_restricted,
                    rss_unrestricted=original.rss_unrestricted,
                    log_likelihood_gain=original.log_likelihood_gain,
                    aic_restricted=original.aic_restricted,
                    aic_unrestricted=original.aic_unrestricted,
                    lag_criterion=original.lag_criterion,
                    adjusted_p_value=value,
                    reason=original.reason,
                )

    return TemporalCausalGraph.from_results(results, alpha=alpha, correction=correction)


__all__ = [
    "CLAIM_BOUNDARY",
    "GRANGER_CAUSES",
    "GRANGER_VERSION",
    "NOT_GRANGER_CAUSAL",
    "UNAVAILABLE",
    "GrangerResult",
    "LagCriterion",
    "TemporalCausalGraph",
    "discover_temporal_causality",
    "f_survival",
    "granger_causality",
    "regularized_incomplete_beta",
    "select_lag",
]
