"""Computational decision explanation + contrast + falsification — §§13-15.

No language generation: every field is reconstructed from the decision's
own computation (the evaluated futures, constraint verdicts, objective
values) plus the causal machinery (paths through the supplied graph,
counterfactual worlds, exact propagation).

* ``explain_decision`` — why this action: target, active causes (the
  intervention's own variables), causal paths to the objective target,
  counterfactual delta vs the runner-up, constraints, rejected
  alternatives with their reasons, uncertainty, provenance.

* ``explain_contrastive`` — why A rather than B: the two predicted
  futures, the objective delta, the constraint delta (what B violates
  that A passes), the causal contribution difference, uncertainty.

* ``falsify_explanation`` — every important explanation is testable:
  for each input attributed as relevant, re-run the model with that
  input ablated and check the outcome changes as the attribution claims.
  Faithfulness is a measured fraction, not prose plausibility.

* ``falsify_decision`` — the decisive factor is the intervention value;
  set it to the rejected action's value and the decision must change as
  claimed (objective order must reverse).
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from .causal_ladder import StructuralCausalModel
from .causal_stack import _all_simple_paths
from .policy import PolicyDecision

DECISION_EXPLANATION_VERSION = "toe.decision_explanation/v1"


def _record(decision: PolicyDecision, action: str) -> Optional[Dict[str, Any]]:
    for r in decision.futures:
        if r.get("action") == action:
            return r
    return None


def explain_decision(
    decision: PolicyDecision,
    *,
    scm: Optional[StructuralCausalModel] = None,
    uncertainty: Optional[Mapping[str, Any]] = None,
    state: Optional[Mapping[str, float]] = None,
) -> Dict[str, Any]:
    """The decision's computational anatomy — every field traceable."""
    base: Dict[str, Any] = {
        "version": DECISION_EXPLANATION_VERSION,
        "available": decision.available,
        "reason": decision.reason,
        "objective": decision.objective,
        "constraints": decision.constraints_applied,
        "provenance": {
            "decision_sha256": decision.decision_sha256,
            "model_id": decision.model_id,
            "state_sha256": decision.state_sha256,
        },
    }
    if not decision.available:
        return base

    selected = _record(decision, decision.selected_action or "")
    if selected is None:
        base["available"] = False
        base["reason"] = "selected action missing from evaluated futures"
        return base

    target = decision.objective.get("target")
    intervention = selected.get("intervention", {})

    causal_paths: Dict[str, Any] = {}
    if scm is not None and target:
        cut = scm.mutilate(intervention)[0].graph
        causal_paths = {
            node: _all_simple_paths(cut, node, target) for node in intervention
        }

    admissible = [r for r in decision.futures if r.get("admissible")]
    runner_up = next(
        (r for r in admissible if r["action"] != decision.selected_action), None
    )
    rejected = [
        {
            "action": r["action"],
            "reason": r.get("excluded_because"),
            "objective_value": r.get("objective_value"),
            "violated_constraints": r.get("violated", []),
        }
        for r in decision.futures
        if r["action"] != decision.selected_action
    ]
    cf_delta = None
    if runner_up and target:
        a = (selected.get("future") or {}).get(target)
        b = (runner_up.get("future") or {}).get(target)
        if a is not None and b is not None:
            cf_delta = {
                "selected_future": a,
                "runner_up": runner_up["action"],
                "runner_up_future": b,
                "objective_delta": a - b,
            }

    base.update(
        selected_action=decision.selected_action,
        intervention=intervention,
        target=target,
        state_sha256=decision.state_sha256,
        active_causes=sorted(intervention),
        causal_paths_to_target=causal_paths,
        counterfactual_delta=cf_delta,
        margin=decision.margin,
        tie_broken=decision.tie_broken,
        rejected_alternatives=rejected,
        uncertainty=dict(uncertainty) if uncertainty else None,
    )
    return base


def explain_contrastive(
    decision: PolicyDecision,
    rejected_action: str,
    *,
    scm: Optional[StructuralCausalModel] = None,
) -> Dict[str, Any]:
    """Why A rather than B — the computational difference between them."""
    out: Dict[str, Any] = {
        "version": DECISION_EXPLANATION_VERSION,
        "available": False,
        "selected": decision.selected_action,
        "rejected": rejected_action,
    }
    if not decision.available:
        out["reason"] = "no decision to contrast"
        return out
    a = _record(decision, decision.selected_action or "")
    b = _record(decision, rejected_action)
    if a is None or b is None:
        out["reason"] = "one or both actions absent from evaluated futures"
        return out
    target = decision.objective.get("target")
    fa = a.get("future") or {}
    fb = b.get("future") or {}
    objective_delta = None
    if fa.get(target) is not None and fb.get(target) is not None:
        objective_delta = fa[target] - fb[target]
    only_b_violates = sorted(set(b.get("violated", [])) - set(a.get("violated", [])))
    only_a_violates = sorted(set(a.get("violated", [])) - set(b.get("violated", [])))
    decisive = None
    if b.get("excluded_because"):
        decisive = f"{rejected_action} inadmissible: {b['excluded_because']}"
    elif objective_delta is not None:
        decisive = (
            f"objective '{target}': {fa[target]} vs {fb[target]} "
            f"(delta {objective_delta})"
        )
    contribution_diff: Dict[str, Any] = {}
    if scm is not None and target:
        for label, rec in (("selected", a), ("rejected", b)):
            cut = scm.mutilate(rec.get("intervention", {}))[0].graph
            contribution_diff[label] = {
                "intervention": rec.get("intervention"),
                "paths": {
                    n: _all_simple_paths(cut, n, target)
                    for n in (rec.get("intervention") or {})
                },
            }
    out.update(
        available=True,
        decisive_factor=decisive,
        future_A=fa,
        future_B=fb,
        objective_delta=objective_delta,
        constraint_delta={
            "only_rejected_violates": only_b_violates,
            "only_selected_violates": only_a_violates,
        },
        causal_contribution=contribution_diff,
        reason=None,
    )
    return out


