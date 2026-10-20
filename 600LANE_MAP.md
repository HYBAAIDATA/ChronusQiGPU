# 600-Lane Solving Machine Architecture & Production Readiness Completion Map (600LANE_MAP.md)

**Branch:** `cto/rewire600-p1-proof-map-20261020`

> **P1-only reconciliation, 2026-10-20.** Source baseline `2bc45bd4f9c45a29fea00aa1f6ed34222ed58f07`. This is a blueprint and source inspection, not current test/production proof. P2/P3 DONE statements below were inherited; current execution has not been reverified. The proof requirements in Section 0 control acceptance.  
**Governing Documents:** [`OWNER_DECLARATIONS.md`](./OWNER_DECLARATIONS.md), [`UNIVERSAL_PRINCIPLE_MAP.md`](./UNIVERSAL_PRINCIPLE_MAP.md), [`AGENTS.md`](./AGENTS.md)  
**Doctrine:** SOLVE (represent + prune + prove) not SEARCH (blind probe). SHA256d ≤ target inviolable. CPU/emulator never reported as device.  
**Baseline State:** 21:09 boot (chronus lane, Virtual iGPU cpu-emulator known-answer PASS, braiins Auth:true jobs 00-06, 780 journals, 28 modules/14 live, 19 skills, M3 tenant). Preserve. Break nothing.  
**Definition of DONE:** 600 lanes proven complete/disjoint + recheck 100% + per-lane 5+1 logs + arsenal clamped + 10-min soak on Braiins jobs + release MD with MEASURED numbers only.

---

## 0. P1 evidence scope and required closure

### 0.1 Source findings versus targets

- **Micro-tether:** `euclid/sovereign/micro_tether.py` contains mapping, HMAC receipts, local reflex records and a cost-delta calculator, not a GPU kernel/hasher. Treat it as a child security/economic adapter; execution requests must use existing Chronus authority. `system_fabric.py:32-45` is now the end of its docstring and imports, not a child-adapter binding. The inspected fabric source has no `micro_tether` registration. Therefore **architectural disposition is resolved; live fabric binding remains unproven**, not WIRED by implication. The seal is software HMAC, not independent SGX/Nitro hardware attestation; deleting a Python reference is not proof of memory zeroization. No claim of PII privacy, legal compliance, secure TEE or measured sub-millisecond reflex follows from those labels.
- **Hendrix clamp:** `quantum_compute_substrate/amplitude_amplification.py` retains declared space separately from capped simulation dimension, capped at `2**20`. Its ratio is an oracle-query ratio, not measured device throughput or wall-clock speedup. Boundary tests must cover both sides of the cap and label simulated versus executed dimensions. Do not infer repository-wide enforcement from one file.
- **Kellogg:** `kellogg/mother_tensor.py` is the existing canonical state, not a module to create again. Keep re-exports identity-preserving. Its shape uses `len(futures)` with a maximum of 8 (default 1), not always 8. Critically, `build_search_plan()` currently emits `lane_order=tuple(range(32))`, `dispatch_breadth=min(32, self.lanes)`: **600-lane metadata is not proof of 600-lane dispatch**. Record this as an integration gap for later owner-authorised phases; P1 changes no runtime.
- **Method separation:** Mother-tensor `phi_method` checks the golden-ratio algebraic identity. That is not the cross-layer integrated-information capital-Phi method in SPRINT1 Section 1. Neither test substitutes for the other.

### 0.2 600-position bijection proof target

A logical 600-position execution fabric is not a claim that a geometric 600-cell has 600 vertices or that 600 physical devices exist. Prove the concrete mapping, not a count inferred from 20+12 or from an embedding dimension.

For a leased half-open interval W=[a,a+n), require exactly 600 labelled lanes and a vertex-to-lane bijection on IDs 0..599. Require each W_i to be a subset of W, union_i W_i=W, and **pairwise** W_i intersect W_j=empty for every i!=j, including internal duplicate rejection. A global intersection over all lanes being empty is insufficient: two lanes can overlap while the global intersection is empty. Cardinality equality alone also cannot prove coverage.

