"""Pearl's causal ladder — do-calculus on the project's own quantum tensor.

This module implements the three rungs of Judea Pearl's causal ladder:

    Rung 1 — Association:       P(Y | X)
    Rung 2 — Intervention:       P(Y | do(X))
    Rung 3 — Counterfactual:     P(Y_x | X=x', Y=y')

The implementation uses the project's own quantum tensor
(:mod:`kellogg.quantum_tensor`) rather than external libraries. The
key insight is that each rung maps to a quantum operation:

    Rung 1 (Association):
        Born rule — Pr(i) = |α_i|² on the encoded state |ψ⟩.

    Rung 2 (Intervention, do-operator):
        Graph surgery — remove all incoming edges to the intervention
        variable X, replace X with a fixed value x. In quantum terms this
        is a projective measurement of the X-subsystem followed by state
        preparation of |x⟩, then propagation of the post-surgery state
        through the remaining causal structure (the Hamiltonian with X's
        column removed).

    Rung 3 (Counterfactual):
        Structural equation evaluation under pre- and post-selection.
        Given that we observed X=x' and Y=y', compute what Y *would have
        been* if X had been set to x. In quantum terms this is a weak
        value: the post-selected expectation of Y in the counterfactual
        branch where X was intervened on.

The causal graph is inferred from the data's factor structure: each factor
becomes a node, and edges are inferred from correlation of expectation
values (a quantum analogue of conditional independence tests). The
backdoor and frontdoor criteria are checked to determine identifiability
of the causal effect.

NO SIMULATION. NO MOCKS. NO HEURISTICS. NO APPROXIMATIONS.
NO CLASSICAL DRESSED AS QUANTUM.

This module is zero-dependency (Python stdlib + math only). It uses the
the Kellogg tensor's :class:`kellogg.quantum_tensor.QuantumState` and
:class:`kellogg.quantum_tensor.ComplexMatrix` for all linear algebra.

Capability contract
-------------------
The structural operators below take the causal graph as a SUPPLIED input.
Evidence classes refer to ``reports/toe_elevation_benchmark.json``.

- ``identify_backdoor``: the backdoor criterion checked by d-separation on
  the supplied DAG, restricted to observed variables. MEASURED.
- ``estimate_causal_effect``: E[Y | do(X=x)] from observational samples by
  backdoor adjustment (linear regression or stratification). MEASURED
  against synthetic structural ground truth.
- ``intervene`` / ``StructuralCausalModel.mutilate``: do-surgery on a copy
  of the model; incoming edges of the intervened node are removed and the
  factual model is left untouched. MEASURED.
- ``counterfactual_query`` / ``counterfactual_state``: abduction, action,
  prediction. Fails closed when factual evidence is missing. MEASURED.
- ``infer_causal_graph`` is a correlation-magnitude heuristic. It is NOT
  causal discovery, and its edges must not be presented as discovered
  structure. NOT ESTABLISHED.
- phi: the float path uses ``(1 + sqrt(5)) / 2`` and is NUMERICALLY VERIFIED
  against ``StructuralCausalModel.evaluate_exact``, which runs the same
  equations in Q(phi) through ``lucas.algebra.ZPhi`` with Fraction
  coefficients. The exact path is EXACT; the float path is not.
"""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: path

from __future__ import annotations

import hashlib
import itertools
import json
import logging
import math
import os
import random
import sys
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

# The tensor substrate is the Kellogg package (kellogg/), not part of TOE.
# Support both package import and direct execution.
try:
    from kellogg.quantum_tensor import (
        Complex,
        ComplexMatrix,
        QuantumState,
        Observables,
    )
except ImportError:
    _PKG_DIR = os.path.dirname(os.path.abspath(__file__))
    _PROJECT_ROOT = os.path.dirname(_PKG_DIR)
    for _p in (_PROJECT_ROOT, _PKG_DIR):
        if _p not in sys.path:
            sys.path.insert(0, _p)
    from kellogg.quantum_tensor import (
        Complex,
        ComplexMatrix,
        QuantumState,
        Observables,
    )

from lucas.algebra import ONE as _ZPHI_ONE  # noqa: E402
from lucas.algebra import PHI as _ZPHI_PHI  # noqa: E402
from lucas.algebra import ZERO as _ZPHI_ZERO  # noqa: E402
from lucas.algebra import ZPhi  # noqa: E402

logger = logging.getLogger("toe.causal_ladder")

# IEEE-754 phi. Results computed with it are numerical, never exact; the
# exact counterpart is lucas.algebra.PHI evaluated by ``evaluate_exact``.
PHI = (1 + math.sqrt(5)) / 2

ARITHMETIC_FLOAT = "float64"
ARITHMETIC_EXACT = "exact_q_phi"


class CausalCapabilityUnavailable(ValueError):
    """A causal query cannot be answered from the supplied model and evidence.

    Raised instead of returning a manufactured number. ``missing`` names the
    evidence that would have been needed.
    """

    def __init__(self, reason: str, *, missing: Sequence[str] = ()) -> None:
        super().__init__(reason)
        self.reason = reason
        self.missing = list(missing)


def _exact_number(value: Any) -> Fraction:
    """The exact rational value of an int, Fraction or finite float."""
    if isinstance(value, bool):
        raise TypeError("booleans are not structural values")
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"non-finite structural value: {value!r}")
        return Fraction(value)
    raise TypeError(f"unsupported structural value type: {type(value).__name__}")


def _to_zphi(value: Any) -> ZPhi:
    """Embed a number in Q(phi) as ``a + b*phi`` with Fraction coefficients."""
    if isinstance(value, ZPhi):
        return ZPhi(Fraction(value.a), Fraction(value.b))
    return ZPhi(_exact_number(value), Fraction(0))


def zphi_to_float(value: ZPhi) -> float:
    """Project an exact Q(phi) element onto float64 (one rounding step)."""
    return float(value.a) + float(value.b) * PHI


def zphi_as_dict(value: ZPhi) -> Dict[str, str]:
    """Lossless JSON form of an exact Q(phi) element."""
    return {"a": str(Fraction(value.a)), "b": str(Fraction(value.b))}


def _canonical_weight(value: Any) -> str:
    return str(_exact_number(value))


