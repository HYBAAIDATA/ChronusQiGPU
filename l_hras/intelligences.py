"""The six intelligences — Part VIII.

Predictive, Causal, Counterfactual, Topological, Geometric, Quantum —
entangled in F4. Each is a computable operator with declared inputs,
outputs, invariants and tests.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

import numpy as np

from . import substrates
from .result import (
    CAUSAL_ASSOCIATION_FAILED,
    CAUSAL_COUNTERFACTUAL_FAILED,
    CAUSAL_INTERVENTION_FAILED,
    GEOMETRIC_ANALYSIS_FAILED,
    PREDICTION_FAILED,
    QUANTUM_FOLD_FAILED,
    TOPOLOGICAL_ANALYSIS_FAILED,
    Ok,
    Result,
    error,
)
from .types import (
    CounterfactualPath,
    CurvatureReport,
    Distribution,
    JointState,
    Prediction,
    TopologicalSignature,
)

INTELLIGENCES = (
    "predictive",
    "causal",
    "counterfactual",
    "topological",
    "geometric",
    "quantum",
)


# ---------------------------------------------------------------------------
# Entanglement of all six in F4 (EI1–EI5)
# ---------------------------------------------------------------------------


def init_intelligence_subspace(name: str, cfg: Any) -> Any:
    """Each intelligence owns one exact basis projection of the joint."""
    index = INTELLIGENCES.index(name)
    return substrates.exact_basis(cfg.state_dim, index % (1 << cfg.state_dim))


def build_full_entanglement_graph(projections: dict[str, Any]) -> dict[tuple[str, str], bool]:
    """Complete graph K6 over the intelligence projections."""
    names = list(projections.keys())
    return {(a, b): True for i, a in enumerate(names) for b in names[i + 1 :]}


def entangle_all_six_in_f4(cfg: Any, attester: Any = None) -> Result[JointState]:
    projections = {name: init_intelligence_subspace(name, cfg) for name in INTELLIGENCES}
    graph = build_full_entanglement_graph(projections)
    correlations = substrates.f4_correlations(graph, projections, list(projections))
    predictor = Predictor()
    causal_graph = load_causal_graph()
    return Ok(
        JointState(
            projection=projections,
            entanglement=graph,
            correlations=correlations,
            predictor=predictor,
            causal_graph=causal_graph,
        )
    )


# ---------------------------------------------------------------------------
# Predictive (PRED1–4)
# ---------------------------------------------------------------------------


class Predictor:
    """Deterministic feature→threat-level predictor.

    ``warm`` fits the predictor's window statistics once at standing;
    ``infer`` returns a measured :class:`Distribution`, always validated
    by ``is_valid_distribution`` before it reaches a verdict.
    """

    def __init__(self) -> None:
        self.warmed = False
        self._baseline_mean = 0.0
        self._baseline_std = 0.0

    def warm(self, windows: Sequence[float] | None = None) -> "Predictor":
        samples = [float(v) for v in (windows or [0.5, 0.5, 0.5])]
        self._baseline_mean = sum(samples) / len(samples)
        var = sum((v - self._baseline_mean) ** 2 for v in samples) / len(samples)
        self._baseline_std = math.sqrt(var)
        self.warmed = True
        return self

    def infer(self, features: dict[str, float]) -> Result[Distribution]:
        if not self.warmed:
            return error(PREDICTION_FAILED, reason="predictor_not_warmed")
        values = [float(v) for _, v in sorted(features.items())] or [0.0]
        n = len(values)
        mean = sum(values) / n
        var = sum((v - mean) ** 2 for v in values) / n
        ordered = sorted(values)

        def _pct(p: float) -> float:
            idx = min(n - 1, max(0, int(round(p * (n - 1)))))
            return ordered[idx]

        return Ok(
            Distribution(
                mean=mean,
                stddev=math.sqrt(var),
                samples=n,
                p50=_pct(0.50),
                p95=_pct(0.95),
                p99=_pct(0.99),
            )
        )


def extract_features(telemetry: Sequence[float] | dict[str, Any]) -> dict[str, float]:
    if isinstance(telemetry, dict):
        return {str(k): float(v) for k, v in telemetry.items() if isinstance(v, (int, float))}
    return {f"t{i}": float(v) for i, v in enumerate(telemetry)}


def is_valid_distribution(d: Distribution) -> bool:
    return (
        math.isfinite(d.mean)
        and d.stddev >= 0
        and d.samples > 0
        and d.p50 <= d.p95
        and d.p95 <= d.p99
    )


def predict(model: Predictor, telemetry: Sequence[float] | dict[str, Any]) -> Result[Prediction]:
    features = extract_features(telemetry)
    dist = model.infer(features)
    if dist.is_err:
        return dist
    if not is_valid_distribution(dist.value):
        return error(PREDICTION_FAILED, reason="invalid_distribution")
    return Ok(
        Prediction(
            distribution=dist.value,
            threat_level=min(1.0, max(0.0, dist.value.mean)),
            features=features,
        )
    )


def warm_predictor(model: Predictor) -> Result[Predictor]:
    return Ok(model.warm())


# ---------------------------------------------------------------------------
# Causal — Pearl L1/L2/L3 (CAUS1–3)
# ---------------------------------------------------------------------------


def load_causal_graph() -> Any:
    """The Guardian's declared causal skeleton over the intelligence
    factors — edges are the blueprint's data flow."""
    edges = [
        ("predictive", "causal", 0.8),
        ("causal", "counterfactual", 0.7),
        ("topological", "causal", 0.6),
        ("geometric", "topological", 0.5),
        ("quantum", "geometric", 0.6),
        ("counterfactual", "quantum", 0.4),
    ]
    return substrates.build_causal_scm(INTELLIGENCES, edges)