For a deterministic interval-partition reference, n=600q+r with 0<=r<600 gives sizes q+1 for the first r lanes and q for the rest; this specifies a proof oracle, not a replacement for retained geometric ordering. For n<600, explicitly allow empty estates or reject the domain; never silently drop lanes/nonces. Validate n=0,1,599,600,601, nonmultiples, nonzero starts, uint32 endpoint/wrap rules, and seeds [1337,42,2026]. A vertex bijection must not be confused with nonce-to-lane injectivity: multiple nonces legitimately share one lane.

`tests/test_600_geometry_bijection.py` exists and asserts totality, seen-set overlap rejection, ownership and re-export identity for selected windows. **NOT RUN in this session.** Its host-hash example uses a synthetic 76-byte prefix and an all-ones target, samples a subset independently, and is not proof that every real submission is independently rechecked. Require full submitted-candidate recheck records, meaningful positive/negative targets, malformed headers, stale identity rejection and independent expected digests. Preserve SHA256d <= target and pool ACK as separate authorities.

### 0.3 Frozen baseline and readiness proof

Use documented **154 (18+17+14+36+20+38+11)** for the scoped SPRINT1 baseline, not total repository tests and not newly executed proof. Gate **p95 <4.85ms**, canonical Ricci **<=8 steps** at kappa0=-1.62/tau=0.05, intact XOR **0.5625**, capital Phi per SPRINT1 Method A. Preserve historical results rather than globally replacing all counts.

PR #90 check-runs returned 403; legacy status returned pending with zero statuses. Per-suite conclusions and a 154-test tail remain unavailable. Manifest declares chain_verified=true/count=1, not independently reverified growth. Full-checkout collection, exact-suite execution, timing evidence, independent chain replay and real campaign receipts remain mandatory. Do not mark P2/P3/P4-P6 complete from source presence, blueprint prose or Boolean receipt fields. No runtime rewiring, live pool submission, soak, quarantine of code or Phase 3 authorisation is performed here.

---

## 1. Executive Summary & Production Target Architecture

The **600-Lane Solving Machine** transitions the execution engine from flat candidate iteration or coarse 32-face partitioning to an exact **Dodecahedron ⊕ Icosahedron overlay lifted to 11D** yielding **600 logical vertices = 600 independent execution lanes** operating under **1 central cognition head** (the Octopus model: 600 arms × 1 cognition head = `EuclidRuntime.production()`).

```
                    ┌────────────────────────────────────────┐
                    │    1 COGNITION HEAD: EuclidRuntime     │
                    │   (SearchPlan, Superposition Hold,     │
                    │    5+1 Scoring, Salamander Recovery)   │
                    └───────────────────┬────────────────────┘
                                        │
           ┌────────────────────────────┼────────────────────────────┐
           │ (Octopus Model: 600 Arms)  │                            │
           ▼                            ▼                            ▼
  ┌──────────────────┐         ┌──────────────────┐         ┌──────────────────┐
  │ Lane 000 (V_000) │         │ Lane 001 (V_001) │   ...   │ Lane 599 (V_599) │
  │ Nonce Estate [0] │         │ Nonce Estate [1] │         │ Nonce Estate[599]│
  │ 11D Coord Rep    │         │ 11D Coord Rep    │         │ 11D Coord Rep    │
  │ CHRONUS Route    │         │ CHRONUS Route    │         │ CHRONUS Route    │
  └──────────────────┘         └──────────────────┘         └──────────────────┘
           │                            │                            │
           └────────────────────────────┼────────────────────────────┘
                                        ▼
                    ┌────────────────────────────────────────┐
                    │  100% HOST SHA256d VERIFICATION GATE   │
                    │   (Double SHA256 <= Target Inviolable) │
                    └───────────────────┬────────────────────┘
                                        ▼
                    ┌────────────────────────────────────────┐
                    │  THESEUS Custody + OVID Meta + AETHEL  │
                    │  Merkle Root Hash-Chained Audit Ledger │
                    └────────────────────────────────────────┘
```

