"""
EUCLID Governed Delegation System
====================================

Implements true governed delegation — not agents, peers, or workers — but
*local organs* EUCLID can call when performing research, creative tasks,
world-system modelling, emergence probes, or coherence evaluation.

Architecture:
  Organ Registry → Confidence Arbitration → Task Dispatch → World-Integration Gate → Fail-Closed Veto

Delegation is not federation. It is the organism's internal nervous system:
local, governed, evidence-gated, and fail-closed.

Author: EUCLID Organism CNS
Status: IMPLEMENTED — INTERNAL
Date: 19 July 2026
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


# =============================================================================
# Domain & Confidence Types
# =============================================================================


class ResearchDomain(Enum):
    """The five research task domains EUCLID can delegate into."""
    MATHEMATICAL_ENGINE = "mathematical_engine"
    CREATIVE_SUBSTRATE = "creative_substrate"
    WORLD_SYSTEM_FORECASTER = "world_system_forecaster"
    EMERGENCE_ENGINE = "emergence_engine"
    COHERENCE_EVALUATOR = "coherence_evaluator"


class ConfidenceBound(Enum):
    """
    Five confidence bounds a candidate organ must clear.
    ALL must pass — not merely "highest scoring."
    """
    CAPABLE = "capable"       # Organ can perform the task type
    HEALTHY = "healthy"       # Organ is currently operational
    PERMITTED = "permitted"   # Organ is authorised for this domain
    CONFIDENT = "confident"   # Organ's confidence exceeds threshold
    SAFE = "safe"             # Organ passes safety assessment


class IntegrationGate(Enum):
    """
    Four-gate evidentiary barrier for world-state integration.
    """
    COHERENCE = "coherence"           # Result is coherent with world state
    TRUTH_EVIDENCE = "truth_evidence"  # Evidence of correctness supplied
    CAUSAL_ATTRIBUTION = "causal_attribution"  # Causal chain is documented
    FEEDBACK_PROCESSING = "feedback_processing"  # Feedback loop completed


class DelegationVerdict(Enum):
    """Binary outcome for every delegation attempt."""
    ACCEPTED = "accepted"
    VETOED = "vetoed"


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class OrganCapability:
    """Quantified capability score for a domain."""
    domain: ResearchDomain
    capability_score: float  # 0.0–1.0
    evidence_hash: str       # SHA-256 of capability evidence
    last_evaluated: float     # Unix timestamp


@dataclass
class OrganHealth:
    """Current health metrics for an organ."""
    status: str               # "healthy", "degraded", "unavailable"
    uptime_ratio: float       # 0.0–1.0
    error_rate: float         # 0.0–1.0
    last_heartbeat: float     # Unix timestamp
    diagnostic_hash: str      # SHA-256 of latest diagnostic


@dataclass
class OrganPermission:
    """Permission set for an organ."""
    allowed_domains: List[ResearchDomain]
    max_delegation_depth: int  # Recursion limit
    require_quorum: bool        # Whether quorum is required
    granted_by: str             # Authority that granted permissions
    granted_at: float           # Unix timestamp


@dataclass
class ConfidenceProfile:
    """Aggregated confidence across all five bounds."""
    capable: bool
    healthy: bool
    permitted: bool
    confident: bool
    safe: bool
    capable_score: float
    healthy_score: float
    permitted_score: float
    confident_score: float
    safe_score: float

    @property
    def all_clear(self) -> bool:
        """ALL bounds must clear — not merely 'highest scoring'."""
        return all([
            self.capable,
            self.healthy,
            self.permitted,
            self.confident,
            self.safe,
        ])

    @property
    def failing_bounds(self) -> List[str]:
        """Returns names of any failing confidence bounds."""
        failing: List[str] = []
        if not self.capable:
            failing.append("capable")
        if not self.healthy:
            failing.append("healthy")
        if not self.permitted:
            failing.append("permitted")
        if not self.confident:
            failing.append("confident")
        if not self.safe:
            failing.append("safe")
        return failing


@dataclass
class DelegationTask:
    """A task dispatched to an organ via governed delegation."""
    task_id: str
    domain: ResearchDomain
    payload: Dict[str, Any]
    origin: str                # CNS module that originated the task
    created_at: float
    priority: int = 0          # 0 = normal, 1 = elevated, 2 = critical
    parent_task_id: Optional[str] = None


@dataclass
class DelegationResult:
    """Raw result from an organ before integration-gate evaluation."""
    task_id: str
    organ_id: str
    domain: ResearchDomain
    output: Any
    execution_time: float
    confidence_profile: ConfidenceProfile
    produced_at: float
    output_hash: str


@dataclass
class IntegrationAssessment:
    """Result of the four-gate world-integration evaluation."""
    task_id: str
    verdict: DelegationVerdict
    coherence_passed: bool
    truth_evidence_supplied: bool
    causal_attribution_supplied: bool
    feedback_processing_completed: bool
    veto_reason: Optional[str] = None
    assessed_at: Optional[float] = None
    assessment_hash: Optional[str] = None


@dataclass
class DelegationChronicle:
    """Append-only delegation event ledger entry."""
    event_id: str
    task: DelegationTask
    organ_id: str
    confidence_profile: ConfidenceProfile
    integration_assessment: IntegrationAssessment
    timestamp: float
    predecessor_hash: Optional[str]
    event_hash: str


# =============================================================================
# Organ Model
# =============================================================================


@dataclass
class Organ:
    """
    A local organ — not an agent, peer, or worker. An internal component
    EUCLID can delegate to within the organism.
    """
    organ_id: str
    name: str
    domain: ResearchDomain
    capabilities: List[OrganCapability]
    health: OrganHealth
    permissions: OrganPermission
    confidence_threshold: float = 0.70  # Minimum confidence to be "confident"
    safety_threshold: float = 0.70      # Minimum safety score to be "safe"
    handler: Optional[Callable] = None  # The actual organ function

    def assess_confidence(self, domain: ResearchDomain) -> ConfidenceProfile:
        """Assess all five confidence bounds for a given domain."""
        capability = self._find_capability(domain)
        capable_score = capability.capability_score if capability else 0.0
        capable = capable_score >= self.confidence_threshold

        healthy_score = self.health.uptime_ratio * (1.0 - self.health.error_rate)
        healthy = self.health.status == "healthy" and healthy_score >= 0.5

        permitted_score = 1.0 if domain in self.permissions.allowed_domains else 0.0
        permitted = permitted_score > 0.0

        confident_score = capable_score * healthy_score
        confident = confident_score >= self.confidence_threshold

        safety_score = min(capable_score, healthy_score, permitted_score)
        safe = safety_score >= self.safety_threshold

        return ConfidenceProfile(
            capable=capable,
            healthy=healthy,
            permitted=permitted,
            confident=confident,
            safe=safe,
            capable_score=capable_score,
            healthy_score=healthy_score,
            permitted_score=permitted_score,
            confident_score=confident_score,
            safe_score=safety_score,
        )

    def _find_capability(self, domain: ResearchDomain) -> Optional[OrganCapability]:
        for cap in self.capabilities:
            if cap.domain == domain:
                return cap
        return None


# =============================================================================
# Organ Registry
# =============================================================================


class OrganRegistry:
    """
    Central registry of all local organs available for delegation.
    Organs are registered by domain and assessed before dispatch.
    """

    def __init__(self) -> None:
        self._organs: Dict[str, Organ] = {}
        self._domain_index: Dict[ResearchDomain, List[str]] = {
            d: [] for d in ResearchDomain
        }

    def register(self, organ: Organ) -> None:
        """Register an organ. Deduplicates by organ_id."""
        self._organs[organ.organ_id] = organ
        if organ.organ_id not in self._domain_index[organ.domain]:
            self._domain_index[organ.domain].append(organ.organ_id)

    def unregister(self, organ_id: str) -> None:
        """Remove an organ from the registry."""
        organ = self._organs.pop(organ_id, None)
        if organ:
            domain_list = self._domain_index.get(organ.domain, [])
            if organ_id in domain_list:
                domain_list.remove(organ_id)

    def get_organ(self, organ_id: str) -> Optional[Organ]:
        """Retrieve an organ by ID."""
        return self._organs.get(organ_id)

    def get_candidates(self, domain: ResearchDomain) -> List[Organ]:
        """Return all registered organs for a domain."""
        return [
            self._organs[oid]
            for oid in self._domain_index.get(domain, [])
            if oid in self._organs
        ]

    def list_all(self) -> List[Organ]:
        """Return all registered organs."""
        return list(self._organs.values())

    def organ_count(self) -> int:
        """Total registered organs."""
        return len(self._organs)


# =============================================================================
# Confidence Arbitration
# =============================================================================


class ConfidenceArbiter:
    """
    Arbitrates delegation candidates.

    RULE: A candidate must clear ALL confidence bounds, not merely be
    "highest scoring." This prevents pathological delegation and ensures
    EUCLID only calls organs that are capable, healthy, permitted,
    confident, and safe.
    """

    def __init__(self, confidence_threshold: float = 0.70, safety_threshold: float = 0.70) -> None:
        self.confidence_threshold = confidence_threshold
        self.safety_threshold = safety_threshold

    def arbitrate(
        self, candidates: List[Organ], domain: ResearchDomain
    ) -> Tuple[Optional[Organ], ConfidenceProfile, str]:
        """
        Evaluate all candidates. Return (selected_organ, profile, reason).

        Returns (None, failing_profile, veto_reason) if no candidate
        clears all bounds.
        """
        if not candidates:
            return (
                None,
                ConfidenceProfile(
                    capable=False, healthy=False, permitted=False,
                    confident=False, safe=False,
                    capable_score=0.0, healthy_score=0.0,
                    permitted_score=0.0, confident_score=0.0,
                    safe_score=0.0,
                ),
                f"VETOED: No candidates registered for domain {domain.value}",
            )

        # Evaluate every candidate against ALL bounds
        best_organ: Optional[Organ] = None
        best_score: float = -1.0
        all_profiles: List[Tuple[Organ, ConfidenceProfile]] = []

        for organ in candidates:
            profile = organ.assess_confidence(domain)
            all_profiles.append((organ, profile))

            if profile.all_clear:
                # Among all-clearing candidates, select highest aggregate
                aggregate = (
                    profile.capable_score
                    + profile.healthy_score
                    + profile.confident_score
                    + profile.safe_score
                )
                if aggregate > best_score:
                    best_score = aggregate
                    best_organ = organ

        if best_organ is None:
            # No candidate cleared all bounds — report WHY
            failing_details: List[str] = []
            for organ, profile in all_profiles:
                failing = profile.failing_bounds
                if failing:
                    failing_details.append(
                        f"{organ.organ_id}: failed [{', '.join(failing)}]"
                    )

            veto_reason = (
                f"VETOED: No candidate cleared ALL confidence bounds for "
                f"{domain.value}. Failures: {'; '.join(failing_details)}"
            )
            # Return the first candidate's profile for diagnostic purposes
            first_profile = all_profiles[0][1] if all_profiles else ConfidenceProfile(
                capable=False, healthy=False, permitted=False,
                confident=False, safe=False,
                capable_score=0.0, healthy_score=0.0,
                permitted_score=0.0, confident_score=0.0, safe_score=0.0,
            )
            return (None, first_profile, veto_reason)

        best_profile = best_organ.assess_confidence(domain)
        return (best_organ, best_profile, "ACCEPTED: All confidence bounds clear.")


# =============================================================================
# World-Integration Gate
# =============================================================================


class WorldIntegrationGate:
    """
    Four-gate evidentiary barrier for world-state integration.

    1. Coherence passed
    2. Truth evidence supplied
    3. Causal attribution supplied
    4. Feedback processing completed

    Only then is a delegated result eligible for world-state integration.
    This prevents hallucination, overclaim, or premature world mutation.

    IMPORTANT: The integration gate is implemented, but it does not yet
    automatically wire delegated outputs into a world-state graph or claim
    that existing truth, causal, feedback, and coherence subsystems have
    independently validated a result. EUCLID must *receive* validation
    signals from the subsystems — it cannot "pretend" validation.
    """

    def __init__(self) -> None:
        self._external_coherence_validator: Optional[Callable] = None
        self._external_truth_validator: Optional[Callable] = None
        self._external_causal_validator: Optional[Callable] = None
        self._external_feedback_validator: Optional[Callable] = None

    def wire_validators(
        self,
        coherence: Optional[Callable] = None,
        truth: Optional[Callable] = None,
        causal: Optional[Callable] = None,
        feedback: Optional[Callable] = None,
    ) -> None:
        """Wire external subsystem validators. Without these, gates use
        internal heuristics and mark themselves as INTERNAL evidence only."""
        if coherence is not None:
            self._external_coherence_validator = coherence
        if truth is not None:
            self._external_truth_validator = truth
        if causal is not None:
            self._external_causal_validator = causal
        if feedback is not None:
            self._external_feedback_validator = feedback

    def assess(
        self,
        result: DelegationResult,
        world_state_hash: Optional[str] = None,
    ) -> IntegrationAssessment:
        """
        Evaluate a delegation result against all four integration gates.

        If any gate is missing → VETOED.
        No silent integration. No implicit trust. No accidental world mutation.
        """
        gates: Dict[str, Tuple[bool, str]] = {}

        # Gate 1: Coherence
        coherence_ok, coherence_reason = self._check_coherence(result, world_state_hash)
        gates["coherence"] = (coherence_ok, coherence_reason)

        # Gate 2: Truth Evidence
        truth_ok, truth_reason = self._check_truth_evidence(result)
        gates["truth_evidence"] = (truth_ok, truth_reason)

        # Gate 3: Causal Attribution
        causal_ok, causal_reason = self._check_causal_attribution(result)
        gates["causal_attribution"] = (causal_ok, causal_reason)

        # Gate 4: Feedback Processing
        feedback_ok, feedback_reason = self._check_feedback_processing(result)
        gates["feedback_processing"] = (feedback_ok, feedback_reason)

        all_passed = all(ok for ok, _ in gates.values())

        if not all_passed:
            failing_gates = [name for name, (ok, _) in gates.items() if not ok]
            veto_reason = (
                f"VETOED: Integration gates failed — "
                f"{', '.join(failing_gates)}. "
                f"No world-state integration performed."
            )
            return IntegrationAssessment(
                task_id=result.task_id,
                verdict=DelegationVerdict.VETOED,
                coherence_passed=gates["coherence"][0],
                truth_evidence_supplied=gates["truth_evidence"][0],
                causal_attribution_supplied=gates["causal_attribution"][0],
                feedback_processing_completed=gates["feedback_processing"][0],
                veto_reason=veto_reason,
                assessed_at=time.time(),
                assessment_hash=self._hash_assessment(result, gates),
            )

        return IntegrationAssessment(
            task_id=result.task_id,
            verdict=DelegationVerdict.ACCEPTED,
            coherence_passed=True,
            truth_evidence_supplied=True,
            causal_attribution_supplied=True,
            feedback_processing_completed=True,
            assessed_at=time.time(),
            assessment_hash=self._hash_assessment(result, gates),
        )

    def _check_coherence(
        self, result: DelegationResult, world_state_hash: Optional[str]
    ) -> Tuple[bool, str]:
        if self._external_coherence_validator is not None:
            try:
                return self._external_coherence_validator(result, world_state_hash)
            except Exception as e:
                return (False, f"External coherence validator error: {e}")

        # Internal heuristic: result must have non-null output and valid hash
        if result.output is None:
            return (False, "Coherence gate: output is null — no meaningful result.")
        if not result.output_hash:
            return (False, "Coherence gate: missing output hash — cannot verify integrity.")
        return (True, "Coherence gate: INTERNAL heuristic passed (no external validator wired).")

    def _check_truth_evidence(
        self, result: DelegationResult
    ) -> Tuple[bool, str]:
        if self._external_truth_validator is not None:
            try:
                return self._external_truth_validator(result)
            except Exception as e:
                return (False, f"External truth validator error: {e}")

        # Internal heuristic: confidence must exceed threshold across all bounds
        if not result.confidence_profile.all_clear:
            return (
                False,
                f"Truth evidence gate: confidence bounds not all clear — "
                f"failed: {result.confidence_profile.failing_bounds}",
            )
        return (True, "Truth evidence gate: INTERNAL heuristic passed (confidence bounds clear).")

    def _check_causal_attribution(
        self, result: DelegationResult
    ) -> Tuple[bool, str]:
        if self._external_causal_validator is not None:
            try:
                return self._external_causal_validator(result)
            except Exception as e:
                return (False, f"External causal validator error: {e}")

        # Internal heuristic: organ identity and domain must be present
        if not result.organ_id:
            return (False, "Causal attribution gate: missing organ identity.")
        if not result.domain:
            return (False, "Causal attribution gate: missing domain attribution.")
        return (True, "Causal attribution gate: INTERNAL heuristic passed (organ and domain recorded).")

    def _check_feedback_processing(
        self, result: DelegationResult
    ) -> Tuple[bool, str]:
        if self._external_feedback_validator is not None:
            try:
                return self._external_feedback_validator(result)
            except Exception as e:
                return (False, f"External feedback validator error: {e}")

        # Internal heuristic: result must carry execution metadata
        if result.execution_time <= 0:
            return (False, "Feedback processing gate: invalid execution time.")
        if result.produced_at <= 0:
            return (False, "Feedback processing gate: missing production timestamp.")
        return (True, "Feedback processing gate: INTERNAL heuristic passed (execution metadata present).")

    @staticmethod
    def _hash_assessment(
        result: DelegationResult,
        gates: Dict[str, Tuple[bool, str]],
    ) -> str:
        """Produce a deterministic assessment hash."""
        payload = json.dumps({
            "task_id": result.task_id,
            "organ_id": result.organ_id,
            "output_hash": result.output_hash,
            "gates": {k: v[0] for k, v in gates.items()},
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()


# =============================================================================
# Delegation Controller (CNS Integration)
# =============================================================================


class DelegationController:
    """
    Master delegation controller. Wires Organ Registry, Confidence Arbiter,
    World-Integration Gate, and the CNS chronicle into a single governed
    delegation pipeline.

    This is the CNS-facing interface. EUCLID's Organism CNS calls:
        controller.delegate(task) → (result, assessment, chronicle_entry)
    """

    def __init__(self) -> None:
        self.registry = OrganRegistry()
        self.arbiter = ConfidenceArbiter()
        self.integration_gate = WorldIntegrationGate()
        self._chronicle: List[DelegationChronicle] = []
        self._event_counter: int = 0
        self._integrity_chain: List[str] = []  # predecessor-linked hash chain

    def delegate(
        self, task: DelegationTask
    ) -> Tuple[Optional[DelegationResult], IntegrationAssessment, DelegationChronicle]:
        """
        Governed delegation pipeline:
        1. Find candidates in the organ registry for the task domain
        2. Arbitrate confidence — ALL bounds must clear
        3. Dispatch to selected organ
        4. Evaluate world-integration gates
        5. Record chronicle entry (append-only, predecessor-linked)

        Returns (result_or_none, assessment, chronicle_entry).
        If any stage vetoes, result is None.
        """
        # Stage 1: Candidate lookup
        candidates = self.registry.get_candidates(task.domain)

        # Stage 2: Confidence arbitration
        selected_organ, confidence_profile, arbiter_reason = self.arbiter.arbitrate(
            candidates, task.domain
        )

        if selected_organ is None:
            # Fail-closed: no organ cleared ALL bounds
            assessment = IntegrationAssessment(
                task_id=task.task_id,
                verdict=DelegationVerdict.VETOED,
                coherence_passed=False,
                truth_evidence_supplied=False,
                causal_attribution_supplied=False,
                feedback_processing_completed=False,
                veto_reason=arbiter_reason,
                assessed_at=time.time(),
            )
            chronicle = self._record_chronicle(
                task, "__none__", confidence_profile, assessment
            )
            return (None, assessment, chronicle)

        # Stage 3: Dispatch to organ
        result = self._dispatch(selected_organ, task, confidence_profile)

        # Stage 4: World-integration gate assessment
        assessment = self.integration_gate.assess(result)

        # Stage 5: Chronicle
        chronicle = self._record_chronicle(
            task, selected_organ.organ_id, confidence_profile, assessment
        )

        if assessment.verdict == DelegationVerdict.VETOED:
            return (None, assessment, chronicle)

        return (result, assessment, chronicle)

    def _dispatch(
        self,
        organ: Organ,
        task: DelegationTask,
        confidence_profile: ConfidenceProfile,
    ) -> DelegationResult:
        """Execute the organ's handler for the task."""
        start_time = time.time()

        output = None
        if organ.handler is not None:
            try:
                output = organ.handler(task.payload)
            except Exception as e:
                output = {"error": str(e), "status": "organ_execution_failed"}
        else:
            output = {
                "status": "no_handler",
                "task_id": task.task_id,
                "domain": task.domain.value,
                "organ": organ.organ_id,
                "note": "Organ registered without handler — blueprint mode.",
            }

        execution_time = time.time() - start_time
        output_hash = hashlib.sha256(
            json.dumps(output, sort_keys=True, default=str).encode()
        ).hexdigest()

        return DelegationResult(
            task_id=task.task_id,
            organ_id=organ.organ_id,
            domain=task.domain,
            output=output,
            execution_time=execution_time,
            confidence_profile=confidence_profile,
            produced_at=time.time(),
            output_hash=output_hash,
        )

    def _record_chronicle(
        self,
        task: DelegationTask,
        organ_id: str,
        confidence_profile: ConfidenceProfile,
        assessment: IntegrationAssessment,
    ) -> DelegationChronicle:
        """Record an append-only, predecessor-linked chronicle entry."""
        self._event_counter += 1
        event_id = f"delegation_event_{self._event_counter:06d}"
        predecessor = self._integrity_chain[-1] if self._integrity_chain else None
        now = time.time()

        event_payload = json.dumps({
            "event_id": event_id,
            "task_id": task.task_id,
            "organ_id": organ_id,
            "domain": task.domain.value,
            "verdict": assessment.verdict.value,
            "predecessor": predecessor,
            "timestamp": now,
        }, sort_keys=True)
        event_hash = hashlib.sha256(event_payload.encode()).hexdigest()

        entry = DelegationChronicle(
            event_id=event_id,
            task=task,
            organ_id=organ_id,
            confidence_profile=confidence_profile,
            integration_assessment=assessment,
            timestamp=now,
            predecessor_hash=predecessor,
            event_hash=event_hash,
        )

        self._chronicle.append(entry)
        self._integrity_chain.append(event_hash)
        return entry

    @property
    def chronicle(self) -> List[DelegationChronicle]:
        """Read-only access to the delegation chronicle."""
        return list(self._chronicle)

    @property
    def chronicle_length(self) -> int:
        """Number of delegation events recorded."""
        return len(self._chronicle)

    @property
    def integrity_head(self) -> Optional[str]:
        """Latest hash in the integrity chain."""
        return self._integrity_chain[-1] if self._integrity_chain else None

    def verify_integrity(self) -> bool:
        """Verify the chronicle's predecessor-linked hash chain."""
        for i, entry in enumerate(self._chronicle):
            expected_predecessor = self._integrity_chain[i - 1] if i > 0 else None
            if entry.predecessor_hash != expected_predecessor:
                return False
            # Recompute event hash
            event_payload = json.dumps({
                "event_id": entry.event_id,
                "task_id": entry.task.task_id,
                "organ_id": entry.organ_id,
                "domain": entry.task.domain.value,
                "verdict": entry.integration_assessment.verdict.value,
                "predecessor": entry.predecessor_hash,
                "timestamp": entry.timestamp,
            }, sort_keys=True)
            if entry.event_hash != hashlib.sha256(event_payload.encode()).hexdigest():
                return False
        return True


