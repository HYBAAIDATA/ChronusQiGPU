"""Action policy: choose among candidate actions by their evaluated futures.

Domain-general. The inputs are a factual state, named candidate actions
(each an intervention on the state's variables), a futures model that
predicts the state an action would produce, an objective on that future,
and declared constraints. The output is every evaluated future, the
selected action (or none), the reason, and a decision digest.

Rules:

- Every candidate is evaluated by the futures model. Nothing is scored by
  name or position.
- A candidate whose future cannot be computed, whose objective value is
  missing or non-finite, or whose constraints cannot be evaluated is
  excluded with that reason.
- A candidate that violates a declared constraint is excluded, and the
  constraint is named.
- The best remaining objective wins. Exact ties go to the
  lexicographically first action name, and the tie is reported.
- When nothing remains the decision is ``available=False`` with
  ``selected_action=None``. There is no default action.

``counterfactual_futures`` builds the futures model from a structural causal
model: abduct the factual state's noise, apply the action as do(), predict.
"""

from __future__ import annotations

import hashlib
import json
import math
import operator
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

POLICY_VERSION = "toe.policy.decide/v1"

FuturesFn = Callable[[Mapping[str, float], Mapping[str, float]], Mapping[str, float]]

_OPERATORS = {
    "<=": operator.le,
    "<": operator.lt,
    ">=": operator.ge,
    ">": operator.gt,
    "==": operator.eq,
}


def _digest(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Objective:
    """Maximize or minimize one named variable of the predicted future."""

    target: str
    sense: str = "maximize"

    def __post_init__(self) -> None:
        if self.sense not in ("maximize", "minimize"):
            raise ValueError(f"objective sense must be maximize or minimize, not {self.sense!r}")

    def as_dict(self) -> Dict[str, str]:
        return {"target": self.target, "sense": self.sense}


@dataclass(frozen=True)
class Constraint:
    """``future[variable] <op> bound`` must hold for an admissible action."""

    name: str
    variable: str
    op: str
    bound: float

    def __post_init__(self) -> None:
        if self.op not in _OPERATORS:
            raise ValueError(f"unsupported constraint operator {self.op!r}")
        if not math.isfinite(float(self.bound)):
            raise ValueError("constraint bound must be finite")

    def check(self, future: Mapping[str, float]) -> Optional[bool]:
        """True/False when evaluable, None when the variable is unavailable."""
        value = future.get(self.variable)
        if value is None or not math.isfinite(float(value)):
            return None
        return bool(_OPERATORS[self.op](float(value), float(self.bound)))

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "variable": self.variable,
            "op": self.op,
            "bound": float(self.bound),
        }

    @classmethod
    def from_dict(cls, spec: Mapping[str, Any]) -> "Constraint":
        return cls(
            name=str(spec.get("name") or f"{spec['variable']} {spec['op']} {spec['bound']}"),
            variable=str(spec["variable"]),
            op=str(spec["op"]),
            bound=float(spec["bound"]),
        )


@dataclass
class PolicyDecision:
    available: bool
    selected_action: Optional[str]
    reason: str
    objective: Dict[str, str] = field(default_factory=dict)
    futures: List[Dict[str, Any]] = field(default_factory=list)
    constraints_applied: List[Dict[str, Any]] = field(default_factory=list)
    margin: Optional[float] = None
    tie_broken: bool = False
    model_id: Optional[str] = None
    state_sha256: Optional[str] = None
    decision_sha256: Optional[str] = None
    version: str = POLICY_VERSION

    def as_dict(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "selected_action": self.selected_action,
            "reason": self.reason,
            "objective": dict(self.objective),
            "futures": [dict(f) for f in self.futures],
            "constraints_applied": [dict(c) for c in self.constraints_applied],
            "margin": self.margin,
            "tie_broken": self.tie_broken,
            "model_id": self.model_id,
            "state_sha256": self.state_sha256,
            "decision_sha256": self.decision_sha256,
            "version": self.version,
        }


