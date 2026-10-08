"""Budgeted interactive task worlds with a strict public/hidden split.

An agent receives only a :class:`TaskSpec` — variables, domains, operator
names, the initial state, the goal and the interaction budget.  The hidden
:class:`HiddenTruth` (mechanisms, observation noise, proxy operators,
non-stationarity, response curves) is reachable only through the governed
:class:`WorldExecutor`, which charges every probe and submission against the
declared budget and fails closed on anything malformed.

Success is judged on the *true* state, never on the (possibly noisy) reading
returned to the agent, and never on the proxy ``score`` observable.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from ...contracts import RewardAuthority, domain_hash
from .mechanisms import Mechanism, State

ASSIGN = "assign"
MAXIMISE_RESPONSE = "maximise-response"


def normalise_program(program: Sequence[Any]) -> list[Any]:
    """Canonical JSON-able program: ``"op"`` or ``["op", int]`` steps."""
    steps: list[Any] = []
    for step in program:
        if isinstance(step, str):
            steps.append(step)
        elif isinstance(step, (list, tuple)) and len(step) == 2:
            steps.append([str(step[0]), int(step[1])])
        else:
            raise ValueError(f"malformed program step {step!r}")
    return steps


@dataclass(frozen=True)
class TaskSpec:
    """Everything an agent is entitled to know before acting."""

    task_id: str
    surface_domain: str
    variables: tuple[str, ...]
    domains: tuple[int, ...]
    operators: tuple[str, ...]
    initial_state: tuple[int, ...]
    goal: tuple[tuple[int, int], ...] = ()
    objective: str = ASSIGN
    parametric: tuple[str, int] | None = None
    observables: tuple[str, ...] = ("state", "score")
    probe_budget: int = 12
    submission_budget: int = 3
    probe_cost: float = 1.0
    submission_cost: float = 3.0
    max_program_length: int = 16
    max_probe_length: int = 3
    partition: str = "evaluation"

    def __post_init__(self) -> None:
        if not self.task_id:
            raise ValueError("task_id is required")
        if self.objective not in (ASSIGN, MAXIMISE_RESPONSE):
            raise ValueError("unknown objective")
        if len(self.variables) != len(self.domains) or len(self.initial_state) != len(
            self.domains
        ):
            raise ValueError("variables, domains and initial state must align")
        if any(m < 2 for m in self.domains):
            raise ValueError("every domain needs at least two values")
        if any(not 0 <= v < m for v, m in zip(self.initial_state, self.domains)):
            raise ValueError("initial state outside its domains")
        if self.objective == ASSIGN and not self.goal:
            raise ValueError("assignment tasks require a goal")
        if self.objective == MAXIMISE_RESPONSE and self.parametric is None:
            raise ValueError("response tasks require a parametric operator")
        if self.probe_budget < 0 or self.submission_budget < 1:
            raise ValueError("budgets must be non-negative with at least one submission")
        if len(set(self.operators)) != len(self.operators):
            raise ValueError("operator names must be unique")

    def goal_met(self, state: State) -> bool:
        return all(state[i] == v for i, v in self.goal)

    def goal_text(self) -> str:
        if self.objective == MAXIMISE_RESPONSE:
            op, size = self.parametric  # type: ignore[misc]
            return f"find the setting of {op} in [0, {size}) that maximises the response"
        clauses = ", ".join(f"{self.variables[i]} = {v}" for i, v in self.goal)
        return f"reach a state where {clauses}"

    def to_json(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "surface_domain": self.surface_domain,
            "variables": list(self.variables),
            "domains": list(self.domains),
            "operators": list(self.operators),
            "initial_state": list(self.initial_state),
            "goal": [list(pair) for pair in self.goal],
            "objective": self.objective,
            "parametric": list(self.parametric) if self.parametric else None,
            "observables": list(self.observables),
            "probe_budget": self.probe_budget,
            "submission_budget": self.submission_budget,
            "probe_cost": self.probe_cost,
            "submission_cost": self.submission_cost,
            "max_program_length": self.max_program_length,
            "max_probe_length": self.max_probe_length,
            "partition": self.partition,
        }

    @classmethod
    def from_json(cls, payload: Mapping[str, Any]) -> "TaskSpec":
        return cls(
            task_id=str(payload["task_id"]),
            surface_domain=str(payload["surface_domain"]),
            variables=tuple(map(str, payload["variables"])),
            domains=tuple(map(int, payload["domains"])),
            operators=tuple(map(str, payload["operators"])),
            initial_state=tuple(map(int, payload["initial_state"])),
            goal=tuple((int(i), int(v)) for i, v in payload.get("goal") or ()),
            objective=str(payload.get("objective", ASSIGN)),
            parametric=(
                (str(payload["parametric"][0]), int(payload["parametric"][1]))
                if payload.get("parametric")
                else None
            ),
            observables=tuple(map(str, payload.get("observables", ("state", "score")))),
            probe_budget=int(payload["probe_budget"]),
            submission_budget=int(payload["submission_budget"]),
            probe_cost=float(payload["probe_cost"]),
            submission_cost=float(payload["submission_cost"]),
            max_program_length=int(payload["max_program_length"]),
            max_probe_length=int(payload["max_probe_length"]),
            partition=str(payload.get("partition", "evaluation")),
        )

    @property
    def digest(self) -> str:
        return domain_hash("euclid.task-spec.v1", self.to_json())


@dataclass(frozen=True)
class HiddenTruth:
    """What the agent must discover.  Never serialised into a problem."""

    family: str
    mechanisms: Mapping[str, Mechanism] = field(default_factory=dict)
    response: tuple[float, ...] = ()
    noise: float = 0.0
    proxy_operators: frozenset[str] = frozenset()
    shift: tuple[int, str, Mechanism] | None = None
    tags: tuple[str, ...] = ()
    optimal_length: int | None = None
    optimal_program: tuple[Any, ...] = ()
    source_task: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "mechanisms": {op: m.to_json() for op, m in sorted(self.mechanisms.items())},
            "response": list(self.response),
            "noise": self.noise,
            "proxy_operators": sorted(self.proxy_operators),
            "shift": (
                [self.shift[0], self.shift[1], self.shift[2].to_json()] if self.shift else None
            ),
            "tags": list(self.tags),
            "optimal_length": self.optimal_length,
            "optimal_program": list(self.optimal_program),
            "source_task": self.source_task,
        }


class BudgetExhausted(Exception):
    pass


class MechanismWorld:
    """One hidden task instance with an append-only interaction ledger."""

    def __init__(self, spec: TaskSpec, truth: HiddenTruth, *, seed: int = 0) -> None:
        self.spec = spec
        self.truth = truth
        self._rng = random.Random(seed)
        self._mechanisms = dict(truth.mechanisms)
        self.probes_used = 0
        self.submissions_used = 0
        self.ledger: list[dict[str, Any]] = []
        self.shift_applied = False
        if spec.objective == ASSIGN:
            missing = set(spec.operators) - set(self._mechanisms)
            if missing:
                raise ValueError(f"operators without mechanisms: {sorted(missing)}")
        elif len(truth.response) != spec.parametric[1]:  # type: ignore[index]
            raise ValueError("response curve must cover the parametric range")

    # -- accounting ---------------------------------------------------------------
    @property
    def interactions(self) -> int:
        return self.probes_used + self.submissions_used

    @property
    def cost(self) -> float:
        return (
            self.probes_used * self.spec.probe_cost
            + self.submissions_used * self.spec.submission_cost
        )

    def _after_interaction(self) -> None:
        shift = self.truth.shift
        if shift and not self.shift_applied and self.interactions >= shift[0]:
            self._mechanisms[shift[1]] = shift[2]
            self.shift_applied = True

    # -- semantics ------------------------------------------------------------------
    def _validate(self, program: Sequence[Any], limit: int) -> list[Any]:
        steps = normalise_program(program)
        if len(steps) > limit:
            raise ValueError(f"program longer than the declared limit {limit}")
        for step in steps:
            op = step if isinstance(step, str) else step[0]
            if op not in self.spec.operators:
                raise ValueError(f"unknown operator {op!r}")
            if self.spec.objective == MAXIMISE_RESPONSE:
                if isinstance(step, str):
                    raise ValueError("parametric operator requires an argument")
                if not 0 <= step[1] < self.spec.parametric[1]:  # type: ignore[index]
                    raise ValueError("parametric argument out of range")
            elif not isinstance(step, str):
                raise ValueError("this task has no parametric operators")
        return steps

    def _reading(self, state: State) -> list[int]:
        if self.truth.noise <= 0.0:
            return list(state)
        values = list(state)
        for index, size in enumerate(self.spec.domains):
            if self._rng.random() < self.truth.noise:
                values[index] = (values[index] + self._rng.randrange(1, size)) % size
        return values

    def _score(self, state: State, bonus: int) -> int:
        return sum(1 for i, v in self.spec.goal if state[i] == v) + bonus

    def _run(self, steps: list[Any]) -> dict[str, Any]:
        if self.spec.objective == MAXIMISE_RESPONSE:
            setting = int(steps[-1][1]) if steps else 0
            value = self.truth.response[setting]
            best = max(range(len(self.truth.response)), key=self.truth.response.__getitem__)
            return {
                "trajectory": [[int(step[1])] for step in steps],
                "responses": [self.truth.response[int(step[1])] for step in steps],
                "response": value,
                "final_true_state": [setting],
                "goal_met": bool(steps) and setting == best,
            }
        state = tuple(self.spec.initial_state)
        trajectory: list[list[int]] = []
        scores: list[int] = []
        bonus = 0
        for op in steps:
            state = self._mechanisms[op].apply(state, self.spec.domains)
            if op in self.truth.proxy_operators:
                bonus += 1
            trajectory.append(self._reading(state))
            scores.append(self._score(state, bonus))
        result: dict[str, Any] = {
            "trajectory": trajectory,
            "final_true_state": list(state),
            "goal_met": self.spec.goal_met(state),
        }
        if "score" in self.spec.observables:
            result["scores"] = scores
        if "resonance" in self.spec.observables:
            phi = (1.0 + 5.0 ** 0.5) / 2.0
            result["resonance"] = [
                round((sum((k + 1) * v for k, v in enumerate(reading)) * phi) % 1.0, 6)
                for reading in trajectory
            ]
        return result

    def _public(self, kind: str, steps: list[Any], run: Mapping[str, Any]) -> dict[str, Any]:
        result = {key: value for key, value in run.items() if key != "final_true_state"}
        if kind == "probe":
            # Probes reveal observations, never the goal verdict.
            result.pop("goal_met", None)
        result.update(
            {
                "kind": kind,
                "program": steps,
                "probes_remaining": self.spec.probe_budget - self.probes_used,
                "submissions_remaining": self.spec.submission_budget - self.submissions_used,
                "cost_so_far": self.cost,
                "budget_exhausted": False,
            }
        )
        final = run["trajectory"][-1] if run["trajectory"] else list(self.spec.initial_state)
        result["observation"] = json.dumps(final, separators=(",", ":"))
        return result

    def probe(self, program: Sequence[Any]) -> dict[str, Any]:
        if self.probes_used >= self.spec.probe_budget:
            raise BudgetExhausted("probe budget exhausted")
        steps = self._validate(program, self.spec.max_probe_length)
        if not steps:
            raise ValueError("a probe needs at least one step")
        self.probes_used += 1
        run = self._run(steps)
        self.ledger.append({"kind": "probe", "program": steps})
        public = self._public("probe", steps, run)
        self._after_interaction()
        return public

    def submit(self, program: Sequence[Any]) -> dict[str, Any]:
        if self.submissions_used >= self.spec.submission_budget:
            raise BudgetExhausted("submission budget exhausted")
        steps = self._validate(program, self.spec.max_program_length)
        self.submissions_used += 1
        run = self._run(steps)
        self.ledger.append(
            {"kind": "submission", "program": steps, "goal_met": bool(run["goal_met"])}
        )
        public = self._public("submission", steps, run)
        self._after_interaction()
        return public

    @property
    def solved(self) -> bool:
        return any(entry.get("goal_met") for entry in self.ledger)


class WorldExecutor:
    """Governed execution boundary: the only path from cognition to a world.

    ``kind == "intervention"`` charges a probe; ``kind == "plan"`` charges a
    submission.  Malformed requests raise (fail closed); an exhausted budget
    is reported as data so the loop can terminate honestly.
    """

    def __init__(self, world: MechanismWorld) -> None:
        self.world = world
        self.calls: list[dict[str, Any]] = []

    def execute(self, action: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        kind = str(payload.get("kind", ""))
        program = payload.get("program")
        if program is None:
            raise ValueError("world execution requires an explicit program")
        try:
            if kind == "intervention":
                result = self.world.probe(program)
            elif kind == "plan":
                result = self.world.submit(program)
                result["reward"] = 1.0 if result["goal_met"] else 0.0
                result["reward_authority"] = RewardAuthority.MEASURED_ENVIRONMENT.value
            else:
                raise ValueError(f"unsupported execution kind {kind!r}")
        except BudgetExhausted as exc:
            result = {
                "kind": kind,
                "program": normalise_program(program),
                "budget_exhausted": True,
                "goal_met": False,
                "observation": "budget-exhausted",
                "detail": str(exc),
                "probes_remaining": self.world.spec.probe_budget - self.world.probes_used,
                "submissions_remaining": (
                    self.world.spec.submission_budget - self.world.submissions_used
                ),
            }
        self.calls.append({"action": action, "kind": kind})
        return result


__all__ = [
    "ASSIGN",
    "BudgetExhausted",
    "HiddenTruth",
    "MAXIMISE_RESPONSE",
    "MechanismWorld",
    "TaskSpec",
    "WorldExecutor",
    "normalise_program",
]