---

## 2. Current Lanes vs. 600-Vertex Target

| Property | Current Architecture | Target Architecture (P3-P5) | Gap & Production Completion Path |
| :--- | :--- | :--- | :--- |
| **Lane Topology** | **32 Logical Lanes** (`salamander_control.py:15` `LANES = 32`, `FACE_COUNT = 32` in `lucas_partition.py`, `0xFFFFFFFF` mask in `agentic_mining.py`) | **600 Logical Vertices = 600 Lanes** (`LANES = 600`, Dodecahedron (20V, 12F) ⊕ Icosahedron (12V, 20F) overlay embedded in 11D) | **EXPANSION TO 600**: Expand `LANES` to 600; partition leased window $W$ into 600 exact disjoint estates. Reconcile in `salamander_control`, `coordinator`, and `agentic_mining`. |
| **Estate Ownership** | Nonce windows distributed non-uniformly across physical device queues; multiple faces multiplexed over single workers | **Strict Vertex Ownership**: Each vertex $V_i \in \{0..599\}$ strictly owns its disjoint nonce-estate $W_i$. $\bigcup W_i = W$, $W_i \cap W_j = \emptyset\;\forall i \ne j$. | **BIJECTION COMPLETION**: Deterministic bijection mapping each vertex to unique estate chunk. Unit test verified for totality and disjointness. |
| **Coverage Guarantee** | Best-effort traversal ordering; fallback to partial interval polling | **Complete Hilbert-Space Tiling**: Every nonce in leased window visited exactly once, zero overlap, independently verifiable with proof receipt. | **PROOF HARNESS**: Automated mathematical assertion $\{ \text{complete}, \text{disjoint}, \text{recheck} \}$. |
| **Geometric Metric** | Poincaré-Cassini and M32 Voronoi embeddings | **11D Poincaré-Cassini + Klein/Poincaré Reps**: Normalized coordinates $\frac{n}{\sqrt{d}}$ over exact field $Q(\phi)$ and $\mathbb{R}^{11}$. | **EXPLICIT LABELLING**: Label every transform as `NUMERICAL` (Float64 boundary) vs `EXACT` ($Q(\phi)$ rational). |
| **Superposition Width**| Ad-hoc candidate tracking per job | **8-Future Superposition Hold** (`FUTURES = 8`, LRU hold) with probabilities derived strictly from literal outcomes. | **TENSOR CORE**: Mother-tensor dimension `[600 × 8 × chunksize × 11]`. |

---

## 3. Classical Path Audit (Files : Line Numbers)

To satisfy the **SOLVE not SEARCH** doctrine, all classical paths (flat state space loops, linear nonce incrementation `nonce++`, un-vectored brute-force scanning) are identified for quarantine and fail-closed shims in Phase P2.

### 3.1 Existing Quarantined Classical Path (`legacy_mining_classical_quarantined_814002a7/`)
Quarantined in commit `814002a7` with fail-closed shim in `mining/__init__.py`:
1. `legacy_mining_classical_quarantined_814002a7/search.py:1-200`: Flat iterative search loop over candidate nonces.
2. `legacy_mining_classical_quarantined_814002a7/hash_pipeline.py:1-250`: Raw sequential nonce testing without geometric order.
3. `legacy_mining_classical_quarantined_814002a7/production_miner.py:1-180`: Legacy stratum miner with linear increment.
4. `legacy_mining_classical_quarantined_814002a7/scaled_execution.py:1-120`: Un-anchored nonce dispatcher.
5. `legacy_mining_classical_quarantined_814002a7/nonce_scheduler.py:1-150`: Linear non-manifold window allocator.
6. `legacy_mining_classical_quarantined_814002a7/bitcoin_hasher.py:1-100`: Raw host CPU SHA256 loops.
7. `legacy_mining_classical_quarantined_814002a7/deterministic_hashrate.py:1-80`: Legacy benchmark loops.

