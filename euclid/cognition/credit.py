"""Long-horizon credit assignment for observed cognition trajectories."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class CreditAssignment:
    step: int
    action: str
    credit: float
    discount: float
    source: str


def assign_discounted_credit(
    actions: Sequence[str],
    terminal_value: float,
    *,
    gamma: float = 0.9,
    source: str = "observed-terminal-outcome",
) -> tuple[CreditAssignment, ...]:
    """Assign terminal outcome backwards without inventing intermediate reward.

    The terminal value must come from an observed or authoritative outcome.
    This function only allocates that value across the executed trajectory.
    """
    value = float(terminal_value)
    if not math.isfinite(value):
        raise ValueError("terminal value must be finite")
    if not 0.0 <= float(gamma) <= 1.0:
        raise ValueError("gamma must be in [0,1]")
    if not source:
        raise ValueError("credit source is required")
    n = len(actions)
    return tuple(
        CreditAssignment(
            step=index,
            action=str(action),
            credit=value * (float(gamma) ** (n - index - 1)),
            discount=float(gamma) ** (n - index - 1),
            source=source,
        )
        for index, action in enumerate(actions)
    )


__all__ = ["CreditAssignment", "assign_discounted_credit"]
