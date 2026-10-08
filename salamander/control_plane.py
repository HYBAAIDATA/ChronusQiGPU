"""Production #108 homeostasis, recovery and bounded adaptation.

The control plane coordinates existing authorities.  It does not mine, verify
shares, decide OVID transformation verdicts, own THESEUS/hyba_db custody,
manufacture reward, mutate source at runtime, or execute arbitrary
commands/SQL/filesystem operations.

Canonical authority boundary (governance register):
  OVID     — representation transformation + transform lineage/equivalence
  THESEUS  — durable record/custody/integrity/recovery/provenance
  producer — rebuildable projections under the hyba_db contract
SALAMANDER verifies each of those facts independently; no authority may
impersonate another.
"""
from __future__ import annotations

import copy
import time
import threading
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from typing import Any, Callable, Iterable, Mapping

from .models import (
    ActionKind,
    ActionRequest,
    ActionResult,
    ActionVerification,
    Admission,
    AdmissionDecision,
    Availability,
    AutonomicEvent,
    BackendLifecycle,
    CapabilityIdentity,
    CapabilityState,
    ChronusHealthEnvelope,
    CircuitState,
    DatasetPartition,
    HealthDecision,
    HealthObservation,
    HealthState,
    LearningExperience,
    OptimizationTrial,
    OvidTransformEvidence,
    PolicyLifecycle,
    PolicyVersion,
    RebuildableProjection,
    RewardAuthority,
    Severity,
    TheseusRecordIdentity,
    digest,
)

SCHEMA = "salamander.autonomic-control-plane.v1"
EVIDENCE_SCHEMA = "salamander.autonomic.action.v1"
BASE_SHA = "83c187e2cf9a6ef60271c3c6bfcb1b5669e0321e"
CORPUS_SHA256 = "0b4035e138256cfed08ba5d9e1b0058dc8e7c0dbce2e0ccb50039254de4e1712"


class FailClosed(RuntimeError):
    pass


class EvidenceLedger:
    """Hash-chained action evidence that can append to an existing ledger sink."""

    def __init__(self, sink: Callable[[Mapping[str, Any]], None] | None = None) -> None:
        self._records: list[dict[str, Any]] = []
        self._head = "0" * 64
        self._sink = sink

    @property
    def head(self) -> str:
        return self._head

    @property
    def records(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(copy.deepcopy(self._records))

    def append(self, kind: str, payload: Mapping[str, Any], *, at_ns: int) -> str:
        body = {
            "schema": EVIDENCE_SCHEMA,
            "kind": kind,
            "at_ns": int(at_ns),
            "previous_sha256": self._head,
            "payload": copy.deepcopy(dict(payload)),
        }
        seal = digest("salamander.autonomic.evidence.v1", body)
        record = {**body, "evidence_sha256": seal}
        if self._sink is not None:
            self._sink(copy.deepcopy(record))
        self._records.append(record)
        self._head = seal
        return seal

    def verify(self) -> bool:
        previous = "0" * 64
        for record in self._records:
            body = {k: record[k] for k in ("schema", "kind", "at_ns", "previous_sha256", "payload")}
            if record["schema"] != EVIDENCE_SCHEMA or record["previous_sha256"] != previous:
                raise FailClosed("autonomic evidence chain discontinuity")
            if record["evidence_sha256"] != digest("salamander.autonomic.evidence.v1", body):
                raise FailClosed("autonomic evidence digest mismatch")
            previous = record["evidence_sha256"]
        return previous == self._head

    def to_payload(self) -> Mapping[str, Any]:
        body = {
            "schema": "salamander.autonomic-evidence-checkpoint.v1",
            "records": copy.deepcopy(self._records),
            "head": self._head,
        }
        return {**body, "seal": digest("salamander.autonomic-evidence-checkpoint.v1", body)}

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        sink: Callable[[Mapping[str, Any]], None] | None = None,
    ) -> "EvidenceLedger":
        body = {
            "schema": payload.get("schema"),
            "records": payload.get("records"),
            "head": payload.get("head"),
        }
        if body["schema"] != "salamander.autonomic-evidence-checkpoint.v1":
            raise FailClosed("unsupported autonomic evidence checkpoint")
        if payload.get("seal") != digest("salamander.autonomic-evidence-checkpoint.v1", body):
            raise FailClosed("autonomic evidence checkpoint seal mismatch")
        ledger = cls(sink=sink)
        ledger._records = copy.deepcopy(list(body["records"] or ()))
        ledger._head = str(body["head"])
        if not ledger.verify():
            raise FailClosed("autonomic evidence checkpoint head mismatch")
        return ledger


