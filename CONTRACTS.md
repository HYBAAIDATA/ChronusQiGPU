# CONTRACTS.md

**HYBA / MLA1517 + PRIME-DB — Interface Contract Document**

**Version:** 1.0
**Status:** Canonical
**Audience:** Engineers, architects, auditors, design partners
**Scope:** Every cross-boundary connection in the platform

---

## Doctrine

> **Every connection is a contract. Every contract has a producer, a consumer, a schema, an invariant, a failure mode, and a proof. Nothing crosses a boundary silently.**

### Ten Rules

| # | Rule |
|---|------|
| R1 | Every cross-boundary call has a typed contract |
| R2 | Every contract has a version |
| R3 | Every version has a compatibility matrix |
| R4 | Every failure mode is declared, not discovered |
| R5 | Every fallback is explicit and marked |
| R6 | Every rehydration is recorded |
| R7 | Every claim is reproducible from a command |
| R8 | Every proof is independently verifiable |
| R9 | Every policy travels with the object |
| R10 | No contract is implicit |

---

## Table of Contents

1. [Master Connection Map](#1-master-connection-map)
2. [Contract C1 — User → Assembly Compiler](#c1--user--assembly-compiler)
3. [Contract C2 — Assembly → Policy](#c2--assembly--policy)
4. [Contract C3 — Policy → Query Planner](#c3--policy--query-planner)
5. [Contract C4 — Query Planner → PRIME-DB](#c4--query-planner--prime-db)
6. [Contract C5 — PRIME-DB → Backend Registry](#c5--prime-db--backend-registry)
7. [Contract C6 — Backend Selection](#c6--backend-selection)
8. [Contract C7 — Backend → Result Receipt](#c7--backend--result-receipt)
9. [Contract C8 — Result → Proof + Evidence](#c8--result--proof--evidence)
10. [Contract C9 — Evidence → PRIME-DB Commit](#c9--evidence--prime-db-commit)
11. [Contract C10 — Commit → Observability](#c10--commit--observability)
12. [Foundational Bidirectional Contracts](#12-foundational-bidirectional-contracts)
13. [Prohibited Connections](#13-prohibited-connections)
14. [Failure Taxonomy](#14-failure-taxonomy)
15. [Compatibility Matrix](#15-compatibility-matrix)
16. [Contract Test Suite](#16-contract-test-suite)
17. [Summary Card](#17-summary-card)

---

## 1. Master Connection Map

```
┌─────────────────────────────────────────────────────────────┐
│                     USER / AGENT / APP                      │
└──────────────────────────┬──────────────────────────────────┘
                           │ C1: IntentManifest
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              HYBA ASSEMBLY COMPILER                         │
│  parse → resolve → check → plan → explain → compile         │
└──────────────────────────┬──────────────────────────────────┘
                           │ C2: AssemblyLock
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              POLICY / IDENTITY / ADMISSION                  │
└──────────────────────────┬──────────────────────────────────┘
                           │ C3: AuthorizedQuery
                           ▼
┌─────────────────────────────────────────────────────────────┐
│         TYPED QUERY IR + COST/PROOF PLANNER                 │
│  family detect → operator mode → backend select → cost      │
└──────────────────────────┬──────────────────────────────────┘
                           │ C4: ExecutionPlan
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              PRIME-DB AUTHORITATIVE OBJECT                  │
│  exact_state | folded | residual | proof | lineage | policy │
└──────────────────────────┬──────────────────────────────────┘
                           │ C5: CapabilityRequest
                           ▼
┌─────────────────────────────────────────────────────────────┐
│         BACKEND REGISTRY + CAPABILITY NEGOTIATION           │
└──────┬──────────┬──────────┬──────────┬──────────┬─────────┘
       │ C6a      │ C6b      │ C6c      │ C6d      │ C6e
       ▼          ▼          ▼          ▼          ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ CPU      │ │ MLA1517  │ │ HOST GPU │ │ FPGA     │ │ QUANTUM  │
│ EXACT    │ │ GPU/iGPU │ │ OVERLAY  │ │ (RTL)    │ │ EXACT    │
└────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
     │ C7a        │ C7b        │ C7c        │ C7d        │ C7e
     └────────────┴────────────┴────────────┴────────────┘
                           │ C7: ResultReceipt
                           ▼
┌─────────────────────────────────────────────────────────────┐
│         PROOF + LINEAGE + EVIDENCE COMMIT                   │
└──────────────────────────┬──────────────────────────────────┘
                           │ C8: EvidenceObject
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              PRIME-DB COMMIT / QUARANTINE                   │
└──────────────────────────┬──────────────────────────────────┘
                           │ C9: Transaction
                           ▼
┌─────────────────────────────────────────────────────────────┐
│         OBSERVABILITY + TELEMETRY + AUDIT                   │
└─────────────────────────────────────────────────────────────┘
                           ▲
                           │ C10: TelemetrySnapshot
```

---

## C1 — User → Assembly Compiler

**Producer:** User | Agent | Application
**Consumer:** HYBA Assembly Compiler
**Transport:** `IntentManifest` (YAML)

### Schema

```yaml
apiVersion: hyba.ai/v1
kind: PlatformAssembly
metadata:
  name: <string>
  deploymentSeed: <string>
intent:
  industry: <enum>
  useCases: [<string>]
  scale:
    profile: <enum>
    eventsPerSecond: <int>
    retainedData: <size>
    regions: <int>
  risk:
    level: <enum>
    importantBusinessService: <bool>
  data:
    classes: [<enum>]
    residency: [<region>]
    exactness: <enum>
  compliance:
    packs: [<enum>]
  availability:
    target: <percent>
    recoveryTime: <duration>
    recoveryPoint: <duration>
  execution:
    prefer: [<backend>]
    silentFallback: false
  security:
    customerManagedKeys: <bool>
    privateNetworking: <bool>
    humanApprovalForHighRiskActions: <bool>
  economics:
    optimiseFor: [<enum>]
  operations:
    automaticScaling: <bool>
    automaticRemediation: <enum>
```

### Invariants

| ID | Invariant |
|----|-----------|
| I1 | `silentFallback` MUST be `false` |
| I2 | `residency` MUST be declared |
| I3 | `exactness` MUST be declared |
| I4 | `risk` MUST be declared |
| I5 | Every `useCase` MUST map to a capability in the registry |

### Failure Modes

| ID | Condition | Action |
|----|-----------|--------|
| F1 | Unknown capability | Reject with actionable reason |
| F2 | Incompatible modules | Reject with conflict list |
| F3 | Silent fallback requested | Reject (prohibited) |
| F4 | Missing residency | Reject |
| F5 | Unsupported compliance pack | Warn + continue with gap report |

### Proof

- Manifest hash recorded
- Seed recorded
- Rejected alternatives recorded in explanation

---

## C2 — Assembly → Policy

**Producer:** Assembly Compiler
**Consumer:** Policy / Identity / Admission
**Transport:** `AssemblyLock` + `PolicyContext` draft

### Schema

```
AssemblyLock {
    lock_id
    manifest_hash
    modules[]
    topology
    resources
    policies
    assumptions[]
    compatibility_decisions[]
    test_results[]
    signature
    version
}

PolicyContext {
    identity
    purpose
    residency
    retention
    exactness_requirement
    allowed_operators[]
    reconstruction_rights
    export_rights
    tenant
    sovereignty_domain
}
```

### Invariants

| ID | Invariant |
|----|-----------|
| I1 | `AssemblyLock` is immutable after signing |
| I2 | `PolicyContext` MUST be derived from `AssemblyLock`, not invented |
| I3 | No policy may weaken a declared invariant |
| I4 | Every policy change produces a new `AssemblyLock` version |

### Failure Modes

| ID | Condition | Action |
|----|-----------|--------|
| F1 | Policy conflicts with resilience | Reject |
| F2 | Policy conflicts with exactness | Reject |
| F3 | Policy conflicts with residency | Reject |
| F4 | Key unavailable | Fail closed |

### Proof

- Signed access decision receipt per policy evaluation
- Policy version recorded on every object

---

## C3 — Policy → Query Planner

**Producer:** Policy Engine
**Consumer:** Typed Query IR + Cost/Proof Planner
**Transport:** `AuthorizedQuery`

### Schema

```
AuthorizedQuery {
    query
    policy_context
    allowed_backends[]
    allowed_exactness_modes[]
    allowed_operators[]
    budget: {
        bytes_moved
        latency
        cost
        energy
        proof_bytes
    }
    residency_constraint
    reconstruction_permitted
    export_permitted
}
```

### Invariants

| ID | Invariant |
|----|-----------|
| I1 | Query cannot request an operator not in `allowed_operators` |
| I2 | Query cannot request exactness not in `allowed_exactness_modes` |
| I3 | Query cannot request residency outside constraint |
| I4 | Query cannot bypass reconstruction policy |
| I5 | Budget MUST be enforced before execution, not after |

### Failure Modes

| ID | Condition | Action |
|----|-----------|--------|
| F1 | Operator not allowed | Reject at planning time |
| F2 | Exactness not allowed | Reject at planning time |
| F3 | Residency violation | Reject at planning time |
| F4 | Budget exceeded | Reject at planning time |
| F5 | Unsupported semantics | Reject at planning time |

> **Note:** Never partial, never silent.

### Proof

- Planning decision recorded with reason
- Rejected plan recorded with reason
- Selected backend recorded with capability certificate

---

## C4 — Query Planner → PRIME-DB

**Producer:** Query Planner
**Consumer:** PRIME-DB
**Transport:** `ExecutionPlan`

### Schema

```
ExecutionPlan {
    plan_id
    query
    object_ids[]
    fold_family
    operator
    operator_mode : {PRESERVE, TRANSFORM, REHYDRATE, REJECT}
    backend_target
    exactness_mode
    residual_budget
    movement_budget
    proof_requirement
    policy_context
    fallback_policy : {
        permitted: bool
        marked: bool
    }
}
```

### Invariants

| ID | Invariant |
|----|-----------|
| I1 | `operator_mode` MUST match operator contract |
| I2 | `fold_family` MUST match object fold contract |
| I3 | `backend_target` MUST support operator + exactness |
| I4 | `fallback_policy.permitted` → `fallback_policy.marked` MUST be `true` |
| I5 | No plan may silently rehydrate |
| I6 | No plan may silently change exactness |

### Failure Modes

| ID | Condition | Action |
|----|-----------|--------|
| F1 | Fold family mismatch | Reject |
| F2 | Operator not supported | Reject |
| F3 | Backend lacks capability | Reject |
| F4 | Residual budget exceeded | Reject |
| F5 | Proof requirement unsatisfiable | Reject |
| F6 | Fallback not marked | Reject (prohibited) |

### Proof

- Plan hash recorded
- Every decision recorded with reason
- Every rehydration recorded in materialisation ledger

---

## C5 — PRIME-DB → Backend Registry

**Producer:** PRIME-DB
**Consumer:** Backend Registry + Capability Negotiation
**Transport:** `PRIMEObject` + `FoldContract` + `CapabilityRequest`

### Schema

```
PRIMEObject {
    object_id
    payload_type
    exact_state
    scale_index
    lucas_state
    pisot_fold
    binet_view
    fibonacci_pair
    zeckendorf_code
    prime_address
    polyhedral_location
    transform_state
    cassini_seal
    residual_boundary
    lineage
    version
}

CapabilityRequest {
    required_operator
    required_exactness
    required_precision_bound
    required_residency
    required_attestation
    required_backend_kind[]
    prohibited_backend_kind[]
    fallback_policy
}
```

### Invariants

| ID | Invariant |
|----|-----------|
| I1 | `PRIMEObject` MUST carry its `FoldContract` version |
| I2 | `PRIMEObject` MUST carry its policy context |
| I3 | `PRIMEObject` MUST carry its lineage |
| I4 | `CapabilityRequest` MUST declare fallback policy |
| I5 | No backend may be selected that cannot satisfy exactness |

### Failure Modes

| ID | Condition | Action |
|----|-----------|--------|
| F1 | No backend satisfies capability | Reject |
| F2 | Required attestation absent | Fail closed |
| F3 | Required residency unsupported | Reject |
| F4 | Required precision unsupported | Reject |
| F5 | Fallback required but prohibited | Fail closed |

### Proof

- Backend selection recorded with reason
- Capability negotiation recorded
- Backend certificate attached to result

---

## C6 — Backend Selection

### C6a — CPU Exact

| Field | Value |
|-------|-------|
| **Producer** | Backend Registry |
| **Consumer** | CPU Exact Backend |
| **Transport** | `ExecutionPlan` + `PRIMEObject` |
| **Role** | Correctness floor, conformance |
| **Exactness** | EXACT |

**Guarantees:**
- G1: Deterministic
- G2: Bit-exact with Python reference
- G3: Never approximates

**Failure:** Reject on resource exhaustion (no silent degradation)

---

### C6b — MLA1517 GPU/iGPU

| Field | Value |
|-------|-------|
| **Producer** | Backend Registry |
| **Consumer** | MLA1517 GPU/iGPU |
| **Transport** | `HotDescriptor` (64 bytes) + `ExecutionPlan` |
| **Role** | Native primary |
| **Exactness** | EXACT (for declared operators) |

**Guarantees:**
- G1: Primary when connected
- G2: Host GPU is assist, not replacement
- G3: Reports `scaling_applied` truthfully

**Failure:**
- F1: Device absent → mark degraded, use CPU only if allowed
- F2: Required but absent → fail closed
- F3: Overflow → hard error, no wrap

---

### C6c — Host GPU Overlay

| Field | Value |
|-------|-------|
| **Producer** | Backend Registry |
| **Consumer** | Host GPU Overlay |
| **Transport** | `HostGPUPlan` + tiles + kernel contract |
| **Role** | Optional scale assist |
| **Exactness** | Depends on kernel; MUST match declared |

**Guarantees:**
- G1: MLA1517 remains selected backend when both present
- G2: Tiles are complete, non-overlapping, deterministic
- G3: Merge is deterministic
- G4: Never impersonates MLA1517

**Failure:**
- F1: Host GPU absent → mark degraded if allowed
- F2: Required but absent → fail closed
- F3: Kernel mismatch with reference → reject

---

### C6d — FPGA (RTL)

| Field | Value |
|-------|-------|
| **Producer** | Backend Registry |
| **Consumer** | FPGA Backend |
| **Transport** | `HotDescriptor` + ROM contract |
| **Role** | Hardware target (not yet validated) |
| **Exactness** | EXACT within ROM boundary |
| **Status** | CONTRACTED, not VERIFIED until toolchain runs |

**Guarantees:**
- G1: ROM boundary respected (nonce 0..255)
- G2: Out-of-range nonce rejected, never wrapped
- G3: No IEEE-754

**Failure:**
- F1: Synthesis fail → backend unavailable
- F2: Timing closure fail → backend unavailable
- F3: ROM overflow → reject

---

### C6e — Quantum Exact

| Field | Value |
|-------|-------|
| **Producer** | Backend Registry |
| **Consumer** | Exact Quantum Backend |
| **Transport** | `ExactQuantumState` (Q(√2) + iQ(√2)) |
| **Role** | Exact quantum mathematics |
| **Exactness** | EXACT |

**Guarantees:**
- G1: Rational coordinates only
- G2: No floating arithmetic
- G3: Denominator bound published
- G4: Overflow raises `ExactResourceError`

**Failure:**
- F1: Device kernel absent → `AcceleratorUnavailable`, **NEVER** approximate fallback
- F2: Unsupported Hamiltonian → fail closed
- F3: Denominator overflow → `ExactResourceError`

---

## C7 — Backend → Result Receipt

**Producer:** Any Backend
**Consumer:** Result Assembly + Proof Commit
**Transport:** `ResultReceipt`

### Schema

```
ResultReceipt {
    result
    object_hashes[]
    lineage
    exactness_mode
    invariant_checks[]
    backend_identity
    backend_certificate
    bytes_moved
    materialisation_ledger[]
    rehydration_events[]
    fallback_events[]
    proof_cost
    replay_material
    performance_claim_policy : "measured_only"
}
```

### Invariants

| ID | Invariant |
|----|-----------|
| I1 | Every result carries backend identity |
| I2 | Every result carries exactness mode |
| I3 | Every rehydration is recorded |
| I4 | Every fallback is recorded and marked |
| I5 | Every invariant check is recorded |
| I6 | No result may claim performance without measurement |
| I7 | Result hash must be reproducible from `replay_material` |

### Failure Modes

| ID | Condition | Action |
|----|-----------|--------|
| F1 | Invariant check failed | Quarantine, do not publish |
| F2 | Backend certificate missing | Reject |
| F3 | Rehydration unrecorded | Reject (prohibited) |
| F4 | Fallback unmarked | Reject (prohibited) |
| F5 | Hash mismatch | Quarantine |

### Proof

- Replay command included
- Baseline comparison included
- Movement ledger complete

---

## C8 — Result → Proof + Evidence

**Producer:** Result Assembly
**Consumer:** Proof + Lineage + Evidence Commit
**Transport:** `EvidenceObject`

### Schema

```
EvidenceObject {
    id
    type
    source_hashes[]
    transformations[]
    invariants[]
    backend_certificate
    policy_context
    signature
    timestamp
    reviewer
    replay_command
    independent_verifier_available
}
```

### Invariants

| ID | Invariant |
|----|-----------|
| I1 | `EvidenceObject` is append-only |
| I2 | `EvidenceObject` is independently verifiable |
| I3 | `EvidenceObject` carries policy context |
| I4 | `EvidenceObject` carries backend certificate |
| I5 | `EvidenceObject` replay does not require running MLA1517 |

### Failure Modes

| ID | Condition | Action |
|----|-----------|--------|
| F1 | Signature invalid | Reject |
| F2 | Policy context missing | Reject |
| F3 | Backend certificate missing | Reject |
| F4 | Replay command fails | Reject |

### Proof

- External verifier can validate without MLA1517
- Audit pack exportable
- Control evidence continuously collected

---

## C9 — Evidence → PRIME-DB Commit

**Producer:** Proof Commit
**Consumer:** PRIME-DB Commit / Quarantine
**Transport:** `Transaction`

### Schema

```
Transaction {
    transaction_id
    objects[]
    evidence_objects[]
    lineage
    policy_context
    atomicity_requirement
    durability_requirement
    rollback_material
}
```

### Invariants

| ID | Invariant |
|----|-----------|
| I1 | Multi-object commit is atomic |
| I2 | Commit publishes cursor after state write |
| I3 | Durability barrier is explicit, not implicit |
| I4 | Crash during commit → recoverable, no acknowledged loss |
| I5 | Torn write → detected and rejected |
| I6 | Quarantine path exists for failed invariant |

### Failure Modes

| ID | Condition | Action |
|----|-----------|--------|
| F1 | Partial write | Rollback |
| F2 | Concurrent conflict | Serialize or reject |
| F3 | Cursor publication fail | Retry, then quarantine |
| F4 | Durability fail | Explicit error, never silent loss |
| F5 | Corruption detected | Quarantine, never silent return |

### Proof

- Reopen recovery reproduces object, policy, proof, lineage
- Cursor total matches committed count
- Corruption excluded from queries

---

## C10 — Commit → Observability

**Producer:** PRIME-DB Commit
**Consumer:** Observability + Telemetry + Audit
**Transport:** `TelemetrySnapshot` (seqlock)

### Schema

```
TelemetrySnapshot {
    magic: 0x5A1A1517
    version
    sequence (even/odd)
    per_lane_cassini_faults[32]
    aggregate_stratum_drops
    vertex_cursors[20]
    partition_telemetry[32]
    d5_d7_routing_health
    proof_failures
    residual_growth
    unsupported_operations
    rehydration_events
    backend_mismatches
}
```

### Invariants

| ID | Invariant |
|----|-----------|
| I1 | Telemetry is observational, never on critical path |
| I2 | Relaxed counters, non-blocking |
| I3 | Seqlock snapshot is consistent |
| I4 | Odd sequence → retry |
| I5 | Changed sequence → retry |

### Failure Modes

| ID | Condition | Action |
|----|-----------|--------|
| F1 | Stale snapshot | Retry |
| F2 | Magic mismatch | Reject |
| F3 | Version unsupported | Reject |

### Proof

- C seqlock snapshot matches Python offsets
- 960 bytes across 11 fields
- Telemetry can be replayed

---

## 12. Foundational Bidirectional Contracts

These co-designed pairs define the platform's character. They are not sequential; they are the always-on contracts that every other contract depends on.

### 12.1 PRIME-DB ↔ MLA1517

**Producer/Consumer:** Bidirectional
**Transport:** `HotDescriptor` (64 bytes) + `FoldContract` + `OperatorContract`

**Flow:**
```
PRIME-DB object
    ↓ validate hash, Fibonacci state, Cassini, Zeckendorf
MLA1517 runtime
    ↓ select mode and lane count
Backend connector
    ↓ integrated_iGPU | host_gpu_overlay | cpu_reference
Host-GPU planner
    ↓ deterministic, complete, non-overlapping tiles
Kernel execution
    ↓ hardware adapter or CPU conformance fallback
Proof envelope
    ↓ object validity, seal, coverage, execution status
Deterministic result merge
    ↓
PRIME-DB commit
```

**Guarantees:**
- G1: Same typed object from persistence to execution
- G2: No untracked format conversion
- G3: Transformations produce lineage and proof records
- G4: Fail-closed on missing hardware
- G5: No performance claim until hardware measurements exist

---

### 12.2 Fold ↔ Operator

**Producer:** Fold family
**Consumer:** Operator
**Transport:** `FoldContract` + `OperatorContract`

**Rules:**
- R1: Operator declares accepted fold families
- R2: Operator declares mode: `PRESERVE | TRANSFORM | REHYDRATE | REJECT`
- R3: `PRESERVE`: input and output invariants preserved
- R4: `TRANSFORM`: residual rule must be satisfied
- R5: `REHYDRATE`: materialisation ledger must record
- R6: `REJECT`: fails at planning time, never at execution
- R7: No operator may silently change exactness
- R8: No operator may silently rehydrate
- R9: No operator may bypass invariant check

**Compatibility Matrix:**

| Fold Family | Operators | Mode |
|-------------|-----------|------|
| fibonacci | fib_store, cassini_verify, fold_execute | PRESERVE |
| zeckendorf | zeckendorf_encode, algebraic_query | PRESERVE |
| pisot_binet | pisot_fold, binet_view, lucas_scale | TRANSFORM |
| tensor_exact | tensor_contract, tensor_product | PRESERVE |
| quantum_exact | all_exact_gates | PRESERVE |

**Failure:**
- F1: Family not accepted → reject
- F2: Operator mode unsupported → reject
- F3: Residual bound violated → reject
- F4: Invariant violated → quarantine

---

### 12.3 M32 ↔ Transport

**Producer:** M32 partition router
**Consumer:** Shared-memory ring
**Transport:** 64-byte `HotDescriptor`

**Topology:**
- 12 icosahedral execution nodes
- 20 dodecahedral memory nodes
- 32 logical partitions

**Routing:**
```
nonce = partition_id + 32 * step
vertex = D7 % 20
ASSERT coverage is exact-once
```

**Transport Contract:**
- T1: POSIX shared memory via `/dev/shm`
- T2: Bounded sequence-numbered lock-free ring
- T3: Acquire/release atomic publication
- T4: Fixed 64-byte descriptors
- T5: Sequence positions, not pointers
- T6: Aethel for exact/cold state, lineage, checkpoints, proofs

**Guarantees:**
- G1: Cross-process visibility
- G2: No torn reads (double-read validation)
- G3: Backpressure before loss
- G4: Spill ring for overflow (explicit, not silent)
- G5: Reopen validates magic/version, does not reset

**Failure:**
- F1: Ring full → backpressure, then spill
- F2: Spill full → explicit catastrophic backpressure
- F3: Torn read → retry
- F4: Magic mismatch → reject

---

### 12.4 SIMT ↔ Aethel UMA

**Producer:** 32-lane SIMT warp
**Consumer:** Aethel UMA vault
**Transport:** Winning lane descriptors

**Warp Contract:**
- W1: `lane_id ∈ [0,31]`
- W2: `nonce = lane_id + 32 × step`
- W3: Ballot produces 32-bit acceptance mask
- W4: Zero mask advances full warp
- W5: Non-zero mask triggers compaction
- W6: Prefix-rank compaction
- W7: Only active lanes materialise
- W8: No branch divergence

**UMA Contract:**
- U1: No PCIe transfer
- U2: Atomic sequence publication
- U3: Cache/coherence explicit
- U4: Failed lanes never enter vault
- U5: Only winners, proofs, checkpoints consume bandwidth

**Failure:**
- F1: All lanes zero → advance, no write
- F2: Compaction collision → lowest-lane selection
- F3: Sequence publication fail → retry, then quarantine

---

### 12.5 Salamander ↔ Execution

**Producer:** Salamander supervisor
**Consumer:** Execution warp
**Transport:** MMIO CSR writes + `COMMIT_ACK`

**Control Contract:**
- C1: Sense telemetry consistently (seqlock)
- C2: Stage CSR change
- C3: Commit at warp boundary
- C4: Wait for `COMMIT_ACK`
- C5: At most one transaction per tick
- C6: Stop at 24-lane floor
- C7: Enter degraded mode below floor
- C8: Record lane watermark in orphan min-heap
- C9: Readmission requires 60s probation + 3 passes + fresh watermark

**Actuation Boundary:**
- A1: Quarantine/restore lane via lane-enable CSR
- A2: Update polyhedral-mask CSR
- A3: Request failover via control-plane integration
- A4: Observe-only by default
- A5: Never mount Docker socket
- A6: Never infer thermal fault from one counter

**Failure:**
- F1: ACK timeout → revert
- F2: Lane floor reached → degraded mode
- F3: Telemetry stale → retry, then observe-only
- F4: Failover cooldown active → wait

---

### 12.6 Agentic ↔ Salamander

**Producer:** Agentic layer
**Consumer:** Salamander safety veto
**Transport:** `ProposedAction`

**Flow:**
```
measure → geometry → topology → observed-support lookup
→ Salamander veto → optional ACK-gated actuation
```

**Contract:**
- A1: No generated trajectories
- A2: No probabilistic policy selection in production
- A3: No synthetic counterfactuals
- A4: Forward state requires real before/after record
- A5: Causal effects require commissioned interventions
- A6: Counterfactual scores require observed support in same regime
- A7: Unsupported action → `SupportViolation`
- A8: No supported action → safe action, no write
- A9: Actuator called only after veto + ACK
- A10: Failed ACK → return safe action

**Failure:**
- F1: Support violation → raise, no action
- F2: Veto → no action
- F3: ACK fail → safe action

---

### 12.7 Quantum ↔ Everything

**Producer:** Exact quantum backend
**Consumer:** Any requesting layer
**Transport:** `ExactQuantumState`

**Boundary:**
- B1: Exact quantum mathematics is available now
- B2: Simulation is distinct from physical execution
- B3: Physical QRAM/QDC unavailable until backend conforms
- B4: `mla1517_chronus` quantum selection raises `AcceleratorUnavailable`
- B5: **NEVER** fall back to approximation
- B6: **NEVER** claim quantum advantage without device certificate

**Contract:**
- Q1: Amplitudes stored as Q(√2) + iQ(√2)
- Q2: Rational coordinates only
- Q3: No floating arithmetic in exact path
- Q4: State-vector allocation bounded
- Q5: `ExactResourceError` on overflow, never degrade
- Q6: Unsupported Hamiltonian → fail closed
- Q7: Denominator bound published

**Failure:**
- F1: Device absent → `AcceleratorUnavailable`
- F2: Overflow → `ExactResourceError`
- F3: Unsupported op → fail closed
- F4: Approximation requested → reject

---

### 12.8 Claims ↔ Release Gate

**Producer:** Claim register
**Consumer:** Release gate
**Transport:** `claims.yaml`

**Contract:**
- C1: Every claim has status
- C2: `VERIFIED` requires passing `test_command`
- C3: `VERIFIED` requires `artifact_hash` match
- C4: `VERIFIED` requires baseline
- C5: `REFUTED` requires negative results log
- C6: `PROHIBITED` requires absence from external material
- C7: `HYPOTHESIS` requires isolation from production

**Release Gate:**
- G1: Release fails if any `VERIFIED` claim fails reproduction
- G2: Release fails if any `PROHIBITED` claim appears in external material
- G3: Release fails if any promoted claim lacks evidence pack
- G4: Release fails if any `REFUTED` claim is reintroduced without new evidence

**Failure:**
- F1: Claim fails reproduction → block release
- F2: Prohibited claim found → block release
- F3: Evidence pack missing → block release

---

### 12.9 Pairings ↔ Architecture

**Producer:** Pairing policy
**Consumer:** Architecture admission
**Transport:** `pairings.yaml`

**VERIFIED_PAIRINGS:**
- fibonacci ↔ cassini
- fibonacci ↔ lucas
- fibonacci ↔ zeckendorf
- binet ↔ exact_fibonacci_lucas
- pisot ↔ lucas
- q_matrix ↔ fibonacci_lucas_cassini
- m32 ↔ graph_laplacian
- m32 ↔ (H = L + V)
- m32_engine ↔ cassini_zeckendorf_seals
- quantum_core ↔ substrate_agnostic_backends

**PROHIBITED_PAIRINGS:**
- lucas_pisot_quantum_speedup
- prime_addressing_as_physical_capacity
- universal_binet_compression
- spectral_gap_as_binding_energy
- metallic_ratios_as_zero_resonance
- unvalidated_packing_forecasting_turbine_docking

**REFUTED_RESULTS:**
- zeckendorf_reduces_generic_address_bits
- float64_binet_lossless_storage
- lucas_pisot_phase_quantum_speedup
- global_phase_changes_probabilities
- plastic_identity_rho5_equals_rho2_plus_1
- spectral_gap_proves_drug_binding_affinity

**Contract:**
- C1: New pairing requires `VERIFIED` status
- C2: New pairing requires `PairingTest` record
- C3: New pairing requires matched baseline
- C4: New pairing requires reproducibility command
- C5: `REFUTED` pairings removed or redesigned
- C6: `HYPOTHESIS` pairings isolated in experiments

**Failure:**
- F1: Unverified pairing enters architecture → block
- F2: Refuted pairing reintroduced → block
- F3: Pairing test missing → block

---

### 12.10 Deployment ↔ Platform

**Producer:** Deployment compiler
**Consumer:** Platform services
**Transport:** Signed manifests

**Contract:**
- C1: One manifest describes the whole platform
- C2: Manifest is signed
- C3: Manifest is versioned
- C4: Manifest is reproducible
- C5: Deployment compiles from manifest, not from hand-config
- C6: Every service registers with the canonical object model
- C7: Every service uses the canonical policy engine
- C8: Every service uses the canonical lineage store
- C9: No service creates a disconnected identity/policy/lineage/vector/scheduler

**Profiles:**
`developer | edge | enterprise | sovereign | hyperscaler | regulated | classified`

**Failure:**
- F1: Manifest invalid → reject with reason
- F2: Service violates canonical contract → reject
- F3: Disconnected subsystem detected → reject
- F4: Unattested backend required → fail closed

---

### 12.11 Security ↔ Object

**Producer:** Security plane
**Consumer:** Every object
**Transport:** `PolicyContext`

**Fold-Aware Permissions:**
```
separate_permissions_for:
    exact_state
    folded_state
    residual
    projection
    proof
    reconstruction
    training
    execution
    export
```

**Contract:**
- C1: Policy travels with object
- C2: Moving object does not detach policy
- C3: Moving object does not change residency
- C4: Moving object does not change retention
- C5: Operator may be allowed while raw retrieval denied
- C6: Proof metadata may be auditable without payload reveal
- C7: Model training may consume projection without exact source
- C8: Every unfold/projection/export/translation logged

**Failure:**
- F1: Policy detached → reject
- F2: Residency violated → reject
- F3: Unauthorized reconstruction → reject
- F4: Unlogged translation → reject

---

### 12.12 Evidence ↔ Compliance

**Producer:** Evidence plane
**Consumer:** Compliance / audit
**Transport:** `EvidenceObject` + `AssurancePack`

**Contract:**
- C1: Every control has a machine-enforced policy
- C2: Every control produces continuous evidence
- C3: Every evidence pack is independently verifiable
- C4: Every mapping is labelled enablement, not certification
- C5: Every AI system has inventory, impact assessment, model card, data card
- C6: Every human approval is recorded
- C7: Every legal hold is immutability-enforced
- C8: Every retention policy is enforced, not documented

**Failure:**
- F1: Control unmapped → gap report
- F2: Evidence unverifiable → reject
- F3: Certification claim → reject
- F4: Retention violation → reject

---

### 12.13 Observability ↔ Everything

**Producer:** Every module
**Consumer:** Observability plane
**Transport:** Structured events + metrics + traces + proofs

**Contract:**
- C1: Every module emits structured events
- C2: Every module emits metrics
- C3: Every module emits traces
- C4: Every module emits proof state
- C5: Every module emits backend identity
- C6: Every module emits movement ledger
- C7: Every module emits policy context
- C8: Observability is off the critical path
- C9: Observability does not block execution
- C10: Observability can be replayed

**Failure:**
- F1: Observability blocks execution → reject
- F2: Observability on critical path → reject
- F3: Telemetry not replayable → reject

---

### 12.14 Upgrade ↔ Recovery

**Producer:** Upgrade orchestrator
**Consumer:** Recovery plane
**Transport:** Release unit

**Release Unit:**
```
model
features
data_snapshot
indexes
policy
runtime
evidence
```

**Contract:**
- C1: Release unit promotes as one
- C2: Release unit rolls back as one
- C3: Rollback restores objects, policies, proofs, models, lineage
- C4: Upgrade is staged → tested → switched → verified → committed
- C5: Rollback is rehearsed before production
- C6: Recovered release retains everything

**Failure:**
- F1: Partial promotion → rollback
- F2: Verification fail → rollback
- F3: Recovered state missing evidence → reject

---

## 13. Prohibited Connections

These connections **MUST NOT** exist. A linter should scan for all twenty.

| ID | Prohibited Connection |
|----|----------------------|
| X1 | Any path that silently rehydrates |
| X2 | Any path that silently approximates |
| X3 | Any path that silently falls back |
| X4 | Any path that silently moves residency |
| X5 | Any path that silently changes exactness |
| X6 | Any path that submits invalid external proof |
| X7 | Any path that claims quantum advantage without device |
| X8 | Any path that describes simulator as hardware |
| X9 | Any path that describes reference as silicon |
| X10 | Any path that claims unlimited capacity |
| X11 | Any path that claims unlimited speed |
| X12 | Any path that claims compliance as certification |
| X13 | Any path that claims institutional affiliation |
| X14 | Any path that promotes unverified pairing |
| X15 | Any path that reintroduces refuted result |
| X16 | Any path that bypasses invariant check |
| X17 | Any path that disables audit |
| X18 | Any path that crosses sovereignty without authority |
| X19 | Any path that treats simulation as physical evidence |
| X20 | Any path that removes human oversight on high-risk action |

**Assertion:** Every prohibited connection is absent.

---

## 14. Failure Taxonomy

Every failure in the system maps to exactly one of six classes. No failure is silent.

### Class A — Reject at Planning

Fail early. Never partial. Never silent.

| ID | Failure |
|----|---------|
| A1 | `unknown_capability` |
| A2 | `incompatible_modules` |
| A3 | `silent_fallback_requested` |
| A4 | `operator_not_allowed` |
| A5 | `exactness_not_allowed` |
| A6 | `residency_violation` |
| A7 | `budget_exceeded` |
| A8 | `unsupported_semantics` |
| A9 | `fold_family_mismatch` |
| A10 | `backend_lacks_capability` |

### Class B — Fail Closed

Never approximate. Never substitute.

| ID | Failure |
|----|---------|
| B1 | `required_attestation_absent` |
| B2 | `required_hardware_absent` |
| B3 | `required_precision_unsupported` |
| B4 | `fallback_prohibited_but_required` |
| B5 | `quantum_device_absent` |
| B6 | `overflow_in_exact_arithmetic` |
| B7 | `unsupported_hamiltonian` |

### Class C — Quarantine

Never silently return corrupted data.

| ID | Failure |
|----|---------|
| C1 | `invariant_check_failed` |
| C2 | `hash_mismatch` |
| C3 | `corruption_detected` |
| C4 | `cassini_seal_failed` |
| C5 | `zeckendorf_invalid` |

### Class D — Retry

Transient conditions.

| ID | Failure |
|----|---------|
| D1 | `torn_read` |
| D2 | `stale_snapshot` |
| D3 | `sequence_changed` |
| D4 | `cursor_publication_fail` |

### Class E — Degrade (Marked)

Fallback only when allowed and marked.

| ID | Failure |
|----|---------|
| E1 | CPU fallback when allowed |
| E2 | Host GPU absent when optional |
| E3 | Lane floor reached |

### Class F — Backpressure

Never silent loss.

| ID | Failure |
|----|---------|
| F1 | Ring full → spill |
| F2 | Spill full → catastrophic backpressure |

**Assertions:**
- Every failure maps to exactly one class
- Every failure is logged
- No failure is silent

---

## 15. Compatibility Matrix

| Component | v1 | v2 | v3 | v4 |
|-----------|----|----|----|----|
| Object schema | ✓ | ✓ | ✓ | ✓ |
| FoldContract | ✓ | ✓ | ✓ | ✓ |
| OperatorContract | ✓ | ✓ | ✓ | ✓ |
| HotDescriptor | ✓ | ✓ | ✓ | ✓ |
| Telemetry ABI | ✓ | ✓ | ✓ | ✓ |
| AssemblyLock | - | ✓ | ✓ | ✓ |
| EvidenceObject | - | - | ✓ | ✓ |
| BackendCertificate | - | - | ✓ | ✓ |
| PolicyContext | - | - | ✓ | ✓ |

**Rule:** Breaking change requires major version bump + migration path.

---

## 16. Contract Test Suite

Every contract in this document maps to a set of runnable tests. The suite is organised by contract ID.

### C1 Tests — Intent Manifest
- T1: Valid manifest compiles
- T2: Invalid manifest rejected with reason
- T3: Silent fallback request rejected
- T4: Missing residency rejected

### C2 Tests — Assembly → Policy
- T1: Assembly lock is immutable
- T2: Policy derived from lock, not invented
- T3: Policy cannot weaken invariant

### C3 Tests — Policy → Query
- T1: Unauthorized operator rejected at planning
- T2: Unauthorized exactness rejected at planning
- T3: Budget enforced before execution

### C4 Tests — Query → PRIME-DB
- T1: Operator mode matches contract
- T2: Fold family matches contract
- T3: Fallback marked when permitted
- T4: No silent rehydration

### C5 Tests — PRIME-DB → Registry
- T1: Object carries fold contract version
- T2: Object carries policy context
- T3: Capability negotiation correct
- T4: No backend selected that violates exactness

### C6 Tests — Backend Selection
- T1: CPU exact is bit-exact with Python reference
- T2: MLA1517 primary when connected
- T3: Host GPU never impersonates MLA1517
- T4: FPGA ROM boundary respected
- T5: Quantum fail closed on device absence

### C7 Tests — Result Receipt
- T1: Every result carries backend identity
- T2: Every rehydration recorded
- T3: Every fallback marked
- T4: Result hash reproducible

### C8 Tests — Proof + Evidence
- T1: Evidence independently verifiable
- T2: Replay without MLA1517
- T3: Signature valid

### C9 Tests — Commit
- T1: Multi-object commit atomic
- T2: Cursor total matches count
- T3: Crash during commit recoverable
- T4: Torn write rejected
- T5: Corruption quarantined

### C10 Tests — Observability
- T1: Telemetry seqlock consistent
- T2: C snapshot matches Python offsets
- T3: Telemetry replayable

### Foundational Contract Tests
- PRIME-DB ↔ MLA1517: same object from persistence to execution
- Fold ↔ Operator: every mode declared, invariants preserved
- M32 ↔ Transport: cross-process, no torn reads, backpressure before loss
- SIMT ↔ Aethel: ballot correct, prefix rank correct, no divergence
- Salamander: observe-only default, ACK enforced, lane floor enforced
- Agentic: no generated trajectories, SupportViolation raised, safe action on no support
- Quantum: rational coordinates only, no floats, AcceleratorUnavailable on absence
- Claims: VERIFIED requires passing test, PROHIBITED absent from external
- Pairings: new pairing requires VERIFIED, prohibited blocked
- Deployment: manifest signed, no disconnected subsystem
- Security: policy travels with object, fold-aware permissions separate
- Evidence: control has machine-enforced policy, pack independently verifiable
- Observability: off critical path, replayable
- Upgrade: release unit promotes as one, rollback restores everything
- Prohibited: every prohibited connection absent

**Total: ~120 contract tests.**

---

## 17. Summary Card

```
┌──────────────────────────────────────────────────────────────┐
│  EVERY CONNECTION IN HYBA / MLA1517 + PRIME-DB               │
├──────────────────────────────────────────────────────────────┤
│  C1   User → Assembly Compiler       : IntentManifest        │
│  C2   Assembly → Policy              : AssemblyLock          │
│  C3   Policy → Query Planner         : AuthorizedQuery       │
│  C4   Query Planner → PRIME-DB       : ExecutionPlan         │
│  C5   PRIME-DB → Backend Registry    : CapabilityRequest     │
│  C6a  Registry → CPU Exact           : ExecutionPlan         │
│  C6b  Registry → MLA1517 GPU/iGPU    : HotDescriptor         │
│  C6c  Registry → Host GPU Overlay    : HostGPUPlan           │
│  C6d  Registry → FPGA                : ROM contract          │
│  C6e  Registry → Quantum Exact       : ExactQuantumState     │
│  C7   Backend → Result Receipt       : ResultReceipt         │
│  C8   Result → Proof + Evidence      : EvidenceObject        │
│  C9   Evidence → PRIME-DB Commit     : Transaction           │
│  C10  Commit → Observability         : TelemetrySnapshot     │
├──────────────────────────────────────────────────────────────┤
│  FOUNDATIONAL BIDIRECTIONAL CONTRACTS:                       │
│  PRIME-DB ↔ MLA1517      : HotDescriptor + Fold/Operator     │
│  FOLD ↔ OPERATOR         : FoldContract + OperatorContract   │
│  M32 ↔ TRANSPORT         : 64-byte ring                      │
│  SIMT ↔ AETHEL UMA       : winning-lane descriptors          │
│  SALAMANDER ↔ EXECUTION  : MMIO CSR + COMMIT_ACK             │
│  AGENTIC ↔ SALAMANDER    : ProposedAction + veto             │
│  QUANTUM ↔ EVERYTHING    : ExactQuantumState + fail-closed   │
│  CLAIMS ↔ RELEASE GATE   : claims.yaml                       │
│  PAIRINGS ↔ ARCHITECTURE : pairings.yaml                     │
│  DEPLOYMENT ↔ PLATFORM   : signed manifests                  │
│  SECURITY ↔ OBJECT       : PolicyContext                     │
│  EVIDENCE ↔ COMPLIANCE   : EvidenceObject + AssurancePack    │
│  OBSERVABILITY ↔ ALL     : events + metrics + traces         │
│  UPGRADE ↔ RECOVERY      : release unit                      │
├──────────────────────────────────────────────────────────────┤
│  PROHIBITED CONNECTIONS: 20 (X1–X20)                         │
│  FAILURE CLASSES: 6 (A–F)                                    │
│  CONTRACT TESTS: ~120                                        │
└──────────────────────────────────────────────────────────────┘
```

---

## Doctrine (Restated)

> **Every connection is a contract. Every contract has a producer, a consumer, a schema, an invariant, a failure mode, and a proof. Nothing crosses a boundary silently.**

---

**End of CONTRACTS.md**

---

*This document is canonical. Every engineer, auditor, and design partner should read it before touching the platform. Every CI pipeline should enforce it. Every release should verify it.*

*When a contract changes, this document changes. When this document changes, every downstream test changes. Nothing is implicit.*