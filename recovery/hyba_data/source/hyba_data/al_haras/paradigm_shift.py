"""AL HARAS Paradigm Shift — from detection to state-governance control plane.

The old model: recognise attacks and alert humans.
The new model: define a permission manifold of allowed system states, prove that
each requested transition stays inside the manifold, and deny anything else.

Core primitives:
  SecurityState           — typed state vector (identity, posture, intent, payload, provenance)
  PermissionManifold      — boundary conditions and transition rules
  ControlBarrier          — fail-closed barrier function
  AdversarialInvariant    — properties that must hold under attack stress
  EvidenceLedger          — tamper-evident, externally-anchored decision log
  SecurityGovernor        — unified decision engine
  SelfHealingGovernor     — governed repair proposals, never autonomous mutation

Claim lane: IMPLEMENTED / EVIDENCE_BOUND / NOT_UNHACKABLE.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from al_haras.security_core import CryptographicAuditChain
from al_haras.quantum_defense.five_form_swarm import FiveFormDutySwarm
from al_haras.topological_counter_offensive import TopologicalCounterOffensive

PHI = (1.0 + 5.0**0.5) / 2.0


class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    ESCALATE = "ESCALATE"
    QUARANTINE = "QUARANTINE"


@dataclass(frozen=True)
class SecurityState:
    """A point in the security state manifold."""

    identity: str = ""
    posture: Tuple[str, ...] = ()
    intent: str = ""
    payload_hash: str = ""
    provenance: Tuple[str, ...] = ()
    timestamp: float = 0.0
    channel: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict, hash=False, compare=False)

    def canonical(self) -> bytes:
        return json.dumps(
            {
                "identity": self.identity,
                "posture": sorted(self.posture),
                "intent": self.intent,
                "payload_hash": self.payload_hash,
                "provenance": sorted(self.provenance),
                "timestamp": self.timestamp,
                "channel": self.channel,
            },
            sort_keys=True,
            default=str,
        ).encode()

    def digest(self) -> str:
        return hashlib.sha256(self.canonical()).hexdigest()[:32]


@dataclass
class PermissionManifold:
    """Boundary conditions that define allowed states and transitions."""

    allowed_intents: Set[str] = field(default_factory=lambda: {
        "read", "write", "execute", "deploy", "heartbeat", "administer", "query", "heal_propose",
    })
    required_posture: Set[str] = field(default_factory=lambda: {"launch_guard_ready"})
    forbidden_payload_patterns: Set[str] = field(default_factory=lambda: {"exploit", "shellcode", "rce", "meterpreter", "reverse_shell"})
    trusted_provenance_roots: Set[str] = field(default_factory=lambda: {"sovereign_ci", "hsm_signed", "euclid_vetted"})
    max_staleness_seconds: float = 300.0
    identity_required: bool = True
    channel_whitelist: Optional[Set[str]] = None

    def contains(self, state: SecurityState) -> Tuple[bool, str]:
        """Point-in-manifold check; returns (ok, reason)."""
        if self.identity_required and not state.identity:
            return False, "identity_missing"
        if state.intent and state.intent not in self.allowed_intents:
            return False, f"intent_not_allowed:{state.intent}"
        missing_posture = self.required_posture - set(state.posture)
        if missing_posture:
            return False, f"posture_missing:{','.join(sorted(missing_posture))}"
        if (time.time() - state.timestamp) > self.max_staleness_seconds:
            return False, "state_stale"
        if self.channel_whitelist and state.channel not in self.channel_whitelist:
            return False, f"channel_not_allowed:{state.channel}"
        for pattern in self.forbidden_payload_patterns:
            if pattern in state.payload_hash.lower():
                return False, f"payload_forbidden_pattern:{pattern}"
        return True, "inside_manifold"

    def transition_allowed(self, from_state: SecurityState, to_state: SecurityState) -> Tuple[bool, str]:
        """Check that a state-to-state transition is allowed."""
        ok, reason = self.contains(to_state)
        if not ok:
            return False, reason
        # Principal continuity: identity cannot change mid-transition unless explicitly delegated
        if from_state.identity and to_state.identity and from_state.identity != to_state.identity:
            if "delegation" not in to_state.posture:
                return False, "identity_jump_without_delegation"
        return True, "transition_inside_manifold"


class ControlBarrier:
    """Fail-closed barrier function: any unsafe state is mapped to DENY."""

    def __init__(self, manifold: PermissionManifold):
        self.manifold = manifold

    def evaluate(self, state: SecurityState) -> Tuple[Decision, str, Dict[str, Any]]:
        ok, reason = self.manifold.contains(state)
        if not ok:
            return Decision.DENY, reason, {"barrier": "closed", "violation": reason}
        return Decision.ALLOW, "barrier_open", {"barrier": "open"}


class AdversarialInvariant:
    """A property that must hold under stress — tested, not assumed."""

    def __init__(self, name: str, predicate: Callable[[SecurityState], Tuple[bool, str]]):
        self.name = name
        self.predicate = predicate

    def hold(self, state: SecurityState) -> Tuple[bool, str]:
        return self.predicate(state)


class EvidenceLedger:
    """Tamper-evident ledger of security decisions, externally anchored.
    Every record is sealed to the current chain tip so later evidence
    verification always has a matching anchored checkpoint.
    """

    def __init__(self, external_anchor: str):
        self.chain = CryptographicAuditChain(use_merkle=True)
        self.chain.set_external_anchor(external_anchor)
        self.chain.add_entry("EVIDENCE_LEDGER_GENESIS")
        self._checkpoint = self.chain.seal_checkpoint()
        self._sealed_decisions: Set[str] = set()
        self._lock = threading.RLock()

    def record(self, state: SecurityState, decision: Decision, reason: str, evidence: Dict[str, Any]) -> str:
        with self._lock:
            entry = {
                "state_digest": state.digest(),
                "decision": decision.value,
                "reason": reason,
                "evidence": evidence,
                "ts": time.time(),
            }
            entry_json = json.dumps(entry, sort_keys=True, default=str)
            h = self.chain.add_entry(entry_json)
            self._sealed_decisions.add(h)
            # Anchor every record so the chain tip is always externally sealed.
            self._checkpoint = self.chain.seal_checkpoint()
            return h

    def verify(self, entry_hash: str) -> Dict[str, Any]:
        with self._lock:
            if entry_hash not in self._sealed_decisions:
                return {"ok": False, "error": "no_such_decision"}
            chain_ok = self.chain.verify_integrity()
            anchor_ok = self.chain.verify_with_external_anchor(self._checkpoint)
            return {"ok": chain_ok and anchor_ok, "chain_ok": chain_ok, "anchor_ok": anchor_ok}


class SecurityGovernor:
    """Unified control-plane governor: state → manifold → barrier → evidence."""

    def __init__(
        self,
        *,
        external_anchor: str = "hyba-sovereign-hsm-root",
        manifold: Optional[PermissionManifold] = None,
        invariants: Optional[List[AdversarialInvariant]] = None,
    ):
        self.phi = PHI
        self.manifold = manifold or self._default_manifold()
        self.barrier = ControlBarrier(self.manifold)
        self.ledger = EvidenceLedger(external_anchor)
        self.invariants = invariants or self._default_invariants()
        self.topo = TopologicalCounterOffensive()
        self.swarm = FiveFormDutySwarm(max_agents=4096)
        self._lock = threading.RLock()
        self.stats = {"allowed": 0, "denied": 0, "escalated": 0, "quarantined": 0}

    def _default_manifold(self) -> PermissionManifold:
        return PermissionManifold()

    def _default_invariants(self) -> List[AdversarialInvariant]:
        return [
            AdversarialInvariant(
                "identity_non_empty",
                lambda s: (bool(s.identity), "identity_missing"),
            ),
            AdversarialInvariant(
                "posture_not_empty",
                lambda s: (bool(s.posture), "posture_missing"),
            ),
            AdversarialInvariant(
                "payload_not_forbidden",
                lambda s: (
                    all(p not in s.payload_hash.lower() for p in {"exploit", "shellcode"}),
                    "forbidden_payload_marker",
                ),
            ),
            AdversarialInvariant(
                "timestamp_fresh",
                lambda s: (time.time() - s.timestamp <= 300.0, "state_stale"),
            ),
        ]

    def _swarm_assess(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Resilient swarm assessment with cap fallback."""
        try:
            return self.swarm.observe(event)
        except Exception as exc:
            return {
                "threat_level": "probe",
                "error": str(exc),
                "fallback": "resilient_governor",
            }

    def decide(self, state: SecurityState) -> Dict[str, Any]:
        with self._lock:
            # Layer 1: adversarial invariants
            for inv in self.invariants:
                holds, reason = inv.hold(state)
                if not holds:
                    return self._record(state, Decision.DENY, f"invariant:{inv.name}:{reason}", {"layer": "invariant"})

            # Layer 2: topological payload check
            topo_payload = state.metadata.get("raw_payload") or state.payload_hash
            topo = self.topo.check_payload(str(topo_payload))
            if topo.get("status") == "REJECTED":
                return self._record(
                    state, Decision.DENY, "topological_invariant", {"topo_violations": topo.get("violations")}
                )

            # Layer 3: permission manifold + barrier
            decision, reason, evidence = self.barrier.evaluate(state)
            if decision == Decision.DENY:
                return self._record(state, decision, f"barrier:{reason}", evidence)

            # Layer 4: six-form intelligence on residual risk
            swarm_out = self._swarm_assess(
                {
                    "kind": state.metadata.get("kind", "probe"),
                    "source": state.identity,
                    "target": state.metadata.get("target", "core"),
                    "vector": state.intent,
                    "severity": float(state.metadata.get("severity", 0.3) or 0.3),
                    "payload": str(topo_payload)[:200],
                }
            )
            swarm_level = swarm_out.get("threat_level") or swarm_out.get("level")
            if swarm_level in {"attack", "persistent"}:
                return self._record(
                    state, Decision.QUARANTINE, "swarm_high_threat", {"swarm": swarm_out}
                )
            if swarm_level == "probe":
                decision = Decision.ESCALATE

            return self._record(state, decision, "all_layers_clear", {"barrier": evidence, "swarm": swarm_out})

    def _record(self, state: SecurityState, decision: Decision, reason: str, evidence: Dict[str, Any]) -> Dict[str, Any]:
        if decision == Decision.ALLOW:
            self.stats["allowed"] += 1
        elif decision == Decision.DENY:
            self.stats["denied"] += 1
        elif decision == Decision.ESCALATE:
            self.stats["escalated"] += 1
        elif decision == Decision.QUARANTINE:
            self.stats["quarantined"] += 1

        entry_hash = self.ledger.record(state, decision, reason, evidence)
        return {
            "decision": decision.value,
            "reason": reason,
            "state_digest": state.digest(),
            "entry_hash": entry_hash,
            "evidence": evidence,
            "audit_ok": self.ledger.chain.verify_integrity(),
            "anchor_ok": self.ledger.chain.verify_with_external_anchor(self.ledger._checkpoint),
            "phi": self.phi,
            "unhackable": False,
            "claim_lane": "IMPLEMENTED_STATE_GOVERNANCE",
        }

    def inspect_transition(self, from_state: SecurityState, to_state: SecurityState) -> Dict[str, Any]:
        ok, reason = self.manifold.transition_allowed(from_state, to_state)
        if not ok:
            return self._record(to_state, Decision.DENY, f"transition:{reason}", {"from": from_state.digest(), "to": to_state.digest()})
        return self.decide(to_state)

    def verify(self, entry_hash: str) -> Dict[str, Any]:
        return self.ledger.verify(entry_hash)

    def status(self) -> Dict[str, Any]:
        return {
            "stats": dict(self.stats),
            "manifold_allowed_intents": sorted(self.manifold.allowed_intents),
            "manifold_required_posture": sorted(self.manifold.required_posture),
            "audit_len": len(self.ledger.chain.chain),
            "audit_ok": self.ledger.chain.verify_integrity(),
            "anchor_ok": self.ledger.chain.verify_with_external_anchor(self.ledger._checkpoint),
        }