def falsify_explanation(
    model: Any,
    instance: Mapping[str, float],
    background: Mapping[str, float],
    attributions: Mapping[str, float],
    target: str,
    *,
    tolerance: float = 1e-9,
) -> Dict[str, Any]:
    """Test the claimed attributions by intervention.

    For each input claimed relevant, ablate it to its background value and
    require the outcome to move in the direction the attribution asserts.
    ``faithfulness`` = fraction of verified claims.
    """
    checks: List[Dict[str, Any]] = []
    verified = 0
    for name, phi in sorted(attributions.items()):
        if abs(phi) <= tolerance:
            continue
        ablated = dict(instance)
        if name not in background:
            checks.append(
                {"input": name, "verifiable": False, "reason": "no background value"}
            )
            continue
        ablated[name] = float(background[name])
        try:
            before = model(dict(instance))
            after = model(ablated)
            v_before = float(before[target] if isinstance(before, Mapping) else before)
            v_after = float(after[target] if isinstance(after, Mapping) else after)
        except Exception as exc:
            checks.append(
                {"input": name, "verifiable": False, "reason": f"model error: {exc}"}
            )
            continue
        actual_delta = v_before - v_after
        claimed = phi > 0
        observed = actual_delta > 0
        ok = claimed == observed
        verified += ok
        checks.append(
            {
                "input": name,
                "verifiable": True,
                "claimed_direction": "raises" if claimed else "lowers",
                "observed_delta_on_removal": actual_delta,
                "falsified": not ok,
            }
        )
    testable = [c for c in checks if c.get("verifiable")]
    return {
        "version": DECISION_EXPLANATION_VERSION,
        "claims_tested": len(testable),
        "claims_verified": verified,
        "faithfulness": verified / len(testable) if testable else None,
        "checks": checks,
    }


def falsify_decision(
    decision: PolicyDecision,
    *,
    futures_fn: Any,
    state: Mapping[str, float],
) -> Dict[str, Any]:
    """The decisive intervention must decide: swap it, the choice flips.

    For each admissible runner-up, re-evaluate the futures function with
    the rejected action's intervention on the same state; the objective
    ordering must reproduce the recorded margin direction, else the
    claimed decisive factor is falsified.
    """
    out: Dict[str, Any] = {"version": DECISION_EXPLANATION_VERSION, "available": False}
    if not decision.available or not decision.selected_action:
        out["reason"] = "no decision to falsify"
        return out
    selected = _record(decision, decision.selected_action)
    admissible_others = [
        r for r in decision.futures if r.get("admissible") and r["action"] != decision.selected_action
    ]
    target = decision.objective.get("target")
    sense = decision.objective.get("sense", "maximize")
    checks: List[Dict[str, Any]] = []
    falsified = 0
    for other in admissible_others:
        try:
            fut = futures_fn(state, other["intervention"])
        except Exception as exc:
            checks.append(
                {"versus": other["action"], "verifiable": False, "reason": str(exc)}
            )
            continue
        va = (selected.get("future") or {}).get(target)
        vb = fut.get(target) if isinstance(fut, Mapping) else None
        if va is None or vb is None:
            checks.append(
                {"versus": other["action"], "verifiable": False, "reason": "target absent"}
            )
            continue
        still_better = va > vb if sense == "maximize" else va < vb
        falsified += not still_better
        checks.append(
            {
                "versus": other["action"],
                "verifiable": True,
                "selected_future": va,
                "recomputed_rejected_future": vb,
                "ordering_reproduced": still_better,
            }
        )
    testable = [c for c in checks if c.get("verifiable")]
    out.update(
        available=True,
        checks=checks,
        comparisons=len(testable),
        falsified=falsified,
        faithful=falsified == 0 if testable else None,
    )
    return out


__all__ = [
    "DECISION_EXPLANATION_VERSION",
    "explain_decision",
    "explain_contrastive",
    "falsify_explanation",
    "falsify_decision",
]