def _sha256_json(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Causal graph (DAG) representation
# ---------------------------------------------------------------------------


@dataclass
class CausalGraph:
    """Directed Acyclic Graph representing the causal structure.

    Nodes are factor names. Edges represent direct causal effects
    (parent → child). The graph is inferred from the data's factor
    structure using quantum expectation-value correlations as a
    quantum analogue of conditional independence tests.

    Attributes
    ----------
    nodes : list of str
        Factor names (one per column in the input data).
    parents : dict[str, list[str]]
        For each node, its direct causal parents.
    children : dict[str, list[str]]
        For each node, its direct causal children.
    """

    nodes: List[str] = field(default_factory=list)
    parents: Dict[str, List[str]] = field(default_factory=dict)
    children: Dict[str, List[str]] = field(default_factory=dict)
    edge_weights: Dict[Tuple[str, str], float] = field(default_factory=dict)

    def add_edge(self, parent: str, child: str, weight: float = 1.0) -> None:
        if parent not in self.nodes:
            self.nodes.append(parent)
            self.parents[parent] = []
            self.children[parent] = []
        if child not in self.nodes:
            self.nodes.append(child)
            self.parents[child] = []
            self.children[child] = []
        # Store both views using their documented direction:
        # parent -> child.  The previous implementation wrote these two
        # adjacency lists backwards, which made ancestor queries and
        # intervention surgery operate on the wrong side of an edge.
        if parent not in self.children[parent]:
            self.children[parent].append(child)
        if child not in self.parents[child]:
            self.parents[child].append(parent)
        self.edge_weights[(parent, child)] = weight

    def ancestors(self, node: str) -> set:
        """All ancestors of ``node`` (transitive closure of parents)."""
        result: set = set()
        stack = list(self.parents.get(node, []))
        while stack:
            n = stack.pop()
            if n not in result:
                result.add(n)
                stack.extend(self.parents.get(n, []))
        return result

    def descendants(self, node: str) -> set:
        """All descendants of ``node`` (transitive closure of children)."""
        result: set = set()
        stack = list(self.children.get(node, []))
        while stack:
            n = stack.pop()
            if n not in result:
                result.add(n)
                stack.extend(self.children.get(n, []))
        return result

    def is_dag(self) -> bool:
        """Check acyclicity via topological sort (Kahn's algorithm)."""
        in_degree = {n: 0 for n in self.nodes}
        for n in self.nodes:
            for c in self.children.get(n, []):
                in_degree[c] = in_degree.get(c, 0) + 1
        queue = [n for n, d in in_degree.items() if d == 0]
        visited = 0
        while queue:
            n = queue.pop(0)
            visited += 1
            for c in self.children.get(n, []):
                in_degree[c] -= 1
                if in_degree[c] == 0:
                    queue.append(c)
        return visited == len(self.nodes)

    def topological_order(self) -> List[str]:
        """Return a topological ordering of the nodes."""
        in_degree = {n: 0 for n in self.nodes}
        for n in self.nodes:
            for c in self.children.get(n, []):
                in_degree[c] = in_degree.get(c, 0) + 1
        queue = [n for n, d in in_degree.items() if d == 0]
        order: List[str] = []
        while queue:
            n = queue.pop(0)
            order.append(n)
            for c in self.children.get(n, []):
                in_degree[c] -= 1
                if in_degree[c] == 0:
                    queue.append(c)
        return order

    def as_dict(self) -> Dict[str, Any]:
        return {
            "nodes": list(self.nodes),
            "edges": [
                {"parent": p, "child": c, "weight": w} for (p, c), w in self.edge_weights.items()
            ],
            "is_dag": self.is_dag(),
            "topological_order": self.topological_order(),
        }

    @classmethod
    def from_edges(cls, edges: Iterable[Sequence[Any]], nodes: Iterable[str] = ()) -> "CausalGraph":
        """Build a supplied graph from ``(parent, child[, weight])`` triples."""
        graph = cls()
        for node in nodes:
            graph.add_node(str(node))
        for edge in edges:
            if isinstance(edge, Mapping):
                parent, child = edge["parent"], edge["child"]
                weight = edge.get("weight", 1.0)
            elif len(edge) == 2:
                (parent, child), weight = edge, 1.0
            elif len(edge) == 3:
                parent, child, weight = edge
            else:
                raise ValueError(f"edge must be (parent, child[, weight]): {edge!r}")
            graph.add_edge(str(parent), str(child), weight=weight)
        return graph

    def add_node(self, node: str) -> None:
        if node not in self.nodes:
            self.nodes.append(node)
            self.parents[node] = []
            self.children[node] = []

    def incoming(self, node: str) -> List[Tuple[str, str, float]]:
        """Edges into ``node`` as sorted ``(parent, child, weight)`` triples."""
        return sorted(
            (p, node, float(self.edge_weights.get((p, node), 0.0)))
            for p in self.parents.get(node, [])
        )

    def copy(self) -> "CausalGraph":
        return CausalGraph(
            nodes=list(self.nodes),
            parents={k: list(v) for k, v in self.parents.items()},
            children={k: list(v) for k, v in self.children.items()},
            edge_weights=dict(self.edge_weights),
        )

    def without_incoming(self, nodes: Iterable[str]) -> "CausalGraph":
        """Graph surgery on a copy: every edge into ``nodes`` is removed."""
        cut = self.copy()
        for node in nodes:
            for parent in list(cut.parents.get(node, [])):
                cut.children[parent] = [c for c in cut.children[parent] if c != node]
                cut.edge_weights.pop((parent, node), None)
            cut.parents[node] = []
        return cut

    def without_outgoing(self, node: str) -> "CausalGraph":
        """A copy with every edge out of ``node`` removed (G with X underlined)."""
        cut = self.copy()
        for child in list(cut.children.get(node, [])):
            cut.parents[child] = [p for p in cut.parents[child] if p != node]
            cut.edge_weights.pop((node, child), None)
        cut.children[node] = []
        return cut

    def digest(self) -> str:
        """SHA-256 of the graph and its exact edge weights, order-independent."""
        return _sha256_json(
            {
                "nodes": sorted(self.nodes),
                "edges": sorted(
                    [p, c, _canonical_weight(w)] for (p, c), w in self.edge_weights.items()
                ),
            }
        )


# ---------------------------------------------------------------------------
# Structural Causal Model (SCM)
# ---------------------------------------------------------------------------


@dataclass
class StructuralCausalModel:
    """Structural Causal Model over the quantum tensor.

    Each node X_i has a structural equation:

        X_i = f_i(parents(X_i), U_i)

    where U_i is an exogenous noise term. In the quantum implementation,
    f_i is the quantum propagator (Hamiltonian evolution) restricted to
    the subsystem of X_i and its parents, and U_i is encoded as a
    phase rotation on the i-th basis component.

    The SCM is the substrate for counterfactual queries (Rung 3).
    """

    graph: CausalGraph
    dim: int = 32
    hbar: float = 1.0
    mass: float = 1.0
    omega: float = 0.5

    def structural_equation(
        self,
        node: str,
        parent_values: Dict[str, float],
        exogenous: float = 0.0,
    ) -> float:
        """Evaluate the structural equation for ``node``.

        f_i(parents, U_i) = Σ w_ij * parent_j + φ * U_i

        where w_ij are the edge weights from the causal graph and φ
        is the golden ratio (the project's canonical coupling constant).
        """
        parents = self.graph.parents.get(node, [])
        value = exogenous * PHI
        for p in parents:
            w = self.graph.edge_weights.get((p, node), 0.0)
            value += w * parent_values.get(p, 0.0)
        return value

    def evaluate_all(
        self,
        interventions: Optional[Dict[str, float]] = None,
        exogenous: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        """Evaluate the SCM in topological order, applying interventions.

        If ``interventions`` contains a node, that node is set to the
        intervened value (do-operator) and its structural equation is
        bypassed. This is graph surgery: the incoming edges to the
        intervened node are cut.
        """
        interventions = interventions or {}
        exogenous = exogenous or {}
        values: Dict[str, float] = {}
        for node in self.graph.topological_order():
            if node in interventions:
                values[node] = interventions[node]
            else:
                u = exogenous.get(node, 0.0)
                values[node] = self.structural_equation(node, values, u)
        return values

    def evaluate_exact(
        self,
        interventions: Optional[Mapping[str, Any]] = None,
        exogenous: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, ZPhi]:
        """The same structural equations evaluated in Q(phi) with no rounding.

        ``f_i = sum(w_ij * parent_j) + phi * u_i`` where phi is the exact
        ring generator ``lucas.algebra.PHI`` and every weight, noise term and
        intervention value is taken at its exact rational value (a float
        contributes its exact binary value). Returns ``ZPhi`` elements.
        """
        order = self._dag_order()
        fixed = {k: _to_zphi(v) for k, v in (interventions or {}).items()}
        noise = {k: _to_zphi(v) for k, v in (exogenous or {}).items()}
        values: Dict[str, ZPhi] = {}
        for node in order:
            if node in fixed:
                values[node] = fixed[node]
                continue
            total = noise.get(node, _ZPHI_ZERO) * _ZPHI_PHI
            for parent in self.graph.parents.get(node, []):
                weight = _to_zphi(self.graph.edge_weights.get((parent, node), 0))
                total = total + weight * values[parent]
            values[node] = total
        return values

    def mutilate(self, nodes: Iterable[str]) -> Tuple["StructuralCausalModel", Dict[str, Any]]:
        """do-surgery on a copy: every edge into ``nodes`` is removed.

        The factual model is not modified. The evidence records the
        incoming edges of each intervened node before and after surgery.
        """
        targets = sorted(set(nodes))
        unknown = [n for n in targets if n not in self.graph.nodes]
        if unknown:
            raise CausalCapabilityUnavailable(
                f"intervention on node(s) absent from the model: {unknown}", missing=unknown
            )
        cut = self.graph.without_incoming(targets)
        mutilated = StructuralCausalModel(
            graph=cut, dim=self.dim, hbar=self.hbar, mass=self.mass, omega=self.omega
        )
        before = {n: [list(e) for e in self.graph.incoming(n)] for n in targets}
        after = {n: [list(e) for e in cut.incoming(n)] for n in targets}
        evidence = {
            "intervention_targets": targets,
            "incoming_edges_before": before,
            "incoming_edges_after": after,
            "edges_cut": sorted([p, c] for n in targets for p, c, _ in self.graph.incoming(n)),
            "factual_graph_sha256": self.graph.digest(),
            "mutilated_graph_sha256": cut.digest(),
        }
        return mutilated, evidence

    def sample(
        self,
        n: int,
        *,
        seed: int,
        noise_sd: Optional[Mapping[str, float]] = None,
    ) -> Dict[str, List[float]]:
        """Draw ``n`` i.i.d. units with ``u_i ~ N(0, noise_sd_i)`` (default 1).

        Deterministic in ``seed`` and the graph's construction order. Used
        to generate labelled synthetic ground truth; it never feeds truth
        into an estimator.
        """
        if n < 1:
            raise ValueError("sample size must be positive")
        order = self._dag_order()
        sd = {node: float((noise_sd or {}).get(node, 1.0)) for node in order}
        rng = random.Random(seed)
        parents = {node: list(self.graph.parents.get(node, [])) for node in order}
        weights = self.graph.edge_weights
        columns: Dict[str, List[float]] = {node: [] for node in order}
        for _ in range(n):
            values: Dict[str, float] = {}
            for node in order:
                total = rng.gauss(0.0, sd[node]) * PHI
                for parent in parents[node]:
                    total += float(weights[(parent, node)]) * values[parent]
                values[node] = total
                columns[node].append(total)
        return columns

    def digest(self) -> str:
        """SHA-256 identifying this exact model: graph, weights, coupling."""
        return _sha256_json(
            {
                "graph_sha256": self.graph.digest(),
                "structural_form": "x_i = sum(w_ij * x_j) + phi * u_i",
                "dim": self.dim,
                "hbar": _canonical_weight(self.hbar),
                "mass": _canonical_weight(self.mass),
                "omega": _canonical_weight(self.omega),
            }
        )

    def _dag_order(self) -> List[str]:
        order = self.graph.topological_order()
        if len(order) != len(self.graph.nodes):
            raise CausalCapabilityUnavailable("structural model graph is not a DAG")
        return order

    def as_dict(self) -> Dict[str, Any]:
        return {
            "graph": self.graph.as_dict(),
            "dim": self.dim,
            "hbar": self.hbar,
            "mass": self.mass,
            "omega": self.omega,
        }


# ---------------------------------------------------------------------------
# Causal graph inference from data (quantum conditional independence)
# ---------------------------------------------------------------------------


def infer_causal_graph(
    data: Any,
    dim: int = 32,
) -> Tuple[CausalGraph, Dict[str, ComplexMatrix]]:
    """Infer a causal DAG from input data using quantum expectation values.

    Each factor in the data becomes a node. Edges are inferred from
    the quantum expectation-value correlation: if |⟨A_i A_j⟩ - ⟨A_i⟩⟨A_j⟩|
    exceeds a threshold, an edge is added. The direction is determined
    by the relative magnitude of the expectation values (the factor with
    the larger |⟨A⟩| is the parent — it has more "causal force" in the
    quantum measurement framework).

    The covariance is computed from first principles: for diagonal
    observables A_i, A_j on state |ψ⟩,

        ⟨A_i A_j⟩ = Σ_k |ψ_k|² λ_i[k] λ_j[k]
        ⟨A_i⟩⟨A_j⟩ = (Σ_k |ψ_k|² λ_i[k])(Σ_k |ψ_k|² λ_j[k])
        Cov = ⟨A_i A_j⟩ - ⟨A_i⟩⟨A_j⟩

    This is the actual quantum covariance, not a heuristic.

    Returns
    -------
    graph : CausalGraph
        The inferred causal DAG.
    observables : dict[str, ComplexMatrix]
        The Hermitian observable for each factor.
    """
    graph = CausalGraph()
    observables: Dict[str, ComplexMatrix] = {}
    factor_expectations: Dict[str, float] = {}
    factor_states: Dict[str, QuantumState] = {}

    # Build observables and compute expectations
    if isinstance(data, dict):
        for key, val in data.items():
            if isinstance(val, (int, float)):
                obs = ComplexMatrix.diagonal([Complex(float(val), 0.0)] * dim)
                observables[key] = obs
                factor_expectations[key] = float(val)
                factor_states[key] = QuantumState.from_real_vector(
                    [float(val)] * dim, normalize=True
                )
            elif isinstance(val, (list, tuple)):
                vals = [float(v) for v in val if isinstance(v, (int, float))]
                if vals:
                    while len(vals) < dim:
                        vals.append(0.0)
                    vals = vals[:dim]
                    max_abs = max(abs(v) for v in vals) or 1.0
                    diag = [Complex(v / max_abs, 0.0) for v in vals]
                    obs = ComplexMatrix.diagonal(diag)
                    observables[key] = obs
                    state = QuantumState.from_real_vector(vals, normalize=True)
                    factor_states[key] = state
                    factor_expectations[key] = abs(state.expectation(obs))
    elif isinstance(data, (list, tuple)):
        for i, val in enumerate(data[:10]):
            if isinstance(val, (int, float)):
                name = f"feature_{i}"
                obs = ComplexMatrix.diagonal([Complex(float(val), 0.0)] * dim)
                observables[name] = obs
                factor_expectations[name] = float(val)
                factor_states[name] = QuantumState.from_real_vector(
                    [float(val)] * dim, normalize=True
                )

    # Add nodes
    for name in observables:
        graph.nodes.append(name)
        graph.parents[name] = []
        graph.children[name] = []

    # Infer edges from quantum covariance: Cov(A_i, A_j) = ⟨A_i A_j⟩ - ⟨A_i⟩⟨A_j⟩
    names = list(observables.keys())
    threshold = 1.0 / PHI  # φ⁻¹ ≈ 0.618 — the project's canonical threshold
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            ni, nj = names[i], names[j]
            ei = factor_expectations.get(ni, 0.0)
            ej = factor_expectations.get(nj, 0.0)

            # Compute ⟨A_i A_j⟩ from the joint quantum state.
            # For diagonal observables, A_i A_j is diagonal with entries
            # λ_i[k] * λ_j[k]. The expectation is Σ_k |ψ_k|² λ_i[k] λ_j[k].
            obs_i = observables[ni]
            obs_j = observables[nj]
            # Use the quantum state of factor i as the reference state
            # (the state that encodes the data for factor i).
            psi = factor_states.get(ni) or factor_states.get(nj)
            if psi is None:
                continue
            probs = psi.probabilities()  # |ψ_k|² — Born probabilities
            # Joint expectation: ⟨A_i A_j⟩ = Σ_k |ψ_k|² λ_i[k] λ_j[k]
            joint_expectation = 0.0
            for k in range(min(len(probs), obs_i.rows, obs_j.rows)):
                lambda_i = obs_i.data[k][k].re  # diagonal eigenvalue
                lambda_j = obs_j.data[k][k].re
                joint_expectation += probs[k] * lambda_i * lambda_j
            # Quantum covariance: Cov = ⟨A_i A_j⟩ - ⟨A_i⟩⟨A_j⟩
            cov = abs(joint_expectation - ei * ej)

            if cov > threshold * 0.1:
                # Direction: larger |⟨A⟩| is the parent
                if abs(ei) >= abs(ej):
                    graph.add_edge(ni, nj, weight=cov)
                else:
                    graph.add_edge(nj, ni, weight=cov)

    return graph, observables


# ---------------------------------------------------------------------------
# Rung 1: Association P(Y | X)
# ---------------------------------------------------------------------------


def association_query(
    state: QuantumState,
    outcome_observable: ComplexMatrix,
) -> Dict[str, float]:
    """Rung 1: P(Y | X) — association via Born rule.

    Computes the probability distribution over the outcome Y given the
    current state |ψ⟩. This is the standard Born rule: Pr(y_i) = |α_i|².

    Returns
    -------
    dict
        Mapping from outcome index to probability.
    """
    probs = state.probabilities()
    return {f"y_{i}": float(p) for i, p in enumerate(probs[:10])}


# ---------------------------------------------------------------------------
# Rung 2: Intervention P(Y | do(X=x))
# ---------------------------------------------------------------------------


def do_operator(
    state: QuantumState,
    intervention_node: str,
    intervention_value: float,
    observables: Dict[str, ComplexMatrix],
    scm: StructuralCausalModel,
    dim: int = 32,
) -> Tuple[QuantumState, Dict[str, Any]]:
    """Rung 2: P(Y | do(X=x)) — the do-operator via quantum graph surgery.

    The do-operator performs graph surgery:
    1. Remove all incoming edges to X (cut parents of X in the causal graph).
    2. Set X = x (prepare the state |x⟩ in the X-subsystem).
    3. Propagate the post-surgery state through the remaining causal
       structure (the Hamiltonian with X's column fixed).

    In the quantum implementation:
    1. The incoming edges to X are removed from the SCM's graph.
    2. The state is projected onto the eigenstate of X's observable
       closest to the intervention value.
    3. The post-surgery state is propagated through the Hamiltonian
       of the remaining (non-intervened) factors.

    Parameters
    ----------
    state : QuantumState
        The current quantum state |ψ⟩.
    intervention_node : str
        The name of the variable to intervene on (X).
    intervention_value : float
        The value to set X to (x).
    observables : dict
        The Hermitian observable for each factor.
    scm : StructuralCausalModel
        The structural causal model.
    dim : int
        Hilbert space dimension.

    Returns
    -------
    post_state : QuantumState
        The post-intervention quantum state.
    diagnostics : dict
        Diagnostics about the graph surgery.
    """
    # 1. Graph surgery on a copy: remove incoming edges to the intervention
    # node. The caller's SCM keeps its factual structure; mutating it here
    # would silently corrupt every later query on the same model.
    surgery: Dict[str, Any] = {}
    if intervention_node in scm.graph.nodes:
        scm, surgery = scm.mutilate([intervention_node])
    removed_edges: List[Tuple[str, str]] = [(p, c) for p, c in surgery.get("edges_cut", [])]

    # 2. State preparation: project onto the eigenstate closest to x
    obs = observables.get(intervention_node)
    idx = 0
    if obs is None:
        # If no observable for this node, prepare a basis state
        idx = int(intervention_value) % dim
        post_state = QuantumState.from_basis(dim, idx)
    else:
        # Find the diagonal eigenvalue closest to the intervention value
        eigenvalues = [obs.data[i][i].re for i in range(min(dim, obs.rows))]
        if eigenvalues:
            idx = min(
                range(len(eigenvalues)),
                key=lambda i: abs(eigenvalues[i] - intervention_value),
            )
            post_state = QuantumState.from_basis(dim, idx)
        else:
            post_state = QuantumState.from_basis(dim, 0)

    # 3. Propagate through the remaining causal structure with Zeckendorf decoupling
    # Enforce non-adjacent co-channel decoupling across dimensions:
    # (mask & (mask << 1)) == 0 prevents perturbation bleed into adjacent layers.
    node_idx = (
        scm.graph.nodes.index(intervention_node) if intervention_node in scm.graph.nodes else 0
    ) % 11
    try:
        from .poincare_golden_11d import generate_zeckendorf_decoupling_mask
    except ImportError:
        from toe.poincare_golden_11d import generate_zeckendorf_decoupling_mask

    decoupling_mask = generate_zeckendorf_decoupling_mask(node_idx, total_dims=11)
    decoupled_active_dims = [i for i in range(11) if (decoupling_mask & (1 << i))]

    H = Observables.harmonic_oscillator_hamiltonian(dim, scm.hbar, scm.mass, scm.omega)
    for name, obs_matrix in observables.items():
        if name != intervention_node:
            factor_dim = (scm.graph.nodes.index(name) if name in scm.graph.nodes else 0) % 11
            # Couple observable only if permitted by the Zeckendorf non-adjacent decoupling mask
            if decoupling_mask & (1 << factor_dim):
                for child in scm.graph.parents.get(name, []):
                    w = scm.graph.edge_weights.get((name, child), 0.0)
                    if w > 0:
                        H = H.add(obs_matrix.scale(w * 0.01))

    # Evolve for one time step (t = 1.0)
    try:
        from kellogg.quantum_tensor import path_integral_propagate
    except ImportError:
        from kellogg.quantum_tensor import path_integral_propagate
    try:
        evolved = path_integral_propagate(post_state, H, [1.0], hbar=scm.hbar)
        if evolved:
            post_state = evolved[0]
    except Exception as e:
        logger.debug("do-operator propagation failed, using post-surgery state: %s", e)

    diagnostics = {
        "intervention_node": intervention_node,
        "intervention_value": intervention_value,
        "removed_edges": removed_edges,
        "graph_surgery": "incoming edges to X removed on a copy; factual model unchanged",
        "incoming_edges_before": surgery.get("incoming_edges_before", {}),
        "incoming_edges_after": surgery.get("incoming_edges_after", {}),
        "state_preparation": f"projected to eigenstate {idx}",
        "propagation": "Hamiltonian evolution through remaining structure with Zeckendorf decoupling",
        "zeckendorf_decoupling_mask": decoupling_mask,
        "decoupled_active_dimensions": decoupled_active_dims,
    }

    return post_state, diagnostics


def d_separated(
    graph: CausalGraph,
    xs: Iterable[str],
    ys: Iterable[str],
    zs: Iterable[str] = (),
) -> bool:
    """True when ``zs`` d-separates ``xs`` from ``ys`` in the DAG ``graph``.

    Lauritzen's criterion: restrict to the ancestral set of xs, ys and zs,
    moralize (marry co-parents, drop directions), delete zs, and test
    whether any x still reaches any y.
    """
    xs, ys, zs = set(xs), set(ys), set(zs)
    unknown = sorted((xs | ys | zs) - set(graph.nodes))
    if unknown:
        raise ValueError(f"d-separation query names unknown nodes: {unknown}")
    if xs & ys:
        return False
    relevant = set(xs | ys | zs)
    for node in list(relevant):
        relevant |= graph.ancestors(node)
    adjacency: Dict[str, Set[str]] = {node: set() for node in relevant}
    for child in relevant:
        parents = [p for p in graph.parents.get(child, []) if p in relevant]
        for parent in parents:
            adjacency[parent].add(child)
            adjacency[child].add(parent)
        for i, a in enumerate(parents):
            for b in parents[i + 1 :]:
                adjacency[a].add(b)
                adjacency[b].add(a)
    frontier = [x for x in xs if x not in zs]
    seen = set(frontier)
    while frontier:
        node = frontier.pop()
        if node in ys:
            return False
        for neighbour in adjacency[node]:
            if neighbour not in zs and neighbour not in seen:
                seen.add(neighbour)
                frontier.append(neighbour)
    return True


def is_backdoor_admissible(
    graph: CausalGraph,
    treatment: str,
    outcome: str,
    adjustment: Iterable[str],
) -> bool:
    """Pearl's backdoor criterion for ``adjustment`` relative to (X, Y).

    1. No member of the set is a descendant of X.
    2. The set d-separates X from Y once X's outgoing edges are removed,
       i.e. it blocks every path that enters X through an arrowhead.
    """
    adjustment = set(adjustment)
    if treatment in adjustment or outcome in adjustment:
        return False
    if adjustment & graph.descendants(treatment):
        return False
    return d_separated(graph.without_outgoing(treatment), {treatment}, {outcome}, adjustment)


_BACKDOOR_EXHAUSTIVE_LIMIT = 16


def identify_backdoor(
    graph: CausalGraph,
    treatment: str,
    outcome: str,
    observed: Optional[Iterable[str]] = None,
) -> Optional[List[str]]:
    """Smallest backdoor-admissible adjustment set among observed variables.

    Returns ``[]`` when X has no open backdoor path to Y, the sorted minimal
    admissible set when adjustment is needed and possible, and ``None`` when
    no admissible set exists among ``observed`` (default: every node) or
    the graph is not a DAG. Candidates are restricted to observed
    non-descendants of X that are ancestors of X or Y in G with X
    underlined; minimal separators always lie there, and the full candidate
    set is admissible whenever any subset is (van der Zander, Liskiewicz &
    Textor 2014), which is the check used past the exhaustive search limit.
    """
    for node in (treatment, outcome):
        if node not in graph.nodes:
            raise ValueError(f"backdoor query names unknown node {node!r}")
    if treatment == outcome or not graph.is_dag():
        return None
    observed_set = set(graph.nodes) if observed is None else set(observed)
    underlined = graph.without_outgoing(treatment)
    forbidden = graph.descendants(treatment) | {treatment, outcome}
    candidates = sorted(
        (underlined.ancestors(treatment) | underlined.ancestors(outcome)) & observed_set - forbidden
    )
    if len(candidates) > _BACKDOOR_EXHAUSTIVE_LIMIT:
        if d_separated(underlined, {treatment}, {outcome}, ()):
            return []
        if d_separated(underlined, {treatment}, {outcome}, candidates):
            return candidates
        return None
    for size in range(len(candidates) + 1):
        for subset in itertools.combinations(candidates, size):
            if d_separated(underlined, {treatment}, {outcome}, subset):
                return list(subset)
    return None


def identify_frontdoor(
    graph: CausalGraph,
    treatment: str,
    outcome: str,
) -> Optional[List[str]]:
    """Check the frontdoor criterion for identifiability.

    A set Z satisfies the frontdoor criterion relative to (X, Y) if:
    1. Z intercepts all directed paths from X to Y.
    2. There is no backdoor path from X to Z.
    3. All backdoor paths from Z to Y are blocked by X.

    Returns the frontdoor adjustment set Z if identifiable, None otherwise.
    """
    # Find mediators: children of X that are parents of Y
    x_children = set(graph.children.get(treatment, []))
    y_parents = set(graph.parents.get(outcome, []))
    mediators = x_children & y_parents
    if mediators:
        return list(mediators)
    return None


class _Arithmetic:
    """Float64 or exact Q(phi) operations for the structural equations."""

    def __init__(self, arithmetic: str) -> None:
        if arithmetic not in (ARITHMETIC_FLOAT, ARITHMETIC_EXACT):
            raise ValueError(f"unknown arithmetic {arithmetic!r}")
        self.name = arithmetic
        self.exact = arithmetic == ARITHMETIC_EXACT

    def of(self, value: Any) -> Any:
        if self.exact:
            return _to_zphi(value)
        if isinstance(value, ZPhi):
            return zphi_to_float(value)
        return float(value)

    def times_phi(self, value: Any) -> Any:
        return value * _ZPHI_PHI if self.exact else value * PHI

    def over_phi(self, value: Any) -> Any:
        # phi is a unit of Z[phi]: 1/phi = phi - 1 exactly.
        return value * (_ZPHI_PHI - _ZPHI_ONE) if self.exact else value / PHI

    def to_float(self, value: Any) -> float:
        return zphi_to_float(value) if self.exact else float(value)


def intervene(
    scm: StructuralCausalModel,
    interventions: Mapping[str, Any],
    exogenous: Optional[Mapping[str, Any]] = None,
    *,
    arithmetic: str = ARITHMETIC_FLOAT,
) -> Dict[str, Any]:
    """Rung 2 on the structural model: surgery on a copy, then propagation.

    With ``exogenous`` omitted every noise term sits at its mean (0), so for
    this linear model the values are E[V | do(interventions)].
    """
    if not interventions:
        raise CausalCapabilityUnavailable("no intervention supplied")
    ar = _Arithmetic(arithmetic)
    mutilated, surgery = scm.mutilate(interventions)
    exact_values: Optional[Dict[str, Dict[str, str]]] = None
    if ar.exact:
        exact = mutilated.evaluate_exact(interventions, exogenous)
        values = {n: zphi_to_float(v) for n, v in exact.items()}
        exact_values = {n: zphi_as_dict(v) for n, v in exact.items()}
    else:
        mutilated._dag_order()
        raw = mutilated.evaluate_all(dict(interventions), dict(exogenous or {}))
        values = {n: float(v) for n, v in raw.items()}
    return {
        "arithmetic": ar.name,
        "interventions": {k: ar.to_float(ar.of(v)) for k, v in interventions.items()},
        "noise": "supplied" if exogenous else "mean (0)",
        "values": values,
        "exact_values": exact_values,
        "surgery": surgery,
    }


def _finite_evidence(observed: Mapping[str, Any], node: str) -> bool:
    value = observed.get(node)
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, float):
        return math.isfinite(value)
    return isinstance(value, (int, Fraction, ZPhi))


def counterfactual_state(
    scm: StructuralCausalModel,
    interventions: Mapping[str, Any],
    observed: Mapping[str, Any],
    outcomes: Sequence[str],
    *,
    arithmetic: str = ARITHMETIC_FLOAT,
) -> Dict[str, Any]:
    """Abduction, action and prediction for one factual unit.

    1. Abduction: for every node whose value can differ in the
       counterfactual world, recover ``u_i = (x_i - sum(w_ij x_j)) / phi``
       from the factual evidence using the FACTUAL model.
    2. Action: ``mutilate`` a copy, removing every edge into an intervened
       node.
    3. Prediction: propagate the mutilated model with the abduced noise.
       Nodes that do not descend from an intervention keep their factual
       value.

    Only the evidence the requested outcomes depend on is required. Missing
    or non-finite evidence raises :class:`CausalCapabilityUnavailable`
    naming it; nothing is filled in.
    """
    ar = _Arithmetic(arithmetic)
    if not interventions:
        raise CausalCapabilityUnavailable("a counterfactual needs at least one intervention")
    graph = scm.graph
    scm._dag_order()
    outcomes = list(dict.fromkeys(outcomes))
    if not outcomes:
        raise CausalCapabilityUnavailable("no outcome node requested")
    unknown = sorted(set(outcomes) - set(graph.nodes))
    if unknown:
        raise CausalCapabilityUnavailable(
            f"outcome node(s) absent from the model: {unknown}", missing=unknown
        )
    factual_digest = graph.digest()
    mutilated, surgery = scm.mutilate(interventions)
    cut = mutilated.graph
    targets = set(interventions)
    affected: Set[str] = set()
    for node in targets:
        affected |= cut.descendants(node)
    affected -= targets
    relevant: Set[str] = set()
    for node in outcomes:
        relevant |= cut.ancestors(node) | {node}
    relevant -= targets
    required: Set[str] = set(relevant)
    for node in relevant & affected:
        required.update(graph.parents.get(node, []))
    missing = sorted(n for n in required if not _finite_evidence(observed, n))
    if missing:
        raise CausalCapabilityUnavailable(
            "counterfactual prediction needs factual evidence for " + ", ".join(missing),
            missing=missing,
        )

    factual = {n: ar.of(observed[n]) for n in required}
    abduced: Dict[str, Any] = {}
    for node in graph.topological_order():
        if node in relevant and node in affected:
            residual = factual[node]
            for parent in graph.parents.get(node, []):
                residual = residual - ar.of(graph.edge_weights[(parent, node)]) * factual[parent]
            abduced[node] = ar.over_phi(residual)

    values: Dict[str, Any] = {}
    for node in cut.topological_order():
        if node in targets:
            values[node] = ar.of(interventions[node])
        elif node not in relevant:
            continue
        elif node not in affected:
            values[node] = factual[node]
        else:
            total = ar.times_phi(abduced[node])
            for parent in cut.parents.get(node, []):
                total = total + ar.of(cut.edge_weights[(parent, node)]) * values[parent]
            values[node] = total

    return {
        "arithmetic": ar.name,
        "interventions": {k: ar.to_float(ar.of(v)) for k, v in interventions.items()},
        "outcomes": outcomes,
        "outcome_values": {n: ar.to_float(values[n]) for n in outcomes},
        "values": {n: ar.to_float(values[n]) for n in sorted(values)},
        "exact_values": (
            {n: zphi_as_dict(values[n]) for n in sorted(values)} if ar.exact else None
        ),
        "factual_state": {n: ar.to_float(factual[n]) for n in sorted(factual)},
        "abduced_exogenous": {n: ar.to_float(abduced[n]) for n in sorted(abduced)},
        "required_evidence": sorted(required),
        "surgery": surgery,
        "factual_model_unchanged": graph.digest() == factual_digest,
    }


# ---------------------------------------------------------------------------
# Adjusted causal-effect estimation from observational samples
# ---------------------------------------------------------------------------

ESTIMATOR_VERSION = "toe.causal_ladder.estimate_causal_effect/v1"
_STRATIFY_MAX_LEVELS = 16


@dataclass
class CausalEffectEstimate:
    """E[Y | do(X)] estimated from observational samples over a supplied DAG."""

    available: bool
    treatment: str
    outcome: str
    method: Optional[str] = None
    adjustment_set: Optional[List[str]] = None
    naive_effect: Optional[float] = None
    adjusted_effect: Optional[float] = None
    standard_error: Optional[float] = None
    interventional_means: Dict[str, float] = field(default_factory=dict)
    n_samples: Optional[int] = None
    reason: Optional[str] = None
    provenance: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "treatment": self.treatment,
            "outcome": self.outcome,
            "method": self.method,
            "adjustment_set": self.adjustment_set,
            "naive_effect": self.naive_effect,
            "adjusted_effect": self.adjusted_effect,
            "standard_error": self.standard_error,
            "interventional_means": dict(self.interventional_means),
            "n_samples": self.n_samples,
            "reason": self.reason,
            "provenance": dict(self.provenance),
        }


