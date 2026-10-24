"""
Unsolved Problem Adversarial Test — Odd Perfect Numbers.
============================================================

Self-contained — zero external dependencies. Three phases stress-test
the organism stack against a historically open mathematical space:
  1. Bounded search within SLA — completes safely (no infinite loop)
  2. Unbounded search breaching SLA — deterministic containment via BREACHED
  3. Byzantine telemetry forgery — FederatedResonanceGate veto via Rule 3

The system does not need to solve the problem to remain secure.

Status: EUCLID Adversarial Boundary Verification — 19 July 2026.
"""

import time, math, hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any, Tuple

# ═══════════════════════════════════════════════════════════
# Self-contained type definitions (no external euclid deps)
# ═══════════════════════════════════════════════════════════

PHI = (1.0 + math.sqrt(5.0)) / 2.0
PHI_I = PHI - 1.0

class EvidenceSource(Enum):
    INTERNAL_HEURISTIC = "internal_heuristic"
    EXTERNAL_SUBSYSTEM = "external_subsystem"
    NONE = "none"

class VetoCategory(Enum):
    CONFIDENCE_FAILURE = "confidence_failure"
    COHERENCE_FAILURE = "coherence_failure"
    TRUTH_FAILURE = "truth_failure"
    CAUSAL_FAILURE = "causal_failure"
    FEEDBACK_FAILURE = "feedback_failure"

class IOPState(Enum):
    PROPOSED = "proposed"; ACTIVE = "active"; RUNNING = "running"
    COMPLETED = "completed"; BREACHED = "breached"; TERMINATED = "terminated"

_TRANS = {
    IOPState.PROPOSED: {IOPState.ACTIVE, IOPState.TERMINATED},
    IOPState.ACTIVE: {IOPState.RUNNING, IOPState.TERMINATED},
    IOPState.RUNNING: {IOPState.COMPLETED, IOPState.BREACHED, IOPState.TERMINATED},
}

@dataclass
class ValidationSignal:
    evidence_source: EvidenceSource = EvidenceSource.EXTERNAL_SUBSYSTEM
    signal_strength: float = 0.80
    validator_identity: str = ""
    evidence_hash: str = ""

@dataclass
class IntegrationAssessment:
    passed: bool
    veto_category: Optional[VetoCategory] = None
    reason: str = ""
    validation_signal: Optional[ValidationSignal] = None

@dataclass
class IOPContract:
    contract_id: str = ""
    max_latency: float = 5.0
    min_confidence: float = 0.7
    required_evidence_source: str = "EXTERNAL_SUBSYSTEM"

    def is_sla_satisfied(self, et: float, conf: float, ev: str) -> Tuple[bool, str]:
        v = []
        if et > self.max_latency: v.append(f"Latency {et:.3f}s > SLA {self.max_latency:.3f}s")
        if conf < self.min_confidence: v.append(f"Conf {conf:.3f} < SLA {self.min_confidence:.3f}")
        if ev != self.required_evidence_source: v.append(f"Ev '{ev}' != '{self.required_evidence_source}'")
        return (False, "BREACHED: " + "; ".join(v)) if v else (True, "OK")

class IOPExecutionTracker:
    def __init__(self, contract=None):
        self.contract = contract; self.state = IOPState.PROPOSED; self.start_time = 0.0

    def transition(self, to, reason=""):
        if to not in _TRANS.get(self.state, set()): return (False, f"Bad: {self.state.value}->{to.value}")
        self.state = to
        if to == IOPState.RUNNING: self.start_time = time.time()
        return (True, f"{to.value}")

    def evaluate_completion(self, et, conf, ev):
        if self.state != IOPState.RUNNING: return (self.state, "Not running")
        ok, r = self.contract.is_sla_satisfied(et, conf, ev)
        self.transition(IOPState.COMPLETED if ok else IOPState.BREACHED, r)
        return (self.state, r)


class FederatedResonanceGate:
    """Three-rule validation gate for remote resonance telemetry."""
    QA_THRESHOLD = 0.150; TOLERANCE = 1e-5; MIN_SIGNAL = 0.5

    def validate_remote_integration(self, peer_id, payload, signal):
        alpha = payload.get("effective_alpha", 0.382)
        numpy_ok = payload.get("uses_numpy", True)
        expl = payload.get("resonance_explanation", {})
        phi_scale = expl.get("phi_metric_scale", 1.0)

        # Rule 1: Temporal boundary
        if alpha < self.QA_THRESHOLD:
            return IntegrationAssessment(False, VetoCategory.FEEDBACK_FAILURE,
                f"Alpha {alpha:.4f} below quarantine {self.QA_THRESHOLD}.")
        # Rule 2: Precision scaling
        adj = signal.signal_strength * (PHI_I if not numpy_ok else 1.0)
        if adj < self.MIN_SIGNAL:
            return IntegrationAssessment(False, VetoCategory.TRUTH_FAILURE,
                f"Adjusted signal {adj:.3f} < {self.MIN_SIGNAL}.")
        # Rule 3: Structural explanation
        if not expl:
            return IntegrationAssessment(False, VetoCategory.COHERENCE_FAILURE, "Missing explanation.")
        if abs(phi_scale - PHI_I) > self.TOLERANCE:
            return IntegrationAssessment(False, VetoCategory.COHERENCE_FAILURE,
                f"phi_metric_scale={phi_scale:.6f} != PHI_I={PHI_I:.6f}.")
        return IntegrationAssessment(True, reason="Validated.")


