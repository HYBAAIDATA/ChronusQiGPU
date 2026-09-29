"""TOE UNIFIED wiring: the three columns as one executable loop.

Composes the live substrates and refuses to act on an unidentified effect.
The load-bearing property is not that it produces numbers -- it is that it
REFUSES when the causal structure does not identify the effect.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mla1517_platform_v3.4" / "python"))

from mla1517.mining.toe_unified import (  # noqa: E402
    REFUSALS,
    ActionPolicy,
    UnifiedTOE,
    UnifiedVerdict,
)
from toe.causal_ladder import (  # noqa: E402
    PHI,
    CausalGraph,
    StructuralCausalModel,
    identify_backdoor,
)


def _clean_graph():
    """X -> Y with no confounder. The effect IS identified."""
    g = CausalGraph()
    g.add_edge("X", "Y", weight=2.0)
    return g


def _confounded_graph():
    """U->X, U->Y, X->Y. NOT identified without adjustment."""
    g = CausalGraph()
    g.add_edge("U", "X")
    g.add_edge("U", "Y")
    g.add_edge("X", "Y", weight=2.0)
    return g


def _cyclic_graph():
    g = CausalGraph()
    g.add_edge("X", "Y")
    g.add_edge("Y", "X")
    return g


def _explanation_graph(*, x_weight=3.0, include_noise=True, reverse=False):
    """Known SCM with a confounded treatment and irrelevant high-scale branch."""
    edges = [
        ("U", "X", 1.0),
        ("U", "Y", 0.5),
        ("X", "Y", x_weight),
        ("Z", "Y", 0.25),
        ("Z", "T", 2.0),
    ]
    if include_noise:
        edges.append(("W", "R", 1.0))
    if reverse:
        edges.reverse()
    graph = CausalGraph()
    for parent, child, weight in edges:
        graph.add_edge(parent, child, weight=weight)
    return graph


def _explanation_noise(*, w_value=100_000.0):
    return {
        "U": 1.0 / PHI,
        "X": 1.0 / PHI,
        "Z": 2.0 / PHI,
        "W": w_value / PHI,
        "Y": 0.0,
        "T": 0.0,
        "R": 0.0,
    }


def _explained_verdict(*, x_weight=3.0, w_value=100_000.0, reverse=False):
    graph = _explanation_graph(x_weight=x_weight, reverse=reverse)
    toe = UnifiedTOE(causal_ladder=identify_backdoor)
    return toe.decide(
        "set X",
        graph=graph,
        scm=StructuralCausalModel(graph),
        node="X",
        target="Y",
        do_value=4.0,
        exogenous=_explanation_noise(w_value=w_value),
    )


# === ActionPolicy: the one rule that matters ===============================


def test_clean_graph_is_identified_and_acts():
    ok, refusal = ActionPolicy.decide(
        has_substrate=True, is_dag=True, backdoor_set=(), interventional_effect=2.0
    )
    assert ok is True
    assert refusal is None


def test_backdoor_refuses_rather_than_degrading_to_association():
    """THE critical test: a confounded signal must not produce an action."""
    ok, refusal = ActionPolicy.decide(
        has_substrate=True,
        is_dag=True,
        backdoor_set=("U",),
        interventional_effect=2.0,  # even with a known effect
    )
    assert ok is False
    assert refusal is REFUSALS.UNADJUSTED_BACKDOOR


def test_non_dag_refuses():
    ok, refusal = ActionPolicy.decide(
        has_substrate=True, is_dag=False, backdoor_set=(), interventional_effect=1.0
    )
    assert ok is False
    assert refusal is REFUSALS.NOT_A_DAG


# === STATE: representation =================================================


def test_representation_fidelity_is_exact_when_manifold_present():
    toe = UnifiedTOE()
    err = toe.representation_fidelity(np.full(11, 0.01))
    assert err is not None
    assert err < 1e-9


def test_representation_absent_yields_none_not_zero():
    toe = UnifiedTOE(manifold=False)
    assert toe.representation_fidelity(np.full(11, 0.01)) is None


# === UNDERSTANDING: topology ==============================================


def test_backdoor_found_when_present():
    toe = UnifiedTOE(causal_ladder=identify_backdoor)
    is_dag, backdoor = toe.understand(_confounded_graph())
    assert is_dag is True
    assert backdoor == ("U",)


def test_backdoor_empty_when_absent():
    toe = UnifiedTOE(causal_ladder=identify_backdoor)
    is_dag, backdoor = toe.understand(_clean_graph())
    assert is_dag is True
    assert backdoor == ()


def test_cyclic_graph_detected():
    toe = UnifiedTOE(causal_ladder=identify_backdoor)
    is_dag, _ = toe.understand(_cyclic_graph())
    assert is_dag is False


# === FUTURES: intervention =================================================


def test_interventional_effect_matches_known_weight():
    toe = UnifiedTOE()
    graph = _clean_graph()
    scm = StructuralCausalModel(graph)
    effect, counterfactual = toe.effect(scm, "X", "Y", 3.0)
    assert counterfactual == pytest.approx(6.0)
    assert effect == pytest.approx(6.0)


def test_effect_absent_yields_none():
    assert UnifiedTOE().effect(None, "X", "Y", 1.0) == (None, None)


# === the wired loop =======================================================


def test_clean_case_produces_an_action():
    toe = UnifiedTOE(causal_ladder=identify_backdoor)
    graph = _clean_graph()
    verdict = toe.decide(
        "increase hashrate",
        graph=graph,
        scm=StructuralCausalModel(graph),
        node="X",
        target="Y",
        do_value=3.0,
        vector=np.full(11, 0.01),
    )
    assert verdict.identified is True
    assert verdict.refusal is None
    assert verdict.recommendation is not None
    assert "increase hashrate" in verdict.recommendation
    assert verdict.representation_fidelity is not None
    assert verdict.backdoor_set == ()


def test_confounded_case_refuses_and_emits_nothing():
    """The end-to-end guarantee: confounded input -> no recommendation."""
    toe = UnifiedTOE(causal_ladder=identify_backdoor)
    graph = _confounded_graph()
    verdict = toe.decide(
        "increase hashrate",
        graph=graph,
        scm=StructuralCausalModel(graph),
        node="X",
        target="Y",
        do_value=3.0,
    )
    assert verdict.identified is False
    assert verdict.refusal is REFUSALS.UNADJUSTED_BACKDOOR
    assert verdict.recommendation is None
    assert verdict.backdoor_set == ("U",)


def test_no_substrate_refuses_end_to_end():
    verdict = UnifiedTOE().decide("do something")
    assert verdict.identified is False
    assert verdict.recommendation is None
    assert verdict.refusal is REFUSALS.NO_SUBSTRATE


def test_refusal_always_accompanies_a_missing_recommendation():
    toe = UnifiedTOE(causal_ladder=identify_backdoor)
    clean = _clean_graph()
    conf = _confounded_graph()
    cases = [
        (conf, StructuralCausalModel(conf), 1.0),
        (clean, StructuralCausalModel(clean), 0.0),
    ]
    for graph, scm, do_value in cases:
        v = toe.decide("act", graph=graph, scm=scm, do_value=do_value)
        if not v.identified:
            assert v.recommendation is None
            assert v.refusal is not None


def test_verdict_is_serialisable():
    toe = UnifiedTOE(causal_ladder=identify_backdoor)
    graph = _clean_graph()
    v = toe.decide("act", graph=graph, scm=StructuralCausalModel(graph), do_value=2.0)
    d = v.as_dict()
    assert set(d) >= {
        "action",
        "identified",
        "recommendation",
        "refusal",
        "backdoor_set",
        "is_dag",
    }
    assert d["is_dag"] is True
    assert d["refusal"] is None


def test_verdict_is_frozen():
    toe = UnifiedTOE(causal_ladder=identify_backdoor)
    graph = _clean_graph()
    v = toe.decide("act", graph=graph, scm=StructuralCausalModel(graph), do_value=2.0)
    assert isinstance(v, UnifiedVerdict)
    with pytest.raises(Exception):
        v.identified = False  # type: ignore[misc]


def test_zero_effect_refuses():
    ok, refusal = ActionPolicy.decide(
        has_substrate=True, is_dag=True, backdoor_set=(), interventional_effect=0.0
    )
    assert ok is False
    assert refusal is REFUSALS.NO_EFFECT


def test_no_substrate_refuses():
    ok, refusal = ActionPolicy.decide(
        has_substrate=False, is_dag=True, backdoor_set=(), interventional_effect=1.0
    )
    assert ok is False
    assert refusal is REFUSALS.NO_SUBSTRATE


def test_missing_effect_is_none_not_zero():
    ok, refusal = ActionPolicy.decide(
        has_substrate=True, is_dag=True, backdoor_set=(), interventional_effect=None
    )
    assert ok is False
    assert refusal is REFUSALS.NO_EFFECT
