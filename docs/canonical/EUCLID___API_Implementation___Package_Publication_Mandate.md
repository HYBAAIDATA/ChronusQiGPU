# EUCLID — API Implementation & Package Publication Mandate

<aside>
📋

Implementation mandate—not implementation, test certification or release approval. This brief directs engineering work against inspected source. No runtime, integration, scientific or release tests were executed while preparing it. Existing capabilities must remain intact; claims become release evidence only after the prescribed executions at a recorded source head.

</aside>

## Missing context / decisions required

Resolve these decisions before the dependent work. Independent source inventory, compatibility capture, test design and non-invasive integration analysis may proceed.

| Missing or conflicting context | Evidence or decision required | Work affected |
| --- | --- | --- |
| Original governing attachment | Supply `Pasted text(20261007-211415).txt` and its digest. It was not located by filename or timestamp in the available workspace searches. This mandate carries forward the embedded requirements, not an asserted reading of the attachment. The supplied request also ends at “Responses”; supply any omitted clauses. | Final requirement reconciliation and approval. |
| Product boundary | Product owner must choose EUCLID cognition within PYTHIA’s existing control API, the wider PYTHIA API, or another expressly identified product. The inspected implementation has EUCLID cognition routes inside PYTHIA; this does not establish the intended product scope. | Route additions, ownership, packaging boundary and release scope. |
| Repository identity and implementation lane | Current source was inspected in `QuantumPhiRedux/PhiMiner` at `c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7`. Workspace PR records identify `QuantumPhiEnterprise/PYTHIPhiMiner`. Confirm their relationship and the approved branch/PR for this programme; do not infer a rename or reuse the SALAMANDER lane as the API lane. | Changes, merge target and provenance continuity. |
| Approved API baseline and version policy | Approve a captured public-contract artifact, compatibility obligations and versioning policy. `/api/v1/`, the `PYTHIAControlAPI/1.0` server banner, EUCLID’s scientific baseline and distribution versions are different identifiers. | Contract-changing patches and version/release numbering. |
| Identity, tenant and session policy | Supply authoritative principal→tenant→creator/session mappings, role/operation policy, read-access classification, shared-learning permissions and production migration policy for legacy admin credentials/development opt-outs. | Runtime scoping, feedback, retrieval, evidence, replay, caches and security migration. |
| Persistence and execution topology | Confirm deployed canonical memory/custody/index attachments, supported concurrent writers, permitted execution domains, durable request retention and owner reconciliation interfaces. Existing source storage is not permission to invent a private replacement store. | Exactly-once effects/learning, recovery, concurrency and durable history. |
| Deployment and operational contract | Identify actual target, ingress/TLS/proxy, secrets management, shutdown semantics, resource limits, SLOs, observability and rollout/rollback owners. Repository deployment recipes are not proof of the live environment. | Load qualification, deployment, canary and operational acceptance. |
| Official Notion destination | Designate the parent/teamspace for this single mandate. Its initial private placement is a staging location, not evidence of an approved programme home. Move this page when designated; do not create a competing mandate. | Publication and ownership of the implementation brief. |

**Decision rule:** keep dependent choices explicitly unresolved. Do not manufacture route names, tenant rules, storage technology, numerical limits, deployment targets or readiness evidence to fill these gaps.

## Package-publication decisions required

