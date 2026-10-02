"""Evidence-gated training pipeline for the existing experience learner."""
from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .contracts import Experience, RewardAuthority, domain_hash
from .evidence import atomic_write
from .learning_service import LearningService


@dataclass(frozen=True)
class TrainingCase:
    case_id: str
    state: Mapping[str, Any]


@dataclass(frozen=True)
class TrainingEvidence:
    task_id: str
    train_cases: int
    holdout_cases: int
    epochs: int
    baseline_mean: float
    trained_mean: float
    null_mean: float
    improvement: float
    passed: bool
    generated_at: float
    evidence_hash: str
    boundaries: Mapping[str, bool]


class TrainingPipeline:
    """Train and evaluate without turning training observations into proof."""

    def __init__(
        self,
        learner: Any,
        learning_service: LearningService,
        *,
        mission_id: str,
        provenance: str,
    ) -> None:
        self.learner = learner
        self.learning_service = learning_service
        self.mission_id = mission_id
        self.provenance = provenance

    @staticmethod
    def _mean(values: Sequence[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    def _evaluate(
        self,
        task_id: str,
        cases: Sequence[TrainingCase],
        reward: Callable[[TrainingCase, str], float],
        action_override: str | None = None,
    ) -> float:
        values = []
        for case in cases:
            action = action_override or str(
                self.learner.select_action(task_id, dict(case.state), explore=False)
            )
            values.append(float(reward(case, action)))
        return self._mean(values)

    def run(
        self,
        *,
        task_id: str,
        actions: Sequence[str],
        train_cases: Sequence[TrainingCase],
        holdout_cases: Sequence[TrainingCase],
        reward: Callable[[TrainingCase, str], float],
        epochs: int = 5,
        minimum_improvement: float = 0.05,
        report_path: str | Path | None = None,
    ) -> TrainingEvidence:
        actions = tuple(str(action) for action in actions)
        if not task_id or len(actions) < 2 or len(set(actions)) != len(actions):
            raise ValueError("task and at least two unique actions are required")
        if not train_cases or not holdout_cases or epochs <= 0:
            raise ValueError("non-empty train/holdout cases and positive epochs are required")
        self.learner.register_task(
            task_id,
            actions,
            reward_range=(-1.0, 1.0),
            metadata={"authority": "governed-training"},
        )
        baseline = self._evaluate(task_id, holdout_cases, reward)
        null_mean = self._evaluate(
            task_id, holdout_cases, reward, action_override=sorted(actions)[0]
        )
        for epoch in range(epochs):
            for case in train_cases:
                state = dict(case.state)
                action = str(self.learner.select_action(task_id, state, explore=True))
                measured_reward = float(reward(case, action))
                if not -1.0 <= measured_reward <= 1.0:
                    raise ValueError("training reward must be in [-1,1]")
                self.learning_service.record(
                    Experience(
                        experience_id="training-" + uuid.uuid4().hex,
                        mission_id=self.mission_id,
                        domain=task_id,
                        source="training-pipeline",
                        observation=state,
                        action=action,
                        outcome={"case_id": case.case_id, "epoch": epoch},
                        reward=measured_reward,
                        reward_authority=RewardAuthority.VALIDATED_SIMULATION,
                        provenance=self.provenance,
                        uncertainty=0.0,
                        replay_id=f"{task_id}:{epoch}:{case.case_id}",
                    )
                )
        trained = self._evaluate(task_id, holdout_cases, reward)
        improvement = trained - baseline
        generated_at = time.time()
        base = {
            "task_id": task_id,
            "train_cases": len(train_cases),
            "holdout_cases": len(holdout_cases),
            "epochs": epochs,
            "baseline_mean": baseline,
            "trained_mean": trained,
            "null_mean": null_mean,
            "improvement": improvement,
            "passed": improvement >= minimum_improvement and trained > null_mean,
            "generated_at": generated_at,
            "boundaries": {
                "held_out_evaluation": True,
                "null_control": True,
                "external_validation": False,
                "general_intelligence_proven": False,
            },
        }
        report = TrainingEvidence(
            **base,
            evidence_hash=domain_hash("euclid.training-evidence.v1", base),
        )
        if report_path is not None:
            atomic_write(
                Path(report_path),
                {"schema": "euclid.training-evidence/1", **asdict(report)},
            )
        return report


__all__ = ["TrainingCase", "TrainingEvidence", "TrainingPipeline"]