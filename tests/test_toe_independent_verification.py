"""Independent adversarial verification of the elevated TOE capabilities.

This file deliberately re-derives expected values from first principles instead
of importing the repository probe's expectations, so it is a second opinion
rather than a mirror of scripts/probe_hyba_capability.py.

Run: python -m pytest tests/test_toe_independent_verification.py -q
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from toe.causal_ladder import (  # noqa: E402
    CausalCapabilityUnavailable,
    CausalGraph,
    StructuralCausalModel,
    counterfactual_state,
    estimate_causal_effect,
    identify_backdoor,
    intervene,
)
from toe.explanation import explain, structural_model  # noqa: E402
from toe.policy import Constraint, Objective, counterfactual_futures, decide  # noqa: E402
from toe.receipts import ReceiptLedger, replay, verify_binding, verify_chain  # noqa: E402

PHI = (1 + math.sqrt(5)) / 2


def _scm(edges, nodes=()):
    return StructuralCausalModel(CausalGraph.from_edges(edges, nodes=list(nodes)))


def test_adjusted_effect_truth_derived_by_independent_do_simulation():
    """Adjusted estimate must materially beat naive against a do() truth.

    The truth is NOT a repository constant: it is recomputed here by an
    independent Monte-Carlo do() pass that severs the incoming edges of X.
    """
    beta, gamma, alpha = 3.0, 2.0, 1.5
    scm = _scm([("U", "X", alpha), ("X", "Y", beta), ("U", "Y", gamma)])
    rng = np.random.default_rng(20260929)
    n_mc = 400_000

    def do_effect(x_value):
        u = rng.normal(0.0, 1.0, n_mc)
        u_y = rng.normal(0.0, 1.0, n_mc)
        return (beta * x_value + gamma * u + u_y).mean()

    truth = do_effect(1.0) - do_effect(0.0)
    assert abs(truth - beta) < 0.05, f"independent do() truth {truth} should be near {beta}"

    n = 60_000
    u = rng.normal(0.0, 1.0, n)
    ex = rng.normal(0.0, 1.0, n)
    ey = rng.normal(0.0, 1.0, n)
    x = alpha * u + ex
    y = beta * x + gamma * u + ey
    est = estimate_causal_effect(
        {"U": u.tolist(), "X": x.tolist(), "Y": y.tolist()},
        scm.graph,
        "X",
        "Y",
        observed=["U", "X", "Y"],
    )
    assert est.available, est.reason
    assert est.adjustment_set == ["U"]
    naive_err = abs(est.naive_effect - truth)
    adjusted_err = abs(est.adjusted_effect - truth)
    assert naive_err > 0.4, "naive estimate must be biased for this test to mean anything"
    assert adjusted_err < naive_err / 5.0, (
        f"adjusted {est.adjusted_effect} not materially closer to truth {truth} "
        f"than naive {est.naive_effect}"
    )
    assert adjusted_err < 0.05, f"adjusted error {adjusted_err} exceeds 0.05"


def test_counterfactual_hand_computed_with_genuine_incoming_parents():
    """U -> X -> Y, U -> Y, Z -> X. do(X) must sever U->X and Z->X."""
    scm = _scm(
        [("U", "X", 2.0), ("X", "Y", 3.0), ("U", "Y", 5.0), ("Z", "X", 7.0)],
        nodes=["U", "X", "Y", "Z"],
    )
    factual = {"U": 1.0, "Z": 2.0, "X": 3.0, "Y": 4.0}
    cf = counterfactual_state(scm, {"X": 10.0}, factual, ["Y"], arithmetic="float64")
    assert cf["surgery"]["edges_cut"], "intervened node has parents; edges must be cut"

    u_y = (factual["Y"] - 3.0 * factual["X"] - 5.0 * factual["U"]) / PHI
    expected = 3.0 * 10.0 + 5.0 * factual["U"] + PHI * u_y
    assert cf["outcome_values"]["Y"] == pytest.approx(expected, abs=1e-9)

    moved = counterfactual_state(
        scm, {"X": 10.0}, {**factual, "Z": 1002.0}, ["Y"], arithmetic="float64"
    )
    assert moved["outcome_values"]["Y"] == pytest.approx(expected, abs=1e-9)


def test_intervention_edge_cut_is_observed_and_factual_model_survives():
    scm = _scm([("U", "X", 2.0), ("X", "Y", 3.0), ("U", "Y", 5.0)], nodes=["U", "X", "Y"])
    surgery = intervene(scm, {"X": 10.0})["surgery"]
    assert [list(e)[:2] for e in surgery["incoming_edges_before"]["X"]] == [["U", "X"]]
    assert surgery["incoming_edges_after"]["X"] == []
    assert scm.graph.incoming("X"), "factual model must be untouched by do()"


def _adversarial_model(beta=4.0):
    """Y = beta*X1 + X2. Z and W are never read by the model."""

    def model(inputs):
        return {"Y": beta * inputs["X1"] + 1.0 * inputs["X2"]}

    return model


def test_explanation_ignores_irrelevant_huge_feature():
    background = [{"X1": 0.1 * i, "X2": 0.2 * i, "Z": 3.0, "W": 10.0 * i} for i in range(1, 9)]
    for scale in (1.0, 10.0, 1000.0):
        point = {"X1": 2.0, "X2": 1.0, "Z": 500.0, "W": 9000.0 * scale}
        bg = [dict(row, W=row["W"] * scale) for row in background]
        res = explain(_adversarial_model(), point, target="Y", background=bg, model_id="adv")
        assert res.available, res.reason
        assert res.attributions["Z"] == 0.0
        assert res.attributions["W"] == 0.0
        assert res.ranking[0] == "X1", f"W scale {scale} let an irrelevant feature lead"
        assert res.ranking.index("X1") < res.ranking.index("W")
        assert res.completeness_residual == pytest.approx(0.0, abs=1e-8)


def test_explanation_is_target_specific_and_order_invariant():
    def model(inputs):
        return {"Y": 3.0 * inputs["X1"], "T": 2.0 * inputs["X2"]}

    bg = [{"X1": i * 0.5, "X2": i * 0.25} for i in range(1, 7)]
    point = {"X1": 2.0, "X2": 3.0}
    a = explain(model, point, target="Y", background=bg, model_id="m")
    b = explain(model, point, target="T", background=bg, model_id="m")
    assert a.ranking[0] == "X1"
    assert b.ranking[0] == "X2"
    c = explain(model, {"X2": 3.0, "X1": 2.0}, target="Y", background=bg, model_id="m")
    assert c.attributions == a.attributions
    assert c.evidence_sha256 == a.evidence_sha256


def test_explanation_attribution_is_monotone_in_the_true_coefficient():
    bg = [{"X1": 0.5 * i, "X2": 0.25 * i} for i in range(1, 7)]
    point = {"X1": 2.0, "X2": 1.0}
    series = [
        explain(
            _adversarial_model(beta), point, target="Y", background=bg, model_id="m"
        ).attributions["X1"]
        for beta in (1.0, 2.0, 4.0)
    ]
    assert series[0] < series[1] < series[2], f"not monotone: {series}"


def test_explanation_refuses_without_model_identity():
    def model(inputs):
        return {"Y": inputs["X1"]}

    bg = [{"X1": 1.0}, {"X1": 2.0}]
    res = explain(model, {"X1": 1.0}, target="Y", background=bg, model_id=None)
    assert res.available is False
    assert res.attributions == {}
    assert "model identifier" in res.reason


def test_explanation_refuses_when_the_model_cannot_be_evaluated():
    def model(inputs):
        raise RuntimeError("substrate offline")

    bg = [{"X1": 1.0}, {"X1": 2.0}]
    res = explain(model, {"X1": 1.0}, target="Y", background=bg, model_id="broken")
    assert res.available is False
    assert res.attributions == {}
    assert res.reason


def test_policy_follows_futures_and_flips_with_the_model():
    scm = _scm([("X", "Y", 1.0)], nodes=["X", "Y"])
    state = {"X": 0.0, "Y": 0.0}
    candidates = {"A": {"X": 4.0}, "B": {"X": 9.0}, "C": {"X": 14.0}}
    decision = decide(
        state,
        candidates,
        futures=counterfactual_futures(scm, outcomes=["Y"]),
        objective=Objective(target="Y", sense="maximize"),
        constraints=[Constraint(name="safety", variable="Y", op="<=", bound=10.0)],
        model_id=scm.digest(),
    )
    assert decision.available
    assert decision.selected_action == "B"
    excluded = {f["action"]: f["excluded_because"] for f in decision.futures}
    assert "safety" in excluded["C"]

    flipped = _scm([("X", "Y", -1.0)], nodes=["X", "Y"])
    d2 = decide(
        state,
        candidates,
        futures=counterfactual_futures(flipped, outcomes=["Y"]),
        objective=Objective(target="Y", sense="maximize"),
        constraints=[],
        model_id=flipped.digest(),
    )
    assert d2.selected_action == "A", "selection must follow the structural model"


def test_counterfactual_negative_controls():
    scm = _scm(
        [("U", "X", 2.0), ("X", "Y", 3.0), ("U", "Y", 5.0), ("Z", "X", 7.0)],
        nodes=["U", "X", "Y", "Z"],
    )
    base = {"U": 1.0, "Z": 2.0, "X": 3.0, "Y": 4.0}
    a = counterfactual_state(scm, {"X": 10.0}, base, ["Y"])["outcome_values"]["Y"]
    b = counterfactual_state(scm, {"X": 11.0}, base, ["Y"])["outcome_values"]["Y"]
    assert abs(a - b) > 1.0, "changing the intervention value must change the outcome"

    # A node with no path to Y must not fabricate an effect. Here Z does reach
    # Y (Z -> X -> Y), so it legitimately does; use a genuinely isolated node.
    isolated = _scm([("X", "Y", 3.0)], nodes=["X", "Y", "W"])
    quiet = {"X": 1.0, "Y": 2.0, "W": 0.0}
    c = counterfactual_state(isolated, {"W": 500.0}, quiet, ["Y"])["outcome_values"]["Y"]
    assert c == pytest.approx(quiet["Y"], abs=1e-9)

    with pytest.raises(CausalCapabilityUnavailable):
        counterfactual_state(scm, {"X": 10.0}, {"X": 3.0, "Y": 4.0}, ["Y"])


def test_receipts_detect_every_mutation_channel():
    scm = _scm([("X", "Y", 1.0)], nodes=["X", "Y"])
    ledger = ReceiptLedger(run_id="verify")
    state = {"X": 0.0, "Y": 0.0}
    obj = Objective(target="Y", sense="maximize")

    def build(model):
        return decide(
            state,
            {"A": {"X": 1.0}, "B": {"X": 2.0}},
            futures=counterfactual_futures(model, outcomes=["Y"]),
            objective=obj,
            model_id=model.digest(),
        ).as_dict()

    output = build(scm)
    receipt = ledger.issue(
        "action",
        inputs={"state": state},
        config={"model_id": scm.digest(), "objective": obj.as_dict()},
        output=output,
        execution_evidence={"arithmetic": "float64"},
    )
    assert verify_chain(ledger.records)["ok"]
    assert verify_binding(receipt, inputs={"state": state}, output=output)["ok"]
    assert not verify_binding(receipt, inputs={"state": {"X": 99.0, "Y": 0.0}})["ok"]
    assert not verify_binding(receipt, output={**output, "selected_action": "Z"})["ok"]
    assert replay(receipt, lambda: build(scm))["ok"]
    mutated = _scm([("X", "Y", 5.0)], nodes=["X", "Y"])
    assert not replay(receipt, lambda: build(mutated))["ok"], "parameter change must break replay"

    two = ReceiptLedger(run_id="order")
    two.issue("a", inputs={"x": 1}, config={}, output={"v": 1})
    two.issue("b", inputs={"x": 2}, config={}, output={"v": 2})
    assert verify_chain(list(reversed(two.records)))["ok"] is False


def test_agreement_collapses_for_duplicates_and_drops_on_conflict():
    from toe.agreement import evaluator_agreement

    same = evaluator_agreement(
        {"m1": [1.0, 2.0], "m2": [1.0, 2.0]}, evaluator_ids={"m1": "cfg", "m2": "cfg"}
    )
    assert same["available"] is False and same["agreement"] is None
    disagree = evaluator_agreement({"a": [1.0, 0.0], "b": [-1.0, 0.0]})
    assert disagree["available"] is True
    assert disagree["agreement"] == pytest.approx(0.0, abs=1e-9)


def test_backdoor_sets_match_hand_analysis():
    confounded = CausalGraph.from_edges([("U", "X", 1.0), ("U", "Y", 1.0), ("X", "Y", 1.0)])
    assert identify_backdoor(confounded, "X", "Y") == ["U"]
    assert identify_backdoor(CausalGraph.from_edges([("X", "Y", 1.0)]), "X", "Y") == []
    collider = CausalGraph.from_edges(
        [("X", "Y", 1.0), ("A", "Y", 1.0), ("B", "Y", 1.0), ("A", "B", 1.0)]
    )
    assert identify_backdoor(collider, "X", "Y") == []


def test_structural_model_helper_is_do_semantics():
    scm = _scm([("X", "Y", 2.0)], nodes=["X", "Y"])
    assert structural_model(scm)({"X": 3.0})["Y"] == pytest.approx(6.0)


def test_toe_core_contains_no_mining_vocabulary():
    banned = (
        "bitcoin",
        "nonce",
        "mining",
        "blockchain",
        "block_hash",
        "hashrate",
        "wallet",
        "share submission",
    )
    for name in ("causal_ladder", "explanation", "policy", "receipts", "agreement"):
        text = (REPO_ROOT / "toe" / f"{name}.py").read_text(encoding="utf-8").lower()
        # "stratum" on its own is ordinary statistics vocabulary (a
        # stratification stratum), so the mining sense is matched explicitly.
        hits = [w for w in banned if w in text]
        if "stratum" in text:
            hits += [w for w in ("stratum tcp", "stratum+tcp", "mining stratum") if w in text]
        assert hits == [], f"toe/{name}.py contains mining vocabulary: {hits}"


def test_report_artifact_is_valid_and_declares_boundaries():
    data = json.loads(
        (REPO_ROOT / "reports" / "toe_elevation_benchmark.json").read_text(encoding="utf-8")
    )
    for key in ("commit", "causality", "explanation", "action_policy", "claim_boundaries"):
        assert key in data, f"report is missing {key}"
    assert data["summary"]["checks_failed"] == 0
    assert "NOT ESTABLISHED" in " ".join(data["claim_boundaries"])


def test_bridge_reason_runs_the_full_sequence():
    from toe.bridge import TOEBridge

    bridge = TOEBridge()
    rng = np.random.default_rng(7)
    n = 5000
    u = rng.normal(size=n)
    x = 1.5 * u + rng.normal(size=n)
    y = 3.0 * x + 2.0 * u + rng.normal(size=n)
    out = bridge.reason(
        {
            "graph": [("U", "X", 1.5), ("X", "Y", 3.0), ("U", "Y", 2.0)],
            "state": {"U": float(u[0]), "X": float(x[0]), "Y": float(y[0])},
            "samples": {"U": u.tolist(), "X": x.tolist(), "Y": y.tolist()},
            "treatment": "X",
            "outcome": "Y",
            "observed": ["U", "X", "Y"],
            "intervention": {"X": 1.0},
            "candidates": {"low": {"X": -1.0}, "high": {"X": 2.0}},
            "objective": {"target": "Y", "sense": "maximize"},
        }
    )
    assert out["available"], out["unavailable"]
    for section in (
        "state",
        "causal_analysis",
        "intervention",
        "counterfactual",
        "explanation",
        "action_policy",
        "provenance",
        "execution_evidence",
    ):
        assert out[section]["available"] is True, f"{section}: {out[section].get('reason')}"
    assert out["causal_analysis"]["effect"]["adjusted_effect"] == pytest.approx(3.0, abs=0.2)
    assert out["action_policy"]["selected_action"] == "high"
    assert out["provenance"]["ledger"]["ok"] is True


def test_bridge_reason_fails_closed_without_samples():
    from toe.bridge import TOEBridge

    out = TOEBridge().reason(
        {
            "graph": [("U", "X", 1.0), ("X", "Y", 2.0)],
            "state": {"U": 1.0, "X": 2.0, "Y": 3.0},
            "treatment": "X",
            "outcome": "Y",
        }
    )
    assert out["available"] is False
    effect = out["causal_analysis"]["effect"]
    assert effect["available"] is False
    assert effect.get("adjusted_effect") is None, "must not invent an effect"
    assert out["unavailable"], "unavailable sections must be named"


def test_probe_exits_nonzero_when_an_invariant_is_broken(tmp_path):
    """Run the real probe out of process with a sabotaged estimator.

    The estimator is replaced so the adjusted effect equals the biased naive
    effect. If the harness were not fail-closed this run would print PASS and
    exit 0, which is exactly the regression this guards against.
    """
    probe = REPO_ROOT / "scripts" / "probe_hyba_capability.py"
    assert probe.exists()
    (tmp_path / "sitecustomize.py").write_text(
        "import toe.causal_ladder as cl\n"
        "_real = cl.estimate_causal_effect\n"
        "def _fake(samples, graph, treatment, outcome, *a, **kw):\n"
        "    est = _real(samples, graph, treatment, outcome, *a, **kw)\n"
        "    if est.available:\n"
        "        est.adjusted_effect = est.naive_effect\n"
        "    return est\n"
        "cl.estimate_causal_effect = _fake\n"
        "import toe.bridge as br\n"
        "br.estimate_causal_effect = _fake\n",
        encoding="utf-8",
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{tmp_path}{os.pathsep}{REPO_ROOT}"
    proc = subprocess.run(
        [sys.executable, str(probe), "--only", "causality"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    # The sabotage must be caught by name, not merely produce a nonzero exit:
    # otherwise this test would still pass if the harness crashed for an
    # unrelated reason.
    assert proc.returncode == 1, f"expected exit 1, got {proc.returncode}\n{proc.stdout[-2000:]}"
    assert "STATUS        : FAIL" in proc.stdout
    assert "adjusted_effect == truth" in proc.stdout
    assert "STATUS        : PASS" not in proc.stdout


def test_probe_passes_and_exits_zero_on_intact_code():
    """The control for the test above: unmodified code must exit 0 and PASS."""
    probe = REPO_ROOT / "scripts" / "probe_hyba_capability.py"
    proc = subprocess.run(
        [sys.executable, str(probe), "--only", "causality,intervention,counterfactual"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout[-2000:]
    assert "STATUS        : PASS" in proc.stdout
