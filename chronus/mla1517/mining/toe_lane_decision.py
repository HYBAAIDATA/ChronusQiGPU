"""TOE as the decision authority for lane selection.

This module constructs a domain-neutral Problem for choosing the next
declared lane order. It does not replace the rule-based chooser; it
provides the Problem that a TOE machine can decide on.

Operators are the declared M32 lane orders. The objective is marked-state
probability. The query is whether lane order affects yield. The reward
is bound only from real pool responses.

theorem_proven: False
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from toe.problem import Problem


DECLARED_LANE_ORDERS = ("m32_structured", "flat_exhaustive")


def build_lane_selection_problem(
    *,
    observation: Mapping[str, Any],
    uncertain_range: tuple[float, float, float] = (0.0, 0.5, 1.0),
    forecast_steps: int = 0,
) -> Problem:
    """Build the Problem for lane-order selection.

    The reasoning path never reads the domain label. The label is
    provenance only.
    """
    return Problem(
        domain="mining.lane_selection",
        observation=dict(observation),
        operators=list(DECLARED_LANE_ORDERS),
        objective="P_marked",
        query=("lane_order", "share_yield"),
        uncertain={"effect:lane_order->share_yield": uncertain_range},
        forecast=forecast_steps if forecast_steps > 0 else None,
    )


def reward_from_pool_response(response: Mapping[str, Any]) -> float | None:
    """Bind the reward only from a real pool response.

    Returns None if the response does not carry an accepted share.
    """
    if not response.get("accepted"):
        return None
    return 1.0 if response.get("valid") else 0.0
