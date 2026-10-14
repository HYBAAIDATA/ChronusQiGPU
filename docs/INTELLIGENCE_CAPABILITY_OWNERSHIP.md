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
