# Intelligence & Agent Capability Ownership Register

> **Canonical Principle**: Substrate-agnostic intelligence with strict domain boundary ownership.
> No third-party proprietary client SDKs (e.g. Claude) exist in the codebase.
> External capabilities, patterns, and cookbook recipes are native mathematical and operational implementations assigned to named agents based on functional authority.
> **Default Invariant**: Where no specialized domain agent has explicit ownership, authority resides in **EUCLID** (Overall Intelligence Owner).

---

## 1. Named Agents & Architectural Authorities

| Named Agent | Architectural Domain | Presumed Capability Scope |
|:---|:---|:---|
| **EUCLID** | Overall Intelligence & CNS | Central Nervous System of the autonomous organism. High-level cognitive task planning, decision arbitration, multimodal representation, operator compilation (`compile_operator`), multi-agent orchestration, and **universal fallback owner**. |
| **AL HARAS** | Security, Gatekeeping & Assurance | Sovereign control, cryptographic enforcement (CEDR), no-float guards, anti-tamper, zero-trust admission control, audit trails, and security boundary enforcement. |
| **SALAMANDER** | Autonomic Self-Healing & Self-Optimisation | Continuous autonomic telemetry, fault detection, closed-loop runtime repair, recovery governor, discovery optimization, and dynamic latency/budget Pareto adjustments. |
| **PYTHIA** | Predictive Guidance & Knowledge Memory | Manifold search strategy, learned plan generation, prime memory and PVSNP store, active learning replaying measured outcomes, and RAG over structured historical state. |
| **CHRONUS** | Hardware Substrate Acceleration | Heterogeneous GPU/iGPU OpenCL acceleration, tile/ladder kernel dispatch, ISA emulation, ASIC protocol adapter, and physical execution latency profiling. |
| **TURING** | Exact Mathematical & Quantum Foundations | Exact algebraic arithmetic ($Z[\phi]$, Lucas sequences, Binet, Cassini), complex Hilbert space linear algebra, group character decomposition, and exact amplitude rotation. |
| **OVID** | Authoritative Durable Custody | Enduring authoritative storage, state and representation custody; successor to `aethel`. |
| **THESEUS** | Rebuildable Projections | Database, query, index, graph, ontology and lineage projections; successor to `hyba_db`. Rebuildable from OVID, never its authority source. |
| **HENDRIX** | Resonant Search & Mining Traversal | Geodesic 32-face frame orientation, coprime step traversal, and non-redundant search manifold routing. |

---

## 2. Cookbook Patterns & Capability Mapping Matrix

External patterns (such as multi-agent collaboration, tool integration, and prompt optimization recipes) are mapped directly to their specialized named agents. All general/unassigned capabilities fall back to EUCLID:

```
                                    ┌────────────────────────────────────────────────────────┐
                                    │                     EUCLID                             │
                                    │     Overall Intelligence Owner (Central Nervous System) │
                                    └──────────────────────────┬─────────────────────────────┘
                                                               │
                 ┌──────────────────┬──────────────────────────┼──────────────────────────┬──────────────────┐
                 ▼                  ▼                          ▼                          ▼                  ▼
          ┌─────────────┐    ┌──────────────┐           ┌──────────────┐           ┌─────────────┐    ┌──────────────┐
          │  AL HARAS   │    │  SALAMANDER  │           │    PYTHIA    │           │   CHRONUS   │    │    TURING    │
          │  (Security) │    │(Self-Healing)│           │ (Knowledge)  │           │ (Execution) │    │   (Quantum)  │
          └─────────────┘    └──────────────┘           └──────────────┘           └─────────────┘    └──────────────┘
```

### Detailed Capability Assignment

