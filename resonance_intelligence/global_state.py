"""Transactional global-state coherence for EUCLID.

Candidate states are validated before commit. Critical/error violations never
silently mutate the accepted state; optional repair means rollback to the last
accepted snapshot, with an auditable repair record.
"""
from __future__ import annotations

import copy
import math
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping

from hyba_substrate.memory_preservation import canonical_json_bytes, sha256_bytes


class InvariantType(str, Enum):
    IDENTITY_CONSISTENCY = "identity_consistency"
    TEMPORAL_MONOTONICITY = "temporal_monotonicity"
    MEMORY_COHERENCE = "memory_coherence"
    BELIEF_CONSISTENCY = "belief_consistency"
    RESOURCE_CONSERVATION = "resource_conservation"


class ViolationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


ValidationFunction = Callable[["GlobalState", "GlobalState | None"], bool | tuple[bool, str]]


@dataclass(frozen=True)
class StateInvariant:
    invariant_id: str
    invariant_type: InvariantType
    description: str
    validation_fn: ValidationFunction
    severity: ViolationSeverity = ViolationSeverity.ERROR
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.invariant_id.strip() or not callable(self.validation_fn):
            raise ValueError("invariant_id must be non-empty and validation_fn callable")


@dataclass
class StateViolation:
    violation_id: str
    invariant_id: str
    invariant_type: InvariantType
    severity: ViolationSeverity
    timestamp: float
    state_snapshot: dict[str, Any]
    details: str
    previous_violation_hash: str | None = None
    violation_hash: str = ""
    resolved: bool = False
    resolution: str | None = None


@dataclass(frozen=True)
class GlobalState:
    state_id: str
    identity_signature: Mapping[str, Any]
    temporal_trace: tuple[Mapping[str, Any], ...]
    memory_state: Mapping[str, Any]
    ego_state: Mapping[str, Any]
    belief_state: Mapping[str, Any]
    resource_state: Mapping[str, Any]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.state_id.strip() or not math.isfinite(float(self.timestamp)):
            raise ValueError("state_id must be non-empty and timestamp finite")

    def get_snapshot(self) -> dict[str, Any]:
        return copy.deepcopy({
            "state_id": self.state_id, "timestamp": float(self.timestamp),
            "identity": dict(self.identity_signature), "temporal": [dict(x) for x in self.temporal_trace],
            "memory": dict(self.memory_state), "ego": dict(self.ego_state),
            "beliefs": dict(self.belief_state), "resources": dict(self.resource_state),
            "metadata": dict(self.metadata),
        })

    @property
    def state_hash(self) -> str:
        return sha256_bytes(canonical_json_bytes(self.get_snapshot()))


@dataclass(frozen=True)
class StateUpdateResult:
    accepted: bool
    candidate_state_id: str
    accepted_state_id: str | None
    violations: tuple[StateViolation, ...]
    repaired_by_rollback: bool
    state_hash: str | None


