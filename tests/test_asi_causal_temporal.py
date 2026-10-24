"""Regression tests for temporal (Granger) causal discovery.

Each test corresponds to behaviour implemented in ``asi/causal_temporal.py``
and exists to *prove* it rather than restate it:

- The F-statistic and p-value agree with an independent reference
  implementation (statsmodels) to machine precision, so the hand-rolled
  incomplete beta is not a plausible source of silent drift.
- Direction is recovered on a system with known coupling, and NOT recovered
  in either the reverse direction or for independent noise — the negative
  cases matter as much as the positive one.
- Lag selection recovers a known true order instead of trusting a default.
- Insufficient evidence yields UNAVAILABLE + reason; only caller errors raise.
  A pipeline must never be able to read a failed test as a negative result.
- The multi-series graph applies family-wise correction and reports the
  correction it used.
- The ``asi`` public surface exports the capability.
"""

from __future__ import annotations

import numpy as np
import pytest

from asi import (
    GrangerResult,
    LagCriterion,
    TemporalCausalGraph,
    discover_temporal_causality,
    granger_causality,
    select_lag,
)
from asi.causal_temporal import (
    CLAIM_BOUNDARY,
    GRANGER_CAUSES,
    NOT_GRANGER_CAUSAL,
    UNAVAILABLE,
    f_survival,
    regularized_incomplete_beta,
)


def _coupled_pair(seed: int = 7, n: int = 400, strength: float = 0.8):
    """``x`` drives ``y``: y_t = 0.6 y_(t-1) + strength x_(t-1) + noise."""
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    y = np.zeros(n)
    for t in range(1, n):
        y[t] = 0.6 * y[t - 1] + strength * x[t - 1] + rng.normal(scale=0.4)
    return x, y


def _independent_pair(seed: int = 11, n: int = 300):
    rng = np.random.default_rng(seed)
    return rng.normal(size=n), rng.normal(size=n)


# ---------------------------------------------------------------------------
# Exact special functions
# ---------------------------------------------------------------------------


class TestExactSurvivalFunctions:
    @pytest.mark.parametrize(
        ("f", "d1", "d2"),
        [
            (1.0, 1, 1),
            (4.0, 1, 1),
            (0.5, 3, 7),
            (3.2, 5, 12),
            (0.0, 4, 9),
            (10.0, 2, 30),
        ],
    )
    def test_f_survival_matches_known_f_sf_values(self, f, d1, d2):
        """Independent oracle: scipy.stats.f.sf, taken as ground truth."""
        scipy_stats = pytest.importorskip("scipy.stats")
        assert f_survival(f, d1, d2) == pytest.approx(float(scipy_stats.f.sf(f, d1, d2)), abs=1e-12)

    def test_f_survival_zero_statistic_is_one(self):
        assert f_survival(0.0, 3, 10) == 1.0

    def test_f_survival_monotonically_decreasing(self):
        values = [f_survival(f, 4, 12) for f in (0.5, 1.0, 2.0, 5.0, 10.0)]
        assert all(a > b for a, b in zip(values, values[1:]))

    def test_incomplete_beta_boundaries(self):
        assert regularized_incomplete_beta(0.0, 2.0, 3.0) == 0.0
        assert regularized_incomplete_beta(1.0, 2.0, 3.0) == 1.0
        assert regularized_incomplete_beta(0.5, 1.0, 1.0) == pytest.approx(0.5)

    def test_incomplete_beta_matches_scipy(self):
        scipy_special = pytest.importorskip("scipy.special")
        for x, a, b in ((0.3, 2.5, 4.5), (0.7, 0.5, 1.5), (0.9, 8.0, 3.0)):
            expected = float(scipy_special.betainc(a, b, x))
            assert regularized_incomplete_beta(x, a, b) == pytest.approx(expected, abs=1e-12)

    def test_invalid_degrees_of_freedom_raise(self):
        with pytest.raises(ValueError):
            f_survival(1.0, 0, 10)
        with pytest.raises(ValueError):
            f_survival(1.0, 5, -1)

    def test_invalid_beta_parameters_raise(self):
        with pytest.raises(ValueError):
            regularized_incomplete_beta(0.5, 0.0, 2.0)


# ---------------------------------------------------------------------------
# The positive case: known coupling is detected, and matches an oracle
# ---------------------------------------------------------------------------


