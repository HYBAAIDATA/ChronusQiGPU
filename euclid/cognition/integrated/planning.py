"""Model-based planning over learned mechanisms at several abstraction levels.

Representations are genuinely different search spaces, not labels:

* ``literal`` — every operator over the full state;
* ``causal-relevance`` — the quotient that drops operators which cannot
  influence the goal variables through the learned causal graph (backward
  closure over writes and guard/copy reads);
* ``hierarchical`` — goal variables ordered by causal dependency and achieved
  as serial subgoals, each protected once achieved, with a joint fallback.

Learned macros (bound skills) enter as compound actions.  Every search is
bounded by an explicit node budget and reports its expansions so planning
cost is a measured quantity.  Programs are open-loop; contingency is realised
by observe-and-repair between submissions (:func:`repair`).
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from ..worlds.mechanisms import Mechanism, State

REPRESENTATIONS = ("literal", "causal-relevance", "hierarchical")


@dataclass
class PlanResult:
    program: tuple[str, ...] | None
    expanded: int
    representation: str
    budget_exhausted: bool = False
    subgoals: list[dict[str, Any]] = field(default_factory=list)
    macros_used: list[str] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return self.program is not None

    def to_json(self) -> dict[str, Any]:
        return {
            "program": list(self.program) if self.program is not None else None,
            "expanded": self.expanded,
            "representation": self.representation,
            "budget_exhausted": self.budget_exhausted,
            "subgoals": list(self.subgoals),
            "macros_used": list(self.macros_used),
        }


def _satisfied(state: State, goal: Sequence[tuple[int, int]]) -> bool:
    return all(state[i] == v for i, v in goal)


def _unsatisfied(state: State, goal: Sequence[tuple[int, int]]) -> int:
    return sum(1 for i, v in goal if state[i] != v)


def best_first(
    table: Mapping[str, Mechanism],
    actions: Sequence[tuple[str, tuple[str, ...]]],
    start: State,
    goal: Sequence[tuple[int, int]],
    domains: Sequence[int],
    *,
    max_length: int,
    node_budget: int,
    protect: Sequence[tuple[int, int]] = (),
) -> tuple[tuple[str, ...] | None, int, bool, list[str]]:
    """Greedy best-first search (h = unsatisfied goal clauses, ties by length).

    ``actions`` are ``(label, op-sequence)``; plain operators are 1-sequences.
    ``protect`` lists clauses that must hold in every expanded state.
    """
    start = tuple(start)
    if _satisfied(start, goal):
        return (), 0, False, []
    counter = 0
    frontier: list[tuple[int, int, int, State]] = [(_unsatisfied(start, goal), 0, counter, start)]
    parents: dict[State, tuple[State | None, str | None, tuple[str, ...]]] = {
        start: (None, None, ())
    }
    depth: dict[State, int] = {start: 0}
    expanded = 0
    while frontier:
        _, g, _, state = heapq.heappop(frontier)
        if expanded >= node_budget:
            return None, expanded, True, []
        expanded += 1
        for label, ops in actions:
            nxt = state
            for op in ops:
                nxt = table[op].apply(nxt, domains)
            length = g + len(ops)
            if length > max_length or nxt in parents:
                continue
            if protect and not _satisfied(nxt, protect):
                continue
            parents[nxt] = (state, label, ops)
            depth[nxt] = length
            if _satisfied(nxt, goal):
                program: list[str] = []
                labels: list[str] = []
                cursor = nxt
                while parents[cursor][0] is not None:
                    previous, used, sequence = parents[cursor]
                    program[:0] = list(sequence)
                    if len(sequence) > 1:
                        labels.append(used)  # type: ignore[arg-type]
                    cursor = previous  # type: ignore[assignment]
                return tuple(program), expanded, False, labels
            counter += 1
            heapq.heappush(frontier, (_unsatisfied(nxt, goal), length, counter, nxt))
    return None, expanded, False, []


def relevant_operators(
    table: Mapping[str, Mechanism], goal: Sequence[tuple[int, int]]
) -> list[str]:
    """Operators that can influence goal variables (backward causal closure)."""
    relevant_vars = {i for i, _ in goal}
    changed = True
    while changed:
        changed = False
        for mechanism in table.values():
            if mechanism.writes() & relevant_vars:
                extra = mechanism.reads() - relevant_vars
                if extra:
                    relevant_vars |= extra
                    changed = True
    return [
        op for op, mechanism in table.items()
        if mechanism.kind != "noop" and mechanism.writes() & relevant_vars
    ]


def dependency_order(
    table: Mapping[str, Mechanism], goal: Sequence[tuple[int, int]]
) -> list[tuple[int, int]]:
    """Order goal clauses so variables read by other clauses' writers come first."""
    goal_vars = {i for i, _ in goal}
    readers: dict[int, int] = {i: 0 for i in goal_vars}
    for mechanism in table.values():
        written = mechanism.writes() & goal_vars
        if not written:
            continue
        for read in mechanism.reads() - mechanism.writes():
            if read in readers:
                readers[read] += len(written)
    return sorted(goal, key=lambda clause: (-readers[clause[0]], clause[0]))