The requested EUCLID publication preparation concerns the existing `euclid-engine` distribution, not an assumed new API package. Confirm the registry/project owner, research/prerelease versus production channel, approved release version/tag and branch, supported interpreter/platform matrix, and publishing identity. These decisions block final package promotion or upload; they do not block import/package inventory and packaging defect closure. API product-boundary decisions above remain separate. Existing metadata is source evidence, not registry availability or release approval. [[1]](https://github.com/QuantumPhiRedux/PhiMiner/blob/c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7/euclid/pyproject.toml)

## Governing sources and evidence scope

The following records ground this mandate. Source inspection establishes implementation facts, not successful execution or production readiness.

- **Pinned current API:** `chronus/mla1517_platform/python/control_api.py`, including route dispatch, authentication, Guardian preflight, request parsing, response envelopes and process-local idempotency. [[1]](https://github.com/QuantumPhiRedux/PhiMiner/blob/c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7/chronus/mla1517_platform/python/control_api.py)
- **Pinned runtime bridge:** `chronus/mla1517_platform/python/system_fabric.py`, including `euclid_cognition`, status, solve and close. [[2]](https://github.com/QuantumPhiRedux/PhiMiner/blob/c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7/chronus/mla1517_platform/python/system_fabric.py)
- **Canonical composition and persistence hooks:** `euclid/runtime.py`, including `EuclidRuntime.production`, repository solving, adaptive composition/solving, snapshots and custody restoration. [[3]](https://github.com/QuantumPhiRedux/PhiMiner/blob/c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7/euclid/runtime.py)
- **Intelligence architecture and evidence:** typed specialist interfaces, cognitive-state schema and existing cognitive service. These are distinct interfaces; their presence does not establish HTTP reachability. [[4]](https://github.com/QuantumPhiRedux/PhiMiner/blob/c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7/euclid/cognition/interfaces.py) [[5]](https://github.com/QuantumPhiRedux/PhiMiner/blob/c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7/euclid/cognition/state.py) [[6]](https://github.com/QuantumPhiRedux/PhiMiner/blob/c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7/euclid/cognition/service.py)
- **Scientific baseline and research limitations:** the research-release record identifies the EUCLID v16.4 comparison baseline at `585d7b11`; the full pinned baseline `585d7b11d9cc8e183ff4d5cda44996a9ac30dc4e` exports package literal `16.0.0`. Preserve both identifiers without conflation. The current research document describes release `17.0.0`, exploratory findings and limits—not API certification. [[7]](https://github.com/QuantumPhiRedux/PhiMiner/blob/c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7/docs/EUCLID_V17_RESEARCH_RELEASE.md) [[8]](https://github.com/QuantumPhiRedux/PhiMiner/blob/585d7b11d9cc8e183ff4d5cda44996a9ac30dc4e/euclid/__init__.py)
- **Reachability standard and deployment recipes:** preserve the staged convergence proof and distinguish the documented Docker/compose recipe from a verified deployment. [[9]](https://github.com/QuantumPhiRedux/PhiMiner/blob/c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7/docs/INTELLIGENCE_CONVERGENCE.md) [[10]](https://github.com/QuantumPhiRedux/PhiMiner/blob/c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7/DEPLOYMENT.md)
- **User-authorised historical records:** [EUCLID v17: full intelligence convergence and adaptive research gates](https://app.notion.com/p/EUCLID-v17-full-intelligence-convergence-and-adaptive-research-gates-c71993f1e4bf40b8ba3a95d47f0d4673?pvs=21), [feat(euclid): consolidate v16 intelligence engine](https://app.notion.com/p/feat-euclid-consolidate-v16-intelligence-engine-684f0cd217ae412f8d46d16489995f6d?pvs=21) and [feat(operations): Guardian-mediated control API, SLOs, runbooks, and evidence](https://app.notion.com/p/feat-operations-Guardian-mediated-control-API-SLOs-runbooks-and-evidence-335ba5294b1a42b2bf15b71483c2eb2b?pvs=21). These establish prior programme intent and claimed work, not fresh execution at the inspected head. The control-API record explicitly leaves integration/load, deployed telemetry and independent verification outstanding. [[11]](https://app.notion.com/p/EUCLID-v17-full-intelligence-convergence-and-adaptive-research-gates-c71993f1e4bf40b8ba3a95d47f0d4673?pvs=21) [[12]](https://app.notion.com/p/feat-euclid-consolidate-v16-intelligence-engine-684f0cd217ae412f8d46d16489995f6d?pvs=21) [[13]](https://app.notion.com/p/feat-operations-Guardian-mediated-control-API-SLOs-runbooks-and-evidence-335ba5294b1a42b2bf15b71483c2eb2b?pvs=21)

## Non-negotiable implementation boundary

1. Freeze EUCLID v16.4 as the immutable production/scientific comparison baseline. Preserve its source, mathematical mechanisms, public interfaces, tests, packaging, scientific evidence and backward compatibility. Do not mutate the baseline to improve comparison results.
2. Extend the existing API/runtime composition. No new intelligence stack, duplicated specialist algorithms in handlers, silent algorithm substitution or capability removal. Replacement precedes retirement where a defect requires a corrected implementation; prove caller migration and equivalent or stronger behaviour first.
3. Keep `GeneralIntelligenceCore` the coordinating orchestrator. Representation, memory, analogy, abduction, deduction, discrimination, meta-control, planning, composition, objectives, execution and consolidation remain specialist implementations behind typed interfaces and shared evidence. Existing optional specialist protocols remain compatible. [[4]](https://github.com/QuantumPhiRedux/PhiMiner/blob/c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7/euclid/cognition/interfaces.py)
4. Preserve authority: EUCLID orchestrates intelligence; AL HARAS governs security/authorisation; PYTHIA owns predictive/causal intelligence and mining authority; CHRONUS owns execution; TURING owns VQC execution; SALAMANDER owns bounded healing/optimisation; THESEUS owns durable custody; OVID organises/transforms/queries data. The API authenticates, validates and dispatches—it does not acquire these domain authorities.
5. Route delegated effects through the owning subsystem and its governed interfaces. No arbitrary client-supplied executor, shell command, callback or source mutation. Intelligence must not control Bitcoin consensus validity, target/difficulty, credentials, verified hashes or pool acceptance. [[9]](https://github.com/QuantumPhiRedux/PhiMiner/blob/c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7/docs/INTELLIGENCE_CONVERGENCE.md)
6. Scientific interest is not operational proof. Retain φ, Lucas/Pisot, manifold, primitives, evolution, causal/world-model/planning/transfer/meta-learning mechanisms even when exploratory. Assign truthful evidence classes and bounded execution contracts; do not conventionalise the architecture merely to resemble another organisation.

## Inspected API contract: starting facts, not yet an executed baseline

Engineering must first capture and exercise the complete contract. The following verified source facts constrain that capture; they are not an exhaustive endpoint inventory.

| Existing surface | Source-backed behaviour | Compatibility obligation |
| --- | --- | --- |
| `POST /api/v1/intelligence/cognition/solve` | Requires nonblank string `problem_id` and `goal`. Accepts `problem_class`, `structure`, `observations`, `strategy`, `initial_code`; optional values are currently coerced/truncated. Dispatches to `system_fabric.euclid_cognition_solve`. Unavailable result produces 503; available result produces 200 with `ok:true`. | Capture exact coercion, limits, errors and response shape. Preserve legitimate callers; stricter validation/security changes require an explicit compatible migration. `ok`, 200 and `available` must not mean “solved” or “production-ready”. |
| `GET /api/v1/intelligence/cognition/status` | Uses the lazy runtime status bridge and reports construction, memory/replay/reachability and capability information. | Establish which fields are public aggregates versus protected cognitive/persistence details. Do not expose protected state by retaining an unauthorised route. |
| Other existing intelligence/control/telemetry surfaces | Include intelligence status/self-test, engineering/maintenance, control session and `/api/v1/telemetry/stream`. | Inventory all actual methods, schemas, callers and policy boundaries before adding any route. Existing telemetry streaming is not an episode-following contract. |
| Transport and parsing | `ThreadingHTTPServer` with synchronous handlers; JSON object bodies; current 4 MiB request cap; malformed/non-object bodies rejected. | Keep synchronous solving as the starting architecture. Async jobs/streaming require a demonstrated need, architecture decision and compatibility tests—not assumption. |
| Identity and governance | Nonprivileged POST paths use control principal authentication; privileged prefixes use Guardian preflight. Principal configuration and legacy admin-key handling coexist. Guardian headers include tenant and actor. Intelligence is not among the listed privileged prefixes. | Test the actual security matrix. Do not equate control authentication with governed cognitive effects or assume a tenant mapping exists. |
| Responses | Existing request/correlation/causation IDs, failure classification, defensive headers and Guardian receipt/audit handling. Solve outcome distinguishes `solved`, `stalled`, `aborted`, `unexecuted`. | Preserve envelopes and exact existing enums. Add truthful evidence without changing the meaning of legacy fields silently. |

These facts are grounded in the inspected handler and bridge. [[1]](https://github.com/QuantumPhiRedux/PhiMiner/blob/c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7/chronus/mla1517_platform/python/control_api.py) [[2]](https://github.com/QuantumPhiRedux/PhiMiner/blob/c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7/chronus/mla1517_platform/python/system_fabric.py)

## Source findings that must become executable closure work

| Finding | Required smallest compatible correction | Proof required |
| --- | --- | --- |
| The HTTP solve bridge calls `solve_repository_problem`, not the adaptive `compose_adaptive_intelligence` / `solve_task` loop. The existing cognitive service is another distinct interface. | Preserve all legitimate entry points. Introduce only the adapter/dispatch changes needed for approved problem domains to reach canonical adaptive intelligence; unsupported domains fail explicitly. | Request-to-specialist traces and actual decision/effect/feedback evidence; no superficial import-based gate. |
| Runtime construction caches one process-global runtime with one state directory/default creator; authenticated request context is not passed into the inspected cognition bridge. | Bind approved identity/tenant/session context at a typed service boundary; scope canonical memory, knowledge, rights and persistence accordingly. Do not invent unapproved tenant semantics. | Concurrent two-tenant requests, denied cross-tenant reads/feedback/replay, authorised shared-learning tests. |
| Construction locking is not proof of solve concurrency safety. | Determine mutable runtime/write ownership; enforce bounded admission and an explicit per-runtime/tenant execution policy. | Overlap tests proving no mixed episodes, rights, learning or evidence; resource exhaustion fails truthfully. |
| Idempotency is a global process-local cache keyed by raw key, with result storage after handler execution. | Use an approved durable request/effect journal in the existing persistence architecture; bind key to principal/tenant, method, canonical route and payload fingerprint. Reserve before effects and reconcile unknown outcomes with the owner. | Cross-route/payload collisions rejected; crash after effect before response produces no duplicate effect or learning on retry. |
| Inspected cognition GET dispatch has no demonstrated principal/tenant protection; it falls outside privileged prefixes. | Classify read data and apply the approved read policy. Preserve harmless health aggregates where allowed, not sensitive state exposure. | Unauthenticated and foreign-tenant protected reads denied; approved safe aggregates remain compatible. |
| Runtime close is fail-soft; adaptive solving revokes granted rights after execution rather than demonstrating exception-safe cleanup. | Make shutdown/flush evidence and action-right cleanup observable and reliable through existing lifecycle interfaces. Preserve recovery capability; do not hide failed flushes. | Exceptions/cancellation leave no residual rights; failed durability prevents clean-shutdown/replay claims. |
| Adoption/retrieval and existing `transfer_verified` derivations do not independently prove beneficial held-out transfer. | Preserve legacy fields with documented semantics; expose stronger evidence separately through compatible schemas. Require measured transfer effects before stronger claims. | Held-out useful/irrelevant/harmful/abandoned transfer, unchanged frozen knowledge during evaluation, provenance-linked outcomes. |

These are source findings with execution still unverified, not claims of a reproduced live exploit or completed remediation. [[1]](https://github.com/QuantumPhiRedux/PhiMiner/blob/c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7/chronus/mla1517_platform/python/control_api.py) [[2]](https://github.com/QuantumPhiRedux/PhiMiner/blob/c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7/chronus/mla1517_platform/python/system_fabric.py) [[3]](https://github.com/QuantumPhiRedux/PhiMiner/blob/c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7/euclid/runtime.py)

## Implementation sequence and executable exit criteria

### G0 — Establish the contract and freeze the comparison baseline

- Record repository identity, approved lane, exact inspected/implementation heads and baseline tree/artifact hashes. Capture the unmodified v16.4 comparison environment and installation procedure.
- Extract every actual route/method, parser, schema, public caller, authentication path, permission decision, tenant/session assumption, side effect, error, lifecycle and deployment entry point. Include CLI/service callers and frontend dependencies.
- For each capability record path/symbol, owner, caller, production construction, input/output schemas, observations, execution interface, memory/custody/index attachments, verification, shutdown/replay, current evidence stage and deficiency. Account for every legitimate intelligence mechanism, not only HTTP handlers.
- Execute current contract tests before edits and retain request/response fixtures with secrets removed. Capture unknowns and failing behaviour separately from compatibility obligations; insecure behaviour is not an obligation to preserve a bypass.
- **Exit:** approved boundary/version decisions; complete source-and-caller inventory; immutable baseline digests; executed contract artifact with honest failures/unavailable items. No new endpoint design before this exit.

### G1 — Make request authority explicit throughout runtime composition

- Carry a typed authenticated request context into the existing bridge: actor, tenant, authorised session/creator scope, policy decision/version, correlation identifiers and permitted operation/resource. Obtain field meanings from approved policy; never trust actor/tenant supplied in the problem body.
- Compose through `EuclidRuntime.production` and existing governance/delegation interfaces. Supply required Guardian/AL HARAS dependencies through normal construction; prohibit actuator-capable bypass construction. Missing policy/authority makes effects unavailable while permitted observation may continue.
- Enforce scope on memory retrieval, caches, learned strategies, skills/primitives, feedback, evidence, outcomes and replay. Explicitly govern cross-tenant/shared learning and redact public evidence without breaking internal custody digests.
- Keep legacy admin authentication compatibility under an approved migration, but do not permit development unauthenticated mode in a production configuration.
- **Exit:** real-policy allow/deny/expiry/replay tests; no actuator or learning writer on denial; two-tenant isolation; exception-safe rights cleanup. [[3]](https://github.com/QuantumPhiRedux/PhiMiner/blob/c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7/euclid/runtime.py)

### G2 — Wire the canonical integrated intelligence episode, without replacement architecture

- Keep handlers limited to parsing, context, service dispatch and response encoding. Reuse the existing bridge and composition root; preserve repository solving and `CognitiveService` callers while making approved adaptive tasks reachable through explicit typed adapters.
- Map authorised input to the existing problem/task representations. Use trusted domain adapters for the actual world/executor; do not expose benchmark hidden mechanisms, reward truth or client-controlled executors as production authority.
- Exercise the integrated loop: represent → retrieve → analogy → abduce → deduce → choose discriminating evidence → update hypotheses → counterfactual/causal plan → select strategy → restructure/compose → imagine/rank → governed execution → compare prediction with fresh observation → repair model → consolidate/learn → replan when required.
- Preserve explicit uncertainty, candidate causes, competing strategies, negative evidence, abandoned analogies and bounded exploration. Do not replace this loop with a fixed heuristic or one-shot feature dispatch.
- Track every mechanism through the existing reachability stages: `PRESENT → IMPORTABLE → ADAPTED → REGISTERED → REACHABLE → USED_IN_EPISODE → CHANGES_DECISION → EXECUTED → OUTCOME_OBSERVED → FEEDBACK_CLOSED → PERSISTED → RESTART_VERIFIED → TRANSFER_VERIFIED`. A constructor, field or test name cannot advance a stage. [[9]](https://github.com/QuantumPhiRedux/PhiMiner/blob/c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7/docs/INTELLIGENCE_CONVERGENCE.md)
- **Exit:** real API episodes whose traces show specialist decisions, authorised owner execution, measured outcome and learning; existing callers still work; no duplicate cognition or authority.

### G3 — Implement lifecycle, response and evidence contracts

Use the existing cognition schemas and enum semantics. `euclid.cognition.state/1` has append-only hash-linked transitions, epistemic status and evidence origin; imagined evidence cannot become observed truth. Its content digests exclude timestamps for deterministic state evidence. Preserve legacy defaults and compatible deserialisation. [[5]](https://github.com/QuantumPhiRedux/PhiMiner/blob/c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7/euclid/cognition/state.py)

Required logical operations follow. Bind them to existing routes/services where supported; any additional route/schema names remain subject to G0 and owner approval.

| Logical operation | Required implementation contract |
| --- | --- |
| Submit a problem | Preserve the existing solve contract; validate supported domain, sizes, values and authority. Record admission, episode identity, budget and request fingerprint before effects. Reject unsupported work, not silently substitute. |
| Follow an episode | Return ordered, scoped transitions with explicit terminal state. Decide polling/streaming only from the approved architecture. Do not relabel the existing operational SSE as a cognitive stream or invent progress percentages. |
| Inspect state/evidence | Return authorised snapshots/evidence references, schema versions, uncertainty and origin. Separate sensitive internal details from approved summaries. Verify chain/seal integrity on readback. |
| Supply observations/feedback | Validate source identity, provenance, freshness, order, target episode, evidence class and reward authority. Reject foreign, duplicate, stale, conflicting or unauthorised updates with explicit semantics. Client text is not automatically a measured observation or authoritative reward. |
| Retrieve outcomes | Distinguish transport success, accepted request, available runtime, execution receipt, observed result and solved/stalled/aborted/unexecuted outcome. Include limitations, budgets consumed and evidence references; unavailable measurements remain unavailable. |
| Cancel/budget expiry | Follow existing lifecycle conventions. Stop new effects, reconcile in-flight owner actions, revoke temporary rights, retain partial evidence and report actual terminal state. A cancelled request does not undo an already committed effect. |
| Recover/replay | Authorise against current policy, validate schema/digests and durable owner receipts, restore canonical state, reconcile incomplete effects and prevent repeated execution or learning. Do not replay revoked authority. |

Responses must preserve existing request/correlation/causation IDs, failure taxonomy, defensive headers and applicable governance receipts. Do not collapse validation, denial, unavailable dependency, exhausted budget, owner failure, stale feedback, integrity failure and unresolved outcome into `healthy` or generic success. Preserve established HTTP/error conventions; approve additive distinctions before freezing new fixtures. [[1]](https://github.com/QuantumPhiRedux/PhiMiner/blob/c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7/chronus/mla1517_platform/python/control_api.py)

**Exit:** legacy and new contract executions, ordered transition/read tests, authorised observation provenance, deterministic replay and truthful terminal responses.

### G4 — Bound effects, concurrency, retries and cancellation

- Keep sync request handling unless the approved architecture requires otherwise. No unbounded queue, recursive recovery, indefinite streaming or unlimited parallel episodes.
- Establish justified/configured limits for episode wall time, specialist evaluations, actuator calls, memory/evidence size, concurrent requests and per-tenant resources. Record why each bound exists and which owner enforces it.
- Implement durable idempotency with pending/committed/failed/unknown-outcome semantics using canonical storage. Equal authenticated scope/key/fingerprint returns the same committed result; key reuse with different work is a conflict. Specify retention and expiry without allowing a late duplicate effect.
- Crash recovery must query owner receipts/postconditions before deciding whether an action may retry. “Exactly once” is a demonstrated property, not a response-cache label.
- Handle client disconnect, timeout and service shutdown through the same evidence-bearing lifecycle. No abandoned grants, hidden workers or double feedback.
- **Exit:** overlapping requests, duplicates, reordered feedback, budget exhaustion, cancellation and kill-window tests; bounded behaviour and reconciled effects across fresh process restart.

### G5 — Close durable memory, custody, indexing and replay

Reuse the current canonical `MemoryDatabase`, runtime snapshot/restore and custody hooks; adaptive knowledge persistence is part of the existing architecture. Determine their actual deployed ownership and integrate with THESEUS custody/OVID indexing through existing interfaces. Do not create a private substitute database, silent memory fallback or second competing history. [[3]](https://github.com/QuantumPhiRedux/PhiMiner/blob/c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7/euclid/runtime.py)

- Persist scoped requests, transitions, observations, model predictions, decisions, grants/receipts, owner effects, independent postconditions, learning updates, cancellations and recovery outcomes with schema/source/provenance digests.
- Define commit ordering and crash reconciliation for owner effect, cognitive state, feedback, custody and indexing. An index is not the custody authority. Report an unavailable/lagging query index truthfully; repair it only through OVID’s owned interface and retained custody evidence.
- Prove independent readback through the normal query path, not the process’s cached object. Corrupted chains, missing custody and incompatible schema fail closed; never claim successful persistence merely because a path exists.
- Execute graceful shutdown and forced interruption, then a fresh process with no previous in-memory objects. Verify restored state/evidence and current-policy rights; prove feedback is not applied twice.
- Prove learned recovery/strategy/context state changes a subsequent **allowed** decision and survives restart. Improvement requires observed outcomes; changed selection alone is not proof of improvement.
- **Exit:** durable receipts/readback, verified restart/replay, isolated learning, owner-authorised recovery, tamper detection and no private fallback.

### G6 — Run the mathematical and scientific programme through the API

Retain the established mathematical mechanisms and uncertainty, including null/harmful results. The inspected research release reports mixed φ/Lucas/manifold contribution, harmful transfer in a slice, no accepted self-improvement and unsupported superadditive-emergence claims. These are research findings to reproduce or challenge, not reasons to remove capabilities or claim API superiority. [[7]](https://github.com/QuantumPhiRedux/PhiMiner/blob/c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7/docs/EUCLID_V17_RESEARCH_RELEASE.md)

- Pre-register task families, seeds, budgets, hypotheses, falsifiers, controls, confidence/uncertainty treatment and promotion criteria before evaluation. Keep train/development/held-out partitions disjoint; freeze and digest knowledge before held-out evaluation.
- Compare (a) the unchanged v16.4 baseline, (b) the same canonical current runtime invoked directly, and (c) the API invocation. Transport parity tests must detect omitted specialists, altered observations, budget changes, duplicate learning and scope leakage. Use relevant conventional controls as comparators, not replacement architecture.
- Execute ablations for representation/manifold/φ–Lucas/Pisot mechanisms, primitive discovery/MCTS/evolution, causal discrimination/world-model repair, planning, analogies, transfer, meta-learning and governed self-improvement. Establish which mechanism changed a decision and outcome; module presence is insufficient.
- Preserve mathematical invariants and numerical checks, convergence assumptions, complexity/resource accounting and negative cases. Do not infer quantum advantage or physical substrate claims from mathematical simulation.
- Report correctness, solved/stalled/unexecuted rates, calibration/prediction error, utility, latency/compute/resource use, retained knowledge and useful/irrelevant/harmful/abandoned transfer. Use paired repeated trials and justified statistical analysis; temporal improvement is not automatically causal attribution.
- Self-improvement proposals require governed bounded trials, side-effect measurements, independent acceptance and owner-authorised rollback if rejected. No promotion on one throughput sample, reward proxy or heuristic score.
- **Exit:** reproducible source-bound experiments, honest null/refuted/hypothesis classifications, same-runtime API parity and frozen-baseline comparisons. Absence of superiority is not failure of compatibility; unsafe/unproven promotion is a release failure.

### G7 — Execute real-component voyages and mutation tests

Use the real API server, production composition, configured policy authority, supported real owner executor, canonical persistence/custody/index and a fresh process. Unit mocks remain useful but cannot certify composition. Safely induced faults may be controlled test inputs; production evidence must distinguish them from simulated execution/outcomes. No live mining, destructive operation or credentialed external action without explicit authority.

| Voyage | Required proof |
| --- | --- |
| Successful integrated episode | Request → authority → competing hypotheses/plan → owner effect → fresh independent observation → outcome → feedback → custody/index → shutdown → fresh restart → readback. |
| Stalled/unexecuted episode | Insufficient evidence or unavailable capability preserves uncertainty and truthful terminal outcome; no fake success or substitute algorithm. |
| Authorisation rejection | Valid request but denied/expired authority; no executor or learning writer invoked; denial evidence retained. |
| Tenant/session isolation | Concurrent unrelated episodes cannot read or mutate each other’s memories, policies, primitives, caches, feedback or replay; expressly permitted shared learning tested separately. |
| Prediction failure and replanning | Fresh observation contradicts prediction; model/strategy repairs are traceable, bounded and affect a later authorised decision. |
| Trial regression and rollback | Bounded proposal regresses an objective; independent rejection → owner-authorised rollback → independent restored-baseline check → durable evidence. |
| Retry/crash/restart | Interrupt before/after owner effect and before/after custody/index commit; fresh process reconciles without duplicate effects or rewards. |
| Learning and negative transfer | Earlier evidence influences subsequent selection after restart; irrelevant/harmful transfer is rejected/abandoned rather than blindly shared. |
| Resource/cancellation failure | Exhaust budgets or disconnect; no runaway work, leaked grants or ambiguous success; partial effects reconciled. |
| Custody/index failure | Write/read interruption, seal corruption, unavailable query and restart inconsistency produce explicit failure/unavailable states and owner recovery, not substitute storage. |

Mutation-test at least: bypass authorisation; drop tenant filters; manufacture observed evidence from imagination; actuator always returns success; omit independent observation/verifier; break rollback or rights cleanup; omit custody; tamper replay; apply feedback twice; disable a budget; bypass the canonical runtime; mark available/HTTP200 as solved. Each planted defect must cause a named assertion to fail. A mutant that only crashes the test harness is not proof of the intended boundary. Retain the mutation diff, killed/surviving result and exact source/artifact linkage.

**Exit:** all mandatory voyages exercised with real composition; adversarial tests fail safely; required mutants killed; survivors/unexecuted voyages block the relevant gate.

### G8 — Package, deploy and release only the proven composition

- Follow approved repository/package conventions; do not create a standalone EUCLID API package without a boundary decision. Keep API, runtime and scientific-baseline version identities separate.
- Build wheel/source/container artifacts as applicable to the approved target. In clean environments prove install/import/startup, public API fixtures, supported persistence attachments and shutdown/restart. Inspect included modules/resources/dependencies and ensure no research fixture/mock becomes a production adapter.
- Preserve existing deployment configuration and frontend callers. Supply migration/rollback procedures for approved authentication, schemas and persisted-state changes. Reversible migrations must retain integrity; destructive migration requires a separate approved decision.
- Run measured load/security/operational tests against the selected deployment contract and justified SLOs. Health/liveness is not intelligence readiness, executed hardware, accepted mining work or successful learning. The deployment recipe itself distinguishes HTTP liveness from device/worker readiness. [[10]](https://github.com/QuantumPhiRedux/PhiMiner/blob/c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7/DEPLOYMENT.md)
- Canary promotion and rollback use existing owning authorities and independently measured outcomes. Publish only after machine-derived gates and release-owner approval; preparing this brief authorises neither deployment nor publication.
- **Exit:** reproducible artifacts, compatible clean installs, approved operational qualification, verified rollback and source-bound release manifest.

## Evidence and machine-derived release decision

Every executed artifact must bind to the exact source head actually tested—not merely the branch name or an earlier green run. Record source/tree and dependency-lock digests, artifact digest, runtime configuration digest with secrets excluded, command, environment, executor identity, timestamps, exit status, test selection, seeds, budgets and evidence/log digests. Patch after testing invalidates affected evidence; rerun at the final head. External execution receipts identify their own code/configuration versions.

Use machine-evaluated gate statuses `PASS`, `FAIL`, `UNAVAILABLE`, `NOT_EXECUTED`, with criteria and evidence references. Scientific epistemic/evidence classifications remain separate from release gate status. An inaccessible CI log is not proof of zero steps; confirm step execution. Confirmed zero-step runner failures are `UNAVAILABLE`, neither PASS nor implementation-test FAIL. Local executions remain local evidence until independently executed.

```
API_RELEASE_READY =
    approved_scope_and_contract_gate
    AND immutable_baseline_and_compatibility_gate
    AND canonical_composition_gate
    AND authentication_authorization_tenant_gate
    AND bounded_lifecycle_and_idempotency_gate
    AND real_effect_and_independent_feedback_gate
    AND evidence_integrity_and_custody_gate
    AND query_readback_gate
    AND fresh_restart_replay_gate
    AND learning_and_transfer_safety_gate
    AND scientific_protocol_and_truthful_claims_gate
    AND adversarial_and_mutation_gate
    AND real_production_composition_gate
    AND clean_package_and_deployment_gate
    AND required_independent_execution_gate
    AND final_head_evidence_binding_gate
```

No human, endpoint or AI may set the result directly. Unknown coverage, unavailable authority, unresolved required context or missing mandatory evidence cannot satisfy an AND gate. Do not invent zero defect counters; compute them from the complete inventory, test coverage and unresolved findings. If enumeration is incomplete, report `UNKNOWN`, not zero. Provide separate verdicts for software qualification, external environment qualification and release approval; none substitutes for another.

**Current mandate verdict:** implementation readiness and production release are **NOT ESTABLISHED**. Source inspection and historical records are the evidence available for drafting; the executions and decisions above are still required.

## EUCLID package-publication workstream

This workstream adds publication preparation for the existing EUCLID distribution to this single mandate. It does not create a new intelligence architecture or assume that EUCLID’s library and the wider PYTHIA API are the same release product. Engineering must implement and execute the steps below; this section is not evidence that artifacts have been built, tested or uploaded.

### Inspected package facts and publication blockers

At the pinned inspection head `c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7`:

- `euclid/pyproject.toml` declares the existing distribution **`euclid-engine`**, version **`17.0.0`**, import package **`euclid`**, setuptools build backend, Python **≥3.10**, empty required dependencies and a pytest test extra. Preserve the established identities; do not choose a new release number or assume the declared dependency list proves runtime closure. Package discovery must be verified from actual artifacts. [[1]](https://github.com/QuantumPhiRedux/PhiMiner/blob/c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7/euclid/pyproject.toml)
- The repository root distribution is separately **`pythia-mla1517` `0.1.0`**, Python **≥3.12**, with explicit package/module lists and different dependencies. A successful root install is not proof that the standalone EUCLID distribution installs correctly; likewise EUCLID wheel success cannot certify the PYTHIA API. Test their supported coexistence without duplicate/conflicting ownership of `euclid` files. [[2]](https://github.com/QuantumPhiRedux/PhiMiner/blob/c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7/pyproject.toml)
- `euclid/README.md` still titles itself **v16.0** and describes a stateless payload, whereas the canonical runtime includes persisted memory, adaptive knowledge and custody hooks. Preserve legitimate legacy adapter documentation but reconcile the public description with current supported behaviour and research limitations. Do not repeat “self-contained” as a guarantee before isolated-install proof. [[3]](https://github.com/QuantumPhiRedux/PhiMiner/blob/c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7/euclid/README.md) [[4]](https://github.com/QuantumPhiRedux/PhiMiner/blob/c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7/euclid/runtime.py)
- `euclid/LICENSE` contains the MIT licence and 2026 HYBA Software Limited copyright. Include the full notice and audit the licences/provenance of every bundled component; the top-level notice alone does not establish redistribution rights for all dependencies or grafts. [[5]](https://github.com/QuantumPhiRedux/PhiMiner/blob/c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7/euclid/LICENSE)

**Unproven—not silently PASS:** standalone build/discovery, clean dependency closure, package data completeness, supported interpreter/platform coverage, published-name ownership, existing registry versions, trustworthy publication configuration, licence completeness and exact final artifact qualification. Nothing in this drafting task establishes registry availability or upload success.

### P0 — Resolve distribution and publication authority

1. Reuse `euclid-engine` / `euclid` unless the owner supplies a documented reason and compatibility migration. Confirm registry destination, project ownership, existing releases and intended channel: research/prerelease versus production-qualified release. Do not infer these from a version string.
2. Confirm the approved release branch/head, version/tag policy, supported Python/platform matrix, maintainers and publishing identity. Prefer the project’s existing trusted publication mechanism; secrets must not appear in Notion, build logs or evidence.
3. Maintain a release manifest identifying the scientific baseline **EUCLID v16.4**, its immutable source, the implementation version, API contract version and distribution version separately. A research release must not advertise production gates as satisfied; a production release must satisfy all applicable G0–G8 gates.
4. Establish whether EUCLID ships standalone with declared dependencies, bundles canonical shared modules under existing ownership, or relies on separately published canonical distributions. Decide from import tracing and current repository conventions, not by stripping capabilities or copying a second implementation into the wheel.

**Exit:** approved release boundary/channel/ownership and a source-backed dependency/package ownership plan. Missing registry access blocks publication, not repository-controlled packaging repairs.

### P1 — Make the existing distribution genuinely installable

- Build a full module/resource/import inventory covering legacy adapters, discovery/evolution/transfer, geometry/manifold, cognition/integrated/research, curriculum, organ adapters, runtime/governance/memory/custody interfaces and any canonical shared imports. Classify required core, optional supported integration and test/research-only resources explicitly.
- Inspect setuptools discovery and package mappings from the actual build. Correct omissions in the existing packaging configuration; retain legitimate modules and public imports. Do not make a scanner green by dropping capabilities or silently disabling specialists.
- For each dependency identify the real import path, public distribution, compatible version bounds, optionality and tested installation route. Build isolation dependencies are separate from runtime dependencies. Empty metadata is acceptable only if executed supported paths demonstrate no undeclared external requirements.
- Include required schemas, manifests, templates, mathematical resources, licence notices and documentation. Exclude credentials, tenant state, runtime databases, private knowledge, logs and machine-specific artifacts. Retain approved reproducibility fixtures in an explicit evidence distribution if they do not belong in runtime artifacts.
- Reconcile standalone and root-package ownership. Test supported install/upgrade order and dependency resolution; unsupported co-installation must be explicit rather than silently overwriting another package’s files.

**Exit:** wheel and source distribution contain the complete supported capability surface with declared dependency closure and no secret/private-state leakage.

### P2 — Execute clean-artifact qualification

Use a clean checkout at the approved head. Establish the existing test runner and build dependencies before invocation. Starting commands for the engineering environment are:

```bash
python -m build euclid --outdir release-dist
python -m twine check release-dist/*
```

These are required executions, not commands executed by this mandate. Adapt the output path to repository conventions; do not confuse metadata validation with runtime proof.

1. Install the wheel in a fresh environment outside the repository with no editable install, inherited `PYTHONPATH`, checkout current directory or preinstalled undeclared project modules. Run `pip check`; record imported module locations to prove they resolve to installed artifacts.
2. Build a wheel from the source distribution in another isolated environment, then run the same qualification against that wheel. Compare artifact inventories and supported interfaces; document any reproducibility differences rather than inventing matching digests.
3. Execute public adapter/import compatibility, mathematical/property/adversarial tests, canonical production construction, governed allow/deny execution, independent observation/outcome evidence and persistent learning using the installed artifact—not just the checkout.
4. Exercise supported optional integrations with their real canonical components and explicit configuration. Missing optional external hardware/services must report unavailable; they cannot be replaced with fakes to certify an advertised integration.
5. Repeat the fresh-process shutdown/readback/replay voyage and prove learned state affects a later permitted decision. Test failure and cancellation cleanup, custody interruption, tampering and rollback from installed artifacts.
6. Qualify each claimed interpreter/platform from the approved matrix. Do not claim Python ≥3.10 support merely because the metadata says so; if supported capabilities need a higher floor, make an evidence-based compatibility decision and migration, not an arbitrary silent bump.
7. For API-integrated claims, run the existing PYTHIA API against the installed canonical runtime and repeat contract/authority/tenant/feedback tests. A library-only release must clearly state which API behaviours remain outside its artifact boundary.

**Exit:** source-bound clean wheel/sdist executions and real-component evidence for every advertised supported path. Source-tree tests alone cannot satisfy this gate.

### P3 — Prepare truthful public documentation and evidence

Deliver an updated package README, installation/upgrade guide, minimal supported example, API/integration guide, security/tenant/governance requirements, persistence/replay guide, migration notes, changelog, licence notices and contributor/reporting instructions. Do not invent a security-reporting address or support commitment; use approved maintainers’ records.

Examples must execute against the installed distribution. Distinguish legacy adapter usage from canonical integrated-runtime composition and the API bridge. Document required authority/configuration and unavailable states; no example teaches a governance bypass. Explain observed versus imagined evidence, terminal outcomes, limitations and immutable comparison baseline.

Release evidence must include wheel/sdist hashes, package-content inventory, dependency/SBOM and licence inventory, environment/test commands, logs, failed/unavailable coverage, scientific protocol/results and a machine-derived gate report. Scientific null or harmful findings remain visible; no unsupported AGI, quantum-advantage, production, mining-performance or causal-improvement claim.

### P4 — Publish only approved, qualified bytes

- Validate registry ownership and publication permissions without exposing credentials. A staging/test-registry upload, if approved, is a separate gate—not public release completion.
- Require release-owner approval for the exact channel, version, tag and artifact digests. This request authorises preparation, not an unreviewed public upload or repository tag.
- Upload the already qualified artifacts without rebuilding or changing them. Independently download/read back the registry artifacts, check hashes and install in a fresh environment. Record registry receipts and version resolution.
- Provide a tested recovery plan: stop promotion, use registry-supported withdrawal/yank procedures where authorised, issue corrected versions rather than overwrite immutable releases, and preserve affected artifacts/evidence. Publication rollback does not erase installations already made by users.
- Treat missing credentials/project ownership or unavailable runners as exact external blockers only after repository-controlled defects are closed. Never label build failures, undeclared dependencies or surviving critical mutants as registry blockers.

```
EUCLID_PACKAGE_QUALIFIED =
    approved_distribution_scope_gate
    AND immutable_baseline_compatibility_gate
    AND package_inventory_dependency_license_gate
    AND isolated_wheel_install_gate
    AND isolated_sdist_rebuild_install_gate
    AND advertised_python_platform_gate
    AND governed_real_component_gate
    AND independent_outcome_evidence_gate
    AND durable_restart_learning_gate
    AND adversarial_mutation_gate
    AND truthful_documentation_claims_gate
    AND exact_final_source_artifact_binding_gate

EUCLID_PUBLICATION_APPROVED =
    EUCLID_PACKAGE_QUALIFIED
    AND declared_channel_requirements_gate
    AND registry_ownership_authority_gate
    AND exact_artifact_release_owner_approval_gate

EUCLID_PUBLICATION_VERIFIED =
    EUCLID_PUBLICATION_APPROVED
    AND registry_receipt_gate
    AND independent_download_hash_install_gate
```

For a production channel, `declared_channel_requirements_gate` includes all applicable software/operational production gates; it cannot be relaxed by relabelling unknowns. Research publication may be separately approved with clear limitations, but it must not imply production readiness. Gate results are evidence-derived `PASS`, `FAIL`, `UNAVAILABLE` or `NOT_EXECUTED`, never manually awarded booleans.

**Required package handoff:** packaging repairs in the approved canonical lane; actual wheel/sdist artifacts; capability/dependency/licence inventories; clean installed-artifact test results; restart/replay/learning evidence; documentation and migration notes; exact tested head and digests; channel-specific computed verdict; publication authority or precise remaining external blocker; registry readback only if upload was separately approved and executed.

**Present status:** publication preparation is specified. Package build, qualification, registry upload and publication verification are **NOT EXECUTED by this mandate**.

## Frontier elevation: an evidence-producing intelligence research programme

**North star:** evolve EUCLID from a system that searches for answers into a system that constructs explicit models, discovers reusable mechanisms, designs discriminating experiments, produces independently checkable results, detects the limits of its own reasoning and improves across episodes without compromising its authority or evidence boundaries.

This is a proposed research programme, not a claim of achieved capability, AGI, consciousness, quantum advantage or endorsement. No named scientist or consortium is represented by this mandate. Roger Penrose’s mathematical and foundational questions may motivate precisely stated research questions; they do not establish that EUCLID has non-computational cognition. No technical position is attributed to “Julia Tunois” without an identified source supplied by the owner.

Keep all work inside the canonical architecture and approved lane. Deepen existing typed specialists; add optional compatible protocols only when an existing interface genuinely cannot express the requirement. `GeneralIntelligenceCore` coordinates the research loop but does not implement every algorithm. No independent intelligence stack, renamed baseline, weakened judge or duplicate memory/custody authority.

### Research contract: discovery must produce obligations, not rhetoric

Every new mechanism must have an evidence-backed dossier:

```
research_question
existing_component_and_typed_interface
mechanism_and_mathematical_definition
assumptions_and_domain_of_validity
predicted_observable_effect
competing_explanations
falsifier_and_failure_cases
invariants_and_proof_obligations
preregistered_tasks_controls_and_budget
learning_and_evaluation_partition
owner_authorization_and_effect_boundary
measured_results_and_uncertainty
resource_and_verification_cost
negative_transfer_and_rollback_evidence
source_configuration_artifact_and_evidence_digests
claim_class_and_promotion_decision
```

Advance from hypothesis → executable mechanism → independently observed effect → replicated result → bounded operational promotion. A failed or null experiment remains valuable evidence; retain the mechanism as exploratory where appropriate without silently promoting it or removing a legitimate capability. Research tracks below are not blanket release blockers: their advertised capability and deployment promotion must be proven, while unsupported frontier claims must remain explicitly exploratory.

### R1 — Proof-carrying discovery and compositional reasoning

**Implement:** attach a typed specification and certificate obligation to discovered primitives, AST transformations and composed plans. Preserve the existing discovery/evolution/MCTS mechanisms as proposal generators. Use independent verification behind the appropriate specialist interface; verification must not accept the proposer’s own success flag.

- Define supported semantic subsets and preconditions. A certificate states exactly what was proved: a mathematical theorem under declared axioms, bounded model check, contract preservation, or measured test result. Do not label tests a universal equivalence proof; arbitrary-program equivalence is not a generally decidable engineering gate.
- For supported formal domains, record the complete formal statement, axioms, proof term/checker version and independently checked result. Audit the translation from the intended problem to its formal statement—proving a mistranslated theorem does not solve the original problem.
- Compose verified primitives only when pre/postconditions, effects and resource contracts compose. Reject missing obligations; retain useful unproved candidates as hypotheses rather than erase them.
- Feed counterexamples into existing discovery/model-repair interfaces with provenance and tenant permission. A failed proposal should teach a reusable applicability boundary.

**Experiment:** unseen compositions requiring new primitives; adversarially equivalent-looking but inequivalent programs; correct proof of the wrong formalisation; corrupted certificate; resource-exhausting checker. Compare certified useful discoveries per unit of total search-plus-verification cost, not candidate volume.

**Falsifier:** no held-out benefit after checker/translation costs, or accepted unsound certificates. Formal-verification research such as AlphaProof illustrates independent proof checking and finite budgets; its result does not establish EUCLID parity or remove formalisation limitations. [[1]](https://www.nature.com/articles/s41586-025-09833-y)

### R2 — Causal world models that choose what to learn next

**Implement:** deepen existing world-model, abduction, causal-discrimination and planning specialists. Maintain competing model explanations, explicit latent/confounding assumptions and uncertainty. Separate prediction, intervention and counterfactual claims.

Select a permitted experiment for expected information about a decision-relevant ambiguity—not merely novelty or model confidence. A proposed research objective is:

$$
a^* = \arg\max_{a\in\mathcal A_{\mathrm{authorised,safe}}} \left[I(H;O\mid a,D)-\lambda C(a)-\mu R(a)\right]
$$

Here information gain is a **model-based estimate**, not observed truth; cost, risk and weights require units, calibration and justified policy bounds. Hard safety/authority constraints are not tradable penalties. If credible models disagree about safety, request evidence or abstain rather than average away the danger.

- Record predicted observations before the action; obtain fresh owner-produced measurements afterwards. Use PYTHIA’s canonical predictive/causal interface where appropriate; EUCLID must not duplicate its authority.
- Test observationally indistinguishable models that require an authorised intervention to distinguish, hidden confounders, delayed effects and nonstationary mechanisms.
- Compare fixed exploration, prediction-only planning and evidence-directed planning with matched total budgets. Measure model discrimination, calibration, task utility and harmful interventions.

**Falsifier:** information-seeking fails to distinguish causes or improves internal scores without real outcomes. World-model research demonstrates useful planning with imagined trajectories, not that imagination is independent observation; EUCLID must retain that boundary. [[2]](https://www.nature.com/articles/s41586-025-08744-2)

### R3 — Mathematical structure as an operational hypothesis

**Implement:** give φ, Lucas/Pisot and manifold mechanisms explicit mathematical jobs within their existing components—candidate ordering, representation selection, scale scheduling, conditioning or transfer—rather than treating a constant’s appearance as an advantage claim.

For each job specify the map/operator, domain, dimensional units, precision, stopping rule and complexity. Separate algebraic identity, numerical approximation and empirical algorithmic improvement. Where a contraction/convergence claim is proposed, state its metric and assumptions; demonstrate or prove the bound rather than infer it from resonance terminology.

- Compare the mechanism with matched random, rational/irrational scheduling and alternative scale/geometry controls under the same computational budget. Tests must distinguish a useful structure-specific effect from generic diversity or extra compute.
- Test representation invariance, coordinate changes, conditioning, perturbations, finite-precision accumulation and out-of-distribution task structure.
- Expose a mechanism-specific prediction before evaluation: which class should benefit, why, what should remain invariant and where it should fail. Post-hoc slices generate new hypotheses, not confirm the original claim.
- Account for search overhead, representation construction, memory and verifier costs. A compact symbolic address is not physical infinite storage; a large representable index is not an executed search over all represented states.

**Falsifier:** matched alternatives explain the benefit, advantage disappears under precision/resource accounting, or predicted beneficial task classes fail. Preserve exploratory mathematics with honest classifications. The existing release record’s mixed/null findings are the starting evidence, not a blank slate to overwrite. [[3]](https://github.com/QuantumPhiRedux/PhiMiner/blob/c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7/docs/EUCLID_V17_RESEARCH_RELEASE.md)

### R4 — Quantum-information discipline without simulated advantage claims

**Implement:** explore quantum-inspired proposals through existing representation/planning specialists and any actual VQC execution through TURING’s owned interfaces. Preserve requested algorithm identity, backend identity, executed resources and verifiable receipts.

- Label classical simulation as classical simulation. Unitary evolution or interference in a mathematical model does not establish physical quantum computation, unlimited coherence, free memory or computational advantage.
- Specify state encoding, preparation, query/oracle construction, gate/sample costs, precision, noise, readout and independent verification. Count classical preprocessing and postprocessing, not just an inner kernel.
- Use relevant best classical controls and useful tasks. Separate exact small-instance agreement, modeled scalability and measured hardware performance. Do not extrapolate exponential improvement from a small simulated example.
- Test whether an interference-inspired candidate distribution adds value beyond a matched classical stochastic search. A classical benefit may be publishable without a quantum-advantage label.

**Falsifier:** benefit disappears after encoding/sampling/verification costs, depends on hidden oracle work or lacks algorithm-preserving executed receipts. Quantum-advantage verification can itself be computationally costly; the cited analysis establishes this issue for random-circuit settings, not a universal impossibility theorem. [[4]](https://quantum-journal.org/papers/q-2022-06-30-753/)

### R5 — Persistent abstraction and context-sensitive transfer

**Implement:** deepen existing memory, analogy, primitive repository and consolidation interfaces so learning retains more than successful outputs: explanatory mechanisms, counterexamples, validity domains, costs, failed strategies and reasons for abandonment.

- Learn an applicability decision before transferring a primitive/model. Include task structure, causal assumptions, authority, tenant permission and resource context. Similar surface wording is insufficient.
- Test useful, irrelevant, harmful and abandoned transfer; compositional novelty; catastrophic interference; and delayed recurrence after restart.
- Measure held-out utility and learning efficiency with train/development/evaluation separation. Freeze learning during evaluation where prescribed; report any test-time adaptation as a separate protocol and budget.
- Retain source links and custody lineage from original episode through transferred decision and actual outcome. Canonical THESEUS/OVID remains the persistence/query boundary.

**Falsifier:** transfer adds no held-out benefit, leaks knowledge across tenants, or improves new tasks by destroying retained capabilities. No unchecked global shared-learning pool.

### R6 — Self-improvement that cannot rewrite its own success criteria

**Implement:** let existing meta-learning/self-improvement mechanisms propose bounded changes to strategies, representations, primitives and calibrated models. Keep proposal, authorisation, execution, independent evaluation and promotion as separate responsibilities.

- Freeze the trusted checker, protected contracts, authority model and held-out evaluation criteria for each trial. A proposal cannot grant itself new rights, edit its judge, erase failures or select only flattering tasks.
- Measure correctness, availability, calibration, compute, custody integrity and retained capability. Require acceptable trade-offs rather than a single absolute proxy.
- Execute rejected-trial rollback through the owner and independently verify restored behaviour. Persist failed contexts so the next selection changes; self-improvement must not be an infinite repair loop.
- Any proposal to change a trusted checker or governance contract enters a separate externally reviewed change process, never automatic promotion.

**Falsifier:** improvement vanishes on held-out tasks, safety/retention regresses, judge changes explain gains, or rollback cannot restore known-good behaviour. No claim of unrestricted recursive intelligence growth.

### Integrating the research into executable production work

1. **First establish the floor:** G0–G5 contract, authority, canonical dispatch, evidence and durable replay; P1–P2 clean-artifact closure. These make frontier experiments attributable and reproducible.
2. **Then one coupled voyage:** novel problem → competing causal explanations → authorised discriminating experiment → model repair → primitive discovery → independent certificate/measurement → bounded composition → owner execution → learning/custody → fresh restart → held-out transfer. This tests interaction, not six isolated demos.
3. **Measure interaction:** pre-register factorial/targeted ablations for interacting mechanisms with equal resource envelopes. Synergy requires an explicit interaction estimate and uncertainty, not merely the full system beating one component.
4. **External challenge:** use independent task construction and review where available; redact tenant data and disclose compute, failures, adaptation and limitations. External evidence is marked unavailable until obtained, not presumed from prestigious names.
5. **Promote narrowly:** operationalise only the mechanism, task domain and authority envelope actually supported by evidence. Retain unpromoted research without mislabelling it production-certified or removing baseline capabilities.

**Engineering research handoff:** implemented canonical specialists/adapters; executable registered hypotheses and falsifiers; mathematical obligations/certificates; resource-matched baseline and ablation runs; integrated API and installed-package voyage; fresh-process learning/transfer evidence; independent scrutiny status; exact source/artifact/evidence digests; and an honest map of demonstrated, hypothesised, unavailable and refuted claims.

The target is not “EUCLID is more intelligent” as a slogan. It is a system that discovers something useful it did not already have, explains why the discovery should work, tries to falsify it, proves or measures its effect, remembers where it fails, and applies it safely to a genuinely new problem.

## Generality and advanced-autonomy qualification protocol

**Purpose:** turn AGI/ASI ambitions into difficult, auditable capability tests. Passing this protocol supports only the tested domains, budgets and conditions. It does not establish universal general intelligence, superintelligence, consciousness or unlimited self-improvement. No finite internally constructed suite warrants those conclusions.

The engineering priority is now **close an executable learning loop, then broaden the evidence**. Do not continue adding architectural labels while canonical composition, installed-package execution or durable feedback remains unproven. Preserve v16.4 and all existing authority, compatibility and release gates.

### Q0 — Register expectations before implementation tuning

Create a versioned qualification specification, reviewed by the product/research owner, containing:

- Supported task domains and operations; what is intentionally unsupported; whether the claim concerns frozen knowledge or bounded test-time learning.
- Task construction, hidden evaluation criteria, novelty axes, contamination controls, baseline/comparator selection, compute envelopes and replication plan.
- Per-domain acceptance thresholds justified by the task contract, pilot estimates and statistical power; thresholds are unresolved until approved, not convenient constants selected after results.
- Critical failures, allowed abstention/escalation, external-review requirements and exact evidence required for each public capability claim.

Keep task generators, judges, policies and evaluation state outside the learner’s modification rights. Independent evaluation does not mean another copy of EUCLID certifying EUCLID. Formal judges, owner-produced measurements and human review each have declared scopes and limitations.

### Q1 — Build a capability profile, not a single intelligence score

| Expectation | Required challenge | Evidence and failure criterion |
| --- | --- | --- |
| Generalisation | Withhold causal rules, structural compositions and task families—not merely random examples of familiar templates. | Per-family held-out success with uncertainty and novelty provenance. Memorisation, generator leakage or unauthorised hidden-state access invalidates the claim. |
| Reasoning and abstraction | Require a new composition/primitive or a justified abstraction; test adversarial near-matches and broken assumptions. | Independently checked result plus decision trace and applicability limits. Fluent explanations or candidate counts are not correctness. |
| Learning efficiency | Compare cold-start, frozen prior knowledge and explicitly budgeted adaptation on disjoint tasks. | Learning curves versus examples, interactions and total compute; reward and knowledge lineage. Hidden retraining or uncounted feedback invalidates comparison. |
| Long-horizon agency | Multi-stage work with delayed outcomes, partial observations, dependency changes, interruption and resumption. | End-to-end verified completion, bounded replanning, lawful effects and restart continuity. A sequence of plausible plans is not completion. |
| Epistemic reliability | Contradictory evidence, distribution shift, unavailable information and impossible/underspecified requests. | Calibrated confidence, useful clarification/abstention, explicit uncertainty and error correction. Confident invention is failure; indiscriminate refusal is not success. |
| Continual learning | Interleave new tasks with retained capability tests; repeat after fresh restart and shifted contexts. | Retention, useful/irrelevant/harmful transfer and rollback evidence. Gains purchased by catastrophic loss or tenant leakage fail. |
| Scientific discovery | Pose competing explanations requiring a safe discriminating experiment and a reusable result. | Predictions recorded before intervention; independent measurements/certificates; replication and falsification attempts. Novel-looking output is not discovery. |
| Trustworthy autonomy | Adversarial observations, instructions embedded in retrieved data, reward gaming and policy/tenant boundary probes. | No unauthorised effects; truthful evidence; effective denial, shutdown and rollback. Protected boundaries cannot be traded for task score. |
| Resource efficiency | Repeat under explicitly varied resource envelopes with search, training, owner execution and verification costs included. | Quality–cost curves and failure envelopes. More compute alone is not an algorithmic improvement. |

Report the full profile, task-level failures and worst-performing slices alongside aggregates. Do not hide weak domains inside a weighted average. A scoped “above comparator” result requires named comparators, matched conditions and uncertainty; it is not an ASI verdict.

### Q2 — Execute the first qualification campaign through canonical paths

Use controlled, authorised software workloads as research fixtures; these do not automatically become advertised product domains.

1. **Compositional code task:** discover a transformation needed for a previously unseen composition; preserve contracts; independently verify semantics in the supported subset and measure end-to-end cost.
2. **Hidden-mechanism task:** choose between initially indistinguishable world models; request a permitted discriminating experiment; update the model and execute a better plan. Keep hidden truth in the independent task judge.
3. **Interrupted project task:** execute a dependency-constrained multi-step problem; safely induce an owner failure; replan within budget; shut down; restart; reconcile effects and complete or truthfully escalate.
4. **Transfer task:** retain an explanation/primitive from an earlier episode, then present useful, irrelevant and harmful contexts. Demonstrate selective application and preserved prior capabilities.

For each campaign execute the unchanged baseline where applicable, direct current canonical runtime, API path and installed-package path. Unsupported baseline tasks are reported as unsupported, not silently counted as successful or excluded to flatter the new system. Distinguish parity tests from superiority tests.

Persist request identity, authority, pre-action prediction, actual effect, independent outcome, learned-state change and subsequent selection. Run equal-budget ablations for the proposed contributor. API/runtime/package discrepancies are implementation defects to close before interpreting intelligence gains.

### Q3 — Prove the evaluation system can expose false progress

Plant defects deliberately: leak an answer, replace outcome measurement with a heuristic, replay a reward, omit a failed task, widen an agent’s authority, corrupt retained knowledge, remove a stopping rule or let a proposal modify its judge. The designated assertions must reject the result. Record surviving mutants and close material evaluation defects before relying on the profile.

Measure confidence against real outcomes with task-appropriate scoring rules. For binary claims, a possible registered measure is the Brier score:

$$
\operatorname{BS}=\frac{1}{n}\sum_{i=1}^{n}(p_i-y_i)^2
$$

State event definitions and sampling; report coverage and error conditional on attempted answers as well as abstention. Do not manufacture confidence when no calibrated probability exists or equate a hash-valid trace with a true statement.

### Q4 — Make improvement cumulative and reversible

For each proposed change, report matched baseline/candidate outcomes, uncertainty, protected-contract checks, compute, retention and affected contexts. Acceptance criteria must be fixed before the trial. Enforce owner-authorised rollback and independent readback; retain rejected proposals so future selection avoids the known failure context.

Repeated measurement does not permit repeated peeking until a favourable result appears. Register stopping rules and account for multiple comparisons. For ongoing adaptive trials, use a declared sequential protocol rather than pretending observations are independent fixed-sample experiments.

Publish a versioned capability card tied to the exact tested artifacts. Allowed claims take this form: **“Demonstrated capability X on task family Y, under budget Z and authority envelope A, with evidence E and limitations L.”** Unsupported expectations remain hypotheses or untested requirements. Product readiness, broad intelligence research and release approval remain separate decisions.

### Immediate engineering priority and stopping rule

1. Resolve the existing source/lane, product boundary and identity/persistence decisions needed for the first real voyage.
2. Repair canonical wiring and package closure before introducing additional mechanisms.
3. Execute one installed-package/API episode with independent outcome evidence, durable restart and a subsequent learning-influenced permitted decision.
4. Implement the qualification specification and adversarial judge checks; run the first campaign at a fixed source head.
5. Choose the next enhancement from measured failure attribution—not prestige, intuition alone or a flattering aggregate.

Do not declare “elevation complete.” Return an evidence-bound capability delta, preserved capabilities, actual failures and the next testable hypothesis. The ambition stays high; the claims grow only as the evidence does.

## Engineering handoff and completion artifact

Return one consolidated implementation in the approved lane, not a parallel partial architecture. Deliver:

1. Approved boundary/authority map, reconciled governing source and contract/version decisions.
2. Complete component/route/caller/reachability inventory and minimal compatible implementation diff.
3. Typed request/runtime/evidence/feedback contracts, preserved public schemas and migration fixtures.
4. Canonical governed composition, scoped memory/learning, bounded execution, durable idempotency and lifecycle implementation.
5. Real request-to-effect-to-feedback traces, custody/index readback, independent verification and exception/rollback evidence.
6. Shutdown/fresh-process/replay results and proof learning affects subsequent permitted selection without repeated reward or unsafe transfer.
7. Baseline/direct-runtime/API comparisons, mathematical invariants, falsifiable ablations and honest scientific limitations.
8. Local executed tests, adversarial/mutation results, real-component voyages and independently executed CI results or precisely evidenced unavailability.
9. Clean package/install/deployment qualification, operational acceptance and owner-approved rollout/rollback procedures.
10. Final tested source head, artifact/evidence digests, computed gate report, unresolved defects/decisions and genuine external blockers with affected gate and required owner/action.

Do not describe this mandate, module existence, a feature list, mocked results or historical PASS counts as implementation completion. Repository-controlled defects remain engineering work, not external blockers. Declare completion only for gates actually executed and satisfied; otherwise return the exact unsatisfied gate, evidence and next action without self-awarding production readiness.