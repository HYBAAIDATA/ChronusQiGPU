"""Canonical fail-closed TOE capability harness.

Every claim this script prints is an assertion. A failed assertion, or a
section that crashes, marks the run FAILED and the process exits 1. A
required section that cannot run in this environment (for example the Iris
reproduction without scikit-learn) is recorded as UNAVAILABLE with its
reason, and the process exits 2. Only when every check passes and nothing is
unavailable does it print PASS and exit 0.

Sections (the TOE verification matrix):

  state            11D Poincare fold/unfold roundtrip
  prediction       kellogg exact_linear, binary setosa-vs-rest (binary scope)
  causality        confounding bias, backdoor sets, adjusted effect vs the
                   model's own do() truth, synthetic calibration/validation
  intervention     node with incoming parents; edges cut on a copy
  counterfactual   abduction-action-prediction with negative controls
  explanation      the ten-property adversarial suite
  agreement        distinct evaluators; drops when they disagree
  action_policy    known optimum, constraint exclusion, model perturbation
  provenance       replay and mutation detection
  exact_arithmetic Q(phi) exact path vs float path
  bridge           the canonical TOEBridge.reason sequence
  domain           TOE core modules carry no mining vocabulary

Usage:
  python scripts/probe_hyba_capability.py
  python scripts/probe_hyba_capability.py --pytest --report reports/toe_elevation_benchmark.json

History: the previous version of this probe printed booleans without
asserting them, measured bias against a hard-coded 3.000 instead of running a
repository estimator, used ``evaluate_all`` in place of the counterfactual
API, intervened on a node with no parents, and called the float phi path
exact. Each of those is now an asserted check against repository code.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import random
import re
import subprocess
import sys
import tempfile
import time
import traceback
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lucas.algebra import ZPhi  # noqa: E402
from toe.agreement import evaluator_agreement  # noqa: E402
from toe.bridge import CAPABILITY_EVIDENCE, TOEBridge  # noqa: E402
from toe.causal_ladder import (  # noqa: E402
    ARITHMETIC_EXACT,
    PHI,
    CausalCapabilityUnavailable,
    CausalGraph,
    StructuralCausalModel,
    counterfactual_query,
    counterfactual_state,
    estimate_causal_effect,
    identify_backdoor,
    intervene,
)
from toe.explanation import explain, structural_model  # noqa: E402
from toe.policy import Constraint, Objective, counterfactual_futures, decide  # noqa: E402
from toe.receipts import ReceiptLedger, replay, verify_binding, verify_chain  # noqa: E402

EFFECT_TOLERANCE_SE = 4.0
COUNTERFACTUAL_TOLERANCE = 1e-12
CALIBRATION_SEEDS = list(range(0, 10))
VALIDATION_SEEDS = list(range(100, 120))
COEFFICIENT_SEED = 2026
PYTEST_FILES = [
    "tests/test_toe_elevation.py",
    # Second opinion: re-derives expected values from first principles and
    # proves the harness fails closed when an invariant is broken.
    "tests/test_toe_independent_verification.py",
    "tests/test_toe_package.py",
    "tests/test_toe_propagator_cache.py",
    "tests/test_toe_expansion_contract.py",
    "tests/test_toe_consensus_boundary.py",
    "tests/test_intelligence_poincare_salamander.py",
]
PLATFORM_PYTEST_FILES = ["test_toe_mining_integration.py", "test_structured_observed_context.py"]


class Harness:
    def __init__(self) -> None:
        self.checks: List[Dict[str, Any]] = []
        self.unavailable: List[Dict[str, str]] = []

    def check(self, section: str, name: str, passed: bool, **evidence: Any) -> bool:
        passed = bool(passed)
        self.checks.append(
            {"section": section, "name": name, "passed": passed, "evidence": evidence}
        )
        mark = "PASS" if passed else "FAIL"
        detail = ", ".join(f"{k}={_short(v)}" for k, v in evidence.items())
        print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))
        return passed

    def mark_unavailable(self, section: str, reason: str) -> None:
        self.unavailable.append({"section": section, "reason": reason})
        print(f"  [UNAVAILABLE] {section}: {reason}")

    @property
    def failed(self) -> List[Dict[str, Any]]:
        return [c for c in self.checks if not c["passed"]]


def _short(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    text = str(value)
    return text if len(text) <= 60 else text[:57] + "..."


def _graph(*edges: Any) -> CausalGraph:
    return CausalGraph.from_edges(edges)


def _zphi(d: Dict[str, str]) -> ZPhi:
    return ZPhi(Fraction(d["a"]), Fraction(d["b"]))


def structural_truth(scm: StructuralCausalModel, treatment: str, outcome: str) -> float:
    """E[Y|do(X=1)] - E[Y|do(X=0)] from the model's exact do(), not the estimator."""
    one = intervene(scm, {treatment: 1}, arithmetic=ARITHMETIC_EXACT)["exact_values"][outcome]
    zero = intervene(scm, {treatment: 0}, arithmetic=ARITHMETIC_EXACT)["exact_values"][outcome]
    diff = _zphi(one) - _zphi(zero)
    if diff.b != 0:
        raise AssertionError("linear structural effect acquired a phi component")
    return float(diff.a)


# --- sections ---------------------------------------------------------------


