"""Software engineering task world with process isolation and diff generation.

Bridges real Python code transformation and test verification to the
governed task world interface (TaskSpec, WorldExecutor).
Candidate code patches are checked for AST safety, compiled, executed in
an isolated subprocess, and verified against functional tests.
"""
from __future__ import annotations

import difflib
import json
from typing import Any, Callable, Mapping, Sequence

from euclid.core.primitives import ASTPrimitives
from euclid.validation.process_sandbox import ASTSafetyValidator, IsolatedProcessEvaluator
from .worlds.world import ASSIGN, BudgetExhausted, TaskSpec, normalise_program


class SoftwareTaskWorld:
    """A governed software-engineering task world with sandbox isolation.

    Probes inspect syntax and AST safety without executing the test suite.
    Submissions run isolated execution against the declared functional test suite.
    """

    def __init__(
        self,
        spec: TaskSpec,
        initial_code: str,
        test_code: str,
        *,
        operators: Mapping[str, Callable[[str, int], tuple[str, str]]] | None = None,
        timeout_sec: float = 2.0,
    ) -> None:
        self.spec = spec
        self.initial_code = initial_code
        self.test_code = test_code
        self.timeout_sec = timeout_sec
        self.evaluator = IsolatedProcessEvaluator(timeout_sec=timeout_sec)
        if operators is None:
            self.operators = dict(ASTPrimitives.get_all_operators())
        else:
            self.operators = dict(operators)

        self.current_code = initial_code
        self.probes_used = 0
        self.submissions_used = 0
        self.cost = 0.0
        self.ledger: list[dict[str, Any]] = []

    def _apply_program(self, program: Sequence[Any]) -> tuple[str, list[str]]:
        code = self.initial_code
        applied_ops: list[str] = []
        for step in program:
            op_name = step if isinstance(step, str) else step[0]
            if op_name in self.operators:
                op_fn = self.operators[op_name]
                code, label = op_fn(code, 42)
                applied_ops.append(label)
        return code, applied_ops

    def _diff(self, before: str, after: str) -> str:
        return "".join(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile="before.py",
                tofile="after.py",
            )
        )

    def probe(self, program: Sequence[Any]) -> dict[str, Any]:
        if self.probes_used >= self.spec.probe_budget:
            raise BudgetExhausted("probe budget exhausted")
        self.probes_used += 1
        self.cost += self.spec.probe_cost

        candidate_code, ops = self._apply_program(program)
        safe, sec_msg = ASTSafetyValidator.validate_code_str(candidate_code)
        diff = self._diff(self.initial_code, candidate_code)
        trajectory = [[1 if safe else 0, 0] for _ in program]

        result = {
            "kind": "intervention",
            "program": normalise_program(program),
            "trajectory": trajectory,
            "safe": safe,
            "security_message": sec_msg,
            "diff": diff,
            "probes_remaining": self.spec.probe_budget - self.probes_used,
            "submissions_remaining": self.spec.submission_budget - self.submissions_used,
            "cost_so_far": self.cost,
            "budget_exhausted": False,
            "observation": json.dumps({
                "safe": safe,
                "msg": sec_msg,
                "diff_lines": len(diff.splitlines()),
                "ops_applied": ops,
            }),
        }
        self.ledger.append({"kind": "probe", "program": program, "safe": safe})
        return result

    def submit(self, program: Sequence[Any]) -> dict[str, Any]:
        if self.submissions_used >= self.spec.submission_budget:
            raise BudgetExhausted("submission budget exhausted")
        self.submissions_used += 1
        self.cost += self.spec.submission_cost

        candidate_code, ops = self._apply_program(program)
        diff = self._diff(self.initial_code, candidate_code)
        parse_v, comp_v, test_v, diag = self.evaluator.evaluate_validity(
            candidate_code,
            external_test_code=self.test_code,
        )
        goal_met = bool(parse_v and comp_v and test_v)
        trajectory = [[1 if parse_v and comp_v else 0, 1 if test_v else 0] for _ in program]

        result = {
            "kind": "plan",
            "program": normalise_program(program),
            "trajectory": trajectory,
            "parse_valid": parse_v,
            "compile_valid": comp_v,
            "test_valid": test_v,
            "goal_met": goal_met,
            "diagnostic": diag,
            "diff": diff,
            "candidate_code": candidate_code,
            "probes_remaining": self.spec.probe_budget - self.probes_used,
            "submissions_remaining": self.spec.submission_budget - self.submissions_used,
            "cost_so_far": self.cost,
            "budget_exhausted": False,
            "reward": 1.0 if goal_met else 0.0,
            "reward_authority": "measured-environment",
            "observation": json.dumps({
                "goal_met": goal_met,
                "diag": diag,
                "test_valid": test_v,
            }),
        }
        self.ledger.append({
            "kind": "submission",
            "program": program,
            "goal_met": goal_met,
            "diagnostic": diag,
        })
        if goal_met:
            self.current_code = candidate_code
        return result

    @property
    def solved(self) -> bool:
        return any(entry.get("goal_met") for entry in self.ledger)


def create_software_task(
    task_id: str,
    code: str,
    test_code: str,
    *,
    probe_budget: int = 10,
    submission_budget: int = 3,
) -> tuple[TaskSpec, SoftwareTaskWorld]:
    """Create a TaskSpec and SoftwareTaskWorld pair for a Python software task."""
    operators = [name for name, _ in ASTPrimitives.get_all_operators()]
    spec = TaskSpec(
        task_id=task_id,
        surface_domain="python-source",
        variables=("syntax", "tests"),
        domains=(2, 2),
        operators=tuple(operators),
        initial_state=(0, 0),
        goal=((0, 1), (1, 1)),
        objective=ASSIGN,
        probe_budget=probe_budget,
        submission_budget=submission_budget,
        partition="evaluation",
    )
    world = SoftwareTaskWorld(spec, code, test_code)
    return spec, world


__all__ = [
    "SoftwareTaskWorld",
    "create_software_task",
]
