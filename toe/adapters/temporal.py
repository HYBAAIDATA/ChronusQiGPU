"""Time series with a control input → Problem (one-step lag structure)."""

from __future__ import annotations

from typing import Any, Mapping

from ..planning import OperatorSpec
from ..policy import Constraint, Objective
from ..problem import Problem, Structure
from .base import ProblemAdapter


class TimeSeriesAdapter(ProblemAdapter):
    """``series``: {state_name: [...], control_name: [...]}; ``state`` and
    ``control`` name the two columns; ``levels``: candidate control values;
    ``goal``: "maximize"|"minimize" the next state; optional ``cap`` puts a
    chance constraint on the next state's 95th percentile.

    Declared shape (an assumption): next = a*state + b*control + noise.
    The strengths a, b are NOT set here — the backend estimates them from
    the lagged pairs.
    """

    name = "temporal"

    def to_problem(self, raw: Mapping[str, Any]) -> Problem:
        s, u = raw["state"], raw["control"]
        xs = [float(v) for v in raw["series"][s]]
        us = [float(v) for v in raw["series"][u]]
        cur, ctl, nxt = f"{s}_t", f"{u}_t", f"{s}_next"
        self.vocabulary = {cur: f"{s} (now)", ctl: f"{u} (now)", nxt: f"{s} (next step)"}
        constraints = ()
        if raw.get("cap") is not None:
            constraints = (Constraint(f"{nxt} p95 <= cap", f"{nxt}@p95", "<=", float(raw["cap"])),)
        return Problem(
            domain=str(raw.get("domain", self.name)),
            observation={s: xs, u: us},
            state={cur: xs[-1], ctl: us[-1]},
            structure=Structure.of([(cur, nxt), (ctl, nxt)]),
            samples={cur: xs[:-1], ctl: us[:-1], nxt: xs[1:]},
            operators=(OperatorSpec(f"set_{u}", ctl, tuple(float(v) for v in raw["levels"])),),
            objective=Objective(nxt, raw.get("goal", "maximize")),
            constraints=constraints,
            query=(ctl, nxt),
            metadata={"adapter": self.name},
        )


__all__ = ["TimeSeriesAdapter"]