class CircuitBreaker:
    def __init__(self, failure_limit: int = 3, cooldown_ns: int = 1_000_000_000) -> None:
        if failure_limit <= 0 or cooldown_ns <= 0:
            raise ValueError("circuit bounds must be positive")
        self.failure_limit = failure_limit
        self.cooldown_ns = cooldown_ns
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.opened_at_ns: int | None = None
        self.probe_in_flight = False

    def admit(self, now_ns: int) -> bool:
        if self.state is CircuitState.CLOSED:
            return True
        if self.state is CircuitState.OPEN:
            if self.opened_at_ns is None or now_ns - self.opened_at_ns < self.cooldown_ns:
                return False
            self.state = CircuitState.HALF_OPEN
        if self.probe_in_flight:
            return False
        self.probe_in_flight = True
        return True

    def record(self, success: bool, now_ns: int) -> None:
        self.probe_in_flight = False
        if success:
            self.failures = 0
            self.opened_at_ns = None
            self.state = CircuitState.CLOSED
            return
        self.failures += 1
        if self.state is CircuitState.HALF_OPEN or self.failures >= self.failure_limit:
            self.state = CircuitState.OPEN
            self.opened_at_ns = now_ns


@dataclass(frozen=True)
class RecoveryStep:
    step_id: str
    request: ActionRequest
    depends_on: tuple[str, ...] = ()
    rollback: ActionRequest | None = None


@dataclass(frozen=True)
class RecoveryPlan:
    recovery_id: str
    tenant_id: str
    target: str
    steps: tuple[RecoveryStep, ...]
    max_actions: int
    deadline_ns: int

    def ordered(self) -> tuple[RecoveryStep, ...]:
        action_budget_cost = sum(1 + int(step.rollback is not None) for step in self.steps)
        if action_budget_cost > self.max_actions:
            raise FailClosed("recovery exceeds action budget")
        by_id = {s.step_id: s for s in self.steps}
        if len(by_id) != len(self.steps):
            raise FailClosed("duplicate recovery step")
        for step in self.steps:
            if step.request.tenant_id != self.tenant_id:
                raise FailClosed("recovery step tenant does not match recovery plan")
            if step.request.target != self.target:
                raise FailClosed("recovery step target does not match recovery plan")
            if step.rollback is not None:
                rollback = step.rollback
                if rollback.kind is not ActionKind.ROLLBACK:
                    raise FailClosed("recovery rollback must use ActionKind.ROLLBACK")
                if rollback.tenant_id != self.tenant_id:
                    raise FailClosed("recovery rollback tenant does not match recovery plan")
                if rollback.target != self.target:
                    raise FailClosed("recovery rollback target does not match recovery plan")
                if rollback.action_id == step.request.action_id:
                    raise FailClosed("recovery action and rollback require distinct action ids")
                if rollback.idempotency_key == step.request.idempotency_key:
                    raise FailClosed(
                        "recovery action and rollback require distinct idempotency keys"
                    )
        ordered: list[RecoveryStep] = []
        remaining = dict(by_id)
        while remaining:
            ready = sorted(
                (s for s in remaining.values() if set(s.depends_on) <= {x.step_id for x in ordered}),
                key=lambda s: s.step_id,
            )
            if not ready:
                raise FailClosed("recovery DAG is cyclic or references missing dependencies")
            for step in ready:
                ordered.append(step)
                remaining.pop(step.step_id)
        return tuple(ordered)