### 3.2 Active Classical / Linear Remnants to be Quarantined in P2
The following active files contain linear scanning fallbacks or flat loops that will be quarantined or replaced with fail-closed shims:
1. `Intelligence/poincare_cassini_search.py:85-160`: Brute linear fallback when attractor basin is undefined.
2. `Intelligence/pool_aware_miner.py:70-135`: `for nonce in range(start, end):` flat sequential scanning fallback.
3. `chronus/mla1517/mining/pythia_search.py:45-92`: Scalar sequential candidate test loop.
4. `chronus/mla1517_platform/python/mining_runtime.py:110-185`: Unbounded CPU thread fallback with sequential nonces.
5. `gpu/backends/chronus.py:50-98`: Un-vectored CPU loop lacking tensor contraction.
6. `hyba/hybrid/coordinator.py:120-180`: Legacy 32-face queue polling loop.

---

## 4. Subsystems Audit: Locations, Status & Production Completion

| Subsystem | Primary Code Locations | Status | Production Readiness Gap & Concrete Completion Deliverable |
| :--- | :--- | :--- | :--- |
| **KELLOGG Mother-Tensor** | `kellogg/phi_tensor_core.py`, `kellogg/scales.py`, `kellogg/exact_tensor.py`, `kellogg/traversal.py`, `tensor/` | **PARTIAL** | **Completion Deliverable (P3)**: Create single canonical module `kellogg/mother_tensor.py` with dimension `[600 lanes × 8 futures × nonce-chunks × 11D coords]`. Re-export across `tensor/` and `chronus/`. Verify contraction reproduces $\{ \phi, 0.0520 \to 0.5625 \text{ XOR}, \kappa \text{ trace} \}$. |
| **TURING Virtual QPU** | `turing_universal_quantum_computer/`, `chronus/exact_geometry.py:300-341`, `chronus/mla1517_platform/python/turing_core.py` | **PARTIAL** | **Completion Deliverable (P4)**: Virtual QPU emulator (labelled emulator until silicon PASS). Wire tunnelling (barrier escape for stuck futures), warm-start annealing from literal pool history, Hadamard quantum walk (8 steps, seed-pinned same-hash replay), and Hendrix-Grover clamped amplitude reweighting. |
| **CHRONUS GPU / iGPU** | `chronus/one_igpu.py`, `chronus/one_igpu_mining.py`, `chronus/exact_geometry.py`, `chronus/mla1517/mining/h4_600_execution.py` | **WIRED** | **Completion Deliverable (P5)**: Sole execution route. Requested/executed/fallback logged with 100% host SHA256d recheck. CPU/emulator never reported as physical silicon. Reconcile `micro_tether.py` into Chronus. |
| **THESEUS Custody & OVID Metamorphosis** | `aethel/theseus.py`, `aethel/ovid.py`, `aethel/constants.py`, `hyba_db/theseus_custody.py`, `hyba_db/ovid_index.py` | **WIRED** | **Completion Deliverable (P5)**: Superposition hold (8 futures), SearchPlan, ExecutionRecord, literal pool outcome, heal record. Hash-chained with Merkle root per campaign. |
| **YANG-MILLS Gauge Plane** | `millennium/hyba_poincare_yangmills.py`, `toe/poincare_yangmills.py`, `toe/golden_unified.py` | **PARTIAL** | **Completion Deliverable (P4)**: Gauge-invariant lane transport: audit assertion verifying no lane among the 600 possesses structural privilege. |
| **RICCI Flow & Curvature** | `euclid/cognition/cognitive_topology.py:413-431, 523-585`, `Intelligence/recursive_self_learning.py:247-274` | **WIRED** | **Completion Deliverable (P4)**: Forman-Ricci curvature on lane graph; golden flow $\kappa_{k+1} = \phi^{-1} \kappa_k$ with canonical trauma $(I=9, c=0.8) \implies \kappa_0 = -1.62$, reaching $|\kappa| \le 0.05$ within $\le 8$ steps. |
| **TOE Parametric Ansatz** | `toe/golden_unified.py:24-53`, `Intelligence/quantum_algorithms.py:628-713` | **PARTIAL** | **Completion Deliverable (P4)**: Create versioned `toe/ansatz_v3.py` unifying 5 intelligences (predictive, causal, counterfactual, topological, geometric) + quantum-ext into single parametric tensor contraction. |
| **SALAMANDER Healer** | `chronus/mla1517_platform/python/salamander_engine.py`, `chronus/mla1517_platform/python/control_api.py`, `salamander_control.py` | **PARTIAL** | **Completion Deliverable (P2)**: Healer > optimizer loop: observe $\to$ classify $\to$ bounded-action $\to$ ack $\to$ post-observe $\to$ verified-recovery $\to$ resume. Wire 15.7s re-auth template for WinError 10054 pool drop. Offload tree inference (rf/xgb/lgbm/gb), discovery campaigns, and JSON snapshots to `ThreadPoolExecutor(4)` to achieve heartbeat p95 < 1.0s. |