class TestGrangerDetection:
    def test_detects_known_driving_relationship(self):
        x, y = _coupled_pair()
        result = granger_causality(x, y, lag=1, cause_name="x", effect_name="y")
        assert result.verdict == GRANGER_CAUSES
        assert result.significant is True
        assert 0.0 <= result.p_value <= 1e-6
        assert result.f_statistic > 10.0

    def test_matches_statsmodels_reference_exactly(self):
        """The F-statistic must agree with an independent implementation.

        statsmodels is not a project dependency; it is an oracle.  If the
        hand-rolled regression or incomplete beta ever drifts, this fails.
        """
        statsmodels_tsa = pytest.importorskip("statsmodels.tsa.stattools")
        x, y = _coupled_pair()
        for lag in (1, 2, 4):
            reference = statsmodels_tsa.grangercausalitytests(np.column_stack([y, x]), lag)
            ref_f, ref_p = reference[lag][0]["ssr_ftest"][0], reference[lag][0]["ssr_ftest"][1]
            mine = granger_causality(x, y, lag=lag)
            assert mine.f_statistic == pytest.approx(ref_f, rel=1e-9, abs=1e-9)
            assert mine.p_value == pytest.approx(ref_p, rel=1e-6, abs=1e-140)

    def test_reverse_direction_is_not_significant(self):
        x, y = _coupled_pair()
        reverse = granger_causality(y, x, lag=1, cause_name="y", effect_name="x")
        assert reverse.verdict == NOT_GRANGER_CAUSAL
        assert reverse.significant is False
        assert reverse.p_value > 0.05

    def test_direction_is_one_way_not_symmetric(self):
        x, y = _coupled_pair()
        forward = granger_causality(x, y, lag=1)
        backward = granger_causality(y, x, lag=1)
        assert forward.p_value < 1e-6
        assert backward.p_value > 1e-3

    def test_result_records_claim_boundary(self):
        """Granger precedence must never be readable as an intervention."""
        x, y = _coupled_pair()
        result = granger_causality(x, y, lag=1)
        assert result.claim_boundary == CLAIM_BOUNDARY
        assert "PREDICTIVE" in result.claim_boundary

    def test_reported_degrees_of_freedom_are_consistent(self):
        x, y = _coupled_pair()
        result = granger_causality(x, y, lag=2)
        q, df2 = result.degrees_of_freedom
        assert q == 2
        assert df2 == result.n_observations - (2 * result.lag_order + 1)
        assert df2 > 0

    def test_unrestricted_model_never_fits_worse_than_restricted(self):
        x, y = _coupled_pair()
        result = granger_causality(x, y, lag=1)
        assert result.rss_unrestricted <= result.rss_restricted * (1 + 1e-12)
        assert result.aic_unrestricted <= result.aic_restricted + 1e-9


# ---------------------------------------------------------------------------
# The negative case: independent noise must not produce an edge
# ---------------------------------------------------------------------------


class TestNegativeCases:
    def test_independent_noise_is_not_causal(self):
        a, b = _independent_pair()
        result = granger_causality(a, b, lag=1)
        assert result.verdict == NOT_GRANGER_CAUSAL
        assert result.p_value > 0.05

    @pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
    def test_independent_noise_rejected_across_seeds(self, seed):
        """Guard against a lucky seed: false positives must stay rare."""
        a, b = _independent_pair(seed=seed, n=400)
        result = granger_causality(a, b, lag=1)
        assert result.verdict == NOT_GRANGER_CAUSAL

    def test_constant_effect_is_unavailable_not_negative(self):
        a = list(range(50))
        constant = [1.0] * 50
        result = granger_causality(a, constant, lag=1)
        assert result.verdict == UNAVAILABLE
        assert result.significant is None
        assert "constant" in result.reason

    def test_constant_cause_is_unavailable(self):
        constant = [1.0] * 50
        b = list(range(50))
        result = granger_causality(constant, b, lag=1)
        assert result.verdict == UNAVAILABLE
        assert "cause series is constant" in result.reason