| Cookbook Recipe / Capability Pattern | Owning Agent | Rationale & Codebase Alignment |
|:---|:---|:---|
| **Multi-Agent Teams & Team Swarms** | **EUCLID** | Coordinates multi-agent collaboration, task division, and shared context across the organism (`euclid/runtime.py`, `euclid/task_orchestrator.py`). |
| **Coordinator-Worker Pattern** | **EUCLID** | High-level cognitive planning model directing specialized execution units (`euclid/delegation.py`). |
| **Sub-Agent Delegation** | **EUCLID** | Spawning and managing sub-agents with bounded scopes (`euclid/agents/`, `Intelligence/agentic_controller.py`). |
| **Moderation & Safety Filters** | **AL HARAS** | Fail-closed input/output verification, policy checks, and sovereign admission control (`al_haras/guardian.py`, `al_haras/no_float_guard.py`). |
| **Token, Rate & Budget Limits** | **AL HARAS** | Hard resource boundaries, privilege quotas, and anti-abuse gates (`al_haras/entitlements.py`). |
| **Self-Healing & Auto-Recovery Loops** | **SALAMANDER** | Closed-loop error detection, state rollbacks, and self-correcting retries (`salamander/runtime.py`, `salamander/discovery_optimisation.py`). |
| **Latency & Cost Pareto Optimization** | **SALAMANDER** | Dynamic governor adjusting compute intensity under latency pressure (`salamander/control_plane.py`). |
| **Structured RAG & Domain Knowledge** | **PYTHIA** | Vector/topological indexing over prime memory and historical search states (`Intelligence/pythia_memory.py`, `Intelligence/pythia_knowledge.py`). |
| **Prompt Caching & Trajectory Reuse** | **PYTHIA** | Replay of verified trajectory snapshots avoiding redundant re-planning (`Intelligence/pythia_store.py`). |
| **Exact Calculator Tool Integration** | **TURING** | Deterministic fixed-point and ring arithmetic without floating point approximations (`turing_universal_quantum_computer/`, `lucas/core.py`). |
| **High-Throughput Batch Inference** | **CHRONUS** | SIMD/OpenCL execution pipeline and tile dispatcher (`chronus/`, `gpu/`). |
| **Audit Logging & Causal Receipts** | **OVID / THESEUS** | Immutable cryptographic provenance and causal trail (`hyba_db/theseus_registry.py`, `al_haras/witness.py`). |
| **Cognitive Classification & Summarization** | **EUCLID** | *(No specialized domain owner)* Resides in overall intelligence (`euclid/cognition/`). |
| **Multimodal Vision & Chart Interpretation** | **EUCLID** | *(No specialized domain owner)* Resides in overall intelligence (`euclid/cognition/`). |
| **Tool Calling & Agent Action Dispatch** | **EUCLID** | *(No specialized domain owner)* Action routing and tool dispatch (`Intelligence/pythia_tools.py`, `euclid/runtime.py`). |
| **Automated Evaluations & Benchmarking** | **EUCLID** (with Agent H) | Intelligence benchmark execution and evaluation harnesses (`Intelligence/agentic_mining_evals.py`, `tests/`). |

---

## 3. The Euclid Fallback Invariant

> **Rule**: If a new capability, tool, pattern, or recipe is introduced and cannot be unambiguously claimed by AL HARAS (Security), SALAMANDER (Self-Healing/Optimization), PYTHIA (Memory/Learning), CHRONUS (Hardware), TURING (Math/Quantum), or OVID/THESEUS (Storage/Provenance), it **MUST** be placed under `euclid/` or `Intelligence/` under the direct stewardship of **EUCLID** (Agent A).


## 4. Canonical Intelligence bridge review — 2026-10-14

This revision adds an explicit interface, not an alternative runtime or learner.
`EuclidRuntime.bind_intelligence(existing_registry, profile=..., capabilities=...)`
registers an Intelligence specialist without installing a guardian, issuing an
entitlement, granting rights or creating another registry, learner or memory root.
A host can supply the existing `SalamanderEngine.capability_registry`; its full
constructor/skill composition was not executed in this selective-source review.

The verified minimal native research composition uses the same registration
function now called by Salamander, `register_proof_capability(registry, tracker)`.
The real canonical call path is:

```text
EuclidRuntime.dispatch_specialist
  -> AL HARAS Guardian (entitlement, tenant, actor and operation policy)
  -> creator-scoped RightsLedger + Delegator gates
  -> IntelligenceSpecialist (fixed profile and explicit capability allowlist)
  -> existing CapabilityRegistry (schema, permission and envelope checks)
  -> native MathematicalProofTracker register/get/experiment handler
  -> local hash-bound receipt, fabric audit, EUCLID evidence and Guardian audit
```

