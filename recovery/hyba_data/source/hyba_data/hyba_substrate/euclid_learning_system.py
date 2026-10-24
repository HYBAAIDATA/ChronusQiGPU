"""EUCLID governed developmental learning system.

The system distinguishes seeded knowledge, experience-derived capability,
novel derivation, and independently validated discovery. It provides an
append-only learning-event ledger, multi-form memory, active curriculum,
evidence-gated claim promotion, consolidation, and durable checkpoints.

This module does not claim AGI/ASI or universal computability. It creates the
instrumentation required to test learning and discovery without self-award.
"""
from __future__ import annotations

import json
import math
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

from .memory_preservation import (
    MemoryVault,
    canonical_json_bytes,
    sha256_bytes,
    verified_atomic_json_write,
)

SCHEMA_VERSION = "HYBA_EUCLID_LEARNING_V1"
IDENTITY = "EUCLID"


class MemoryKind(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    CAUSAL = "causal"
    COUNTERFACTUAL = "counterfactual"
    FAILURE = "failure"
    META = "meta"


class ClaimStage(str, Enum):
    SEEDED = "seeded"
    HYPOTHESIZED = "hypothesized"
    INTERNALLY_REPRODUCED = "internally_reproduced"
    ADVERSARIALLY_TESTED = "adversarially_tested"
    EXTERNALLY_COMPARED = "externally_compared"
    PROVISIONALLY_TRUSTED = "provisionally_trusted"
    REFUTED = "refuted"


class EvidenceKind(str, Enum):
    INTERNAL_REPRODUCTION = "internal_reproduction"
    ADVERSARIAL_TEST = "adversarial_test"
    EXTERNAL_COMPARISON = "external_comparison"
    OPERATOR_REVIEW = "operator_review"


@dataclass(frozen=True)
class SeedRecord:
    seed_id: str
    domain: str
    statement: str
    provenance: str
    content_hash: str
    created_at: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LearningEvent:
    event_id: str
    timestamp: float
    domain: str
    memory_kind: str
    observation: Any
    prediction: Any
    action: Any
    outcome: Any
    prediction_error: float
    uncertainty: float
    attribution: dict[str, float]
    modules: tuple[str, ...]
    resource_cost: float
    generalized: bool
    previous_event_hash: str | None
    event_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ClaimEvidence:
    evidence_id: str
    kind: str
    passed: bool
    event_ids: tuple[str, ...]
    issuer: str
    reference_id: str | None
    operator_approved: bool
    timestamp: float
    notes: str = ""


@dataclass
class KnowledgeClaim:
    claim_id: str
    domain: str
    statement: str
    derivation: str
    source_seed_ids: tuple[str, ...]
    novel_relative_to_seeds: bool
    stage: str
    confidence: float
    created_at: float
    evidence: list[ClaimEvidence] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CurriculumTask:
    task_id: str
    domain: str
    claim_id: str | None
    objective: str
    acceptance_criteria: tuple[str, ...]
    priority: float
    reason: str


@dataclass(frozen=True)
class ConsolidationSnapshot:
    snapshot_id: str
    timestamp: float
    seed_count: int
    event_count: int
    claim_count: int
    trusted_claim_count: int
    refuted_claim_count: int
    mean_prediction_error: float
    mean_uncertainty: float
    generalization_rate: float
    replay_event_ids: tuple[str, ...]
    semantic_concepts: int
    state_digest: str


class EuclidLearningSystem:
    """Evidence-first continual learning and active curriculum controller."""

    _INTERNAL_ISSUERS = {"euclid", "hyba", "hyba_internal", "internal", "self"}

    def __init__(
        self,
        state_path: str | Path | None = None,
        *,
        archive_roots: Sequence[str | Path] | None = None,
        feedback_core: Any | None = None,
    ) -> None:
        self.state_path = str(Path(state_path).resolve()) if state_path else None
        self.archive_roots = tuple(Path(root).resolve() for root in (archive_roots or ()))
        self.feedback_core = feedback_core
        self.seeds: dict[str, SeedRecord] = {}
        self.events: list[LearningEvent] = []
        self.claims: dict[str, KnowledgeClaim] = {}
        self.memory_index: dict[str, list[str]] = {kind.value: [] for kind in MemoryKind}
        self.snapshots: list[ConsolidationSnapshot] = []
        self._last_state_hash: str | None = None
        self.last_archive_manifest: dict[str, Any] | None = None
        if self.state_path and Path(self.state_path).exists():
            self._load()

    @staticmethod
    def _nonempty(value: Any, name: str) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError(f"{name} must not be empty")
        return text

    @staticmethod
    def _unit(value: Any, name: str) -> float:
        number = float(value)
        if not math.isfinite(number) or not 0 <= number <= 1:
            raise ValueError(f"{name} must be finite and in [0, 1]")
        return number

    @staticmethod
    def _nonnegative(value: Any, name: str) -> float:
        number = float(value)
        if not math.isfinite(number) or number < 0:
            raise ValueError(f"{name} must be finite and nonnegative")
        return number

    @staticmethod
    def _statement_hash(statement: str) -> str:
        normalized = " ".join(statement.lower().split())
        return sha256_bytes(normalized.encode("utf-8"))

    def register_seed(
        self,
        *,
        domain: str,
        statement: str,
        provenance: str,
        metadata: Mapping[str, Any] | None = None,
        persist: bool = True,
    ) -> SeedRecord:
        domain = self._nonempty(domain, "domain")
        statement = self._nonempty(statement, "statement")
        provenance = self._nonempty(provenance, "provenance")
        payload = {
            "domain": domain,
            "statement": statement,
            "provenance": provenance,
            "metadata": dict(metadata or {}),
        }
        digest = sha256_bytes(canonical_json_bytes(payload))
        seed_id = "seed-" + digest.split(":", 1)[1][:24]
        if seed_id in self.seeds:
            return self.seeds[seed_id]
        record = SeedRecord(seed_id, domain, statement, provenance, digest, time.time(), dict(metadata or {}))
        self.seeds[seed_id] = record
        if persist:
            self._checkpoint()
        return record

    @staticmethod
    def _prediction_error(prediction: Any, outcome: Any) -> float:
        if isinstance(prediction, (int, float)) and not isinstance(prediction, bool) and isinstance(outcome, (int, float)) and not isinstance(outcome, bool):
            left, right = float(prediction), float(outcome)
            if not math.isfinite(left) or not math.isfinite(right):
                raise ValueError("prediction and outcome must be finite")
            return min(1.0, abs(left - right) / max(1.0, abs(left), abs(right)))
        return 0.0 if prediction == outcome else 1.0

    def record_experience(
        self,
        *,
        domain: str,
        memory_kind: MemoryKind | str,
        observation: Any,
        prediction: Any,
        action: Any,
        outcome: Any,
        uncertainty: float,
        attribution: Mapping[str, float] | None = None,
        modules: Sequence[str] = (),
        resource_cost: float = 0.0,
        generalized: bool = False,
        prediction_error: float | None = None,
        metadata: Mapping[str, Any] | None = None,
        persist: bool = True,
    ) -> LearningEvent:
        domain = self._nonempty(domain, "domain")
        kind = MemoryKind(memory_kind).value
        uncertainty_value = self._unit(uncertainty, "uncertainty")
        cost = self._nonnegative(resource_cost, "resource_cost")
        error = self._prediction_error(prediction, outcome) if prediction_error is None else self._unit(prediction_error, "prediction_error")
        attribution_values = {}
        for name, value in dict(attribution or {}).items():
            number = float(value)
            if not math.isfinite(number) or not -1 <= number <= 1:
                raise ValueError("attribution values must be finite and in [-1, 1]")
            attribution_values[self._nonempty(name, "attribution module")] = number
        module_names = tuple(self._nonempty(item, "module") for item in modules)
        timestamp = time.time()
        previous = self.events[-1].event_hash if self.events else None
        event_base = {
            "timestamp": timestamp,
            "domain": domain,
            "memory_kind": kind,
            "observation": observation,
            "prediction": prediction,
            "action": action,
            "outcome": outcome,
            "prediction_error": error,
            "uncertainty": uncertainty_value,
            "attribution": attribution_values,
            "modules": module_names,
            "resource_cost": cost,
            "generalized": bool(generalized),
            "previous_event_hash": previous,
            "metadata": dict(metadata or {}),
        }
        event_hash = sha256_bytes(canonical_json_bytes(event_base))
        event_id = "event-" + uuid.uuid4().hex
        event_metadata = dict(metadata or {})
        if self.feedback_core is not None and module_names:
            outputs = {name: attribution_values.get(name, 0.0) for name in module_names}
            decision_id = self.feedback_core.record_decision(
                prediction,
                confidence=1.0 - uncertainty_value,
                module_outputs=outputs,
                context={"domain": domain, "event_id": event_id},
                source_id="euclid_learning",
            )
            report = self.feedback_core.process(decision_id, outcome)
            event_metadata["feedback"] = {
                "decision_id": decision_id,
                "report_id": report.report_id,
                "learning_signal": report.learning_signal,
                "calibration_score": report.calibration_score,
            }
        event = LearningEvent(
            event_id, timestamp, domain, kind, observation, prediction, action, outcome,
            error, uncertainty_value, attribution_values, module_names, cost,
            bool(generalized), previous, event_hash, event_metadata,
        )
        self.events.append(event)
        self.memory_index[kind].append(event_id)
        if error > 0.5 and event_id not in self.memory_index[MemoryKind.FAILURE.value]:
            self.memory_index[MemoryKind.FAILURE.value].append(event_id)
        if persist:
            self._checkpoint()
        return event

    def propose_claim(
        self,
        *,
        domain: str,
        statement: str,
        derivation: str,
        source_seed_ids: Sequence[str] = (),
        metadata: Mapping[str, Any] | None = None,
        persist: bool = True,
    ) -> KnowledgeClaim:
        domain = self._nonempty(domain, "domain")
        statement = self._nonempty(statement, "statement")
        derivation = self._nonempty(derivation, "derivation")
        seed_ids = tuple(source_seed_ids)
        missing = [seed_id for seed_id in seed_ids if seed_id not in self.seeds]
        if missing:
            raise ValueError(f"unknown source seeds: {missing}")
        statement_hash = self._statement_hash(statement)
        seeded_hashes = {self._statement_hash(seed.statement) for seed in self.seeds.values()}
        novel = statement_hash not in seeded_hashes
        stage = ClaimStage.HYPOTHESIZED.value if novel else ClaimStage.SEEDED.value
        digest = sha256_bytes(canonical_json_bytes({
            "domain": domain,
            "statement": statement,
            "derivation": derivation,
            "source_seed_ids": seed_ids,
        }))
        claim_id = "claim-" + digest.split(":", 1)[1][:24]
        if claim_id in self.claims:
            return self.claims[claim_id]
        claim = KnowledgeClaim(
            claim_id, domain, statement, derivation, seed_ids, novel, stage,
            0.25 if novel else 0.1, time.time(), metadata=dict(metadata or {}),
        )
        self.claims[claim_id] = claim
        if persist:
            self._checkpoint()
        return claim

    def add_claim_evidence(
        self,
        claim_id: str,
        *,
        kind: EvidenceKind | str,
        passed: bool,
        event_ids: Sequence[str] = (),
        issuer: str,
        reference_id: str | None = None,
        operator_approved: bool = False,
        notes: str = "",
        persist: bool = True,
    ) -> ClaimEvidence:
        if claim_id not in self.claims:
            raise ValueError("unknown claim")
        claim = self.claims[claim_id]
        evidence_kind = EvidenceKind(kind)
        issuer = self._nonempty(issuer, "issuer")
        ids = tuple(event_ids)
        known_events = {event.event_id for event in self.events}
        missing = [event_id for event_id in ids if event_id not in known_events]
        if missing:
            raise ValueError(f"unknown events: {missing}")
        if evidence_kind in {EvidenceKind.INTERNAL_REPRODUCTION, EvidenceKind.ADVERSARIAL_TEST} and not ids:
            raise ValueError("internal and adversarial evidence require learning events")
        current = ClaimStage(claim.stage)
        if current is ClaimStage.REFUTED:
            raise ValueError("refuted claims require a new claim version")
        target = current
        if evidence_kind is EvidenceKind.INTERNAL_REPRODUCTION:
            if current not in {ClaimStage.SEEDED, ClaimStage.HYPOTHESIZED}:
                raise ValueError("internal reproduction is out of sequence")
            target = ClaimStage.INTERNALLY_REPRODUCED if passed else ClaimStage.REFUTED
        elif evidence_kind is EvidenceKind.ADVERSARIAL_TEST:
            if current is not ClaimStage.INTERNALLY_REPRODUCED:
                raise ValueError("adversarial testing requires internal reproduction")
            target = ClaimStage.ADVERSARIALLY_TESTED if passed else ClaimStage.REFUTED
        elif evidence_kind is EvidenceKind.EXTERNAL_COMPARISON:
            if current is not ClaimStage.ADVERSARIALLY_TESTED:
                raise ValueError("external comparison requires adversarial testing")
            if issuer.lower() in self._INTERNAL_ISSUERS or not reference_id or not operator_approved:
                raise PermissionError("external evidence requires a non-internal issuer, reference, and operator approval")
            target = ClaimStage.EXTERNALLY_COMPARED if passed else ClaimStage.REFUTED
        elif evidence_kind is EvidenceKind.OPERATOR_REVIEW:
            if current is not ClaimStage.EXTERNALLY_COMPARED or not operator_approved:
                raise PermissionError("provisional trust requires approved review of external evidence")
            target = ClaimStage.PROVISIONALLY_TRUSTED if passed else ClaimStage.REFUTED
        evidence = ClaimEvidence(
            "evidence-" + uuid.uuid4().hex, evidence_kind.value, bool(passed), ids,
            issuer, reference_id, bool(operator_approved), time.time(), str(notes),
        )
        claim.evidence.append(evidence)
        claim.stage = target.value
        confidence_by_stage = {
            ClaimStage.SEEDED: 0.1,
            ClaimStage.HYPOTHESIZED: 0.25,
            ClaimStage.INTERNALLY_REPRODUCED: 0.6,
            ClaimStage.ADVERSARIALLY_TESTED: 0.75,
            ClaimStage.EXTERNALLY_COMPARED: 0.85,
            ClaimStage.PROVISIONALLY_TRUSTED: 0.95,
            ClaimStage.REFUTED: 0.0,
        }
        claim.confidence = confidence_by_stage[target]
        if target is ClaimStage.REFUTED:
            claim.contradictions.append(evidence.evidence_id)
        if persist:
            self._checkpoint()
        return evidence

    def generate_curriculum(self, limit: int = 10) -> list[CurriculumTask]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        tasks: list[CurriculumTask] = []
        progress = {
            ClaimStage.SEEDED: 0.05,
            ClaimStage.HYPOTHESIZED: 0.15,
            ClaimStage.INTERNALLY_REPRODUCED: 0.45,
            ClaimStage.ADVERSARIALLY_TESTED: 0.65,
            ClaimStage.EXTERNALLY_COMPARED: 0.85,
            ClaimStage.PROVISIONALLY_TRUSTED: 1.0,
            ClaimStage.REFUTED: 1.0,
        }
        next_step = {
            ClaimStage.SEEDED: "reproduce the seeded statement under controlled conditions",
            ClaimStage.HYPOTHESIZED: "design an internal reproduction with falsification criteria",
            ClaimStage.INTERNALLY_REPRODUCED: "run adversarial and ablation tests",
            ClaimStage.ADVERSARIALLY_TESTED: "obtain an external reference comparison",
            ClaimStage.EXTERNALLY_COMPARED: "conduct operator review of the external evidence",
        }
        for claim in self.claims.values():
            stage = ClaimStage(claim.stage)
            if stage in {ClaimStage.PROVISIONALLY_TRUSTED, ClaimStage.REFUTED}:
                continue
            disagreement = self._unit(claim.metadata.get("disagreement", 0.0), "claim disagreement")
            downstream = self._unit(claim.metadata.get("downstream_importance", 0.5), "downstream importance")
            priority = min(1.0, 0.45 * (1 - progress[stage]) + 0.3 * (1 - claim.confidence) + 0.15 * disagreement + 0.1 * downstream)
            tasks.append(CurriculumTask(
                "task-" + uuid.uuid4().hex, claim.domain, claim.claim_id,
                next_step[stage],
                ("pre-register the metric", "preserve raw evidence", "include a falsification condition", "compare against the prior stage"),
                priority, f"stage={stage.value}; confidence={claim.confidence:.3f}; disagreement={disagreement:.3f}",
            ))
        event_domains = {event.domain for event in self.events}
        for seed in self.seeds.values():
            if seed.domain not in event_domains:
                tasks.append(CurriculumTask(
                    "task-" + uuid.uuid4().hex, seed.domain, None,
                    "create the first controlled experience for this seeded domain",
                    ("make a prediction before observing the outcome", "record uncertainty", "preserve provenance"),
                    0.8, "seeded domain has no experience record",
                ))
        return sorted(tasks, key=lambda task: (-task.priority, task.domain, task.objective))[:limit]

    def consolidate(self, *, replay_limit: int = 64, persist: bool = True, archive: bool = True) -> ConsolidationSnapshot:
        if replay_limit <= 0:
            raise ValueError("replay_limit must be positive")
        ranked = sorted(self.events, key=lambda event: (event.prediction_error + event.uncertainty, event.timestamp), reverse=True)
        replay = tuple(event.event_id for event in ranked[:replay_limit])
        event_count = len(self.events)
        mean_error = sum(event.prediction_error for event in self.events) / event_count if event_count else 0.0
        mean_uncertainty = sum(event.uncertainty for event in self.events) / event_count if event_count else 0.0
        generalization_rate = sum(event.generalized for event in self.events) / event_count if event_count else 0.0
        concepts = {
            self._statement_hash(seed.statement) for seed in self.seeds.values()
        } | {
            self._statement_hash(claim.statement) for claim in self.claims.values()
            if claim.stage != ClaimStage.REFUTED.value
        }
        metrics = {
            "seed_count": len(self.seeds),
            "event_count": event_count,
            "claim_count": len(self.claims),
            "trusted_claim_count": sum(claim.stage == ClaimStage.PROVISIONALLY_TRUSTED.value for claim in self.claims.values()),
            "refuted_claim_count": sum(claim.stage == ClaimStage.REFUTED.value for claim in self.claims.values()),
            "mean_prediction_error": mean_error,
            "mean_uncertainty": mean_uncertainty,
            "generalization_rate": generalization_rate,
            "replay_event_ids": replay,
            "semantic_concepts": len(concepts),
        }
        digest = sha256_bytes(canonical_json_bytes(metrics))
        snapshot = ConsolidationSnapshot(
            "snapshot-" + uuid.uuid4().hex, time.time(), metrics["seed_count"], event_count,
            metrics["claim_count"], metrics["trusted_claim_count"], metrics["refuted_claim_count"],
            mean_error, mean_uncertainty, generalization_rate, replay, len(concepts), digest,
        )
        self.snapshots.append(snapshot)
        if persist:
            self._checkpoint()
        if archive and self.archive_roots and self.state_path:
            vault = MemoryVault(self.archive_roots)
            self.last_archive_manifest = vault.preserve_json_files(
                [self.state_path], label=f"EUCLID learning consolidation {snapshot.snapshot_id}"
            )
            vault.verify_snapshot(self.last_archive_manifest["snapshot_id"])
        return snapshot

    def evidence_report(self) -> dict[str, Any]:
        stages = {stage.value: 0 for stage in ClaimStage}
        for claim in self.claims.values():
            stages[claim.stage] += 1
        return {
            "schema": "HYBA_EUCLID_LEARNING_EVIDENCE_V1",
            "identity": IDENTITY,
            "learning_schema": SCHEMA_VERSION,
            "generated_at": time.time(),
            "counts": {
                "seeds": len(self.seeds),
                "events": len(self.events),
                "claims": len(self.claims),
                "consolidations": len(self.snapshots),
            },
            "claim_stages": stages,
            "memory_counts": {name: len(ids) for name, ids in self.memory_index.items()},
            "state_hash": self._last_state_hash,
            "event_chain_head": self.events[-1].event_hash if self.events else None,
            "curriculum": [asdict(task) for task in self.generate_curriculum()] if (self.seeds or self.claims) else [],
            "boundaries": {
                "seed_is_not_learning": True,
                "internal_evidence_is_not_external_validation": True,
                "provisional_trust_requires_external_comparison_and_operator_review": True,
                "refuted_claims_are_retained": True,
                "universal_computability_claimed": False,
                "agi_or_asi_claimed": False,
            },
        }

    def preserve_evidence(self, report_path: str | Path, *, label: str = "EUCLID learning evidence") -> dict[str, Any] | None:
        report_path = Path(report_path).resolve()
        verified_atomic_json_write(report_path, self.evidence_report())
        if not self.archive_roots:
            return None
        files = [report_path]
        if self.state_path:
            self._checkpoint()
            files.insert(0, Path(self.state_path))
        vault = MemoryVault(self.archive_roots)
        manifest = vault.preserve_json_files(files, label=label)
        vault.verify_snapshot(manifest["snapshot_id"])
        self.last_archive_manifest = manifest
        return manifest

    def _state_payload(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA_VERSION,
            "identity": IDENTITY,
            "previous_state_hash": self._last_state_hash,
            "seeds": {key: asdict(value) for key, value in self.seeds.items()},
            "events": [asdict(value) for value in self.events],
            "claims": {key: asdict(value) for key, value in self.claims.items()},
            "memory_index": self.memory_index,
            "snapshots": [asdict(value) for value in self.snapshots],
        }

    def _checkpoint(self) -> None:
        if not self.state_path:
            return
        payload = self._state_payload()
        payload["state_hash"] = sha256_bytes(canonical_json_bytes(payload))
        verified_atomic_json_write(Path(self.state_path), payload)
        self._last_state_hash = payload["state_hash"]

    def _load(self) -> None:
        path = Path(self.state_path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        supplied_hash = payload.pop("state_hash", None)
        if payload.get("schema") != SCHEMA_VERSION or payload.get("identity") != IDENTITY:
            raise ValueError("persisted EUCLID learning state is incompatible")
        calculated = sha256_bytes(canonical_json_bytes(payload))
        if supplied_hash != calculated:
            raise ValueError("persisted EUCLID learning state hash mismatch")
        self.seeds = {key: SeedRecord(**value) for key, value in payload.get("seeds", {}).items()}
        self.events = [LearningEvent(**value) for value in payload.get("events", [])]
        self.claims = {}
        for key, value in payload.get("claims", {}).items():
            evidence = [ClaimEvidence(**item) for item in value.pop("evidence", [])]
            claim = KnowledgeClaim(**value)
            claim.evidence = evidence
            self.claims[key] = claim
        self.memory_index = {kind.value: list(payload.get("memory_index", {}).get(kind.value, [])) for kind in MemoryKind}
        self.snapshots = [ConsolidationSnapshot(**value) for value in payload.get("snapshots", [])]
        self._last_state_hash = supplied_hash
        self._validate_event_chain()

    def _validate_event_chain(self) -> None:
        previous = None
        for event in self.events:
            if event.previous_event_hash != previous:
                raise ValueError("learning event chain is discontinuous")
            event_base = {
                "timestamp": event.timestamp,
                "domain": event.domain,
                "memory_kind": event.memory_kind,
                "observation": event.observation,
                "prediction": event.prediction,
                "action": event.action,
                "outcome": event.outcome,
                "prediction_error": event.prediction_error,
                "uncertainty": event.uncertainty,
                "attribution": event.attribution,
                "modules": event.modules,
                "resource_cost": event.resource_cost,
                "generalized": event.generalized,
                "previous_event_hash": event.previous_event_hash,
                "metadata": {key: value for key, value in event.metadata.items() if key != "feedback"},
            }
            # Feedback metadata is attached after the event base hash and has its own IDs.
            if sha256_bytes(canonical_json_bytes(event_base)) != event.event_hash:
                raise ValueError("learning event hash mismatch")
            previous = event.event_hash


__all__ = [
    "SCHEMA_VERSION", "IDENTITY", "MemoryKind", "ClaimStage", "EvidenceKind",
    "SeedRecord", "LearningEvent", "ClaimEvidence", "KnowledgeClaim",
    "CurriculumTask", "ConsolidationSnapshot", "EuclidLearningSystem",
]
