# Market-ready elevations: RTL, norm proofs, climb-in, console

Four capabilities elevate the verified core (108 tests, green CI) toward the sovereign/institutional market. This document records exactly what was implemented and how it is verified.

## 1. Native RTL for the phi-ALU (`hw/`)

`hw/zeckendorf_norm_alu.sv` implements two exact integer-lattice datapaths in synthesizable SystemVerilog:

- `norm_f257phi` — the Galois norm `N(a + b*phi) = a^2 + a*b - b^2 (mod 257)`, fully combinational 9-bit arithmetic over the field F_257[phi] (5 is a quadratic non-residue mod 257, so F_257[phi] is F_257^2).
- `zeckendorf_fold_sweep` — one parallel even-phase rewrite sweep of the base-phi fold rule `F_k + F_{k+1} = F_{k+2}` (bit pattern `011 -> 100`). Even-indexed pairs share no input bits, so the sweep is constant gate delay with no binary carry chain. When a fold target meets a firing pair (pattern `1111`), the identity `F_k + F_{k+1} + F_{k+2} + F_{k+3} = F_{k+2} + F_{k+4}` keeps every sweep value-preserving.
- `qigpu_phi_alu` — top level binding one fold sweep and one norm unit.

Verification: `hw/tb_qigpu_phi_alu.sv` runs known-answer vectors with Icarus Verilog (`TB PASS`), and CI synthesizes the netlist with Yosys (4,622 generic cells, zero inferred memory). The CI job `rtl-synthesis` uploads the testbench log and synthesis statistics as artifacts. This is a verified netlist, not an ASIC tape-out; timing closure and physical design remain client-specific work.

## 2. Zero-knowledge norm proofs (`src/chronus/security/norm_proof.py`)

Ovid receipts gain a genuine proof-of-knowledge layer: a Schnorr-style Sigma protocol over the norm homomorphism of F_257[phi]. A prover holding a witness `x` with `N(x) = v` proves knowledge of `x` without revealing it:

- commit `t = N(r)` for uniform random `r`, Fiat-Shamir challenge `c = SHA-256(context | v | t) mod 257`, response `s = r * x^c`;
- verifier checks `N(s) == t * v^c (mod 257)`;
- soundness error 1/257 per proof; honest-verifier zero-knowledge because `r` uniform makes `s` uniform.

Exposed as the native workload `OVID_NORM_PROOF` (`{"operation": "prove", "witness": [a, b]}` / `{"operation": "verify", "proof": {...}}`). Tests cover round trips, tamper rejection on every field, randomized commitments, deterministic nonce vectors, and workload-level prove/verify. This is a Sigma protocol, not a full zk-STARK; the STARK interface in `security/stark.py` remains explicitly non-conformant.

## 3. Autonomous climb-in orchestration (`QiGPUOrchestrator.auto_select`)

The QiGPU now resolves `backend_preference: "auto"` at the API layer: when a client-provisioned accelerator surface (OpenCL GPU, KAT-verified at startup) supports the requested workload, execution climbs into that instance's silicon; otherwise it operates on the CPU substrate. Unsupported or unknown surfaces fail closed. Tests cover climb-in with a provisioned accelerator, CPU fallback, per-workload support filtering, and fail-closed behavior. Real-time bandwidth probing and unified-memory pointer sharing remain hardware-dependent and are only reported, never simulated.

## 4. Sovereign control plane console (`/console`)

An authenticated, embedded HTML dashboard renders live telemetry with no external assets: provisioned QiGPU surfaces, the phyllotaxis golden-ratio lane density histogram, a golden-angle spiral plot of stored records, and workload counters. Unauthenticated access returns 401. Tenant-isolated telemetry is embedded as JSON for downstream tooling.