def section_state(h: Harness) -> Dict[str, Any]:
    import numpy as np

    from toe.poincare_golden_11d import fold_poincare_11d_vector, unfold_poincare_11d_vector

    rng = np.random.default_rng(1517)
    errors = []
    for _ in range(20):
        v = rng.normal(size=11) * 0.1
        if np.linalg.norm(v) >= 0.95:
            v = v * (0.9 / np.linalg.norm(v))
        folded, passes = fold_poincare_11d_vector(v)
        recovered = unfold_poincare_11d_vector(folded, passes)
        errors.append(float(np.max(np.abs(np.asarray(v) - np.asarray(recovered)))))
    h.check(
        "state",
        "11D fold/unfold roundtrip max error < 1e-9",
        max(errors) < 1e-9,
        max_abs_error=max(errors),
        trials=len(errors),
    )
    return {
        "roundtrip_trials": len(errors),
        "max_abs_error": max(errors),
        "tolerance": 1e-9,
        "evidence_class": "MEASURED",
    }


def section_prediction(h: Harness) -> Dict[str, Any]:
    try:
        from sklearn.datasets import load_iris
    except ImportError:
        h.mark_unavailable("prediction", "scikit-learn is not installed; Iris cannot be loaded")
        return {"available": False, "reason": "scikit-learn not installed", "accuracy_mean": None}
    import numpy as np

    from kellogg.tensor_ml import exact_linear

    data = load_iris()
    X, y = data.data.astype(float), (data.target != 0).astype(int)
    rng = np.random.default_rng(1517)
    scores = []
    for _ in range(20):
        idx = rng.permutation(len(y))
        train, test = idx[:120], idx[120:]
        model = exact_linear()
        model.fit(X[train], y[train])
        scores.append(float((model.predict(X[test]) == y[test]).mean()))
    mean = float(np.mean(scores))
    h.check(
        "prediction",
        "binary setosa-vs-rest mean accuracy >= 0.95 over 20 splits",
        mean >= 0.95,
        mean=mean,
        min=min(scores),
    )
    return {
        "available": True,
        "task": "binary Iris setosa-vs-rest (3-class is unreachable)",
        "splits": 20,
        "accuracy_mean": mean,
        "accuracy_min": min(scores),
        "accuracy_max": max(scores),
        "claimed_in_repo": 0.9933,
        "evidence_class": "REPRODUCED (binary scope only)",
    }


def section_causality(h: Harness) -> Dict[str, Any]:
    confounded = StructuralCausalModel(_graph(("U", "X", 1.5), ("U", "Y", 1.2), ("X", "Y", 3.0)))
    g = confounded.graph
    sets = {
        "confounded_fork": identify_backdoor(g, "X", "Y"),
        "unconfounded": identify_backdoor(_graph(("X", "Y", 2.0)), "X", "Y"),
        "instrument_only": identify_backdoor(_graph(("Z", "X", 1), ("X", "Y", 1)), "X", "Y"),
        "latent_confounder": identify_backdoor(g, "X", "Y", observed={"X", "Y"}),
        "m_bias": identify_backdoor(
            _graph(("A", "X", 1), ("A", "M", 1), ("B", "M", 1), ("B", "Y", 1), ("X", "Y", 1)),
            "X",
            "Y",
        ),
    }
    h.check(
        "causality",
        "confounded_backdoor_set == ['U']",
        sets["confounded_fork"] == ["U"],
        got=sets["confounded_fork"],
    )
    h.check(
        "causality",
        "unconfounded_backdoor_set == []",
        sets["unconfounded"] == [],
        got=sets["unconfounded"],
    )
    h.check(
        "causality",
        "instrument is not adjusted for",
        sets["instrument_only"] == [],
        got=sets["instrument_only"],
    )
    h.check(
        "causality",
        "latent confounder is not identified (None)",
        sets["latent_confounder"] is None,
        got=sets["latent_confounder"],
    )
    h.check(
        "causality", "M-bias collider left unadjusted", sets["m_bias"] == [], got=sets["m_bias"]
    )

    truth = structural_truth(confounded, "X", "Y")
    samples = confounded.sample(50_000, seed=1517)
    est = estimate_causal_effect(samples, g, "X", "Y")
    h.check("causality", "adjusted effect available", est.available, reason=est.reason)
    abs_err = abs(est.adjusted_effect - truth)
    naive_err = abs(est.naive_effect - truth)
    h.check(
        "causality",
        "confounding measurably biases association (> 0.15)",
        naive_err > 0.15,
        naive=est.naive_effect,
        truth=truth,
    )
    h.check(
        "causality",
        f"adjusted_effect == truth within {EFFECT_TOLERANCE_SE} SE",
        abs_err <= EFFECT_TOLERANCE_SE * est.standard_error,
        adjusted=est.adjusted_effect,
        se=est.standard_error,
        truth=truth,
    )
    h.check(
        "causality",
        "adjusted error < naive error / 10",
        abs_err < naive_err / 10,
        adjusted_error=abs_err,
        naive_error=naive_err,
    )
    samples_latent = dict(samples)
    del samples_latent["U"]
    latent = estimate_causal_effect(samples_latent, g, "X", "Y")
    h.check(
        "causality",
        "unobserved confounder -> unavailable, no numeric estimate",
        (not latent.available) and latent.adjusted_effect is None,
        reason=latent.reason,
    )

    strat = _stratified_case()
    h.check(
        "causality",
        "stratified estimate on discrete confounding within 4 SE",
        strat["method"] == "stratification" and abs(strat["adjusted"] - 2.0) <= 4 * strat["se"],
        adjusted=strat["adjusted"],
        naive=strat["naive"],
        truth=2.0,
    )

    calibration = _calibration(h)
    return {
        "observational_effect": est.naive_effect,
        "adjusted_effect": est.adjusted_effect,
        "ground_truth_effect": truth,
        "ground_truth_source": "exact do() difference on the generating SCM (Q(phi))",
        "absolute_error": abs_err,
        "relative_error": abs_err / abs(truth),
        "observational_absolute_error": naive_err,
        "standard_error": est.standard_error,
        "tolerance": f"{EFFECT_TOLERANCE_SE} standard errors",
        "adjustment_set": est.adjustment_set,
        "method": est.method,
        "n_samples": est.n_samples,
        "provenance": est.provenance,
        "backdoor_sets": sets,
        "latent_confounder_estimate": latent.as_dict(),
        "stratified_binary_case": strat,
        "calibration": calibration,
        "evidence_class": "MEASURED on synthetic SCMs with a supplied DAG",
    }