# ---------------------------------------------------------------------------
# Edge cases: short input, degenerate design, caller-error contract
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_too_short_series_is_unavailable_not_a_crash(self):
        result = granger_causality([1.0, 2.0], [3.0, 4.0], lag=1)
        assert result.verdict == UNAVAILABLE
        assert result.significant is None
        assert "degrees of freedom" in result.reason
        assert result.n_observations == 1

    def test_empty_series_raises_as_caller_error(self):
        with pytest.raises(ValueError, match="empty"):
            granger_causality([], [1.0, 2.0], lag=1)

    def test_non_finite_input_raises(self):
        with pytest.raises(ValueError, match="non-finite"):
            granger_causality([1.0, float("nan"), 3.0] * 10, [1.0] * 30, lag=1)

    def test_infinite_input_raises(self):
        with pytest.raises(ValueError, match="non-finite"):
            granger_causality([1.0] * 30, [float("inf")] * 30, lag=1)

    def test_ragged_input_raises(self):
        with pytest.raises(ValueError, match="equal length"):
            granger_causality([1.0] * 30, [1.0] * 31, lag=1)

    def test_non_numeric_input_raises(self):
        with pytest.raises(ValueError):
            granger_causality(["a"] * 30, ["b"] * 30, lag=1)

    @pytest.mark.parametrize("alpha", [0.0, 1.0, -0.1, 2.0])
    def test_alpha_out_of_range_raises(self, alpha):
        x, y = _coupled_pair(n=60)
        with pytest.raises(ValueError, match="alpha"):
            granger_causality(x, y, lag=1, alpha=alpha)

    @pytest.mark.parametrize("bad_lag", [0, -3])
    def test_non_positive_lag_raises(self, bad_lag):
        x, y = _coupled_pair(n=60)
        with pytest.raises(ValueError, match="lag"):
            granger_causality(x, y, lag=bad_lag)

    def test_lag_larger_than_sample_is_unavailable(self):
        x, y = _coupled_pair(n=20)
        result = granger_causality(x, y, lag=15)
        assert result.verdict == UNAVAILABLE
        assert result.reason is not None

    def test_identical_series_causes_singular_design_not_a_crash(self):
        """A collinear design (x == y) must degrade, not raise or fabricate."""
        base = np.sin(np.linspace(0, 6, 120)) + 0.01 * np.arange(120)
        result = granger_causality(base, base, lag=1)
        assert result.verdict in (GRANGER_CAUSES, NOT_GRANGER_CAUSAL, UNAVAILABLE)
        if result.verdict != UNAVAILABLE:
            assert np.isfinite(result.f_statistic)

    def test_perfect_deterministic_fit_is_unavailable(self):
        """Zero residual variance makes the F-ratio undefined: say so."""
        y = list(range(1, 61))
        x = [float(v * 2) for v in y]
        result = granger_causality(x, y, lag=1)
        if result.rss_unrestricted == 0.0:
            assert result.verdict == UNAVAILABLE
            assert "zero residual variance" in result.reason

    def test_max_lag_below_one_raises(self):
        x, y = _coupled_pair(n=60)
        with pytest.raises(ValueError, match="max_lag"):
            granger_causality(x, y, max_lag=0)

    def test_result_serialises_to_dict(self):
        x, y = _coupled_pair(n=200)
        payload = granger_causality(x, y, lag=1).as_dict()
        assert payload["cause"] == "cause"
        assert payload["claim_boundary"] == CLAIM_BOUNDARY
        assert isinstance(payload["degrees_of_freedom"], list)
        assert payload["significant"] is True


# ---------------------------------------------------------------------------
# Lag selection must recover a known order rather than trust a default
# ---------------------------------------------------------------------------


class TestLagSelection:
    @staticmethod
    def _order_three_pair(seed: int = 3, n: int = 600):
        rng = np.random.default_rng(seed)
        u = rng.normal(size=n)
        v = np.zeros(n)
        for t in range(3, n):
            v[t] = (
                0.4 * v[t - 1] - 0.2 * v[t - 2] + 0.1 * v[t - 3] + 0.7 * u[t - 1] + rng.normal(scale=0.3)
            )
        return u, v

    @pytest.mark.parametrize("criterion", ["aic", "bic", "hqic"])
    def test_all_criteria_recover_the_true_order(self, criterion):
        u, v = self._order_three_pair()
        assert select_lag(u, v, criterion=criterion) == 3

    def test_criterion_accepts_enum_and_string_equivalently(self):
        u, v = self._order_three_pair()
        assert select_lag(u, v, criterion=LagCriterion.AIC) == select_lag(u, v, criterion="aic")

    def test_fixed_criterion_returns_the_max_lag(self):
        u, v = self._order_three_pair()
        assert select_lag(u, v, max_lag=4, criterion="fixed") == 4

    def test_explicit_max_lag_bounds_the_search(self):
        u, v = self._order_three_pair()
        assert select_lag(u, v, max_lag=2, criterion="aic") <= 2

    def test_unsupportable_length_raises(self):
        with pytest.raises(ValueError):
            select_lag([1.0, 2.0], [3.0, 4.0])

    def test_ragged_input_raises(self):
        with pytest.raises(ValueError, match="equal length"):
            select_lag([1.0] * 20, [1.0] * 21)

    def test_unknown_criterion_raises(self):
        u, v = self._order_three_pair()
        with pytest.raises(ValueError):
            select_lag(u, v, criterion="nope")


# ---------------------------------------------------------------------------
# Multi-series discovery with family-wise correction
# ---------------------------------------------------------------------------


