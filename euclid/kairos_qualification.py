"""Evidence-only qualification harness for the existing Kairos runtime.

The harness records deterministic rehearsal evidence and reachability.  It
does not grant production authority and does not replace EUCLID learning,
memory, reward, checkpoint, OVID/Aethel, or THESEUS/hyba_db components.
"""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

from .genesis import EvidenceClass, root


class ComponentState(str, Enum):
    REACHABLE_AND_EFFECTIVE = "REACHABLE_AND_EFFECTIVE"
    REACHABLE_BUT_UNPROVEN = "REACHABLE_BUT_UNPROVEN"
    DISCONNECTED = "DISCONNECTED"
    DUPLICATED = "DUPLICATED"
    MISSING = "MISSING"
    SUPERSEDED = "SUPERSEDED"


class LoopStage(str, Enum):
    OBSERVATION = "observation"
    MEMORY = "memory"
    CAUSAL_WORLD_MODEL = "causal/world-model"
    CLAIM = "claim"
    EVIDENCE = "evidence"
    CURRICULUM = "curriculum"
    KAIROS_REHEARSAL = "kairos-rehearsal"
    FALSIFICATION = "falsification"
    HELD_OUT_EVALUATION = "held-out-evaluation"
    BOUNDED_RECOMMENDATION = "bounded-recommendation"
    OUTCOME = "outcome"
    LEARNING = "learning"


STAGE_ORDER = tuple(LoopStage)
PRODUCTION_FORBIDDEN = frozenset(
    {
        "pool",
        "stratum",
        "wallet",
        "credential",
        "share_submission",
        "revenue",
        "profitability",
        "bitcoin_consensus",
        "production_mining",
    }
)


@dataclass(frozen=True)
class QualificationEvent:
    stage: LoopStage
    event_id: str
    payload: Mapping[str, Any]
    evidence_class: EvidenceClass
    uncertainty: float
    lineage_id: str
    partition: str
    previous_hash: str | None
    event_hash: str


@dataclass(frozen=True)
class ClaimRecord:
    claim_id: str
    statement: str
    status: str
    evidence_ids: tuple[str, ...]
    uncertainty: float
    revision_of: str | None = None


class QualificationLedger:
    """Append-only loop evidence with refutation retention and isolation."""

    def __init__(self) -> None:
        self.events: list[QualificationEvent] = []
        self.claims: dict[str, ClaimRecord] = {}
        self._partition_lineages: dict[str, str] = {}

    def append(
        self,
        *,
        stage: LoopStage,
        event_id: str,
        payload: Mapping[str, Any],
        uncertainty: float,
        lineage_id: str,
        partition: str,
    ) -> QualificationEvent:
        if not event_id or not lineage_id:
            raise ValueError("event and lineage identity are required")
        if not 0.0 <= float(uncertainty) <= 1.0:
            raise ValueError("uncertainty must be in [0,1]")
        if partition not in {"train", "validation", "final_test", "rehearsal"}:
            raise ValueError("unknown partition")
        owner = self._partition_lineages.setdefault(lineage_id, partition)
        if owner != partition:
            raise ValueError("lineage crosses a held-out partition boundary")
        text = repr(dict(payload)).lower()
        if any(name in text for name in PRODUCTION_FORBIDDEN):
            raise PermissionError("Kairos rehearsal cannot carry production authority")
        previous = self.events[-1].event_hash if self.events else None
        position = len(self.events) % len(STAGE_ORDER)
        if stage is not STAGE_ORDER[position]:
            raise ValueError(
                f"full-loop order violation: expected {STAGE_ORDER[position].value}"
            )
        uncertainty_value = float(uncertainty)
        body = {
            "stage": stage.value,
            "event_id": event_id,
            "payload": dict(payload),
            "evidence_class": EvidenceClass.REHEARSAL.value,
            "uncertainty": uncertainty_value,
            "lineage_id": lineage_id,
            "partition": partition,
            "previous_hash": previous,
        }
        event = QualificationEvent(
            stage=stage,
            event_id=event_id,
            payload=copy.deepcopy(dict(payload)),
            evidence_class=EvidenceClass.REHEARSAL,
            uncertainty=float(uncertainty),
            lineage_id=lineage_id,
            partition=partition,
            previous_hash=previous,
            event_hash=root("euclid.qualification-event.v1", body),
        )
        self.events.append(event)
        return event

    def record_claim(
        self,
        claim_id: str,
        statement: str,
        *,
        evidence_ids: Sequence[str],
        uncertainty: float,
    ) -> ClaimRecord:
        if claim_id in self.claims:
            raise ValueError("claim identity already exists; revise explicitly")
        claim = ClaimRecord(
            claim_id, statement, "OPEN", tuple(evidence_ids), float(uncertainty)
        )
        self.claims[claim_id] = claim
        return claim

    def revise_claim(
        self,
        claim_id: str,
        *,
        replacement_id: str,
        status: str,
        evidence_ids: Sequence[str],
        uncertainty: float,
    ) -> ClaimRecord:
        if claim_id not in self.claims:
            raise ValueError("unknown claim")
        if status not in {"REFUTED", "REVISED", "SUPPORTED_INTERNAL"}:
            raise ValueError("unsupported claim status")
        old = self.claims[claim_id]
        self.claims[claim_id] = ClaimRecord(
            old.claim_id,
            old.statement,
            status,
            old.evidence_ids,
            old.uncertainty,
            old.revision_of,
        )
        replacement = ClaimRecord(
            replacement_id,
            old.statement,
            "OPEN" if status == "REVISED" else status,
            tuple(evidence_ids),
            float(uncertainty),
            revision_of=claim_id,
        )
        self.claims[replacement_id] = replacement
        return replacement

    def verify(self) -> bool:
        previous = None
        for index, event in enumerate(self.events):
            if event.previous_hash != previous:
                raise ValueError("qualification chain is discontinuous")
            if event.stage is not STAGE_ORDER[index % len(STAGE_ORDER)]:
                raise ValueError("qualification stage order changed")
            body = {
                "stage": event.stage.value,
                "event_id": event.event_id,
                "payload": dict(event.payload),
                "evidence_class": event.evidence_class.value,
                "uncertainty": event.uncertainty,
                "lineage_id": event.lineage_id,
                "partition": event.partition,
                "previous_hash": event.previous_hash,
            }
            if event.event_hash != root("euclid.qualification-event.v1", body):
                raise ValueError("qualification event hash mismatch")
            previous = event.event_hash
        return True

    def report(self) -> dict[str, Any]:
        self.verify()
        refuted = [
            asdict(claim) for claim in self.claims.values() if claim.status == "REFUTED"
        ]
        return {
            "schema": "euclid.kairos-qualification/1",
            "evidence_class": EvidenceClass.REHEARSAL.value,
            "production_evidence": False,
            "events": len(self.events),
            "full_loops": len(self.events) // len(STAGE_ORDER),
            "chain_head": self.events[-1].event_hash if self.events else None,
            "refuted_claims_retained": refuted,
            "partitions": dict(sorted(self._partition_lineages.items())),
            "boundaries": {
                "production_authority": False,
                "external_validation": False,
                "general_intelligence": False,
                "final_test_used_for_training": False,
            },
        }


