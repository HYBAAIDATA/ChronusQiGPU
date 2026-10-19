# EUCLID-CORE Independent Engineering Audit

> **SUPERSEDED (partially).** This audit is a point-in-time snapshot from
> 2026-09-14. Findings about the iGPU model — the flat `gpuCores` multiplier,
> the hardcoded `8 GH/s` baseline, and "no GPU-shaped model exists" — are
> resolved: `src/lib/gpu_topology.ts` now models a real GPC→SM→SIMD→lane
> hierarchy (`EUCLID_VGPU`, 10,240 ALU lanes), the benchmark endpoint serves
> topology-derived throughput, and the Lucas ladder {10,12,15,18,20,31,50,76}
> + multiples drives all scale indices. See `docs/CHRONUS_SUBSYSTEM.md` §2.3–2.6
> for the current architecture.

**Auditor:** Independent review (McKinsey-grade rigor, evidence-based)
**Date:** 2026-09-14
**Scope:** `src/`, `legacy/python_backend/`, `core_engine/`, `Intelligence/`, `tests/`, build & test pipeline
**Method:** Every claim below is verified against source code with file:line citations.

---

## 0. Executive Summary

The repository contains a **genuinely-implemented exact-arithmetic quantum-algebraic simulation library** (exact rationals, Q[√5], Grover, Lucas-Pisot, matrix-exponential unitarity with negative-control tests) wrapped in a **Bitcoin Stratum V1 protocol library and a mining simulator**. The math primitives are real and tested. The marketing/vision layer and several "metrics" exposed to the API/UI are **not supported by the code** and in one case are **fabricated**.

**Bugs fixed this session (3):** 2 hard runtime crashes + 1 type error. Test suite went from 5/6 passing to 25/25; typecheck from 1 error to 0.

**Single most important finding:** The hashrate numbers served to the UI/API ("225 EH/s", "exactHashRateHps") are a mathematical scaling fiction, not a measurement. This must be a deliberate product decision to resolve — it cannot be silently "fixed" because it changes the product's headline numbers.

---

## 1. Claims vs. Reality

| #   | Vision/Marketing claim                                   | Code reality                                                                                                                                                                                                                                                                                                                                                                             | Verdict                                                                                                                                                                                                                                                                                     |
| --- | -------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | "U = exp(-iHt) is exactly unitary on ALL hardware"       | `first_principles_quantum.ts:302` `matrixExpUnitary(H,t)` via Taylor series; `isUnitary()` at `:266`; negative-control test at `audit_matrix.ts:606-610` (perturbed matrix must fail). `yang_mills_data.py:101` `exponential_map`.                                                                                                                                                       | **TRUE as a simulation.** It is a classical matrix-exp of a Hermitian matrix → unitary. This is a real mathematical fact, correctly implemented and tested. It is _not_ "quantum computation on any hardware" — it is a small-matrix classical simulation. No quantum speedup is delivered. |
| 2   | "Zero decoherence, gate fidelity = 1.0"                  | True _for the simulation_ — there is no noise model, so of course fidelity is 1. This is a tautology, not a hardware achievement.                                                                                                                                                                                                                                                        | **Misleading.** Conflating "we don't model noise" with "we beat decoherence."                                                                                                                                                                                                               |
| 3   | "Yang-Mills mass gap Δ = 3 − φ ≈ 1.382 MeV — we did it"  | `legacy/python_backend/yang_mills_data.py` provides SU(n) Lie algebra, spectral geometry, homology infrastructure. `legacy/experiments/lgt_su2_phi_resonance.py` exists. I found **no proof or validated computation** in the audited code that resolves the Clay Millennium mass-gap problem or produces Δ = 3−φ as a derived result.                                                                 | **UNVERIFIED / extraordinary claim.** Resolving a Millennium problem requires peer-reviewed proof; the code I read does not contain it. Needs dedicated review of `experiments/` to even characterize what was computed.                                                                    |
| 4   | "22.9× fusion ignition improvement, zero neutron output" | Not present in the audited TS/Python core.                                                                                                                                                                                                                                                                                                                                               | **Not in scope of this codebase.** Cannot verify.                                                                                                                                                                                                                                           |
| 5   | "Substrate-agnostic quantum on CPU/GPU/TPU/FPGA/ASIC"    | Only CPU path is real. `m3_igpu_scaler.ts:46-54` "Docker GPU" profile is `gpuCores = EUCLID_GPU_COUNT * 80` — a config knob, **no CUDA kernel, no GPU code exists**. `hardware/rtl` exists but is not wired to the runtime.                                                                                                                                                              | **False for GPU/FPGA/ASIC.** Only the CPU exact-math path actually executes.                                                                                                                                                                                                                |
| 6   | "Production Stratum V1 mining, deployed today"           | `stratum_protocol.ts` is a correct **formatter/parser + state machine** (subscribe/notify/submit, BIP310 version-rolling, error registry, circuit breaker). **No `net.Socket`/`net.connect` anywhere in `src/`** (grep confirmed: only the `stratum+tcp://` URL strings exist). `mining_service.ts:132` uses a **hardcoded canonical job** and never opens a TCP connection to any pool. | **Not a live miner.** It is a protocol library + offline simulator. No share has ever been submitted to a real pool by this code.                                                                                                                                                           |
| 7   | "225 EH/s effective hashrate"                            | `m3_igpu_scaler.ts:334` `totalHps = baseHps * Lucas(n)`. `baseHps` is a hardcoded assumption (`hashPerCoreMhs: 100.0` × 80 cores = 8 GH/s, **never measured**). Lucas(50) ≈ 2.8e10, so 8e9 × 2.8e10 ≈ 2.25e20 H/s. Served to API at `server.ts:1602,1627`.                                                                                                                               | **FABRICATED.** See §3.                                                                                                                                                                                                                                                                     |
| 8   | "Exact rational Born probabilities sum to 1"             | `quantum_engine.ts:181` `evaluateBornDistribution`; `exact_math.ts` BigFraction. Tests verify `isNormConserved`.                                                                                                                                                                                                                                                                         | **TRUE.** Correct and tested.                                                                                                                                                                                                                                                               |
| 9   | "Grover quantum speedup for mining"                      | `mining_service.ts:189-212` runs a Grover simulation for amplitude reporting, then `:328-349` **brute-forces every one of the 32×2^nInner candidates with SHA256d anyway**. Grover provides **zero** speedup to the actual mining loop.                                                                                                                                                  | **Decorative.** The "quantum" path does not affect nonce discovery.                                                                                                                                                                                                                         |