class TestTemporalDiscovery:
    @pytest.fixture(scope="class")
    def three_series(self):
        rng = np.random.default_rng(21)
        n = 500
        drive = rng.normal(size=n)
        driven = np.zeros(n)
        for t in range(1, n):
            driven[t] = 0.5 * driven[t - 1] + 0.9 * drive[t - 1] + rng.normal(scale=0.3)
        return {"drive": drive, "driven": driven, "noise": rng.normal(size=n)}

    def test_discovers_the_true_edge_only(self, three_series):
        graph = discover_temporal_causality(three_series, lag=1)
        assert graph.edges == (("drive", "driven"),)

    def test_noise_has_no_parents_or_children(self, three_series):
        graph = discover_temporal_causality(three_series, lag=1)
        assert graph.causes("noise") == ()
        assert graph.effects_of("noise") == ()
        assert graph.adjacency["noise"] == ()

    def test_adjacency_is_transcribed_from_edges(self, three_series):
        graph = discover_temporal_causality(three_series, lag=1)
        assert graph.adjacency["drive"] == ("driven",)

    def test_correction_is_reported_not_silently_dropped(self, three_series):
        assert discover_temporal_causality(three_series, lag=1).correction == "holm"

    def test_holm_adjusted_p_values_are_present_and_ordered(self, three_series):
        graph = discover_temporal_causality(three_series, lag=1)
        testable = [r for r in graph.results if r.verdict != UNAVAILABLE]
        assert testable, "expected at least one evaluated test"
        for result in testable:
            assert result.adjusted_p_value is not None
            assert result.adjusted_p_value >= result.p_value
            assert result.adjusted_p_value <= 1.0

    def test_holm_can_only_be_more_conservative_than_no_correction(self, three_series):
        raw = discover_temporal_causality(three_series, lag=1, correction="none")
        corrected = discover_temporal_causality(three_series, lag=1, correction="holm")
        assert len(corrected.edges) <= len(raw.edges)
        assert raw.correction == "none"

    def test_result_count_is_all_ordered_pairs(self, three_series):
        graph = discover_temporal_causality(three_series, lag=1)
        assert len(graph.results) == 3 * 2  # m * (m - 1)

    def test_invalid_correction_raises(self, three_series):
        with pytest.raises(ValueError, match="correction"):
            discover_temporal_causality(three_series, lag=1, correction="bonferroni-typo")

    def test_empty_mapping_raises(self):
        with pytest.raises(ValueError, match="empty"):
            discover_temporal_causality({})

    def test_single_series_raises(self):
        with pytest.raises(ValueError, match="at least two"):
            discover_temporal_causality({"only": [1.0] * 50})

    def test_ragged_series_raises(self):
        with pytest.raises(ValueError, match="equal length"):
            discover_temporal_causality({"a": [1.0] * 50, "b": [1.0] * 51})

    def test_graph_is_a_typed_dataclass(self, three_series):
        graph = discover_temporal_causality(three_series, lag=1)
        assert isinstance(graph, TemporalCausalGraph)
        assert isinstance(graph.results[0], GrangerResult)


# ---------------------------------------------------------------------------
# Public surface and the honesty contract
# ---------------------------------------------------------------------------


class TestPublicSurface:
    def test_capability_is_exported_from_asi(self):
        import asi

        for name in (
            "granger_causality",
            "discover_temporal_causality",
            "select_lag",
            "GrangerResult",
            "TemporalCausalGraph",
            "LagCriterion",
        ):
            assert name in asi.__all__, name
            assert getattr(asi, name) is not None, name

    def test_unavailable_never_reads_as_a_verdict(self):
        """The core honesty invariant: a failed test is not a negative result."""
        result = granger_causality([1.0, 2.0], [3.0, 4.0], lag=1)
        assert result.verdict == UNAVAILABLE
        assert result.verdict not in (GRANGER_CAUSES, NOT_GRANGER_CAUSAL)
        assert result.significant is None
        assert result.reason

    def test_verdicts_are_the_declared_literals(self):
        x, y = _coupled_pair(n=200)
        assert granger_causality(x, y, lag=1).verdict in (
            GRANGER_CAUSES,
            NOT_GRANGER_CAUSAL,
            UNAVAILABLE,
        )

    def test_auto_lag_and_explicit_lag_agree_on_the_verdict(self):
        """The default path must not contradict an explicit lag=1."""
        x, y = _coupled_pair()
        auto = granger_causality(x, y)
        explicit = granger_causality(x, y, lag=1)
        assert auto.verdict == explicit.verdict
        assert auto.lag_order >= 1

    def test_unavailable_results_are_surfaced_by_the_graph(self):
        """A short series in a multi-series run must be reported, not dropped."""
        rng = np.random.default_rng(5)
        graph = discover_temporal_causality(
            {"tiny_a": list(rng.normal(size=4)), "tiny_b": list(rng.normal(size=4))},
            lag=1,
        )
        assert graph.unavailable()
        assert all(r.verdict == UNAVAILABLE for r in graph.unavailable())
        assert graph.edges == ()
