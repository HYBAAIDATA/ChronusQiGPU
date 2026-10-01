# EUCLID-CORE / HYBA // PYTHIA — Architecture

> **Post-consolidation note (2026):** this document was written against the
> pre-consolidation tree. The canonical runtime view is
> [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Paths below have been
> updated to current locations (`legacy/` for archived components);
> `docs/UNIFIED_RUNTIME.md` remains the end-to-end blueprint.

> **Unified runtime blueprint:** for the end-to-end production pipeline
> (device registry, co-scheduling, Docker topology, self-healing, and the
> measured/computed/projected truth-class rules), see
> [`docs/UNIFIED_RUNTIME.md`](docs/UNIFIED_RUNTIME.md).

> **Exact-Mathematics Treasury Orchestrator**
> Joint Venture computational platform for exact algebraic mining orchestration, Stratum telemetry, and hardware verification.
> Mathematical substrate: **Q[√5] Exact Rational Field** — zero floating-point units.

---

## 1. What this project is

EUCLID-CORE (a.k.a. HYBA // PYTHIA) is a full-stack research/engineering platform whose central thesis is:

> **Cryptocurrency mining can be reformulated as an exact rational arithmetic problem over the quadratic field Q[√5] = {a + b√5 | a, b ∈ Q}, using a 32-face topological state space, with Grover amplitude amplification + Lucas-Pisot scaling — and the correctness of every step is provable in silicon via fatal SVA assertions.**

The repo contains four interlocking layers:

| Layer                              | Language      | Location                                                                     | Role                                                                                                 |
| ---------------------------------- | ------------- | ---------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| **Exact math / quantum core**      | TypeScript    | `src/lib/`                                                                   | The reference engine: BigFraction, Q[√5] field, Grover over 32×2^N states, hardware projections      |
| **Stratum / mining orchestration** | TypeScript    | `src/lib/`, `server.ts`                                                      | Stratum V1 protocol, mining lifecycle, mempool, difficulty, repositories, event bus                  |
| **Hardware (ASIC)**                | SystemVerilog | `legacy/hardware/rtl/`, `legacy/hardware/tb/`                                | The Q5 ASIC: zero-FPU rational ALU, Zeckendorf HBM3e controller, 9-invariant monitor, SVA assertions |
| **Verification & CI**              | Python        | `turing_core.py`, `legacy/scripts/euclid_tapeout_checklist.py`, `legacy/python_backend/`, `tests/` | Golden-model invariants, FPU-ban static analysis, tape-out checklist, CI kill switch                 |

A React/TypeScript frontend (`src/App.tsx` + `src/components/`) exposes 37 panels, and an Express server (`server.ts`) exposes ~90 HTTP endpoints plus an SSE stream. Firebase/Firestore persists audit reports and mining sessions; Prometheus scrapes `/metrics`.

---

## 2. Repository layout

```
euclid-core/
├── server.ts                 # Express API server (~1800 lines, ~90 endpoints + SSE)
├── package.json              # Node 22+, Vite + React 19, esbuild, firebase, prom-client
├── index.html                # SPA entry (Fraunces / IBM Plex fonts)
├── vite.config.ts / tsconfig.json
├── metadata.json             # AI Studio applet metadata
├── .env.example              # GEMINI_API_KEY, APP_URL
│
├── src/
│   ├── App.tsx               # Root SPA — 25+ tabbed panels, 60s auto-audit loop
│   ├── main.tsx / index.css
│   ├── components/           # 37 React panels (see §6)
│   ├── lib/                  # 31 TypeScript modules (see §3–§5)
│   └── security/
│       └── al_haras_gateway.ts   # Topological auth middleware (Hodge/Lucas/Yang-Mills)
│
├── legacy/hardware/
│   ├── rtl/
│   │   ├── q5_types_pkg.sv            # Shared types: q_rational_t, q5_exact_amp_t, opcodes
│   │   ├── q5_exact_alu.sv            # Zero-FPU rational ALU + inline Lucas-Pisot SVA
│   │   ├── q5_top_asic.sv             # Top ASIC: Stratum V1 iface + Cassini SVA + circuit breaker
│   │   ├── q5_zeckendorf_hbm3e_ctrl.sv# Fibonacci bank memory controller + Zeckendorf SVA
│   │   ├── golden_invariant_monitor.sv   # GIMB: all 9 invariants combinationally
│   │   ├── golden_ontology_transform.sv  # Fibonacci butterfly FFT replacement
│   │   ├── emergent_intelligence_detector.sv
│   │   ├── yang_mills_gap_monitor.sv
│   │   └── assertions/
│   │       └── golden_invariant_sva.sv    # 9 fatal assert property + 10 cover property
│   └── tb/
│       └── q5_formal_sva_tb.sv       # 1000-cycle formal proof @ 2.4 GHz
│
├── legacy/papers/discovery/          # tape-out verification trio
│   ├── euclid_tapeout_checklist.py   # 12-item tape-out checklist + 5 dynamic engines
│   ├── q5_golden_formal.py           # 9-invariant exact Python verification + FORMAL_JOBS
│   └── clay_checklist.py             # Yang-Mills mass-gap honesty layer (0 ESTABLISHED)
│
├── turing_core.py                   # Zero-dep Python golden model + PythiaMiningEngine
├── legacy/scripts/euclid_tapeout_checklist.py  # Checklist mirror (was repo-root copy)
├── legacy/tests/
│   └── load_test_k6.js               # k6 load test
├── scripts/                         # TS test scripts (Q5 reference, RTL, Al Haras handshake)
├── legacy/infra/prometheus/          # prometheus.yml + alerts.yml (6 alert rules)
├── legacy/firestore.rules            # Default-deny, immutable audit trails
├── legacy/firebase-blueprint.json    # JSON-schema for MiningSession / Share / AuditReport
└── firebase-applet-config.json       # Firebase client config (AI Studio applet)
```

---

## 3. The exact-math / quantum core (`src/lib/`)

### 3.1 Numeric substrate

| File              | Exports                                  | Role                                                                                                                                                                                                                                     |
| ----------------- | ---------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `exact_math.ts`   | `BigFraction`, `Q5`, `ExactSequenceMath` | Arbitrary-precision rationals (BigInt, auto-GCD); the quadratic field Q[√5] with field-closed +,×, conjugate, norm, inverse; exact Fibonacci/Lucas/Cassini/Zeckendorf. **Every amplitude in the system is a `Q5` (two `BigFraction`s).** |
| `hodge_bridge.ts` | `HodgeBridge`                            | Zeckendorf indices + Lucas spectral gap → 11D manifold projection. Thin geometric connector.                                                                                                                                             |

Key insight in `exact_math.ts`: amplitudes are stored **projectively** (amplitude 1, not 1/√N), deferring normalization to the Born rule. This avoids irrational 1/√N factors entirely.

### 3.2 Quantum engines

| File                          | Exports                                                                                                                 | Role                                                                                                                                                                                                                                                                                                                    |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `quantum_engine.ts`           | `QuantumAlgebraicEngine`, `GlobalStateSpace`                                                                            | Grover over the 32-face space using `BigFraction` amplitudes. `computeOptimalIterations` finds the discrete-optimal k* by exact 2D-subspace evaluation. `compare32FaceModels` is a formal audit proving the 32-face topology must not be collapsed.                                                                     |
| `q5_reference.ts`             | `Q5ReferenceEngine`, `UnimodularSL2Z`, `LucasAlgebra`, `HARDWARE_TARGETS`                                               | Phase-0 reference: Grover over Q5 on the 2D invariant subspace, exact OptimalK via rational π convergents (333/106, 355/113), `verifySymmetry` (bit-identical dense↔reduced proof), `runPreFlightAudit` (Cassini, Lucas-Fibonacci, field axioms). Hardware targets for 5 platforms (Q5 ASIC, M3 Max/Ultra, H100, B200). |
| `q5_coprocessor.ts`           | `Q5CoprocessorScaffold`, `Q5CoprocessorSpec`                                                                            | Frozen ASIC architecture spec (TSMC N3E, 850mm², 12 HBM3e stacks, 384 TB/s, ISA opcodes). `runPhase0Benchmark` cross-verifies dense vs reduced Grover bit-for-bit and proves the **bit-width bound** `log₂(den) ≤ k·log₂(φ²)+1` — the feasibility argument that denominators grow only logarithmically.                 |
| `q5_golden_silicon.ts`        | `evaluateAll9Invariants`, `computeGoldenOntologyTransform`, `detectEmergentIntelligence`, `computeYangMillsSpectralGap` | The 9 "golden discoveries" (Cassini, Pisot, Binet, Lucas, Zeckendorf, Soliton, Holographic, Structure, P-vs-NP) as exact-algebra checks; Fibonacci-butterfly FFT replacement; emergent-intelligence detector; Yang-Mills gap = 17/7 > 0.                                                                                |
| `q5_rtl_specs.ts`             | `Q5RtlSpecification`                                                                                                    | Emits the SystemVerilog RTL + SVA assertions as strings (the `.sv` files in `legacy/hardware/rtl/` are the materialized output). 4 fatal SVA properties + GIMB + ontology transform + intelligence detector + Yang-Mills monitor. *(module not present in current tree)*                                                                                              |
| `first_principles_quantum.ts` | `Complex`, `ComplexMatrix`, `QuantumState`, `QuantumGates`, `ExactGrover`, `ExactQFT`, `ExactVQE`, `ExactTopology`      | The **floating-point reference baseline** (standard quantum computing over ℂ). The exact rational engine is claimed to produce equivalent results without FP errors.                                                                                                                                                    |
| `quantum_walker_aqo.ts`       | `GlobalHybridQuantumWalker`, `DTQWLayer`, `CTQWLayer`, `AQOLayer`, `RiemannianSimplexLayer`, `M32_ADJACENCY`            | Runtime mining optimizer: hybrid quantum walk (discrete + continuous + adiabatic + Riemannian retraction) on the 32-face icosahedral graph. Redistributes mining effort across faces in real time.                                                                                                                      |
| `grand_unified_tensor.ts`     | `GrandUnifiedKelloggTensor`                                                                                             | 9 institutional modules (CERN, Oxford, Cambridge, MIT, Caltech, Princeton, Harvard, Stanford, Chicago) mapping physics/math frameworks to the mining structure. Conceptual unification layer.                                                                                                                           |
| `blockchain_consciousness.ts` | `GlobalBlockchainConsciousness`                                                                                         | Meta-monitor: pairwise Cassini verification across all C(32,2)=496 face pairs; 6-level consciousness classification (NONE→TRANSCENDENT).                                                                                                                                                                                |

### 3.3 The 9 golden invariants

These are the mathematical guarantees enforced everywhere — in TS, in Python, and as fatal SVA assertions in silicon:

| #     | Invariant           | Formula                            | Where enforced                                                                             |
| ----- | ------------------- | ---------------------------------- | ------------------------------------------------------------------------------------------ |
| INV-1 | Cassini identity    | F_{n-1}F_{n+1} − F_n² = (−1)^n     | `q5_top_asic.sv:84`, `golden_invariant_sva.sv:36`, `q5_golden_formal.py:118`, audit_matrix |
| INV-2 | Pisot decay         | \|ψ\|^n → 0 (ψ = −1/φ)             | `golden_invariant_sva.sv:46`, `q5_golden_formal.py:136`                                    |
| INV-3 | Binet recurrence    | F_n = F_{n-1} + F_{n-2}            | `golden_invariant_sva.sv:56`, `q5_golden_formal.py:152`                                    |
| INV-4 | Lucas-Pisot scaling | new_amp·L_{n+1} = old_amp·L_n      | `q5_exact_alu.sv:105`, `golden_invariant_sva.sv:66`, `q5_golden_formal.py:166`             |
| INV-5 | Zeckendorf spacing  | \|k_i − k_j\| ≥ 2 (no adjacent 1s) | `q5_zeckendorf_hbm3e_ctrl.sv:96`, `golden_invariant_sva.sv:76`, `q5_golden_formal.py:183`  |
| INV-6 | Soliton commutator  | [H, Φ] = 0                         | `golden_invariant_sva.sv:86`, `q5_golden_formal.py:204`                                    |
| INV-7 | Holographic entropy | S = Area(γ_A)/4G > 0               | `golden_invariant_sva.sv:96`, `q5_golden_formal.py:211`                                    |
| INV-8 | Structure existence | ∃ Φ > 0 (non-degenerate spectrum)  | `golden_invariant_sva.sv:106`, `q5_golden_formal.py:220`                                   |
| INV-9 | P-vs-NP gap         | L_n − ψ^n = 2φ^n > 0               | `golden_invariant_sva.sv:116`, `q5_golden_formal.py:227`                                   |

---

## 4. The Stratum / mining / mempool layer

### 4.1 Mining lifecycle (end-to-end)

```
SUBSCRIBE → NOTIFY → SEARCH → SUBMIT → RESOLVE
```

| Phase         | File                                                            | Key function                                      | What happens                                                                                                                                                                          |
| ------------- | --------------------------------------------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Subscribe** | `stratum_protocol.ts`                                           | `buildConfigurePayload`, `parseSubscribeResponse` | BIP310 version-rolling negotiate; extract **extranonce1** + **extranonce2_size** (NOT nBits). Session opened via `Database.openSession`.                                              |
| **Notify**    | `stratum_protocol.ts`, `mining_service.ts`                      | `StratumJobLifecycleCoordinator.onJobNotify`      | 9-field `mining.notify` parsed; if `cleanJobs && jobId changed`, abort listeners fire. Job inserted into DB.                                                                          |
| **Search**    | `mining_service.ts`, `quantum_engine.ts`                        | `MiningService.executeMiningStep`                 | Init 32×2^N superposition → compute OptimalK (bounded ≤6) → Grover loop: **each iteration checks `isJobStale`** (clean_jobs interrupt) → Oracle → Diffusion → Lucas-Pisot scaling.    |
| **Submit**    | `mining_service.ts`, `bitcoin_header.ts`, `stratum_protocol.ts` | `meetsTarget`, `buildSubmitPayload`               | Measure best state → `transformCandidateToNonce` (5 bits face + 27 bits local) → build 80-byte header → **MeetsTarget pre-submit gate** (SHA-256d ≤ target) → `Database.insertShare`. |
| **Resolve**   | `mining_service.ts`, `repositories.ts`                          | `markShareResolved`                               | Simulated pool acceptance → `EventBus.publish("euclid:shares","share.resolved")` → telemetry (exact BigInt hashrate).                                                                 |

### 4.2 Key files

| File                        | Role                                                                                                                                                                                                                                                                                                                                                          |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `stratum_protocol.ts`       | `StratumV1ProtocolEngine` (message builders/parsers, MeetsTarget gate, stale-rate estimator), `StratumJobLifecycleCoordinator` (clean_jobs/stale-share handling), `StratumCircuitBreaker` (Fibonacci-backoff pool failover), `ENTERPRISE_MINING_POOLS` (ViaBTC primary, Braiins secondary), `ENTERPRISE_STRATUM_SLA`, `STRATUM_ERROR_REGISTRY` (codes 20–25). |
| `mining_service.ts`         | `MiningService.executeMiningStep` — the orchestrator. `transformCandidateToNonce` preserves 32-face topology in the nonce. `startContinuousMining`/`stopContinuousMining` run the background loop (default 2500ms).                                                                                                                                           |
| `mempool_service.ts`        | `MempoolService.optimizeBlockSpace` — package-aware greedy selection with **exact cross-multiplication** fee density (zero FP). Topological ancestry enforced at selection + insertion. `MAX_BLOCK_WEIGHT_WU = 4,000,000`. `generateAuthenticMempoolSnapshot` builds realistic CPFP chains.                                                                   |
| `mempool_nonce_analyzer.ts` | Pulls last 100 Bitcoin nonces from mempool.space, scores structured (Kellogg) vs unstructured (Grover), recommends search strategy.                                                                                                                                                                                                                           |
| `bitcoin_header.ts`         | 80-byte header builder, merkle root, `targetFromBits` (compact → 256-bit), SHA-256d. `getCanonicalJob` provides a benchmark sample job.                                                                                                                                                                                                                       |
| `difficulty_retargeting.ts` | `ExactDifficultyRetargeter` — BIP-22 consensus math with factor-of-4 bounds, MAX_TARGET ceiling, multiply-before-divide. 6 benchmark scenarios.                                                                                                                                                                                                               |
| `repositories.ts`           | `Database` (in-memory Maps): Worker, Session, Job, Share, GroverRun, ExactAuditEntry, TelemetryMetric. All numeric fields stored as exact strings. Two-phase share resolution.                                                                                                                                                                                |
| `event_bus.ts`              | `EventBus` — typed pub/sub on 5 channels (`euclid:jobs`, `euclid:shares`, `euclid:telemetry`, `euclid:control`, `euclid:audit`). 200-event history cap.                                                                                                                                                                                                       |
| `m3_igpu_scaler.ts`         | `ExactLucasEngine`, `NearStateIGpuSubsystem`, `GlobalPoolMiner` — Apple M3 Ultra baseline hashrate scaling with pool ceilings (ViaBTC 300 EH/s, Braiins 20 EH/s). Scale indices restricted to the Lucas/Pisot ladder {10,12,15,18,20,31,50,76} and multiples.                                                                                                  |
| `gpu_topology.ts`           | `EUCLID_VGPU` — real GPU hierarchy model (8 GPCs → 80 SMs → 4 SIMD × 32 lanes = 10,240 ALU lanes), reference GPU presets (M5 Pro/Max, RTX 4090, H100, MI300X), `scaleTopology`/`rivalry`/`fleetOf`/`fleetForHashrate`, sha256d throughput model.                                                                                                                |
| `kellogg_operator.ts`       | `KelloggPipeline` — 6-layer structured search (QW, AA, Riemannian, tensor network, variational, topological). `verifyGroverDegenerateLimit` proves Theorem A.1 (Kellogg → Grover in empty-structure limit, < 1e-12).                                                                                                                                          |
| `kellogg_full_stack.ts`     | 9 refactored modules + 5 named systems (TURING, COGITO, AL HARAS, EUCLID, SALAMANDER). `KelloggFullStack` orchestrator.                                                                                                                                                                                                                                       |

### 4.3 Stratum error prevention

| Error                       | Code | Prevention mechanism                                                                                                                             |
| --------------------------- | ---- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Job not found (stale share) | 21   | `StratumJobLifecycleCoordinator.isJobStale` checked at top of every Grover iteration; mid-flight abort + `clean_jobs_aborts_prevented` telemetry |
| Low difficulty share        | 23   | `MiningService.meetsTarget` pre-submit gate (SHA-256d ≤ target) before any `insertShare`                                                         |
| Duplicate share             | 22   | (structural — unique nonce per face/local index)                                                                                                 |
| Unauthorized                | 24   | `Database.findWorkerByName` + password hash                                                                                                      |
| Not subscribed              | 25   | Session status check                                                                                                                             |

---

## 5. Verification, audit & security

### 5.1 Audit matrix (`audit_matrix.ts`)

`RigorousAuditMatrix.runFullPreFlightAudit()` runs **11 mandatory audits**, each with a deterministic proof, a negative control, and an epistemic classification:

1. Cassini identity (n=1..100)
2. Born norm conservation (∑P=1 exact rational)
3. Q[√5] field closure (norm multiplicativity, inverse existence)
4. 32-face topology (partition preservation, collision elimination)
5. Lucas-Pisot invariance (Born-rule invariance under scalar scaling)
6. Bitcoin 80-byte header + SHA-256d (with negative control)
7. Zeckendorf non-consecutive decomposition
8. Q5 memory footprint (2000-iteration zero-leak chain)
9. Stratum post-handshake workflow (5-phase lifecycle)
10. First-principles quantum (QFT/Grover unitarity, Schmidt decomposition)
11. Kellogg-Grover degenerate limit (Theorem A.1)

### 5.2 Adversarial checks (`adversarial_checks.ts`)

`AdversarialIntegrityEngine` deliberately attacks the engine to prove it **hard-fails** (circuit breaker trips) on:

- IEEE-754 epsilon injection into rational amplitudes
- SL(2,Z) companion matrix entry perturbation
- Lucas number L_n tampering
- Phase oracle 10⁻⁷ decay
- 256-bit denominator overflow

### 5.3 Verification suite (`verification_suite.ts`)

`VerificationSuiteEngine` runs **14 tests** across 4 categories × 4 "Orders of Truth" (MATHEMATICAL, COMPUTATIONAL, EMPIRICAL, HYPOTHESIS):

- UNIT (4): Q[√5] inverse, Cassini, Pisot, header packing
- INTEGRATION (4): 32-node walk conservation, hybrid superposition, nonce analyzer, Zeckendorf router
- E2E (3): full block assembly, clean-jobs stale prevention, BIP-22 retargeting
- CLIENT_HANDOVER (3): zero-leak memory, Stratum SLA (<50ms, >99.8%), sovereign determinism

### 5.4 Al Haras security gateway (`src/security/al_haras_gateway.ts`)

Replaces JWT/OAuth with **exact structural resonance authentication** over Q[√5] and an 11D manifold. Protects only `/api/sovereign/*`, `/api/hyba/*`, `/api/alharas/*`. On failure: **silently destroys the socket** (no HTTP response). Three checks:

1. Zeckendorf index non-consecutiveness
2. Cassini invariant det(M^n) = (−1)^n
3. Yang-Mills mass gap Δ > 0

---

## 6. Hardware (SystemVerilog RTL)

### 6.1 The Q5 ASIC modules

| File                                 | Module                     | Role                                                                                                                                                                                                                                           |
| ------------------------------------ | -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `q5_types_pkg.sv`                    | (package)                  | 256-bit `q_rational_t`, `q5_exact_amp_t` (a+b√5), `sl2z_matrix_t`, `zeck_addr_t`, opcode enum. Single source of truth for widths.                                                                                                              |
| `q5_exact_alu.sv`                    | `q5_exact_alu`             | Zero-FPU rational ALU. `OP_ORACLE_PHASE_INV` (negate), `OP_LUCAS_PISOT_MUL` (scale by L_n/L_{n+1} via integer multiply). **Inline SVA `assert_lucas_scale`** (line 105) — fatal on cross-multiplication mismatch.                              |
| `q5_top_asic.sv`                     | `q5_top_asic`              | Top-level. Stratum V1 ports (`job_valid`, `golden_nonce`). Companion matrix M^n evolution, Lucas sequence. **Inline SVA `assert_cassini`** (line 84) — fatal if det(M^n) ≠ (−1)^n. **Circuit breaker** halts clock on violation (lines 91–97). |
| `q5_zeckendorf_hbm3e_ctrl.sv`        | `q5_zeckendorf_hbm3e_ctrl` | Fibonacci bank memory controller. Amputates L1/L2/L3. Greedy Zeckendorf encoder → conflict-free HBM3e routing (16 ch / 512 banks). **SVA `assert_zeckendorf`** (line 96) — fatal if adjacent 1s.                                               |
| `golden_invariant_monitor.sv`        | GIMB                       | Combinational monitor for all 9 invariants. `all_ok` AND of 9 checks; `halt_trip_out` on any failure.                                                                                                                                          |
| `golden_ontology_transform.sv`       | —                          | Fibonacci butterfly FFT replacement with Binet exact basis. Inline Binet/Cassini/orthogonality checks.                                                                                                                                         |
| `emergent_intelligence_detector.sv`  | —                          | 5-criteria intelligence detector (φ self-similarity, Lucas compression, Cassini alternation, Pisot decay, Fibonacci hierarchy). Score 0–5.                                                                                                     |
| `yang_mills_gap_monitor.sv`          | —                          | Exact rational spectral gap Δ = λ₁ − λ₀ via integer cross-products. Asserts Δ > 0.                                                                                                                                                             |
| `assertions/golden_invariant_sva.sv` | (binding)                  | 9 `assert property` + 10 `cover property` wrapping the GIMB outputs. The formal assertion layer for model checkers (SymbiYosys/JasperGold).                                                                                                    |
| `tb/q5_formal_sva_tb.sv`             | (testbench)                | Instantiates `q5_top_asic`, 2.4 GHz clock, Stratum job (n_inner=20, k=4548), runs 1000 cycles. Pass = circuit breaker stays low.                                                                                                               |

### 6.2 The verification mirror

The same 9 invariants are verified in three layers:

1. **Silicon datapath** — inline SVA in each `.sv` module (fatal `$fatal` on violation)
2. **Formal/simulation** — `q5_formal_sva_tb.sv` runs 1000 cycles at 2.4 GHz
3. **Python golden model** — `q5_golden_formal.py` mirrors all 9 in exact Python arithmetic; `turing_core.py` provides the Fibonacci/Lucas/Cassini/Zeckendorf reference

---

## 7. Python verification & CI

| File                                                      | Role                                                                                                                                                                                                                                                                                                              |
| --------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `turing_core.py`                                          | Zero-dependency Python golden model. `fibonacci`/`lucas`/`cassini_check`/`zeckendorf_encode`. 32-node dual overlay (icosa + dodeca = 32). `PythiaMiningEngine` with midstate chunking (64B + 12B). `run_self_verification()` asserts all invariants.                                                              |
| `legacy/scripts/euclid_tapeout_checklist.py`              | 12-item checklist (H1–H12). `run_full_tapeout_audit()` runs 4 dynamic checks (FPU ban, Cassini SVA, Zeckendorf routing, Stratum decoupling). `assert_ready_for_tapeout()` is the CI kill switch.                                                                                                                  |
| `legacy/papers/discovery/euclid_tapeout_checklist.py`     | Authoritative checklist: 12 closed items (H1–H12) + 3 open silicon-pending gaps (P1–P3: High-NA EUV, CoWoS packaging, datacenter field test). 5 dynamic engines: FPU static analysis, SVA verification (100 powers), Zeckendorf routing (500 addresses), Stratum handshake signal check, GIMB delegation. |
| `legacy/papers/discovery/q5_golden_formal.py`             | `verify_golden_invariants_exact()` — all 9 invariants in exact Python. `FORMAL_JOBS` dict maps each invariant to its SVA property name for SymbiYosys flows.                                                                                                                                                      |
| `legacy/papers/discovery/clay_checklist.py`               | **Intellectual honesty layer.** Tracks Yang-Mills mass-gap proof obligations (C1–C10 closed, G1–G6 open). `assert_no_established()` guarantees 0 items may be labelled ESTABLISHED without a continuum proof.                                                                                                     |
| `tests/test_euclid_tapeout.py`                            | CI unittest suite described here is **not present in the current tree** — the checklist's own `run_full_tapeout_audit()` is the executable gate. Related coverage: `chronus/mla1517_platform/python/test_euclid_core.py`.                              |

### Tape-out checklist items (H1–H12)

| ID  | Item                                          | Status                  |
| --- | --------------------------------------------- | ----------------------- |
| H1  | Zero FPU policy (static analysis ban)         | FORMAL_RTL_PROVEN       |
| H2  | Cassini SVA (det(M^n) = (−1)^n)               | FORMAL_RTL_PROVEN       |
| H3  | Zeckendorf non-consecutive routing            | FORMAL_RTL_PROVEN       |
| H4  | Stratum V1 interface decoupling               | FORMAL_RTL_PROVEN       |
| H5  | Lucas-Pisot exact scaling                     | FORMAL_RTL_PROVEN       |
| H6  | Unimodular SL(2,Z) inversion                  | EXACT_ARITHMETIC        |
| H7  | Holographic min-cut (2nm GAAFET floorplan)    | FPGA_EMULATION_VERIFIED |
| H8  | Non-zero companion structure (HBM3e roofline) | FPGA_EMULATION_VERIFIED |
| H9  | GIMB 9 golden discoveries                     | FORMAL_RTL_PROVEN       |
| H10 | Golden ontology transform                     | FORMAL_RTL_PROVEN       |
| H11 | Emergent intelligence detector                | FORMAL_RTL_PROVEN       |
| H12 | Yang-Mills gap monitor                        | FORMAL_RTL_PROVEN       |

Open silicon-pending gaps: **P1** (High-NA EUV mask set), **P2** (CoWoS packaging), **P3** (datacenter field test) — all `SILICON_PENDING`.

---

## 8. Server API surface (`server.ts`)

Single Express app on port 3000. ~90 endpoints grouped by subsystem. No background TCP servers (only outbound `net.Socket` in `/api/stratum/probe`). BigInt serialized as strings globally (line 54).

| Subsystem           | Endpoints                                                                | Notable                                            |
| ------------------- | ------------------------------------------------------------------------ | -------------------------------------------------- |
| Health / Prometheus | `/metrics`, `/api/v1/healthz`, `/api/v1/readyz`, `/api/health`           | Kubernetes probes                                  |
| Audit               | `/api/audit/run-all`, `/api/audit/q5-memory-diagnostics` (×2)            | 11 pre-flight audits                               |
| Kellogg             | `/api/kellogg/*` (6 endpoints)                                           | TURING, COGITO, AL HARAS, full-stack               |
| Stratum             | `/api/stratum/*` (11 endpoints)                                          | Circuit breaker, pools, BIP310, probe, credentials |
| M3 iGPU             | `/api/m3-chronus/*`, `/api/chronus/*` (6 endpoints)                            | Hardware scaling, pool miner                       |
| Bitcoin / Quantum   | `/api/bitcoin/block-header`, `/api/quantum/grover-run`                   |                                                    |
| Difficulty          | `/api/v1/difficulty/*` (2)                                               | BIP-22 retargeting                                 |
| Mempool             | `/api/v1/mempool/*` (2)                                                  | BIP-141 optimization                               |
| Repositories        | `/api/v1/{workers,sessions,jobs,shares,grover,audit,telemetry}`          | In-memory DB                                       |
| Mining control      | `/api/v1/mining/{trigger-step,toggle}`, `/api/v1/telemetry/stream` (SSE) |                                                    |
| Q5 co-processor     | `/api/q5/*` (12 endpoints)                                               | Spec, benchmark, RTL, tape-out, golden silicon     |
| Clay checklist      | `/api/quantum/clay-checklist`                                            | Yang-Mills honesty                                 |
| Al Haras            | `/api/alharas/generate-headers`, `/api/sovereign/*` (2)                  | Topological auth                                   |
| Quantum walk        | `/api/quantum-walk/*` (9 endpoints)                                      | DTQW/CTQW/AQO/hybrid                               |
| Consciousness       | `/api/consciousness/*` (5 endpoints)                                     | 32-face entanglement                               |
| Nonce analyzer      | `/api/nonce/*` (3 endpoints)                                             | mempool.space pull                                 |
| Verification        | `/api/tests/*` (5 endpoints)                                             | 14-test suite                                      |
| Visitor analytics   | `/api/analytics/*` (3 endpoints)                                         | Adaptive briefing                                  |
| SPA fallback        | `GET *`                                                                  | `dist/index.html` (production)                     |

Three endpoints (`/api/q5/tapeout-checklist`, `/api/quantum/clay-checklist`, `/api/q5/golden-silicon/invariants`) run Python scripts synchronously via `execSync` (blocks the event loop).

---

## 9. Frontend (`src/`)

`App.tsx` is a tab-based SPA with 25+ panels. Key behaviors:

- **60-second auto-audit loop** when mining is active (line 131)
- Mining status polled every 2.5s (line 110)
- Audit results persisted to Firestore
- Visitor analytics tracked on tab change

37 panel components in `src/components/` — see the table in the research notes. Highlights:

- `ResearchLandingPanel` — institutional briefing / paper catalog (default tab)
- `LiveMiningConsolePanel` — real-time mining with play/pause/step
- `Q5CoprocessorPanel` — ASIC spec, benchmark, RTL, tape-out checklist (142KB, the largest panel)
- `StratumWorkflowConsole` — 5-phase Stratum lifecycle visualization
- `VerificationSuitePanel` — 14-test runner
- `CassiniMonitorPanel` — D3 real-time Cassini identity monitor
- `KelloggFullStackPanel` — TURING/COGITO/AL HARAS/EUCLID/SALAMANDER

---

## 10. Infrastructure

| Component  | Config                                          | Notes                                                                                                                      |
| ---------- | ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Firestore  | `firestore.rules`, `firebase-blueprint.json`    | Default-deny; immutable audit trails (no update/delete on `audit_reports`); `shares` subcollection create-only             |
| Prometheus | `legacy/infra/prometheus/prometheus.yml`, `alerts.yml` | 6 alerts: exact-math violation, audit hash mismatch, RTT > 250ms, stratum disconnect, stale shares, stale mempool snapshot |
| Build      | `package.json`                                  | `dev` (tsx + Vite middleware), `build` (Vite + esbuild CJS bundle), `start` (production node)                              |
| Node       | `engines`                                       | `>=22.0.0`                                                                                                                 |

---

## 11. How to run

```bash
npm install
npm run dev      # http://localhost:3000 (Vite dev + tsx server)
npm run build    # dist/public + dist/server.cjs
npm start        # production
npm run lint     # tsc --noEmit
npm test         # node --test (TS tests)
python -m pytest tests/  # Python CI suite
```

Set `GEMINI_API_KEY` in `.env.local` for Gemini AI features.

---

## 12. Key cross-references

```
exact_math.ts (BigFraction, Q5, ExactSequenceMath)
    ├─> quantum_engine.ts (Grover over BigFraction, 32-face)
    ├─> q5_reference.ts (Grover over Q5, hardware projections, audits)
    ├─> q5_coprocessor.ts (ASIC spec, dense vs reduced proof)
    ├─> q5_golden_silicon.ts (9 invariants, ontology transform, Yang-Mills gap)
    │       └─> q5_rtl_specs.ts (emits .sv RTL + SVA)
    │               └─> legacy/hardware/rtl/*.sv (materialized silicon)
    ├─> hodge_bridge.ts (Zeckendorf + Lucas → 11D)
    └─> blockchain_consciousness.ts (Cassini over 496 face pairs)

mining_service.ts (orchestrator)
    ├─> quantum_engine.ts (Grover search)
    ├─> bitcoin_header.ts (80-byte header, SHA-256d)
    ├─> stratum_protocol.ts (MeetsTarget gate, clean_jobs, circuit breaker)
    ├─> repositories.ts (in-memory DB)
    ├─> event_bus.ts (pub/sub)
    └─> mempool_service.ts (BIP-141 template)

turing_core.py (Python golden model)
    └─> legacy/scripts/euclid_tapeout_checklist.py (CI kill switch — suite file not committed)
            ├─> 12 items, FPU ban, SVA
            ├─> q5_golden_formal.py (9 invariants exact)
            └─> clay_checklist.py (Yang-Mills honesty: 0 ESTABLISHED)
```