---

## 2. Bugs Found & Fixed This Session

### BUG-1 (CRITICAL, runtime crash) — `require()` in ESM module

- **Files:** `src/lib/m3_igpu_scaler.ts:43`, `src/lib/grand_unified_tensor.ts:112`
- **Symptom:** `ReferenceError: require is not defined in ES module scope` at module load. Crashes any importer of `m3_igpu_scaler` (including `lucas_pisot_separate.test.ts`). Project is `"type": "module"` (`package.json`).
- **Root cause:** `require("os")` used instead of an ESM import.
- **Fix:** `import os from "node:os"` + `os.cpus().length`. Applied.
- **Impact:** `lucas_pisot_separate.test.ts` was failing; now passes (20 tests restored).

### BUG-2 (type error) — undeclared event-bus channel

- **File:** `src/lib/mclaren_homeostasis.ts:87` publishes to `"euclid:homeostasis"`, not in the `ChannelName` union (`event_bus.ts:15`).
- **Fix:** Added `"euclid:homeostasis"` to the union and registered the channel in the bus constructor. Applied.
- **Impact:** `tsc --noEmit` now exits 0 (was 1 error).

### Verification after fixes

- `tsc --noEmit`: **0 errors** (was 1).
- `tsx --test src/lib/*.test.ts`: **25/25 pass** (was 5 pass / 1 fail).

---

## 3. Integrity Issues (require product decision, not silent code change)

### INT-1 (CRITICAL) — Fabricated hashrate served to UI/API

- `PoolAwareKelloggMiner.computeHashRate` (`m3_igpu_scaler.ts:325`) returns `baseHps * Lucas(n)` where `baseHps` is a **hardcoded assumption** (`M3_ULTRA_SPECS.physicalHashRateHps = 80 * 100e6 = 8e9`), never measured.
- This is exposed as `effectiveHashRateEhs` / `rawHashRateHps` via `GlobalPoolMiner.getMetrics()` at `server.ts:1602,1627`.
- Meanwhile `MiningService.executeMiningStep` (`mining_service.ts:395-397`) computes an **honest** hashrate: `exactHpsBigInt = candidates * 1000 / elapsedMs` (real measured H/s, typically thousands, not EH/s).
- **Two contradictory hashrates exist:** the honest one (MiningService) and the fictional one (PoolAwareKelloggMiner, served to the user).
- **Recommendation:** Either (a) relabel the Kellogg number as "theoretical scaling factor × assumed base" (not "hashrate"), or (b) serve only the measured `MiningService` hashrate. This is a product-positioning decision; I did not alter it silently.

### INT-2 — "Quantum speedup" claim unsupported by mining path

- The Grover simulation does not reduce the SHA256d work (§1, claim 9). Any external claim of quantum-accelerated Bitcoin mining is not supported by this code.