Registration is not authorization. The host must configure AL HARAS policy for
`intelligence.proof-conjecture`, supply an entitled token and explicitly grant
`intelligence.request` dispatch rights. No defaults grant those permissions.
Existing specialism authority remains with its owners. The bridge refuses
external/mutating permissions until owner-enforced execution controls exist;
that is an implementation/evidence limitation, not a scope reduction.

### Implemented and locally verified subset

- Public leaf imports no longer initialize unrelated Intelligence engines;
  exports resolve from their actual owners, with missing dependencies visible.
- Shared profile denies code-execution permission before invoking a handler.
- Supported input/output schema constraints are enforced; unsupported schema
  keywords reject registration rather than being silently ignored.
- Failure/refusal dictionaries and native repair-result dataclasses are not
  SUCCESS. Simulation, guidance and unverified outcomes remain distinguishable.
- Missing/disabled capability requests and handler failures are audited.
- Registered manifests and returned audit records are detached snapshots.
- Numerical conjecture experiments remain evidence, not proof; absent conjectures
  fail rather than returning a successful null result.
- The canonical runtime records specialist refusal/failure events without
  converting them into observed successful executions.

### Evidence boundary and remaining work

Thirty new unittest cases passed normally and under Python `-O` on Linux/Python
3.13.14. Tests use real package imports, canonical runtime, SQLite, Guardian
policy/HMAC validation, registry, native tracker, filesystem JSONL and hash-chain
verification. Local randomly generated test entitlement keys are not external
trust anchors or independent certification. Adversarial fabric unit handlers
are explicitly test contracts; they are not advertised production executors.

`proof-conjecture` is the one native-handler path exercised end-to-end here.
The other seven advertised native capabilities are not verified through this
bridge. Full Salamander construction, installed artifacts, the existing pytest
battery, Windows filesystem/reparse behavior, T5 external assurance, Lucas
TIER-15/TIER-20, production drift-gate integration and required CI gates remain
unverified or blocked. There is no whole-system completion or merge-readiness
claim. No provider, pool, mining, network or production operations were launched.

The registry observes duration **after return**; it does not preempt handlers or
enforce OS/process isolation, memory limits or protected filesystem operations.
Its local hashes are not signatures, immutable/WORM storage or independent
execution proof. Legacy callable/path arguments have string-projected digests,
not authenticated object/state bindings. The canonical bridge accepts JSON
arguments only and refuses external-effect capabilities. Registered manifests
still require owner review; permission flags alone do not create OS isolation.

The existing source lock is unchanged because no graft or upstream skill bytes
changed. Original PHILOS contracts at `1b653442` are separate; do not merge the
reconstructed PR73 models over them. PR66 -> PR68 -> PR69 -> PR71 is unchanged;
this review targets the elevation branch and does not authorize merging that
stack, installing a production signer or changing assurance gates.


### Security follow-up: atomic registry admission

Review of PR74 at `563c480a` reproduced a registration/admission race: after
read-only admission, concurrent registry replacement could execute a newly
mutating handler under the earlier authorization. The bounded regression
confirmed a real unauthorized write inside a temporary directory; no production
filesystem, network, provider, pool or mining action was exercised.

Registry registration, removal and discovery now serialize contract/handler
updates. Dispatch captures the exact contract/handler pair together, and the
bridge re-applies its read-only policy to a detached copy of that same contract
before execution. Mutating a policy callback's copy cannot weaken validation.
Dispatch executes the admitted handler snapshot, not a later replacement.
This is internal admission consistency, **not** OS isolation or retroactive
revocation/cancellation of already admitted execution.

The expanded focused suite passed **33 tests normally and under Python -O**.
Initial 30-test evidence remains preserved for its original revision. Full
Salamander constructor, existing pytest/installed-artifact/Windows validation,
the other native capability paths and independent assurance remain unverified;
this selective-source snapshot is not a complete repository execution environment.
The PR remains draft and not merge-ready.

## 5. Current EUCLID unification execution review (supersedes earlier counts)

### Identity and canonical architecture

**The frontier-agent and PHILOS are constituent parts of EUCLID.** Separate
review branches preserve implementation and qualification boundaries; they do
not make these components separate products or optional architectural add-ons.
Their missing runtime integration remains missing implementation/evidence, not
an owner scope reduction.