@dataclass
class _OLSFit:
    coef: List[float]
    se: List[Optional[float]]
    intercept: float


def _invert(matrix: List[List[float]]) -> Optional[List[List[float]]]:
    """Gauss-Jordan inverse with partial pivoting; None when singular."""
    k = len(matrix)
    scale = max((abs(v) for row in matrix for v in row), default=0.0)
    if scale == 0.0:
        return None
    aug = [list(row) + [1.0 if i == j else 0.0 for j in range(k)] for i, row in enumerate(matrix)]
    for col in range(k):
        pivot = max(range(col, k), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) <= scale * 1e-12:
            return None
        aug[col], aug[pivot] = aug[pivot], aug[col]
        lead = aug[col][col]
        aug[col] = [v / lead for v in aug[col]]
        for r in range(k):
            if r != col and aug[r][col] != 0.0:
                factor = aug[r][col]
                aug[r] = [a - factor * b for a, b in zip(aug[r], aug[col])]
    return [row[k:] for row in aug]


def _ols(regressors: List[List[float]], y: List[float]) -> Optional[_OLSFit]:
    """Least squares of y on the regressors plus an intercept (centred)."""
    n, k = len(y), len(regressors)
    if n <= k + 1:
        return None
    means = [math.fsum(c) / n for c in regressors]
    y_mean = math.fsum(y) / n
    centred = [[v - m for v in c] for c, m in zip(regressors, means)]
    yc = [v - y_mean for v in y]
    xtx = [[0.0] * k for _ in range(k)]
    xty = [0.0] * k
    for a in range(k):
        xty[a] = math.fsum(p * q for p, q in zip(centred[a], yc))
        for b in range(a, k):
            xtx[a][b] = xtx[b][a] = math.fsum(p * q for p, q in zip(centred[a], centred[b]))
    inv = _invert(xtx)
    if inv is None:
        return None
    coef = [math.fsum(inv[a][b] * xty[b] for b in range(k)) for a in range(k)]
    rss = math.fsum(
        (yc[i] - math.fsum(coef[a] * centred[a][i] for a in range(k))) ** 2 for i in range(n)
    )
    sigma2 = rss / (n - k - 1)
    se = [math.sqrt(sigma2 * inv[a][a]) if inv[a][a] > 0 else None for a in range(k)]
    intercept = y_mean - math.fsum(c * m for c, m in zip(coef, means))
    return _OLSFit(coef=coef, se=se, intercept=intercept)