def causal_association(graph: Any, obs: dict[str, float]) -> Result[dict]:
    try:
        state = substrates.quantum_state_from_observation(obs, graph.dim)
        observables = substrates.default_observables(graph.graph.nodes, graph.dim)
        outcome = observables[graph.graph.nodes[-1]] if graph.graph.nodes else None
        if outcome is None:
            return error(CAUSAL_ASSOCIATION_FAILED, reason="empty graph")
        return Ok(substrates.causal_association(state, outcome))
    except Exception as exc:
        return error(CAUSAL_ASSOCIATION_FAILED, reason=str(exc))


def causal_intervention(graph: Any, do_var: tuple[str, float]) -> Result[Any]:
    try:
        node, value = do_var
        state = substrates.quantum_state_from_observation({}, graph.dim)
        observables = substrates.default_observables(graph.graph.nodes, graph.dim)
        post, diagnostics = substrates.causal_intervention(state, node, value, observables, graph)
        return Ok({"post_state": post, "diagnostics": diagnostics})
    except Exception as exc:
        return error(CAUSAL_INTERVENTION_FAILED, reason=str(exc))


def causal_counterfactual(
    graph: Any, obs: dict[str, float], intervention: tuple[str, float]
) -> Result[Any]:
    try:
        node, value = intervention
        state = substrates.quantum_state_from_observation(obs, graph.dim)
        observables = substrates.default_observables(graph.graph.nodes, graph.dim)
        y, diagnostics = substrates.causal_counterfactual(
            graph, state, node, value, obs, observables
        )
        return Ok({"counterfactual": y, "diagnostics": diagnostics})
    except Exception as exc:
        return error(CAUSAL_COUNTERFACTUAL_FAILED, reason=str(exc))


# ---------------------------------------------------------------------------
# Counterfactual — 10,000 paths (CF1–6)
# ---------------------------------------------------------------------------

_ACTIONS = ("block", "redirect", "entangle", "monitor")