The supported governed entry point remains `euclid.EuclidRuntime`; no new
runtime, registry owner, learner, reward authority or memory root was introduced.
The capability fabric resolves executable handlers; `Intelligence.registry` is
an import/provenance inventory and the EUCLID organ registry routes specialists.
These are distinct roles, not interchangeable evidence of handler execution.

```text
host: existing CapabilityRegistry + existing native owner(s)
  -> register_proof_capability(registry, existing_tracker)
  -> register_repository_review_capability(registry, repo_root=host_root,
                                           approved_policies=host_policies)
  -> runtime.bind_intelligence(registry, profile=explicit_profile,
                               capabilities=explicit_allowlist)
caller -> runtime.dispatch_specialist
  -> detached request -> AL HARAS entitlement/operation/tenant/actor decision
  -> creator-scoped RightsLedger / Delegator
  -> IntelligenceSpecialist admission against atomic manifest/handler snapshot
  -> exact JSON input snapshot + schema/profile/byte-envelope validation
  -> existing HashChainAudit durable admission append (must succeed)
  -> actual registered handler -> exact JSON output + schema/status validation
  -> receipt + durable completion append (must succeed before returning success)
  -> EUCLID delegation result/evidence -> caller
```

Guardian observations are detached from the request eventually dispatched.
The handler receives a separate JSON value from the one hashed as admitted
input. A handler changing its input cannot rewrite the input digest or mutate
the caller's nested data. JSON boundary values reject non-string nested keys,
tuples, custom objects, cycles and non-finite numbers rather than coercing them.
Trusted legacy direct-fabric calls remain a compatibility path, **not** proof
of governed EUCLID authorization, durable audit, or authenticated input binding.

### Host-approved repository review API and migration

```python
from pathlib import Path
from Intelligence.capability_fabric import CapabilityRegistry, ExecutionProfile
from Intelligence.repository_review import ReviewPolicy
from Intelligence.repository_review_capability import register_repository_review_capability

registry = CapabilityRegistry()
# Host computes/approves this digest independently of the caller's request.
policy = ReviewPolicy((("example.py", approved_sha256),))
register_repository_review_capability(
    registry, repo_root=Path(host_repository), approved_policies={"review-1": policy})
specialist = runtime.bind_intelligence(
    registry, profile=ExecutionProfile.SHARED_RESTRICTED,
    capabilities=["repository-review"], organ_id="review")
# Separately configure AL HARAS policy/entitlement and creator grant for
# review.repository-review and review.request. Binding grants neither.
result = runtime.dispatch_specialist(
    "review", {"operation": "repository-review", "arguments": {"review_id": "review-1"}},
    tenant_id=tenant_id, actor=actor, subscription_token=subscription_token)
```

`SalamanderEngine(..., repository_review_policies={...})` calls the **same**
registration owner. Without approved policies repository review is disabled.
The fabric capability's old arbitrary `repo_root`/Python `policy` arguments are
not supported by version 1.1.0: migrate callers to host-approved identifiers.
The low-level `review_repository(repo_root=..., policy=...)` function remains
available for explicit trusted host use; it does not provide runtime authority.
Full Salamander construction/skills have NOT been executed in this review.

`specialist.catalog()` describes the explicit host binding and current schema,
version and availability. Availability is not entitlement, creator rights,
execution evidence or qualification. Missing/disabled/replaced unsafe manifests
are reported unavailable. The catalog returns detached schemas.

### Consumer and capability integration matrix

| Consumer/capability | Real implementation / route | Current evidence and remaining work |
| --- | --- | --- |
| Canonical proof-conjecture | runtime -> shared proof registration -> existing MathematicalProofTracker | Integrated and locally verified register/get/experiment; numerical evidence is not formal proof |
| Canonical repository-review | runtime -> shared review registration -> existing source-bound review_repository | Integrated and locally verified on real Linux temporary files; approved policy, source changes, symlinks and refusal paths tested |
| Salamander composition | existing constructor calls shared proof and review registration owners | Source wiring implemented; full constructor, skills and operational consumers not locally verified |
| source-repair | existing owner handler; mutating/external permissions refused by this bridge | Canonical execution boundary and end-to-end evidence incomplete |
| codebase-healing | existing owner handler; mutating execution refused by this bridge | Canonical execution boundary and end-to-end evidence incomplete |
| isolated-repair | existing owner executor; subprocess/mutation permissions refused by this bridge | Full real repair/recovery and Windows boundary evidence incomplete |
| repair-learning-query | existing repair outcome ledger adapter | Not exercised through canonical runtime; does not create a second learner |
| bsd-exploration | existing solver integration | Not verified through canonical runtime; finite rank experiments and heuristic quantities must not be reported as general BSD certification |
| external-agent-boundary | existing external integration owner | Not exercised/qualified through canonical runtime; external authority and controls not established |
| Skills / CLI / module inventory | existing loader, entry points and import inventory | Complete consumer migration and installed dispatch evidence missing; imports are not execution |
| EUCLID frontier-agent | PR68/69 owner interfaces and operational/qualification work | Constituent EUCLID capability; not connected or tested by this PR's current elevation snapshot; budget/STOP/WAIT/drift integration remains incomplete |
| EUCLID PHILOS | original emergence track + PR75 candidate custody work | Constituent EUCLID capability; current base lacks that track; measured reproduction/stress and canonical integration remain incomplete. No synthetic qualification promotion |

