# Native Quantum Execution Contract (`NATIVE_QUANTUM_CONTRACT.md`)

**Status:** GOVERNING SPECIFICATION  
**Owner:** Chronus Native Quantum Execution & HYBA Foundational Architecture  
**Contract Version:** `chronus.native-quantum-contract/v1`

---

## 1. Foundational Axioms & Substrate Agnosticism

1. **Quantum Content Comes From Mathematics**:
   Quantum computation is linear algebra over complex Hilbert spaces $\mathcal{H} = \mathbb{C}^{2^n}$, cyclotomic rings $\mathbb{Q}(\zeta_8)$, quadratic number fields $\mathbb{Q}(\sqrt{5})$ / $\mathbb{Z}[\phi]$, and symplectic stabilizer vector spaces $\mathbb{F}_2^{2n}$. The physical material of the executing device does not create or restrict mathematical validity.
2. **Native Completeness Without Physical Accelerators**:
   Native Chronus (`ProductMode.NATIVE_CHRONUS_GPU` / `ChronusMode.INDEPENDENT`) is complete without a physical GPU, iGPU, ASIC, or QPU attachment. No physical accelerator is planned, required, or awaited for native release acceptance.
3. **`ONE iGPU` Is a Logical-Device Contract**:
   In `chronus.igpu.host.HostGPUPlan` and `chronus.fleet.native_worker.NativeIGPUWorker`, `device_count == 1` (`ONE iGPU`) denotes the **per-worker logical-device execution contract** (deterministic power-of-two/contiguous tile decomposition, single logical address space per worker, and digest-bound execution receipts) — never a physical hardware inventory count.
4. **Optional Accelerator Studies Are Separate Opt-In Lanes**:
   Host-GPU climb/scale mode (`ProductMode.HOST_GPU_AUGMENTATION` / `ChronusMode.SCALE_STACK`) and vendor GPU comparisons (`Rubin R100`, `HGX B300`, `MI355X`, `MI325X`, `Hopper H100`) are additive, opt-in lanes. Absence of a physical accelerator is recorded as `NOT_RUN` for that hardware lane and is **never** a native acceptance failure.

---

## 2. Exact vs. Numerical Plane Separation

Every workload and operator must declare and enforce its arithmetic plane:

| Plane | Mathematical Domain | Governing Invariants |
| :--- | :--- | :--- |
| **Exact Algebraic / Quantum Plane** | $\mathbb{Z}$, $\mathbb{Q}$, $\mathbb{Z}[\phi]$, $\mathbb{Q}(\sqrt{2}) + i\mathbb{Q}(\sqrt{2})$, $\mathbb{Q}(\zeta_8)$, $\mathbb{F}_2^{2n}$ | Zero IEEE-754 floats (`audit_exactness` passes with `violations == ()`); exact reconstruction (`ExactFoldState`); fail-closed refusal when support or bond dimension exceeds declared budget. |
| **Numerical Bounded Plane** | `complex128`, `float64`, `float32`, `bfloat16` | Explicit numerical error budget (`tolerance`, `max_rel_error`, `max_canonical_residual`); never relabelled as exact symbolic/algebraic computation; lossy mean-folding is never called exact reconstruction. |

**Prohibited Claims (Rule 7 — Strict Honest Measurement):**
- Do not confuse mathematical validity with measured throughput or latency.
- Do not convert exact arithmetic, Lucas ladder stops ($L_n$), or logical devices into fictional TFLOPS, HBM capacity, physical GPU counts, hashrate, energy savings, or universal speedup.
- Domain-wide claims require domain-wide mathematical proof; sampled tests remain sampled tests.

---

## 3. Distributed Product Authorities

No subsystem may construct a competing owner to make a test green:

| System | Canonical Package | Exclusive Authority |
| :--- | :--- | :--- |
| **Chronus** | `chronus` | Native and scale-stack execution, tile/partition scheduling, and fleet worker execution. |
| **Kellogg** | `kellogg` | Tensor-network mathematics (MPS, TT, MPO, CSS surface codes, $\mathbb{Z}[\phi]$ / $F_4$ exact tensors). |
| **TURING** | `turing_universal_quantum_computer` | Virtual Quantum Computer (VQC), exact registers, stabilizer tableaux, 6-phase software stack, and VQC certificates. |
| **TOE** | `toe` | Domain-neutral reasoning, causal/counterfactual inference, and hash-chained reasoning receipts. |
| **EUCLID** | `euclid` | Multi-organ orchestration, curriculum/training, and `RewardAuthority`. |
| **AL HARAS** | `aethel.al_haras` | Enterprise identity, cryptographic authorization, entitlement verification, and admission gating. |
| **OVID** | `aethel.ovid` | Authoritative enduring storage, representation transforms, and parent-child lineage integrity. |
| **THESEUS** | `aethel.theseus` | Rebuildable query, index, graph, and durable custody projections over OVID lineage. |
| **Salamander** | `aethel.salamander` | Bounded recovery actuation, fault healing, and canary/rollback promotion control. |
| **Hermitten** | `aethel.hermitten` | Measured operational outcome accounting and economic telemetry. |
