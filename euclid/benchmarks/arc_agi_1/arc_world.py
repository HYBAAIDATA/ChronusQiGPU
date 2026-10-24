"""ARC-AGI-1 demonstration world behind EUCLID's governed TaskSpec boundary."""
from __future__ import annotations

import json
from typing import Any, Sequence

from euclid.cognition.worlds.world import (
    ASSIGN,
    BudgetExhausted,
    TaskSpec,
    normalise_program,
)
from euclid.benchmarks.arc_agi_1.grid_primitives import (
    FITTED,
    OPERATOR_NAMES,
    Grid,
    OperatorFailed,
    apply_unary,
    fit_colour_map,
    fit_constant_output,
)

SURFACE_DOMAIN = "arc-agi-1-grid"


def _apply_step(
    op: str, train_cur: list[Grid], train_out: Sequence[Grid], extra_cur: list[Grid]
) -> tuple[list[Grid], list[Grid], int]:
    failures = 0
    if op in FITTED:
        pairs = list(zip(train_cur, train_out))
        try:
            if op == "recolor_fit":
                mapping = fit_colour_map(pairs)

                def fn(g: Grid) -> Grid:
                    return [[mapping.get(v, v) for v in row] for row in g]
            else:
                constant = fit_constant_output(pairs)

                def fn(g: Grid) -> Grid:
                    return [list(r) for r in constant]
        except OperatorFailed:
            n = len(train_cur) + len(extra_cur)
            return train_cur, extra_cur, n
        return [fn(g) for g in train_cur], [fn(g) for g in extra_cur], 0

    def one(g: Grid) -> Grid:
        nonlocal failures
        try:
            return apply_unary(op, g)
        except (OperatorFailed, IndexError, ValueError):
            failures += 1
            return g

    return [one(g) for g in train_cur], [one(g) for g in extra_cur], failures


def execute_program(
    program: Sequence[Any],
    train_pairs: Sequence[tuple[Grid, Grid]],
    extra_inputs: Sequence[Grid] = (),
) -> tuple[list[list[Grid]], list[Grid], int]:
    train_cur = [[list(r) for r in inp] for inp, _ in train_pairs]
    train_out = [out for _, out in train_pairs]
    extra_cur = [[list(r) for r in g] for g in extra_inputs]
    trace: list[list[Grid]] = []
    failures = 0
    for step in normalise_program(program):
        op = step if isinstance(step, str) else step[0]
        train_cur, extra_cur, f = _apply_step(op, train_cur, train_out, extra_cur)
        failures += f
        trace.append(train_cur)
    return trace, extra_cur, failures


def abstract_state(grids: Sequence[Grid], targets: Sequence[Grid]) -> list[int]:
    state: list[int] = []
    for g, t in zip(grids, targets):
        shape = int(len(g) == len(t) and len(g[0]) == len(t[0]))
        palette = int({v for r in g for v in r} == {v for r in t for v in r})
        state.extend([shape, palette, int(g == t)])
    return state


def build_spec(
    task_id: str,
    train_pairs: Sequence[tuple[Grid, Grid]],
    *,
    probe_budget: int = 12,
    submission_budget: int = 3,
    max_program_length: int = 16,
    max_probe_length: int = 3,
    partition: str = "evaluation",
) -> TaskSpec:
    variables: list[str] = []
    for k in range(len(train_pairs)):
        variables += [f"pair{k}_shape", f"pair{k}_palette", f"pair{k}_exact"]
    initial = abstract_state([i for i, _ in train_pairs], [o for _, o in train_pairs])
    goal = tuple((3 * k + 2, 1) for k in range(len(train_pairs)))
    return TaskSpec(
        task_id=task_id,
        surface_domain=SURFACE_DOMAIN,
        variables=tuple(variables),
        domains=tuple(2 for _ in variables),
        operators=OPERATOR_NAMES,
        initial_state=tuple(initial),
        goal=goal,
        objective=ASSIGN,
        observables=("state", "score"),
        probe_budget=probe_budget,
        submission_budget=submission_budget,
        max_program_length=max_program_length,
        max_probe_length=max_probe_length,
        partition=partition,
    )