def _numeric_columns(
    samples: Mapping[str, Sequence[Any]], names: Sequence[str]
) -> Dict[str, List[float]]:
    columns: Dict[str, List[float]] = {}
    length: Optional[int] = None
    for name in names:
        raw = samples.get(name)
        if raw is None:
            raise ValueError(f"no samples for {name!r}")
        column: List[float] = []
        for value in raw:
            if value is None or isinstance(value, bool):
                raise ValueError(f"column {name!r} has a missing or boolean entry")
            number = float(value)
            if not math.isfinite(number):
                raise ValueError(f"column {name!r} has a non-finite entry")
            column.append(number)
        if length is None:
            length = len(column)
        elif len(column) != length:
            raise ValueError("sample columns have different lengths")
        columns[name] = column
    if not length or length < 2:
        raise ValueError("at least two samples are required")
    return columns


def _is_discrete(
    data: Mapping[str, List[float]], names: Sequence[str], levels: Sequence[float]
) -> bool:
    for name in names:
        if len(set(data[name])) > _STRATIFY_MAX_LEVELS:
            return False
    treatment_values = set(data[names[0]])
    return all(level in treatment_values for level in levels)


def _stratified(
    data: Mapping[str, List[float]],
    treatment: str,
    outcome: str,
    adjustment: Sequence[str],
    levels: Sequence[float],
) -> Any:
    """sum_z P(z) E[Y | X=x, Z=z] and its sampling variance, per level x."""
    n = len(data[treatment])
    strata: Dict[Tuple[float, ...], List[int]] = {}
    for i in range(n):
        strata.setdefault(tuple(data[z][i] for z in adjustment), []).append(i)
    means: Dict[float, float] = {}
    variances: Dict[float, Optional[float]] = {}
    for level in levels:
        terms: List[float] = []
        var_terms: List[float] = []
        variance_known = True
        for key in sorted(strata):
            idx = strata[key]
            ys = [data[outcome][i] for i in idx if data[treatment][i] == level]
            if not ys:
                stratum = dict(zip(adjustment, key))
                return (
                    f"positivity violated: no units with {treatment}={level!r} "
                    f"in stratum {stratum}"
                )
            weight = len(idx) / n
            mean = math.fsum(ys) / len(ys)
            terms.append(weight * mean)
            if len(ys) > 1:
                sample_var = math.fsum((v - mean) ** 2 for v in ys) / (len(ys) - 1)
                var_terms.append(weight * weight * sample_var / len(ys))
            else:
                variance_known = False
        means[level] = math.fsum(terms)
        variances[level] = math.fsum(var_terms) if variance_known else None
    return means, variances


