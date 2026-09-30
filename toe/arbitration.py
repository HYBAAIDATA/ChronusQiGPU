"""Disagreement between intelligence surfaces — §34.

Two reasoning paths disagreeing is a RESULT, not an error to average
away. ``arbitrate`` returns DISAGREEMENT with evidence whenever the
declared answers conflict, then resolves by declared authority rules —
never by blending the answers:

- interventional questions: the causal surface outranks associational
  prediction (its evidence class is stronger BY CONSTRUCTION, not by
  vote)
- among equals: higher measured calibration and evidence quality win
- unresolvable by the declared rules: the disagreement is returned
  unresolved — the honest answer
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence

ARBITRATION_VERSION = "toe.arbitration/v1"

# Authority order by problem type: which surface's evidence class is
# constitutively stronger for this question. Declared, not learned.
AUTHORITY = {
    "interventional": ["causal_interventional", "scm_simulation",
                       "associational_predictor", "trajectory_extrapolation"],
    "observational": ["associational_predictor", "causal_interventional",
                      "scm_simulation", "trajectory_extrapolation"],
    "planning": ["planning", "causal_interventional", "associational_predictor"],
}


def arbitrate(
    claims: Sequence[Mapping[str, Any]],
    *,
    problem_type: str = "interventional",
) -> Dict[str, Any]:
    """Arbitrate conflicting answers.

    ``claims``: ``{surface, answer, calibration (0-1, optional),
    evidence_quality (0-1, optional)}``. Returns ``status`` DISAGREEMENT
    or AGREEMENT plus ``resolution`` — chosen surface and the rule that
    picked it — or ``resolution: None`` when no declared rule applies.
    """
    if not claims:
        return {"status": "UNAVAILABLE", "reason": "no claims supplied"}
    answers = {c["surface"]: c["answer"] for c in claims}
    distinct = sorted(set(answers.values()), key=str)
    base: Dict[str, Any] = {
        "version": ARBITRATION_VERSION,
        "claims": list(claims),
        "distinct_answers": distinct,
    }
    if len(distinct) == 1:
        return {**base, "status": "AGREEMENT", "resolution": None}

    order = AUTHORITY.get(problem_type, [])
    best: Optional[Mapping[str, Any]] = None
    rule = None
    for surface in order:
        hit = [c for c in claims if c["surface"] == surface]
        if hit:
            best, rule = hit[0], f"authority[{problem_type}]:{surface}"
            break
    if best is None:
        # no declared authority present: fall to measured quality
        scored = [
            c
            for c in claims
            if c.get("calibration") is not None or c.get("evidence_quality") is not None
        ]
        if scored:
            best = max(
                scored,
                key=lambda c: (
                    float(c.get("calibration", 0.0)),
                    float(c.get("evidence_quality", 0.0)),
                ),
            )
            rule = "measured calibration+evidence quality"
    if best is None:
        return {
            **base,
            "status": "DISAGREEMENT",
            "resolution": None,
            "reason": "no declared authority applies; unresolved on the evidence",
        }
    return {
        **base,
        "status": "DISAGREEMENT",
        "resolution": {
            "surface": best["surface"],
            "answer": best["answer"],
            "rule": rule,
        },
    }


__all__ = ["ARBITRATION_VERSION", "AUTHORITY", "arbitrate"]