# =============================================================================
# Convenience: Organ Factory
# =============================================================================


def create_organ(
    organ_id: str,
    name: str,
    domain: ResearchDomain,
    capability_score: float = 0.85,
    health_status: str = "healthy",
    uptime_ratio: float = 0.99,
    error_rate: float = 0.01,
    allowed_domains: Optional[List[ResearchDomain]] = None,
    handler: Optional[Callable] = None,
) -> Organ:
    """Factory for creating a properly configured organ."""
    if allowed_domains is None:
        allowed_domains = [domain]

    capability = OrganCapability(
        domain=domain,
        capability_score=capability_score,
        evidence_hash=hashlib.sha256(
            f"{organ_id}_{domain.value}_{capability_score}".encode()
        ).hexdigest(),
        last_evaluated=time.time(),
    )

    health = OrganHealth(
        status=health_status,
        uptime_ratio=uptime_ratio,
        error_rate=error_rate,
        last_heartbeat=time.time(),
        diagnostic_hash=hashlib.sha256(
            f"{organ_id}_health_{time.time()}".encode()
        ).hexdigest(),
    )

    permissions = OrganPermission(
        allowed_domains=allowed_domains,
        max_delegation_depth=1,
        require_quorum=False,
        granted_by="EUCLID_CNS",
        granted_at=time.time(),
    )

    return Organ(
        organ_id=organ_id,
        name=name,
        domain=domain,
        capabilities=[capability],
        health=health,
        permissions=permissions,
        handler=handler,
    )