def _stratified_case() -> Dict[str, Any]:
    rng = random.Random(9)
    cols: Dict[str, List[float]] = {"U": [], "X": [], "Y": []}
    for _ in range(20_000):
        u = 1.0 if rng.random() < 0.5 else 0.0
        x = 1.0 if rng.random() < (0.2 + 0.6 * u) else 0.0
        cols["U"].append(u)
        cols["X"].append(x)
        cols["Y"].append(2.0 * x + 3.0 * u + rng.gauss(0.0, 1.0))
    est = estimate_causal_effect(
        cols, _graph(("U", "X", 1), ("U", "Y", 1), ("X", "Y", 1)), "X", "Y"
    )
    return {
        "method": est.method,
        "adjusted": est.adjusted_effect,
        "naive": est.naive_effect,
        "se": est.standard_error,
        "truth": 2.0,
        "n": est.n_samples,
        "adjustment_set": est.adjustment_set,
    }


def _calibration(h: Harness) -> Dict[str, Any]:
    """Synthetic calibration of the estimator's reported uncertainty.

    Nothing is fitted: the estimator has no learnable parameter. The
    calibration seeds check that the OLS standard error is calibrated (z
    scores against truth); the held-out validation seeds, with independently
    drawn structural coefficients, are the acceptance set. Truth comes from
    the generating SCM's exact do(); it never reaches the estimator.
    """
    coef_rng = random.Random(COEFFICIENT_SEED)

    def run(seed: int) -> Dict[str, Any]:
        a, gamma = coef_rng.uniform(0.5, 2.0), coef_rng.uniform(0.5, 2.0)
        beta = coef_rng.uniform(-3.0, 3.0)
        scm = StructuralCausalModel(_graph(("U", "X", a), ("U", "Y", gamma), ("X", "Y", beta)))
        truth = structural_truth(scm, "X", "Y")
        est = estimate_causal_effect(scm.sample(20_000, seed=seed), scm.graph, "X", "Y")
        return {
            "seed": seed,
            "a": a,
            "gamma": gamma,
            "beta": beta,
            "truth": truth,
            "naive": est.naive_effect,
            "adjusted": est.adjusted_effect,
            "se": est.standard_error,
            "z": (est.adjusted_effect - truth) / est.standard_error,
        }

    cal = [run(s) for s in CALIBRATION_SEEDS]
    val = [run(s) for s in VALIDATION_SEEDS]

    def coverage(rows: List[Dict[str, Any]]) -> float:
        return sum(abs(r["z"]) <= 1.96 for r in rows) / len(rows)

    beats = all(abs(r["adjusted"] - r["truth"]) < abs(r["naive"] - r["truth"]) for r in val)
    max_z = max(abs(r["z"]) for r in val)
    h.check(
        "causality", "validation: every run within 4 SE of truth", max_z <= 4.0, max_abs_z=max_z
    )
    h.check(
        "causality",
        "validation: 95% interval coverage >= 0.80",
        coverage(val) >= 0.80,
        coverage=coverage(val),
    )
    h.check("causality", "validation: adjusted beats naive in every run", beats)
    return {
        "label": "SYNTHETIC CALIBRATION: labelled synthetic SCMs, not production evidence",
        "learned_parameters": None,
        "coefficient_draw_seed": COEFFICIENT_SEED,
        "calibration_seeds": CALIBRATION_SEEDS,
        "validation_seeds": VALIDATION_SEEDS,
        "calibration_coverage_95": coverage(cal),
        "validation_coverage_95": coverage(val),
        "validation_max_abs_z": max_z,
        "adjusted_beats_naive_in_all_validation_runs": beats,
        "calibration_runs": cal,
        "validation_runs": val,
    }


def _cf_scm() -> StructuralCausalModel:
    return StructuralCausalModel(
        _graph(("U", "X", 1.5), ("Z", "X", 0.5), ("U", "Y", 1.2), ("X", "Y", 3.0))
    )


NOISE = {"U": 0.2, "Z": -0.4, "X": 0.1, "Y": 0.3}


