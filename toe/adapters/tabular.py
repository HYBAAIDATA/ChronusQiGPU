"""Tabular / numeric records → Problem."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping

from ..planning import OperatorSpec
from ..policy import Constraint, Objective
from ..problem import Problem, Structure
from .base import ProblemAdapter


class TabularAdapter(ProblemAdapter):
    """Rows of numeric records plus declared relations and levers.

    ``raw``: ``rows`` (list of {column: number}), ``relations`` ([parent,
    child] or [parent, child, weight]), optional ``latent``, ``current``
    (defaults to the last row), ``levers`` ({column: [levels]}), ``goal``
    ({"maximize"|"minimize": column}), ``limits`` ([[column, op, bound]]),
    ``question`` ([treatment, outcome]), ``noise``, ``uncertain``.
    """

    name = "tabular"

    def to_problem(self, raw: Mapping[str, Any]) -> Problem:
        rows: List[Mapping[str, float]] = list(raw["rows"])
        cols = sorted({k for r in rows for k in r})
        samples = {c: [float(r[c]) for r in rows] for c in cols if all(c in r for r in rows)}
        goal = dict(raw.get("goal") or {})
        sense, target = next(iter(goal.items())) if goal else (None, None)
        return Problem(
            domain=str(raw.get("domain", self.name)),
            observation={c: v[:64] for c, v in samples.items()},
            state=dict(raw.get("current") or rows[-1]),
            structure=Structure.of(raw.get("relations") or [], latent=raw.get("latent") or ()) if raw.get("relations") else None,
            samples=samples,
            operators=tuple(
                OperatorSpec(f"set_{c}", c, tuple(float(x) for x in lv)) for c, lv in sorted((raw.get("levers") or {}).items())
            ),
            objective=Objective(target, sense) if target else None,
            constraints=tuple(Constraint(f"{c} {op} {b}", c, op, float(b)) for c, op, b in raw.get("limits") or ()),
            query=tuple(raw["question"]) if raw.get("question") else None,
            noise_sd=dict(raw.get("noise") or {}),
            uncertain={k: tuple(v) for k, v in (raw.get("uncertain") or {}).items()},
            metadata={"adapter": self.name, "columns": cols},
        )


__all__ = ["TabularAdapter"]


def _example() -> Dict[str, Any]:  # pragma: no cover - documentation aid
    return {
        "rows": [{"x": 1.0, "y": 2.0}, {"x": 2.0, "y": 4.1}],
        "relations": [["x", "y"]],
        "levers": {"x": [0.0, 1.0]},
        "goal": {"maximize": "y"},
    }