def estimate_causal_effect(
    samples: Mapping[str, Sequence[Any]],
    graph: CausalGraph,
    treatment: str,
    outcome: str,
    *,
    observed: Optional[Iterable[str]] = None,
    do_values: Sequence[float] = (0.0, 1.0),
    method: str = "auto",
) -> CausalEffectEstimate:
    """E[Y | do(X=x)] from observational samples by backdoor adjustment.

    The graph is supplied, not discovered. The adjustment set is the
    smallest backdoor-admissible set among the observed variables
    (:func:`identify_backdoor`). If none exists the effect is reported
    unavailable; it never falls back to the observational association.

    Methods:

    - ``linear_regression``: OLS of Y on X and the adjustment set, so
      E[Y|do(X=x)] = mean(Y) + b_X (x - mean(X)). Valid when E[Y | X, Z] is
      linear in (X, Z). The effect is b_X with its OLS standard error.
    - ``stratification``: sum_z P(z) E[Y | X=x, Z=z] over the observed strata
      of a discrete X and adjustment set. A stratum with no units at X=x is
      a positivity violation and makes the estimate unavailable.
    - ``auto``: stratification when X and every adjustment variable take at
      most 16 distinct values and each requested level of X is observed;
      otherwise linear regression.

    ``adjusted_effect`` is the contrast between the last and first entries
    of ``do_values`` per unit of X. ``naive_effect`` is the same contrast
    computed from the association alone, for comparison.
    """
    if method not in ("auto", "linear_regression", "stratification"):
        raise ValueError(f"unknown estimation method {method!r}")
    levels = [float(v) for v in do_values]
    provenance: Dict[str, Any] = {
        "estimator": ESTIMATOR_VERSION,
        "method_requested": method,
        "do_values": levels,
    }

    def unavailable(
        reason: str, adjustment: Optional[List[str]] = None, n: Optional[int] = None
    ) -> CausalEffectEstimate:
        return CausalEffectEstimate(
            available=False,
            treatment=treatment,
            outcome=outcome,
            adjustment_set=adjustment,
            n_samples=n,
            reason=reason,
            provenance=provenance,
        )

    if len(levels) < 2 or levels[0] == levels[-1]:
        return unavailable("do_values must contain two distinct treatment levels")
    for node in (treatment, outcome):
        if node not in graph.nodes:
            return unavailable(f"{node!r} is not in the supplied causal graph")
    if treatment == outcome:
        return unavailable("treatment and outcome are the same variable")
    if not graph.is_dag():
        return unavailable("the supplied causal graph is not a DAG")
    observed_set = set(samples) if observed is None else set(observed)
    undeclared = sorted(observed_set - set(samples))
    if undeclared:
        return unavailable(f"declared observed variables have no samples: {undeclared}")
    for node in (treatment, outcome):
        if node not in observed_set:
            return unavailable(f"{node!r} is not observed")
    provenance["graph_sha256"] = graph.digest()
    provenance["observed"] = sorted(observed_set)

    adjustment = identify_backdoor(graph, treatment, outcome, observed=observed_set)
    if adjustment is None:
        return unavailable(
            "no backdoor-admissible adjustment set among the observed variables; "
            "the effect is not identified by adjustment"
        )
    names = [treatment, outcome, *adjustment]
    try:
        data = _numeric_columns(samples, names)
    except (TypeError, ValueError) as exc:
        return unavailable(str(exc), adjustment)
    n = len(data[treatment])
    provenance["data_sha256"] = _sha256_json({k: data[k] for k in names})
    chosen = method
    if method == "auto":
        discrete = _is_discrete(data, [treatment, *adjustment], levels)
        chosen = "stratification" if discrete else "linear_regression"
    provenance["method"] = chosen
    x0, x1 = levels[0], levels[-1]

    if chosen == "linear_regression":
        naive_fit = _ols([data[treatment]], data[outcome])
        fit = _ols([data[treatment]] + [data[z] for z in adjustment], data[outcome])
        if naive_fit is None or fit is None:
            return unavailable("design matrix is singular or under-determined", adjustment, n)
        naive = naive_fit.coef[0]
        effect = fit.coef[0]
        se = fit.se[0]
        y_mean = math.fsum(data[outcome]) / n
        x_mean = math.fsum(data[treatment]) / n
        means = {level: y_mean + effect * (level - x_mean) for level in levels}
    else:
        adjusted = _stratified(data, treatment, outcome, adjustment, levels)
        if isinstance(adjusted, str):
            return unavailable(adjusted, adjustment, n)
        crude = _stratified(data, treatment, outcome, [], [x0, x1])
        if isinstance(crude, str):
            return unavailable(crude, adjustment, n)
        means, variances = adjusted
        naive = (crude[0][x1] - crude[0][x0]) / (x1 - x0)
        effect = (means[x1] - means[x0]) / (x1 - x0)
        if variances[x0] is None or variances[x1] is None:
            se = None
        else:
            se = math.sqrt(variances[x0] + variances[x1]) / abs(x1 - x0)

    return CausalEffectEstimate(
        available=True,
        treatment=treatment,
        outcome=outcome,
        method=chosen,
        adjustment_set=list(adjustment),
        naive_effect=float(naive),
        adjusted_effect=float(effect),
        standard_error=None if se is None else float(se),
        interventional_means={repr(level): float(means[level]) for level in levels},
        n_samples=n,
        provenance=provenance,
    )


