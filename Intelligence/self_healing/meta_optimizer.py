"""
Salamander Autopoietic Meta-Tuning Loop (Phase 5)
=====================================================

Implements the "frontal lobe learns how to learn" capstone: a pure,
stateful *recommender* that watches Salamander's own operational
efficiency metrics across successive generation runs and produces
exact-rational tuning adjustments for two knobs that already exist
elsewhere in the substrate:

  * **Michie exploration rate** -- how much weight the McLaren loop's
    operator-selection strategy should still give to under-explored
    (low-confidence) operators versus exploiting the currently
    highest-weighted prior. Callers apply this to their own selection
    strategy; ``AutopoieticMetaOptimizer`` never touches
    ``MichiePolicy`` weights directly (it is a pure recommender, not an
    invasive mutator -- consistent with this codebase's additive,
    non-invasive engineering discipline).
  * **E-Graph saturation depth** -- the ``max_iterations`` a caller
    passes to ``ExactCostEGraph.saturate()``.

``AutopoieticMetaOptimizer`` is deliberately *not* a machine-learning
model: every adjustment is a fixed, exact-rational step (``Fraction``
arithmetic only, never a float) applied deterministically based on
whether the most recently observed ``mean_time_to_stable_repair``
improved, regressed, or stayed flat relative to the previous
observation. As the repository matures and repairs stabilize faster,
the optimizer narrows exploration (favoring exploitation of proven
priors) and permits deeper saturation passes (since the extra search
cost is paying off); if repair times regress, it widens exploration
back out and shortens saturation passes (to fail fast and try a
different strategy rather than sinking more search budget into a
degrading trend).
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import List


class MetaOptimizerError(Exception):
    """Raised on malformed metric observations (e.g. non-exact-rational
    fields where an exact rational is required)."""


@dataclass(frozen=True)
class SelfObservedMetrics:
    """A single generation run's self-observed efficiency metrics, all
    exact-rational or integer -- never float."""

    mean_time_to_stable_repair: Fraction
    saturation_iterations_to_convergence: int
    memory_allocated_per_eclass: Fraction

    def __post_init__(self) -> None:
        if not isinstance(self.mean_time_to_stable_repair, Fraction):
            raise MetaOptimizerError(
                "mean_time_to_stable_repair must be an exact fractions.Fraction"
            )
        if not isinstance(self.memory_allocated_per_eclass, Fraction):
            raise MetaOptimizerError(
                "memory_allocated_per_eclass must be an exact fractions.Fraction"
            )
        if not isinstance(self.saturation_iterations_to_convergence, int):
            raise MetaOptimizerError("saturation_iterations_to_convergence must be an int")
        if self.mean_time_to_stable_repair < 0:
            raise MetaOptimizerError("mean_time_to_stable_repair cannot be negative")
        if self.saturation_iterations_to_convergence < 0:
            raise MetaOptimizerError("saturation_iterations_to_convergence cannot be negative")


@dataclass(frozen=True)
class TuningRecommendation:
    """A recommended pair of tuning knobs. Purely advisory -- callers
    decide how (and whether) to apply it to their own
    ``MichiePolicy``/``ExactCostEGraph.saturate()`` call sites."""

    exploration_rate: Fraction
    saturation_max_iterations: int
    trend: str  # "improving" | "regressing" | "flat" | "initial"


class AutopoieticMetaOptimizer:
    """Monitors successive ``SelfObservedMetrics`` observations and
    produces deterministic, exact-rational ``TuningRecommendation``
    adjustments. See module docstring for the exact adjustment rule.
    """

    def __init__(
        self,
        *,
        initial_exploration_rate: Fraction = Fraction(1, 2),
        initial_saturation_max_iterations: int = 10,
        min_exploration_rate: Fraction = Fraction(1, 20),
        max_exploration_rate: Fraction = Fraction(9, 10),
        min_saturation_iterations: int = 2,
        max_saturation_iterations: int = 50,
        exploration_step: Fraction = Fraction(1, 20),
        saturation_step: int = 1,
    ) -> None:
        for name, value in (
            ("initial_exploration_rate", initial_exploration_rate),
            ("min_exploration_rate", min_exploration_rate),
            ("max_exploration_rate", max_exploration_rate),
            ("exploration_step", exploration_step),
        ):
            if not isinstance(value, Fraction):
                raise MetaOptimizerError(f"{name} must be an exact fractions.Fraction, not a float")
        if min_exploration_rate > max_exploration_rate:
            raise MetaOptimizerError("min_exploration_rate cannot exceed max_exploration_rate")
        if min_saturation_iterations > max_saturation_iterations:
            raise MetaOptimizerError(
                "min_saturation_iterations cannot exceed max_saturation_iterations"
            )

        self._min_exploration_rate = min_exploration_rate
        self._max_exploration_rate = max_exploration_rate
        self._min_saturation_iterations = min_saturation_iterations
        self._max_saturation_iterations = max_saturation_iterations
        self._exploration_step = exploration_step
        self._saturation_step = saturation_step

        self.history: List[SelfObservedMetrics] = []
        self._exploration_rate = self._clamp_rate(initial_exploration_rate)
        self._saturation_max_iterations = self._clamp_saturation(initial_saturation_max_iterations)
        self._current = TuningRecommendation(
            exploration_rate=self._exploration_rate,
            saturation_max_iterations=self._saturation_max_iterations,
            trend="initial",
        )

    def _clamp_rate(self, rate: Fraction) -> Fraction:
        return max(self._min_exploration_rate, min(self._max_exploration_rate, rate))

    def _clamp_saturation(self, depth: int) -> int:
        return max(self._min_saturation_iterations, min(self._max_saturation_iterations, depth))

    @property
    def current(self) -> TuningRecommendation:
        """The most recently produced recommendation (also returned by
        the last ``record_observation`` call, if any)."""
        return self._current

    def record_observation(self, metrics: SelfObservedMetrics) -> TuningRecommendation:
        """Record one generation run's metrics and produce the next
        ``TuningRecommendation``.

        The very first observation has no prior to compare against and
        returns the initial recommendation unchanged (``trend="initial"``).
        Every subsequent observation compares ``mean_time_to_stable_repair``
        against the immediately preceding observation:

          * strictly lower (faster stable repair) -> ``"improving"``:
            narrow exploration by one step (exploit proven priors more)
            and widen saturation depth by one step (afford deeper search
            since it is paying off);
          * strictly higher (slower stable repair) -> ``"regressing"``:
            widen exploration by one step (explore alternatives again)
            and narrow saturation depth by one step (fail fast rather
            than sinking more budget into a degrading trend);
          * equal -> ``"flat"``: no change to either knob.

        All adjustments are exact ``Fraction``/``int`` steps, clamped to
        the configured min/max bounds -- the optimizer can never walk
        exploration or saturation depth outside its configured safe
        range no matter how long a trend persists.
        """
        if not isinstance(metrics, SelfObservedMetrics):
            raise MetaOptimizerError("metrics must be a SelfObservedMetrics instance")

        if not self.history:
            self.history.append(metrics)
            return self._current

        previous = self.history[-1]
        self.history.append(metrics)

        if metrics.mean_time_to_stable_repair < previous.mean_time_to_stable_repair:
            trend = "improving"
            new_rate = self._clamp_rate(self._exploration_rate - self._exploration_step)
            new_depth = self._clamp_saturation(
                self._saturation_max_iterations + self._saturation_step
            )
        elif metrics.mean_time_to_stable_repair > previous.mean_time_to_stable_repair:
            trend = "regressing"
            new_rate = self._clamp_rate(self._exploration_rate + self._exploration_step)
            new_depth = self._clamp_saturation(
                self._saturation_max_iterations - self._saturation_step
            )
        else:
            trend = "flat"
            new_rate = self._exploration_rate
            new_depth = self._saturation_max_iterations

        self._exploration_rate = new_rate
        self._saturation_max_iterations = new_depth
        self._current = TuningRecommendation(
            exploration_rate=new_rate,
            saturation_max_iterations=new_depth,
            trend=trend,
        )
        return self._current
