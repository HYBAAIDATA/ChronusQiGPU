"""Graph / network topology → Problem."""

from __future__ import annotations

from typing import Any, Mapping

from ..problem import Problem
from .base import ProblemAdapter


class GraphAdapter(ProblemAdapter):
    """``edges``: [[a, b], ...]; ``directed`` (default False: each link is
    traversable both ways); optional ``positions`` ({node: [x, y]}) —
    declared planar coordinates; ``from`` / ``to`` — the navigation query."""

    name = "graph"

    def to_problem(self, raw: Mapping[str, Any]) -> Problem:
        edges = [(str(a), str(b)) for a, b in raw["edges"]]
        if not raw.get("directed", False):
            edges = sorted(set(edges) | {(b, a) for a, b in edges})
        nodes = sorted({n for e in edges for n in e})
        degree = {n: sum(1 for a, _b in edges if a == n) for n in nodes}
        positions = raw.get("positions")
        return Problem(
            domain=str(raw.get("domain", self.name)),
            observation={"degree": [degree[n] for n in nodes]},
            transitions=edges,
            coordinates={str(k): (float(v[0]), float(v[1])) for k, v in positions.items()} if positions else None,
            navigation=(str(raw["from"]), str(raw["to"])) if raw.get("from") is not None else None,
            metadata={"adapter": self.name, "nodes": len(nodes)},
        )


__all__ = ["GraphAdapter"]
