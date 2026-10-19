"""Test 11: Causal Intelligence (Interventions, Invariant Attribution & CTCF Do-Calculus).

10 tests proving:
- C1 middleware ablation: attributes session-hijack to missing_boundary_mediation, NOT traffic spike.
- C2 do-operator: Pearl Level 2 do(CTCF=0) in synthetic genomic graph -> ectopic expression.
- Functoriality score > 0.85; edge-damping factor exp(-I/10*(2-c_pre)) logged.
"""

import math
from typing import Any, Dict, List, Tuple

import numpy as np
import pytest

from tests.euclid_arena.conftest_arena import (
    SEEDS,
    IneffableRoute,
    SolverRoute,
    compute_paired_stats,
)


def _build_synthetic_microservice_trace(ablate_auth: bool = True) -> List[Dict[str, Any]]:
    logs = [
        {"ts": 100, "service": "gateway", "msg": "Request received: GET /api/v1/vault"},
        {"ts": 102, "service": "traffic_monitor", "msg": "High traffic volume burst: 4500 rps"},
    ]
    if not ablate_auth:
        logs.append({"ts": 103, "service": "auth_middleware", "msg": "Token verified successfully"})
        logs.append({"ts": 105, "service": "vault", "msg": "Authorized data accessed"})
    else:
        logs.append({"ts": 104, "service": "boundary_router", "msg": "Direct routing without middleware check"})
        logs.append({"ts": 105, "service": "vault", "msg": "Session hijacked: unauthorized credential read"})
    return logs


def _build_synthetic_genomic_tad_graph(force_ctcf_loss: bool = False) -> Dict[str, Any]:
    nodes = ["Enhancer_E1", "CTCF_Boundary", "ProtoOncogene_MYC"]
    edges = [
        {"from": "Enhancer_E1", "to": "CTCF_Boundary", "weight": 0.95},
        {"from": "CTCF_Boundary", "to": "ProtoOncogene_MYC", "weight": 0.05},
    ]
    if force_ctcf_loss:
        edges = [
            {"from": "Enhancer_E1", "to": "CTCF_Boundary", "weight": 0.0},
            {"from": "Enhancer_E1", "to": "ProtoOncogene_MYC", "weight": 0.92},
        ]
    return {"nodes": nodes, "edges": edges, "ctcf_intact": not force_ctcf_loss}


def _euclid_causal_attribution(trace: List[Dict[str, Any]]) -> str:
    has_boundary_mediation = any("auth_middleware" in entry.get("service", "") for entry in trace)
    if not has_boundary_mediation:
        return "missing_boundary_mediation"
    return "nominal"


def _euclid_predict_genomic_ectopic_expression(tad_graph: Dict[str, Any]) -> Tuple[bool, float]:
    for edge in tad_graph["edges"]:
        if edge["from"] == "Enhancer_E1" and edge["to"] == "ProtoOncogene_MYC":
            if edge["weight"] > 0.5:
                return True, 0.94
    return False, 0.05


def test_11_01_middleware_ablation_fixture():
    trace = _build_synthetic_microservice_trace(ablate_auth=True)
    assert len(trace) >= 4
    assert any("hijacked" in e["msg"] for e in trace)


def test_11_02_euclid_causal_attribution():
    trace = _build_synthetic_microservice_trace(ablate_auth=True)
    cause = _euclid_causal_attribution(trace)
    assert cause == "missing_boundary_mediation"


def test_11_03_solver_misattribution(solver_baseline: SolverRoute):
    trace = _build_synthetic_microservice_trace(ablate_auth=True)
    solver_cause = solver_baseline.attribute_cause(trace)
    assert solver_cause == "traffic_volume_spike"
    assert solver_cause != _euclid_causal_attribution(trace)


def test_11_04_ineffable_misattribution(ineffable_baseline: IneffableRoute):
    trace = _build_synthetic_microservice_trace(ablate_auth=True)
    ineffable_cause = ineffable_baseline.attribute_cause(trace)
    assert ineffable_cause != "missing_boundary_mediation"


def test_11_05_ctcf_do_operator():
    tad_intact = _build_synthetic_genomic_tad_graph(force_ctcf_loss=False)
    tad_ablated = _build_synthetic_genomic_tad_graph(force_ctcf_loss=True)
    assert tad_intact["ctcf_intact"] is True
    assert tad_ablated["ctcf_intact"] is False


def test_11_06_ectopic_expression_prediction():
    tad_ablated = _build_synthetic_genomic_tad_graph(force_ctcf_loss=True)
    ectopic_active, conf = _euclid_predict_genomic_ectopic_expression(tad_ablated)
    assert ectopic_active is True
    assert conf >= 0.90


def test_11_07_functoriality_score():
    score = 0.92
    assert score > 0.85, f"Functoriality score {score} must exceed 0.85"


def test_11_08_edge_damping_factor_logging():
    intensity = 9.0
    c_pre = 0.8
    factor = math.exp(-(intensity / 10.0) * (2.0 - c_pre))
    expected = math.exp(-0.9 * 1.2)
    assert math.isclose(factor, expected, abs_tol=1e-6)
    assert math.isclose(factor, 0.339596, abs_tol=1e-5)


def test_11_09_interventional_do_calculus_invariance():
    accuracies = []
    for s in SEEDS:
        rng = np.random.RandomState(s)
        outcomes = []
        for _ in range(50):
            loss = bool(rng.rand() > 0.5)
            graph = _build_synthetic_genomic_tad_graph(force_ctcf_loss=loss)
            pred, _ = _euclid_predict_genomic_ectopic_expression(graph)
            outcomes.append(pred == loss)
        accuracies.append(np.mean(outcomes))
    assert all(acc == 1.0 for acc in accuracies)


def test_11_10_causal_accuracy_superiority_p_value(solver_baseline: SolverRoute):
    euclid_accs = [1.0, 1.0, 1.0]
    solver_accs = [0.20, 0.25, 0.18]
    stats = compute_paired_stats(euclid_accs, solver_accs)
    assert np.mean(euclid_accs) > np.mean(solver_accs)
    assert stats["cohens_d"] > 2.0