class ActionRegistry:
    """Bounded actuators paired with independent postcondition verifiers."""

    def __init__(self) -> None:
        self._authorizer = None
        self._handlers: dict[
            str,
            tuple[
                set[ActionKind],
                Callable[[ActionRequest], Mapping[str, Any]],
                str,
                Callable[[ActionRequest, Mapping[str, Any]], Mapping[str, Any]],
            ],
        ] = {}

    def register(
        self,
        name: str,
        kinds: Iterable[ActionKind],
        handler: Callable[[ActionRequest], Mapping[str, Any]],
        *,
        verifier_id: str,
        verifier: Callable[[ActionRequest, Mapping[str, Any]], Mapping[str, Any]],
    ) -> None:
        if not name or name in self._handlers or not callable(handler):
            raise ValueError("handler must be callable, named and unique")
        if not verifier_id or not callable(verifier):
            raise ValueError("an independent named postcondition verifier is required")
        allowed = set(kinds)
        if not allowed:
            raise ValueError("handler must have explicit action kinds")
        self._handlers[name] = (allowed, handler, verifier_id, verifier)

    def bind_authorizer(self, authorizer: Any) -> None:
        from .authority import ALHarasActionAuthorizer
        if not isinstance(authorizer, ALHarasActionAuthorizer):
            raise FailClosed("registry requires canonical AL HARAS authorizer")
        if self._authorizer is not None and self._authorizer is not authorizer:
            raise FailClosed("registry already belongs to another authorisation boundary")
        self._authorizer = authorizer

    def execute(
        self, request: ActionRequest, *, authorization: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        if self._authorizer is None or authorization is None:
            raise FailClosed("registry actuation requires bound AL HARAS authorization")
        if not self._authorizer.consume_decision(request, authorization):
            raise FailClosed("registry authorization is expired, forged or unbound")
        registered = self._handlers.get(request.handler)
        if registered is None:
            raise FailClosed("unregistered action handler")
        kinds, handler, _, _ = registered
        if request.kind not in kinds:
            raise FailClosed("handler is not registered for action kind")
        return dict(handler(request))

    def verify(
        self, request: ActionRequest, response: Mapping[str, Any]
    ) -> ActionVerification:
        registered = self._handlers.get(request.handler)
        if registered is None:
            raise FailClosed("unregistered action handler")
        _, _, verifier_id, verifier = registered
        result = dict(verifier(request, dict(response)))
        verified = result.get("verified") is True
        evidence_ref = result.get("evidence_ref")
        return ActionVerification(
            verifier_id=verifier_id,
            verified=verified,
            evidence_ref=str(evidence_ref) if evidence_ref else None,
            observations=dict(result.get("observations", {})),
            error=None if verified else str(result.get("error") or "postcondition not proven"),
        )


class HealthEnvelope:
    """Multidimensional homeostasis without opaque synthetic health scores."""

    PRECEDENCE = {
        HealthState.UNKNOWN: 0,
        HealthState.HEALTHY: 1,
        HealthState.PRESSURED: 2,
        HealthState.DEGRADED: 3,
        HealthState.RECOVERING: 4,
        HealthState.QUARANTINED: 5,
        HealthState.UNAVAILABLE: 6,
        HealthState.FAILED: 7,
    }

    def decide(
        self,
        observations: Iterable[HealthObservation],
        *,
        now_ns: int,
        policy_id: str,
    ) -> HealthDecision:
        values = tuple(observations)
        if not values:
            return HealthDecision(HealthState.UNKNOWN, ("no observations",), (), now_ns, policy_id)
        states: list[HealthState] = []
        reasons: list[str] = []
        for obs in values:
            if obs.availability in (Availability.UNAVAILABLE, Availability.NOT_MEASURED):
                states.append(HealthState.UNAVAILABLE)
                reasons.append(f"{obs.subsystem}.{obs.dimension}:{obs.availability.value}")
                continue
            if obs.availability is Availability.NOT_APPLICABLE:
                continue
            state = self._state_from_value(obs)
            states.append(state)
            if state is not HealthState.HEALTHY:
                reasons.append(f"{obs.subsystem}.{obs.dimension}:{state.value}")
        state = max(states, key=self.PRECEDENCE.get) if states else HealthState.UNKNOWN
        return HealthDecision(state, tuple(reasons), values, now_ns, policy_id)

    @staticmethod
    def _state_from_value(obs: HealthObservation) -> HealthState:
        if isinstance(obs.value, bool):
            return HealthState.HEALTHY if obs.value else HealthState.FAILED
        if isinstance(obs.value, str):
            try:
                return HealthState(obs.value.upper())
            except ValueError:
                return HealthState.UNKNOWN
        # Numeric values require the producer to supply explicit state semantics.
        return HealthState.UNKNOWN


class AutonomicControlPlane:
    def __init__(
        self,
        *,
        registry: ActionRegistry,
        ledger: EvidenceLedger | None = None,
        clock_ns: Callable[[], int] = time.time_ns,
        max_recoveries_per_target: int = 2,
        authorizer: Callable[[ActionRequest], Mapping[str, Any]] | None = None,
        require_authorization: bool = True,
    ) -> None:
        self.registry = registry
        self.ledger = ledger or EvidenceLedger()
        self.clock_ns = clock_ns
        if type(max_recoveries_per_target) is not int or max_recoveries_per_target <= 0:
            raise ValueError("positive recovery budget required")
        self.max_recoveries_per_target = max_recoveries_per_target
        self.health = HealthEnvelope()
        self.capabilities: dict[CapabilityIdentity, CapabilityState] = {}
        self.circuits: dict[str, CircuitBreaker] = {}
        self.events: deque[AutonomicEvent] = deque(maxlen=2048)
        self._recoveries: dict[tuple[str, str], int] = defaultdict(int)
        self._idempotency: dict[tuple[str, str, str], ActionResult] = {}
        self._request_fingerprints: dict[tuple[str, str, str], str] = {}
        self._in_doubt: set[tuple[str, str, str]] = set()
        self._execution_lock = threading.RLock()
        self._tenant_capacity: dict[str, int] = {}
        self._tenant_inflight: dict[str, int] = defaultdict(int)
        self._policies: dict[str, PolicyVersion] = {}
        self._current_policy: str | None = None
        self._baseline_metrics: dict[str, tuple[float, float, bool]] = {}
        self.authorizer = authorizer
        self.require_authorization = bool(require_authorization)

    def _authorize(self, request: ActionRequest) -> Mapping[str, Any]:
        """Require an evidence-bearing security verdict before actuation.

        Production composition is fail-closed by default. Tests or isolated
        research callers may opt out only by explicitly constructing the
        control plane with require_authorization=False.
        """
        if not self.require_authorization:
            return {
                "allowed": True,
                "authority": "AUTHORIZATION_EXPLICITLY_DISABLED",
                "reason": "non-production composition opted out",
                "actor": request.actor_id or "UNSPECIFIED",
                "evidence_id": None,
            }
        if not request.actor_id.strip():
            return {
                "allowed": False,
                "authority": "AL_HARAS",
                "reason": "ACTOR_REQUIRED",
                "actor": "",
                "evidence_id": None,
            }
        if self.authorizer is None:
            return {
                "allowed": False,
                "authority": "AL_HARAS",
                "reason": "AUTHORIZER_UNAVAILABLE",
                "actor": request.actor_id,
                "evidence_id": None,
            }
        try:
            decision = dict(self.authorizer(request))
        except Exception as exc:
            return {
                "allowed": False,
                "authority": "AL_HARAS",
                "reason": f"AUTHORIZER_ERROR:{type(exc).__name__}",
                "actor": request.actor_id,
                "evidence_id": None,
            }
        decision.setdefault("authority", "AL_HARAS")
        decision.setdefault("actor", request.actor_id)
        evidence_id = decision.get("evidence_id") or decision.get("evidence_ref")
        if decision.get("allowed") is True and not evidence_id:
            return {
                **decision,
                "allowed": False,
                "reason": "AUTHORIZATION_EVIDENCE_REQUIRED",
            }
        return decision

    # --------------------------------------------------------- health/events
    def observe(
        self, observations: Iterable[HealthObservation], *, policy_id: str = "default"
    ) -> HealthDecision:
        decision = self.health.decide(observations, now_ns=self.clock_ns(), policy_id=policy_id)
        event = AutonomicEvent(
            event_id=decision.decision_id,
            kind="HEALTH_DECISION",
            tenant_id=decision.observations[0].tenant_id if decision.observations else "system",
            subsystem="aggregate",
            severity=Severity.ERROR if decision.state in {HealthState.FAILED, HealthState.UNAVAILABLE} else Severity.INFO,
            observed_at_ns=decision.decided_at_ns,
            decision_id=decision.decision_id,
            attributes={"state": decision.state.value, "reasons": decision.reasons},
        )
        self.events.append(event)
        self.ledger.append("health-decision", asdict(decision), at_ns=decision.decided_at_ns)
        return decision

    # ------------------------------------------------ backend/capability truth
    def discover(self, identity: CapabilityIdentity) -> CapabilityState:
        state = self.capabilities.setdefault(identity, CapabilityState(identity))
        return state

    def qualify(
        self, identity: CapabilityIdentity, *, passed: bool, evidence_ref: str, expires_at_ns: int
    ) -> CapabilityState:
        state = self.discover(identity)
        state.qualification_ref = evidence_ref
        state.qualified_at_ns = self.clock_ns()
        state.expires_at_ns = expires_at_ns
        state.lifecycle = BackendLifecycle.QUALIFIED if passed else BackendLifecycle.QUARANTINED
        state.quarantine_reason = None if passed else "qualification failed"
        self.ledger.append("capability-qualification", asdict(state), at_ns=self.clock_ns())
        return state

    def refresh_qualification(
        self, identity: CapabilityIdentity, verifier: Callable[[CapabilityIdentity], tuple[bool, str, int]]
    ) -> CapabilityState:
        passed, evidence_ref, expires_at_ns = verifier(identity)
        return self.qualify(
            identity, passed=bool(passed), evidence_ref=evidence_ref, expires_at_ns=int(expires_at_ns)
        )

    def chronus_envelope(
        self, identity: CapabilityIdentity, *, requested_operation: str
    ) -> ChronusHealthEnvelope:
        state = self.capabilities.get(identity)
        now = self.clock_ns()
        if state is None or state.lifecycle is BackendLifecycle.DISCOVERED:
            health, action = HealthState.UNAVAILABLE, ActionKind.DEFER
        elif state.expires_at_ns is not None and now >= state.expires_at_ns:
            state.lifecycle = BackendLifecycle.QUARANTINED
            state.quarantine_reason = "qualification expired"
            health, action = HealthState.QUARANTINED, ActionKind.REQUALIFY
        elif state.lifecycle is BackendLifecycle.QUALIFIED:
            health, action = HealthState.HEALTHY, ActionKind.REPLAN
        elif state.lifecycle is BackendLifecycle.DEGRADED:
            health, action = HealthState.DEGRADED, ActionKind.THROTTLE
        elif state.lifecycle is BackendLifecycle.QUARANTINED:
            health, action = HealthState.QUARANTINED, ActionKind.FAILOVER
        else:
            health, action = HealthState.UNAVAILABLE, ActionKind.REJECT
        legal = (requested_operation,) if health is HealthState.HEALTHY else ()
        prohibited = () if legal else (requested_operation,)
        return ChronusHealthEnvelope(
            identity.backend_id,
            identity.device_id,
            health,
            legal,
            prohibited,
            action,
            tuple(filter(None, (state.qualification_ref if state else None,))),
            now,
            {
                "precision": identity.precision,
                "f64_boundary": "CPU_OR_EXACT_INTEGER_UNTIL_CERTIFIED_FP64",
                "opencl.BINET_EXACT": "UNSUPPORTED",
                "FOLDED_NATIVE": "OPEN",
            },
        )

    # ---------------------------------------------------- admission/isolation
    def set_tenant_capacity(self, tenant_id: str, limit: int) -> None:
        if not tenant_id or limit <= 0:
            raise ValueError("tenant and positive capacity required")
        self._tenant_capacity[tenant_id] = limit

    def admit(self, tenant_id: str, workload_id: str, isolation_key: str) -> Admission:
        if not isolation_key.startswith(tenant_id + ":"):
            return Admission(AdmissionDecision.ISOLATE, tenant_id, workload_id, "isolation mismatch", None, isolation_key)
        limit = self._tenant_capacity.get(tenant_id)
        if limit is None:
            return Admission(AdmissionDecision.DEFER, tenant_id, workload_id, "capacity unavailable", None, isolation_key)
        if self._tenant_inflight[tenant_id] >= limit:
            return Admission(AdmissionDecision.DEFER, tenant_id, workload_id, "tenant capacity exhausted", f"limit:{limit}", isolation_key)
        self._tenant_inflight[tenant_id] += 1
        return Admission(AdmissionDecision.ADMIT, tenant_id, workload_id, "within isolated quota", f"limit:{limit}", isolation_key)

    def release(self, tenant_id: str) -> None:
        self._tenant_inflight[tenant_id] = max(0, self._tenant_inflight[tenant_id] - 1)

    # ------------------------------------------------------------ actuation
    def execute(self, request: ActionRequest) -> ActionResult:
        # Serialize admission, durable reservation, actuator and verifier. A
        # second thread cannot race past an idempotency/circuit budget gate.
        with self._execution_lock:
            return self._execute_locked(copy.deepcopy(request))

    def _execute_locked(self, request: ActionRequest) -> ActionResult:
        if not request.idempotency_key or not request.action_id:
            raise FailClosed("action identity and idempotency key required")
        key = self._action_key(request)
        fingerprint = digest("salamander.action-request.v1", asdict(request))
        if key in self._request_fingerprints and self._request_fingerprints[key] != fingerprint:
            raise FailClosed("idempotency key reused for different request")
        if key in self._in_doubt:
            raise FailClosed("prior action outcome is uncertain; owner reconciliation required")
        if key in self._idempotency:
            return self._idempotency[key]
        now = self.clock_ns()
        authorization = self._authorize(request)
        authorization_ref = self.ledger.append(
            "action-authorization",
            authorization,
            at_ns=now,
        )
        if authorization.get("allowed") is not True:
            reason = str(authorization.get("reason") or "authorization denied")
            self.ledger.append(
                "action-rejected",
                {
                    "action_id": request.action_id,
                    "reason": reason,
                    "authorization_ref": authorization_ref,
                },
                at_ns=self.clock_ns(),
            )
            raise FailClosed(f"AL HARAS authorization denied: {reason}")

        circuit = self.circuits.setdefault(request.handler, CircuitBreaker())
        if not circuit.admit(now):
            raise FailClosed("handler circuit is open")
        before = self.ledger.append(
            "action-proposed",
            {
                **asdict(request),
                "authorization_ref": authorization_ref,
                "authorization_evidence_id": (
                    authorization.get("evidence_id") or authorization.get("evidence_ref")
                ),
            },
            at_ns=now,
        )
        try:
            response = self.registry.execute(request, authorization=authorization)
            execution_ref = self.ledger.append(
                "action-result-payload", response, at_ns=self.clock_ns()
            )
            try:
                verification = self.registry.verify(request, response)
            except Exception as exc:
                verification = ActionVerification(
                    verifier_id="unavailable",
                    verified=False,
                    evidence_ref=None,
                    observations={"execution_ref": execution_ref},
                    error=f"{type(exc).__name__}: {exc}",
                )
            verification_ref = self.ledger.append(
                "action-independent-verification",
                asdict(verification),
                at_ns=self.clock_ns(),
            )
            verified = verification.verified
            result = ActionResult(
                request.action_id, "VERIFIED" if verified else "UNVERIFIED",
                now, self.clock_ns(), request.handler, before, verification_ref, verified,
                verification.error,
            )
            circuit.record(verified, self.clock_ns())
            self._record_circuit(circuit_key, circuit)
        except FailClosed as exc:
            # A structural contract violation (unregistered handler, wrong
            # action kind) is not an execution outcome: it must propagate
            # fail-closed rather than degrade into a FAILED result record.
            circuit.record(False, self.clock_ns())
            self._record_circuit(circuit_key, circuit)
            self.ledger.append(
                "action-rejected",
                {"action_id": request.action_id, "reason": str(exc)},
                at_ns=self.clock_ns(),
            )
            raise
        except Exception as exc:
            circuit.record(False, self.clock_ns())
            self._record_circuit(circuit_key, circuit)
            result = ActionResult(
                request.action_id, "FAILED", now, self.clock_ns(), request.handler,
                before, None, False, f"{type(exc).__name__}: {exc}",
            )
        self.ledger.append("action-result", {
            "result": asdict(result), "request_key": list(key),
        }, at_ns=result.completed_at_ns)
        self._idempotency[key] = result
        self._in_doubt.discard(key)
        return result

    def recover(self, plan: RecoveryPlan) -> tuple[ActionResult, ...]:
        """Execute one bounded recovery DAG with verified rollback on rejection.

        A handler may have changed external state before its independent
        postcondition verifier rejects the result.  In that case the recovery
        must not merely stop and leave an unverified mutation behind: a
        declared ROLLBACK action is executed through the same AL HARAS
        authorization, idempotency, circuit and independent-verification
        boundary.  Missing or unverified rollback fails closed.
        """
        if self.clock_ns() > plan.deadline_ns:
            raise FailClosed("recovery deadline elapsed")
        key = (plan.tenant_id, plan.target)
        if self._recoveries[key] >= self.max_recoveries_per_target:
            self.ledger.append("recovery-escalated", {
                "tenant_id": plan.tenant_id, "target": plan.target,
                "recovery_id": plan.recovery_id, "reason": "recovery budget exhausted",
            }, at_ns=self.clock_ns())
            raise FailClosed("recovery budget exhausted")
        ordered = plan.ordered()
        self._recoveries[plan.target] += 1
        results: list[ActionResult] = []
        by_step: dict[str, ActionResult] = {}
        for step in ordered:
            if any(not by_step[d].verified for d in step.depends_on):
                break
            result = self.execute(step.request)
            results.append(result)
            by_step[step.step_id] = result
            if result.verified:
                continue
            if step.rollback is None:
                self.ledger.append(
                    "recovery-rollback-required",
                    {
                        "recovery_id": plan.recovery_id,
                        "step_id": step.step_id,
                        "action_id": result.action_id,
                        "status": result.status,
                        "reason": result.error or "independent verification rejected action",
                    },
                    at_ns=self.clock_ns(),
                )
                raise FailClosed("unverified recovery action has no rollback")
            rollback_result = self.execute(step.rollback)
            results.append(rollback_result)
            self.ledger.append(
                "recovery-rollback-result",
                {
                    "recovery_id": plan.recovery_id,
                    "step_id": step.step_id,
                    "failed_action_id": result.action_id,
                    "rollback_action_id": rollback_result.action_id,
                    "rollback_verified": rollback_result.verified,
                    "rollback_status": rollback_result.status,
                },
                at_ns=self.clock_ns(),
            )
            if not rollback_result.verified:
                raise FailClosed("rollback failed independent verification")
            break
        return tuple(results)

    # ------------------------------------------- THESEUS / OVID / projection
    def verify_theseus_custody(
        self,
        identity: TheseusRecordIdentity,
        verifier: Callable[[TheseusRecordIdentity], Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        """Independent check that a THESEUS custody record is intact.

        Custody/integrity facts are THESEUS's alone: the verifier re-reads
        the durable record and reports its observed digest.  A producer's
        claim never substitutes for the custody check.
        """
        result = dict(verifier(identity))
        if result.get("payload_sha256") != identity.payload_sha256 or not result.get("valid"):
            raise FailClosed("THESEUS custody verification failed")
        self.ledger.append("theseus-custody-verified", result, at_ns=self.clock_ns())
        return result

    def verify_ovid_transform(
        self,
        evidence: OvidTransformEvidence,
        verifier: Callable[[OvidTransformEvidence], Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        """Independent check that an OVID transformation is valid.

        The verifier answers the OVID equivalence question for the declared
        lineage.  A verdict not bound to this lineage id and its input/output
        digests is not evidence for this transform.
        """
        result = dict(verifier(evidence))
        bound = (
            result.get("lineage_id") == evidence.lineage_id
            and result.get("input_sha256") == evidence.input_sha256
            and result.get("output_digest") == evidence.output_digest
        )
        if not result.get("valid") or not bound:
            raise FailClosed("OVID transformation verification failed")
        self.ledger.append("ovid-transform-verified", result, at_ns=self.clock_ns())
        return result

    def verify_projection(
        self,
        projection: RebuildableProjection,
        verifier: Callable[[], Any],
        custody_verifier: Callable[[TheseusRecordIdentity], Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        """Projection/database validity under the producer contract.

        A rebuildable projection is only as good as its durable anchor, so
        THESEUS custody is proven independently and first; the projection
        check itself is the producer/hyba_db contract, not a THESEUS or OVID
        fact.
        """
        self.verify_theseus_custody(projection.custody_identity, custody_verifier)
        raw = verifier()  # expected to be OntologyStore.verify_database()
        result = asdict(raw) if hasattr(raw, "__dataclass_fields__") else dict(raw)
        valid = bool(result.get("valid", result.get("ok", False)))
        observed = result.get("projection_sha256")
        drift = observed is not None and observed != projection.projection_sha256
        status = {"valid": valid and not drift, "drift": drift, "details": result}
        self.ledger.append("projection-verified", status, at_ns=self.clock_ns())
        return status

    # ------------------------------------------------ learning and deployment
    def form_experience(
        self,
        *,
        replay_id: str,
        tenant_id: str,
        task: str,
        observation_ref: str,
        action: str,
        outcome_ref: str,
        reward_authority: RewardAuthority = RewardAuthority.NONE,
        reward: float | None = None,
        partition: DatasetPartition = DatasetPartition.INCIDENT,
        temporal_lineage: str,
    ) -> LearningExperience:
        experience = LearningExperience(
            replay_id, tenant_id, task, observation_ref, action, outcome_ref,
            reward_authority, reward, partition, temporal_lineage,
        )
        self.ledger.append("governed-experience", asdict(experience), at_ns=self.clock_ns())
        return experience

    def register_policy(self, policy: PolicyVersion) -> None:
        if policy.policy_id in self._policies:
            raise FailClosed("policy identity already registered")
        self._policies[policy.policy_id] = policy

    def transition_policy(self, policy_id: str, target: PolicyLifecycle, evidence_ref: str) -> PolicyVersion:
        policy = self._policies[policy_id]
        order = [
            PolicyLifecycle.CANDIDATE, PolicyLifecycle.TRAINED, PolicyLifecycle.VALIDATED,
            PolicyLifecycle.FINAL_TESTED, PolicyLifecycle.SHADOW, PolicyLifecycle.CANARY,
            PolicyLifecycle.PROMOTED,
        ]
        if target in {PolicyLifecycle.ROLLED_BACK, PolicyLifecycle.QUARANTINED}:
            policy.lifecycle = target
        else:
            expected = order[order.index(policy.lifecycle) + 1] if policy.lifecycle in order[:-1] else None
            if target is not expected:
                raise FailClosed("policy lifecycle transition skipped a gate")
            policy.lifecycle = target
        policy.evidence_refs.append(evidence_ref)
        if target is PolicyLifecycle.PROMOTED:
            self._current_policy = policy_id
        self.ledger.append("policy-transition", asdict(policy), at_ns=self.clock_ns())
        return policy

    def set_baseline(
        self,
        metric: str,
        mean: float,
        tolerance: float,
        *,
        higher_is_better: bool = True,
    ) -> None:
        if not metric or tolerance < 0:
            raise ValueError("metric and non-negative tolerance are required")
        self._baseline_metrics[metric] = (
            float(mean), float(tolerance), bool(higher_is_better)
        )

    def regression(self, metric: str, measured: float) -> bool:
        if metric not in self._baseline_metrics:
            raise FailClosed("regression baseline unavailable")
        mean, tolerance, higher_is_better = self._baseline_metrics[metric]
        value = float(measured)
        return value < mean - tolerance if higher_is_better else value > mean + tolerance

    def evaluate_optimization(
        self,
        trial: OptimizationTrial,
        verifier: Callable[[OptimizationTrial], Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        policy = self._policies.get(trial.policy_id)
        if policy is None:
            raise FailClosed("optimization policy is not registered")
        if policy.lifecycle not in {
            PolicyLifecycle.VALIDATED,
            PolicyLifecycle.FINAL_TESTED,
            PolicyLifecycle.SHADOW,
            PolicyLifecycle.CANARY,
            PolicyLifecycle.PROMOTED,
        }:
            raise FailClosed("optimization policy has not reached an evaluation gate")
        baseline = dict(trial.baseline_measurements)
        candidate = dict(trial.candidate_measurements)
        missing = sorted(set(candidate) - set(self._baseline_metrics))
        if missing:
            raise FailClosed("optimization baselines unavailable: " + ", ".join(missing))
        verification = dict(verifier(trial))
        independently_verified = verification.get("verified") is True
        verifier_ref = str(verification.get("evidence_ref") or "")
        if independently_verified and not verifier_ref:
            raise FailClosed("independent optimization evidence is required")
        regressions: list[str] = []
        improvements: list[str] = []
        for metric, value in candidate.items():
            configured, tolerance, higher_is_better = self._baseline_metrics[metric]
            if abs(float(baseline[metric]) - configured) > tolerance:
                raise FailClosed(f"optimization baseline drifted for {metric}")
            delta = float(value) - float(baseline[metric])
            if self.regression(metric, value):
                regressions.append(metric)
            elif (higher_is_better and delta > tolerance) or (
                not higher_is_better and delta < -tolerance
            ):
                improvements.append(metric)
        accepted = independently_verified and not regressions and bool(improvements)
        result = {
            "trial_id": trial.trial_id,
            "policy_id": trial.policy_id,
            "partition": trial.partition.value,
            "sample_count": trial.sample_count,
            "accepted": accepted,
            "regressions": tuple(sorted(regressions)),
            "improvements": tuple(sorted(improvements)),
            "trial_evidence_ref": trial.evidence_ref,
            "verifier_evidence_ref": verifier_ref or None,
        }
        evidence = self.ledger.append(
            "optimization-evaluation", result, at_ns=self.clock_ns()
        )
        if not accepted:
            target = (
                PolicyLifecycle.ROLLED_BACK
                if policy.lifecycle is PolicyLifecycle.PROMOTED
                else PolicyLifecycle.QUARANTINED
            )
            self.transition_policy(policy.policy_id, target, evidence)
        return result

    def rollback_on_regression(self, policy_id: str, measurements: Mapping[str, float], evidence_ref: str) -> bool:
        regressed = any(self.regression(name, value) for name, value in measurements.items())
        if regressed:
            self.transition_policy(policy_id, PolicyLifecycle.ROLLED_BACK, evidence_ref)
            return True
        return False

    # ---------------------------------------------------------- restart/API
    def reacquire_truth(
        self,
        probes: Mapping[str, Callable[[], Mapping[str, Any]]],
    ) -> Mapping[str, Any]:
        """Never restore liveness/health from stale process memory."""
        acquired: dict[str, Any] = {}
        for name in sorted(probes):
            try:
                acquired[name] = {"availability": "MEASURED", "value": dict(probes[name]())}
            except Exception as exc:
                acquired[name] = {"availability": "UNAVAILABLE", "error": type(exc).__name__}
        self.ledger.append("restart-truth-reacquired", acquired, at_ns=self.clock_ns())
        return acquired

    def mining107_snapshot(self, integration: Any, *, hasher: Any, recovery: Any) -> Mapping[str, Any]:
        """Consume #107 evidence; do not duplicate its mining recovery policy."""
        snapshot = dict(integration.snapshot(hasher=hasher, recovery=recovery))
        if snapshot.get("schema") != "chronus.production-mining-integration.v1":
            raise FailClosed("invalid #107 mining integration")
        self.ledger.append("mining107-consumed", snapshot, at_ns=self.clock_ns())
        return snapshot

    def api_snapshot(self) -> Mapping[str, Any]:
        return {
            "schema": SCHEMA,
            "base_sha": BASE_SHA,
            "conformance_corpus_sha256": CORPUS_SHA256,
            "routes": {
                "/api/salamander/health": "AVAILABLE",
                "/api/salamander/events": "AVAILABLE",
                "/api/salamander/backends": "AVAILABLE",
                "/api/salamander/recoveries": "AVAILABLE",
                "/api/salamander/policies": "AVAILABLE",
                "/api/salamander/evidence": "AVAILABLE",
            },
            "capabilities": [
                {
                    "identity": asdict(identity),
                    "state": asdict(state),
                }
                for identity, state in sorted(
                    self.capabilities.items(),
                    key=lambda item: (
                        item[0].backend_id, item[0].device_id, item[0].capability,
                        item[0].precision, item[0].implementation_digest,
                    ),
                )
            ],
            "circuits": {
                name: {"state": breaker.state.value, "failures": breaker.failures}
                for name, breaker in sorted(self.circuits.items())
            },
            "policies": {name: asdict(value) for name, value in sorted(self._policies.items())},
            "current_policy": self._current_policy,
            "evidence_head": self.ledger.head,
        }
