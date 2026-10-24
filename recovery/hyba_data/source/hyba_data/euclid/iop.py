"""IOP types for unsolved problem test."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import time

class IOPState(Enum):
    PROPOSED = "proposed"; ACTIVE = "active"; RUNNING = "running"
    COMPLETED = "completed"; BREACHED = "breached"; TERMINATED = "terminated"

_TRANS = {
    IOPState.PROPOSED: {IOPState.ACTIVE, IOPState.TERMINATED},
    IOPState.ACTIVE: {IOPState.RUNNING, IOPState.TERMINATED},
    IOPState.RUNNING: {IOPState.COMPLETED, IOPState.BREACHED, IOPState.TERMINATED},
}

@dataclass
class IOPContract:
    contract_id: str = ""
    requester_id: str = ""
    provider_id: str = ""
    target_domain: str = ""
    max_latency: float = 5.0
    min_confidence: float = 0.7
    required_evidence_source: str = "EXTERNAL_SUBSYSTEM"
    state_proof_requirement: str = "MERKLE_ROOT"

    def is_sla_satisfied(self, execution_time: float, confidence: float, evidence_source: str) -> Tuple[bool, str]:
        violations = []
        if execution_time > self.max_latency:
            violations.append(f"Latency {execution_time:.3f}s > SLA {self.max_latency:.3f}s")
        if confidence < self.min_confidence:
            violations.append(f"Confidence {confidence:.3f} < SLA {self.min_confidence:.3f}")
        if evidence_source != self.required_evidence_source:
            violations.append(f"Evidence '{evidence_source}' != '{self.required_evidence_source}'")
        if violations:
            return (False, "SLA BREACHED: " + "; ".join(violations))
        return (True, "SLA satisfied.")

class IOPExecutionTracker:
    def __init__(self, contract=None):
        self.contract = contract
        self.state = IOPState.PROPOSED
        self.start_time: float = 0.0
        self.completion_time: Optional[float] = None
        self.events: List[Dict[str, Any]] = []

    def transition(self, to_state, reason=""):
        if to_state not in _TRANS.get(self.state, set()):
            return (False, f"Invalid: {self.state.value} -> {to_state.value}")
        old = self.state; self.state = to_state
        if to_state == IOPState.RUNNING: self.start_time = time.time()
        elif to_state in (IOPState.COMPLETED, IOPState.BREACHED): self.completion_time = time.time()
        self.events.append({"from": old.value, "to": to_state.value, "reason": reason})
        return (True, f"{old.value} -> {to_state.value}")

    def evaluate_completion(self, execution_time, confidence, evidence_source):
        if self.state != IOPState.RUNNING:
            return (self.state, f"Cannot evaluate from {self.state.value}")
        ok, reason = self.contract.is_sla_satisfied(execution_time, confidence, evidence_source)
        if ok:
            self.transition(IOPState.COMPLETED, reason)
        else:
            self.transition(IOPState.BREACHED, reason)
        return (self.state, reason)

    @property
    def elapsed(self):
        if self.start_time == 0: return 0.0
        return (self.completion_time or time.time()) - self.start_time
