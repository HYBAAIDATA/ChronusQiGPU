"""Explicit, calibrated-by-host impasse policy; no self-rated intelligence claim."""

from dataclasses import dataclass
from fractions import Fraction
from ._contracts import integer, ratio


@dataclass(frozen=True)
class MetacognitivePolicy:
    understanding_floor: Fraction
    strategy_fit_floor: Fraction
    no_progress_limit: int

    def __post_init__(self):
        ratio(self.understanding_floor)
        ratio(self.strategy_fit_floor)
        integer(self.no_progress_limit, minimum=1)


def metacognitive_review(
    *, understanding, strategy_fit, no_progress, contradictory, capability_available, policy
):
    ratio(understanding)
    ratio(strategy_fit)
    integer(no_progress)
    if not capability_available:
        return "CREATE_CAPABILITY"
    if contradictory:
        return "SEEK_INDEPENDENT_REVIEW"
    if understanding < policy.understanding_floor:
        return "REFRAME_PROBLEM"
    if strategy_fit < policy.strategy_fit_floor:
        return "CHANGE_STRATEGY"
    if no_progress >= policy.no_progress_limit:
        return "GATHER_INFORMATION"
    return "CONTINUE"
