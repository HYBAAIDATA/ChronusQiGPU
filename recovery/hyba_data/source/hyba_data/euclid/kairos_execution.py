"""Kairos Runtime Execution Layer — bounded in-process world evolution.

The execution layer sits above the Kairos control plane.  It has no transport,
provider, rendering, SDK, multi-user, or distributed-persistence capability.
It turns an authorised operator action into a governed Fold, deterministic
rule-pack state transition, CNS snapshot, and hash-linked chronicle record.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from .kairos_runtime import FoldEvent, FoldOutcome, KairosRuntime, RuntimeResult


@dataclass(frozen=True)
class OperatorAction:
    domain_from: str
    domain_to: str
    intent: str
    payload: Mapping[str, Any]
    constraints: Mapping[str, Any]
    provenance: Mapping[str, Any]


@dataclass(frozen=True)
class DomainTransition:
    domain: str
    action: str
    local_revision: int
    evolution: Mapping[str, float]
    state_hash: str


@dataclass(frozen=True)
class FoldExecution:
    outcome: FoldOutcome
    control: RuntimeResult
    coherence_delta: float
    volatility_impact: float
    resonance_triggered: bool
    source_transition: DomainTransition | None
    target_transition: DomainTransition | None
    cns_event_hash: str | None


class DomainExecutionEngine:
    """Applies only rule-pack-authorised local state and driver evolution."""

    def __init__(self, runtime: KairosRuntime) -> None:
        self.runtime = runtime

    def apply(self, world_id: str, domain: str, action: str, payload: Mapping[str, Any]) -> DomainTransition:
        world = self.runtime.load_world(world_id)
        pack = self.runtime.rule_packs[domain]
        if not pack.permits(action):
            raise PermissionError("domain execution rejected by rule pack")
        domains = dict(world.state.get("domains", {}))
        prior = dict(domains.get(domain, {}))
        revision = int(prior.get("local_revision", 0)) + 1
        # Driver increments are deterministic and bounded.  They express a
        # laboratory state transition, not physics, ecology, or politics.
        evolution = dict(prior.get("evolution", {}))
        for driver in pack.evolution_drivers:
            step = 0.02 if driver in {"coherence", "stability", "resonance", "balance"} else 0.01
            evolution[driver] = min(1.0, round(float(evolution.get(driver, 0.0)) + step, 8))
        local = {
            **prior,
            "last_action": action,
            "payload_hash": self._hash(payload),
            "local_revision": revision,
            "evolution": evolution,
            "invariants": pack.invariants,
        }
        domains[domain] = local
        world.state = {**world.state, "domains": domains}
        self.runtime._chronicle(world, "domain_execution", FoldOutcome.ACCEPTED.value, {"domain": domain, "action": action, "local_revision": revision, "evolution": evolution, "state_hash": world.state_hash})
        return DomainTransition(domain, action, revision, evolution, world.state_hash)

    @staticmethod
    def _hash(value: Any) -> str:
        from .kairos_runtime import _hash
        return _hash(value)


class FoldExecutionEngine:
    """Routes governed Folds and records measurable in-process deltas."""

    def __init__(self, runtime: KairosRuntime, domains: DomainExecutionEngine) -> None:
        self.runtime = runtime
        self.domains = domains

    def execute(self, world_id: str, session_id: str, action: OperatorAction) -> FoldExecution:
        world = self.runtime.load_world(world_id)
        before_coherence = float(world.state["coherence"])
        before_volatility = float(world.state["volatility"])
        event = FoldEvent(action.domain_from, action.domain_to, action.intent, action.payload, action.constraints, action.provenance)
        control = self.runtime.dispatch_fold(world_id, session_id, event)
        if control.outcome is not FoldOutcome.ACCEPTED:
            return FoldExecution(control.outcome, control, 0.0, 0.0, False, None, None, None)
        source = self.domains.apply(world_id, action.domain_from, action.intent, action.payload)
        target = self.domains.apply(world_id, action.domain_to, "observe", {"resonance_from": action.domain_from, "fold_event": control.event_hash})
        world = self.runtime.load_world(world_id)
        coherence_delta = round(float(world.state["coherence"]) - before_coherence, 8)
        volatility_impact = round(float(world.state["volatility"]) - before_volatility, 8)
        resonance = action.intent in {"build", "cultivate", "reconcile", "preserve", "transform"}
        self.runtime._chronicle(world, "fold_execution", FoldOutcome.ACCEPTED.value, {"control_event_hash": control.event_hash, "coherence_delta": coherence_delta, "volatility_impact": volatility_impact, "resonance_triggered": resonance, "source_state_hash": source.state_hash, "target_state_hash": target.state_hash})
        phase = "COHERENT" if float(world.state["coherence"]) >= 0.85 else "GUARDED"
        mood = "CURIOUS" if resonance else "REFLECTIVE"
        cns = self.runtime.record_cns_snapshot(world_id, phase=phase, mood=mood, risk=round(1 - float(world.state["coherence"]), 8), volatility=float(world.state["volatility"]))
        return FoldExecution(control.outcome, control, coherence_delta, volatility_impact, resonance, source, target, cns.event_hash)


class KairosExecutionLayer:
    """Operator execution loop and local world-state reporting surface."""

    def __init__(self, runtime: KairosRuntime | None = None) -> None:
        self.runtime = runtime or KairosRuntime()
        self._enforce_boundary()
        self.domains = DomainExecutionEngine(self.runtime)
        self.fold_engine = FoldExecutionEngine(self.runtime, self.domains)

    def execute(self, world_id: str, session_id: str, action: OperatorAction) -> FoldExecution:
        self._enforce_boundary()
        return self.fold_engine.execute(world_id, session_id, action)

    def run(self, world_id: str, session_id: str, actions: Sequence[OperatorAction]) -> tuple[FoldExecution, ...]:
        return tuple(self.execute(world_id, session_id, action) for action in actions)

    def world_state(self, world_id: str) -> Mapping[str, Any]:
        self._enforce_boundary()
        world = self.runtime.load_world(world_id)
        return {"world_id": world.world_id, "lifecycle": world.lifecycle.value, "world_hash": world.state_hash, "state": dict(world.state), "chronicle_head": world.chronicle[-1].event_hash if world.chronicle else None, "boundary": asdict(self.runtime.boundary)}

    def _enforce_boundary(self) -> None:
        boundary = self.runtime.boundary
        if boundary.runtime_mode != "LABORATORY" or boundary.network_enabled or boundary.multi_user_enabled or boundary.external_providers_enabled:
            raise RuntimeError("execution layer boundary violation")


__all__ = ["OperatorAction", "DomainTransition", "FoldExecution", "DomainExecutionEngine", "FoldExecutionEngine", "KairosExecutionLayer"]
