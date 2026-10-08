"""Relationship reasoning — five things that must never be conflated.

=========================  ==================================================
ASSOCIATION                statistical dependence measured in samples
                           (Pearson r, regression slope = E[Y|X] per unit)
STRUCTURE_DISCOVERED       an observational *equivalence class* of DAGs —
                           never presented as a unique causal graph
STRUCTURE_SUPPLIED         a caller-declared causal graph — an ASSUMPTION
STRUCTURE_CONTRADICTED     the supplied graph's testable implications fail
                           in the data (local Markov conditional
                           independencies, Fisher-z with Bonferroni)
EFFECT_IDENTIFIED          the causal effect is identified from observed
                           variables under the (supplied) structure;
                           only then is an estimate released
EFFECT_NOT_IDENTIFIED      refusal — no number is manufactured
=========================  ==================================================

The implication test is the strongest *mechanical* check on a supplied
graph available from observational data, and it is one-sided: a graph in
the same Markov-equivalence class as the truth passes it while still being
wrong about direction. That boundary is reported on every result.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .causal_ladder import CausalGraph, estimate_causal_effect
from .causal_stack import (
    IDENTIFIED,
    NOT_IDENTIFIED,
    _corr_matrix,
    _partial_corr,
    discover_structures,
    identifiability,
)

RELATIONSHIPS_VERSION = "toe.relationships/v1"

ASSOCIATION = "ASSOCIATION"
STRUCTURE_DISCOVERED = "STRUCTURE_DISCOVERED"
STRUCTURE_SUPPLIED = "STRUCTURE_SUPPLIED"
STRUCTURE_CONTRADICTED = "STRUCTURE_CONTRADICTED"
EFFECT_IDENTIFIED = "EFFECT_IDENTIFIED"
EFFECT_NOT_IDENTIFIED = "EFFECT_NOT_IDENTIFIED"

_BOUNDARY = (
    "a supplied graph that passes the implication test is consistent with "
    "the data, not proven: Markov-equivalent graphs share every testable "
    "implication and latent confounding can mimic them"
)


def association(samples: Mapping[str, Sequence[float]], x: str, y: str) -> Dict[str, Any]:
    """Rung 1: Pearson r and the OLS slope of ``y`` on ``x`` (E[Y|X] per unit)."""
    xs = [float(v) for v in samples.get(x, ())]
    ys = [float(v) for v in samples.get(y, ())]
    n = min(len(xs), len(ys))
    if n < 3:
        return {"available": False, "reason": f"need >= 3 paired samples, got {n}"}
    xs, ys = xs[:n], ys[:n]
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((a - mx) ** 2 for a in xs)
    syy = sum((b - my) ** 2 for b in ys)
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    if sxx <= 0 or syy <= 0:
        return {"available": False, "reason": "a variable is constant in the sample"}
    return {
        "available": True,
        "rung": 1,
        "x": x,
        "y": y,
        "n": n,
        "pearson_r": sxy / math.sqrt(sxx * syy),
        "slope_E_y_given_x": sxy / sxx,
        "meaning": "observational dependence only; not an effect",
    }


def _fisher_p(r: float, n: int, k: int) -> Optional[float]:
    dof = n - k - 3
    if dof <= 0 or not -1.0 < r < 1.0:
        return None
    z = 0.5 * math.log((1.0 + r) / (1.0 - r)) * math.sqrt(dof)
    return math.erfc(abs(z) / math.sqrt(2.0))


def implied_independencies(
    graph: CausalGraph, observed: Iterable[str]
) -> List[Tuple[str, str, Tuple[str, ...]]]:
    """Local Markov implications ``v ⫫ w | pa(v)`` restricted to observed
    variables (every term of the statement must be observed)."""
    obs = set(observed)
    out: List[Tuple[str, str, Tuple[str, ...]]] = []
    for v in sorted(graph.nodes):
        pa = set(graph.parents.get(v, []))
        if v not in obs or not pa <= obs:
            continue
        excluded = pa | graph.descendants(v) | {v}
        for w in sorted(obs - excluded):
            key = tuple(sorted((v, w)))
            cond = tuple(sorted(pa))
            if (key[0], key[1], cond) not in out:
                out.append((key[0], key[1], cond))
    return out


def check_supplied_structure(
    graph: CausalGraph,
    samples: Mapping[str, Sequence[float]],
    *,
    alpha: float = 0.01,
) -> Dict[str, Any]:
    """Test a supplied DAG's local Markov implications against the data.

    Gaussian partial correlation + Fisher z, Bonferroni over the tested
    implications. ``contradicted`` lists implications rejected at the
    corrected level — evidence that the supplied structure (or its
    no-latent-confounder assumption) is wrong.
    """
    names, r, n = _corr_matrix({k: list(v) for k, v in samples.items()})
    idx = {nm: i for i, nm in enumerate(names)}
    tests = [
        t
        for t in implied_independencies(graph, names)
        if all(x in idx for x in (t[0], t[1], *t[2]))
    ]
    if not tests:
        return {
            "available": False,
            "reason": "the supplied graph implies no testable independence among observed variables",
            "boundary": _BOUNDARY,
        }
    level = alpha / len(tests)
    results = []
    for a, b, cond in tests:
        pc = _partial_corr(r, idx[a], idx[b], [idx[c] for c in cond])
        p = _fisher_p(pc, n, len(cond)) if pc is not None else None
        results.append(
            {
                "independence": f"{a} _||_ {b} | {{{', '.join(cond)}}}",
                "partial_correlation": pc,
                "p_value": p,
                "rejected": p is not None and p < level,
            }
        )
    contradicted = [t["independence"] for t in results if t["rejected"]]
    return {
        "available": True,
        "n_samples": n,
        "alpha": alpha,
        "bonferroni_level": level,
        "tests": results,
        "contradicted": contradicted,
        "consistent": not contradicted,
        "boundary": _BOUNDARY,
    }


def relationship_ladder(
    samples: Optional[Mapping[str, Sequence[float]]],
    *,
    treatment: Optional[str] = None,
    outcome: Optional[str] = None,
    graph: Optional[CausalGraph] = None,
    observed: Optional[Iterable[str]] = None,
    alpha: float = 0.01,
) -> Dict[str, Any]:
    """Climb the ladder as far as the evidence allows — and say where it stops.

    Every level reports what it is. The effect estimate is released only on
    EFFECT_IDENTIFIED; otherwise the refusal and its reason are the answer.
    """
    levels: Dict[str, Any] = {}
    reached: List[str] = []
    data = {k: list(v) for k, v in (samples or {}).items()}

    if data and treatment and outcome:
        assoc = association(data, treatment, outcome)
        levels[ASSOCIATION] = assoc
        if assoc.get("available"):
            reached.append(ASSOCIATION)

    if graph is None:
        if data:
            disc = discover_structures(data)
            levels[STRUCTURE_DISCOVERED] = {
                "available": disc.get("available", False),
                "equivalence_class_size": disc.get("equivalence_class_size"),
                "directed_edges": disc.get("directed_edges"),
                "undirected_edges": disc.get("undirected_edges"),
                "unique_graph": disc.get("equivalence_class_size") == 1,
                "reason": disc.get("reason"),
                "meaning": "a set of observationally equivalent DAGs, not a causal graph",
            }
            if disc.get("available"):
                reached.append(STRUCTURE_DISCOVERED)
        levels[EFFECT_NOT_IDENTIFIED] = {
            "reason": "no causal structure supplied; a discovered equivalence "
            "class does not identify a unique effect and is not promoted to one",
        }
        return {
            "version": RELATIONSHIPS_VERSION,
            "levels": levels,
            "reached": reached,
            "highest": reached[-1] if reached else None,
            "effect_released": False,
            "boundary": _BOUNDARY,
        }

    levels[STRUCTURE_SUPPLIED] = {
        "graph_sha256": graph.digest(),
        "n_nodes": len(graph.nodes),
        "meaning": "caller-declared structure: an assumption, not a finding",
    }
    reached.append(STRUCTURE_SUPPLIED)
    if data:
        check = check_supplied_structure(graph, data, alpha=alpha)
        levels["IMPLICATION_TEST"] = check
        if check.get("available") and check["contradicted"]:
            levels[STRUCTURE_CONTRADICTED] = {
                "contradicted": check["contradicted"],
                "consequence": "effect estimates under this graph are withheld",
            }
            reached.append(STRUCTURE_CONTRADICTED)

    effect_released = False
    if treatment and outcome:
        verdict = identifiability(graph, treatment, outcome, observed=observed)
        if STRUCTURE_CONTRADICTED in reached:
            levels[EFFECT_NOT_IDENTIFIED] = {
                "verdict": verdict["verdict"],
                "reason": "supplied structure contradicted by the data",
            }
        elif verdict["verdict"] == IDENTIFIED:
            estimate = None
            if data and treatment in data and outcome in data:
                est = estimate_causal_effect(data, graph, treatment, outcome, observed=observed)
                estimate = est.as_dict()
            levels[EFFECT_IDENTIFIED] = {
                "verdict": verdict["verdict"],
                "strategy": verdict.get("strategy"),
                "adjustment_set": verdict.get("adjustment_set"),
                "estimate": estimate,
            }
            reached.append(EFFECT_IDENTIFIED)
            effect_released = estimate is not None and bool(estimate.get("available"))
        else:
            levels[EFFECT_NOT_IDENTIFIED] = {
                "verdict": verdict["verdict"],
                "reason": verdict.get("reason"),
                "refused": True,
            }
    return {
        "version": RELATIONSHIPS_VERSION,
        "levels": levels,
        "reached": reached,
        "highest": reached[-1] if reached else None,
        "effect_released": effect_released,
        "not_identified_verdict": NOT_IDENTIFIED,
        "boundary": _BOUNDARY,
    }


__all__ = [
    "RELATIONSHIPS_VERSION",
    "ASSOCIATION",
    "STRUCTURE_DISCOVERED",
    "STRUCTURE_SUPPLIED",
    "STRUCTURE_CONTRADICTED",
    "EFFECT_IDENTIFIED",
    "EFFECT_NOT_IDENTIFIED",
    "association",
    "implied_independencies",
    "relationship_ladder",
    "check_supplied_structure",
]
