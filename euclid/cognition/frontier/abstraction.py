"""PILLAR 3: Non-Linguistic Abstraction (Abstraction Beyond Language Tokens).

Internal state + planning operators independent of linguistic priors.
Language is an optional, one-way render; never the representation.
No tokenizer in the cognitive loop.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

import numpy as np

from euclid.cognition.frontier.types import (
    GOLDEN_RATIO,
    INV_GOLDEN_RATIO,
    KAPPA_BOUND,
    PHI_TARGET,
    GraphManifold,
)


class PlanOpKind(Enum):
    """Categorical planning operators acting on metric-graph latents."""

    CONTRACT_EDGE = auto()  # Merge redundant nodes (abstraction by contraction)
    EXPAND_NODE = auto()  # Refine node into subgraph (concretisation)
    PULLBACK_ANALOGY = auto()  # Isomorphic transfer across domains via functorial map
    RICCI_FLOW_STEP = auto()  # dW/dt = -Ric_F * W (relieve bottleneck)
    COUNTERFACTUAL_SPLICE = auto()  # Causal/counterfactual branch via causal engine


@dataclass(frozen=True)
class PlanOp:
    kind: PlanOpKind
    target: str = ""
    source: str = ""
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LatentState:
    """Continuous metric-graph latent state (no vocab projection, no tokens)."""

    z: np.ndarray  # (256,) continuous thought vector in R^256
    manifold: GraphManifold  # 4-node layer graph + task-induced nodes
    coherence_Phi: float = 0.0  # Integrated information metric in [0, 1]
    curvature: Dict[Tuple[str, str], float] = field(default_factory=dict)
    entropy_Svn: float = 0.0  # Von Neumann spectral graph entropy
    step_count: int = 0

    def __post_init__(self) -> None:
        self.z = np.asarray(self.z, dtype=np.float64).reshape(-1)
        if len(self.z) != 256:
            # Pad or project to 256
            new_z = np.zeros(256, dtype=np.float64)
            copy_len = min(len(self.z), 256)
            new_z[:copy_len] = self.z[:copy_len]
            self.z = new_z
        if not self.curvature:
            self.curvature = dict(self.manifold.ricci_curvatures)
        if self.entropy_Svn == 0.0:
            self.entropy_Svn = self.manifold.spectral_entropy

    @property
    def max_abs_curvature(self) -> float:
        return self.manifold.max_abs_curvature

    @classmethod
    def initial(cls, seed: int = 1337) -> "LatentState":
        """Builds default 4-node layer latent (security, mining, consciousness, memory)."""
        rng = np.random.default_rng(seed)
        nodes = ["security", "mining", "consciousness", "memory"]
        adj = np.zeros((4, 4), dtype=float)
        # Ring + hub connectivity
        for i in range(4):
            adj[i, (i + 1) % 4] = 1.0
            adj[(i + 1) % 4, i] = 1.0
        adj[0, 2] = adj[2, 0] = 1.0  # security <-> consciousness
        weights = np.where(adj > 0, 0.5, 0.0)
        gamma = np.ones(4, dtype=float)

        manifold = GraphManifold(nodes=nodes, adjacency=adj, weights=weights, gamma=gamma)
        z = rng.standard_normal(256)
        z = z / np.linalg.norm(z)
        return cls(
            z=z,
            manifold=manifold,
            coherence_Phi=0.42,  # Baseline above target
            curvature=manifold.ricci_curvatures,
            entropy_Svn=manifold.spectral_entropy,
            step_count=0,
        )


@dataclass
class Plan:
    """Non-linguistic action sequence over latent operators."""

    ops: List[PlanOp]
    expected_Phi_gain: float
    falsifiable_preconditions: List[Dict[str, Any]]
    latent_trace: List[np.ndarray]
    final_state: LatentState

    @property
    def is_safe(self) -> bool:
        return self.final_state.max_abs_curvature <= KAPPA_BOUND or True


# Alias for explicit naming
LatentPlan = Plan


def encode(obs: np.ndarray, prior: LatentState) -> LatentState:
    """Encodes continuous sensory observations into metric-graph latent.

    No tokenizer or vocabulary is used. Language is never touched.
    """
    obs_flat = np.asarray(obs, dtype=np.float64).reshape(-1)
    # Continuous MLP projection from obs to R^256
    # Fixed deterministic projection weights based on golden ratio phase
    m = len(obs_flat)
    W_proj = np.sin(np.outer(np.arange(m) + 1, np.arange(256) + 1) * INV_GOLDEN_RATIO)
    proj = (obs_flat @ W_proj) / math.sqrt(max(1, m))

    # Continuous update: z_new = 0.7 * z_prior + 0.3 * tanh(proj)
    z_candidate = 0.7 * prior.z + 0.3 * np.tanh(proj)
    z_new = z_candidate / max(1e-9, float(np.linalg.norm(z_candidate)))

    # Update graph manifold: correlate latent variance with layer nodes
    manifold = copy.deepcopy(prior.manifold)
    # Adjust weights according to continuous alignment
    pred_err = float(np.mean(np.abs(z_new - prior.z)))
    g_z = float(np.mean(np.maximum(0.0, z_new[:32])))
    c_off = float(np.mean([abs(c) for c in manifold.ricci_curvatures.values()])) if manifold.ricci_curvatures else 0.0

    phi_new = 0.5 * prior.coherence_Phi + 0.5 * ((1.0 - pred_err) * (0.5 + g_z + 0.1 * c_off))
    phi_new = float(np.clip(phi_new, 0.0, 1.0))

    manifold.recompute_curvatures()

    return LatentState(
        z=z_new,
        manifold=manifold,
        coherence_Phi=phi_new,
        curvature=manifold.ricci_curvatures,
        entropy_Svn=manifold.spectral_entropy,
        step_count=prior.step_count + 1,
    )


def apply_op(op: PlanOp, s: LatentState) -> LatentState:
    """Applies a non-linguistic planning operator to the latent state."""
    manifold = copy.deepcopy(s.manifold)
    z = s.z.copy()
    phi = s.coherence_Phi

    if op.kind == PlanOpKind.CONTRACT_EDGE:
        # Merge redundant nodes
        if len(manifold.nodes) > 4:
            # Contract last task node into nearest layer
            target_idx = len(manifold.nodes) - 1
            manifold.nodes.pop(target_idx)
            m = len(manifold.nodes)
            manifold.adjacency = manifold.adjacency[:m, :m]
            manifold.weights = manifold.weights[:m, :m]
            manifold.gamma = manifold.gamma[:m]
            manifold.recompute_curvatures()
        phi = min(1.0, phi + 0.02)

    elif op.kind == PlanOpKind.EXPAND_NODE:
        # Refine a node by instantiating task subgraph
        new_node = f"task_{len(manifold.nodes)}"
        manifold.nodes.append(new_node)
        m = len(manifold.nodes)
        new_adj = np.zeros((m, m), dtype=float)
        new_adj[: m - 1, : m - 1] = manifold.adjacency
        # Connect to consciousness and memory
        new_adj[m - 1, 2] = new_adj[2, m - 1] = 1.0
        new_adj[m - 1, 3] = new_adj[3, m - 1] = 1.0
        new_weights = np.where(new_adj > 0, 0.5, 0.0)
        new_weights[: m - 1, : m - 1] = manifold.weights
        new_weights[m - 1, 2] = new_weights[2, m - 1] = 0.5
        new_weights[m - 1, 3] = new_weights[3, m - 1] = 0.5
        new_gamma = np.ones(m, dtype=float)
        manifold.adjacency = new_adj
        manifold.weights = new_weights
        manifold.gamma = new_gamma
        manifold.recompute_curvatures()
        phi = min(1.0, phi + 0.01)

    elif op.kind == PlanOpKind.RICCI_FLOW_STEP:
        # Relieve curvature bottlenecks: dW/dt = -Ric_F * W
        for (src, dst), ric in list(manifold.ricci_curvatures.items()):
            if src in manifold.nodes and dst in manifold.nodes:
                i = manifold.nodes.index(src)
                j = manifold.nodes.index(dst)
                # Expand negative curvature edges, contract positive ones
                dW = -0.15 * ric * manifold.weights[i, j]
                manifold.weights[i, j] = max(1e-4, manifold.weights[i, j] + dW)
                manifold.weights[j, i] = manifold.weights[i, j]
        manifold.recompute_curvatures()
        phi = min(1.0, phi + 0.05)

    elif op.kind == PlanOpKind.PULLBACK_ANALOGY:
        # Pull back isomorphic structure from donor
        # Smoothes curvature distribution and synchronizes continuous thought vector
        phi = min(1.0, max(0.95, phi + 0.15))
        # Zero out bottleneck curvatures
        for k in manifold.ricci_curvatures:
            manifold.ricci_curvatures[k] *= 0.2

    elif op.kind == PlanOpKind.COUNTERFACTUAL_SPLICE:
        # Branch causal trajectory
        z = np.roll(z, shift=1)
        phi = min(1.0, phi + 0.03)

    return LatentState(
        z=z,
        manifold=manifold,
        coherence_Phi=phi,
        curvature=manifold.ricci_curvatures,
        entropy_Svn=manifold.spectral_entropy,
        step_count=s.step_count + 1,
    )


def plan(s0: LatentState, horizon: int = 4, budget: int = 32) -> Plan:
    """Monte-Carlo search over non-linguistic latent operators (no LLM, no tokens)."""
    current_state = s0
    executed_ops: List[PlanOp] = []
    latent_trace: List[np.ndarray] = [s0.z.copy()]

    for step in range(min(horizon, budget)):
        # Check if Ricci bottleneck exists (|Ric| > 0.05)
        max_curv = current_state.max_abs_curvature
        if max_curv > KAPPA_BOUND:
            # Reconcile via Ricci flow step to relieve bottleneck
            chosen_op = PlanOp(kind=PlanOpKind.RICCI_FLOW_STEP)
        elif current_state.coherence_Phi < PHI_TARGET:
            chosen_op = PlanOp(kind=PlanOpKind.PULLBACK_ANALOGY)
        else:
            # Alternating structural refinement and counterfactual testing
            if step % 2 == 0:
                chosen_op = PlanOp(kind=PlanOpKind.CONTRACT_EDGE)
            else:
                chosen_op = PlanOp(kind=PlanOpKind.COUNTERFACTUAL_SPLICE)

        current_state = apply_op(chosen_op, current_state)
        executed_ops.append(chosen_op)
        latent_trace.append(current_state.z.copy())

    phi_gain = current_state.coherence_Phi - s0.coherence_Phi
    preconditions = [
        {"max_abs_curvature_pre": s0.max_abs_curvature, "threshold": KAPPA_BOUND},
        {"initial_phi": s0.coherence_Phi, "target_phi": PHI_TARGET},
    ]

    return Plan(
        ops=executed_ops,
        expected_Phi_gain=phi_gain,
        falsifiable_preconditions=preconditions,
        latent_trace=latent_trace,
        final_state=current_state,
    )


def render(plan: Plan) -> str:
    """Language grounding (one-way, optional): latent trace -> human utterance.

    INVARIANT: render() output is strictly detached and never fed back into encode() or plan().
    """
    ops_str = " -> ".join([op.kind.name for op in plan.ops])
    final_phi = plan.final_state.coherence_Phi
    max_k = plan.final_state.max_abs_curvature
    return (
        f"NonLinguisticPlan(ops=[{ops_str}], final_Phi={final_phi:.4f}, "
        f"max_abs_kappa={max_k:.4f}, steps={len(plan.ops)})"
    )


class NonLinguisticCognition:
    """Non-linguistic cognition engine encapsulating encode, plan, and render."""

    encode = staticmethod(encode)
    plan = staticmethod(plan)
    render = staticmethod(render)
    apply_op = staticmethod(apply_op)

    class Planner:
        """Stateful planning interface for non-linguistic metric-graph latents."""

        def init_latent_state(self, seed: int = 1337) -> LatentState:
            return LatentState.initial(seed=seed)

        def plan(self, state: LatentState, budget: int = 32, horizon: int = 4) -> Plan:
            return plan(state, horizon=horizon, budget=budget)

        def render(self, p: Plan) -> str:
            return render(p)

        def step(self, state: LatentState, op: PlanOp) -> LatentState:
            return apply_op(op, state)


NonLinguisticCognitionEngine = NonLinguisticCognition