The earlier seven-unverified count is now **six** among the eight named native
capabilities for this minimal canonical composition. This does not establish
that every applicable supported consumer uses the canonical contract.

### Security and evidence custody

- Reproduced old handler-input mutation rewriting receipt input, and a Guardian
  observer mutating the request ultimately executed. Both now have regressions.
- Admission/completion/failure share an execution identifier. Receipt side-effect
  metadata binds the admitted manifest digest and local Python handler code
  fingerprint. The fingerprint does not bind closure/global/external state,
  establish trusted hardware, authenticate a signer or prove independent execution.
- Capability audit reuses the existing AL HARAS `HashChainAudit` implementation
  under the runtime state directory. It is a local hash chain, not OVID durable
  custody integration, a signature, WORM storage or independent certification.
- Admission-audit failure prevents handler execution. Completion-audit failure
  propagates failure, even if the handler already ran: no automatic rollback or
  exactly-once claim. Failed failure-audit writes are noted on the raised error.
- Runtime-duration enforcement remains post-return; no hard deadline, preemption,
  process isolation, memory ceiling or in-flight revocation guarantee was added.
- External/mutating execution still needs its owner's enforced controls. No
  protocol, mining, pool, acceptance or cryptographic boundary was changed.
- Targeted GitHub secret scanning was attempted but refused because Advanced
  Security is not enabled. No security-scanner pass or independent sign-off.

### Packaging and publication readiness

Inspection of the existing packaging found a concrete blocker:
`packaging/euclid-engine/build_and_verify.py` stages only `euclid`,
`hyba_substrate`, and `resonance_intelligence`, and explicitly forbids
`Intelligence` in the wheel. Its pyproject likewise excludes `Intelligence`.
The Salamander product package includes `salamander`/`al_haras`, not the
uppercase `Intelligence` package. Therefore the optional canonical bridge is
not established as usable from that standalone EUCLID artifact. This review
does not paper over the gap with an invented wheel or copied runtime alias.

The supported build entry point remains:
`python packaging/euclid-engine/build_and_verify.py` in a complete checkout
with its declared build tools, sibling products and dependency access. The
existing script removes stale artifacts and resolves dependencies; it was
inspected but NOT run here. An offline root build attempt using
`python -m pip wheel --no-index --no-deps --no-build-isolation --wheel-dir ... .`
failed with exit 2 because setuptools is absent. `build`, wheel and pytest are
also absent; the source snapshot is incomplete. No clean-installed artifact,
supported-platform matrix, reproducible release or publication readiness claim.
Do not publish, release, deploy or merge from these local results.

### Release criteria and disposition

| Criterion | Disposition |
| --- | --- |
| Real canonical schema/auth/handler/result path | PASS for two native capability paths only |
| Admission/completion audit and input snapshot regressions | PASS locally on Linux/Python 3.13.14 |
| All supported consumers / six remaining native handlers | INCOMPLETE |
| Frontier-agent and PHILOS constituent runtime integration | INCOMPLETE |
| Full Salamander lifecycle and skill composition | NOT EXECUTED |
| Original pytest/full regression, lint and optimized checks | 46 unittest cases pass normally and under -O; pytest/lint tools unavailable |
| Built package / clean install / installed API execution | BLOCKED by missing build tools, incomplete snapshot and identified package omission |
| Windows filesystem/reparse/process evidence | NOT EXECUTED |
| Security scanning / independent T5 assurance / production drift and Lucas gates | OPEN; no qualification advance |
| Required authoritative CI and reviews | NOT established; keep draft and merge blocked |