def _initial_path(obs: dict[str, float]) -> CounterfactualPath:
    return CounterfactualPath(
        steps=[],
        likelihood=1.0,
        adversary=obs.get("adversary_id"),
        expected_target=str(obs.get("expected_target", "generic")),
        next_action_distribution={a: 0.25 for a in _ACTIONS},
    )


def _branching_actions(path: CounterfactualPath) -> list[str]:
    return list(_ACTIONS)


def _extend(path: CounterfactualPath, step: str) -> CounterfactualPath:
    return CounterfactualPath(
        steps=path.steps + [step],
        likelihood=path.likelihood,
        adversary=path.adversary,
        expected_target=path.expected_target,
        next_action_distribution=dict(path.next_action_distribution),
    )


def _score(path: CounterfactualPath, obs: dict[str, float]) -> float:
    """Measured likelihood: observation energy times a gentle depth decay."""
    energy = (
        sum(
            abs(float(v))
            for k, v in obs.items()
            if isinstance(v, (int, float)) and k not in ("adversary_id",)
        )
        or 0.5
    )
    decay = 0.85 ** len(path.steps)
    base = min(1.0, energy) * decay
    bias = {"block": 1.0, "redirect": 0.9, "entangle": 0.8, "monitor": 0.7}
    action = path.steps[-1] if path.steps else "monitor"
    return base * bias.get(action, 0.5)


def counterfactual_paths(
    graph: Any,
    obs: dict[str, float],
    max_paths: int,
    threshold: float,
) -> Result[list[CounterfactualPath]]:
    """BFS over the decision tree; paths scoring above the declared
    threshold are retained and re-expanded, ranked by likelihood."""
    paths: list[CounterfactualPath] = []
    queue: list[CounterfactualPath] = [_initial_path(obs)]
    iterations = 0
    max_iter = max_paths * 10
    while len(paths) < max_paths and queue:
        iterations += 1
        if iterations > max_iter:
            break
        path = queue.pop()
        next_steps = _branching_actions(path)
        if not next_steps:
            continue
        for step in next_steps:
            new_path = _extend(path, step)
            new_path.likelihood = _score(new_path, obs)
            if new_path.likelihood > threshold:
                paths.append(new_path)
                if len(paths) >= max_paths:
                    break
                queue.append(new_path)
    paths.sort(key=lambda p: p.likelihood, reverse=True)
    return Ok(paths)


# ---------------------------------------------------------------------------
# Topological / Geometric / Quantum (TOPO1–3, GEO1–3, QNT1–3)
# ---------------------------------------------------------------------------


def topological_analysis(event: Any) -> Result[TopologicalSignature]:
    try:
        point = substrates.to_point(event.position)
        cls = substrates.manifold_classify(point)
    except Exception as exc:
        return error(TOPOLOGICAL_ANALYSIS_FAILED, reason=str(exc))
    return Ok(
        TopologicalSignature(
            manifold=str(cls["manifold"]),
            region=str(cls["region"]),
            homotopy=str(cls["homotopy"]),
            lyapunov=float(cls["lyapunov"]),
            greene=float(cls["greene"]),
            action_var=float(cls["action_variance"]),
            period1=bool(cls["period1"]),
        )
    )


def geometric_analysis(event: Any) -> Result[CurvatureReport]:
    try:
        point = substrates.to_point(event.position)
        curv = substrates.curvature_at(point)
    except Exception as exc:
        return error(GEOMETRIC_ANALYSIS_FAILED, reason=str(exc))
    return Ok(
        CurvatureReport(
            point=point,
            ricci=float(curv["ricci"]),
            scalar=float(curv["scalar"]),
            sectional=float(curv["sectional"]),
            geodesic_dist=float(curv["geodesic_distance_to_origin"]),
        )
    )


def quantum_fold(state: Sequence[float]) -> Result[np.ndarray]:
    try:
        folded, _ = substrates.fold_11d_vector(state)
    except Exception as exc:
        return error(QUANTUM_FOLD_FAILED, reason=str(exc))
    return Ok(np.asarray(folded, dtype=np.float64))
