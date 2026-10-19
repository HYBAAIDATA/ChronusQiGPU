# MINING REWIRE MAP — Intelligence-Front-and-Centre
**Document Version:** 1.0.0-canonical  
**Date:** 2026-10-19  
**Branch:** `feat/mining-intelligence-rewire-20261019`  
**Classification:** Foundational Architecture & Execution Plan  
**Governing Documents:** [`OWNER_DECLARATIONS.md`](./OWNER_DECLARATIONS.md), [`UNIVERSAL_PRINCIPLE_MAP.md`](./UNIVERSAL_PRINCIPLE_MAP.md), [`AGENTS.md`](./AGENTS.md)

---

## 1. Executive Summary & Governing Axioms

This document establishes the canonical blueprint for rewiring the mining architecture of `PhiEnterprise-main`. The legacy design placed classical execution and brute-force nonce looping at the foundation, treating intelligence as an optional advisory wrapper. This rewire inverts the hierarchy:

$$\mathbf{Intelligence\ Plane\ (TOE\ +\ Kellogg\ +\ Turing)} \longrightarrow \mathbf{Superposition\ (N=8)} \longrightarrow \mathbf{Collapse} \longrightarrow \mathbf{Chronus\ Actuator} \longrightarrow \mathbf{Salamander\ Healing} \longrightarrow \mathbf{Pythia\ Truth}$$

### Non-Negotiable Operational Principles
1. **Consensus Truth is Inviolable:** 80-byte header, double-SHA256 ($H \le T$), target comparison, and literal Stratum pool acceptance (`mining.submit` $\to$ `true`) are the sole sources of validation. Search topology and geometry provide algorithmic ordering, never proof authority.
2. **Route Honesty:** CPU and emulator executions are never reported as physical device execution. Every `ExecutionRecord` must explicitly record `{requested_route, executed_route, fallback_reason, device_id, host_recheck_pass}`. `silicon_status() != PASS` mandates `hashrate = NOT_RUN`.
3. **Authority Boundary:** In accordance with [`toe/intelligences/authority_boundary.py`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/toe/intelligences/authority_boundary.py), EUCLID advises `SearchPlan`, but PYTHIA exclusively owns finalisation, nonce-estate coverage, SHA256d verification, and share submission.
4. **Classical Path Quarantine:** The legacy classical mining library in `mining/` is deprecated and moved to `legacy_mining_classical_quarantined_<hash>/` with a fail-closed import shim ("use Kellogg route"). It is never silently deleted (`rm -rf` forbidden).
5. **Canonical Kellogg Tensor:** Consolidated high-dimensional joint state $\mathcal{T} \in \mathbb{C}^{\text{futures} \times \text{lanes} \times \text{nonces}}$ with exact bijection coverage proofs (zero overlap) over leased windows.

---

## 2. Current Classical Path Audit (Files & Lines)

The existing repository retains several legacy classical mining paths that treat nonce searching as sequential or flat random sampling, or wrap classical loops in superficial quantum labels:

