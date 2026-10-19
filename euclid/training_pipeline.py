"""Evidence-gated training pipeline for the existing experience learner.

Partitions are explicit and frozen by contract: ``train`` tunes the learner,
``validation`` selects/passes it, and an optional ``final_test`` is evaluated
exactly once after every decision is fixed — it never influences tuning or
pass-threshold selection.  Overlap between partitions is rejected before any
training step runs: duplicate case identity, shared lineage/session/seed, or
identical case content is a hard error, never a warning.

Controls are named, not "null": a current-policy baseline, a deterministic
fixed-action control, and a seeded uniform-random uninformed control are each
recorded separately in the evidence report along with the control seed.
"""
from __future__ import annotations

import math
import random
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from hyba_substrate.memory_preservation import verified_atomic_json_write

from .checkpoint_manifest import (
    dataset_partition_fingerprint,
    sha256_file,
    write_manifest,
)
from .contracts import Experience, RewardAuthority, domain_hash
from .learning_service import LearningService

PARTITION_NAMES = ("train", "validation", "final_test")


@dataclass(frozen=True)
class TrainingCase:
    """One partition-owned training case with stable identity and lineage."""

    case_id: str
    state: Mapping[str, Any]
    lineage_id: str | None = None
    session_id: str | None = None
    seed: int | None = None

    def __post_init__(self) -> None:
        if not str(self.case_id).strip():
            raise ValueError("training cases require a stable non-empty case_id")

    def lineage_key(self) -> str:
        """Whole-lineage identity used for partition-ownership checks."""
        return self.lineage_id or self.session_id or self.case_id

    def content_key(self) -> str:
        """Full case-content identity (state + lineage + session + seed)."""
        return domain_hash(
            "euclid.training-case.v1",
            {
                "state": dict(self.state),
                "lineage_id": self.lineage_id,
                "session_id": self.session_id,
                "seed": self.seed,
            },
        )

    def as_identity(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "state": dict(self.state),
            "lineage_id": self.lineage_id,
            "session_id": self.session_id,
            "seed": self.seed,
        }


@dataclass(frozen=True)
class PartitionReport:
    partitions: Mapping[str, int]
    partition_hashes: Mapping[str, str]
    distinct_lineages: Mapping[str, int]


@dataclass(frozen=True)
class TrainingEvidence:
    task_id: str
    train_cases: int
    holdout_cases: int
    final_test_cases: int
    epochs: int
    baseline_mean: float
    trained_mean: float
    fixed_action_mean: float
    uninformed_mean: float
    final_test_mean: float | None
    improvement: float
    passed: bool
    generated_at: float
    evidence_hash: str
    boundaries: Mapping[str, bool]
    control_seed: int
    reward_range: tuple[float, float]
    controls: Mapping[str, Any]
    partitions: Mapping[str, Any]
    learner_identity: Mapping[str, Any]

    @property
    def null_mean(self) -> float:
        """Back-compat alias of the deterministic fixed-action control."""
        return self.fixed_action_mean