class SelfHealingGovernor:
    """Governed self-healing: propose, never auto-apply, under sovereign gate."""

    def __init__(self, governor: SecurityGovernor):
        self.governor = governor
        self.proposals: List[Dict[str, Any]] = []
        self._lock = threading.RLock()

    def propose(self, trigger: SecurityState, remediation: Dict[str, Any], *, proposer: str = "salamander") -> Dict[str, Any]:
        target_posture = tuple(sorted(set(trigger.posture) | set(remediation.get("add_posture", []))))
        target_state = SecurityState(
            identity=trigger.identity,
            posture=target_posture,
            intent=remediation.get("intent", "heal_propose"),
            payload_hash=remediation.get("payload_hash", hashlib.sha256(b"remediation").hexdigest()),
            provenance=trigger.provenance,
            timestamp=time.time(),
            channel=trigger.channel,
            metadata={**trigger.metadata, "proposer": proposer, "healing": True},
        )
        transition = self.governor.inspect_transition(trigger, target_state)
        proposal = {
            "proposer": proposer,
            "trigger_digest": trigger.digest(),
            "target_digest": target_state.digest(),
            "transition_decision": transition,
            "approved": transition["decision"] == Decision.ALLOW.value,
            "requires_human_approval": transition["decision"] != Decision.ALLOW.value,
            "evidence": transition,
        }
        with self._lock:
            self.proposals.append(proposal)
        return proposal

    def list_proposals(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self.proposals)
