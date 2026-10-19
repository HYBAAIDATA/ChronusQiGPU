# PI-01: Evidence Restoration and Operational Hardening

Status: Governing program charter approved by the repository owner. Operational qualification has not been demonstrated
by adopting this charter. The 90-day delivery clock starts only after scope, owners,
capacity, pilot population and acceptance thresholds are approved.

## Objective and governing principle

Demonstrate an evidence-qualified operational path:

Observed Event → Validated Ingestion → Correlated Execution Evidence → Durable Custody → Operator Visibility.

Success means behavior can be reconstructed, authenticated, recovered and operated
safely. Success does not mean all Azure services are deployed.

Preserve domain authority. Strengthen surrounding infrastructure. Require executed
evidence for readiness claims. Presence is not evidence: source, modules, workflows,
README sections and architecture patterns are hypotheses about capability until
validated within a stated environment, scenario and candidate identity.

Keep mining logic, mathematical substrate, control-plane semantics and domain
ownership boundaries. Elevate identity, transport, observability, recovery and
deployment assurance. Prove readiness through executed evidence.

THESEUS, CHRONUS, OVID, AL HARAS, EUCLID, PYTHIA and SALAMANDER retain their existing
responsibilities. Infrastructure placement is not responsibility transfer; cloud
service selection is not domain redesign. Any change needs an explicit approved ADR
and reconciliation with [Owner Declarations](../../OWNER_DECLARATIONS.md).

## Scope boundary

Identity, telemetry, evidence, operator visibility and release assurance are **in scope
for qualification**, not already qualified. Mining hardware, hashrate, pool performance
and profitability are not qualified unless independently demonstrated. A healthy
control plane is hosting evidence, never evidence of mining effectiveness.

The repository has a Container Apps deployment template; the live Azure estate has
not been verified by this program. AKS is only a candidate. See
[ADR-PI01-001](../decisions/ADR-PI01-001-hosting-platform.md) and the existing
[Azure deployment preparation](../../deploy/azure/README.md).

## Evidence hierarchy

Documentation → Static Review → Unit Validation → Integration Validation → Live
Execution → Operational Confidence.

Observed evidence accompanies every executed validation stage; it is not reserved
for live execution. A pass at one level does not qualify another backend, environment,
fleet, operating window or integration. Live execution is authorized separately from
this charter; no program approval authorizes mining, share submission or movement of funds.

Every readiness claim records capability, commit SHA, artifact digest, environment,
executor/backend/device identity, scenarios, execution time, result, limitations,
evidence location, freshness and accountable review. Initial maturity estimates
remain UNVERIFIED. Finite samples support only their recorded scope, not universal reliability.

## Four evidence classes

These are versioned contract requirements, not yet implemented telemetry runtime APIs.
The executable readiness register and promotion enforcement are described in
[CEDR enforcement](PI-01-cedr-enforcement.md); engine validation does not qualify runtime behavior.
Class names are independent of the existing measured/computed/projected truth labels.

| Class | Required meaning | Does not establish |
| --- | --- | --- |
| A — Observation | A source reports a measurement at an observation time; include ingestion time, units, window, source identity and quality/freshness | Hardware qualification or validated performance merely because a reading exists |
| B — Execution | What was requested and what actually executed; include requested/executed route, executor, operation identity and correlation | Submission or acknowledgement merely because execution occurred |
| C — Outcome | Observed response/result; include the responding authority, linked operation/submission and response time | Pool acceptance from a local send, broker acknowledgement or inferred result |
| D — Attestation | Integrity/authorship under a specified trust policy; bind the exact evidence digest, algorithm, key identifier and verification | Truth of the payload, correct execution or production readiness |

Do not store private signing keys in evidence records. A key identifier is not key
material. A caller-supplied verification result is not trusted: verify the signature,
issuer authorization and exact signed digest at the consuming trust boundary.
Confidence scores are not proof; predictions must remain separately labelled.

All classes require schema identity/version, immutable record identity, source and
subject identity, correlation/causation links and appropriate timestamps. Specify
canonical serialization, signature policy, retention/access, time/clock quality,
compatibility and rejection/quarantine rules before implementing a shared contract.

## Mandatory P0 qualification gates

### P0-1 — Release Truth

Prove PASS, FAIL, SKIP and NOT_RUN remain distinct. Unknown/unverified is never PASS.
Required checks must be green for the exact candidate commit and artifact, with
known exclusions recorded and reviewed before execution. Skipped hardware workflows
remain UNVERIFIED. No hidden failures, downgraded required checks, automatic acceptance
from missing evidence or administrative bypasses. Human approval does not convert
failed or unexecuted validation into a pass.

Evidence package: candidate identity, required-check inventory, raw results, status
mapping tests, exclusion register, hardware qualification gaps and review decision.
A report failing to include a required result blocks promotion.

### P0-2 — Correlation Truth

Chain: SearchPlan → Route Selection → Execution → Submission → Pool Response.

Freeze the eligible execution population and window. Approve N and its rationale
before sampling. Record the population, selection method/seed, selected IDs and all
results; do not remove failed or incomplete samples after selection. N must be positive.
Random sampling is supplemented by explicit rejection, timeout, cancellation,
non-submission, retry and missing-hardware scenarios.

Each sampled execution must have intact correlation/causation linkage, requested and
executed route, executor and timestamps. Locate the plan, route, execution, submission
and outcome records, or an explicit authorized terminal non-submission state. Do not
fabricate submission IDs, pool responses or missing stages. Distinguish not_attempted,
submitted, pending, accepted, rejected, timed_out and unknown. Retries retain their own
attempt identities linked to the original operation.

