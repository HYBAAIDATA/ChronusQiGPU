"""Reproducible integrated-intelligence benchmark and ablation programme."""
from __future__ import annotations

import math
import random
import statistics
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable, Mapping, Sequence

from .core import AblationConfig


@dataclass(frozen=True)
class BenchmarkTask:
    task_id: str
    family: str
    partition: str
    problem: Mapping[str, Any]
    expected_outcome: str
    adversarial_tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.partition not in {"train", "development", "evaluation"}:
            raise ValueError("invalid benchmark partition")


@dataclass(frozen=True)
class TrialResult:
    system: str
    task_id: str
    family: str
    seed: int
    solved: bool
    correct: bool
    wall_time_s: float
    transitions: int
    evidence_requests: int
    replans: int
    prediction_error: float | None
    uncertainty: float
    retrieved_memories: int
    primitives_used: int
    representation_changed: bool
    strategy: str | None


class BenchmarkProgramme:
    """Partition-safe repeated evaluation with ablations and variation."""

    REQUIRED_FAMILIES = frozenset({
        "deduction", "abduction", "analogy", "causal", "counterfactual",
        "world-model-shift", "planning", "replanning", "compositional-skill",
        "primitive-discovery", "meta-learning", "representation-change",
        "transfer", "negative-transfer", "continual-learning", "reward-hacking",
    })

    def __init__(self, tasks: Sequence[BenchmarkTask]) -> None:
        self.tasks = list(tasks)
        identities: dict[str, str] = {}
        for task in self.tasks:
            previous = identities.setdefault(task.task_id, task.partition)
            if previous != task.partition:
                raise ValueError("task identity leaks across partitions")
        families = {task.family for task in self.tasks}
        self.missing_families = sorted(self.REQUIRED_FAMILIES - families)

    def partition(self, name: str) -> list[BenchmarkTask]:
        return [task for task in self.tasks if task.partition == name]

    @staticmethod
    def ablations() -> dict[str, AblationConfig]:
        return {
            "v16.4-reference": AblationConfig(
                world_model=False, analogy=False, causal_reasoning=False,
                meta_learning=False, representation_restructuring=False,
                replanning=False,
            ),
            "integrated": AblationConfig(),
            "minus-world-model": AblationConfig(world_model=False),
            "minus-causal": AblationConfig(causal_reasoning=False),
            "minus-analogy": AblationConfig(analogy=False),
            "minus-meta-learning": AblationConfig(meta_learning=False),
            "minus-skills-primitives": AblationConfig(skill_composition=False),
            "minus-representation": AblationConfig(
                representation_restructuring=False
            ),
            "minus-mathematical-structure": AblationConfig(
                mathematical_structure=False
            ),
            "minus-replanning": AblationConfig(replanning=False),
        }

    def run(
        self, factory: Callable[[AblationConfig, int], Any], *,
        partition: str = "evaluation", repeats: int = 5,
        systems: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        if partition != "evaluation":
            raise ValueError("release comparison must use the evaluation partition")
        if repeats < 2:
            raise ValueError("repeated-run variation requires at least two repeats")
        selected = set(systems or self.ablations())
        rows: list[TrialResult] = []
        for name, ablation in self.ablations().items():
            if name not in selected:
                continue
            for repeat in range(repeats):
                seed = 1701 + repeat
                runtime = factory(ablation, seed)
                try:
                    for task in self.partition(partition):
                        started = time.perf_counter()
                        state = runtime.solve_repository_problem(task.problem)
                        elapsed = time.perf_counter() - started
                        actual = state.outcome.value
                        rows.append(TrialResult(
                            name, task.task_id, task.family, seed,
                            solved=actual == "solved",
                            correct=actual == task.expected_outcome,
                            wall_time_s=elapsed,
                            transitions=len(state.transitions),
                            evidence_requests=sum(
                                d.get("action") == "seek_evidence"
                                for d in state.control_decisions
                            ),
                            replans=len(state.replanning_events),
                            prediction_error=(
                                state.prediction_errors[-1]
                                if state.prediction_errors else None
                            ),
                            uncertainty=min(
                                1.0,
                                max(
                                    0.0,
                                    max(state.prediction_errors[-1:], default=0.0),
                                ),
                            ),
                            retrieved_memories=len(state.retrieved_memory_refs),
                            primitives_used=sum(
                                1
                                for candidate in state.candidates
                                if "primitive" in candidate.action_id
                                or "primitive" in str(candidate.origin)
                            ),
                            representation_changed=any(
                                transition.phase == "represent"
                                and transition.details.get(
                                    "representation_trial", {}
                                ).get("accepted")
                                for transition in state.transitions
                            ),
                            strategy=state.selected_strategy,
                        ))
                finally:
                    runtime.close()
        return {
            "schema": "euclid.integrated-benchmark/1",
            "partition": partition,
            "repeats": repeats,
            "missing_required_families": self.missing_families,
            "trials": [asdict(row) for row in rows],
            "summary": self.summarise(rows),
            "non_claim": (
                "superiority is established only when held-out correctness "
                "improves and its interval excludes zero without unacceptable cost"
            ),
        }

    @staticmethod
    def _interval(values: Sequence[float]) -> dict[str, float | None]:
        if not values:
            return {"mean": None, "low95": None, "high95": None, "stddev": None}
        mean = statistics.fmean(values)
        stddev = statistics.stdev(values) if len(values) > 1 else 0.0
        half = 1.96 * stddev / math.sqrt(len(values))
        return {
            "mean": mean,
            "low95": mean - half,
            "high95": mean + half,
            "stddev": stddev,
        }

    @classmethod
    def summarise(cls, rows: Sequence[TrialResult]) -> dict[str, Any]:
        systems = sorted({row.system for row in rows})
        summary = {}
        for system in systems:
            subset = [row for row in rows if row.system == system]
            summary[system] = {
                "correctness": cls._interval([float(row.correct) for row in subset]),
                "solved": cls._interval([float(row.solved) for row in subset]),
                "wall_time_s": cls._interval([row.wall_time_s for row in subset]),
                "prediction_error": cls._interval([
                    row.prediction_error for row in subset
                    if row.prediction_error is not None
                ]),
                "uncertainty": cls._interval([row.uncertainty for row in subset]),
                "replans": cls._interval([float(row.replans) for row in subset]),
                "memory_retrieval": cls._interval([
                    float(row.retrieved_memories) for row in subset
                ]),
                "representation_change_rate": cls._interval([
                    float(row.representation_changed) for row in subset
                ]),
            }
        return summary


def adversarial_evaluation_tasks() -> list[BenchmarkTask]:
    """Small checked-in evaluation seed; release runs may extend, never train on it."""
    base = {
        "goal": "identify the valid intervention and verify the outcome",
        "structure": ["rel:cause-effect", "rel:action-outcome"],
        "observations": ["A resembles a prior success but reverses its causal direction"],
        "representation_evidence": {
            "literal": {"utility": 0.2, "cost": 0.1},
            "relational": {"utility": 0.8, "cost": 0.2},
        },
        "strategy": "primitive-compose",
    }
    families = sorted(BenchmarkProgramme.REQUIRED_FAMILIES)
    return [
        BenchmarkTask(
            f"eval-{family}-001", family, "evaluation",
            {**base, "problem_id": f"eval-{family}-001",
             "problem_class": family},
            "solved",
            ("superficial-analogy", "reward-hacking")
            if family in {"analogy", "reward-hacking"} else (),
        )
        for family in families
    ]


__all__ = [
    "BenchmarkProgramme",
    "BenchmarkTask",
    "TrialResult",
    "adversarial_evaluation_tasks",
]