---

## 5. Hendrix Clamp Status

- **Origin & Commit:** Commit `9e3420bb49` (`fix(quantum): close amplitude-amplification claim, clamp and difficulty gaps`).
- **Mathematical Bound:** In `quantum_compute_substrate/amplitude_amplification.py:60-68`:
  $$\text{MATERIALISATION\_BOUND} = 2^{20}$$
  $$\text{simulation\_dimension} = \min(\text{search\_space}, \text{MATERIALISATION\_BOUND})$$
- **Claim Enforcement:** 
  - `al_haras/refuted_claims.py:38-44` permanently refutes and bans phrases: `"8192x parallelism"`, `"Grover search at 8,192x parallelism"`, `"theoretical_speedup"`.
  - The ratio $\sqrt{N/M}$ is strictly designated an **oracle-query ratio**, NOT a wall-clock speedup or physical device throughput multiplier.
  - In `chronus/mla1517/mining/hendrix_order.py`, the Hendrix schedule is strictly an **ordering bijection** ($gcd(stride, n) = 1$) over the leased window; every visited nonce is hashed with double SHA256 and checked against target.
- **Audit Verdict:** **CLAMP CONFIRMED IN THE INSPECTED MODULE**. `MATERIALISATION_BOUND = 2 ** 20` and `min(search_space, bound)` are present. Repository-wide absence of unclamped claims is not established by this inspection.

---

## 6. Micro-Tether vs. Chronus Duplication Verdict

- **Inspection:** `euclid/sovereign/micro_tether.py` implements:
  1. `TEEEnclaveSeal`: Hardware enclave simulation / attestation (Intel SGX / AWS Nitro).
  2. `AGI_Interface`: Autonomous schema/causality parsing, semantic pressure gauge, stochastic noise.
  3. `TopologicalMapper`: 3D vs 7D manifold coordinate mapping.
  4. `SovereignDeltaOracle`: DIFC Zero-Gharar delta fee capture (~0.19% of verified $\Delta = \max(0, X - Y)$).
- **Substrate Analysis:** `micro_tether.py` does **NOT** contain an iGPU, GPU kernel, OpenCL driver, or proof-of-work hasher. It is an edge security and economic oracle adapter.
- **Owner Directive Compliance:** Owner Declarations D1, D3, D4, and D9 state:
  - *Chronus is the owner's GPU — exponential potential, limited by math only.*
  - *Chronus is the sole execution plane and sole iGPU.*
- **Duplication Verdict:** **P1 CHILD-ADAPTER CONTRACT; RUNTIME BINDING NOT PROVEN.**
  `micro_tether.py` is an edge attestation and DIFC contract oracle adapter, not a parallel execution engine. All execution and tensor compute requests within `euclid/sovereign` MUST bind exclusively to `chronus.one_igpu` / `ChronusExecutionEngine`. No second iGPU or parallel execution route will be created.

---

## 7. The 11-Step Solving & Completing Lifecycle (Production Execution Contract)

In production, the 600-Lane Solving Machine does NOT blindly search or iterate. It executes an exact, deterministic 11-step lifecycle under `EuclidRuntime.production()` where every phase gate must strictly complete before state transitions occur:

```
[1. Stratum Intake] ──> [2. 600-Vertex 11D Bijection] ──> [3. 8-Future Superposition]
                                                                     │
[6. Chronus iGPU Exec] <── [5. SearchPlan Collapse] <── [4. 5+1 Intelligence Scoring]
        │
        ▼
[7. 100% Host SHA256d Recheck] ──> [8. Approval Gate: Shadow vs Submit]
                                                  │
[11. Aethel Ledger Sealing] <── [10. Salamander Healing] <── [9. Literal Outcome Feedback]
```

1. **Stratum Job Intake & Leased Window:**
   - Ingestion of `mining.notify` from Braiins pool (jobs 00-06).
   - Establishes leased nonce estate window $W = [N_{\text{start}}, N_{\text{end}})$.
   - Re-verifies baseline tenant isolation (M3 tenant context, `Auth: true`).

2. **600-Vertex Geometric Bijection (`Build600Partition`):**
   - Lifts the Dodecahedron (20V, 12F) $\oplus$ Icosahedron (12V, 20F) overlay into 11D coordinates over $\mathbb{Q}(\phi)$ and $\mathbb{R}^{11}$.
   - Decomposes window $W$ into exactly 600 disjoint estate chunks $\{W_0, W_1, \dots, W_{599}\}$.
   - **Completing Invariant:** $\bigcup_{i=0}^{599} W_i = W$ (100% Hilbert space coverage) and $W_i \cap W_j = \emptyset\;\forall i \ne j$ (0% overlap).

3. **8-Future Superposition Hold (THESEUS Memory):**
   - Retains 8 candidate future trajectories in LRU superposition.
   - Priors seeded strictly from historical literal pool outcomes; zero invented priors.

4. **5+1 Per-Lane Intelligence Scoring:**
   - Evaluates all 600 lanes across the 5+1 fundamental state spaces:
     - **Predictive:** $P(\text{accept})$ scored via literal-trained ensemble (`rf`, `xgb`, `lgbm`, `gb`) offloaded to `ThreadPoolExecutor(4)`.
     - **Causal:** Pearl Layer-2 $do(\text{lease}, \text{route}, \text{transport})$ intervention attribution.
     - **Counterfactual:** Pearl Layer-3 regret ledger evaluating alternative path value.
     - **Topological:** Forman-Ricci curvature $\kappa$ damping singularities ($\kappa_0 = -1.62 \implies |\kappa| \le 0.05$).
     - **Geometric:** Bijection traversal ordering over 11D Poincaré-Cassini manifold.
     - **Quantum-Ext:** Hadamard walk reweighting with seed-pinned same-hash replayability.
   - Applies bounded Arsenal operators (tunnelling for stuck futures, annealing from truth).
   - **Yang-Mills Symmetry Check:** Asserts gauge invariance — no lane among the 600 holds arbitrary structural privilege.

5. **SearchPlan Collapse:**
   - Collapses the scored superposition into a deterministic `SearchPlan`.
   - Records cryptographic `collapse_reason` and logs evaluated alternative paths for auditability.

6. **CHRONUS Execution (Sole Execution Route):**
   - Dispatches chunks to `chronus.one_igpu` (or Virtual iGPU CPU-emulator fallback).
   - Logs `{requested: chronus, executed: device_id, fallback: bool}`.
   - Emits hardware honesty tag: `EMULATOR` permanently logged when running on silicon CPU.

7. **100% Host SHA-256d Recheck Gate (Double SHA-256 $\le$ Target Inviolable):**
   - **Zero Unchecked Submissions:** Every candidate share meeting difficulty target $H \le \text{Target}$ is independently re-hashed on the host ALU.
   - Mismatch triggers immediate halt (`FAIL_CLOSED`) and raises `AttestationViolation`.

8. **Approval Gate: Shadow Logging vs. Live Pool Submit:**
   - **Safe Gate:** Defaults to `SHADOW_LOG` (no live stratum submission without explicit `approval_flag=True`).
   - If approved, dispatches `mining.submit` to Braiins pool with session credentials.

