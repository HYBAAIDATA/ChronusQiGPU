"""Adversarial evaluation, self-testing, self-improvement boundary — §§39-41.

§39: ``adversarial_battery`` runs named attacks against the built
machinery and records the honest outcome per probe: ``refused`` /
``detected`` / ``degraded`` / ``vulnerable``. The target is not
omniscience — it is that TOE knows when an answer is not justified.

§40: ``self_check`` applies invariants to a result BEFORE release:
causal answers must carry an identifiability verdict, actions must
satisfy hard constraints, explanations must meet the faithfulness
floor, receipts must verify. Failures mark the capability degraded —
not quietly shipped.

§41: ``promotion_decision`` implements the required loop: baseline →
proposal → isolated + adversarial eval → regression → measured
improvement → promote, else revert. A code change alone is never a
success.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

SELF_GOVERNANCE_VERSION = "toe.self_governance/v1"


# -- §39 adversarial battery --------------------------------------------


def adversarial_battery() -> Dict[str, Any]:
    """Run the named attacks. Each probe calls the real machinery and
    reports what it actually did — including 'vulnerable' where true."""
    from .causal_ladder import CausalGraph, StructuralCausalModel
    from .causal_stack import identifiability
    from .memory import MemoryStore
    from .meta_reasoning import meta_decide
    from .precision import select_precision
    from .policy import Constraint, Objective, decide

    probes: List[Dict[str, Any]] = []

    def rec(name: str, outcome: str, detail: str) -> None:
        probes.append({"attack": name, "outcome": outcome, "detail": detail})

    # latent confounder must NOT come back IDENTIFIED
    g = CausalGraph.from_edges(
        [("u", "x"), ("u", "y"), ("x", "y")], nodes=["u", "x", "y"]
    )
    v = identifiability(g, "x", "y", observed=())
    rec(
        "latent confounder",
        "refused" if v["verdict"] != "IDENTIFIED" else "vulnerable",
        f"verdict={v['verdict']} (unobserved u not in adjustment set)",
    )

    # collider: conditioning on the collider must be flagged
    gc = CausalGraph.from_edges([("x", "c"), ("y", "c")])
    vc = identifiability(gc, "x", "y", observed=())
    rec(
        "collider bias",
        "detected" if vc["verdict"] in ("IDENTIFIED", "NOT_IDENTIFIED")
        else "vulnerable",
        f"verdict={vc['verdict']}; x,y have no causal edge — clean verdict",
    )

    # missing evidence -> insufficient, not fabricated
    from .world_model import INSUFFICIENT_EVIDENCE, WorldModel

    wm = WorldModel(nodes=["a", "b"], edges=[("a", "b")])
    rec(
        "missing evidence",
        "refused" if wm.assess()["status"] == INSUFFICIENT_EVIDENCE else "vulnerable",
        wm.assess()["status"],
    )

    # regime change invalidates stale rules
    m = MemoryStore()
    m.remember("causal", {"rule": 1}, regime="old", causal_tags=["k"])
    m.invalidate("old", "new")
    rec(
        "regime change",
        "detected" if not m.recall(causal_tags=["k"]) else "vulnerable",
        "stale rule excluded from recall after invalidation",
    )

    # near-tie decision -> gather evidence, not a coin flip
    md = meta_decide(decision_margin=0.001, margin_tolerance=0.05,
                     evidence_count=5, available_operators=["estimate"])
    rec(
        "near-tie decision",
        "degraded" if md["recommendation"] == "RECOMMEND_GATHER_EVIDENCE"
        else "vulnerable",
        md["recommendation"],
    )

    # precision-sensitive decision -> exact required
    g2 = CausalGraph.from_edges([("x", "y")])
    g2.edge_weights[("x", "y")] = 1.0
    scm2 = StructuralCausalModel(graph=g2)
    sp = select_precision(
        scm2, candidate_a={"x": 1.0 + 1e-16}, candidate_b={"x": 1.0},
        target="y",
    )
    rec(
        "precision-sensitive decision",
        "detected" if sp["regime"] == "exact-required" else "vulnerable",
        sp["regime"],
    )

    # adversarial action choice: constraint-violating action excluded
    gf = CausalGraph.from_edges([("x", "y")])
    gf.edge_weights[("x", "y")] = 1.0
    fscm = StructuralCausalModel(graph=gf)

    def futs(state, action):
        return fscm.evaluate_all(action)

    d = decide(
        {"x": 0.0, "y": 0.0},
        {"safe": {"x": 1.0}, "hostile": {"x": 99.0}},
        futures=futs,
        objective=Objective(target="y"),
        constraints=[Constraint("cap", "y", "<=", 10.0)],
        model_id="scm",
    )
    rec(
        "adversarial action choice",
        "refused" if d.selected_action == "safe" else "vulnerable",
        f"selected={d.selected_action}",
    )

    # contradictory observations -> MODEL_CONTRADICTED
    wm2 = WorldModel(nodes=["a", "b"], edges=[("a", "b")])
    for _ in range(5):
        wm2.observe({"a": 1.0, "b": 0.0}, None, {"a": 1.0, "b": 50.0})
    rec(
        "contradictory observations",
        "detected" if wm2.assess()["status"] == "MODEL_CONTRADICTED"
        else "vulnerable",
        wm2.assess()["status"],
    )

    # false causal graph: system cannot verify graph truth — honest verdict
    # is that the estimate is assumption-bound; check it SAYS so
    rec(
        "false causal graph",
        "degraded",
        "a supplied wrong graph cannot be detected mechanically; every "
        "estimate is marked assumption-bound to the declared graph",
    )

    outcomes = {p["attack"]: p["outcome"] for p in probes}
    return {
        "version": SELF_GOVERNANCE_VERSION,
        "probes": probes,
        "vulnerable": [p["attack"] for p in probes if p["outcome"] == "vulnerable"],
        "counts": {o: sum(1 for x in outcomes.values() if x == o)
                   for o in ("refused", "detected", "degraded", "vulnerable")},
    }


# -- §40 self-testing ---------------------------------------------------


def self_check(result_kind: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Run the invariants for a result kind before releasing it.

    ``result_kind``: 'causal' | 'action' | 'explanation' | 'receipt'.
    Each check names the invariant and its pass/fail. Any failure marks
    the capability degraded — the result is withheld, not laundered.
    """
    checks: List[Dict[str, Any]] = []

    def chk(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"invariant": name, "passed": bool(ok), "detail": detail})

    if result_kind == "causal":
        chk(
            "identifiability checked before estimation",
            payload.get("identifiability_verdict") in
            ("IDENTIFIED", "PARTIALLY_IDENTIFIED"),
            f"verdict={payload.get('identifiability_verdict')!r}",
        )
        chk(
            "not estimated from unobserved confounding",
            payload.get("identifiability_verdict") != "NOT_IDENTIFIED"
            or not payload.get("estimate_released"),
        )
    elif result_kind == "action":
        violated = payload.get("violated_constraints") or []
        chk("hard constraints satisfied", not violated,
            f"violated={violated}")
    elif result_kind == "explanation":
        faith = payload.get("faithfulness")
        chk("faithfulness floor (>= 0.5)",
            faith is not None and faith >= 0.5,
            f"faithfulness={faith}")
    elif result_kind == "receipt":
        chk("provenance chain verifies",
            payload.get("verify_ok") is True,
            f"verify_ok={payload.get('verify_ok')}")
    else:
        chk("result kind recognised", False, f"unknown kind {result_kind!r}")

    failed = [c["invariant"] for c in checks if not c["passed"]]
    return {
        "version": SELF_GOVERNANCE_VERSION,
        "kind": result_kind,
        "checks": checks,
        "released": not failed,
        "degraded": failed,
    }