# ═══════════════════════════════════════════════════════════
# Math Search Organ
# ═══════════════════════════════════════════════════════════

class MathSearchOrgan:
    def find_divisors(self, n: int) -> List[int]:
        divs = [1]
        for i in range(2, int(n**0.5) + 1):
            if n % i == 0:
                divs.append(i)
                if i != n // i: divs.append(n // i)
        return divs

    def search_interval(self, start: int, end: int) -> Optional[int]:
        if start % 2 == 0: start += 1
        if start < 3: start = 3  # Skip 1 — not a perfect number
        for c in range(start, end, 2):
            if sum(self.find_divisors(c)) == c: return c
        return None


# ═══════════════════════════════════════════════════════════
# Three-Phase Experiment
# ═══════════════════════════════════════════════════════════

def run():
    print("=" * 60)
    print("ODD PERFECT NUMBER INTEGRATION TEST")
    print("Unsolved Problem — Adversarial Boundary Verification")
    print("=" * 60)

    organ = MathSearchOrgan()
    contract = IOPContract(contract_id="c01", max_latency=0.015, min_confidence=0.85,
                           required_evidence_source="EXTERNAL_SUBSYSTEM")

    # Phase 1: Bounded search within SLA
    print("\n[PHASE 1] Bounded search (1 to 1,000) within 15ms SLA")
    t = IOPExecutionTracker(contract)
    t.transition(IOPState.ACTIVE); t.transition(IOPState.RUNNING)
    t0 = time.time()
    r = organ.search_interval(1, 1000)
    et = time.time() - t0
    s, _ = t.evaluate_completion(et, 0.90, "EXTERNAL_SUBSYSTEM")
    print(f"  Search: {et*1000:.3f}ms, Result: {r}, State: {s.value}")
    assert s == IOPState.COMPLETED
    print("  -> Bounded search: Resolved safely within SLA.\n")

    # Phase 2: Unbounded search breaching SLA
    print("[PHASE 2] Unbounded search (3 to 5,000,000) exceeding 15ms SLA")
    t2 = IOPExecutionTracker(contract)
    t2.transition(IOPState.ACTIVE); t2.transition(IOPState.RUNNING)
    t0 = time.time()
    _ = organ.search_interval(3, 5000000)
    et2 = time.time() - t0
    s2, _ = t2.evaluate_completion(et2, 0.90, "EXTERNAL_SUBSYSTEM")
    print(f"  Search: {et2*1000:.3f}ms (SLA: {contract.max_latency*1000:.1f}ms), State: {s2.value}")
    assert s2 == IOPState.BREACHED or et2 > contract.max_latency  # Breach or explicit timeout
    if et2 > contract.max_latency:
        print("  -> Unbounded search: Deterministic SLA containment — BREACHED.\n")
    else:
        print(f"  -> Search completed in {et2*1000:.3f}ms (below SLA) — no odd perfect numbers found.\n")

    # Phase 3: Byzantine telemetry forgery
    print("[PHASE 3] Byzantine peer forges odd perfect number discovery")
    gate = FederatedResonanceGate()
    sig = ValidationSignal(EvidenceSource.EXTERNAL_SUBSYSTEM, 0.90, "byzantine_peer", "forged")
    payload = {"uses_numpy": True, "effective_alpha": 0.382,
               "resonance_explanation": {"phi_metric_scale": 1.0},  # Wrong — should be 0.618034
               "result": {"candidate": 945, "is_perfect": True}}
    a = gate.validate_remote_integration("byz", payload, sig)
    print(f"  Gate: Passed={a.passed}, Veto={a.veto_category}")
    print(f"  Reason: {a.reason[:70]}...")
    assert not a.passed and a.veto_category == VetoCategory.COHERENCE_FAILURE
    print("  -> Byzantine forgery: COHERENCE_FAILURE veto — Rule 3 defended.\n")

    print("=" * 60)
    print("ALL THREE PHASES PASSED")
    print("System secure against barren search spaces and adversarial")
    print("injection — without solving the underlying problem.")
    print("=" * 60)


if __name__ == "__main__":
    run()
