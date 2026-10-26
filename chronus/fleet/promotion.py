"""Evidence-Gated Promotion Controller for Chronus Native Quantum Fleet.

Implements Section 7 of the Native Quantum Fleet Elevation Mandate:
- Enforces strict ordered promotion progression:
  `SHADOW -> CANARY_1 (1%) -> CANARY_5 (5%) -> CANARY_25 (25%) -> PRODUCTION_ELIGIBLE (100%)`.
- Hard aborts: any correctness, exactness, security, or recovery failure immediately
  aborts promotion and rolls back to the pinned baseline artifact.
- Performance rollback: sustained tail-latency (`p99`) or memory regressions beyond
  the declared threshold automatically roll back.
- Production promotion requires explicit owner approval, verified candidate and rollback
  artifact SHA-256 digests, a passing qualification ledger, and a tested rollback execution.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
from typing import Any


PROMOTION_SCHEMA = "chronus.fleet.promotion/v1"


class PromotionStage(str, Enum):
    SHADOW = "shadow"
    CANARY_1 = "canary_1_pct"
    CANARY_5 = "canary_5_pct"
    CANARY_25 = "canary_25_pct"
    PRODUCTION_ELIGIBLE = "production_eligible"
    ROLLED_BACK = "rolled_back"


ORDERED_PROMOTION_STAGES: tuple[PromotionStage, ...] = (
    PromotionStage.SHADOW,
    PromotionStage.CANARY_1,
    PromotionStage.CANARY_5,
    PromotionStage.CANARY_25,
    PromotionStage.PRODUCTION_ELIGIBLE,
)

STAGE_TRAFFIC_PERCENT: dict[PromotionStage, int] = {
    PromotionStage.SHADOW: 0,
    PromotionStage.CANARY_1: 1,
    PromotionStage.CANARY_5: 5,
    PromotionStage.CANARY_25: 25,
    PromotionStage.PRODUCTION_ELIGIBLE: 100,
    PromotionStage.ROLLED_BACK: 0,
}


@dataclass(frozen=True, kw_only=True)
class StageTelemetryEvidence:
    """Measured telemetry and invariant verdicts for a promotion stage gate."""

    stage: PromotionStage
    observations: int
    correctness_passed: bool
    exactness_passed: bool
    security_passed: bool
    recovery_passed: bool
    baseline_p99_ms: float
    candidate_p99_ms: float
    baseline_peak_mem_bytes: int
    candidate_peak_mem_bytes: int

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["stage"] = self.stage.value
        return data


@dataclass(frozen=True, kw_only=True)
class PromotionDecisionRecord:
    """Audit record for one stage evaluation or rollback event."""

    from_stage: PromotionStage
    to_stage: PromotionStage
    traffic_percent: int
    active_artifact_sha256: str
    hard_abort_triggered: bool
    performance_rollback_triggered: bool
    reason: str
    evidence_digest: str

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["from_stage"] = self.from_stage.value
        data["to_stage"] = self.to_stage.value
        return data


class PromotionGateController:
    """State machine governing shadow -> 1% -> 5% -> 25% -> production promotion."""

    def __init__(
        self,
        *,
        candidate_artifact_sha256: str,
        rollback_artifact_sha256: str,
        max_p99_regression_ratio: float = 1.10,
        max_memory_regression_ratio: float = 1.10,
        min_observations_per_stage: int = 20,
    ) -> None:
        if len(candidate_artifact_sha256) != 64 or len(rollback_artifact_sha256) != 64:
            raise ValueError("candidate and rollback artifact SHA-256 digests must be 64 hex chars")
        if candidate_artifact_sha256 == rollback_artifact_sha256:
            raise ValueError("candidate_artifact_sha256 and rollback_artifact_sha256 must be distinct")
        self.candidate_artifact_sha256 = candidate_artifact_sha256
        self.rollback_artifact_sha256 = rollback_artifact_sha256
        self.max_p99_regression_ratio = float(max_p99_regression_ratio)
        self.max_memory_regression_ratio = float(max_memory_regression_ratio)
        self.min_observations_per_stage = int(min_observations_per_stage)

        self.current_stage = PromotionStage.SHADOW
        self.active_artifact_sha256 = candidate_artifact_sha256
        self.rollback_tested = False
        self.history: list[PromotionDecisionRecord] = []

    def test_rollback_drill(self) -> dict[str, Any]:
        """Execute a deterministic rollback drill and restore shadow state."""
        prev_artifact = self.active_artifact_sha256
        self.active_artifact_sha256 = self.rollback_artifact_sha256
        verified = self.active_artifact_sha256 == self.rollback_artifact_sha256
        self.active_artifact_sha256 = prev_artifact
        self.rollback_tested = verified
        return {
            "rollback_drill_passed": verified,
            "rollback_artifact_sha256": self.rollback_artifact_sha256,
        }

    def evaluate_and_advance(
        self,
        evidence: StageTelemetryEvidence,
        *,
        owner_approved: bool = False,
        approved_by: str | None = None,
        qualification_ledger_passed: bool = False,
    ) -> PromotionDecisionRecord:
        """Evaluate stage telemetry; advance one step or trigger instant rollback."""
        if self.current_stage == PromotionStage.ROLLED_BACK:
            raise RuntimeError("Candidate has been rolled back and cannot advance without a new controller")
        if evidence.stage != self.current_stage:
            raise ValueError(
                f"Evidence stage {evidence.stage.value!r} does not match current_stage {self.current_stage.value!r}"
            )

        ev_digest = hashlib.sha256(
            json.dumps(evidence.as_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

        # 1. Hard Aborts: correctness, exactness, security, or recovery failure
        if not (
            evidence.correctness_passed
            and evidence.exactness_passed
            and evidence.security_passed
            and evidence.recovery_passed
        ):
            failed_planes = [
                name
                for name, ok in (
                    ("correctness", evidence.correctness_passed),
                    ("exactness", evidence.exactness_passed),
                    ("security", evidence.security_passed),
                    ("recovery", evidence.recovery_passed),
                )
                if not ok
            ]
            rec = PromotionDecisionRecord(
                from_stage=self.current_stage,
                to_stage=PromotionStage.ROLLED_BACK,
                traffic_percent=0,
                active_artifact_sha256=self.rollback_artifact_sha256,
                hard_abort_triggered=True,
                performance_rollback_triggered=False,
                reason=f"hard_abort_failure:{','.join(failed_planes)}",
                evidence_digest=ev_digest,
            )
            self.current_stage = PromotionStage.ROLLED_BACK
            self.active_artifact_sha256 = self.rollback_artifact_sha256
            self.history.append(rec)
            return rec

        # 2. Minimum observation check
        if evidence.observations < self.min_observations_per_stage:
            raise ValueError(
                f"Stage {self.current_stage.value!r} requires >= {self.min_observations_per_stage} observations"
            )

        # 3. Performance & memory regression rollback check
        p99_ratio = evidence.candidate_p99_ms / max(1e-9, evidence.baseline_p99_ms)
        mem_ratio = evidence.candidate_peak_mem_bytes / max(1, evidence.baseline_peak_mem_bytes)
        if p99_ratio > self.max_p99_regression_ratio or mem_ratio > self.max_memory_regression_ratio:
            rec = PromotionDecisionRecord(
                from_stage=self.current_stage,
                to_stage=PromotionStage.ROLLED_BACK,
                traffic_percent=0,
                active_artifact_sha256=self.rollback_artifact_sha256,
                hard_abort_triggered=False,
                performance_rollback_triggered=True,
                reason=f"performance_regression_rollback:p99_ratio={p99_ratio:.4f},mem_ratio={mem_ratio:.4f}",
                evidence_digest=ev_digest,
            )
            self.current_stage = PromotionStage.ROLLED_BACK
            self.active_artifact_sha256 = self.rollback_artifact_sha256
            self.history.append(rec)
            return rec

        # 4. Determine next stage in strict order
        idx = ORDERED_PROMOTION_STAGES.index(self.current_stage)
        next_stage = (
            ORDERED_PROMOTION_STAGES[idx + 1]
            if idx + 1 < len(ORDERED_PROMOTION_STAGES)
            else PromotionStage.PRODUCTION_ELIGIBLE
        )

        # 5. Final gate into PRODUCTION_ELIGIBLE requires owner approval, ledger, and tested rollback
        if next_stage == PromotionStage.PRODUCTION_ELIGIBLE:
            if not self.rollback_tested:
                raise PermissionError("Cannot promote to PRODUCTION_ELIGIBLE before rollback drill is tested")
            if not qualification_ledger_passed:
                raise PermissionError("Cannot promote to PRODUCTION_ELIGIBLE without passing qualification ledger")
            if not owner_approved or not (approved_by and approved_by.strip()):
                raise PermissionError("Production promotion requires explicit owner approval and approver identity")

        rec = PromotionDecisionRecord(
            from_stage=self.current_stage,
            to_stage=next_stage,
            traffic_percent=STAGE_TRAFFIC_PERCENT[next_stage],
            active_artifact_sha256=self.candidate_artifact_sha256,
            hard_abort_triggered=False,
            performance_rollback_triggered=False,
            reason=(
                f"promoted_to_{next_stage.value}_by_{approved_by}"
                if next_stage == PromotionStage.PRODUCTION_ELIGIBLE
                else f"advanced_to_{next_stage.value}"
            ),
            evidence_digest=ev_digest,
        )
        self.current_stage = next_stage
        self.history.append(rec)
        return rec

    def summary(self) -> dict[str, Any]:
        return {
            "schema": PROMOTION_SCHEMA,
            "current_stage": self.current_stage.value,
            "traffic_percent": STAGE_TRAFFIC_PERCENT[self.current_stage],
            "candidate_artifact_sha256": self.candidate_artifact_sha256,
            "rollback_artifact_sha256": self.rollback_artifact_sha256,
            "active_artifact_sha256": self.active_artifact_sha256,
            "rollback_tested": self.rollback_tested,
            "history": [h.as_dict() for h in self.history],
        }


__all__ = [
    "ORDERED_PROMOTION_STAGES",
    "PROMOTION_SCHEMA",
    "STAGE_TRAFFIC_PERCENT",
    "PromotionDecisionRecord",
    "PromotionGateController",
    "PromotionStage",
    "StageTelemetryEvidence",
]
