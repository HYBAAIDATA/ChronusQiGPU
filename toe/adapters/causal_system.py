"""An explicitly specified causal system (structural equations) → Problem."""

from __future__ import annotations

from typing import Any, Mapping

from ..planning import OperatorSpec
from ..policy import Constraint, Objective
from ..problem import Problem, Structure
from .base import ProblemAdapter


class CausalSystemAdapter(ProblemAdapter):
    """``equations``: {child: {parent: weight}}; ``factual``: observed unit
    state; ``interventions``: {node: [levels]}; ``target`` + ``sense``;
    optional ``limits``, ``latent``, ``noise_sd``, ``uncertain``,
    ``horizon``, ``budget``, ``costs`` ({node: operator cost}),
    ``question`` ([treatment, outcome]), ``samples``."""

    name = "causal_system"

    def to_problem(self, raw: Mapping[str, Any]) -> Problem:
        edges = [
            (p, c, w)
            for c, parents in sorted(raw["equations"].items())
            for p, w in sorted(parents.items())
        ]
        nodes = sorted(set(raw["equations"]) | {p for _c, ps in raw["equations"].items() for p in ps})
        costs = dict(raw.get("costs") or {})
        deltas = dict(raw.get("deltas") or {})
        ops = []
        for node in sorted(set(raw.get("interventions") or {}) | set(deltas)):
            ops.append(
                OperatorSpec(
                    f"do_{node}",
                    node,
                    tuple(float(x) for x in (raw.get("interventions") or {}).get(node, ())),
                    tuple(float(x) for x in deltas.get(node, ())),
                    float(costs.get(node, 1.0)),
                )
            )
        return Problem(
            domain=str(raw.get("domain", self.name)),
            observation=dict(raw.get("factual") or {}),
            state=dict(raw.get("factual") or {}),
            structure=Structure.of(edges, nodes=nodes, latent=raw.get("latent") or ()),
            samples=raw.get("samples"),
            operators=tuple(ops),
            objective=Objective(raw["target"], raw.get("sense", "maximize")) if raw.get("target") else None,
            constraints=tuple(Constraint(f"{v} {op} {b}", v, op, float(b)) for v, op, b in raw.get("limits") or ()),
            query=tuple(raw["question"]) if raw.get("question") else None,
            noise_sd=dict(raw.get("noise_sd") or {}),
            uncertain={k: tuple(v) for k, v in (raw.get("uncertain") or {}).items()},
            horizon=int(raw.get("horizon", 1)),
            budget=raw.get("budget"),
            metadata={"adapter": self.name},
        )


__all__ = ["CausalSystemAdapter"]
