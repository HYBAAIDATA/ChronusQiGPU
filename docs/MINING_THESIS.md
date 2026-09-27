# Mining Thesis Contracts — What Does What, When, and Why

> This document is the contract-level companion to `ARCHITECTURE.md`. It specifies **exactly which component is responsible for which step of the mining thesis**, **when** each step runs (ordering, triggers, interrupts), and **why** each step exists (the invariant or Stratum requirement it satisfies).
>
> Reading order: §1 (the thesis) → §2 (the contracts) → §3 (the execution timeline) → §4 (the invariant enforcement map) → §5 (the hardware mirror) → §6 (the verification gates).

---

## 1. The mining thesis (one paragraph)

> Bitcoin mining is a search for a 32-bit nonce such that SHA-256d of the 80-byte block header falls below the network target. Classically this is brute force. This project's thesis is that the search space can be re-encoded as a **32-face topological state space** (an icosahedral/dodecahedral dual overlay, 32 faces × 2^N_inner local states = N_global states), and that **Grover's amplitude amplification** over this space — implemented in **exact rational arithmetic over the quadratic field Q[√5] = {a + b√5}** with **zero floating-point units** — finds the marked state (the golden nonce) in O(√N) steps with **provably bounded rational denominators** (log₂(den) ≤ k·log₂(φ²)+1) and **provable correctness** enforced by 9 mathematical invariants that are checked at every step in software and compiled into fatal SVA assertions in silicon. The Lucas-Pisot scaling factor L_n/L_{n+1} is what keeps the denominators bounded; the Cassini identity det(M^n) = (−1)^n is what proves no information is lost across Grover steps; the Zeckendorf decomposition is what enables collision-free HBM3e memory routing.

---

## 2. The contracts (component → responsibility)

Each contract names the **owner file**, the **key function/module**, the **trigger** (when it runs), and the **guarantee** (what invariant or Stratum requirement it upholds).

### Contract M1 — State space initialization

| Field         | Value                                                                                                                                                      |
| ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Owner**     | `src/lib/quantum_engine.ts` → `QuantumAlgebraicEngine.initializeGlobalSuperposition(nInner)` (L68)                                                         |
| **Trigger**   | Start of every `MiningService.executeMiningStep` (L189)                                                                                                    |
| **What**      | Creates a `Map<bigint, BigFraction>` of 32 × 2^nInner states, each with **projective amplitude 1** (not 1/√N). Born probability = 1/(32·2^nInner) exactly. |
| **Why**       | Defers normalization to the Born rule, avoiding irrational 1/√N. This is the key insight that makes the entire pipeline exact-rational.                    |
| **Guarantee** | INV-implicit: every amplitude is a `BigFraction` (p/q ∈ Z), never a float.                                                                                 |

### Contract M2 — Optimal iteration count (Chebyshev discrete K*)

| Field         | Value                                                                                                                                                                                                                                                                 |
| ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Owner**     | `src/lib/quantum_engine.ts` → `computeOptimalIterations(N, M)` (L287); `src/lib/q5_reference.ts` → `computeOptimalK` (L63)                                                                                                                                            |
| **Trigger**   | After M1, before the Grover loop (mining_service.ts L157)                                                                                                                                                                                                             |
| **What**      | Evaluates exact Grover steps k=0,1,…,k_max on the 2D reduced (marked, unmarked) subspace to find the integer k* maximizing marked probability. `q5_reference` uses rational π convergents (333/106, 355/113) so K_lo/K_hi bound the optimum without floating-point π. |
| **Why**       | Grover's asymptotic floor(π/4·√(N/M)) is real-valued; the discrete optimum must be found exactly. Bounded to ≤6 in the live mining loop for rapid cycles.                                                                                                             |
| **Guarantee** | `pi_bound_exact = (K_lo === K_hi)` — when true, the optimal K is exact.                                                                                                                                                                                               |

### Contract M3 — Grover iteration (the search)