| Module / File Path | Line Range | Current Classical Behavior | Deprecation & Migration Path |
| :--- | :--- | :--- | :--- |
| `mining/scaled_execution.py` | L1–L60, L36–L38 | Declares `_EXECUTION_MODE = "structured_classical"` and delegates to `FourLayerMiningStack.mine`. Classical loop over nonces. | Quarantine to legacy; replace execution engine with Kellogg tensor state and Chronus actuator. |
| `mining/four_layer_stack.py` | L1–L35, L145–L210 | Layer 4 executes classical double-SHA256 brute-force loop over CPU/iGPU array (`FourLayerMiningStack.mine()`). | Quarantine to legacy; replace with canonical tensor superposition hold and Chronus resident dispatch. |
| `mining/search.py` | L1–L15, L60–L140, L150–L250 | `GroverStyleSearch` implements classical walk on 2-node graph; `PreimageSearch` performs sequential linear nonce scanning. | Quarantine to legacy; replace with Kellogg/Hendrix coprime bijection ($gcd(s, W) = 1$). |
| `mining/nonce_scheduler.py` | L1–L120 | `NonceScheduler` provides basic sequential and stride offsets without exact coverage or tensor state. | Quarantine to legacy; supersede by `kellogg.traversal` and `chronus.mla1517.mining.hendrix_order`. |
| `mining/hash_pipeline.py` | L1–L180 | Classical CPU double-SHA256 pipeline loop. | Quarantine to legacy; preserve SHA256d reference verifier as host recheck oracle only. |
| `mining/bitcoin_hasher.py` | L1–L150 | `BitcoinHasher` implements scalar CPU loop without tensor representation. | Quarantine to legacy. Host verification is handled by `chronus/mla1517/mining/execution_router.py`. |
| `mining/stratum_bridge.py` | L1–L250 | Legacy Stratum bridge with flat lane allocation (`_lane_nonces`). | Quarantine to legacy; canonical Stratum transport resides in `chronus/mla1517/mining/production_transport.py`. |
| `mining/deterministic_hashrate.py` | L1–L180 | Deterministic hashrate estimation using classical timing models. | Quarantine to legacy; replace with measured telemetry and execution receipts. |
| `mining/difficulty.py` | L1–L150 | Classical difficulty calculation and target conversion. | Quarantine to legacy; canonical compact target resides in `chronus/mla1517/mining/pow.py`. |
| `mining/fault_tolerant_asic.py` | L1–L200 | Theoretical transmon/surface-code ASIC simulation model. | Quarantine to legacy; substrate-agnostic exact algebra resides in `kellogg/` and `turing_universal_quantum_computer/`. |
| `mining/thermodynamics_exact.py` | L1–L160 | Landauer limit and thermal dissipation calculator. | Quarantine to legacy; runtime thermal monitoring managed via Salamander and Plastic Intelligence. |
| `python_backend/pythia_mining/search_lane_descriptor.py` | L25–L48 | Reports `mode: "exhaustive_scan"` or `quantum: {"execution_type": "classical_simulation"}`. | Quarantine/shim; bind to canonical `SearchPlan` and `ExecutionRecord` telemetry. |
| `chronus/mla1517/mining/execution_router.py` | L87–L98, L800–L880 | `NONCE_ORDER_SEQUENTIAL` and CPU fallback `sha256d_scan` flat loops. | Deprecate sequential mode; enforce Hendrix/M32/Poincaré-11D bijections with 100% host recheck. |
| `chronus/mla1517/mining/solver.py` | L1–L200 | `M32SearchSolver` legacy sweep. | Replace with canonical Kellogg tensor collapse to `SearchPlan`. |

---

## 3. Kellogg Canonical Tensor State Architecture

### 3.1 Consolidation & Single Canonical Entrypoint
Currently, tensor operations are split across `kellogg/` (exact algebraic field arithmetic over $Q(\sqrt{2})$ and $Z[\phi]$) and `tensor/` (hybrid engine, router, and pulvini bridges).
- **Canonical Tensor Module:** `kellogg.canonical_tensor` (or consolidated `kellogg/` entrypoint) will serve as the single source of truth for high-dimensional state representation.
- **`tensor/` Directory:** Maintained as an import shim and client bridge, re-exporting canonical symbols from `kellogg`.
- **Representation Logging:** Every run logs its representation choice (`ExactStateVector` over $Q(\sqrt{2}) + i Q(\sqrt{2})$, $Z[\phi]$ ring, or canonical complex amplitude vector).

### 3.2 High-Dimensional Superposition Tensor Slices
The state space is represented algebraically as a joint tensor:
$$\mathcal{T} \in \mathcal{H}_{\text{futures}} \otimes \mathcal{H}_{\text{lanes}} \otimes \mathcal{H}_{\text{nonces}}$$
- $\dim(\mathcal{H}_{\text{futures}}) = N = 8$: Superposition over future chain states (next job variants, difficulty adjustments, reorg branches, stale risks).
- $\dim(\mathcal{H}_{\text{lanes}}) = 32$: M32 / 32-face frame ($20 \text{ icosahedral} + 12 \text{ dodecahedral normals}$).
- $\dim(\mathcal{H}_{\text{nonces}}) = W$: Leased nonce window size.

