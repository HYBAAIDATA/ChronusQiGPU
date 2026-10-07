"""The domain-neutral problem contract — what every domain is reduced to.

A ``Problem`` carries *structure*, never domain semantics. A domain adapter
translates its world (rows, a graph, a series, source code, a telemetry
frame …) into some subset of these fields; the TOE machine decides what to
do from which fields are present and what structure they carry. The
``domain`` label is provenance and a learning namespace — the reasoning
path never branches on it (``tests/test_toe_machine.py`` pins that two
problems differing only in ``domain`` produce identical decisions).

Fields, by the reasoning they enable:

==================  =========================================================
observation         any payload → multi-representation state (lenses)
state               current numeric world state (node -> value)
structure           supplied causal structure: weighted DAG edges, latent
                    nodes — an ASSUMPTION, recorded as such
samples             observational data columns (association, discovery,
                    implication tests, effect estimation)
operators           the declared action vocabulary (the ONLY actions)
objective           what a decision optimises
constraints         hard admissibility conditions (may bind quantiles,
                    e.g. ``Y@p05``)
query               (treatment, outcome) causal question
uncertain           declared plausible ranges of uncertain parameters,
                    e.g. ``{"edge:X->Y": (0.2, 0.8, 1.4)}`` — value of
                    information is computed over them
noise_sd            declared exogenous noise scale per node
transitions         a state-transition graph (navigation, reachability)
coordinates         declared planar coordinates of transition states
                    (the neutral geometric baseline)
navigation          (source, target) query over ``transitions``
forecast            steps ahead to extrapolate the observation's primary
                    numeric series (exact when an integer recurrence is
                    verified on every observed term)
horizon / budget    planning depth and operator-cost budget
==================  =========================================================
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Hashable, List, Mapping, Optional, Sequence, Tuple

from .causal_ladder import CausalGraph, StructuralCausalModel
from .planning import OperatorSpec
from .policy import Constraint, Objective
from .receipts import digest

PROBLEM_SCHEMA = "toe.problem/v1"


class ProblemError(ValueError):
    """The problem is malformed; TOE refuses it rather than guessing."""


@dataclass(frozen=True)
class Structure:
    """A supplied linear causal structure: ``(parent, child, weight)`` edges.

    ``latent`` names nodes that exist in the model but are never observed.
    Supplied structure is an assumption; the machine tests what it can.
    """

    edges: Tuple[Tuple[str, str, float], ...]
    nodes: Tuple[str, ...] = ()
    latent: Tuple[str, ...] = ()

    @classmethod
    def of(cls, edges: Sequence[Sequence[Any]], *, nodes: Sequence[str] = (), latent: Sequence[str] = ()) -> "Structure":
        norm = []
        for e in edges:
            if len(e) == 2:
                norm.append((str(e[0]), str(e[1]), 1.0))
            else:
                norm.append((str(e[0]), str(e[1]), float(e[2])))
        return cls(tuple(norm), tuple(str(n) for n in nodes), tuple(str(n) for n in latent))

    def all_nodes(self) -> List[str]:
        seen = list(dict.fromkeys([*self.nodes, *(e[0] for e in self.edges), *(e[1] for e in self.edges)]))
        return seen

    def graph(self, weights: Optional[Mapping[Tuple[str, str], float]] = None) -> CausalGraph:
        g = CausalGraph.from_edges([(p, c) for p, c, _ in self.edges], self.all_nodes())
        for p, c, w in self.edges:
            g.edge_weights[(p, c)] = float(w)
        for key, w in (weights or {}).items():
            if key in g.edge_weights:
                g.edge_weights[key] = float(w)
        return g

    def scm(self, weights: Optional[Mapping[Tuple[str, str], float]] = None) -> StructuralCausalModel:
        return StructuralCausalModel(graph=self.graph(weights))

    def shape_digest(self) -> str:
        """Identity of the structure's *shape* (nodes + edges, no weights):
        what learning namespaces and transfer eligibility key on."""
        return digest(
            {
                "nodes": sorted(self.all_nodes()),
                "edges": sorted([p, c] for p, c, _ in self.edges),
                "latent": sorted(self.latent),
            }
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "edges": [list(e) for e in self.edges],
            "nodes": list(self.nodes),
            "latent": list(self.latent),
        }


def _finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


@dataclass(frozen=True)
class Problem:
    """One problem, any domain. See the module docstring for the fields."""

    domain: str
    observation: Any = None
    state: Mapping[str, float] = field(default_factory=dict)
    structure: Optional[Structure] = None
    samples: Optional[Mapping[str, Sequence[float]]] = None
    operators: Sequence[OperatorSpec] = ()
    objective: Optional[Objective] = None
    constraints: Sequence[Constraint] = ()
    query: Optional[Tuple[str, str]] = None
    observed: Optional[Sequence[str]] = None
    uncertain: Mapping[str, Sequence[float]] = field(default_factory=dict)
    noise_sd: Mapping[str, float] = field(default_factory=dict)
    transitions: Optional[Sequence[Tuple[Hashable, Hashable]]] = None
    coordinates: Optional[Mapping[Hashable, Tuple[float, float]]] = None
    navigation: Optional[Tuple[Hashable, Hashable]] = None
    forecast: Optional[int] = None
    horizon: int = 1
    budget: Optional[float] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    # -- identity ----------------------------------------------------------

    def content(self) -> Dict[str, Any]:
        """Canonical JSON-safe content (metadata and domain excluded): the
        part of the problem the reasoning path may read."""
        return {
            "schema": PROBLEM_SCHEMA,
            "observation": _jsonable(self.observation),
            "state": {str(k): float(v) for k, v in sorted(self.state.items())},
            "structure": self.structure.as_dict() if self.structure else None,
            "samples": (
                {str(k): [float(x) for x in v] for k, v in sorted(self.samples.items())}
                if self.samples
                else None
            ),
            "operators": [list(op) for op in self.operators],
            "objective": self.objective.as_dict() if self.objective else None,
            "constraints": [c.as_dict() for c in self.constraints],
            "query": list(self.query) if self.query else None,
            "observed": sorted(self.observed) if self.observed is not None else None,
            "uncertain": {k: [float(x) for x in v] for k, v in sorted(self.uncertain.items())},
            "noise_sd": {str(k): float(v) for k, v in sorted(self.noise_sd.items())},
            "transitions": (
                sorted([str(a), str(b)] for a, b in self.transitions)
                if self.transitions is not None
                else None
            ),
            "coordinates": (
                {str(k): [float(c) for c in v] for k, v in sorted(self.coordinates.items(), key=lambda kv: str(kv[0]))}
                if self.coordinates is not None
                else None
            ),
            "navigation": [str(x) for x in self.navigation] if self.navigation else None,
            "forecast": self.forecast,
            "horizon": int(self.horizon),
            "budget": self.budget,
        }

    def content_digest(self) -> str:
        """Digest of what the reasoning path reads — domain-label free."""
        return digest(self.content())

    def digest(self) -> str:
        """Full identity: content plus the domain label (provenance)."""
        return digest({"domain": self.domain, "content": self.content_digest()})

    def namespace(self) -> str:
        """Learning namespace: domain + structure shape. Learning in one
        namespace never revises another (the negative-transfer guard)."""
        shape = self.structure.shape_digest()[:16] if self.structure else "unstructured"
        return f"{self.domain}::{shape}"

    # -- validation --------------------------------------------------------

    def validate(self) -> List[str]:
        """Every reason this problem cannot be reasoned about as declared."""
        issues: List[str] = []
        if not str(self.domain).strip():
            issues.append("domain label is empty")
        for k, v in self.state.items():
            if not _finite(v):
                issues.append(f"state[{k!r}] is not a finite number")
        nodes = set(self.structure.all_nodes()) if self.structure else set()
        if self.structure is not None:
            g = self.structure.graph()
            if not g.is_dag():
                issues.append("supplied structure is not a DAG")
            for p, c, w in self.structure.edges:
                if not _finite(w):
                    issues.append(f"edge {p}->{c} weight is not finite")
        for op in self.operators:
            if not isinstance(op, OperatorSpec):
                issues.append(f"operator {op!r} is not a declared OperatorSpec")
                continue
            if nodes and op.node not in nodes:
                issues.append(f"operator {op.name!r} sets unknown node {op.node!r}")
            if not all(_finite(x) for x in (*op.levels, *op.deltas, op.cost)):
                issues.append(f"operator {op.name!r} has a non-finite level/delta/cost")
        if self.objective is not None and nodes and self.objective.target not in nodes:
            issues.append(f"objective target {self.objective.target!r} is not a model node")
        if self.query is not None:
            if len(self.query) != 2:
                issues.append("query must be (treatment, outcome)")
            elif nodes and not set(self.query) <= nodes:
                issues.append(f"query {self.query} names unknown nodes")
        for name, rng in self.uncertain.items():
            if not name.startswith("edge:") or "->" not in name:
                issues.append(f"uncertain parameter {name!r} must be 'edge:P->C'")
                continue
            p, c = name[5:].split("->", 1)
            if self.structure is None or (p, c) not in {(e[0], e[1]) for e in self.structure.edges}:
                issues.append(f"uncertain parameter {name!r} names no supplied edge")
            if len(rng) < 2 or not all(_finite(x) for x in rng):
                issues.append(f"uncertain parameter {name!r} needs >= 2 finite plausible values")
        for k, v in self.noise_sd.items():
            if not _finite(v) or float(v) < 0:
                issues.append(f"noise_sd[{k!r}] must be a finite non-negative number")
        if self.samples:
            lengths = {len(v) for v in self.samples.values()}
            if len(lengths) > 1:
                issues.append("sample columns have unequal lengths")
            for k, col in self.samples.items():
                if not all(_finite(x) for x in col):
                    issues.append(f"samples[{k!r}] contains a non-finite value")
        if self.navigation is not None:
            if self.transitions is None:
                issues.append("navigation query without a transition graph")
            else:
                states = {s for e in self.transitions for s in e}
                for s in self.navigation:
                    if s not in states:
                        issues.append(f"navigation endpoint {s!r} not in the transition graph")
        if self.horizon < 1:
            issues.append("horizon must be >= 1")
        if self.forecast is not None and (not isinstance(self.forecast, int) or self.forecast < 1):
            issues.append("forecast must be a positive integer number of steps")
        return issues


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else repr(value)
    if isinstance(value, (bytes, bytearray)):
        return {"bytes_hex": bytes(value).hex()}
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return repr(value)


__all__ = ["PROBLEM_SCHEMA", "Problem", "ProblemError", "Structure"]
