# Salamander × HYBA × TOE — Adaptive Resilience Contract

## Product intent

Salamander is the consolidated platform's autonomic resilience layer: anomaly
detection, fault diagnosis, bounded self-healing, and self-optimization. It is
not a separate product stack. It coordinates the existing authorities and
subsystems; it must not become a second source of truth for identity, evidence
custody, execution validity, or policy.

The human design reference is the *24* CTU pairing of Jack Bauer and Chloe
O'Brian, translated into engineering roles rather than copied as unchecked
autonomy:

- **Chloe mode — technical operations:** correlate telemetry, detect anomalies,
  investigate likely causes, explain confidence and uncertainty, recommend
  diagnostics, and coordinate subsystems.
- **Jack mode — time-critical response:** prioritize containment, continuity,
  and recovery under a deadline; use only pre-authorized, bounded, reversible
  actions; escalate when evidence or authority is insufficient.
- **Salamander control plane:** joins those modes with typed health, policy,
  admission, recovery, outcome verification, and auditable learning.

For a concise incident-commander operating view and rollout checklist, see [`SALAMANDER_HYBA_GOVERNOR.md`](SALAMANDER_HYBA_GOVERNOR.md). This is a supplemental operating guide; the canonical implementation remains the existing control plane below.

## Canonical implementation

The repository already contains the Salamander Autonomic Control Plane at
`salamander.control_plane.AutonomicControlPlane`, typed models in
`salamander.models`, and the design contract in
`docs/SALAMANDER_AUTONOMIC_CONTROL_PLANE.md`. Integrate this canonical control
plane; do not create a parallel healer in the HYBA offering.

The existing implementation distinguishes observation, proposal, dispatch,
acknowledgement, and post-action verification. It has typed states for unknown,
unavailable, degraded, recovering and failed, and bounded registered action
kinds such as replan, throttle, failover, defer, reject, quarantine, requalify,
rebuild projection, restore custody, circuit-breaker operations and rollback.
Use the existing registered action handlers and authority boundaries.

## Placement in HYBA topology

1. **HYBA trust and evidence plane** authenticates tenant, purpose, source,
   classification and allowed operations before observations enter the system.
2. **Telemetry/evidence normalizer** records provenance, event time, source
   health and data-quality flags. Missing telemetry is UNKNOWN/UNAVAILABLE,
   never healthy by default.
3. **TOE** reasons over the normalized evidence and shared problem contract;
   its five forms are predictive, causal, counterfactual, topological and
   geometric. They explain and compare hypotheses, not grant authority.
4. **Millennium Maths API** remains a separate mathematical sidecar for bounded,
   non-sensitive mathematical workloads only. Do not forward mission telemetry,
   identifiers, incident payloads or classified information to it.
5. **Salamander** fuses runtime health and authorized evidence, diagnoses
   anomalies, selects a registered recovery plan, verifies the outcome and
   rolls back or escalates on regression.
6. **AL HARAS / L-HRAS governance** remains the policy and authorization gate.
   Salamander may propose or execute only the exact actions that existing
   policy and action registration permit. It cannot loosen the policy that
   authorized it.
7. **Chronus or the relevant execution owner** performs actions through its
   qualified execution contract. Salamander must not execute arbitrary shell,
   SQL, dynamic code, arbitrary filesystem writes or unregistered runtime
   patches.
8. **Evidence and feedback** record proposal, authorization, dispatch,
   acknowledgement, verification, result, model/policy version and rollback.
   Learning consumes verified outcomes only; an observation is not a reward.

## Capability contracts

### Anomaly detection

- Start with explicit per-component signals and baselines: latency, error rate,
  resource pressure, queue depth, dependency health, drift, integrity and
  missing/stale telemetry.
- Emit anomaly ID, affected component/tenant scope, observed interval, baseline
  version, evidence references, severity, confidence, plausible causes and
  recommended next diagnostic.
- Correlate signals through TOE's causal and topological reasoning. A score is
  a triage signal, not proof of malicious activity.
- Measure precision/recall, false-positive rate, time-to-detect, detection
  delay, drift and per-tenant performance on temporal holdouts.

### Self-healing

- Classify the incident and check preconditions before any action.
- Default to diagnosis-only when telemetry is missing, evidence conflicts,
  authority is unavailable or the action is not registered.
- Permit unattended actions only from a narrow, reviewed allow-list with
  tenant scope, explicit bounds, idempotency key, action budget, deadline,
  cooldown, and a known rollback.
- Require before/after health checks and independent post-action verification.
  A successful handler return is not proof of recovery.
- Circuit-break, quarantine, defer or escalate if the recovery fails, repeats,
  regresses health, or exceeds its budget.
- High-impact policy changes, evidence deletion, security-control weakening,
  cross-tenant changes and mission-consequential decisions require explicit
  approval and must never be learned into autonomous authority.

### Self-optimization

- Optimize declared service objectives (availability, latency, throughput,
  cost, resource efficiency) subject to hard constraints for security,
  correctness, fairness, tenant isolation and safety.
- Establish a deterministic baseline; run offline replay and counterfactual
  analysis; evaluate on held-out time windows; then shadow, canary, promote.
- Every policy change carries a version, experiment, objective, constraints,
  evidence, approval, rollback condition and measured outcome.
- Optimization cannot rewrite acceptance tests, change the meaning of health,
  relax security constraints, manufacture rewards or redefine execution
  conformance.

## Typed event envelope

Every observation and action should carry these fields (or an equivalent
versioned schema): `schema_version`, `event_id`, `tenant_id`,
`purpose`, `component_id`, `observed_at`, `received_at`,
`source_id`, `source_version`, `health_state`, `availability`,
`evidence_refs`, `anomaly_class`, `confidence`, `severity`,
`proposed_action`, `authorization_ref`, `idempotency_key`,
`deadline`, `action_budget`, `precondition_results`,
`postcondition_results`, `rollback_ref`, `policy_version`,
`receipt_ref` and `final_status`. Values that are not measured must remain
explicitly unavailable, not be invented.

## Acceptance gates

- Reuse and integration tests exercise the canonical Salamander control plane.
- Injected missing, stale, contradictory and adversarial telemetry produces
  unknown/degraded states rather than false health or automatic repair.
- Every action is rejected without tenant, policy authorization, exact
  registered handler, bounds, idempotency key and action budget.
- Repeated failures open the circuit; a bounded half-open probe and requalification
  are required before traffic returns.
- Post-action verification catches a handler that reports success but does not
  restore service; failed verification triggers rollback or escalation.
- Tenant isolation, evidence-sink failure, restart/replay, duplicate event,
  policy regression and rollback tests pass.
- Anomaly models are evaluated on temporal holdouts; optimization is promoted
  only after predeclared metrics and safety constraints pass.
- The actual TOE, Millennium API, Salamander and execution integrations are
  tested together in the target environment before any production claim.

## Delivery status

This document defines the integration contract. Existing Salamander components
are present in the repository, but this branch has not yet wired or validated
the complete end-to-end loop. Do not describe self-healing, anomaly detection
or self-optimization as operationally qualified until runtime evidence and the
acceptance gates above are satisfied.