Pass threshold: 100% traceability for the frozen sampled executions and mandatory
negative controls. Explicit timeouts can be traceable but are not pool acceptance;
scenarios requiring acknowledgement fail without an actual pool response. Pending or
unknown results cannot qualify a terminal outcome. A complete chain alone does not
qualify performance or universal reliability.

### P0-3 — Identity Truth

Under observation, demonstrate authorized access succeeds; unauthorized, revoked and
expired access fails. Test rotation, least privilege and unavailable-identity/secret
behavior. No embedded credentials, broad fallback credential or secrets in evidence.
Fail-closed behavior must be executed, not inferred from configuration.

Azure Key Vault, Managed Identity and Workload Identity are implementation options.
Adopt them only when they measurably improve these outcomes. Validate that applications
actually consume rotated values and that revocation takes effect within an approved window.

Evidence package: access matrix, credential lifecycle cases, observed denials,
rotation/revocation timing, redaction results and least-privilege review.

### P0-4 — Telemetry Truth

Exercise replay, restart recovery, duplicate delivery, outage, overflow and backpressure.
Document partition/ordering assumptions, checkpoint semantics, deduplication identity,
retry bounds, buffer limits, retention and quarantine behavior. Delivery acknowledgement
is not business-outcome acknowledgement. Telemetry replay must never execute a control
command or cause another share submission.

No silent loss: reconcile produced/accepted events with persisted, pending, rejected or
quarantined events; unexplained gaps fail. Bounded buffers must expose overflow and loss
counters/alerts. Exactly-once side effects are not inferred from broker delivery claims.

Evidence package: fault matrix, event reconciliation, duplicate-side-effect assertions,
checkpoint/recovery records, ordering results, lag/buffer observations and operator alerts.

## P1 qualification backlog

| Item | Required demonstration |
| --- | --- |
| P1-A — Operational Visibility | An operator answers what was requested, what executed, which hardware participated, what evidence exists and what the pool acknowledged without opening source code |
| P1-B — Rollout Qualification | Exercise canary, rollback and configuration restoration; assign ownership and measure recovery timing. Image rollback is not data/migration rollback |
| P1-C — Incident Recovery Verification | Exercise failures; measure recovery behavior, operator workflow, evidence capture and escalation. SALAMANDER's presence does not establish operational recovery qualification |

## Phases and 90-day planning windows

| Window | Phase and deliverable | Decision gate |
| --- | --- | --- |
| Days 1–15 | Evidence Restoration: baseline checks, candidate identity, ownership, contracts and pilot sampling/fault plan | Approve owners, capacity, budget, test population, thresholds and unresolved release blockers |
| Days 16–45 | Identity and Telemetry Hardening: one vertical operational slice, developed in parallel | Execute the P0 gates; no cloud dependency or release approval substitutes for missing evidence |
| Days 46–75 | Operational Visibility: passive fleet state, custody, incident reconstruction, rollout/recovery drills | Demonstrate P1 outcomes with assigned operators and measured timings |
| Days 76–90 | Qualification, evidence review and handover | Scoped pilot go/no-go; remaining limitations labelled UNVERIFIED |

Azure-Native Elevation is conditional on a confirmed operational gap and justified
service decision. Advanced Analytics/AI is a later phase after the operational baseline
is qualified, not an automatic commitment within these 90 days.

## Azure dependency decision gate

Problem demonstrated → Evidence collected → Gap confirmed → Alternatives evaluated →
Azure service measurably improves outcome → Costs/risks/rollback approved → Introduce dependency.

Event Hubs needs demonstrated transport requirements; Azure Monitor needs demonstrated
visibility gaps; Digital Twins needs demonstrated fleet-state use cases; AI Search/RAG
needs demonstrated historical-evidence retrieval difficulty. Feature availability is
not a requirement. Preserve domain authority and evaluate cost, complexity, failure
modes, portability, access, retention and recovery obligations.

## Governance dashboard and decision register

Every work item includes Status, Accountable Owner, Acceptance Evidence, Next Decision,
Risk and Dependency. Also include candidate/environment scope, last execution, evidence
freshness and limitations. Delivery status (planned/in progress/blocked) and qualification
status (PASS/FAIL/SKIP/NOT_RUN/UNVERIFIED) are separate fields. 'Done' alone is insufficient.

Accountable roles to assign: program sponsor, platform lead, domain/contract owners,
security lead, SRE/operations lead and release approver. No named assignment or staffing
commitment is implied by this document.

Before starting the clock, approve tenant/subscription and region, pilot fleet, expected
event volume, capacity, cost ceiling, classification, retention, recovery objectives,
operational SLOs, hosting decision and release/emergency authority. Store secrets through
approved private credential channels, never in program documents or issues.

## Day-90 go/no-go statement

A pilot fleet event can be traced from observation through ingestion, execution,
evidence custody and operator visibility. Identities are controlled, telemetry behavior
under failure is understood, evidence contracts are versioned and release decisions are
supported by executed evidence. Remaining limitations are explicitly UNVERIFIED rather
than assumed complete.

This is a target statement, not a current certification. Go requires the required P0/P1
evidence for the approved pilot scope; absent or failed evidence means no-go or a narrower,
explicitly reviewed scope that does not bypass required gates. The result does not certify
mining hardware, hashrate, pool performance, profitability or the entire platform.