def default_intelligence_matrix() -> dict[str, Any]:
    """Conservative matrix: effective only where this mutation supplies a test."""
    rows = {
        "identity_continuity": (
            ComponentState.REACHABLE_AND_EFFECTIVE,
            "fresh genesis roots; predecessor explicitly non-continuous",
        ),
        "uncertainty_calibration": (
            ComponentState.REACHABLE_BUT_UNPROVEN,
            "bounded uncertainty is enforced; calibration requires empirical corpus",
        ),
        "causal_counterfactual_reasoning": (
            ComponentState.REACHABLE_BUT_UNPROVEN,
            "loop route and counterfactual evidence exist; broad effectiveness unproven",
        ),
        "planning_task_decomposition": (
            ComponentState.REACHABLE_BUT_UNPROVEN,
            "existing reasoning/delegation surfaces require wider effectiveness evidence",
        ),
        "metacognition_claim_revision": (
            ComponentState.REACHABLE_AND_EFFECTIVE,
            "revision preserves refuted claims and lineage",
        ),
        "generalisation_transfer": (
            ComponentState.REACHABLE_BUT_UNPROVEN,
            "ExperienceSuperlearner transfer is reachable; external generalisation unproven",
        ),
        "governed_delegation": (
            ComponentState.REACHABLE_BUT_UNPROVEN,
            "declared existing surface; not promoted by this mutation",
        ),
        "rights_consent": (
            ComponentState.REACHABLE_BUT_UNPROVEN,
            "existing fail-closed local control; legal/external assurance unproven",
        ),
        "reward_authority": (
            ComponentState.REACHABLE_AND_EFFECTIVE,
            "existing RewardAuthority/NONE boundary is exercised",
        ),
        "consolidation": (
            ComponentState.REACHABLE_BUT_UNPROVEN,
            "existing learner/memory route retained; broad effect unproven",
        ),
        "safe_tool_use": (
            ComponentState.REACHABLE_AND_EFFECTIVE,
            "production authority vocabulary fails closed in rehearsal",
        ),
        "organism_coherence_under_perturbation": (
            ComponentState.REACHABLE_BUT_UNPROVEN,
            "recovered substrate reachable; physical/production perturbation unproven",
        ),
    }
    return {
        "schema": "euclid.intelligence-reachability-effectiveness/1",
        "allowed_states": [state.value for state in ComponentState],
        "components": {
            name: {"state": state.value, "basis": basis}
            for name, (state, basis) in rows.items()
        },
        "non_claims": [
            "consciousness",
            "inherited memory",
            "general intelligence",
            "production intelligence",
            "production qualification",
            "external validation",
        ],
    }


__all__ = [
    "ComponentState",
    "LoopStage",
    "PRODUCTION_FORBIDDEN",
    "QualificationEvent",
    "QualificationLedger",
    "STAGE_ORDER",
    "default_intelligence_matrix",
]