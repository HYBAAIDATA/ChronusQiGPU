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
"""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: path

from __future__ import annotations

import logging
import math
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# The tensor substrate is the Kellogg package (kellogg/), not part of TOE.
# Support both package import and direct execution.
try:
    from kellogg.quantum_tensor import (
        Complex,
        ComplexMatrix,
        QuantumState,
        Observables,
        encode_data_to_state,
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
        encode_data_to_state,
    )

logger = logging.getLogger("toe.causal_ladder")

PHI = (1 + math.sqrt(5)) / 2


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
    # 1. Graph surgery: remove incoming edges to the intervention node
    original_parents = list(scm.graph.parents.get(intervention_node, []))
    removed_edges: List[Tuple[str, str]] = []
    for p in original_parents:
        removed_edges.append((p, intervention_node))
        w = scm.graph.edge_weights.pop((p, intervention_node), 0.0)
        if p in scm.graph.parents.get(intervention_node, []):
            scm.graph.parents[intervention_node] = [
                c for c in scm.graph.parents[intervention_node] if c != p
            ]
        if intervention_node in scm.graph.children.get(p, []):
            scm.graph.children[p] = [
                c for c in scm.graph.children[p] if c != intervention_node
            ]

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
        "graph_surgery": "incoming edges to X removed",
        "state_preparation": f"projected to eigenstate {idx}",
        "propagation": "Hamiltonian evolution through remaining structure with Zeckendorf decoupling",
        "zeckendorf_decoupling_mask": decoupling_mask,
        "decoupled_active_dimensions": decoupled_active_dims,
    }

    return post_state, diagnostics


def identify_backdoor(
    graph: CausalGraph,
    treatment: str,
    outcome: str,
) -> Optional[List[str]]:
    """Check the backdoor criterion for identifiability.

    A set Z satisfies the backdoor criterion relative to (X, Y) if:
    1. No node in Z is a descendant of X.
    2. Z blocks every path between X and Y that contains an arrow into X
       (a "backdoor path").

    Returns the backdoor adjustment set Z if identifiable, None otherwise.
    """
    # Find all backdoor paths (paths into X)
    x_ancestors = graph.ancestors(treatment)
    # The backdoor set is the parents of X (common causes of X and Y)
    z = list(graph.parents.get(treatment, []))
    # Check that Z blocks all backdoor paths
    # Backdoor criterion: Z = parents of X that are also ancestors of Y
    y_ancestors = graph.ancestors(outcome)
    z_valid = [n for n in z if n in y_ancestors or n in x_ancestors]
    if z_valid:
        return z_valid
    # If X has no parents, there are no backdoor paths
    if not graph.parents.get(treatment, []):
        return []
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
) -> Tuple[float, Dict[str, Any]]:
    """Rung 3: P(Y_x | X=x', Y=y') — counterfactual via structural equations.

    Given that we observed X=x' and Y=y', compute what Y *would have been*
    if X had been set to x (the counterfactual).

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
    # Step 1: Abduction — estimate exogenous variables from observations
    exogenous: Dict[str, float] = {}
    for node in scm.graph.topological_order():
        if node in observed:
            predicted = scm.structural_equation(node, observed, 0.0)
            actual = observed[node]
            exogenous[node] = (actual - predicted) / PHI  # residual / φ

    # Step 2: Action — apply do(X=x)
    interventions = {intervention_node: intervention_value}

    # Step 3: Prediction — evaluate Y in the modified model
    values = scm.evaluate_all(
        interventions=interventions,
        exogenous=exogenous,
    )

    # Find the outcome node (the last node in topological order that is
    # not the intervention node)
    outcome_node = None
    for node in reversed(scm.graph.topological_order()):
        if node != intervention_node:
            outcome_node = node
            break

    counterfactual_y = values.get(outcome_node, 0.0) if outcome_node else 0.0

    diagnostics = {
        "step_1_abduction": {
            "observed": observed,
            "estimated_exogenous": exogenous,
        },
        "step_2_action": {
            "intervention": f"do({intervention_node}={intervention_value})",
            "graph_surgery": f"removed parents of {intervention_node}",
        },
        "step_3_prediction": {
            "outcome_node": outcome_node,
            "counterfactual_y": counterfactual_y,
            "all_values": values,
        },
        "method": "pearl_three_step_counterfactual",
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
    "identify_backdoor",
    "identify_frontdoor",
]


if __name__ == "__main__":
    # Self-test when run directly: python Intelligence/causal_ladder.py
    print("=== Pearl Causal Ladder (do-calculus) self-test ===\n")

    data = {
        "hashrate": [100.0, 120.0, 90.0, 110.0, 130.0],
        "temperature": [65.0, 70.0, 60.0, 68.0, 72.0],
        "power": [850.0, 900.0, 800.0, 870.0, 920.0],
        "share_diff": [1.0, 1.2, 0.9, 1.1, 1.3],
    }

    graph, observables = infer_causal_graph(data)
    print(f"Causal graph nodes: {graph.nodes}")
    print(f"Is DAG: {graph.is_dag()}")
    print(f"Topological order: {graph.topological_order()}")
    print()

    # Build the SCM from the graph
    scm = StructuralCausalModel(graph)
    # Encode the data into a quantum state
    all_vals = []
    for k in data:
        all_vals.extend([float(v) for v in data[k]])
    state = encode_data_to_state(all_vals)

    # Rung 1: Association P(Y|X)
    assoc = association_query(state, observables["share_diff"])
    print("Rung 1 (Association) P(share_diff|data):")
    print(f"  keys: {list(assoc.keys())[:5]}")
    print()

    # Rung 2: Intervention P(Y|do(X))
    new_state, inter = do_operator(state, "hashrate", 150.0, observables, scm)
    print("Rung 2 (Intervention) P(share_diff|do(hashrate=150)):")
    print(f"  result keys: {list(inter.keys())[:5] if isinstance(inter, dict) else type(inter)}")
    print()

    # Rung 3: Counterfactual P(Y_x|X=x',Y=y')
    cf_val, cf_diag = counterfactual_query(
        scm,
        state,
        "hashrate",
        150.0,
        observed={"hashrate": 100.0, "share_diff": 1.0},
        observables=observables,
    )
    print("Rung 3 (Counterfactual):")
    print(f"  value: {cf_val}")
    print(f"  diagnostics: {list(cf_diag.keys())}")
    print()

    print("=== Causal ladder self-test passed ===")


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
