"""Meta-reasoning, value of information, compute-aware routing — §§27-29.

§27: ``meta_decide`` is a bounded controller over EXISTING TOE operators.
Its decisions are tied to measured computation/evidence — margins,
identifiability verdicts, evidence counts — never to vibes. It can
recommend gathering more evidence before acting, and it can refuse to
route when nothing measurable justifies a choice.

§28: ``value_of_information`` answers "is another observation worth
obtaining?" by testing whether the uncertain parameter, varied over its
declared plausible range, can change the selected action. No invented
probabilities: the answer is worst-case over the band.

§29: ``choose_path`` prefers the cheaper reasoning path among those that
meet the declared correctness requirement. Work is measured where it
genuinely exists (operation counts), not estimated vibes.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Mapping, Optional, Sequence

META_VERSION = "toe.meta_reasoning/v1"

RECOMMEND_GATHER_EVIDENCE = "RECOMMEND_GATHER_EVIDENCE"
ACT_NOW = "ACT_NOW"
NO_ROUTE = "NO_ROUTE"


def meta_decide(
    *,
    identifiability: Optional[str] = None,
    decision_margin: Optional[float] = None,
    margin_tolerance: float = 0.05,
    evidence_count: int = 0,
    min_evidence: int = 3,
    available_operators: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Bounded meta-controller over measured signals.

    Routes to a reasoning operator by rule, each rule citing its
    measured inputs:

    - effect NOT_IDENTIFIED and observations < min_evidence →
      RECOMMEND_GATHER_EVIDENCE (more data is the only path)
    - decision margin inside ``margin_tolerance`` →
      RECOMMEND_GATHER_EVIDENCE (a flip is plausible)
    - otherwise → ACT_NOW on the first declared operator
    """
    signals = {
        "identifiability": identifiability,
        "decision_margin": decision_margin,
        "evidence_count": evidence_count,
        "margin_tolerance": margin_tolerance,
        "min_evidence": min_evidence,
    }
    if identifiability == "NOT_IDENTIFIED" and evidence_count < min_evidence:
        return {
            "recommendation": RECOMMEND_GATHER_EVIDENCE,
            "reason": (
                f"effect not identified and only {evidence_count} "
                "observation(s): answering now would be assumption-bound"
            ),
            "signals": signals,
        }
    if decision_margin is not None and abs(decision_margin) < margin_tolerance:
        return {
            "recommendation": RECOMMEND_GATHER_EVIDENCE,
            "reason": (
                f"decision margin {decision_margin:.4g} inside tolerance "
                f"{margin_tolerance}: near-tie can flip"
            ),
            "signals": signals,
        }
    ops = list(available_operators or [])
    if not ops:
        return {
            "recommendation": NO_ROUTE,
            "reason": "no declared operator to route to",
            "signals": signals,
        }
    return {
        "recommendation": ACT_NOW,
        "operator": ops[0],
        "reason": "measured signals justify acting on the declared operator",
        "signals": signals,
    }


def value_of_information(
    *,
    parameter: str,
    plausible_range: Sequence[float],
    decision_fn: Callable[[float], str],
) -> Dict[str, Any]:
    """Would resolving ``parameter`` change the decision?

    ``decision_fn(p)`` returns the selected action under parameter value
    ``p``; we evaluate it across the declared plausible range. If the
    selection is invariant the evidence is worthless — do not request
    it. Any flip means the observation could change the decision.
    """
    outcomes: Dict[float, str] = {}
    for p in plausible_range:
        outcomes[float(p)] = decision_fn(float(p))
    distinct = sorted(set(outcomes.values()))
    flips = [
        (a, b)
        for a, b in zip(plausible_range, list(plausible_range)[1:])
        if outcomes[float(a)] != outcomes[float(b)]
    ]
    return {
        "parameter": parameter,
        "decision_invariant": len(distinct) == 1,
        "selected_actions": distinct,
        "flip_boundaries": len(flips),
        "recommend_evidence": len(distinct) > 1,
        "reason": (
            "request the observation: the selection changes across the "
            "plausible range"
            if len(distinct) > 1
            else "do not request: the decision is invariant to this parameter"
        ),
    }


def choose_path(
    paths: Sequence[Mapping[str, Any]],
    *,
    correctness_required: str = "exact-answer",
) -> Dict[str, Any]:
    """Prefer the cheapest reasoning path meeting the requirement.

    ``paths``: declared alternatives with ``name``, ``cost`` (measured
    units — op counts, latency), ``correctness`` (which requirement tier
    it satisfies: ``exact-answer`` > ``bounded-approximation`` >
    ``heuristic``), and optional ``evidence`` description. The cheapest
    path at the required tier wins; ties keep declaration order.
    """
    tier_rank = {"exact-answer": 2, "bounded-approximation": 1, "heuristic": 0}
    need = tier_rank[correctness_required]
    adequate = [
        p for p in paths if tier_rank.get(p["correctness"], -1) >= need
    ]
    if not adequate:
        return {
            "selected": None,
            "reason": (
                f"no path meets the {correctness_required!r} requirement; "
                "refusing to trade away required correctness"
            ),
            "evaluated": list(paths),
        }
    chosen = min(adequate, key=lambda p: p["cost"])
    cheaper_rejected = [
        p["name"] for p in paths if p["cost"] < chosen["cost"] and p not in adequate
    ]
    return {
        "selected": chosen["name"],
        "cost": chosen["cost"],
        "reason": (
            f"cheapest adequate path; rejected cheaper-but-inadequate: "
            f"{cheaper_rejected or 'none'}"
        ),
        "evaluated": list(paths),
    }


__all__ = [
    "META_VERSION",
    "RECOMMEND_GATHER_EVIDENCE",
    "ACT_NOW",
    "NO_ROUTE",
    "meta_decide",
    "value_of_information",
    "choose_path",
]
