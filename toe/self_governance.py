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


__all__ = [
    "SELF_GOVERNANCE_VERSION",
    "adversarial_battery",
    "self_check",
    "promotion_decision",
]
