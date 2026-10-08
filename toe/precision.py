"""Adaptive precision + exactness as a resource — §§30-31.

§30: ``select_precision`` picks ``float64`` vs ``exact`` (Q(phi) via
``evaluate_exact`` over KELLOGG's ``QPhi``) from the decision's
sensitivity: margin larger than a declared float error bound → the cheap
path cannot flip the answer; margin inside the bound → exact arithmetic is
REQUIRED, and the exact branch decides the comparison in the field itself
(exact sign of the exact difference), never by projecting both sides to
float first. Every downgrade carries its bound — nothing silently degrades.

§31: ``float_error_bound`` is a real bound propagated through the linear
structural equations (2*eps per multiply-add pair, 3*eps on the
``phi*u`` noise term, plus propagated parent bounds). ``measure_exactness``
runs both arithmetics and records whether the difference changes an
ordering, a classification, or a constraint — and says so honestly when it
does not.
"""

from __future__ import annotations

import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .causal_ladder import PHI, StructuralCausalModel, zphi_as_dict, zphi_sign, zphi_to_float

PRECISION_VERSION = "toe.precision/v2"
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
    parents' own bounds amplified by ``|w_ij|``. The noise term is
    ``phi*u_i`` exactly as ``structural_equation`` evaluates it: float
    ``phi`` is itself rounded (half an ulp), then multiplied and added —
    conservatively ``3*eps*|phi*u_i|``.
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
            noise_term = float(ex[node]) * PHI
            linear += noise_term
            err += 3.0 * _EPS * abs(noise_term)
        values[node] = linear
        bounds[node] = err
    return bounds


def _ordering(sign: int) -> str:
    return "a>b" if sign > 0 else "a<b" if sign < 0 else "tie"


def select_precision(
    scm: StructuralCausalModel,
    *,
    candidate_a: Mapping[str, float],
    candidate_b: Mapping[str, float],
    target: str,
    exogenous: Optional[Mapping[str, float]] = None,
) -> Dict[str, Any]:
    """Choose the arithmetic regime by decision sensitivity.

    The decision is "does ``candidate_a`` beat ``candidate_b`` on
    ``target``?". If the float margin exceeds the summed error bound (plus
    the rounding of the subtraction itself), float64 cannot change it — the
    cheap path is admissible and its bound is returned. Otherwise exact
    evaluation is required and the ordering is the exact sign of the exact
    difference in Q(phi).
    """
    ex = dict(exogenous or {})
    a = scm.evaluate_all(dict(candidate_a), dict(ex))[target]
    b = scm.evaluate_all(dict(candidate_b), dict(ex))[target]
    margin = a - b
    bound = (
        float_error_bound(scm, candidate_a, ex)[target]
        + float_error_bound(scm, candidate_b, ex)[target]
        + _EPS * abs(margin)
    )
    if abs(margin) > bound:
        return {
            "regime": "float64",
            "margin": margin,
            "error_bound": bound,
            "float_ordering": _ordering((margin > 0) - (margin < 0)),
            "justification": (
                f"|margin| {abs(margin):.3g} > bound {bound:.3g}: float64 "
                "cannot flip the decision; downgrade admissible with bound"
            ),
        }
    exact_diff = scm.evaluate_exact(candidate_a, ex)[target] - scm.evaluate_exact(
        candidate_b, ex
    )[target]
    exact_sign = zphi_sign(exact_diff)
    float_sign = (margin > 0) - (margin < 0)
    return {
        "regime": "exact-required",
        "margin": margin,
        "exact_margin": zphi_to_float(exact_diff),
        "exact_margin_exact": zphi_as_dict(exact_diff),
        "exact_ordering": _ordering(exact_sign),
        "float_ordering": _ordering(float_sign),
        "error_bound": bound,
        "float_flips": float_sign != exact_sign,
        "justification": (
            f"|margin| {abs(margin):.3g} <= bound {bound:.3g}: the decision "
            "is inside float error; decided by the exact sign in Q(phi)"
        ),
    }


_CMP = {
    "<=": lambda s: s <= 0,
    ">=": lambda s: s >= 0,
    "<": lambda s: s < 0,
    ">": lambda s: s > 0,
}


def measure_exactness(
    scm: StructuralCausalModel,
    cases: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Run float vs exact on each case; report where the difference
    changes the conclusion — and where it does not.

    ``cases``: ``{interventions_a, interventions_b, target}`` — ordering
    plus optional ``constraint`` (``(node, op, value)``) to test
    constraint-satisfaction flips. The exact side compares in Q(phi): the
    sign of ``exact_a - exact_b`` (or ``exact_value - bound``), so an
    exact difference below float resolution is still seen.
    """
    out: List[Dict[str, Any]] = []
    for case in cases:
        ta = case["target"]
        fa = scm.evaluate_all(dict(case["a"]))[ta]
        fb = scm.evaluate_all(dict(case["b"]))[ta]
        exact_a = scm.evaluate_exact(case["a"])
        exact_diff = exact_a[ta] - scm.evaluate_exact(case["b"])[ta]
        float_sign = (fa > fb) - (fa < fb)
        exact_sign = zphi_sign(exact_diff)
        ordering_changed = float_sign != exact_sign
        constraint_changed = False
        if "constraint" in case:
            node, op, val = case["constraint"]
            v_f = scm.evaluate_all(dict(case["a"]))[node]
            sat = _CMP[op]
            float_sat = sat((v_f > val) - (v_f < val))
            exact_sat = sat(zphi_sign(exact_a[node] - val))
            constraint_changed = float_sat != exact_sat
        out.append(
            {
                "target": ta,
                "float_margin": fa - fb,
                "exact_margin": zphi_to_float(exact_diff),
                "exact_ordering": _ordering(exact_sign),
                "float_ordering": _ordering(float_sign),
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