def validate_partitions(
    *,
    train_cases: Sequence[TrainingCase],
    validation_cases: Sequence[TrainingCase],
    final_test_cases: Sequence[TrainingCase] = (),
) -> PartitionReport:
    """Reject duplicate identity, shared lineage/session/seed, and content
    overlap across partitions.  Mandatory before any training step."""
    if not train_cases or not validation_cases:
        raise ValueError("non-empty train and validation partitions are required")
    groups = {
        "train": list(train_cases),
        "validation": list(validation_cases),
        "final_test": list(final_test_cases),
    }
    seen_ids: dict[str, str] = {}
    seen_lineage: dict[str, str] = {}
    seen_session: dict[str, str] = {}
    seen_seed: dict[int, str] = {}
    seen_content: dict[str, str] = {}
    for name, cases in groups.items():
        for case in cases:
            if case.case_id in seen_ids:
                raise ValueError(
                    f"duplicate case_id {case.case_id!r} in partitions "
                    f"{seen_ids[case.case_id]!r} and {name!r}"
                )
            seen_ids[case.case_id] = name
            lineage = case.lineage_key()
            owner = seen_lineage.get(lineage)
            if owner is not None and owner != name:
                raise ValueError(
                    f"lineage {lineage!r} is shared between partitions "
                    f"{owner!r} and {name!r}"
                )
            seen_lineage[lineage] = name
            if case.session_id:
                owner = seen_session.get(case.session_id)
                if owner is not None and owner != name:
                    raise ValueError(
                        f"session {case.session_id!r} is shared between "
                        f"partitions {owner!r} and {name!r}"
                    )
                seen_session[case.session_id] = name
            if case.seed is not None:
                owner = seen_seed.get(case.seed)
                if owner is not None and owner != name:
                    raise ValueError(
                        f"seed {case.seed} is shared between partitions "
                        f"{owner!r} and {name!r}"
                    )
                seen_seed[case.seed] = name
            # Content overlap is only meaningful once a case declares lineage
            # metadata; bare cases share state values legitimately.
            if case.lineage_id or case.session_id or case.seed is not None:
                content = case.content_key()
                owner = seen_content.get(content)
                if owner is not None and owner != name:
                    raise ValueError(
                        "identical case content appears in partitions "
                        f"{owner!r} and {name!r}"
                    )
                seen_content[content] = name
    return PartitionReport(
        partitions={name: len(cases) for name, cases in groups.items()},
        partition_hashes={
            name: dataset_partition_fingerprint(
                [case.as_identity() for case in cases]
            )["hash"]
            for name, cases in groups.items()
        },
        distinct_lineages={
            name: len({case.lineage_key() for case in cases})
            for name, cases in groups.items()
        },
    )


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
        self._actions: tuple[str, ...] = ()

    @staticmethod
    def _mean(values: Sequence[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    def _check_reward(
        self, measured: float, reward_range: tuple[float, float]
    ) -> float:
        value = float(measured)
        low, high = reward_range
        if not math.isfinite(value) or not low <= value <= high:
            raise ValueError(
                "measured reward must be finite and inside the declared "
                f"reward_range [{low},{high}]"
            )
        return value

    def _evaluate(
        self,
        task_id: str,
        cases: Sequence[TrainingCase],
        reward: Callable[[TrainingCase, str], float],
        reward_range: tuple[float, float],
        select: Callable[[TrainingCase], str] | None = None,
    ) -> float:
        values = []
        for case in cases:
            action = (
                str(select(case))
                if select is not None
                else str(
                    self.learner.select_action(
                        task_id, dict(case.state), explore=False
                    )
                )
            )
            if action not in self._actions:
                raise ValueError(
                    f"selected action {action!r} is outside the registered "
                    "action vocabulary"
                )
            values.append(self._check_reward(reward(case, action), reward_range))
        return self._mean(values)

    def _learner_checkpoint_identity(self) -> dict[str, Any]:
        identity = {
            "service_learner_is_pipeline_learner": (
                self.learning_service.experience_learner is None
                or self.learning_service.experience_learner is self.learner
            ),
            "learner_class": (
                f"{type(self.learner).__module__}."
                f"{type(self.learner).__qualname__}"
            ),
            "checkpoint_path": None,
            "checkpoint_sha256": None,
            "internal_state_hash": getattr(
                self.learner, "_last_state_hash", None
            ),
        }
        state_path = getattr(self.learner, "state_path", None)
        if state_path and Path(str(state_path)).is_file():
            identity["checkpoint_path"] = str(state_path)
            identity["checkpoint_sha256"] = sha256_file(str(state_path))
        return identity

    def run(
        self,
        *,
        task_id: str,
        actions: Sequence[str],
        train_cases: Sequence[TrainingCase],
        reward: Callable[[TrainingCase, str], float],
        validation_cases: Sequence[TrainingCase] | None = None,
        holdout_cases: Sequence[TrainingCase] | None = None,
        final_test_cases: Sequence[TrainingCase] = (),
        reward_range: tuple[float, float] = (-1.0, 1.0),
        epochs: int = 5,
        minimum_improvement: float = 0.05,
        control_seed: int | None = None,
        report_path: str | Path | None = None,
        manifest_path: str | Path | None = None,
        source_revision: str | None = None,
        dataset_id: str | None = None,
        state_schema: str = "json-object-state.v1",
        run_id: str | None = None,
    ) -> TrainingEvidence:
        run_id = str(run_id or uuid.uuid4().hex).strip()
        if not run_id or not math.isfinite(float(minimum_improvement)) or minimum_improvement < 0:
            raise ValueError("run identity and finite nonnegative improvement are required")
        if manifest_path is not None and not str(source_revision or "").strip():
            raise ValueError("manifest_path requires an injectable source_revision")
        actions = tuple(str(action) for action in actions)
        if not task_id or len(actions) < 2 or len(set(actions)) != len(actions):
            raise ValueError("task and at least two unique actions are required")
        if validation_cases is not None and holdout_cases is not None:
            raise ValueError("pass validation_cases or holdout_cases, not both")
        validation = list(
            validation_cases if validation_cases is not None else holdout_cases or ()
        )
        if not validation or epochs <= 0:
            raise ValueError(
                "non-empty validation cases and positive epochs are required"
            )
        low, high = map(float, reward_range)
        if not math.isfinite(low) or not math.isfinite(high) or high <= low:
            raise ValueError("reward_range must be finite and increasing")
        reward_range = (low, high)
        if (
            self.learning_service.experience_learner is not None
            and self.learning_service.experience_learner is not self.learner
        ):
            raise ValueError(
                "the learner object trained must be the same object the "
                "learning service mutates and that is evaluated/checkpointed"
            )
        # Mandatory partition validation before any training observation.
        report_partitions = validate_partitions(
            train_cases=train_cases,
            validation_cases=validation,
            final_test_cases=final_test_cases,
        )
        self._actions = actions
        self.learner.register_task(
            task_id,
            actions,
            reward_range=reward_range,
            metadata={"authority": "governed-training"},
        )
        baseline = self._evaluate(
            task_id, validation, reward, reward_range
        )
        fixed_action = sorted(actions)[0]
        fixed_action_mean = self._evaluate(
            task_id,
            validation,
            reward,
            reward_range,
            select=lambda _case: fixed_action,
        )
        seed = int(
            control_seed
            if control_seed is not None
            else int.from_bytes(
                domain_hash("euclid.control-seed.v1", [task_id, list(actions)])
                .encode("utf-8")[:4],
                "big",
            )
        )
        uninformed_rng = random.Random(seed)
        uninformed_mean = self._evaluate(
            task_id,
            validation,
            reward,
            reward_range,
            select=lambda _case: uninformed_rng.choice(list(actions)),
        )
        for epoch in range(epochs):
            for case in train_cases:
                state = dict(case.state)
                action = str(
                    self.learner.select_action(task_id, state, explore=True)
                )
                if action not in actions:
                    raise ValueError(
                        f"learner selected unregistered action {action!r} "
                        "during training"
                    )
                measured_reward = self._check_reward(
                    reward(case, action), reward_range
                )
                if self.learning_service.experience_learner is None:
                    self.learner.observe(
                        task_id,
                        state,
                        action,
                        measured_reward,
                        {"case_id": case.case_id, "epoch": epoch},
                        done=True,
                        metadata={"provenance": self.provenance},
                    )
                self.learning_service.record(
                    Experience(
                        experience_id="training-" + uuid.uuid4().hex,
                        mission_id=self.mission_id,
                        domain=task_id,
                        source="training-pipeline",
                        observation=state,
                        action=action,
                        outcome={"case_id": case.case_id, "epoch": epoch, "done": True},
                        reward=measured_reward,
                        reward_authority=RewardAuthority.VALIDATED_SIMULATION,
                        provenance=self.provenance,
                        uncertainty=0.0,
                        replay_id=f"{self.mission_id}:{run_id}:{task_id}:{epoch}:{case.case_id}",
                    )
                )
        trained = self._evaluate(task_id, validation, reward, reward_range)
        final_test_mean = (
            self._evaluate(task_id, final_test_cases, reward, reward_range)
            if final_test_cases
            else None
        )
        improvement = trained - baseline
        generated_at = time.time()
        learner_identity = self._learner_checkpoint_identity()
        controls = {
            "current_policy_baseline": {
                "policy": "learner-pre-training",
                "mean": baseline,
            },
            "fixed_action": {
                "action": fixed_action,
                "selection": "deterministic",
                "mean": fixed_action_mean,
            },
            "uninformed": {
                "selection": "seeded-uniform-random",
                "seed": seed,
                "mean": uninformed_mean,
            },
        }
        passed = (
            improvement >= minimum_improvement
            and trained > fixed_action_mean
            and trained > uninformed_mean
        )
        base = {
            "task_id": task_id,
            "train_cases": len(train_cases),
            "holdout_cases": len(validation),
            "final_test_cases": len(final_test_cases),
            "epochs": epochs,
            "baseline_mean": baseline,
            "trained_mean": trained,
            "fixed_action_mean": fixed_action_mean,
            "uninformed_mean": uninformed_mean,
            "final_test_mean": final_test_mean,
            "improvement": improvement,
            "passed": passed,
            "generated_at": generated_at,
            "control_seed": seed,
            "reward_range": list(reward_range),
            "controls": controls,
            "partitions": {
                "counts": dict(report_partitions.partitions),
                "hashes": dict(report_partitions.partition_hashes),
                "distinct_lineages": dict(report_partitions.distinct_lineages),
            },
            "learner_identity": learner_identity,
            "boundaries": {
                "held_out_evaluation": True,
                "named_controls": True,
                "final_test_frozen": True,
                "final_test_influenced_pass": False,
                "partition_overlap_validated": True,
                "external_validation": False,
                "general_intelligence_proven": False,
            },
        }
        report = TrainingEvidence(
            **{**base, "reward_range": tuple(reward_range)},
            evidence_hash=domain_hash("euclid.training-evidence.v1", base),
        )
        if report_path is not None:
            verified_atomic_json_write(
                Path(report_path).resolve(),
                {"schema": "euclid.training-evidence/1", **asdict(report)},
            )
        if manifest_path is not None:
            if not str(source_revision or "").strip():
                raise ValueError(
                    "manifest_path requires an injectable source_revision"
                )
            dedup = self.learning_service.replay_state()
            dataset = {
                "dataset_id": dataset_id or f"{task_id}-dataset",
                "partitions": {
                    name: dataset_partition_fingerprint(
                        [case.as_identity() for case in cases]
                    )
                    for name, cases in (
                        ("train", train_cases),
                        ("validation", validation),
                        ("final_test", final_test_cases),
                    )
                },
            }
            evidence_block = {
                "report_hash": report.evidence_hash,
                "report_path": str(report_path) if report_path else None,
                "report_sha256": (
                    sha256_file(str(report_path)) if report_path else None
                ),
            }
            write_manifest(
                manifest_path,
                source_revision=str(source_revision),
                task={
                    "task_id": task_id,
                    "actions": list(actions),
                    "reward_range": list(reward_range),
                    "state_schema": state_schema,
                },
                learner={
                    "class": learner_identity["learner_class"],
                    "checkpoint_path": learner_identity["checkpoint_path"],
                    "state_hash": learner_identity["checkpoint_sha256"],
                    "internal_state_hash": learner_identity[
                        "internal_state_hash"
                    ],
                },
                dataset=dataset,
                dedup=dedup,
                evidence=evidence_block,
            )
        return report


__all__ = [
    "PARTITION_NAMES",
    "PartitionReport",
    "TrainingCase",
    "TrainingEvidence",
    "TrainingPipeline",
    "validate_partitions",
]