def section_intervention(h: Harness) -> Dict[str, Any]:
    scm = _cf_scm()
    result = intervene(scm, {"X": 2}, arithmetic=ARITHMETIC_EXACT)
    surgery = result["surgery"]
    y_exact = _zphi(result["exact_values"]["Y"])
    h.check(
        "intervention",
        "incoming edges before == [U->X, Z->X]",
        surgery["incoming_edges_before"]["X"] == [["U", "X", 1.5], ["Z", "X", 0.5]],
    )
    h.check(
        "intervention", "incoming edges after == []", surgery["incoming_edges_after"]["X"] == []
    )
    h.check(
        "intervention",
        "factual model keeps its edges",
        sorted(scm.graph.parents["X"]) == ["U", "Z"],
    )
    h.check("intervention", "E[Y|do(X=2)] == 6 exactly", y_exact == ZPhi(6, 0), got=str(y_exact))
    return {
        "target": "X",
        "value": 2,
        "incoming_edges_before": surgery["incoming_edges_before"],
        "incoming_edges_after": surgery["incoming_edges_after"],
        "edges_cut": surgery["edges_cut"],
        "expected_Y": 6.0,
        "actual_Y": result["values"]["Y"],
        "arithmetic": result["arithmetic"],
        "evidence_class": "MEASURED; EXACT in Q(phi)",
    }


def section_counterfactual(h: Harness) -> Dict[str, Any]:
    scm = _cf_scm()
    factual = scm.evaluate_all(exogenous=NOISE)
    value, diag = counterfactual_query(
        scm, None, "X", 2.0, observed=factual, observables={}, outcome_node="Y"
    )
    expected = 3.0 * 2.0 + 1.2 * (PHI * NOISE["U"]) + PHI * NOISE["Y"]
    error = abs(value - expected)
    h.check(
        "counterfactual",
        "counterfactual_result == expected within 1e-12",
        error <= COUNTERFACTUAL_TOLERANCE,
        expected=expected,
        actual=value,
    )
    action = diag["step_2_action"]
    h.check(
        "counterfactual",
        "edge_cut_behavior: X's parents cut in counterfactual world",
        action["incoming_edges_after"] == [] and action["factual_model_unchanged"],
    )
    shifted = scm.evaluate_all(exogenous={**NOISE, "Z": 3.0})
    y_shift = counterfactual_state(scm, {"X": 2.0}, shifted, ["Y"])["outcome_values"]["Y"]
    h.check(
        "counterfactual",
        "Z (reaches Y only via X) cannot move the counterfactual Y",
        abs(y_shift - value) <= COUNTERFACTUAL_TOLERANCE,
        with_z_shift=y_shift,
    )
    at3 = counterfactual_state(scm, {"X": 3.0}, factual, ["Y"])["outcome_values"]["Y"]
    h.check(
        "counterfactual",
        "negative control: wrong intervention value changes result",
        abs((at3 - value) - 3.0) <= 1e-12,
        delta=at3 - value,
    )
    same = counterfactual_state(scm, {"X": factual["X"]}, factual, ["Y"])["outcome_values"]["Y"]
    h.check(
        "counterfactual",
        "negative control: do(X = factual X) reproduces factual Y",
        abs(same - factual["Y"]) <= 1e-12,
    )
    unrelated = StructuralCausalModel(
        _graph(("U", "X", 1.5), ("U", "Y", 1.2), ("X", "Y", 3.0), ("W", "R", 4.0))
    )
    uf = unrelated.evaluate_all(exogenous={"U": 0.2, "X": 0.1, "Y": 0.3, "W": 1.0, "R": 0.5})
    ur = counterfactual_state(unrelated, {"W": 50.0}, uf, ["Y"])["outcome_values"]["Y"]
    h.check(
        "counterfactual",
        "negative control: intervention on unrelated node, no effect",
        ur == uf["Y"],
    )
    partial = {k: v for k, v in factual.items() if k != "U"}
    try:
        counterfactual_state(scm, {"X": 2.0}, partial, ["Y"])
        missing_ok, missing = False, None
    except CausalCapabilityUnavailable as exc:
        missing_ok, missing = "U" in exc.missing, exc.missing
    h.check(
        "counterfactual",
        "negative control: missing evidence fails closed",
        missing_ok,
        missing=missing,
    )
    return {
        "factual_state": factual,
        "abduced_exogenous": diag["step_1_abduction"]["estimated_exogenous"],
        "intervention_target": "X",
        "intervention_value": 2.0,
        "incoming_edges_before": action["incoming_edges_before"],
        "incoming_edges_after": action["incoming_edges_after"],
        "counterfactual_state": diag["step_3_prediction"]["counterfactual_state"],
        "expected_result": expected,
        "actual_result": value,
        "absolute_error": error,
        "tolerance": COUNTERFACTUAL_TOLERANCE,
        "negative_controls": [
            "wrong value",
            "consistency",
            "unrelated node",
            "missing evidence",
            "Z via cut edge",
        ],
        "api": "toe.causal_ladder.counterfactual_query -> counterfactual_state",
        "evidence_class": "MEASURED",
    }


def _explanation_scm(beta1: float = 3.0) -> StructuralCausalModel:
    return StructuralCausalModel(
        _graph(("X1", "Y", beta1), ("X2", "Y", 0.3), ("Z", "T", 2.0), ("W", "R", 1.0))
    )


def _background(w_scale: float = 1.0) -> List[Dict[str, float]]:
    rng = random.Random(77)
    return [
        {
            "X1": rng.gauss(0, 1),
            "X2": rng.gauss(0, 1),
            "Z": rng.gauss(0, 1),
            "W": 1e6 * w_scale + rng.gauss(0, 1e5 * w_scale),
        }
        for _ in range(24)
    ]


def _instance(w_scale: float = 1.0) -> Dict[str, float]:
    return {"X1": 2.0, "X2": 2.0, "Z": 2.0, "W": 3e6 * w_scale}