def _finite_mapping(values: Mapping[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for key, value in values.items():
        if value is None or isinstance(value, bool):
            continue
        number = float(value)
        if math.isfinite(number):
            out[str(key)] = number
    return out


def decide(
    state: Mapping[str, float],
    candidates: Mapping[str, Mapping[str, float]],
    *,
    futures: FuturesFn,
    objective: Objective,
    constraints: Sequence[Constraint] = (),
    model_id: Optional[str],
) -> PolicyDecision:
    """Evaluate every candidate's future and select the best admissible one."""
    constraint_specs = [c.as_dict() for c in constraints]
    base = {
        "objective": objective.as_dict(),
        "constraints_applied": constraint_specs,
        "model_id": model_id,
    }
    if not model_id:
        return PolicyDecision(
            available=False,
            selected_action=None,
            reason="no model identifier: futures cannot be bound to a model",
            **base,
        )
    if not candidates:
        return PolicyDecision(
            available=False, selected_action=None, reason="no candidate actions", **base
        )
    state_sha = _digest({"state": _finite_mapping(state)})
    evaluated: List[Dict[str, Any]] = []
    for name in sorted(candidates):
        action = {str(k): float(v) for k, v in candidates[name].items()}
        record: Dict[str, Any] = {
            "action": name,
            "intervention": action,
            "available": False,
            "future": None,
            "objective_value": None,
            "violated": [],
            "unevaluable": [],
            "admissible": False,
            "excluded_because": None,
        }
        try:
            future = _finite_mapping(futures(state, action))
        except Exception as exc:  # an unavailable future excludes the action
            record["excluded_because"] = f"future unavailable: {exc}"
            evaluated.append(record)
            continue
        record["available"] = True
        record["future"] = future
        value = future.get(objective.target)
        if value is None:
            record["excluded_because"] = f"objective {objective.target!r} not in the future"
            evaluated.append(record)
            continue
        record["objective_value"] = value
        for constraint in constraints:
            verdict = constraint.check(future)
            if verdict is None:
                record["unevaluable"].append(constraint.name)
            elif not verdict:
                record["violated"].append(constraint.name)
        if record["unevaluable"]:
            record["excluded_because"] = "constraint not evaluable: " + ", ".join(
                record["unevaluable"]
            )
        elif record["violated"]:
            record["excluded_because"] = "violates constraint: " + ", ".join(record["violated"])
        else:
            record["admissible"] = True
        evaluated.append(record)

    admissible = [r for r in evaluated if r["admissible"]]
    sign = -1.0 if objective.sense == "maximize" else 1.0
    ordered = sorted(admissible, key=lambda r: (sign * r["objective_value"], r["action"]))
    excluded = [
        f"{r['action']} ({r['excluded_because']})" for r in evaluated if not r["admissible"]
    ]
    if not ordered:
        decision = PolicyDecision(
            available=False,
            selected_action=None,
            reason="no candidate is both evaluable and within constraints; excluded: "
            + "; ".join(excluded),
            futures=evaluated,
            state_sha256=state_sha,
            **base,
        )
    else:
        best = ordered[0]
        margin = None
        tie = False
        if len(ordered) > 1:
            margin = abs(best["objective_value"] - ordered[1]["objective_value"])
            tie = margin == 0.0
        reason = (
            f"{best['action']} {objective.sense}s {objective.target} "
            f"({best['objective_value']!r}) among {len(ordered)} admissible candidate(s)"
        )
        if tie:
            reason += "; exact tie broken by action name"
        if excluded:
            reason += "; excluded: " + "; ".join(excluded)
        decision = PolicyDecision(
            available=True,
            selected_action=best["action"],
            reason=reason,
            futures=evaluated,
            margin=margin,
            tie_broken=tie,
            state_sha256=state_sha,
            **base,
        )
    decision.decision_sha256 = _digest(
        {k: v for k, v in decision.as_dict().items() if k != "decision_sha256"}
    )
    return decision


def counterfactual_futures(
    scm: Any, *, outcomes: Optional[Sequence[str]] = None, arithmetic: str = "float64"
) -> FuturesFn:
    """Futures from a structural causal model by abduction-action-prediction.

    ``outcomes`` defaults to every node of the model; the factual state must
    then carry evidence for all of them.
    """
    from .causal_ladder import counterfactual_state

    def futures(state: Mapping[str, float], action: Mapping[str, float]) -> Dict[str, float]:
        wanted = list(outcomes) if outcomes is not None else list(scm.graph.nodes)
        result = counterfactual_state(scm, action, state, wanted, arithmetic=arithmetic)
        return dict(result["values"])

    return futures


__all__ = [
    "POLICY_VERSION",
    "Constraint",
    "Objective",
    "PolicyDecision",
    "counterfactual_futures",
    "decide",
]
