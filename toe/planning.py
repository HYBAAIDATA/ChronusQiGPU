"""Action generation + bounded hierarchical planning — elevation §§16-18.

Candidate actions are generated ONLY from a declared operator vocabulary
(``OperatorSpec``): an operator names the node(s) it may set and the
levels or deltas it may apply. There is no arbitrary code path — an
action is data (``{node: value}``) plus provenance (which operators
produced it). Optional ``max_arity`` composes operators into joint
interventions under an action cap.

``plan`` runs bounded forward search over operator applications: each
step merges the chosen intervention, evaluates the expected intermediate
state through the environment's transition model (an SCM via
``scm_env``, or any mapping), checks step constraints, and accumulates
operator cost under an optional budget. ``greedy`` is the same search
with depth 1 — the explicit baseline the brief requires. The SCM's
linearity means planning only beats greedy when interactions matter
(budgets, intermediate constraints); the tests construct those cases and
also assert the honest parity case.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, NamedTuple, Optional, Sequence, Tuple

from .causal_ladder import StructuralCausalModel
from .policy import Constraint, Objective

PLANNING_VERSION = "toe.planning/v1"


class OperatorSpec(NamedTuple):
    """A declared action vocabulary entry — the ONLY source of actions.

    ``levels`` sets the node absolutely; ``deltas`` shifts it relative to
    the node's current state value. ``cost`` feeds plan budgets.
    """

    name: str
    node: str
    levels: Tuple[float, ...] = ()
    deltas: Tuple[float, ...] = ()
    cost: float = 1.0


def generate_actions(
    operators: Sequence[OperatorSpec],
    state: Optional[Mapping[str, float]] = None,
    *,
    max_arity: int = 1,
    max_actions: int = 256,
) -> List[Dict[str, Any]]:
    """Candidate actions from the declared vocabulary — nothing else.

    Each action is ``{name, interventions, operators, cost}``. With
    ``max_arity > 1`` joint interventions are enumerated under
    ``max_actions``; compositions of the same node keep the LAST level.
    """
    atomic: List[Dict[str, Any]] = []
    for op in operators:
        for level in op.levels:
            atomic.append(
                {
                    "name": f"{op.name}={level}",
                    "interventions": {op.node: float(level)},
                    "operators": [op.name],
                    "cost": op.cost,
                }
            )
        for d in op.deltas:
            if state is None or op.node not in state:
                continue
            atomic.append(
                {
                    "name": f"{op.name}{d:+g}",
                    "interventions": {op.node: float(state[op.node]) + float(d)},
                    "operators": [op.name],
                    "cost": op.cost,
                }
            )
    if max_arity <= 1:
        return atomic[:max_actions]
    out = list(atomic)
    for combo in _combinations(atomic, max_arity):
        merged: Dict[str, float] = {}
        ops: List[str] = []
        cost = 0.0
        for a in combo:
            merged.update(a["interventions"])
            ops.extend(a["operators"])
            cost += a["cost"]
        out.append(
            {
                "name": "+".join(a["name"] for a in combo),
                "interventions": merged,
                "operators": ops,
                "cost": cost,
            }
        )
        if len(out) >= max_actions:
            break
    return out[:max_actions]


def _combinations(items: List[Dict[str, Any]], k: int):
    from itertools import combinations

    for r in range(2, k + 1):
        for c in combinations(items, r):
            yield c


def scm_env(scm: StructuralCausalModel):
    """Environment whose transitions are SCM evaluations.

    State = intervention dict accumulated so far; transition =
    evaluate_all with the merged interventions. Expected intermediate
    states come straight from the structural equations.
    """

    def evaluate(interventions: Mapping[str, float]) -> Dict[str, float]:
        return scm.evaluate_all(dict(interventions), {})

    return evaluate


def _plan_key(interventions: Mapping[str, float]) -> Tuple[Tuple[str, float], ...]:
    return tuple(sorted(interventions.items()))


def plan(
    env_evaluate: Any,
    operators: Sequence[OperatorSpec],
    *,
    objective: Objective,
    constraints: Sequence[Constraint] = (),
    depth: int = 2,
    beam: int = 16,
    budget: Optional[float] = None,
    initial_interventions: Optional[Mapping[str, float]] = None,
) -> Dict[str, Any]:
    """Bounded forward search over the declared operator vocabulary.

    Returns the best plan found: the intervention sequence, the expected
    intermediate states, the terminal objective value, and search
    statistics. Step constraints are checked on EVERY intermediate state;
    ``budget`` caps total operator cost.
    """
    if depth < 1:
        return {"available": False, "reason": "depth must be >= 1"}
    sign = -1.0 if objective.sense == "maximize" else 1.0
    start = dict(initial_interventions or {})
    expanded = 0

    # frontier: (rank, plan_so_far)
    Frontier = Tuple[float, List[Dict[str, Any]]]
    frontier: List[Frontier] = [(0.0, [])]
    best_terminal: Optional[Dict[str, Any]] = None

    for step in range(depth):
        candidates: List[Frontier] = []
        state_of: Dict[Tuple, Dict[str, float]] = {}
        for _, prefix in frontier:
            base_iv = _plan_key(start | _merge(prefix))
            base_iv_map = dict(base_iv)
            try:
                base_state = env_evaluate(base_iv_map)
            except Exception:
                continue
            # delta operators apply relative to the node's current value —
            # the evaluated state, not just the interventions dict
            actions = generate_actions(operators, base_state, max_arity=1)
            for a in actions:
                merged = dict(base_iv_map)
                merged.update(a["interventions"])
                if _plan_key(merged) == tuple(base_iv):
                    continue  # no-op action
                cost = sum(x["cost"] for x in prefix) + a["cost"]
                if budget is not None and cost > budget:
                    continue
                try:
                    state = env_evaluate(merged)
                except Exception:
                    continue
                violated = [
                    c.name
                    for c in constraints
                    if c.check(state) is False
                ]
                expanded += 1
                if violated:
                    continue
                obj = state.get(objective.target)
                if obj is None:
                    continue
                new_plan = prefix + [a]
                key = _plan_key(merged)
                candidates.append((sign * float(obj), new_plan))
                state_of[key] = state
        if not candidates:
            break
        candidates.sort(key=lambda t: (t[0], [a["name"] for a in t[1]]))
        frontier = candidates[:beam]
        step_best = {
            "plan": frontier[0][1],
            "state": state_of[_plan_key(start | _merge(frontier[0][1]))],
            "objective_value": frontier[0][0] * sign,
        }
        # Keep the global best across depths: a deeper search must never
        # return a worse plan than a shallower one found en route.
        if best_terminal is None or (
            step_best["objective_value"] > best_terminal["objective_value"]
            if objective.sense == "maximize"
            else step_best["objective_value"] < best_terminal["objective_value"]
        ):
            best_terminal = step_best
    if best_terminal is None:
        return {"available": False, "reason": "no feasible plan within depth/budget"}

    seq = best_terminal["plan"]
    intermediates: List[Dict[str, float]] = []
    acc = dict(start)
    for a in seq:
        acc.update(a["interventions"])
        intermediates.append(env_evaluate(acc))
    merged_final = dict(start)
    for a in seq:
        merged_final.update(a["interventions"])
    return {
        "version": PLANNING_VERSION,
        "available": True,
        "sequence": [{"name": a["name"], "interventions": a["interventions"],
                      "operators": a["operators"], "cost": a["cost"]} for a in seq],
        "merged_interventions": merged_final,
        "intermediate_states": intermediates,
        "terminal_state": intermediates[-1] if intermediates else env_evaluate(acc),
        "objective": objective.as_dict(),
        "objective_value": best_terminal["objective_value"],
        "total_cost": sum(a["cost"] for a in seq),
        "depth": len(seq),
        "nodes_expanded": expanded,
        "constraints": [c.as_dict() for c in constraints],
        "budget": budget,
    }


def _merge(prefix: List[Dict[str, Any]]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for a in prefix:
        out.update(a["interventions"])
    return out


def greedy(
    env_evaluate: Any,
    operators: Sequence[OperatorSpec],
    *,
    objective: Objective,
    constraints: Sequence[Constraint] = (),
    budget: Optional[float] = None,
    initial_interventions: Optional[Mapping[str, float]] = None,
) -> Dict[str, Any]:
    """One-step greedy policy — the depth-1 case of ``plan``."""
    return plan(
        env_evaluate,
        operators,
        objective=objective,
        constraints=constraints,
        depth=1,
        beam=1 << 20,
        budget=budget,
        initial_interventions=initial_interventions,
    )


def compare_plan_vs_greedy(
    env_evaluate: Any,
    operators: Sequence[OperatorSpec],
    *,
    objective: Objective,
    constraints: Sequence[Constraint] = (),
    depth: int = 2,
    budget: Optional[float] = None,
) -> Dict[str, Any]:
    """The required comparison: multi-step plan vs one-step greedy."""
    g = greedy(
        env_evaluate, operators, objective=objective,
        constraints=constraints, budget=budget,
    )
    p = plan(
        env_evaluate, operators, objective=objective,
        constraints=constraints, depth=depth, budget=budget,
    )
    gv = g.get("objective_value")
    pv = p.get("objective_value")
    better = (
        p["available"]
        and g.get("available")
        and pv is not None
        and gv is not None
        and (pv > gv if objective.sense == "maximize" else pv < gv)
    )
    return {
        "version": PLANNING_VERSION,
        "greedy": g,
        "plan": p,
        "plan_strictly_better": better,
        "objective_gap": (pv - gv) if (pv is not None and gv is not None) else None,
    }


__all__ = [
    "PLANNING_VERSION",
    "OperatorSpec",
    "generate_actions",
    "scm_env",
    "plan",
    "greedy",
    "compare_plan_vs_greedy",
]