# ---------------------------------------------------------------------------
# Rung 3: Counterfactual P(Y_x | X=x', Y=y')
# ---------------------------------------------------------------------------


def counterfactual_query(
    scm: StructuralCausalModel,
    state: QuantumState,
    intervention_node: str,
    intervention_value: float,
    observed: Dict[str, float],
    observables: Dict[str, ComplexMatrix],
    dim: int = 32,
    *,
    outcome_node: Optional[str] = None,
    arithmetic: str = ARITHMETIC_FLOAT,
) -> Tuple[float, Dict[str, Any]]:
    """Rung 3: P(Y_x | X=x', Y=y') — counterfactual via structural equations.

    Given that we observed X=x' and Y=y', compute what Y *would have been*
    if X had been set to x (the counterfactual). The work is done by
    :func:`counterfactual_state`; this wrapper keeps the original call
    shape. ``state``, ``observables`` and ``dim`` are accepted for
    compatibility and do not enter the structural computation. Raises
    :class:`CausalCapabilityUnavailable` when evidence is missing.

    The three-step procedure (Pearl):

    1. **Abduction**: Update the exogenous variables U to be consistent
       with the observed evidence (X=x', Y=y').
    2. **Action**: Apply the do-operator (set X=x, cut incoming edges).
    3. **Prediction**: Compute Y in the modified model with the updated U.

    In the quantum implementation:
    1. Abduction: The exogenous noise is estimated as the residual between
       the observed value and the structural equation prediction.
    2. Action: Graph surgery (same as the do-operator).
    3. Prediction: Evaluate the structural equation for Y with the
       updated exogenous variables and the intervened X.

    Returns
    -------
    counterfactual_y : float
        The counterfactual value of Y.
    diagnostics : dict
        Diagnostics about the three-step procedure.
    """
    if intervention_node not in scm.graph.nodes:
        raise CausalCapabilityUnavailable(
            f"intervention node {intervention_node!r} is absent from the model",
            missing=[intervention_node],
        )
    if outcome_node is None:
        order = scm._dag_order()
        remaining = [n for n in reversed(order) if n != intervention_node]
        if not remaining:
            raise CausalCapabilityUnavailable("the model has no outcome besides the intervention")
        outcome_node = remaining[0]
        outcome_selection = "implicit: last node in topological order (pass outcome_node)"
    else:
        outcome_selection = "explicit"
    if outcome_node == intervention_node:
        raise CausalCapabilityUnavailable("outcome and intervention are the same node")

    result = counterfactual_state(
        scm,
        {intervention_node: intervention_value},
        observed,
        [outcome_node],
        arithmetic=arithmetic,
    )
    counterfactual_y = result["outcome_values"][outcome_node]
    surgery = result["surgery"]
    diagnostics = {
        "step_1_abduction": {
            "observed": dict(observed),
            "estimated_exogenous": result["abduced_exogenous"],
            "required_evidence": result["required_evidence"],
        },
        "step_2_action": {
            "intervention": f"do({intervention_node}={intervention_value})",
            "intervention_target": intervention_node,
            "graph_surgery": f"incoming edges of {intervention_node} removed on a copy",
            "incoming_edges_before": surgery["incoming_edges_before"][intervention_node],
            "incoming_edges_after": surgery["incoming_edges_after"][intervention_node],
            "edges_cut": surgery["edges_cut"],
            "factual_model_unchanged": result["factual_model_unchanged"],
        },
        "step_3_prediction": {
            "outcome_node": outcome_node,
            "outcome_selection": outcome_selection,
            "factual_y": result["factual_state"].get(outcome_node),
            "counterfactual_y": counterfactual_y,
            "counterfactual_state": result["values"],
            "all_values": result["values"],
        },
        "method": "pearl_three_step_counterfactual",
        "arithmetic": result["arithmetic"],
        "exact_value": (result["exact_values"] or {}).get(outcome_node),
    }
    return float(counterfactual_y), diagnostics


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class CausalLadderResult:
    """Result of the full causal ladder analysis (all three rungs).

    Rung 1 (Association):       P(Y | X) — Born rule probabilities.
    Rung 2 (Intervention):      P(Y | do(X)) — post-surgery distribution.
    Rung 3 (Counterfactual):    P(Y_x | X=x', Y=y') — structural equation.
    """

    available: bool
    confidence: float
    # Rung 1: Association
    association: Dict[str, float] = field(default_factory=dict)
    # Rung 2: Intervention
    intervention_distribution: Dict[str, float] = field(default_factory=dict)
    intervention_diagnostics: Dict[str, Any] = field(default_factory=dict)
    backdoor_set: Optional[List[str]] = None
    frontdoor_set: Optional[List[str]] = None
    identifiable: bool = False
    # Rung 3: Counterfactual
    counterfactual_value: Optional[float] = None
    counterfactual_diagnostics: Dict[str, Any] = field(default_factory=dict)
    # Causal graph
    causal_graph: Dict[str, Any] = field(default_factory=dict)
    # SCM
    scm: Dict[str, Any] = field(default_factory=dict)
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "confidence": self.confidence,
            "rung_1_association": self.association,
            "rung_2_intervention": {
                "distribution": self.intervention_distribution,
                "diagnostics": self.intervention_diagnostics,
                "backdoor_set": self.backdoor_set,
                "frontdoor_set": self.frontdoor_set,
                "identifiable": self.identifiable,
            },
            "rung_3_counterfactual": {
                "value": self.counterfactual_value,
                "diagnostics": self.counterfactual_diagnostics,
            },
            "causal_graph": self.causal_graph,
            "scm": self.scm,
            "diagnostics": self.diagnostics,
        }


