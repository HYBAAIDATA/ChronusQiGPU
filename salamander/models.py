"""Typed, fail-closed contracts for Salamander #108.

Unknown and unavailable are first-class truth states.  Observation is never
reward, proposal is never execution, and action is never proof of recovery.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Mapping


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()


def digest(domain: str, value: Any) -> str:
    return hashlib.sha256(domain.encode() + b"\0" + canonical(value)).hexdigest()


class HealthState(StrEnum):
    UNKNOWN = "UNKNOWN"
    HEALTHY = "HEALTHY"
    PRESSURED = "PRESSURED"
    DEGRADED = "DEGRADED"
    QUARANTINED = "QUARANTINED"
    RECOVERING = "RECOVERING"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"


class Availability(StrEnum):
    MEASURED = "MEASURED"
    NOT_MEASURED = "NOT_MEASURED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNAVAILABLE = "UNAVAILABLE"


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class CircuitState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class BackendLifecycle(StrEnum):
    DISCOVERED = "DISCOVERED"
    QUALIFYING = "QUALIFYING"
    QUALIFIED = "QUALIFIED"
    DEGRADED = "DEGRADED"
    QUARANTINED = "QUARANTINED"
    RETIRED = "RETIRED"


class AdmissionDecision(StrEnum):
    ADMIT = "ADMIT"
    DEFER = "DEFER"
    REJECT = "REJECT"
    ISOLATE = "ISOLATE"


class ActionKind(StrEnum):
    REPLAN = "REPLAN"
    THROTTLE = "THROTTLE"
    FAILOVER = "FAILOVER"
    DEFER = "DEFER"
    REJECT = "REJECT"
    QUARANTINE = "QUARANTINE"
    REQUALIFY = "REQUALIFY"
    REBUILD_PROJECTION = "REBUILD_PROJECTION"
    RESTORE_CUSTODY = "RESTORE_CUSTODY"
    OPEN_CIRCUIT = "OPEN_CIRCUIT"
    HALF_OPEN_PROBE = "HALF_OPEN_PROBE"
    ROLLBACK = "ROLLBACK"
    CODE_DIAGNOSTIC = "CODE_DIAGNOSTIC"


class AuthorityClass(StrEnum):
    OVID_TRANSFORMATION = "OVID_TRANSFORMATION"
    THESEUS_CUSTODY = "THESEUS_CUSTODY"
    PROJECTION_REBUILDABLE = "PROJECTION_REBUILDABLE"
    CHRONUS_EXECUTION = "CHRONUS_EXECUTION"
    EUCLID_LEARNING = "EUCLID_LEARNING"
    KAIROS_REHEARSAL = "KAIROS_REHEARSAL"
    MINING_EXISTING = "MINING_EXISTING"
    SALAMANDER_ORCHESTRATION = "SALAMANDER_ORCHESTRATION"


class RewardAuthority(StrEnum):
    NONE = "NONE"
    REGISTERED_TASK = "REGISTERED_TASK"
    EXTERNAL_VERIFIER = "EXTERNAL_VERIFIER"


class DatasetPartition(StrEnum):
    TRAIN = "TRAIN"
    VALIDATION = "VALIDATION"
    FINAL_TEST = "FINAL_TEST"
    INCIDENT = "INCIDENT"
    TEMPORAL_HOLDOUT = "TEMPORAL_HOLDOUT"


class PolicyLifecycle(StrEnum):
    CANDIDATE = "CANDIDATE"
    TRAINED = "TRAINED"
    VALIDATED = "VALIDATED"
    FINAL_TESTED = "FINAL_TESTED"
    SHADOW = "SHADOW"
    CANARY = "CANARY"
    PROMOTED = "PROMOTED"
    ROLLED_BACK = "ROLLED_BACK"
    QUARANTINED = "QUARANTINED"


@dataclass(frozen=True)
class HealthObservation:
    subsystem: str
    dimension: str
    tenant_id: str
    observed_at_ns: int
    availability: Availability
    value: float | int | str | bool | None = None
    unit: str | None = None
    source: str = ""
    evidence_ref: str | None = None
    confidence: float | None = None

    def __post_init__(self) -> None:
        if not self.subsystem or not self.dimension or not self.tenant_id:
            raise ValueError("subsystem, dimension and tenant_id are required")
        if self.availability is Availability.MEASURED and self.value is None:
            raise ValueError("measured observations require a value")
        if self.availability is not Availability.MEASURED and self.value is not None:
            raise ValueError("unmeasured observations cannot carry a fabricated value")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")


@dataclass(frozen=True)
class HealthDecision:
    state: HealthState
    reasons: tuple[str, ...]
    observations: tuple[HealthObservation, ...]
    decided_at_ns: int
    policy_id: str

    @property
    def decision_id(self) -> str:
        return digest("salamander.health-decision.v1", asdict(self))


@dataclass(frozen=True)
class AutonomicEvent:
    event_id: str
    kind: str
    tenant_id: str
    subsystem: str
    severity: Severity
    observed_at_ns: int
    decision_id: str | None = None
    evidence_refs: tuple[str, ...] = ()
    attributes: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionRequest:
    action_id: str
    kind: ActionKind
    handler: str
    tenant_id: str
    target: str
    reason: str
    bounds: Mapping[str, Any]
    requires: tuple[str, ...] = ()
    idempotency_key: str = ""
    actor_id: str = ""


@dataclass(frozen=True)
class ActionResult:
    action_id: str
    status: str
    started_at_ns: int
    completed_at_ns: int
    handler: str
    before_ref: str | None
    after_ref: str | None
    verified: bool
    error: str | None = None


@dataclass(frozen=True)
class ActionVerification:
    verifier_id: str
    verified: bool
    evidence_ref: str | None
    observations: Mapping[str, Any] = field(default_factory=dict)
    error: str | None = None

    def __post_init__(self) -> None:
        if not self.verifier_id:
            raise ValueError("independent verifier identity is required")
        if self.verified and not self.evidence_ref:
            raise ValueError("verified actions require independent evidence")


@dataclass(frozen=True)
class CapabilityIdentity:
    backend_id: str
    device_id: str
    capability: str
    precision: str
    implementation_digest: str


@dataclass
class CapabilityState:
    identity: CapabilityIdentity
    lifecycle: BackendLifecycle = BackendLifecycle.DISCOVERED
    qualification_ref: str | None = None
    qualified_at_ns: int | None = None
    expires_at_ns: int | None = None
    quarantine_reason: str | None = None
    consecutive_failures: int = 0


@dataclass(frozen=True)
class TheseusRecordIdentity:
    """Stable identity for a THESEUS durable custody record.

    THESEUS owns durable record/custody/integrity/recovery/provenance.  The
    payload digest binds the custody record; it carries no transformation
    claim — representation semantics belong to OVID's lineage, not to this
    identity.
    """

    tenant_id: str
    namespace: str
    record_id: str
    payload_sha256: str
    representation: str
    version: int

    def __post_init__(self) -> None:
        if len(self.payload_sha256) != 64:
            raise ValueError("THESEUS payload digest must be SHA-256")

    @property
    def authority(self) -> AuthorityClass:
        return AuthorityClass.THESEUS_CUSTODY


@dataclass(frozen=True)
class OvidTransformEvidence:
    """OVID transformation evidence — never a custody claim.

    OVID owns representation transformation and transform
    lineage/equivalence evidence only.  The fields mirror the shared
    provenance contract aethel.ovid.TransformLineage emits; ``exactness``
    uses the TransformContract vocabulary (EXACT / BOUNDED_LOSS /
    APPROXIMATE — an UNSUPPORTED contract can never produce evidence).
    """

    VALID_EXACTNESS = ("EXACT", "BOUNDED_LOSS", "APPROXIMATE")

    tenant_id: str
    transform_id: str
    lineage_id: str
    contract_version: str
    input_sha256: str
    output_digest: str
    exactness: str

    def __post_init__(self) -> None:
        for name in ("input_sha256", "output_digest"):
            if len(getattr(self, name)) != 64:
                raise ValueError(f"OVID transform {name} must be SHA-256")
        if self.exactness not in self.VALID_EXACTNESS:
            raise ValueError("OVID transform exactness must be declared")

    @property
    def authority(self) -> AuthorityClass:
        return AuthorityClass.OVID_TRANSFORMATION


@dataclass(frozen=True)
class RebuildableProjection:
    """Rebuildable query/index/graph projection anchored to a THESEUS record.

    The projection is owned by its producer under the hyba_db contract: it
    can always be rebuilt from the durable custody record, so it is never
    the authority.  THESEUS does not own projections and OVID does not own
    custody — the anchor field makes that relationship explicit.
    """

    projection_id: str
    tenant_id: str
    custody_identity: TheseusRecordIdentity
    schema_version: str
    projection_sha256: str
    index_generation: int
    graph_generation: int
    cache_generation: int

    @property
    def authority(self) -> AuthorityClass:
        return AuthorityClass.PROJECTION_REBUILDABLE


@dataclass(frozen=True)
class LearningExperience:
    replay_id: str
    tenant_id: str
    task: str
    observation_ref: str
    action: str
    outcome_ref: str
    reward_authority: RewardAuthority
    reward: float | None
    partition: DatasetPartition
    temporal_lineage: str

    def __post_init__(self) -> None:
        if self.reward_authority is RewardAuthority.NONE and self.reward is not None:
            raise ValueError("observation is not reward")
        if self.reward_authority is not RewardAuthority.NONE and self.reward is None:
            raise ValueError("authoritative reward value is required")


@dataclass
class PolicyVersion:
    policy_id: str
    artifact_sha256: str
    dataset_snapshot_sha256: str
    lifecycle: PolicyLifecycle = PolicyLifecycle.CANDIDATE
    evidence_refs: list[str] = field(default_factory=list)
    baseline_id: str | None = None


@dataclass(frozen=True)
class OptimizationTrial:
    trial_id: str
    policy_id: str
    partition: DatasetPartition
    baseline_measurements: Mapping[str, float]
    candidate_measurements: Mapping[str, float]
    sample_count: int
    evidence_ref: str
    temporal_lineage: str

    def __post_init__(self) -> None:
        if not all((self.trial_id, self.policy_id, self.evidence_ref, self.temporal_lineage)):
            raise ValueError("optimization trial identity and evidence are required")
        if self.partition not in {
            DatasetPartition.VALIDATION,
            DatasetPartition.FINAL_TEST,
            DatasetPartition.TEMPORAL_HOLDOUT,
        }:
            raise ValueError("optimization decisions require a held-out evaluation partition")
        if self.sample_count <= 0:
            raise ValueError("optimization trial requires measured samples")
        baseline = dict(self.baseline_measurements)
        candidate = dict(self.candidate_measurements)
        if not baseline or baseline.keys() != candidate.keys():
            raise ValueError("baseline and candidate metrics must be non-empty and identical")
        if any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            for value in (*baseline.values(), *candidate.values())
        ):
            raise ValueError("optimization measurements must be finite numbers")


@dataclass(frozen=True)
class ChronusHealthEnvelope:
    backend_id: str
    device_id: str
    state: HealthState
    legal_operations: tuple[str, ...]
    prohibited_operations: tuple[str, ...]
    required_action: ActionKind
    capability_refs: tuple[str, ...]
    measured_at_ns: int
    constraints: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Admission:
    decision: AdmissionDecision
    tenant_id: str
    workload_id: str
    reason: str
    capacity_ref: str | None
    isolation_key: str
