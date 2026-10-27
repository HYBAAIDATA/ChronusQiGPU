# Salamander inside consolidated HYBA

Salamander is HYBA's governed autonomic operations layer for **anomaly detection,
self-healing, and self-optimisation**. It is not a separate platform or an
unbounded autonomous operator. Its decision loop uses TOE as the shared
reasoning/evidence substrate and AL HARAS/L-HRAS as the policy boundary.

The fictional Jack Bauer / Chloe O'Brian reference is a product metaphor:
rapid incident prioritisation and technical correlation under pressure. It is
not a mandate for unrestricted access, covert actions, or bypassing approvals.

## Closed-loop operating model

```text
OBSERVE -> DETECT -> CORRELATE -> CLASSIFY -> PLAN
   ^                                      |
   |                                      v
VERIFY <- POST-OBSERVE <- APPROVED ACTUATOR <- POLICY GATE
   |                                      |
   +--- verified recovery / rollback -----+--- escalate to operator
```

- **Observe:** collect authorized service health, metrics, traces, configuration
  deltas, identity events and dependency signals. Tag each signal with source,
  timestamp, tenant, purpose and freshness.
- **Detect:** combine hard safety limits, service-health checks and validated
  statistical baselines. Report data gaps and stale telemetry as degraded or
  unavailable, not as healthy.
- **Correlate:** build a common incident timeline and evidence graph; deduplicate
  events and preserve conflicting signals.
- **Classify:** use TOE and the five canonical forms: predictive, causal,
  counterfactual, topological and geometric. These are analytical lenses, not
  independent authorities. Missing results remain explicitly unavailable.
- **Plan:** generate a ranked set of bounded, reversible remediation and
  optimisation options, with expected effect, confidence, blast radius,
  rollback path and verification criteria.
- **Policy gate:** AL HARAS/L-HRAS enforce tenant, purpose, capability and
  change-window policy. High-impact actions require explicit human approval.
- **Actuate:** only an allow-listed actuator receives a narrow action request.
  No arbitrary shell, unrestricted credentials, or model-generated command
  execution.
- **Verify:** independently re-observe after the action. An accepted request or
  actuator acknowledgement is not proof of recovery. If verification fails,
  keep the system guarded, roll back where approved, and escalate.

## Self-healing policy

Use only the canonical Salamander action registry and the owning subsystem's
qualified execution contract (for example, registered replan, throttle, failover,
defer, quarantine, circuit-breaker, projection-rebuild or rollback actions where
supported). Do not invent generic action names or bypass the registered handler
and verifier. Each action needs a per-target allowlist, maximum action count,
timeout, rate limit, cooldown, blast-radius bound, idempotency key, and rollback
procedure.

Never automatically perform destructive data changes, privilege changes,
security-policy weakening, credential rotation without a coordinated runbook,
or actions that affect external/mission systems without the required approval.
If the evidence ledger, policy service, or required health signal is unavailable,
fail closed for actuation.

## Self-optimisation

Optimisation is constrained by a declared objective and hard invariants:
availability, latency, error budget, resource cost, security posture, data
locality and tenant isolation. Compare candidate changes against a baseline,
use shadow/canary rollout where appropriate, and keep a rollback threshold.
A lower cost or faster response does not justify crossing a safety or security
constraint. Optimisation cannot override the healer's incident lock.

## Five-form / TOE contract

Each incident record carries a stable ID and evidence references. For each
intelligence form, record one of `available`, `insufficient_evidence`,
`not_supported`, `degraded` or `unavailable`. Predictions require measured
calibration and false-alarm rates; causal conclusions must state assumptions;
counterfactuals must be labelled simulated; topological/geometric outputs must
identify their data representation and numerical limitations.

Millennium Maths remains a separate mathematical research service. It must not
receive mission telemetry, classified records, operational identifiers, or
network topology. Mathematical probes do not authorize remediation and do not
turn numerical outputs into proofs of open Millennium problems.

## Incident commander experience ("Jack / Chloe" mode)

The operator view should show, in order:

1. **What changed?** A time-ordered incident timeline and the highest-confidence
   anomaly clusters.
2. **Why do we think it matters?** Source-linked evidence, competing hypotheses,
   uncertainty and affected dependencies.
3. **What can we do now?** Ranked options with impact, confidence, approval
   requirement, rollback and verification steps.
4. **What happened after the action?** Before/after health, independent checks,
   audit receipt and whether the incident can safely close.

Use calm, concise alerts and explicit escalation. Do not represent inferred
intent, attribution, or prediction as fact.

## Required release gates

- Replay tests for normal operation, threshold breaches, correlated anomalies,
  stale/missing telemetry, duplicate events, contradictory evidence and
  dependency outages.
- Tests for tenant isolation, policy denial, audit failure, action rate limits,
  idempotency, cooldown, rollback and human-approval enforcement.
- Independent post-action verification and failure-to-recover escalation.
- Held-out evaluation of detection precision/recall, false-alarm rate, detection
  delay and forecast calibration.
- Shadow mode first; canary rollout next; operational actuation only after
  documented acceptance and incident-response drills.

**Status:** target architecture and operating contract. This document alone does
not assert that the control loop is wired, deployed, tested, or production-ready.