def _explain(
    target: str = "Y",
    beta1: float = 3.0,
    w_scale: float = 1.0,
    instance: Optional[Dict[str, Any]] = None,
    background: Any = None,
    model_id: Any = "use-digest",
):
    scm = _explanation_scm(beta1)
    return explain(
        structural_model(scm),
        instance if instance is not None else _instance(w_scale),
        target=target,
        background=background if background is not None else _background(w_scale),
        model_id=scm.digest() if model_id == "use-digest" else model_id,
        causal_parents=scm.graph.parents.get(target, []),
    )


def section_explanation(h: Harness) -> Dict[str, Any]:
    e = _explain()
    rank = e.ranking
    h.check("explanation", "1. X1 ranks above irrelevant Z", rank.index("X1") < rank.index("Z"))
    h.check(
        "explanation",
        "2. X1 ranks above huge irrelevant W",
        rank.index("X1") < rank.index("W"),
        w_attribution=e.attributions["W"],
    )
    unit_diffs = []
    for scale in (10.0, 1000.0):
        s = _explain(w_scale=scale)
        unit_diffs.append(max(abs(s.attributions[k] - e.attributions[k]) for k in e.attributions))
    h.check(
        "explanation",
        "3. rescaling W by 10x/1000x leaves attributions unchanged",
        max(unit_diffs) <= 1e-9,
        max_abs_change=max(unit_diffs),
    )
    rev = _explain(instance=dict(reversed(list(_instance().items()))))
    h.check(
        "explanation",
        "4. input order does not alter the explanation",
        rev.evidence_sha256 == e.evidence_sha256,
    )
    on_t = _explain("T")
    h.check(
        "explanation",
        "5. changing target changes explanation (T -> Z top)",
        on_t.ranking[0] == "Z" and on_t.attributions["X1"] == 0.0,
    )
    top = rank[0]
    abl = e.ablations[top]
    h.check(
        "explanation",
        "6. intervening on the top cause moves outcome as attributed",
        abl["counterfactual_prediction"] < e.factual_prediction
        and math.copysign(1, abl["delta"]) == math.copysign(1, e.attributions[top]),
        delta=abl["delta"],
    )
    no_w = _explain(
        instance={k: v for k, v in _instance().items() if k != "W"},
        background=[{k: v for k, v in r.items() if k != "W"} for r in _background()],
    )
    removal_change = max(abs(no_w.attributions[k] - e.attributions[k]) for k in no_w.attributions)
    h.check(
        "explanation",
        "7. removing W leaves prediction and attributions unchanged",
        abs(no_w.factual_prediction - e.factual_prediction) <= 1e-12 and removal_change <= 1e-12,
    )
    series = [_explain(beta1=b).attributions["X1"] for b in (1.0, 2.0, 3.0, 4.0)]
    h.check(
        "explanation",
        "8. attribution monotone in the true coefficient",
        all(b > a for a, b in zip(series, series[1:])),
        series=series,
    )
    hashes = {_explain().evidence_sha256 for _ in range(3)}
    h.check("explanation", "9. repeated execution is identical", len(hashes) == 1)
    missing_cases = {
        "missing input value": _explain(instance={**_instance(), "X1": None}),
        "no background": _explain(background=[]),
        "no model identifier": _explain(model_id=None),
        "target not produced": _explain(target="Q"),
    }
    all_refused = all((not c.available) and not c.attributions for c in missing_cases.values())
    h.check("explanation", "10. missing evidence -> unavailable, no attributions", all_refused)
    completeness = abs(
        sum(e.attributions.values()) - (e.factual_prediction - e.baseline_prediction)
    )
    h.check(
        "explanation",
        "attributions sum to factual - baseline",
        completeness <= 1e-9,
        residual=completeness,
    )
    return {
        "target": "Y",
        "ground_truth_ranking": ["X1", "X2"],
        "ground_truth_irrelevant": ["W", "Z"],
        "observed_ranking": rank,
        "attributions": e.attributions,
        "irrelevant_feature_rank": {"W": rank.index("W") + 1, "Z": rank.index("Z") + 1},
        "unit_invariance": {
            "max_abs_attribution_change": max(unit_diffs),
            "passed": max(unit_diffs) <= 1e-9,
        },
        "target_specificity": {"Y_top": rank[0], "T_top": on_t.ranking[0]},
        "faithfulness": {"top_cause_ablation": abl, "completeness_residual": completeness},
        "stability": {"distinct_evidence_hashes_over_3_runs": len(hashes)},
        "unavailable_cases": {k: v.reason for k, v in missing_cases.items()},
        "coefficient_monotonicity": series,
        "method": e.method,
        "model_evaluations": e.model_evaluations,
        "evidence_sha256": e.evidence_sha256,
        "evidence_class": "MEASURED (adversarial suite); exact enumeration limited to 12 inputs",
    }


