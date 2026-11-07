# Market-ready elevations: RTL, norm proofs, climb-in, console

Four capabilities elevate the verified core (108 tests, green CI) toward the sovereign/institutional market. This document records exactly what was implemented and how it is verified.

## 1. Native RTL for the phi-ALU (`hw/`)

`hw/zeckendorf_norm_alu.sv` implements two exact integer-lattice datapaths in synthesizable SystemVerilog:

- `norm_f257phi` — the Galois norm `N(a + b*phi) = a^2 + a*b - b^2 (mod 257)`, fully combinational 9-bit arithmetic over the field F_257[phi] (5 is a quadratic non-residue mod 257, so F_257[phi] is F_257^2).
- `zeckendorf_fold_sweep` — one parallel even-phase rewrite sweep of the base-phi fold rule `F_k + F_{k+1} = F_{k+2}` (bit pattern `011 -> 100`). Even-indexed pairs share no input bits, so the sweep is constant gate delay with no binary carry chain. When a fold target meets a firing pair (pattern `1111`), the identity `F_k + F_{k+1} + F_{k+2} + F_{k+3} = F_{k+2} + F_{k+4}` keeps every sweep value-preserving.
- `qigpu_phi_alu` — top level binding one fold sweep and one norm unit.

`hw/zeckendorf_alu_32lane.sv` scales the fold sweep to the full **32-lane carry-free ALU array** (`qigpu_zeckendorf_alu_32lane`): 32 independent 64-bit Zeckendorf registers, each folding in parallel in one constant-delay sweep, with per-lane canonicality flags (`c_k * c_{k+1} = 0`) aggregated into an `all_canonical` structural parity signal.

Verification: `hw/tb_qigpu_phi_alu.sv` and `hw/tb_zeckendorf_alu_32lane.sv` run known-answer vectors with Icarus Verilog (both `TB PASS`), including full-array parallel fold, per-lane independence, canonical passthrough, and value preservation on overlap patterns. CI synthesizes both netlists with Yosys: the phi-ALU is 4,622 cells; the 32-lane array is 8,095 cells of pure AND/OR/NAND logic — zero multipliers, zero dividers, zero inferred memory, confirming the carry-free claim in the synthesized netlist. The CI job `rtl-synthesis` uploads the testbench log and synthesis statistics as artifacts. This is a verified netlist, not an ASIC tape-out; timing closure and physical design remain client-specific work.

## 2. Zero-knowledge norm proofs (`src/chronus/security/norm_proof.py`)

Ovid receipts gain a genuine proof-of-knowledge layer: a Schnorr-style Sigma protocol over the norm homomorphism of F_257[phi]. A prover holding a witness `x` with `N(x) = v` proves knowledge of `x` without revealing it:

- commit `t = N(r)` for uniform random `r`, Fiat-Shamir challenge `c = SHA-256(context | v | t) mod 257`, response `s = r * x^c`;
- verifier checks `N(s) == t * v^c (mod 257)`;
- soundness error 1/257 per proof; honest-verifier zero-knowledge because `r` uniform makes `s` uniform.

Exposed as the native workload `OVID_NORM_PROOF` (`{"operation": "prove", "witness": [a, b]}` / `{"operation": "verify", "proof": {...}}`). Tests cover round trips, tamper rejection on every field, randomized commitments, deterministic nonce vectors, and workload-level prove/verify. This is a Sigma protocol, not a full zk-STARK; the STARK interface in `security/stark.py` remains explicitly non-conformant.

## 3. Autonomous climb-in orchestration (`QiGPUOrchestrator.auto_select`)

The QiGPU now resolves `backend_preference: "auto"` at the API layer: when a client-provisioned accelerator surface (OpenCL GPU, KAT-verified at startup) supports the requested workload, execution climbs into that instance's silicon; otherwise it operates on the CPU substrate. Unsupported or unknown surfaces fail closed. Tests cover climb-in with a provisioned accelerator, CPU fallback, per-workload support filtering, and fail-closed behavior. Real-time bandwidth probing and unified-memory pointer sharing remain hardware-dependent and are only reported, never simulated.

## 5. Exact finite-field quantum evolution (`src/chronus/quantum/`)

The quantum layer is pure mathematics: statevectors evolve over F_257 with exact integer field arithmetic — no floating point, no simulated noise, no fabricated fidelities, no vendor backend facades. The field contains the entire standard gate set exactly: √2 = 60, 1/√2 = 30 (Hadamard), i = 16 (S gate), ω₈ = 4 (T gate). The Bell state computes to exact amplitudes `[30, 0, 0, 30]`; gate algebra (S² = Z, T² = S, H² = I) holds by integer equality; circuit equivalence is exact amplitude comparison. Measurement is intentionally absent — there is no Born rule over a finite field, so the module provides exact state evolution and circuit identity verification, not sampling. The previous holonomic-pulse and vendor-backend facades were removed; distributed and database packages were re-labelled honestly as in-process bookkeeping and configuration scaffolding.

## 7. Exact Grover iteration (`src/chronus/quantum/grover.py`)

Oracle phase flips and the diffusion reflection `D = 2|s><s| - I` execute as exact F_257 field arithmetic. Verified correctness: n = 2 converges in one iteration to marked amplitude exactly 1 and all others exactly 0 (matching the real-valued guarantee); `D² = I` and oracle involution hold by integer equality; trajectories for n ≤ 3 match an independent exact recurrence for every marked state. The **purity gate** (`scripts/ci/purity_gate.py`, CI job `purity-gate`) blocks floating-point computation, pseudo-random heuristics, statistical sampling, and quantum-theatre tokens from the mathematical packages on every commit.

## 6. Generalized runtime bounds (`chronus.config.runtime_bounds`)

No operational limit is hardcoded: search lanes, storage lanes, PV order, Lucas/metallic indices, element counts, payload sizes, and Trinity scale bounds are all environment-overridable (`CHRONUS_*`), failing closed on invalid values. Structural mathematical constants (the field prime 257, the golden fixed-point constant, the packaged kernel digest) remain definition-fixed.

## 4. Sovereign control plane console (`/console`)

An authenticated, embedded HTML dashboard renders live telemetry with no external assets: provisioned QiGPU surfaces, the phyllotaxis golden-ratio lane density histogram, a golden-angle spiral plot of stored records, and workload counters. Unauthenticated access returns 401. Tenant-isolated telemetry is embedded as JSON for downstream tooling.