class GlobalStateManager:
    """Invariant registry and transactional global-state commit manager."""

    def __init__(self, enable_auto_repair: bool = False, max_history: int = 1000) -> None:
        if max_history <= 0:
            raise ValueError("max_history must be positive")
        self.enable_auto_repair = bool(enable_auto_repair)
        self.max_history = int(max_history)
        self.current_state: GlobalState | None = None
        self.state_history: list[GlobalState] = []
        self.invariants: dict[str, StateInvariant] = {}
        self.violations: list[StateViolation] = []
        self.repair_log: list[dict[str, Any]] = []
        self._register_default_invariants()

    def _register_default_invariants(self) -> None:
        defaults = (
            StateInvariant("identity_consistency", InvariantType.IDENTITY_CONSISTENCY,
                           "Core identity fields must remain present and stable", self._validate_identity, ViolationSeverity.CRITICAL),
            StateInvariant("temporal_monotonicity", InvariantType.TEMPORAL_MONOTONICITY,
                           "Trace and state time must be monotonic", self._validate_temporal, ViolationSeverity.ERROR),
            StateInvariant("memory_coherence", InvariantType.MEMORY_COHERENCE,
                           "A fact key may not hold contradictory canonical values", self._validate_memory, ViolationSeverity.WARNING),
            StateInvariant("belief_consistency", InvariantType.BELIEF_CONSISTENCY,
                           "A proposition and its negation may not coexist", self._validate_beliefs, ViolationSeverity.WARNING),
            StateInvariant("resource_conservation", InvariantType.RESOURCE_CONSERVATION,
                           "Resources must be finite, nonnegative, and within declared capacity", self._validate_resources, ViolationSeverity.ERROR),
        )
        for invariant in defaults:
            self.register_invariant(invariant)

    def register_invariant(self, invariant: StateInvariant, *, replace: bool = False) -> None:
        if invariant.invariant_id in self.invariants and not replace:
            raise ValueError(f"invariant already registered: {invariant.invariant_id}")
        self.invariants[invariant.invariant_id] = invariant

    def update_state(self, new_state: GlobalState, *, allow_warning_commit: bool = True) -> StateUpdateResult:
        violations = self.validate_state(new_state)
        blocking = [v for v in violations if v.severity in (ViolationSeverity.ERROR, ViolationSeverity.CRITICAL)]
        if not allow_warning_commit:
            blocking.extend(v for v in violations if v.severity is ViolationSeverity.WARNING)
        if blocking:
            repaired = False
            if self.enable_auto_repair and self.current_state is not None:
                repaired = True
                for violation in blocking:
                    violation.resolved = True
                    violation.resolution = f"candidate rejected; retained {self.current_state.state_id}"
                self.repair_log.append({"timestamp": time.time(), "candidate": new_state.state_id,
                                        "retained": self.current_state.state_id,
                                        "violation_ids": [v.violation_id for v in blocking]})
            return StateUpdateResult(False, new_state.state_id,
                                     self.current_state.state_id if self.current_state else None,
                                     tuple(violations), repaired,
                                     self.current_state.state_hash if self.current_state else None)
        if self.current_state is not None:
            self.state_history.append(self.current_state)
            self.state_history = self.state_history[-self.max_history:]
        self.current_state = copy.deepcopy(new_state)
        return StateUpdateResult(True, new_state.state_id, new_state.state_id,
                                 tuple(violations), False, new_state.state_hash)

    def validate_state(self, state: GlobalState) -> list[StateViolation]:
        detected: list[StateViolation] = []
        for invariant in self.invariants.values():
            if not invariant.enabled:
                continue
            try:
                outcome = invariant.validation_fn(state, self.current_state)
                valid, detail = outcome if isinstance(outcome, tuple) else (bool(outcome), invariant.description)
            except Exception as exc:
                valid, detail = False, f"validator error: {type(exc).__name__}: {exc}"
            if not valid:
                detected.append(self._record_violation(invariant, state, detail))
        return detected

    def _record_violation(self, invariant: StateInvariant, state: GlobalState, detail: str) -> StateViolation:
        timestamp = time.time(); previous = self.violations[-1].violation_hash if self.violations else None
        payload = {"invariant_id": invariant.invariant_id, "state_hash": state.state_hash,
                   "timestamp": timestamp, "details": detail, "previous": previous}
        digest = sha256_bytes(canonical_json_bytes(payload))
        violation = StateViolation("violation-" + uuid.uuid4().hex, invariant.invariant_id,
                                   invariant.invariant_type, invariant.severity, timestamp,
                                   state.get_snapshot(), detail, previous, digest)
        self.violations.append(violation)
        return violation

    @staticmethod
    def _validate_identity(state: GlobalState, previous: GlobalState | None) -> tuple[bool, str]:
        required = ("entity_id", "origin", "core_purpose")
        missing = [key for key in required if not str(state.identity_signature.get(key, "")).strip()]
        if missing:
            return False, f"missing core identity fields: {missing}"
        if previous:
            changed = [key for key in required if previous.identity_signature.get(key) != state.identity_signature.get(key)]
            if changed:
                return False, f"identity drift in fields: {changed}"
        return True, "identity stable"

    @staticmethod
    def _validate_temporal(state: GlobalState, previous: GlobalState | None) -> tuple[bool, str]:
        timestamps: list[float] = []
        for index, item in enumerate(state.temporal_trace):
            value = item.get("timestamp")
            if value is None or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                return False, f"invalid timestamp at trace index {index}"
            timestamps.append(float(value))
        if any(right < left for left, right in zip(timestamps, timestamps[1:])):
            return False, "temporal trace moved backwards"
        if previous and state.timestamp < previous.timestamp:
            return False, "candidate state timestamp predates accepted state"
        if previous and previous.temporal_trace and timestamps:
            last = float(previous.temporal_trace[-1].get("timestamp", previous.timestamp))
            if timestamps[-1] < last:
                return False, "candidate trace head predates accepted trace head"
        return True, "temporal order valid"

    @staticmethod
    def _validate_memory(state: GlobalState, previous: GlobalState | None) -> tuple[bool, str]:
        del previous
        facts = state.memory_state.get("facts", [])
        if not isinstance(facts, (list, tuple)):
            return False, "memory facts must be a sequence"
        seen: dict[str, bytes] = {}
        for index, fact in enumerate(facts):
            if not isinstance(fact, Mapping) or not str(fact.get("key", "")).strip():
                return False, f"invalid fact at index {index}"
            key = str(fact["key"]).strip(); value = canonical_json_bytes(fact.get("value"))
            if key in seen and seen[key] != value:
                return False, f"contradictory memory for key: {key}"
            seen[key] = value
        return True, "memory coherent"

    @staticmethod
    def _normalise_belief(item: Any) -> tuple[str, bool] | None:
        if isinstance(item, str):
            text = " ".join(item.strip().lower().split())
            if not text: return None
            for prefix in ("not ", "¬"):
                if text.startswith(prefix): return text[len(prefix):].strip(), False
            return text, True
        if isinstance(item, Mapping):
            proposition = " ".join(str(item.get("proposition", "")).strip().lower().split())
            if not proposition: return None
            return proposition, bool(item.get("truth", item.get("polarity", True)))
        return None

    @classmethod
    def _validate_beliefs(cls, state: GlobalState, previous: GlobalState | None) -> tuple[bool, str]:
        del previous
        assertions = state.belief_state.get("assertions", [])
        if not isinstance(assertions, (list, tuple)):
            return False, "belief assertions must be a sequence"
        seen: dict[str, bool] = {}
        for item in assertions:
            parsed = cls._normalise_belief(item)
            if parsed is None: return False, "belief assertion is malformed"
            proposition, truth = parsed
            if proposition in seen and seen[proposition] != truth:
                return False, f"contradictory belief: {proposition}"
            seen[proposition] = truth
        return True, "beliefs consistent"

    @staticmethod
    def _validate_resources(state: GlobalState, previous: GlobalState | None) -> tuple[bool, str]:
        del previous
        for name, raw in state.resource_state.items():
            if name in {"capacity", "total"} and isinstance(raw, Mapping):
                continue
            if isinstance(raw, (int, float)):
                value = float(raw)
                if not math.isfinite(value) or value < 0:
                    return False, f"resource {name} is non-finite or negative"
        used = state.resource_state.get("total_used")
        capacity = state.resource_state.get("total_capacity")
        if used is not None and capacity is not None and float(used) > float(capacity):
            return False, "declared resource use exceeds capacity"
        return True, "resources conserved"

    def get_state_health(self) -> dict[str, Any]:
        unresolved = [v for v in self.violations if not v.resolved]
        critical = [v for v in unresolved if v.severity is ViolationSeverity.CRITICAL]
        errors = [v for v in unresolved if v.severity is ViolationSeverity.ERROR]
        status = "critical" if critical else "degraded" if errors else "healthy"
        return {"health_status": status, "total_violations": len(self.violations),
                "unresolved_violations": len(unresolved), "critical_violations": len(critical),
                "state_history_length": len(self.state_history), "invariants_registered": len(self.invariants),
                "current_state_hash": self.current_state.state_hash if self.current_state else None,
                "repair_events": len(self.repair_log)}

    def resolve_violation(self, violation_id: str, resolution: str) -> bool:
        if not resolution.strip(): raise ValueError("resolution must be non-empty")
        for violation in self.violations:
            if violation.violation_id == violation_id:
                violation.resolved = True; violation.resolution = resolution
                return True
        return False

    def set_invariant_enabled(self, invariant_id: str, enabled: bool) -> bool:
        invariant = self.invariants.get(invariant_id)
        if invariant is None: return False
        self.invariants[invariant_id] = StateInvariant(invariant.invariant_id, invariant.invariant_type,
            invariant.description, invariant.validation_fn, invariant.severity, bool(enabled))
        return True


__all__ = ["InvariantType", "ViolationSeverity", "StateInvariant", "StateViolation",
           "GlobalState", "StateUpdateResult", "GlobalStateManager"]