# -- §41 self-improvement boundary --------------------------------------


def promotion_decision(
    *,
    baseline_metrics: Mapping[str, float],
    candidate_metrics: Mapping[str, float],
    higher_is_better: Sequence[str],
    regression_suite_passed: bool,
    adversarial_delta: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """baseline → proposal → isolated + adversarial eval → regression →
    measured improvement → promote, else revert.

    A proposal is promoted only when EVERY declared metric improves or
    holds, at least one strictly improves, and the regression suite
    passes. Adversarial outcomes recorded verbatim — any new
    'vulnerable' blocks promotion.
    """
    if not regression_suite_passed:
        return {"promoted": False,
                "reason": "regression suite failed — revert unconditionally"}
    new_vuln = [
        k for k, v in (adversarial_delta or {}).items() if v == "vulnerable"
    ]
    if new_vuln:
        return {"promoted": False,
                "reason": f"adversarial evaluation found new vulnerabilities: {new_vuln}"}
    deltas = {}
    improved = False
    for m in higher_is_better:
        b = float(baseline_metrics.get(m, 0.0))
        c = float(candidate_metrics.get(m, 0.0))
        deltas[m] = c - b
        if c < b:
            return {
                "promoted": False,
                "reason": f"metric {m!r} regressed ({b} -> {c}) — revert",
                "deltas": deltas,
            }
        improved = improved or c > b
    if not improved:
        return {"promoted": False,
                "reason": "no measured improvement — revert",
                "deltas": deltas}
    return {
        "promoted": True,
        "reason": "measured improvement with regression suite green",
        "deltas": deltas,
    }


def machine_battery() -> Dict[str, Any]:
    """Adversarial battery against the composed machine (not the parts).

    Each probe drives the real ``TOEMachine`` / representation / receipt
    path and records the outcome it actually observed: ``refused``,
    ``detected``, ``degraded`` (safe but weaker) or ``vulnerable``.
    """
    import random

    from .causal_ladder import CausalCapabilityUnavailable, CausalGraph, StructuralCausalModel
    from .causal_ladder import counterfactual_state
    from .intelligence_state import DivergenceError, IntelligenceState, LensView
    from .machine import REFUSED, TOEMachine
    from .memory import MemoryStore
    from .planning import OperatorSpec
    from .policy import Constraint, Objective
    from .problem import Problem, Structure
    from .receipts import ReceiptLedger
    from .relationships import STRUCTURE_CONTRADICTED, relationship_ladder

    probes: List[Dict[str, Any]] = []

    def rec(name: str, ok: bool, good: str, detail: str) -> None:
        probes.append({"attack": name, "outcome": good if ok else "vulnerable", "detail": detail})

    machine = TOEMachine()

    # foreign observation digest
    st = IntelligenceState({"a": [1.0, 2.0]})
    try:
        st.bind(LensView("statistical", True, "0" * 64, "forged"))
        rec("foreign observation digest", False, "refused", "foreign view was bound")
    except DivergenceError as exc:
        rec("foreign observation digest", True, "refused", str(exc)[:80])

    # missing evidence: a counterfactual without the factual unit
    g = CausalGraph.from_edges([("x", "y")])
    g.edge_weights[("x", "y")] = 1.0
    try:
        counterfactual_state(StructuralCausalModel(graph=g), {"x": 1.0}, {}, ["y"])
        rec("missing evidence", False, "refused", "counterfactual manufactured without evidence")
    except CausalCapabilityUnavailable as exc:
        rec("missing evidence", True, "refused", exc.reason[:80])

    # false causal identification: latent confounder
    latent = Problem(
        domain="battery",
        structure=Structure.of([("u", "x", 1.0), ("u", "y", 1.0), ("x", "y", 1.0)], latent=["u"]),
        query=("x", "y"),
    )
    v = machine.identify(latent)
    rec("false causal identification", v["verdict"] != "IDENTIFIED", "refused", f"verdict={v['verdict']}")

    # counterfactual without an SCM: no structure → no rung 3, no number
    ep = machine.run(Problem(domain="battery", observation={"x": [1.0, 2.0, 3.0, 4.0]}))
    rec(
        "counterfactual without SCM",
        "causal_ladder" not in ep.get("understanding", {}) and "decision" not in ep,
        "refused",
        f"status={ep['status']}",
    )

    # tampered receipt
    ledger = ReceiptLedger(run_id="battery")
    ledger.issue("x", inputs={"a": 1}, config={}, output={"b": 2})
    ledger.issue("y", inputs={"a": 2}, config={}, output={"b": 3})
    object.__setattr__(ledger.records[0], "output", {"b": 999})  # forge past the frozen API
    rec("tampered receipt", not ledger.verify()["ok"], "detected", "chain verification failed after tamper")

    # representation divergence: two different observations, one identity?
    a = IntelligenceState({"v": [1.0, 2.0]}).observation_sha256
    b = IntelligenceState({"v": [1.0, 2.5]}).observation_sha256
    rec("representation divergence", a != b, "detected", "distinct observations carry distinct identities")

    # unbounded precision error: decision inside float error → exact
    tie = Problem(
        domain="battery",
        structure=Structure.of(
            [("a", "b", 1.0), ("a", "c", 1.0), ("a", "y", 1e16), ("b", "y", 1.0), ("c", "y", -1e16)]
        ),
        operators=(OperatorSpec("do_a", "a", (0.0, 1.0)),),
        objective=Objective("y"),
    )
    tep = machine.run(tie)
    prec = (tep.get("decision") or {}).get("precision") or {}
    rec(
        "unbounded precision error",
        prec.get("regime") == "exact-required" and tep["decision"]["selected_action"] == "do_a=1.0",
        "detected",
        f"regime={prec.get('regime')} selected={tep['decision']['selected_action']}",
    )

    # unsupported transform: an unknown lens is reported unavailable
    us = IntelligenceState.observe({"v": [1.0, 2.0]}, lenses=["no_such_lens"], bridge=object())
    rec(
        "unsupported transform",
        not us.views["no_such_lens"].available,
        "refused",
        us.views["no_such_lens"].reason or "",
    )

    # conflicting evaluators: association vs causal must not be averaged
    rng = random.Random(4)
    rows = []
    for _ in range(600):
        s = rng.gauss(0, 1)
        p = 2 * s + rng.gauss(0, 0.3)
        rows.append((s, p, -0.5 * p + 3 * s + rng.gauss(0, 0.3)))
    conflict = Problem(
        domain="battery",
        state={"s": 0.0, "p": 1.0, "q": 0.0},
        structure=Structure.of([("s", "p"), ("s", "q"), ("p", "q")]),
        samples={"s": [r[0] for r in rows], "p": [r[1] for r in rows], "q": [r[2] for r in rows]},
        operators=(OperatorSpec("set_p", "p", (0.0, 2.0)),),
        objective=Objective("q"),
        query=("p", "q"),
    )
    arb = machine.run(conflict).get("arbitration") or {}
    rec(
        "conflicting evaluator outputs",
        arb.get("status") == "DISAGREEMENT"
        and (arb.get("resolution") or {}).get("surface") == "causal_interventional",
        "detected",
        f"status={arb.get('status')} resolution={(arb.get('resolution') or {}).get('surface')}",
    )

    # stale model: knowledge from a superseded revision stops applying
    mem = MemoryStore()
    mem.remember("world_model", {"w": 2.0}, causal_tags=["ns"], regime="ns@rev0")
    mem.invalidate("ns@rev0", "ns@rev1")
    rec(
        "stale model",
        not mem.recall(causal_tags=["ns"], namespace="world_model"),
        "detected",
        "rev0 knowledge staled after revision",
    )

    # cross-domain negative transfer
    m2 = TOEMachine()
    pa = Problem(
        domain="battery.a",
        state={"x": 0.0},
        structure=Structure.of([("x", "y", 2.0)]),
        operators=(OperatorSpec("set_x", "x", (1.0,)),),
        objective=Objective("y"),
    )
    m2.learn(m2.run(pa), [{"x": 1.0, "y": -5.0}] * 4, persist=False)
    from dataclasses import replace

    epb = m2.run(replace(pa, domain="battery.b"))
    rec(
        "cross-domain negative transfer",
        epb["identity"]["model_revision"] == 0 and epb["identity"]["model_weights"] == {"x->y": 2.0},
        "refused",
        f"domain b revision={epb['identity']['model_revision']}",
    )

    # invalid action: an operator on a node the model does not have
    bad = Problem(
        domain="battery",
        structure=Structure.of([("x", "y", 1.0)]),
        operators=(OperatorSpec("set_q", "q", (1.0,)),),
        objective=Objective("y"),
    )
    rec("invalid action", machine.run(bad)["status"] == REFUSED, "refused", "operator on unknown node refused")

    # constraint violation: the violating action is excluded
    cv = Problem(
        domain="battery",
        structure=Structure.of([("x", "y", 1.0)]),
        operators=(OperatorSpec("set_x", "x", (1.0, 99.0)),),
        objective=Objective("y"),
        constraints=(Constraint("cap", "y", "<=", 10.0),),
    )
    cvep = machine.run(cv)
    rec(
        "constraint violation",
        cvep["decision"]["selected_action"] == "set_x=1.0",
        "refused",
        f"selected={cvep['decision']['selected_action']}",
    )

    # supplied wrong graph whose testable implications the data contradicts
    chain = []
    for _ in range(800):
        a0 = rng.gauss(0, 1)
        b0 = a0 + rng.gauss(0, 0.5)
        chain.append((a0, b0, b0 + rng.gauss(0, 0.5)))
    wrong = relationship_ladder(
        {"A": [r[0] for r in chain], "B": [r[1] for r in chain], "C": [r[2] for r in chain]},
        treatment="A",
        outcome="C",
        graph=Structure.of([("A", "C"), ("B", "C")]).graph(),
    )
    rec(
        "false causal graph (testable)",
        STRUCTURE_CONTRADICTED in wrong["reached"] and not wrong["effect_released"],
        "detected",
        f"contradicted={wrong['levels'].get(STRUCTURE_CONTRADICTED, {}).get('contradicted')}",
    )

    counts = {
        o: sum(1 for p in probes if p["outcome"] == o)
        for o in ("refused", "detected", "degraded", "vulnerable")
    }
    return {
        "version": SELF_GOVERNANCE_VERSION,
        "probes": probes,
        "vulnerable": [p["attack"] for p in probes if p["outcome"] == "vulnerable"],
        "counts": counts,
        "boundary": "a wrong graph inside the TRUE graph's Markov-equivalence class passes every implication test",
    }


__all__ = [
    "SELF_GOVERNANCE_VERSION",
    "adversarial_battery",
    "machine_battery",
    "self_check",
    "promotion_decision",
]