### 3.3 Exact Coverage Proof (Bijection & Zero Overlap)
Every nonce in the leased window $[N_{\text{base}}, N_{\text{base}} + W)$ must be visited **exactly once**:
$$\pi(i) = N_{\text{base}} + (i \cdot s) \pmod W, \quad \text{for } i \in \{0, 1, \dots, W-1\}$$
- **Coprime Stride Condition:** $\gcd(s, W) = 1$ ensures that the mapping $\pi: \mathbb{Z}_W \to \mathbb{Z}_W$ is an exact group automorphism (bijection).
- **Zero Overlap:**
  $$\forall i \ne j \in \{0, \dots, W-1\}, \quad \pi(i) \ne \pi(j)$$
- **32-Face Frame Invariant:** In `kellogg/traversal.py`, $\text{TRAVERSAL\_STRIDE} = F_5 = 5$. Since $\gcd(5, 32) = 1$, every 32-step cycle traverses all 32 faces with zero duplication.

---

## 4. TOE Intelligence Plane Wiring (§2 Integration)

In accordance with §2 of the mandate, the 5 canonical intelligences + 1 quantum extension (TURING) are wired explicitly into each pipeline stage:

```
STRATUM LIVE (job, difficulty, extranonce)
  └─ Predictive: forecast stale-lease / next-difficulty / churn (literal evidence) → P(state)
AGENTIC PRECOMPUTE (intelligence front door)
  ├─ Predictive: P(future job set) for N=8 futures → tensor slices
  ├─ Causal: attribute job features → expected accept (middleware/lease/transport causes)
  ├─ Counterfactual: "if lease X had run, would share have been stale?" → prune futures, regret log
  ├─ Topological: kappa per future (trauma from prior stale/reject) → damp bad futures (exp(-I/(10*(2-c))))
  ├─ Geometric: order lanes via Hendrix/golden-stride/Lucas bijection → SearchPlan candidates + coverage proof
  └─ Quantum-ext (TURING): Hadamard-coin walk over futures to reweight (NUMERICAL vs exact)
SUPERPOSITION HOLD (Kellogg tensor [futures × lanes × nonces])
  └─ hold all 8 with probabilities, LRU eviction, persisted to aethel
COLLAPSE → SearchPlan (single plan with reason + alternatives log)
CHRONUS EXECUTE (requested/executed route + host SHA256d recheck 100%)
PYTHIA TRUTH (submit → literal pool outcome → ONLY reward source)
SALAMANDER (heal stale/IDENTITY_MISMATCH/invalidated, optimise breadth within PYTHIA bounds)
LEARN (update Predictive/Causal from literal pool outcomes → next precompute)
```

### Stage Telemetry Contract
Every stage execution logs the structured tuple:
```python
{
    "stage": "<stage_name>",
    "intelligence_used": "<predictive|causal|counterfactual|topological|geometric|quantum_ext>",
    "input_hash": "<sha256_of_inputs>",
    "output_hash": "<sha256_of_outputs>",
    "confidence": float,      # Bounded [0.0, 1.0], derived strictly from measured evidence
    "entropy_delta": float,   # Information gain across the stage transformation
    "kappa": float,           # Topological trauma / stability metric
}
```
**Mandate:** If any stage lacks its intelligence log, the run is flagged as `INCOMPLETE`, never `PASS`.

---

## 5. Salamander Autonomic Recovery vs. Optimisation

### 5.1 Core Principle: Healer Outranks Optimiser
Recovery actions take absolute precedence over dispatch expansion, breadth scaling, or candidate throughput. If any degradation or fault is detected, the optimiser is throttled or suspended until the healer verifies complete recovery.

### 5.2 Six-Step Closed-Loop Execution
$$\mathbf{Observe} \longrightarrow \mathbf{Classify} \longrightarrow \mathbf{Bounded\ Action} \longrightarrow \mathbf{Actuator\ Ack} \longrightarrow \mathbf{Post\ Observe} \longrightarrow \mathbf{Verified\ Recovery} \longrightarrow \mathbf{Resume}$$