Current disposition: **focused implementation ready for technical review, not
whole-system consolidation, merge readiness, release candidate or production
qualification**. Exact commands, source hashes and local outputs are appended
to `docs/salamander_consolidation_validation.json`; the existing capability
manifest is the machine-readable current ledger. No competing root ledger was
created: `CAPABILITY-LEDGER.md` was absent from this PR's pinned base.


## 2026-10-14 — Constituent execution and delegated-authority follow-up

This section supersedes earlier current-state counts and the statement that both
constituent boundary paths were entirely unwired. **Frontier-agent and PHILOS are
parts of EUCLID.** Production readiness remains the target; a stand-in is an
explicit migration aid, not the final production architecture or assurance.

Starting review heads: PR74 `29b016c2a1dec377f55cd8f86f271089c5eae527`, PR75
`a41cc1a186bd3460366e6e3fcf55529ec51f7b73`. PR69's unchanged frontier owner is
`370be998286dd8aadc7a9bccb9f397559f2cc791`. All 41 `chronus/agent` source files
reconstructed from connector patches match that head's live Git blob hashes.
No branches were merged/rebased/cherry-picked. Cross-branch local composition is
compatibility evidence, not an already unified deployable branch or wheel.

### Canonical consumer integration map

| Consumer | Actual path / ownership | Current evidence |
| --- | --- | --- |
| Native conjecture + repository review | Existing `bind_intelligence` -> AL HARAS -> creator rights/Delegator -> shared fabric -> actual handler | 48 canonical regressions normal and optimized; two native capabilities, not all eight |
| EUCLID frontier-agent | Host `euclid.frontier_integration.bind_frontier` -> same `dispatch_specialist` -> `FrontierSpecialist` -> existing `FrontierAgent.run` / operational loop | Real temporary-file action; STOP/WAIT, kill, budget/deadline refusal, native grants, signed scope, observation and verification remain checked |
| EUCLID PHILOS | PR75 host `euclid.emergence.integration.bind_philos` -> same canonical boundary -> existing `EmergentQualificationService.qualify` | 11 actual-owner integration/refusal tests; simulated evidence remains REJECTED |
| Full Salamander/skills, six remaining native capabilities, production learning consumers | Earlier map and ownership still apply | Not established as end-to-end production integrations |

New owner adapters do NOT create a parallel registry, learner, memory store,
reward authority or runtime. Optional *imports* defer unavailable dependencies;
they do not reduce either constituent's declared architectural scope. Frontier
and PHILOS bindings must be explicitly configured by the host. Binding grants no
rights, entitlement, signer, model, trust promotion or qualification.
`register_specialist(..., authority=Authority.PROPOSE/MUTATE_WORLD)` now describes
the actual owner rather than labelling every specialist read-only. This metadata
is not an OS guard: actual security remains AL HARAS, creator-scoped grants and
the owner's enforced controls. Default READ_ONLY registration remains compatible.

Host approves native `FrontierCase(objective, cognition, plan)` values and an
actual configured agent. Requests contain only `operation=run` and `case_id`;
clients cannot supply executables, plans, providers or signers. Cases are detached
and fully digested; an SQLite single-use record is consumed before invoking the
agent, survives restart and prevents an automatic duplicate attempt. Failure
never refunds that case. New attempts require explicit new host-approved cases.
This is local idempotency custody, not distributed exactly-once semantics or
rollback of already performed effects. Existing budgeted loop retries remain
inside the one native run and its shared budget.

### Supplied permissive stand-ins (explicit operator delegation)

`euclid.operator_development.OperatorDevelopmentGuards` supplies real
`execute`/`rollback` callback ports requested by the operator. Instantiate it with
`profile="operator-development"`, a named `delegated_by`, an explicit tuple of
`(actual_adapter, exact_ActionRequest)` bindings, durable `HashChainAudit`, and
the host's monotonic frontier clock. Pass its bound methods to the existing
`FrontierAgent` constructor; no production defaults or guards were weakened.