9. **Literal Outcome Feedback Loop (The Only Reward):**
   - Pool response (`ACCEPTED`, `REJECTED`, `STALE`, difficulty adjustment) ingested.
   - Updates predictive weights and causal graphs based exclusively on literal empirical truth.

10. **Salamander Self-Healing Loop:**
    - Loop: `Observe -> Classify -> Bounded Action -> Ack -> Post-Observe -> Verified Recovery -> Resume`.
    - **Pool Disconnect:** WinError 10054 triggers 15.7s auto-reauthentication template.
    - **GIL Stall Elimination:** Worker monitoring, tree inference, and snapshots run in `ThreadPoolExecutor(4)`, ensuring heartbeat p95 $< 1.0\text{s}$.

11. **Attestation & Aethel Ledger Sealing:**
    - Generates Merkle root over `{SearchPlan_hash, ExecutionRecords, outcome_literal, heal_record}`.
    - Appends attested block to hash-chained Aethel ledger, pinning `ledger_head`.

---

## 8. Inviolable Production Readiness Contracts & SLO Verification Matrix

To certify the 600-Lane Solving Machine for production deployment, the implementation must satisfy 8 inviolable SLO gates:

| Invariant / SLO | Metric Target | Verification Mechanism | Production Failure Mode |
| :--- | :--- | :--- | :--- |
| **1. Nonce Disjointness** | $W_i \cap W_j = \emptyset\;\forall i \ne j$ (Overlap = 0) | Set-intersection unit test over all 600 chunks | `OverlapDetected`: Immediate lane halt; campaign aborted. |
| **2. Nonce Totality** | $\bigcup_{i=0}^{599} W_i = W$ (Coverage = 100%) | Range coverage cardinality check $\sum |W_i| = |W|$ | `CoverageIncomplete`: Campaign rejected; fallback triggered. |
| **3. Host Recheck Rate** | 100.0% of candidate hashes | Host ALU double-SHA256 re-computation before submit | `RecheckFailure`: Candidate dropped; hardware fault logged. |
| **4. Hardware Honesty** | Zero false silicon claims | Backend inspection: CPU/emulator flagged `EMULATOR` | `AttestationViolation`: Process terminated on spoofing. |
| **5. Hendrix Amplitude Clamp** | Bound $2^{20}$ enforced | `MATERIALISATION_BOUND = 2**20` assertion in QPU core | `UnclampedClaimError`: Refuted claim triggers audit halt. |
| **6. Heartbeat Latency SLO**| p95 latency $< 1.0\text{s}$ | `ThreadPoolExecutor(4)` offloads tree inference & snapshots | `HeartbeatStall`: Supervisor flags worker stale if p95 > 2.5s. |
| **7. Pool Recovery SLO** | Re-auth $\le 15.7\text{s}$ | Salamander automated socket reconnect on WinError 10054 | `StratumDrop`: Salamander escalates to backup pool endpoint. |
| **8. Submission Safety** | Default Shadow Mode | Live `mining.submit` blocked unless `approval_flag=True` | `UnapprovedSubmit`: Submissions denied; logged to shadow file. |

---

## 9. Phase Completion Mapping & Verification Gates (P1 through P6)

