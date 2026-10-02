# #108 Salamander Autonomic Control Plane

## Stack and authority

This implementation stacks directly on immutable #107 head
`83c187e2cf9a6ef60271c3c6bfcb1b5669e0321e`. It consumes, rather than
reimplements, `ProductionMiningIntegration` and
`IntelligentPoolCoordinator.apply_salamander_mode`. Stratum retains work
identity, proof/host comparison retains target validity, the literal pool
response retains submission outcome, `ExecutionRouter` retains physical
dispatch, the causal ledger retains lineage, and `RecoveryGovernor` remains
the mining recovery writer.

The canonical control plane is `salamander.control_plane.AutonomicControlPlane`.
Its models are in `salamander.models`. The design keeps health, capability
qualification, policy lifecycle, admission and evidence as separate typed
state machines. Unknown, unavailable, unsupported, not-run and not-reported
states never become zero or healthy values.

## Consolidated ownership

* **OVID** is the successor/target name for Aethel's authoritative durable
  storage, state and representation custody. Salamander calls native
  verification/reconstruction through injected bounded adapters.
* **THESEUS** is the successor/target name for `hyba_db`'s rebuildable
  query/index/graph/semantic projection. Salamander consumes
  `OntologyStore.verify_database()` and detects drift. A projection never
  proves that an OVID payload exists.
* **EUCLID** trains and evaluates. Existing `LearningService`,
  `MemoryDatabase`, checkpoint manifests, training partitions and
  `ExperienceSuperlearner` retain learning and reward boundaries.
* **KAIROS** is a deterministic local laboratory for replay, counterfactuals,
  rehearsal and falsification. It has no production mining, network, pool,
  wallet, credential, submission, revenue or profitability authority.
* **CHRONUS** executes through qualified capabilities and emits execution
  evidence. Salamander may replan, throttle, fail over, defer, reject,
  quarantine or request requalification; it cannot redefine conformance.
* **SALAMANDER** observes, forms governed experiences, applies bounded
  registered actions, measures outcomes, and promotes or rolls back policies.

The local `euclid/kairos_runtime.py` is a new fail-closed equivalence
implementation, not a byte-for-byte recovery. `hyba_substrate` is the
recovered/converged enterprise learning substrate.

## Runtime architecture

`HealthEnvelope` evaluates named dimensions without collapsing them into an
opaque synthetic score. Backend capability identities include backend, device,
operation, precision and implementation digest. Qualification expires and
forces quarantine/requalification. The declared 11-D Float64 boundary remains
CPU/exact-integer until a numerically tested, evidence-certified FP64 Chronus
path exists; an advertised extension is not qualification.

`CircuitBreaker` implements CLOSED → OPEN → HALF_OPEN with one bounded probe.
`RecoveryPlan` is an acyclic, deadline- and action-budgeted DAG. Every action
must use an exact registered handler, action kind, tenant, bounds and
idempotency key. No shell, dynamic code execution, arbitrary SQL, arbitrary
filesystem operation or runtime source rewrite exists in the production
control plane. Historical `Intelligence/salamander_agentic.py` remains a
diagnostic/proposal source only.

Admission is per tenant and requires a tenant-prefixed isolation key. Capacity
absence defers rather than inventing availability. Restart reacquisition probes
current authorities; failed probes become `UNAVAILABLE`, never restored
health. Toolchain, evidence, storage, projection, learning and deployment
health use the same explicit observation contract.

## Learning and deployment

The required flow is:

`production observations → OVID → EUCLID/ExperienceSuperlearner → curriculum
→ Kairos worlds → replay/falsification/counterfactuals → held-out evaluation
→ shadow → canary → production policy`.

`RewardAuthority.NONE` stores an observation without reward. Stable replay
identities, immutable dataset snapshot hashes and temporal lineage prevent
restart replay and leakage. TRAIN, VALIDATION, FINAL_TEST, INCIDENT and
TEMPORAL_HOLDOUT remain distinct. Policy transitions cannot skip
CANDIDATE → TRAINED → VALIDATED → FINAL_TESTED → SHADOW → CANARY → PROMOTED;
regression causes rollback. Correctness, conformance, storage integrity and
safety are not trainable policy parameters.

## Evidence and API

Actions append `salamander.autonomic.action.v1` records to a SHA-256 chain and
may forward each record to an existing evidence sink. Proposal, dispatch,
acknowledgement and post-action verification remain distinct; an unverified
handler result is not recovery proof.

`api_snapshot()` exposes truthful backing for:

* `/api/salamander/health`
* `/api/salamander/events`
* `/api/salamander/backends`
* `/api/salamander/recoveries`
* `/api/salamander/policies`
* `/api/salamander/evidence`

## Research provenance and claim boundary

The implementation was shaped by the workspace research inventory under the
governing hierarchy: Notion is research/design/history, GitHub is current
executable implementation, and runtime evidence is execution truth.
Significant sources include the historical Salamander controller
([Notion](https://app.notion.com/p/5042b803b58a4b5fb2fa245c9ec92410)),
SCBC experiment
([Notion](https://app.notion.com/p/3fbf2c3ad65b48b9b00ea5487df2bd93)),
production-readiness review
([Notion](https://app.notion.com/p/35a07f39d6614ce9beba37dd87e6cc73)),
EUCLID recovery plan
([Notion](https://app.notion.com/p/5f064bbd7fa84ea09d3abafd3b6e6742)),
Kairos Polyverse
([Notion](https://app.notion.com/p/8fb2b73e8a314dbea468be18f2c3cfa7)),
recovery/replay
([Notion](https://app.notion.com/p/66fa30a0dc50466998444b444dff25d3)),
experiment register
([Notion](https://app.notion.com/p/6b78e6e89aaf4747bc0e99cf31ee4bd2)),
emergent-intelligence lineage
([Notion](https://app.notion.com/p/1fb64c306b44437a8fa1d32df5e56e71)),
Aethel hardening and measured substrate
([Notion](https://app.notion.com/p/787037a64f7b4d719dee3a85502d5a87),
[Notion](https://app.notion.com/p/c1e2ae66bd5049f4949fec126d29c8e9)),
PULVINI laboratory results
([Notion](https://app.notion.com/p/cef5bd03509e43dcbb399517dfb5a4f9)),
Chronus audit
([Notion](https://app.notion.com/p/6c0bbde40e8b41eeba9cedb15d5bcb9b)),
golden-ratio forensic analysis
([Notion](https://app.notion.com/p/3c1fa98a65b64ef5b95f5f6787a54b3a)),
and the artifact reconciliation register
([Notion](https://app.notion.com/p/585d16ab68ed4162aab9c6859fc2098f)).

Historical runtime source rewriting, arbitrary command execution, opaque
synthetic health scores and mathematics-only promotion are explicitly
superseded for production. SCBC/emergence/coherence results remain
experimental unless runtime evidence promotes their claims. PULVINI's
deterministic φ-depth behavior does not imply net storage compression, and
Chronus φ scheduling does not imply reduced classical complexity.

## Acceptance

Run:

```bash
python scripts/check_salamander_autonomic.py
```

The script runs `scripts/check_chronus107.py` first, then the focused #108
suite, and writes `artifacts/salamander108-evidence.json`. It does not convert
missing hardware, live-pool or CI execution into a pass.