def section_agreement(h: Harness) -> Dict[str, Any]:
    agree = evaluator_agreement({"a": [1.0, 2.0, 3.0], "b": [1.0, 2.0, 3.05]})
    mild = evaluator_agreement({"a": [1.0, 2.0, 3.0], "b": [2.0, 1.0, 3.0]})
    oppose = evaluator_agreement({"a": [1.0, 2.0, 3.0], "b": [-1.0, -2.0, -3.0]})
    single = evaluator_agreement({"a": [1.0, 2.0, 3.0]})
    h.check(
        "agreement",
        "metric drops as evaluators disagree",
        agree["agreement"] > mild["agreement"] > oppose["agreement"],
        agree=agree["agreement"],
        mild=mild["agreement"],
        oppose=oppose["agreement"],
    )
    h.check("agreement", "one evaluator -> None, not 1.0", single["agreement"] is None)
    bridge = TOEBridge()
    scalar = bridge.explain_causality({"a": 1.0, "b": 2.0}).model_agreement
    h.check("agreement", "bridge: identical scalar evaluators -> None (was 1.0)", scalar is None)
    return {
        "agreeing": agree["agreement"],
        "partially_disagreeing": mild["agreement"],
        "opposed": oppose["agreement"],
        "single_evaluator": single["agreement"],
        "bridge_scalar_factors": scalar,
        "metric": agree["metric"],
        "evidence_class": "MEASURED",
    }


def _policy_scm(xy: float = 5.0) -> StructuralCausalModel:
    return StructuralCausalModel(
        _graph(("S", "X", 0.5), ("S", "Y", 1.0), ("X", "Y", xy), ("X", "C", 1.0))
    )


def section_policy(h: Harness) -> Dict[str, Any]:
    state = {"S": 1.0, "X": 1.0, "C": 1.0, "Y": 4.0}
    candidates = {"A": {"X": 1.0}, "B": {"X": 2.0}, "C": {"X": 3.0}}
    budget = [Constraint("budget", "C", "<=", 2.5)]

    def run(scm: StructuralCausalModel):
        return decide(
            state,
            candidates,
            futures=counterfactual_futures(scm, arithmetic=ARITHMETIC_EXACT),
            objective=Objective("Y"),
            constraints=budget,
            model_id=scm.digest(),
        )

    base, perturbed = run(_policy_scm()), run(_policy_scm(xy=-1.0))
    values = {f["action"]: f["objective_value"] for f in base.futures}
    c = next(f for f in base.futures if f["action"] == "C")
    h.check(
        "action_policy",
        "futures A=4, B=9 computed by counterfactual",
        values["A"] == 4.0 and values["B"] == 9.0,
        futures=values,
    )
    h.check("action_policy", "selected == B", base.selected_action == "B")
    h.check(
        "action_policy",
        "C excluded for declared constraint",
        c["violated"] == ["budget"] and not c["admissible"],
    )
    h.check(
        "action_policy",
        "perturbed model (X->Y weight -1) selects A",
        perturbed.selected_action == "A",
    )
    return {
        "futures": base.futures,
        "selected_action": base.selected_action,
        "reason": base.reason,
        "constraints": [b.as_dict() for b in budget],
        "perturbation": "X->Y weight 5 -> -1",
        "perturbed_selected_action": perturbed.selected_action,
        "decision_sha256": base.decision_sha256,
        "evidence_class": "MEASURED",
    }


def section_provenance(h: Harness) -> Dict[str, Any]:
    ledger = ReceiptLedger(run_id="harness")
    e = _explain()
    receipt = ledger.issue(
        "explanation",
        inputs={"instance": _instance()},
        config={"model_id": _explanation_scm().digest(), "target": "Y"},
        output=e.as_dict(),
    )
    bridge = TOEBridge()
    bridge.decide(
        {"S": 1.0, "X": 1.0, "C": 1.0, "Y": 4.0},
        {"A": {"X": 1.0}, "B": {"X": 2.0}},
        model=_policy_scm(),
        objective={"target": "Y"},
    )
    action = bridge.receipts.records[0]
    results = {
        "replay_same_inputs": replay(receipt, lambda: _explain().as_dict())["ok"],
        "parameter_mutation_detected": not replay(receipt, lambda: _explain(beta1=3.1).as_dict())[
            "ok"
        ],
        "config_mutation_detected": not verify_binding(
            receipt, config={"model_id": _explanation_scm(3.1).digest(), "target": "Y"}
        )["ok"],
        "state_mutation_detected": not verify_binding(
            receipt, inputs={"instance": {**_instance(), "X1": 2.5}}
        )["ok"],
    }
    receipt.output["attributions"]["W"] = 99.0
    results["explanation_mutation_detected"] = not ledger.verify()["ok"]
    receipt.output["attributions"]["W"] = e.attributions["W"]
    original = action.output["selected_action"]
    action.output["selected_action"] = "A" if original != "A" else "B"
    results["action_mutation_detected"] = not bridge.verify_receipts()["ok"]
    action.output["selected_action"] = original
    ledger.issue("note", inputs={}, config={}, output={"n": 1})
    results["reordering_detected"] = not verify_chain(list(reversed(ledger.records)))["ok"]
    results["intact_ledger_verifies"] = ledger.verify()["ok"] and bridge.verify_receipts()["ok"]
    for name, ok in results.items():
        h.check("provenance", name, ok)
    return {**results, "receipt_format": receipt.format, "evidence_class": "MEASURED"}