class ArcDemonstrationWorld:
    """Budgeted world over one task's demonstrations. Holds no test data."""

    def __init__(self, spec: TaskSpec, train_pairs: Sequence[tuple[Grid, Grid]]) -> None:
        if len(train_pairs) * 3 != len(spec.variables):
            raise ValueError("spec does not match the demonstrations")
        self.spec = spec
        self._pairs = [([list(r) for r in i], [list(r) for r in o]) for i, o in train_pairs]
        self._targets = [o for _, o in self._pairs]
        self.probes_used = 0
        self.submissions_used = 0
        self.ledger: list[dict[str, Any]] = []

    @property
    def cost(self) -> float:
        return (
            self.probes_used * self.spec.probe_cost
            + self.submissions_used * self.spec.submission_cost
        )

    def _validate(self, program: Sequence[Any], limit: int) -> list[Any]:
        steps = normalise_program(program)
        if len(steps) > limit:
            raise ValueError(f"program longer than the declared limit {limit}")
        for step in steps:
            if not isinstance(step, str):
                raise ValueError("this task has no parametric operators")
            if step not in self.spec.operators:
                raise ValueError(f"unknown operator {step!r}")
        return steps

    def _run(self, steps: list[Any]) -> dict[str, Any]:
        trace, _, failures = execute_program(steps, self._pairs)
        trajectory = [abstract_state(g, self._targets) for g in trace]
        final = trajectory[-1] if trajectory else list(self.spec.initial_state)
        scores = [sum(1 for i, v in self.spec.goal if s[i] == v) for s in trajectory]
        return {
            "trajectory": trajectory,
            "scores": scores,
            "goal_met": self.spec.goal_met(tuple(final)),
            "failed_applications": failures,
            "final_score": scores[-1] if scores else 0,
        }

    def _public(self, kind: str, steps: list[Any], run: dict[str, Any]) -> dict[str, Any]:
        result = dict(run)
        if kind == "probe":
            result.pop("goal_met", None)
        final = run["trajectory"][-1] if run["trajectory"] else list(self.spec.initial_state)
        result.update(
            {
                "kind": kind,
                "program": steps,
                "probes_remaining": self.spec.probe_budget - self.probes_used,
                "submissions_remaining": self.spec.submission_budget - self.submissions_used,
                "cost_so_far": self.cost,
                "budget_exhausted": False,
                "observation": json.dumps(final, separators=(",", ":")),
            }
        )
        return result

    def probe(self, program: Sequence[Any]) -> dict[str, Any]:
        if self.probes_used >= self.spec.probe_budget:
            raise BudgetExhausted("probe budget exhausted")
        steps = self._validate(program, self.spec.max_probe_length)
        if not steps:
            raise ValueError("a probe needs at least one step")
        self.probes_used += 1
        run = self._run(steps)
        self.ledger.append(
            {
                "kind": "probe",
                "program": steps,
                "score": run["final_score"],
                "goal_met": False,
            }
        )
        return self._public("probe", steps, run)

    def submit(self, program: Sequence[Any]) -> dict[str, Any]:
        if self.submissions_used >= self.spec.submission_budget:
            raise BudgetExhausted("submission budget exhausted")
        steps = self._validate(program, self.spec.max_program_length)
        self.submissions_used += 1
        run = self._run(steps)
        self.ledger.append(
            {
                "kind": "submission",
                "program": steps,
                "score": run["final_score"],
                "goal_met": bool(run["goal_met"]),
            }
        )
        return self._public("submission", steps, run)

    @property
    def solved(self) -> bool:
        return any(e["kind"] == "submission" and e["goal_met"] for e in self.ledger)


__all__ = [
    "ArcDemonstrationWorld",
    "SURFACE_DOMAIN",
    "abstract_state",
    "build_spec",
    "execute_program",
]