def plan(
    table: Mapping[str, Mechanism],
    operators: Sequence[str],
    start: State,
    goal: Sequence[tuple[int, int]],
    domains: Sequence[int],
    *,
    representation: str = "literal",
    max_length: int,
    node_budget: int,
    macros: Mapping[str, tuple[str, ...]] | None = None,
) -> PlanResult:
    if representation not in REPRESENTATIONS:
        raise ValueError(f"unknown representation {representation!r}")
    base_ops = (
        list(operators)
        if representation == "literal"
        else relevant_operators({op: table[op] for op in operators}, goal)
    )
    actions: list[tuple[str, tuple[str, ...]]] = [(op, (op,)) for op in base_ops]
    for label, sequence in sorted((macros or {}).items()):
        if representation != "literal" and not set(sequence) <= set(base_ops):
            continue
        actions.append((label, tuple(sequence)))
    if representation != "hierarchical":
        program, expanded, exhausted, used = best_first(
            table, actions, start, goal, domains,
            max_length=max_length, node_budget=node_budget,
        )
        return PlanResult(program, expanded, representation, exhausted, macros_used=used)

    ordered = dependency_order({op: table[op] for op in base_ops}, goal)
    share = max(1, node_budget // (len(ordered) + 1))
    state = tuple(start)
    program: list[str] = []
    achieved: list[tuple[int, int]] = []
    expanded = 0
    subgoals: list[dict[str, Any]] = []
    used_macros: list[str] = []
    for clause in ordered:
        if state[clause[0]] == clause[1]:
            achieved.append(clause)
            subgoals.append({"clause": list(clause), "status": "already-true", "length": 0})
            continue
        piece, spent, exhausted, used = best_first(
            table, actions, state, [clause], domains,
            max_length=max_length - len(program), node_budget=share, protect=achieved,
        )
        expanded += spent
        if piece is None:
            subgoals.append({"clause": list(clause), "status": "failed", "expanded": spent})
            break
        for op in piece:
            state = table[op].apply(state, domains)
        program.extend(piece)
        used_macros.extend(used)
        achieved.append(clause)
        subgoals.append({"clause": list(clause), "status": "achieved", "length": len(piece)})
    if _satisfied(state, goal):
        return PlanResult(tuple(program), expanded, representation, False, subgoals, used_macros)
    # Serial decomposition failed (non-serialisable subgoals): joint fallback
    # with whatever budget remains, recorded as such.
    remaining = max(1, node_budget - expanded)
    joint, spent, exhausted, used = best_first(
        table, actions, start, goal, domains, max_length=max_length, node_budget=remaining,
    )
    subgoals.append({"clause": "joint-fallback", "status": "achieved" if joint else "failed",
                     "expanded": spent})
    return PlanResult(joint, expanded + spent, representation, exhausted, subgoals, used)


def repair(
    failed_program: Sequence[str],
    observed_trajectory: Sequence[Sequence[int]],
    predicted_trajectory: Sequence[Sequence[int]],
    table: Mapping[str, Mechanism],
    operators: Sequence[str],
    start: State,
    goal: Sequence[tuple[int, int]],
    domains: Sequence[int],
    *,
    representation: str,
    max_length: int,
    node_budget: int,
    macros: Mapping[str, tuple[str, ...]] | None = None,
) -> PlanResult:
    """Keep the prefix whose observations matched prediction; replan the rest."""
    keep = 0
    for observed, predicted in zip(observed_trajectory, predicted_trajectory):
        if list(observed) != list(predicted):
            break
        keep += 1
    prefix = tuple(failed_program[:keep])
    state = tuple(start)
    for op in prefix:
        state = table[op].apply(state, domains)
    suffix = plan(
        table, operators, state, goal, domains,
        representation=representation, max_length=max_length - len(prefix),
        node_budget=node_budget, macros=macros,
    )
    program = prefix + suffix.program if suffix.program is not None else None
    result = PlanResult(
        program, suffix.expanded, representation, suffix.budget_exhausted,
        suffix.subgoals + [{"repair_prefix": len(prefix)}], suffix.macros_used,
    )
    return result


__all__ = [
    "PlanResult",
    "REPRESENTATIONS",
    "best_first",
    "dependency_order",
    "plan",
    "relevant_operators",
    "repair",
]