def section_exact(h: Harness) -> Dict[str, Any]:
    scm = StructuralCausalModel(_graph(("X", "Y", 2)))
    y = scm.evaluate_exact(interventions={"X": 1}, exogenous={"Y": 1})["Y"]
    h.check(
        "exact_arithmetic", "exact path: Y = 2 + phi structurally (ZPhi(2, 1))", y == ZPhi(2, 1)
    )
    cf = _cf_scm()
    noise = {k: Fraction(v).limit_denominator(1000) for k, v in NOISE.items()}
    exact = cf.evaluate_exact(exogenous=noise)
    floats = cf.evaluate_all(exogenous={k: float(v) for k, v in noise.items()})
    worst = max(abs(floats[n] - (float(v.a) + float(v.b) * PHI)) for n, v in exact.items())
    h.check(
        "exact_arithmetic",
        "float path agrees with exact path within 1e-12",
        worst <= 1e-12,
        max_abs_diff=worst,
    )
    return {
        "float_phi": "(1 + math.sqrt(5)) / 2 -> NUMERICALLY VERIFIED",
        "exact_phi": "lucas.algebra.ZPhi with Fraction coefficients -> EXACT",
        "exact_Y": {"a": str(y.a), "b": str(y.b)},
        "float_vs_exact_max_abs_diff": worst,
        "tolerance": 1e-12,
    }


def section_bridge(h: Harness) -> Dict[str, Any]:
    edges = [
        ("U", "X", 1.5),
        ("Z", "X", 0.5),
        ("U", "Y", 1.2),
        ("X", "Y", 3.0),
        ("X", "C", 1.0),
        ("C", "Y", 0.0),
    ]
    scm = StructuralCausalModel(CausalGraph.from_edges(edges))
    task = {
        "graph": edges,
        "state": scm.evaluate_all(exogenous={**NOISE, "C": 0.0}),
        "treatment": "X",
        "outcome": "Y",
        "samples": scm.sample(4_000, seed=11),
        "intervention": {"X": 2.0},
        "candidates": {"A": {"X": 1.0}, "B": {"X": 2.0}, "C": {"X": 3.0}},
        "objective": {"target": "Y", "sense": "maximize"},
        "constraints": [{"name": "budget", "variable": "C", "op": "<=", "bound": 2.5}],
    }
    bridge = TOEBridge()
    started = time.perf_counter()
    out = bridge.reason(task)
    elapsed = time.perf_counter() - started
    h.check(
        "bridge",
        "TOEBridge.reason: every section available",
        out["available"],
        unavailable=out["unavailable"],
    )
    h.check(
        "bridge",
        "reason selects B with receipts verified",
        out["action_policy"]["selected_action"] == "B" and out["provenance"]["ledger"]["ok"],
    )
    without = bridge.reason({k: v for k, v in task.items() if k != "samples"})
    h.check(
        "bridge",
        "missing samples -> envelope unavailable, no invented effect",
        (not without["available"])
        and "adjusted_effect" not in without["causal_analysis"]["effect"],
    )
    status = bridge.status()
    h.check(
        "bridge",
        "status declares causal discovery NOT ESTABLISHED",
        status["capability_evidence"]["causal_discovery"].startswith("NOT ESTABLISHED"),
    )
    predict = bridge.predict(bytes(range(64)))
    h.check(
        "bridge", "predict() envelope still available for downstream adapters", predict["available"]
    )
    return {
        "api": "toe.bridge.TOEBridge.reason(task)",
        "elapsed_s": elapsed,
        "sections": [k for k in out if k not in ("available", "unavailable")],
        "receipts": out["provenance"]["receipts"],
        "capability_evidence": dict(CAPABILITY_EVIDENCE),
    }


_DOMAIN = re.compile(
    r"\bStratum\b|(?i:\b(nonces?|extranonce\w*|hashrate|mining|miners?|bitcoin|sha256d"
    r"|wallets?|viabtc|nicehash|braiins|ckpool|share_\w+|pool_\w+|mining\.\w+)\b)"
)


def section_domain(h: Harness) -> Dict[str, Any]:
    modules = ["causal_ladder.py", "explanation.py", "agreement.py", "policy.py", "receipts.py"]
    hits = {
        m: len(_DOMAIN.findall((ROOT / "toe" / m).read_text(encoding="utf-8"))) for m in modules
    }
    control = len(
        _DOMAIN.findall(
            (ROOT / "toe" / "intelligences" / "counterfactual.py").read_text(encoding="utf-8")
        )
    )
    h.check(
        "domain", "TOE reasoning core has no mining vocabulary", not any(hits.values()), hits=hits
    )
    h.check("domain", "detector control: mining module is flagged", control > 0)
    return {
        "modules": hits,
        "control_hits_toe_intelligences_counterfactual": control,
        "note": "toe/intelligences/* remains mining-specific and is outside this core",
    }


def run_pytest(h: Harness) -> Dict[str, Any]:
    def one(files: List[str], cwd: Path) -> Dict[str, Any]:
        with tempfile.TemporaryDirectory() as tmp:
            xml = Path(tmp) / "junit.xml"
            cmd = [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                f"--junitxml={xml}",
                *files,
            ]
            proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
            record: Dict[str, Any] = {
                "command": "python -m pytest -q " + " ".join(files),
                "cwd": cwd.relative_to(ROOT).as_posix(),
                "exit_code": proc.returncode,
            }
            if not xml.exists():
                return {
                    **record,
                    "passed": None,
                    "failed": None,
                    "skipped": None,
                    "error": (proc.stdout + proc.stderr)[-800:],
                }
            suite = ET.parse(xml).getroot()
            suite = suite if suite.tag == "testsuite" else suite.find("testsuite")
            total = int(suite.get("tests", 0))
            failed = int(suite.get("failures", 0)) + int(suite.get("errors", 0))
            skipped = int(suite.get("skipped", 0))
            return {
                **record,
                "passed": total - failed - skipped,
                "failed": failed,
                "skipped": skipped,
            }

    runs = [
        one(PYTEST_FILES, ROOT),
        one(PLATFORM_PYTEST_FILES, ROOT / "mla1517_platform_v3.4" / "python"),
    ]
    for r in runs:
        h.check(
            "tests",
            f"pytest {r['cwd']}: no failures",
            r.get("failed") == 0 and bool(r.get("passed")),
            n_passed=r.get("passed"),
            n_failed=r.get("failed"),
            n_skipped=r.get("skipped"),
        )
    totals = {
        k: (sum(r[k] for r in runs) if all(r.get(k) is not None for r in runs) else None)
        for k in ("passed", "failed", "skipped")
    }
    return {**totals, "runs": runs}