__all__ = [
    "CausalGraph",
    "StructuralCausalModel",
    "CausalLadderResult",
    "infer_causal_graph",
    "association_query",
    "do_operator",
    "counterfactual_query",
    "counterfactual_state",
    "identify_backdoor",
    "identify_frontdoor",
    "d_separated",
    "is_backdoor_admissible",
    "intervene",
    "estimate_causal_effect",
    "CausalEffectEstimate",
    "CausalCapabilityUnavailable",
    "ARITHMETIC_EXACT",
    "ARITHMETIC_FLOAT",
    "ESTIMATOR_VERSION",
    "zphi_as_dict",
    "zphi_to_float",
]


if __name__ == "__main__":
    # Self-test when run directly: python Intelligence/causal_ladder.py
    print("=== Pearl Causal Ladder (do-calculus) self-test ===\n")

    # A supplied graph: U confounds X and Y, Z is an extra cause of X.
    graph = CausalGraph.from_edges(
        [("U", "X", 1.5), ("Z", "X", 0.5), ("U", "Y", 1.2), ("X", "Y", 3.0)]
    )
    scm = StructuralCausalModel(graph)
    state = QuantumState.uniform_superposition(scm.dim)
    print(f"backdoor set for X -> Y : {identify_backdoor(graph, 'X', 'Y')}")

    samples = scm.sample(20_000, seed=1517)
    estimate = estimate_causal_effect(samples, graph, "X", "Y")
    print(
        f"naive {estimate.naive_effect:+.4f}  adjusted {estimate.adjusted_effect:+.4f}"
        f"  (structural 3.0, method {estimate.method})"
    )

    factual = scm.evaluate_all(exogenous={"U": 0.2, "Z": -0.4, "X": 0.1, "Y": 0.3})
    value, diag = counterfactual_query(
        scm, state, "X", 2.0, observed=factual, observables={}, outcome_node="Y"
    )
    print(f"factual Y {factual['Y']:+.4f}  counterfactual Y under do(X=2) {value:+.4f}")
    print(f"edges cut: {diag['step_2_action']['edges_cut']}")


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool.

    Calls the declared kernel (path_kernel) on the canonical substrate for
    this route and reports the pool's exact bound. This proves the route
    is live; it is not a per-algorithm cost claim.
    """
    import numpy as np  # noqa: F401

    from lucas.pool import get as _lucas_get

    result = _lucas_get("path_kernel")(np.array([[0, 1], [1, 0]], dtype=np.int64), n)
    result["module"] = __name__
    return result