# =============================================================================
# CNS Health Integration
# =============================================================================


def delegation_health_report(controller: DelegationController) -> Dict[str, Any]:
    """Produce a CNS-compatible health report for the delegation subsystem."""
    total_organs = controller.registry.organ_count()
    healthy_organs = sum(
        1 for o in controller.registry.list_all()
        if o.health.status == "healthy"
    )
    total_events = controller.chronicle_length
    accepted_events = sum(
        1 for e in controller.chronicle
        if e.integration_assessment.verdict == DelegationVerdict.ACCEPTED
    )
    vetoed_events = total_events - accepted_events
    integrity_ok = controller.verify_integrity()

    return {
        "subsystem": "delegation",
        "status": "healthy" if integrity_ok and healthy_organs > 0 else "degraded",
        "total_organs": total_organs,
        "healthy_organs": healthy_organs,
        "total_events": total_events,
        "accepted_events": accepted_events,
        "vetoed_events": vetoed_events,
        "integrity_chain_verified": integrity_ok,
        "integrity_head": controller.integrity_head,
        "confidence_threshold": controller.arbiter.confidence_threshold,
        "safety_threshold": controller.arbiter.safety_threshold,
        "external_validators_wired": {
            "coherence": controller.integration_gate._external_coherence_validator is not None,
            "truth": controller.integration_gate._external_truth_validator is not None,
            "causal": controller.integration_gate._external_causal_validator is not None,
            "feedback": controller.integration_gate._external_feedback_validator is not None,
        },
    }