def _git(*args: str) -> Optional[str]:
    try:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:
        return None


CLAIM_BOUNDARIES = [
    "Causal structure is SUPPLIED to TOE. Causal discovery is NOT ESTABLISHED: "
    "infer_causal_graph is a correlation heuristic and is labelled so.",
    "Adjusted-effect recovery is MEASURED on synthetic linear-Gaussian and discrete SCMs with "
    "a supplied DAG. It is not established for misspecified graphs, nonlinear outcome "
    "models under linear adjustment, or unobserved confounding (reported unavailable).",
    "Counterfactuals assume the supplied SCM, additive phi-scaled noise and full evidence for "
    "the nodes the outcome depends on; missing evidence fails closed.",
    "phi: the float path is NUMERICALLY VERIFIED against the exact Q(phi) path; only "
    "evaluate_exact and arithmetic='exact_q_phi' are EXACT.",
    "Explanation is faithful to the supplied model (interventional Shapley, exact "
    "enumeration, at most 12 inputs); it explains the model, not the world beyond it.",
    "explain_causality remains a descriptive magnitude ranking and is labelled not causal.",
    "Action policy selects among supplied candidates by modelled futures; it does not "
    "generate actions and it is only as good as the supplied model.",
    "Prediction evidence is the binary Iris setosa-vs-rest task only.",
    "Synthetic calibration has no learned parameters and is not production evidence.",
]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--report", type=Path, help="write the JSON benchmark here")
    parser.add_argument("--pytest", action="store_true", help="also run the TOE test files")
    parser.add_argument("--only", help="comma-separated sections to run (default: all)")
    args = parser.parse_args(argv)

    h = Harness()
    sections: Dict[str, Callable[[Harness], Dict[str, Any]]] = {
        "state": section_state,
        "prediction": section_prediction,
        "causality": section_causality,
        "intervention": section_intervention,
        "counterfactual": section_counterfactual,
        "explanation": section_explanation,
        "agreement": section_agreement,
        "action_policy": section_policy,
        "provenance": section_provenance,
        "exact_arithmetic": section_exact,
        "bridge": section_bridge,
        "domain_generality": section_domain,
    }
    if args.only:
        wanted = [s.strip() for s in args.only.split(",") if s.strip()]
        unknown = [s for s in wanted if s not in sections]
        if unknown:
            parser.error(f"unknown section(s): {unknown}")
        sections = {k: v for k, v in sections.items() if k in wanted}
    report: Dict[str, Any] = {}
    for name, fn in sections.items():
        print(f"\n=== {name} ===")
        try:
            report[name] = fn(h)
        except Exception as exc:  # a crashed section is a failure, never skipped
            h.check(
                name, "section ran without crashing", False, error=f"{type(exc).__name__}: {exc}"
            )
            report[name] = {"available": False, "error": traceback.format_exc()}
    tests: Dict[str, Any] = {
        "passed": None,
        "failed": None,
        "skipped": None,
        "reason": "not run (pass --pytest)",
    }
    if args.pytest:
        print("\n=== tests ===")
        try:
            tests = run_pytest(h)
        except Exception as exc:
            h.check("tests", "test run completed", False, error=f"{type(exc).__name__}: {exc}")
            tests = {"passed": None, "failed": None, "skipped": None, "error": str(exc)}

    failed, unavailable = h.failed, h.unavailable
    status = "FAIL" if failed else ("INCOMPLETE" if unavailable else "PASS")
    print("\n=== SUMMARY ===")
    print(f"  checks passed : {len(h.checks) - len(failed)}")
    print(f"  checks failed : {len(failed)}")
    for c in failed:
        print(f"    FAILED {c['section']}: {c['name']}")
    for u in unavailable:
        print(f"    UNAVAILABLE {u['section']}: {u['reason']}")
    print(f"  STATUS        : {status}")

    if args.report:
        import numpy

        payload = {
            "schema": "toe.elevation_benchmark/v1",
            "commit": _git("rev-parse", "HEAD"),
            "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
            "worktree_clean": _git("status", "--porcelain", "--", "toe", "scripts", "tests") == "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "environment": {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "numpy": numpy.__version__,
            },
            **report,
            "checks": h.checks,
            "tests": tests,
            "unavailable": unavailable,
            "claim_boundaries": CLAIM_BOUNDARIES,
            "summary": {
                "status": status,
                "checks_passed": len(h.checks) - len(failed),
                "checks_failed": len(failed),
            },
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(payload, indent=2, sort_keys=False, allow_nan=False, default=str) + "\n",
            encoding="utf-8",
        )
        print(f"  report        : {args.report}")
    return 1 if failed else (2 if unavailable else 0)


if __name__ == "__main__":
    sys.exit(main())
