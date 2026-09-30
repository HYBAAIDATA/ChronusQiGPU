"""Adaptive precision + exactness as a resource — §§30-31.

§30: ``select_precision`` picks ``float64`` vs ``exact`` (Q(phi) ZPhi via
``evaluate_exact``) from the decision's sensitivity: margin larger than
a declared float error bound → the cheap path cannot flip the answer;
margin inside the bound → exact/high-precision is REQUIRED. Every
downgrade carries its bound — nothing silently degrades.

§31: ``float_error_bound`` is a real bound propagated through the linear
structural equations (2*eps per multiply-add pair plus propagated parent
bounds). ``measure_exactness`` runs both arithmetics and records whether
the difference changes an ordering, a classification, or a constraint —
and says so honestly when it does not.
"""

from __future__ import annotations

import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .causal_ladder import StructuralCausalModel, zphi_to_float

PRECISION_VERSION = "toe.precision/v1"
_EPS = sys.float_info.epsilon


def float_error_bound(
    scm: StructuralCausalModel,
    interventions: Optional[Mapping[str, float]] = None,
    exogenous: Optional[Mapping[str, float]] = None,
) -> Dict[str, float]:
    """Declared worst-case float64 error per node, propagated in
    topological order.

    For ``x_i = Σ_j w_ij x_j + phi*u_i``: each product contributes at
    most ``|w_ij x_j| * eps`` and each addition another ``eps`` of the
    running magnitude — conservatively ``2*eps*Σ|w_ij x_j|`` — plus the
    parents' own bounds amplified by ``|w_ij|``.
    """
    iv = dict(interventions or {})
    ex = dict(exogenous or {})
    values: Dict[str, float] = {}
    bounds: Dict[str, float] = {}
    for node in scm.graph.topological_order():
        if node in iv:
            values[node] = float(iv[node])
            bounds[node] = 0.0
            continue
        linear = 0.0
        err = 0.0
        for p in scm.graph.parents.get(node, []):
            w = float(scm.graph.edge_weights.get((p, node), 0.0))
            linear += w * values[p]
            err += abs(w) * bounds[p] + 2.0 * _EPS * abs(w * values[p])
        if node in ex:
            linear += float(ex[node])
            err += _EPS * abs(float(ex[node]))
        values[node] = linear
        bounds[node] = err
    return bounds


def select_precision(
    scm: StructuralCausalModel,
    *,
    candidate_a: Mapping[str, float],
    candidate_b: Mapping[str, float],
    target: str,
) -> Dict[str, Any]:
    """Choose the arithmetic regime by decision sensitivity.

    The decision is "does ``candidate_a`` beat ``candidate_b`` on
    ``target``?". If the float margin exceeds the summed error bound,
    float64 cannot change it — the cheap path is admissible and its
    bound is returned. Otherwise exact evaluation is required.
    """
    a = scm.evaluate_all(dict(candidate_a))[target]
    b = scm.evaluate_all(dict(candidate_b))[target]
    margin = a - b
    bound = (
        float_error_bound(scm, candidate_a)[target]
        + float_error_bound(scm, candidate_b)[target]
    )
    if abs(margin) > bound:
        return {
            "regime": "float64",
            "margin": margin,
            "error_bound": bound,
            "justification": (
                f"|margin| {abs(margin):.3g} > bound {bound:.3g}: float64 "
                "cannot flip the decision; downgrade admissible with bound"
            ),
        }
    ea = zphi_to_float(scm.evaluate_exact(candidate_a)[target])
    eb = zphi_to_float(scm.evaluate_exact(candidate_b)[target])
    return {
        "regime": "exact-required",
        "margin": margin,
        "exact_margin": ea - eb,
        "error_bound": bound,
        "float_flips": (margin > 0) != (ea > eb),
        "justification": (
            f"|margin| {abs(margin):.3g} <= bound {bound:.3g}: the decision "
            "is inside float error; exact arithmetic required"
        ),
    }


def measure_exactness(
    scm: StructuralCausalModel,
    cases: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Run float vs exact on each case; report where the difference
    changes the conclusion — and where it does not.

    ``cases``: ``{interventions_a, interventions_b, target}`` — ordering
    plus optional ``constraint`` (``(node, op, value)``) to test
    constraint-satisfaction flips.
    """
    out: List[Dict[str, Any]] = []
    for case in cases:
        ta = case["target"]
        fa = scm.evaluate_all(dict(case["a"]))[ta]
        fb = scm.evaluate_all(dict(case["b"]))[ta]
        ea = zphi_to_float(scm.evaluate_exact(case["a"])[ta])
        eb = zphi_to_float(scm.evaluate_exact(case["b"])[ta])
        ordering_changed = (fa > fb) != (ea > eb)
        constraint_changed = False
        if "constraint" in case:
            node, op, val = case["constraint"]
            v_f = scm.evaluate_all(dict(case["a"]))[node]
            v_e = zphi_to_float(scm.evaluate_exact(case["a"])[node])
            sat = {
                "<=": lambda x: x <= val,
                ">=": lambda x: x >= val,
                "<": lambda x: x < val,
                ">": lambda x: x > val,
            }[op]
            constraint_changed = sat(v_f) != sat(v_e)
        out.append(
            {
                "target": ta,
                "float_margin": fa - fb,
                "exact_margin": ea - eb,
                "ordering_changed": ordering_changed,
                "constraint_changed": constraint_changed,
                "exactness_matters": ordering_changed or constraint_changed,
            }
        )
    return {
        "version": PRECISION_VERSION,
        "cases": out,
        "matters_fraction": (
            sum(r["exactness_matters"] for r in out) / len(out) if out else 0.0
        ),
    }


__all__ = [
    "PRECISION_VERSION",
    "float_error_bound",
    "select_precision",
    "measure_exactness",
]
