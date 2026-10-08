"""Kairos Runtime Control Plane — deterministic, fail-closed laboratory control.

This module governs a single-operator, in-process Kairos world.  It deliberately
contains no network listener, external identity provider, distributed storage, or
multi-user execution path.  Every accepted, deferred, and rejected operation is
chronicle-linked; lifecycle errors fail closed.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping


SCHEMA = "EUCLID_KAIROS_RUNTIME_V1"


def _canonical(value: Any) -> bytes:
    def convert(item: Any) -> Any:
        if isinstance(item, Enum):
            return item.value
        if hasattr(item, "__dataclass_fields__"):
            return {key: convert(value) for key, value in asdict(item).items()}
        if isinstance(item, Mapping):
            return {str(key): convert(value) for key, value in item.items()}
        if isinstance(item, (tuple, list)):
            return [convert(value) for value in item]
        return item

    return json.dumps(convert(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def _hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


class WorldLifecycle(str, Enum):
    CREATED = "CREATED"
    BOOTSTRAPPED = "BOOTSTRAPPED"
    ACTIVE = "ACTIVE"
    CHECKPOINTED = "CHECKPOINTED"
    ARCHIVED = "ARCHIVED"
    REPLAYING = "REPLAYING"
    FAILED_CLOSED = "FAILED_CLOSED"


class RuntimeRole(str, Enum):
    CREATOR = "CREATOR"
    OPERATOR = "OPERATOR"
    AUDIENCE = "AUDIENCE"


class SessionState(str, Enum):
    OPEN = "OPEN"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CLOSED = "CLOSED"


class FoldOutcome(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"


@dataclass(frozen=True)
class RuntimeBoundary:
    runtime_mode: str = "LABORATORY"
    network_enabled: bool = False
    multi_user_enabled: bool = False
    external_providers_enabled: bool = False

    def __post_init__(self) -> None:
        if self.runtime_mode != "LABORATORY" or self.network_enabled or self.multi_user_enabled or self.external_providers_enabled:
            raise ValueError("Kairos boundary is laboratory-only and fail-closed")


@dataclass(frozen=True)
class DomainRulePack:
    domain: str
    vocabulary: tuple[str, ...]
    invariants: tuple[str, ...]
    forbidden_actions: tuple[str, ...] = ()
    evolution_drivers: tuple[str, ...] = ()
    permitted_targets: tuple[str, ...] = ()

    def permits(self, action: str, target: str | None = None) -> bool:
        if action not in self.vocabulary or action in self.forbidden_actions:
            return False
        return target is None or not self.permitted_targets or target in self.permitted_targets


@dataclass(frozen=True)
class OperatorSession:
    session_id: str
    operator_id: str
    role: RuntimeRole
    state: SessionState
    opened_at: int
    command_count: int = 0


@dataclass(frozen=True)
class FoldEvent:
    domain_from: str
    domain_to: str
    intent: str
    payload: Mapping[str, Any]
    constraints: Mapping[str, Any]
    provenance: Mapping[str, Any]


@dataclass(frozen=True)
class ChronicleEvent:
    event_id: str
    sequence: int
    kind: str
    outcome: str
    payload: Mapping[str, Any]
    previous_hash: str | None
    event_hash: str


@dataclass(frozen=True)
class RuntimeResult:
    outcome: FoldOutcome
    reason: str
    world_hash: str
    coherence: float
    volatility: float
    event_hash: str


@dataclass
class KairosWorld:
    world_id: str
    lifecycle: WorldLifecycle = WorldLifecycle.CREATED
    state: dict[str, Any] = field(default_factory=dict)
    chronicle: list[ChronicleEvent] = field(default_factory=list)
    checkpoints: dict[str, Mapping[str, Any]] = field(default_factory=dict)

    @property
    def state_hash(self) -> str:
        return _hash({"world_id": self.world_id, "lifecycle": self.lifecycle.value, "state": self.state})


DEFAULT_RULE_PACKS = {
    "frontier_city": DomainRulePack("frontier_city", ("observe", "build", "lore_add"), ("consent_required", "history_retained"), ("erase_history",), ("coherence", "stability"), ("symbolic_orchard", "fractured_commonwealth")),
    "symbolic_orchard": DomainRulePack("symbolic_orchard", ("observe", "cultivate", "lore_add"), ("motif_integrity", "consent_required"), ("corrupt_motif",), ("resonance", "balance"), ("frontier_city", "geometric_plane")),
    "fractured_commonwealth": DomainRulePack("fractured_commonwealth", ("observe", "reconcile", "lore_add"), ("no_false_echo", "history_retained"), ("falsify_echo",), ("coherence", "volatility"), ("frontier_city", "subterranean_vault")),
    "subterranean_vault": DomainRulePack("subterranean_vault", ("observe", "preserve", "lore_add"), ("custody_preserved", "governance_required"), ("override_governance",), ("stability", "risk"), ("fractured_commonwealth", "geometric_plane")),
    "geometric_plane": DomainRulePack("geometric_plane", ("observe", "transform", "lore_add"), ("provenance_linked", "symmetry_preserved"), ("break_provenance",), ("coherence", "resonance"), ("symbolic_orchard", "subterranean_vault")),
}


class KairosRuntime:
    """Single-operator control plane with hash-linked chronicle and replay."""

    def __init__(
        self,
        rule_packs: Mapping[str, DomainRulePack] | None = None,
        boundary: RuntimeBoundary | None = None,
        *,
        fold_volatility_delta: float = 0.05,
        transform_volatility_delta: float = 0.1,
        coherence_volatility_coefficient: float = 0.2,
    ) -> None:
        self.boundary = boundary or RuntimeBoundary()
        self.rule_packs = dict(rule_packs or DEFAULT_RULE_PACKS)
        if not self.rule_packs:
            raise ValueError("at least one domain rule pack required")
        # Declared world-dynamics rule: how much volatility a fold adds and how
        # much coherence volatility subtracts.  World rules, not measurements.
        self.fold_volatility_delta = float(fold_volatility_delta)
        self.transform_volatility_delta = float(transform_volatility_delta)
        self.coherence_volatility_coefficient = float(coherence_volatility_coefficient)
        self.worlds: dict[str, KairosWorld] = {}
        self.sessions: dict[str, OperatorSession] = {}

    def create_world(self, world_id: str, snapshot_hash: str) -> KairosWorld:
        if not world_id.strip() or not snapshot_hash.startswith("sha256:"):
            raise ValueError("world_id and sha256 snapshot_hash required")
        if world_id in self.worlds:
            raise ValueError("world already exists")
        world = KairosWorld(world_id, state={"snapshot_hash": snapshot_hash, "domains": {}, "coherence": 1.0, "volatility": 0.0})
        self.worlds[world_id] = world
        self._chronicle(world, "world_created", FoldOutcome.ACCEPTED.value, {"snapshot_hash": snapshot_hash})
        return world

    def bootstrap_world(self, world_id: str) -> KairosWorld:
        world = self._world(world_id)
        self._transition(world, WorldLifecycle.BOOTSTRAPPED, {WorldLifecycle.CREATED})
        self._transition(world, WorldLifecycle.ACTIVE, {WorldLifecycle.BOOTSTRAPPED})
        return world

    def load_world(self, world_id: str) -> KairosWorld:
        """Load the in-process world only after chronicle integrity verifies."""
        world = self._world(world_id)
        self.replay_world(world_id)
        return world

    def record_cns_snapshot(self, world_id: str, *, phase: str, mood: str, risk: float, volatility: float) -> ChronicleEvent:
        world = self._world(world_id)
        if world.lifecycle is not WorldLifecycle.ACTIVE:
            self._fail_closed(world, "CNS snapshot requires ACTIVE world")
            raise RuntimeError("CNS snapshot requires ACTIVE world")
        if not phase or not mood or not 0.0 <= float(risk) <= 1.0 or not 0.0 <= float(volatility) <= 1.0:
            raise ValueError("invalid CNS snapshot")
        return self._chronicle(world, "cns_snapshot", FoldOutcome.ACCEPTED.value, {"phase": phase, "mood": mood, "risk": float(risk), "volatility": float(volatility), "world_hash": world.state_hash})

    def open_session(self, operator_id: str, role: RuntimeRole = RuntimeRole.OPERATOR) -> OperatorSession:
        if role is not RuntimeRole.OPERATOR:
            raise PermissionError("only OPERATOR may execute in laboratory runtime")
        if any(session.state in {SessionState.OPEN, SessionState.ACTIVE, SessionState.SUSPENDED} for session in self.sessions.values()):
            raise PermissionError("concurrent operator session rejected")
        logical_time = len(self.sessions) + 1
        session_id = "session-" + _hash({"operator": operator_id, "time": logical_time}).split(":", 1)[1][:20]
        session = OperatorSession(session_id, operator_id, role, SessionState.OPEN, logical_time)
        self.sessions[session_id] = session
        return session

    def activate_session(self, session_id: str) -> OperatorSession:
        session = self._session(session_id)
        if session.state is not SessionState.OPEN:
            raise PermissionError("only an open session may activate")
        active = OperatorSession(session.session_id, session.operator_id, session.role, SessionState.ACTIVE, session.opened_at, session.command_count)
        self.sessions[session_id] = active
        return active

    def close_session(self, session_id: str) -> OperatorSession:
        session = self._session(session_id)
        closed = OperatorSession(session.session_id, session.operator_id, session.role, SessionState.CLOSED, session.opened_at, session.command_count)
        self.sessions[session_id] = closed
        return closed

    def checkpoint_world(self, world_id: str) -> str:
        world = self._world(world_id)
        if world.lifecycle is not WorldLifecycle.ACTIVE:
            self._fail_closed(world, "checkpoint requires ACTIVE world")
            raise RuntimeError("checkpoint requires ACTIVE world")
        checkpoint_id = "checkpoint-" + _hash({"world": world.state_hash, "sequence": len(world.chronicle)}).split(":", 1)[1][:20]
        world.checkpoints[checkpoint_id] = {"state": json.loads(_canonical(world.state)), "chronicle": tuple(world.chronicle), "state_hash": world.state_hash}
        self._transition(world, WorldLifecycle.CHECKPOINTED, {WorldLifecycle.ACTIVE})
        self._transition(world, WorldLifecycle.ACTIVE, {WorldLifecycle.CHECKPOINTED})
        self._chronicle(world, "checkpoint", FoldOutcome.ACCEPTED.value, {"checkpoint_id": checkpoint_id, "state_hash": world.state_hash})
        return checkpoint_id

    def restore_world(self, world_id: str, checkpoint_id: str) -> KairosWorld:
        world = self._world(world_id)
        checkpoint = world.checkpoints.get(checkpoint_id)
        if checkpoint is None:
            self._fail_closed(world, "checkpoint unavailable")
            raise KeyError("checkpoint unavailable")
        world.state = json.loads(json.dumps(checkpoint["state"]))
        world.chronicle = list(checkpoint["chronicle"])
        if world.state_hash != checkpoint["state_hash"]:
            self._fail_closed(world, "checkpoint hash mismatch")
            raise RuntimeError("checkpoint hash mismatch")
        world.lifecycle = WorldLifecycle.ACTIVE
        self._chronicle(world, "world_restored", FoldOutcome.ACCEPTED.value, {"checkpoint_id": checkpoint_id})
        return world

    def archive_world(self, world_id: str) -> KairosWorld:
        world = self._world(world_id)
        self._transition(world, WorldLifecycle.ARCHIVED, {WorldLifecycle.ACTIVE})
        return world

    def dispatch_fold(self, world_id: str, session_id: str, event: FoldEvent) -> RuntimeResult:
        world = self._world(world_id)
        session = self._session(session_id)
        if world.lifecycle is not WorldLifecycle.ACTIVE:
            return self._reject(world, "world is not active", event)
        if session.state is not SessionState.ACTIVE or session.role is not RuntimeRole.OPERATOR:
            return self._reject(world, "inactive or unauthorised operator session", event)
        source, target = self.rule_packs.get(event.domain_from), self.rule_packs.get(event.domain_to)
        if source is None or target is None:
            return self._reject(world, "unknown Fold domain", event)
        if event.domain_from == event.domain_to:
            return self._reject(world, "self-transition forbidden", event)
        if not source.permits(event.intent, event.domain_to):
            return self._reject(world, "source rule pack rejected Fold action", event)
        violations = tuple(event.constraints.get("invariant_violations", ()))
        if violations:
            return self._reject(world, "declared domain invariant violation", event)
        if event.constraints.get("defer"):
            return self._defer(world, "explicit deferral constraint", event)
        if not isinstance(event.payload, Mapping) or not isinstance(event.provenance, Mapping):
            return self._reject(world, "payload and provenance must be mappings", event)

        domains = dict(world.state.get("domains", {}))
        domains[event.domain_from] = {"last_action": event.intent, "payload_hash": _hash(event.payload)}
        domains[event.domain_to] = {"resonance_from": event.domain_from, "resonance_hash": _hash({"from": event.domain_from, "provenance": event.provenance})}
        volatility = min(
            1.0,
            float(world.state.get("volatility", 0.0))
            + self.fold_volatility_delta
            + (self.transform_volatility_delta if event.intent == "transform" else 0.0),
        )
        coherence = max(0.0, 1.0 - volatility * self.coherence_volatility_coefficient)
        world.state = {**world.state, "domains": domains, "coherence": coherence, "volatility": volatility}
        record = self._chronicle(world, "fold", FoldOutcome.ACCEPTED.value, {"event": event, "state_hash": world.state_hash, "coherence": coherence, "volatility": volatility})
        self.sessions[session_id] = OperatorSession(session.session_id, session.operator_id, session.role, session.state, session.opened_at, session.command_count + 1)
        return RuntimeResult(FoldOutcome.ACCEPTED, "governed Fold accepted", world.state_hash, coherence, volatility, record.event_hash)

    def replay_world(self, world_id: str, from_event_id: str | None = None, to_event_id: str | None = None) -> Mapping[str, Any]:
        world = self._world(world_id)
        original_lifecycle = world.lifecycle
        if original_lifecycle not in {WorldLifecycle.ACTIVE, WorldLifecycle.ARCHIVED}:
            raise RuntimeError("replay requires active or archived world")
        events = world.chronicle
        start = next((index for index, item in enumerate(events) if item.event_id == from_event_id), 0) if from_event_id else 0
        end = next((index for index, item in enumerate(events) if item.event_id == to_event_id), len(events) - 1) if to_event_id else len(events) - 1
        if start > end or start < 0 or end >= len(events):
            raise ValueError("invalid replay event range")
        previous = None
        for item in events:
            expected = _hash({"sequence": item.sequence, "kind": item.kind, "outcome": item.outcome, "payload": item.payload, "previous": previous})
            if item.previous_hash != previous or item.event_hash != expected:
                self._fail_closed(world, "chronicle integrity failure")
                raise RuntimeError("chronicle integrity failure")
            previous = item.event_hash
        selection = events[start : end + 1]
        return {"schema": SCHEMA, "world_id": world_id, "from_event_id": selection[0].event_id, "to_event_id": selection[-1].event_id, "event_hashes": tuple(item.event_hash for item in selection), "world_hash": world.state_hash, "coherence": world.state["coherence"], "volatility": world.state["volatility"]}

    def _reject(self, world: KairosWorld, reason: str, event: FoldEvent) -> RuntimeResult:
        record = self._chronicle(world, "fold_rejected", FoldOutcome.REJECTED.value, {"reason": reason, "event": event, "state_hash": world.state_hash})
        return RuntimeResult(FoldOutcome.REJECTED, reason, world.state_hash, float(world.state.get("coherence", 0.0)), float(world.state.get("volatility", 0.0)), record.event_hash)

    def _defer(self, world: KairosWorld, reason: str, event: FoldEvent) -> RuntimeResult:
        record = self._chronicle(world, "fold_deferred", FoldOutcome.DEFERRED.value, {"reason": reason, "event": event, "state_hash": world.state_hash})
        return RuntimeResult(FoldOutcome.DEFERRED, reason, world.state_hash, float(world.state.get("coherence", 0.0)), float(world.state.get("volatility", 0.0)), record.event_hash)

    def _transition(self, world: KairosWorld, target: WorldLifecycle, allowed: set[WorldLifecycle]) -> None:
        if world.lifecycle not in allowed:
            self._fail_closed(world, f"invalid lifecycle transition {world.lifecycle.value}->{target.value}")
            raise RuntimeError("invalid lifecycle transition")
        world.lifecycle = target
        self._chronicle(world, "lifecycle", FoldOutcome.ACCEPTED.value, {"lifecycle": target.value})

    def _fail_closed(self, world: KairosWorld, reason: str) -> None:
        world.lifecycle = WorldLifecycle.FAILED_CLOSED
        self._chronicle(world, "failed_closed", FoldOutcome.REJECTED.value, {"reason": reason})

    def _chronicle(self, world: KairosWorld, kind: str, outcome: str, payload: Mapping[str, Any]) -> ChronicleEvent:
        previous = world.chronicle[-1].event_hash if world.chronicle else None
        body = {"sequence": len(world.chronicle), "kind": kind, "outcome": outcome, "payload": payload, "previous": previous}
        record = ChronicleEvent("chronicle-" + _hash(body).split(":", 1)[1][:20], body["sequence"], kind, outcome, dict(payload), previous, _hash(body))
        world.chronicle.append(record)
        return record

    def _world(self, world_id: str) -> KairosWorld:
        if world_id not in self.worlds:
            raise KeyError("world unavailable")
        return self.worlds[world_id]

    def _session(self, session_id: str) -> OperatorSession:
        if session_id not in self.sessions:
            raise KeyError("session unavailable")
        return self.sessions[session_id]


__all__ = [
    "SCHEMA", "WorldLifecycle", "RuntimeRole", "SessionState", "FoldOutcome", "RuntimeBoundary", "DomainRulePack", "OperatorSession", "FoldEvent", "ChronicleEvent", "RuntimeResult", "KairosWorld", "DEFAULT_RULE_PACKS", "KairosRuntime",
]