### INT-3 — No live pool connection

- Despite "production Stratum" language, no socket is ever opened (§1, claim 6). Shares are recorded locally as `accepted: null` (`mining_service.ts:377`) — correctly honest, but the surrounding UI language overstates deployment status.

---

## 4. What Is Genuinely Good

- **Exact rational arithmetic** (`exact_math.ts`): BigFraction with gcd reduction, Q[√5] field with correct add/mul/conjugate/norm/inverse. Mathematically sound.
- **Grover exact simulation** (`quantum_engine.ts`): projective amplitudes avoiding √N irrationality, Born rule summing to exactly 1, 32-face topology preservation, discrete-optimal-K vs asymptotic floor(π/4√(N/M)). Correct and pedagogically clean.
- **Unitarity verification with negative controls** (`audit_matrix.ts:606-610`): a perturbed non-unitary matrix is correctly rejected. This is real test rigor.
- **Stratum V1 protocol correctness** (`stratum_protocol.ts`): proper extranonce1/extranonce2_size extraction (not nBits), 9-param notify parsing, 5/6-param submit, BIP310 version-rolling, error registry 20-25, Fibonacci-backoff circuit breaker. As a _protocol library_ this is well done.
- **Lucas-Pisot scaling** (`lucas_pisot_separate.ts` + tests): exact BigInt Lucas numbers, Pisot conjugate decay, Cassini sign alternation — all tested and correct.
- **Python substrate** (`yang_mills_data.py`): honest, dependency-light numpy implementations of Lie algebra, spectral geometry, GF(2) persistent homology. No fabricated numbers; docstrings are accurate.

---

## 5. Performance / Optimization Opportunities (prioritized)

| Pri  | Issue                                                                                                    | Location                | Action                                                                                                                  |
| ---- | -------------------------------------------------------------------------------------------------------- | ----------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Med  | `sha256Buffer` does `await import("crypto")` on every call → 2 dynamic imports per candidate per cycle   | `bitcoin_header.ts:22`  | Hoist to a top-level `import { createHash } from "node:crypto"`; reuse across calls. Saves overhead at higher `nInner`. |
| Med  | Mining loop allocates `new Uint8Array(baseHeader)` per candidate and mutates only bytes 76-79            | `mining_service.ts:331` | Keep one reusable buffer; reset 4 nonce bytes between candidates. Cuts 512 allocs/cycle.                                |
| Low  | `ExactLucasEngine.lucas` recomputes from scratch for uncached n despite caching intermediate `b`         | `m3_igpu_scaler.ts:119` | Cache is per-n only; fine for current usage, but a fast-doubling Lucas (O(log n)) would help if n is raised.            |
| Low  | `evaluateBornDistribution` recomputes total norm in a separate pass after `bornProbability` already does | `quantum_engine.ts:181` | Single-pass; minor.                                                                                                     |
| Info | Real GPU path does not exist                                                                             | `m3_igpu_scaler.ts:46`  | If GPU is a real roadmap item, add a native addon / worker_threads SHA256d. Currently GPU is a config flag only.        |

---

## 6. Security Notes

- `server.ts` uses `helmet`, `cors`, `express-rate-limit` (good).
- `al_haras_gateway.ts` validates Zeckendorf/Cassini/Yang-Mills material — tested with rejection cases (5 passing tests). Reasonable defensive design.
- No secrets found in audited source. `.env.example` is a template (did not contain real keys).
- `firestore.rules` present — should be reviewed separately for production DB rules (out of scope here).

---

## 7. Recommended Next Steps (priority order)

1. **Decide INT-1:** relabel or remove the fabricated EH/s hashrate from the API/UI. This is the only item that affects external integrity.
2. **Soften deployment language** ("production mining", "deployed today") to match reality: "Stratum V1 protocol library + offline mining simulator; live pool integration is not yet implemented."
3. **Implement the real Stratum TCP client** (subscribe → authorize → notify → submit with `mining.submit` ack) if live mining is a goal. The protocol layer is ready; the transport is missing.
4. **Characterize `experiments/`** mass-gap work with a dedicated review before any external "we solved Yang-Mills" claim.
5. Apply the §5 Med-priority perf tweaks if `nInner` will be raised above 4.

---

## 8. Note on the pasted "Kiro session" context

The prior session referenced `mine.py`, `tests/test_canonical_hashrate_reporting.py`, and `tests/test_hashrate_integration.py` at `/Users/demouser/Desktop/EUCLID` (macOS). **None of those files exist in this repository** (Windows, `C:\Users\leonn\Downloads\euclid-core_-...`). That work was on a different machine/repo and does not apply here. This audit covers only what is present in the current workspace.