```python
ports = OperatorDevelopmentGuards(
    profile="operator-development", delegated_by=operator_identity,
    approved=((adapter, request),), audit=operator_audit, clock=clock,
)
# Existing actual owner construction, including all native authority/verification
# parameters, is retained:
# FrontierAgent(..., execution_guard=ports.execute, rollback_guard=ports.rollback)
bind_frontier(runtime, agent, cases={"approved-change": FrontierCase(objective, cognition, plan)})
# Host must separately grant the creator-scoped frontier.request dispatch right
# and obtain a valid AL HARAS entitlement. Binding itself grants neither.
```

These stand-ins are permissive **within the operator's exact delegated scopes**:
they invoke the real adapter rather than return a success placeholder. They audit
before effects, require native execution receipts, reject false-success mappings,
validate declared returned costs and check deadlines after return. Revocation
blocks new actions but permits budgeted recovery; the real loop must observe and
verify rollback. They do not invent independent reviewers or return fabricated
qualification. Local tests use private random host signers and local observations:
they exercise authorization and verification contracts, not independent assurance.

Known limits are explicit: cooperative/post-return deadlines, adapter-reported
resource use, no forced cancellation, hard memory limit, OS/process sandbox,
independent metering or mid-flight revocation. A late/over-budget return may have
already caused effects and is surfaced as failure, not pretended away. Production
must configure the external execution/isolation/metering controls appropriate to
its owner and deployment; do not relabel these stand-ins as such controls.

### Security fixes and verification

- Reproduced a host-configured absolute organ identifier escaping the designated
  Intelligence audit subdirectory. Both Intelligence and new owner bindings now
  require path-free ASCII identifiers of 1–64 characters before file creation.
  This is a configuration/path bug, not a claim of remote arbitrary-code execution.
- PHILOS's public default signing authority is removed on PR75. Verifier stores
  only allowlisted external Ed25519 public keys; candidate/audience/issuer/officer/
  operation/time/nonce are signed; durable SQLite replay admission is mandatory.
  This authenticates invocation, not a successful result or independent certificate.
- Actual checks: **48 canonical + 19 authorization + 23 custody + 11 PHILOS
  runtime + 14 frontier/operator = 115 tests passed**, with zero failures/errors/
  skips, and the same **115 under Python -O**. These are separate suites, not the
  historical frontier test count. Compileall and tabnanny also returned 0.
- New paths use genuine package initializers, AL HARAS, rights, native services,
  SQLite/JSONL and temporary Linux files. Unit/negative-contract tests retain
  explicitly scoped doubles; canonical runtime/handler composition is not mocked.
- Joint tests require PR69 owner code plus PR74/PR75 changes. On a branch missing
  that prerequisite the relevant tests explicitly SKIP; a skip is NOT integration
  success. Normal and optimized joint runs here had zero skips.

Exact invocations, environment, verbatim output, source hashes and pinned-owner
verification are appended to existing `docs/salamander_consolidation_validation.json`.
Existing capability manifest is updated; upstream skill source locks are unchanged
because no upstream skill content/catalogue/license was changed. Local logs and
hashes are not signed or independent execution attestation.

### Remaining production-readiness gates

The two constituent boundary paths now have local execution/refusal evidence;
that is NOT complete ubiquitous Intelligence or successful PHILOS qualification.
Real measured PHILOS reproduction/stress, detection attestation, full observation
windows/source and executor bindings, independent T5 assurance, actual Lucas/drift
enforcement, all native consumers, full Salamander lifecycle, Windows behavior,
security scanning, authoritative CI/reviews and installed-artifact tests remain
open. PHILOS invocation signatures must not be represented as signatures over a
qualification result. Native request/evidence records can include scoped signed
authorizations; protect those host state stores and their retention/access.

The earlier standalone packaging omission and unavailable build tools remain
unfixed/unverified; no wheel or clean installation was successfully tested. No
pytest/full regression, scanner or formatter/linter pass is claimed. Same-process
Python allowlists and protected local SQLite/JSONL state are not an OS trust
boundary, network replay consensus or backup-rollback resistance. Preserve OVID
state custody, THESEUS projections, EUCLID learning/reward authority, Salamander
experience/deployment ownership and Chronus execution; no alternate learning
store/authority was introduced. No mining/pool/protected protocol changes or live
operations were performed. **Draft technical review; merge/release/production
qualification remain blocked.**