1. **Observe:** Ingest live runtime telemetry and Stratum client state.
2. **Classify:** Map issue to `FaultClass` (`TRANSIENT`, `RECOVERABLE_DEGRADATION`, `HARD_FAILURE`).
3. **Bounded Action:** Issue restricted command from `_SAFE_MINING_COMMANDS` (`FLUSH_LANE`, `SEVER_LANE`, `RESTART_LANE`, `RESET_CURSOR`, `APPLY_BACKPRESSURE`).
4. **Actuator Ack:** Wait for coordinator confirmation of execution.
5. **Post Observe:** Re-poll subsystem telemetry.
6. **Verified Recovery:** Verify against `DurableEvidenceLedger` head.
7. **Resume:** Unblock work generation and resume search.

---

## 6. Deep Dive: `IDENTITY_MISMATCH` Handling Today vs. Target

### 6.1 Current Behavior in Code
In [`chronus/mla1517/mining/coordinator.py`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/chronus/mla1517/mining/coordinator.py#L1234-L1238):
```python
# Lines 1234-1238 in _resolve_work_identity()
if (
    adapter.current_job.job_id != generation.job_id
    or adapter.current_job.target != generation.target
):
    return None, "IDENTITY_MISMATCH"
```
And in `_refresh_work_identity()` (Lines 1253–1265):
```python
identity, reason = self._resolve_work_identity()
if identity is None:
    ...
    self.agentic.clear_work(reason or "NO_WORK_IDENTITY")
    return None
```

### 6.2 The Defect / Gap Today
- **Passive Drop:** When `adapter.current_job` desynchronizes from `state.current_job` (e.g. during rapid Stratum `mining.notify` clean-job bursts or retarget transitions), the coordinator simply logs `clear_work("IDENTITY_MISMATCH")` and returns `None`.
- **No Healing:** No recovery action is queued. Salamander is not notified. The miner spins idly or wastes cycles until the next notify packet arrives.
- **No Audit Trail:** No `ExecutionRecord` is recorded for the dropped generation, creating an unobserved gap in the decision journal.

### 6.3 Target Salamander Healing Architecture for `IDENTITY_MISMATCH`
1. **Diagnosis:** `SalamanderRuntimeBridge` classifies `IDENTITY_MISMATCH` as `FaultClass.RECOVERABLE_DEGRADATION` with root cause `PROOF_ADAPTER_JOB_DESYNC`.
2. **Bounded Action:** Issue `RESET_CURSOR` / `FLUSH_LANE` with parameters specifying the active Stratum `generation.job_id` and `target`.
3. **Reconciliation:** Force synchronous reconciliation of `adapter.current_job` to match the canonical `generation` state.
4. **Telemetry & Ledger:** Emit an explicit `ExecutionRecord` logging:
   `{healed_fault: "IDENTITY_MISMATCH", prior_state: {"adapter_job": adapter.current_job.job_id, "generation_job": generation.job_id}, resolved_job: generation.job_id}`
5. **Resumption:** Once reconciled, re-trigger `_refresh_work_identity()` immediately, restoring search without waiting for an external pool event.

---

## 7. Stage-by-Stage Wire Matrix Table

| Stage | Current Code & Lines | Kellogg / TOE Target | Gap Status |
| :--- | :--- | :--- | :--- |
| **1. Stratum Live Ingestion** | `chronus/mla1517/mining/production_transport.py:65–170`, `stratum_adapter.py:50–120` | Predictive intelligence calculates $P(\text{stale}), P(\text{next\_diff}), P(\text{churn})$ from empirical pool window | **PARTIAL** (Stratum connects; predictive forecasting from literal pool outcomes is missing) |
| **2. Agentic Precompute** | `chronus/mla1517/mining/exact_search.py:1–80`, `pythia_agentic_cycle.py:100–180` | Hold $N=8$ futures in superposition; Causal + Counterfactual + Topological + Geometric + TURING quantum-ext scoring | **PARTIAL** (Static 32 $\to$ 11D $\to$ 600 exists; 8-future superposition & 5-lens scoring missing) |
| **3. Superposition Hold** | `Intelligence/agentic_mining.py:13–18` (research only); none in production coordinator | Canonical Kellogg tensor $[\text{futures} \times \text{lanes} \times \text{nonces}]$ with LRU cache, bounded in aethel memory | **MISSING** in production (Superposition only existed as simulation contract) |
| **4. Collapse to SearchPlan** | `chronus/mla1517/mining/coordinator.py:340–350` (`_build_plan`) | Deterministic collapse of superposition tensor to single `SearchPlan` with logged reason and rejected alternative profiles | **PARTIAL** (Single plan built; selection among superposed futures missing) |
| **5. Chronus Execution** | `chronus/mla1517/mining/execution_router.py:1–100, 350–500` | Chronus resident batch execution with strict route logging (`requested` vs `executed`), device verification, and 100% host SHA256d recheck | **WIRED** (ExecutionRouter enforces route honesty and host recheck) |
| **6. Pythia Final Truth** | `chronus/mla1517/mining/geodesic_support.py:362–420`, `production_transport.py:200–260` | Literal pool response (`ACCEPTED`/`REJECTED`/`STALE`) is sole reward source; updates Causal/Loss ledgers | **WIRED** (Strict pool truth verification intact) |
| **7. Salamander Healing & Optimisation** | `salamander/runtime.py:231–305`, `chronus/mla1517/mining/self_healing_agent.py:107–200` | Healer outranks optimiser. Closed loop: observe $\to$ classify $\to$ action $\to$ ack $\to$ post-observe $\to$ verified recovery. Active healing for `IDENTITY_MISMATCH` | **PARTIAL** (Basic failure classes wired; `IDENTITY_MISMATCH` auto-reconciliation missing) |
| **8. Learning Feedback** | `chronus/mla1517/mining/causal.py:50–120`, `learning.py:40–100` | Update Predictive transition probabilities and Causal SCM edge weights from literal pool outcomes for next precompute | **PARTIAL** (Causal ledger records events; automated feedback into precompute futures missing) |
| **Classical Path Quarantine** | `mining/*.py` active in tree and imported by several test suites | `git mv mining/` to `legacy_mining_classical_quarantined_<hash>/` + fail-closed shims ("use Kellogg route") | **MISSING** (Quarantine scheduled for Phase P2) |

---

## 8. Implementation Roadmap (Phases P2–P6)

- **Phase P2 — Quarantine Classical Path:**
  - Execute `git mv mining/ legacy_mining_classical_quarantined_<commit_hash>/`.
  - Place `mining/DEPRECATED.md` and create `mining/__init__.py` fail-closed import shim raising `ImportError("use Kellogg route")`.
  - Verify that `pytest --collect-only` passes across the repository.
  - Verify control API boot and braiins shadow pool connection.
- **Phase P3 — Kellogg Canonical Tensor State:**
  - Consolidate tensor operations into single canonical module.
  - Implement `SearchPlan` builder with mathematical coverage proof (bijection over leased window, zero overlap).
  - Add unit tests verifying bijection, zero-overlap, and host recheck.
- **Phase P4 — TOE Wiring (§2 Implementation):**
  - Wire 5 intelligences + TURING quantum-ext into pipeline stages with mandatory telemetry logging.
  - Implement $N=8$ superposition hold with LRU eviction and collapse reason logging.
  - Enforce stage logging contract `{intelligence_used, input_hash, output_hash, confidence, entropy_delta, kappa}`.
- **Phase P5 — Salamander Autonomic Closure:**
  - Wire closed-loop healer > optimiser supervisor.
  - Implement active reconciliation for `IDENTITY_MISMATCH` and stale jobs.
  - Run 10-minute soak test against live Braiins pool jobs (without live submit).
- **Phase P6 — Formal Proof & Verification:**
  - Run pytest across mining/lease/router test suites and new `tests/euclid_arena/test_14_geometric.py` (G1–G3).
  - Compile `MINING_INTELLIGENCE_RELEASE.md` with measured numbers, SHA256 hashes, and explicit limits.

---
*Signed and sealed by Principal Mining-Intelligence Engineer on branch `feat/mining-intelligence-rewire-20261019`.*