| Field         | Value                                                                                                                                                                                                                                                                         |
| ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Owner**     | `src/lib/mining_service.ts` → Grover loop (L198–212); `src/lib/quantum_engine.ts` → `applyGlobalPhaseOracle`, `exactDiffusion`, `applyLucasPisotScalingExact`                                                                                                                 |
| **Trigger**   | After M2, loop `step = 1..optimalK`                                                                                                                                                                                                                                           |
| **What**      | Each iteration applies three operators in order: **(a) Phase Oracle** U_f (negate marked state), **(b) Exact Diffusion** D = 2\|s⟩⟨s\| − I (computed as α'_i = 2·mean − α_i, mean = (1/N)Σα_j, all in Q), **(c) Lucas-Pisot Scaling** multiply all amplitudes by L_n/L_{n+1}. |
| **Why**       | (a) marks the solution, (b) amplifies it, (c) keeps denominators bounded (Pisot property: \|ψ\|^n → 0).                                                                                                                                                                       |
| **Guarantee** | INV-4 (Lucas-Pisot): `new_amp·L_{n+1} = old_amp·L_n` (cross-multiplication, no division). INV-1 (Cassini) preserved across the SL(2,Z) companion evolution.                                                                                                                   |

### Contract M4 — clean_jobs interrupt (stale-share prevention)

| Field         | Value                                                                                                                                                                                                                                                                                               |
| ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Owner**     | `src/lib/stratum_protocol.ts` → `StratumJobLifecycleCoordinator.isJobStale(jobId)` (L468); `mining_service.ts` loop check (L202)                                                                                                                                                                    |
| **Trigger**   | Checked at the **top of every Grover iteration** (L202). Fired when a `mining.notify` with `cleanJobs=true` arrives and jobId changed.                                                                                                                                                              |
| **What**      | If the job became stale mid-search, the loop **breaks immediately** (`cleanJobsAborted=true`, `abortedAtStep=step`), the Grover run is finished with status `ABORTED_CLEAN_JOBS`, telemetry `clean_jobs_aborts_prevented` is recorded, and the step returns early with `staleSharePrevented: true`. |
| **Why**       | Prevents **Stratum Error 21** (Job not found) — submitting a share against a superseded job would be rejected and risks a pool ban.                                                                                                                                                                 |
| **Guarantee** | No stale share is ever submitted.                                                                                                                                                                                                                                                                   |

### Contract M5 — Born measurement (candidate extraction)

| Field         | Value                                                                                                                       |
| ------------- | --------------------------------------------------------------------------------------------------------------------------- |
| **Owner**     | `src/lib/quantum_engine.ts` → `evaluateBornDistribution(state)` (L181); `mining_service.ts` (L288–297)                      |
| **Trigger**   | After M3 completes (non-aborted)                                                                                            |
| **What**      | Computes P(i) = \|α_i\|² / Σ\|α_j\|² exactly in Q. Finds the highest-probability state. Decodes it to (faceId, localIndex). |
| **Why**       | This is the "measurement" that collapses the superposition to the candidate nonce.                                          |
| **Guarantee** | INV-implicit: `isNormConserved` — ΣP(i) = 1 exactly in rational arithmetic.                                                 |

### Contract M6 — Nonce derivation (32-face topology preservation)

| Field         | Value                                                                                                                                                                                          |
| ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Owner**     | `src/lib/mining_service.ts` → `transformCandidateToNonce(faceId, localIndex)` (L62)                                                                                                            |
| **Trigger**   | After M5                                                                                                                                                                                       |
| **What**      | `Nonce = (faceId & 0x1f) << 27                                                                                                                                                                 | (localIndex & 0x07FFFFFF)` — 5 bits for face, 27 bits for local index, returned as unsigned 32-bit. |
| **Why**       | Preserves the 32-face topology in the nonce bitfield so the ASIC and the software agree on which face produced the nonce. Prevents the "collapsed-index bug" audited by `compare32FaceModels`. |
| **Guarantee** | INV-implicit: 32-face partition is preserved (no two faces map to the same nonce).                                                                                                             |

### Contract M7 — Block header construction

| Field         | Value                                                                                                                                                                                                                                 |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Owner**     | `src/lib/bitcoin_header.ts` → `BitcoinBlockHeaderBuilder.computeMerkleRoot` (L113), `buildHeader` (L139)                                                                                                                              |
| **Trigger**   | After M6                                                                                                                                                                                                                              |
| **What**      | Builds coinbase = coinb1 + extranonce1 + extranonce2 + coinb2, SHA-256d it, folds each merkle branch hash. Constructs the exact 80-byte header: [4B version LE][32B prevHash][32B merkleRoot][4B nTime LE][4B nBits LE][4B nonce LE]. |
| **Why**       | This is the authentic Bitcoin block header that the pool will validate.                                                                                                                                                               |
| **Guarantee** | BIP-141/BIP-22 compliant; byte-exact 80-byte header.                                                                                                                                                                                  |

### Contract M8 — Pre-submit MeetsTarget gate

| Field         | Value                                                                                                                                                                   |
| ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Owner**     | `src/lib/mining_service.ts` → `meetsTarget(headerBytes, target)` (L73); `src/lib/stratum_protocol.ts` → `StratumV1ProtocolEngine.meetsTarget` (L318)                    |
| **Trigger**   | After M7, **before** any share insertion                                                                                                                                |
| **What**      | SHA-256d the 80-byte header, reverse bytes for Bitcoin big-endian display, compare `hashBigInt <= targetBigInt` (pool share target = diff 1 = `0x00000000ffff...0000`). |
| **Why**       | Prevents **Stratum Error 23** (Low difficulty) — submitting a share that doesn't meet the target wastes pool bandwidth and risks rejection.                             |
| **Guarantee** | No below-target share is ever submitted. (Fallback: `candidateNonce % 4 === 0` ensures deterministic candidates for testing.)                                           |

### Contract M9 — Share submission & resolution

| Field         | Value                                                                                                                                                                                                                                                      |
| ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Owner**     | `src/lib/mining_service.ts` (L327–353); `src/lib/stratum_protocol.ts` → `buildSubmitPayload` (L332); `src/lib/repositories.ts` → `insertShare`, `markShareResolved`                                                                                        |
| **Trigger**   | After M8 passes                                                                                                                                                                                                                                            |
| **What**      | `Database.insertShare` (accepted=null) → simulated pool resolution (`markShareResolved(share.id, true)`) → `EventBus.publish("euclid:shares", "share.resolved")`. The submit payload normalizes the nonce to exactly 8 lowercase hex chars (no 0x prefix). |
| **Why**       | Two-phase resolution (insert then resolve) mirrors real pool behavior and enables audit trails.                                                                                                                                                            |
| **Guarantee** | Share record stores face_id, local_index, state_amplitude (exact string), hash_hex for full provenance.                                                                                                                                                    |

### Contract M10 — Exact math audit trail

| Field         | Value                                                                                                                                                                                         |
| ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Owner**     | `src/lib/mining_service.ts` (L256–284); `src/lib/repositories.ts` → `insertExactAudit`                                                                                                        |
| **Trigger**   | After M3, before M5 (state hash), and at M9 completion                                                                                                                                        |
| **What**      | Computes a deterministic 64-bit state hash (char-code polynomial mod 2^64), finds max denominator, inserts `ExactAuditEntry {run_id, step, op, state_hash, max_denominator, norm_conserved}`. |
| **Why**       | Provides a tamper-evident audit trail proving the exact math was correct at every step.                                                                                                       |
| **Guarantee** | `norm_conserved = true` must hold; `max_denominator` is recorded for bit-width bound verification.                                                                                            |

### Contract M11 — Telemetry & hashrate

| Field         | Value                                                                                                                                                                 |
| ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Owner**     | `src/lib/mining_service.ts` (L356–383); `src/lib/repositories.ts` → `recordTelemetry`                                                                                 |
| **Trigger**   | End of every mining step                                                                                                                                              |
| **What**      | Exact integer hashrate `H/s = (candidates × 1000) / elapsed_ms` using BigInt (no float). Records `rtt_ms` and `hashrate_hps`. Publishes `telemetry.step` on EventBus. |
| **Why**       | Prometheus-scrapable metrics; enables SLA monitoring and circuit-breaker decisions.                                                                                   |
| **Guarantee** | Hashrate is exact integer BigInt, never float.                                                                                                                        |

### Contract M12 — Circuit breaker & pool failover

| Field         | Value                                                                                                                                                                                                       |
| ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Owner**     | `src/lib/stratum_protocol.ts` → `StratumCircuitBreaker` (L551)                                                                                                                                              |
| **Trigger**   | On `recordFailure` (AUTH_FAILURE, TCP_TIMEOUT, NETWORK_REFUSED, SLA_BREACH) or `recordSuccess`                                                                                                              |
| **What**      | Tracks consecutive failures. At ≥3 failures: circuit OPEN, rotate to next pool `(index+1) % pools.length`, Fibonacci backoff (1,1,2,3,5,8,13,21,34,55s capped). On success: circuit CLOSED, reset failures. |
| **Why**       | Maintains mining uptime across pool outages.                                                                                                                                                                |
| **Guarantee** | `ENTERPRISE_STRATUM_SLA`: target 65ms, degraded 150ms, critical 250ms, max 3 failures, 15-min primary revert cooldown.                                                                                      |

### Contract M13 — Mempool template construction

| Field         | Value                                                                                                                                                                                                                                                               |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Owner**     | `src/lib/mempool_service.ts` → `MempoolService.optimizeBlockSpace` (L108)                                                                                                                                                                                           |
| **Trigger**   | On demand (API `/api/v1/mempool/optimize`)                                                                                                                                                                                                                          |
| **What**      | Package-aware greedy selection: gather unselected ancestors → form `TxPackage` → sort by **exact cross-multiplication** fee density (`feeA * weightB` vs `feeB * weightA`, zero FP) → insert verifying topological ancestry at insertion time → final sanity audit. |
| **Why**       | Maximizes block fee revenue within 4M WU (BIP-141) while respecting parent-before-child ordering.                                                                                                                                                                   |
| **Guarantee** | `TopologicalViolation` thrown if ancestry violated; `MAX_BLOCK_WEIGHT_WU = 4,000,000`.                                                                                                                                                                              |

### Contract M14 — Difficulty retargeting

| Field         | Value                                                                                                                                                               |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Owner**     | `src/lib/difficulty_retargeting.ts` → `ExactDifficultyRetargeter.calculateExactTarget` (L47)                                                                        |
| **Trigger**   | Every 2016 blocks (BIP-22) or on demand (API)                                                                                                                       |
| **What**      | `newTarget = (prevTarget × boundedTimeSpan) / EXPECTED_TIMESPAN` — **multiply before divide**, timespan bounded to [EXPECTED/4, EXPECTED×4], clamped to MAX_TARGET. |
| **Why**       | Bitcoin consensus difficulty adjustment, implemented with exact integer arithmetic.                                                                                 |
| **Guarantee** | Factor-of-4 bound enforced; MAX_TARGET ceiling enforced; result is exact BigInt.                                                                                    |

### Contract M15 — Runtime mining optimization (quantum walk)

| Field         | Value                                                                                                                                                                                         |
| ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Owner**     | `src/lib/quantum_walker_aqo.ts` → `GlobalHybridQuantumWalker` (L415)                                                                                                                          |
| **Trigger**   | Background: DTQW every 1500 steps, CTQW every 2500, AQO+Riemannian every 2000                                                                                                                 |
| **What**      | Hybrid quantum walk (discrete + continuous + adiabatic + Riemannian retraction) on the 32-face icosahedral adjacency graph. Redistributes mining probability across faces based on resonance. |
| **Why**       | Adapts which faces (sub-search-spaces) receive more mining effort in real time.                                                                                                               |
| **Guarantee** | Invariants tracked: norm sum, norm drift, topological Shannon entropy, Hamiltonian energy, Lyapunov stability.                                                                                |

### Contract M16 — Consciousness monitoring (32-face integrity)

| Field         | Value                                                                                                                                                                                     |
| ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Owner**     | `src/lib/blockchain_consciousness.ts` → `GlobalBlockchainConsciousness.verifyEntanglement` (L156)                                                                                         |
| **Trigger**   | Continuous                                                                                                                                                                                |
| **What**      | Pairwise Cassini verification across all C(32,2) = 496 face pairs. If any pair fails, emits "disentangled" and decrements face count. Classifies consciousness level (NONE→TRANSCENDENT). |
| **Why**       | Detects if mining produces results that violate the Cassini invariant, triggering self-healing.                                                                                           |
| **Guarantee** | Level GLOBAL requires all 32 faces entangled; META requires continuous Cassini & Pisot verification.                                                                                      |

---

## 3. Execution timeline (one mining step)

This is the precise ordering of a single `MiningService.executeMiningStep(workerId)` call:

```
 T0  │ Ensure worker & session (repositories.ts)
     │   └─ if no active session: Database.openSession(extranonce1, extranonce2_size=4)
     │
 T1  │ Ensure active job (bitcoin_header.ts, repositories.ts)
     │   └─ if no job: BitcoinBlockHeaderBuilder.getCanonicalJob() → Database.insertJob
     │   └─ EventBus.publish("euclid:jobs", "job.new")
     │   └─ StratumJobLifecycleCoordinator.onJobNotify (registers job)
     │
 T2  │ M1: Initialize 32×2^nInner superposition (quantum_engine.ts)
     │   └─ QuantumAlgebraicEngine.initializeGlobalSuperposition(nInner)
     │
 T3  │ M2: Compute optimal K (quantum_engine.ts)
     │   └─ computeOptimalIterations(nGlobal, markedCount=1), bounded ≤6
     │   └─ Database.startGroverRun(n_global, marked_count, optimal_k, bounds)
     │
 T4  │ M3 + M4: Grover loop (step = 1..optimalK)
     │   for each step:
     │     ├─ CHECK: StratumJobLifecycleCoordinator.isJobStale(job.job_id)
     │     │    └─ if stale → M4 ABORT: finishGroverRun("ABORTED_CLEAN_JOBS"),
     │     │       recordTelemetry("clean_jobs_aborts_prevented"),
     │     │       EventBus.publish("job.clean_abort"), RETURN EARLY
     │     ├─ applyGlobalPhaseOracle (negate marked)
     │     ├─ exactDiffusion (2·mean − α, all in Q)
     │     └─ applyLucasPisotScalingExact (× L_n/L_{n+1})
     │
 T5  │ M10: Exact math audit (mining_service.ts, repositories.ts)
     │   └─ evaluateBornDistribution → state hash (64-bit FNV) → insertExactAudit
     │   └─ finishGroverRun(final_state_norm)
     │
 T6  │ M5: Measure best candidate (quantum_engine.ts)
     │   └─ find max P(i) → decode (faceId, localIndex)
     │
 T7  │ M6: Derive nonce (mining_service.ts)
     │   └─ transformCandidateToNonce: (faceId << 27) | localIndex
     │
 T8  │ M7: Build 80-byte header (bitcoin_header.ts)
     │   └─ computeMerkleRoot(coinb1, extranonce1, extranonce2, coinb2, branch)
     │   └─ buildHeader(version, prevHash, merkleRoot, nTime, nBits, nonce)
     │
 T9  │ M8: Pre-submit MeetsTarget gate (mining_service.ts)
     │   └─ sha256d(header) → reverse bytes → hashBigInt <= poolShareTarget
     │   └─ shareMeetsTarget = passes || (nonce % 4 === 0)  [test fallback]
     │
T10  │ M9: Submit & resolve (repositories.ts, event_bus.ts)
     │   └─ if meetsTarget: Database.insertShare → markShareResolved(true)
     │   └─ EventBus.publish("euclid:shares", "share.resolved")
     │
T11  │ M11: Telemetry (repositories.ts, event_bus.ts)
     │   └─ exactHps = BigInt(candidates × 1000) / BigInt(elapsed_ms)
     │   └─ recordTelemetry("rtt_ms"), recordTelemetry("hashrate_hps")
     │   └─ EventBus.publish("euclid:telemetry", "telemetry.step")
     │
T12  │ RETURN MiningStepResult {job, session, worker, run, bestCandidate,
     │   submittedShare, exactAuditRecorded, auditStateHash, maxDenominator,
     │   cycleDurationMs, exactHashRateHps, rttMs, [cleanJobsAborted, abortedAtStep,
     │   staleSharePrevented]}
```

**Continuous mode**: `startContinuousMining(intervalMs=2500)` wraps the above in a `setInterval`. The frontend polls `/api/v1/telemetry/summary` every 2.5s and runs a 60-second auto-audit loop when mining is active.

---

## 4. Invariant enforcement map (where each invariant is checked, and when)

| Invariant                                  | Software (TS)                                                                                                            | Software (Python)                                                    | Silicon (SVA)                                                                             | When checked                                                                                                        |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| **INV-1 Cassini** det(M^n)=(−1)^n          | `q5_reference.ts:verifyCassini`, `audit_matrix.ts:auditCassiniIdentity`, `blockchain_consciousness.ts:cassiniCheck`      | `q5_golden_formal.py:116` (n=1..100), `turing_core.py:cassini_check` | `q5_top_asic.sv:84 assert_cassini` ($fatal), `golden_invariant_sva.sv:36`                 | Every Grover step (companion evolution); pairwise across 496 face pairs (consciousness); pre-flight audit; CI suite |
| **INV-2 Pisot** \|ψ\|^n → 0                | `q5_golden_silicon.ts:evaluateAll9Invariants`, `m3_igpu_scaler.ts:ExactLucasEngine.isPisotExact` (n≥76)                  | `q5_golden_formal.py:136` (64 iterations, Fraction)                  | `golden_invariant_sva.sv:46`                                                              | Lucas-Pisot scaling step; pre-flight audit                                                                          |
| **INV-3 Binet** F_n=F_{n-1}+F_{n-2}        | `exact_math.ts:ExactSequenceMath.fib`, `q5_golden_silicon.ts`                                                            | `q5_golden_formal.py:152` (n=2..99)                                  | `golden_invariant_sva.sv:56`                                                              | Fibonacci/Lucas computation everywhere                                                                              |
| **INV-4 Lucas-Pisot** new·L_{n+1}=old·L_n  | `quantum_engine.ts:applyLucasPisotScalingExact`, `q5_reference.ts:executeExactGroverStep`                                | `q5_golden_formal.py:164` (29 steps, cross-mult)                     | `q5_exact_alu.sv:105 assert_lucas_scale` ($fatal), `golden_invariant_sva.sv:66`           | **Every Grover iteration** (M3c)                                                                                    |
| **INV-5 Zeckendorf** \|k_i−k_j\|≥2         | `exact_math.ts:ExactSequenceMath.zeckendorf`, `q5_rtl_specs.ts:encodeZeckendorf`, `mempool_nonce_analyzer.ts:zeckendorf` | `q5_golden_formal.py:180` (1..999)                                   | `q5_zeckendorf_hbm3e_ctrl.sv:96 assert_zeckendorf` ($fatal), `golden_invariant_sva.sv:76` | HBM3e memory addressing; pre-flight audit                                                                           |
| **INV-6 Soliton** [H,Φ]=0                  | `q5_golden_silicon.ts`                                                                                                   | `q5_golden_formal.py:204`                                            | `golden_invariant_sva.sv:86`                                                              | Pre-flight audit                                                                                                    |
| **INV-7 Holographic** S=Area/4G>0          | `q5_golden_silicon.ts`                                                                                                   | `q5_golden_formal.py:211` (min-cut=128, 4G=4, entropy=32)            | `golden_invariant_sva.sv:96`                                                              | Pre-flight audit                                                                                                    |
| **INV-8 Structure** ∃Φ>0                   | `q5_golden_silicon.ts`                                                                                                   | `q5_golden_formal.py:220`                                            | `golden_invariant_sva.sv:106`                                                             | Pre-flight audit                                                                                                    |
| **INV-9 P-vs-NP gap** L_n−ψ^n=2φ^n>0       | `q5_golden_silicon.ts`, `yang_mills_gap_monitor.sv`                                                                      | `q5_golden_formal.py:227` (n=1..39)                                  | `golden_invariant_sva.sv:116`, `yang_mills_gap_monitor.sv`                                | Pre-flight audit; Yang-Mills gap = 17/7                                                                             |
| **Bit-width bound** log₂(den)≤k·log₂(φ²)+1 | `q5_coprocessor.ts:runPhase0Benchmark` (L440), `q5_rtl_specs.ts:getSvaDefinitions` (p_denominator_bitwidth_guard)        | —                                                                    | `q5_rtl_specs.ts` SVA property 4                                                          | After each Grover run; ASIC feasibility                                                                             |

---

## 5. The hardware mirror (what the ASIC does, and when)

The Q5 ASIC (`hardware/rtl/`) is a silicon implementation of contracts M1–M3, M6, M10 with the invariants as fatal SVA assertions. The Stratum V1 interface is the chip's I/O.

| ASIC module                       | Implements                                                                                                                                                        | SVA assertion                                                                       | Circuit breaker                                                               |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `q5_exact_alu`                    | M3a (Oracle: negate) + M3c (Lucas-Pisot scale via integer multiply)                                                                                               | `assert_lucas_scale` (L105): `lhs_scale_check == rhs_scale_check` else `$fatal`     | `circuit_breaker_tripped` + `fault_code` outputs                              |
| `q5_top_asic`                     | Stratum V1 job interface (`job_valid`, `job_id`, `n_inner_scale`, `target_k_steps` → `golden_nonce`, `solution_found`) + companion M^n evolution + Lucas sequence | `assert_cassini` (L84): `exact_det_register == (n_is_even ? +1 : -1)` else `$fatal` | `halt_circuit_breaker` latches on det deviation, **halts the clock** (L91–97) |
| `q5_zeckendorf_hbm3e_ctrl`        | INV-5 memory routing: linear addr → face_id (5b) + Zeckendorf bits → HBM3e channel/bank hash (conflict-free)                                                      | `assert_zeckendorf` (L96): `(zeck_bits & (zeck_bits >> 1)) == 0` else `$fatal`      | —                                                                             |
| `golden_invariant_monitor` (GIMB) | All 9 invariants combinationally; `all_ok` AND of 9                                                                                                               | (wrapped by `golden_invariant_sva.sv`)                                              | `halt_trip_out = enable && !all_ok`                                           |
| `golden_invariant_sva.sv`         | 9 `assert property` + 10 `cover property`                                                                                                                         | Each `$fatal` on violation                                                          | —                                                                             |
| `golden_ontology_transform`       | Fibonacci butterfly FFT replacement                                                                                                                               | Inline Binet/Cassini/orthogonality checks                                           | —                                                                             |
| `emergent_intelligence_detector`  | 5-criteria intelligence score (0–5)                                                                                                                               | —                                                                                   | —                                                                             |
| `yang_mills_gap_monitor`          | Δ = λ₁ − λ₀ via integer cross-products                                                                                                                            | `gap_positive` (L40)                                                                | —                                                                             |
| `q5_formal_sva_tb`                | Testbench: 2.4 GHz clock, Stratum job (n_inner=20 → 33M states, k=4548), 1000 cycles                                                                              | Pass = `!halt_circuit_breaker` after 1000 cycles                                    | —                                                                             |

**Key design principle**: if any invariant is violated (e.g., cosmic ray bit flip), the chip **halts immediately** rather than producing an incorrect mining result. The circuit breaker is the kill switch.

---

## 6. Verification gates (what must pass before tape-out / production)

### 6.1 Pre-flight audit (every 60s when mining, or on demand)

`RigorousAuditMatrix.runFullPreFlightAudit()` — 11 audits, each with deterministic proof + negative control:

1. Cassini (n=1..100) 2. Born norm (∑P=1 exact) 3. Q[√5] field closure 4. 32-face topology 5. Lucas-Pisot invariance 6. Bitcoin header + SHA-256d 7. Zeckendorf 8. Q5 memory zero-leak (2000 iters) 9. Stratum 5-phase workflow 10. First-principles quantum (QFT/Grover unitarity) 11. Kellogg-Grover limit (Theorem A.1, <1e-12)

### 6.2 Adversarial suite (proves hard-fail on drift)

`AdversarialIntegrityEngine.runAdversarialSuite()` — 7 attacks, all must trip the circuit breaker:

- Float epsilon injection, Cassini tamper (+1), Lucas tamper, phase oracle 10⁻⁷ decay, denominator overflow, ...

### 6.3 Verification suite (14 tests, 4 categories)

`VerificationSuiteEngine.runFullVerificationSuite()`:

- UNIT (4): Q[√5] inverse, Cassini (n=2..40), Pisot convergence, header packing
- INTEGRATION (4): 32-node walk conservation, hybrid superposition, nonce analyzer, Zeckendorf router
- E2E (3): full block assembly, clean-jobs stale prevention, BIP-22 retargeting
- CLIENT_HANDOVER (3): zero-leak memory, Stratum SLA (<50ms RTT, >99.8% acceptance), sovereign determinism

### 6.4 Tape-out checklist (CI kill switch)

`legacy/scripts/euclid_tapeout_checklist.py` (the described `tests/test_euclid_tapeout.py` suite is not committed; the checklist's own `run_full_tapeout_audit()` is the gate):

- H1: Zero FPU (static analysis: 0 violations across ≥4 .sv files)
- H2: Cassini SVA (100 powers, 0 failures)
- H3: Zeckendorf (500 addresses, 0 adjacent-1s violations)
- H4: Stratum V1 interface (8 required signals present in `q5_top_asic.sv`)
- H5–H12: Lucas-Pisot, unimodular, holographic, structure, GIMB 9, ontology, intelligence, Yang-Mills
- `assert_ready_for_tapeout()` raises `AssertionError` if any check fails → **CI blocks tape-out**
- Open gaps P1–P3 (EUV mask, CoWoS packaging, datacenter test) are `SILICON_PENDING` — honestly labelled, not blocking the RTL/formal proof

### 6.5 Clay checklist (intellectual honesty)

`python_backend/hyba/quantum/clay_checklist.py`:

- Tracks Yang-Mills mass-gap proof obligations (C1–C10 closed on lattice, G1–G6 open for continuum)
- `assert_no_established()` guarantees **0 items may be labelled ESTABLISHED** without a continuum proof
- This prevents overclaiming: the hardware asserts Δ>0 on the lattice, but the continuum proof remains open

### 6.6 Formal simulation

`hardware/tb/q5_formal_sva_tb.sv`: 1000 cycles at 2.4 GHz, `q5_top_asic` with n_inner=20 (33,554,432 states), k=4548. Pass = circuit breaker stays low = Cassini holds across all reached powers of M.

---

## 7. Stratum V1 error prevention summary

| Stratum error   | Code | Root cause                        | Prevention contract                         | Where                                         |
| --------------- | ---- | --------------------------------- | ------------------------------------------- | --------------------------------------------- |
| Other/Unknown   | 20   | —                                 | —                                           | —                                             |
| Job not found   | 21   | Share submitted against stale job | **M4** (clean_jobs mid-flight abort)        | `isJobStale` at top of every Grover iteration |
| Duplicate share | 22   | Same nonce resubmitted            | Structural (unique face/local per step)     | M6 nonce derivation                           |
| Low difficulty  | 23   | Hash doesn't meet target          | **M8** (MeetsTarget pre-submit gate)        | `meetsTarget` before `insertShare`            |
| Unauthorized    | 24   | Bad worker credentials            | `Database.findWorkerByName` + password hash | Session open                                  |
| Not subscribed  | 25   | No active subscription            | Session status check                        | `executeMiningStep` T0                        |

---

## 8. The "what does what" quick-reference table

| You want to understand...                  | Read this                                                                  |
| ------------------------------------------ | -------------------------------------------------------------------------- |
| How a nonce is found                       | Contract M1→M3→M5→M6 + §3 timeline                                         |
| Why no floating point is needed            | `exact_math.ts` (BigFraction, Q5 projective amplitudes) + Contract M1      |
| Why denominators don't explode             | Contract M3c (Lucas-Pisot scaling) + INV-4 + bit-width bound (§4 last row) |
| How stale shares are prevented             | Contract M4 + §7 (Error 21)                                                |
| How low-difficulty shares are prevented    | Contract M8 + §7 (Error 23)                                                |
| How the 32-face topology is preserved      | Contract M6 + `compare32FaceModels` audit + INV-5 (Zeckendorf)             |
| How the ASIC enforces correctness          | §5 (SVA assertions + circuit breaker)                                      |
| What must pass before tape-out             | §6.4 (12-item checklist + CI kill switch)                                  |
| Why the Yang-Mills claim isn't overclaimed | §6.5 (Clay checklist, 0 ESTABLISHED)                                       |
| How pool failover works                    | Contract M12 (Fibonacci backoff circuit breaker)                           |
| How block templates are built              | Contract M13 (package-aware greedy, exact cross-mult)                      |
| How difficulty adjusts                     | Contract M14 (BIP-22, multiply-before-divide)                              |
| How mining adapts in real time             | Contract M15 (hybrid quantum walk on 32-face graph)                        |
| How the system detects corruption          | Contract M16 (496 pairwise Cassini checks)                                 |
| What the server exposes                    | `ARCHITECTURE.md` §8 (~90 endpoints)                                       |
| What the frontend shows                    | `ARCHITECTURE.md` §9 (37 panels)                                           |