| Phase | Phase Deliverable | Required Proofs & Code Locations | Production Readiness Verification Gate | Status |
| :--- | :--- | :--- | :--- | :--- |
| **P1: MAP** | Architectural Map & Verification Blueprint | `600LANE_MAP.md` | Full topology map; classical path audit; Hendrix clamp audit ($2^{20}$ bound); micro-tether reconciliation verdict. | **REPORTED DONE — NOT REVERIFIED** |
| **P2: QUARANTINE & GIL FIX** | Isolate classical path + ThreadPoolExecutor(4) | `mining/`, `legacy_mining_classical_quarantined_814002a7/`, `chronus/mla1517_platform/python/control_api.py` | 1. Quarantined classical imports fail closed.<br>2. ThreadPoolExecutor(4) wired for rf/xgb/lgbm/gb + discovery + snapshots.<br>3. Heartbeat p95 logged and verified $< 1.0\text{s}$.<br>4. `pytest --collect-only` passes 100% with 0 errors (7024 collected).<br>5. Braiins pool connection preserved. | **REPORTED DONE — NOT REVERIFIED** |
| **P3: GEOMETRY & KELLOGG** | 600-Vertex Bijection & Canonical Mother-Tensor | `chronus/exact_geometry.py`, `kellogg/mother_tensor.py`, `kellogg/ansatz_v3.py`, `tests/test_600_geometry_bijection.py` | 1. Bijection builder produces 600 disjoint chunks with 100% coverage proof.<br>2. Unit tests verify 0 overlap and 100% host SHA256d recheck.<br>3. Single canonical `kellogg/mother_tensor.py` `[600 × 8 × chunk × 11]` reproduces $\{\phi, 0.5625 \text{ XOR}, \kappa \text{ trace}\}$. | **REPORTED DONE — NOT REVERIFIED** |
| **P4: ARSENAL & TOE WIRING** | Clamped Hendrix, Walk, Tunnelling & Ricci Flow | `chronus/mla1517/mining/`, `toe/ansatz_v3.py`, `euclid/cognition/cognitive_topology.py` | 1. Hendrix-Grover clamped to $2^{20}$; Hadamard walk verifies same-hash across [emulator, CPU, chronus].<br>2. Yang-Mills gauge symmetry check passes for all 600 lanes.<br>3. Ricci flow reaches $|\kappa| \le 0.05$ within $\le 8$ steps canonical.<br>4. Per-lane 5+1 log structure verified. | **SPECIFIED** |
| **P5: OCTOPUS CLOSE** | 600 Arms $\to$ 1 Head Live on Braiins Jobs | `chronus/mla1517_platform/python/coordinator.py`, `euclid/euclid_runtime.py` | 1. 600 arms execute concurrently under `EuclidRuntime.production()`.<br>2. 10-minute soak test on Braiins jobs 00-06 logging jobs, difficulties, invalidated/stale, heals, rechecks.<br>3. Shadow execution active; zero unapproved submissions. | **SPECIFIED** |
| **P6: PROOF GATES & RELEASE** | Proof Verification & Release Documentation | `benchmarks/`, `600LANE_RELEASE.md` | 1. Pytest mining, lease, and router suites pass.<br>2. `test_euclid_vs_ineffable.py`, `test_euclid_vs_frontier_llms.py`, and Arena G1-G3 pass.<br>3. `600LANE_RELEASE.md` issued with MEASURED timings, coverage, and ledger head. | **SPECIFIED** |

---

## 10. Definition of Done Checklist

- [x] **P1 Map:** Complete 600-lane architectural layout, classical audit, Hendrix clamp, micro_tether reconciliation, and 11-step completing lifecycle documented in `600LANE_MAP.md`.
- [ ] **P2 Quarantine & GIL Fix:** Classical paths quarantined with fail-closed shims; `ThreadPoolExecutor(4)` active; heartbeat p95 < 1.0s; Braiins connection maintained; 7024 tests collected with 0 errors.
- [ ] **P3 Geometry & Mother-Tensor:** 600-vertex partition proven complete (100%) and disjoint (0% overlap); unique vertex ownership verified; `kellogg/mother_tensor.py` reproduces $\{\phi, 0.5625 \text{ XOR}, \kappa \text{ trace}\}$; host SHA256d recheck 100%.
- [ ] **P4 Arsenal & TOE:** Clamped Hendrix, quantum walk, annealing/tunnelling, Yang-Mills gauge symmetry, and Ricci flow wired into per-lane 5+1 scoring.
- [ ] **P5 Octopus Close:** 600 arms $\times$ 1 head executing on Braiins pool jobs; 10-minute soak logged; Salamander 15.7s recovery active.
- [ ] **P6 Proof Gates:** Test suites passed; `600LANE_RELEASE.md` issued with measured timings, coverage, and ledger head.

