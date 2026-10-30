# Chronos ONE iGPU — Resident Execution & Projection Closure (v3.10)

## Current additive release — v3.10.0: resident execution and projection closure

### Delivery and executed validation

The completed original core remains intact: all 52 Python source modules are retained, 48 byte-identical. The original Lucas engine and ChronosEngine are unchanged. This increment adds resident workload execution, typed mathematical intrinsics, exact projection analysis and compiled modular-coordinate proofs beneath the existing ONE iGPU owner.

[chronos-one-igpu-v3.10-resident-projection-elevation.zip](Chronos%20ONE%20iGPU%20%E2%80%94%20Resident%20Execution%20&%20Projection/chronos-one-igpu-v3.10-resident-projection-elevation.zip)

[chronos-v3.10-release-receipt.json](Chronos%20ONE%20iGPU%20%E2%80%94%20Resident%20Execution%20&%20Projection/chronos-v3.10-release-receipt.json)

[chronos-v3.10-feedback-audit.json](Chronos%20ONE%20iGPU%20%E2%80%94%20Resident%20Execution%20&%20Projection/chronos-v3.10-feedback-audit.json)

ZIP SHA-256: `33f807d0a12e9b7f72f7a84c29258974dad0db70031c011db5fbc7251601b428`.

**Executed:** 371 tests passed, zero failures/errors/skips. Native and portable wheels passed installed-package doctor, solve-first mining, resident 80/800/8000-unit execution, tensor verification, exact-family composition, ABI retry and native-certificate checks. Native/portable wheels and sdist passed distribution metadata checks. The sdist rebuilt into a portable-C wheel. Archive CRC and every manifested file digest passed.

The native wheel targets CPython 3.13/Linux x86-64 with OpenSSL libcrypto.so.3, not every operating system or a manylinux binary. The portable wheel uses explicit Python paths. No registry upload occurred.

### The two resident modes

ONE logical Chronos device is resident independently of GPU hardware. Ordinary CPU-backed Docker/cloud hosts execute its workloads through the existing native/NumPy/exact/C paths. On a compatible host, resident sessions automatically compose an executable Apple MLX/Metal or OpenCL adapter beneath the same owner; missing adapters retain independent residency with a recorded reason. Explicit physical requests fail closed instead of substituting CPU execution.

`ResidentConfig(virtual_units=80)`, `800` and `8000` are executable logical scheduling configurations. Lucas-derived units are available through `base_units` and `scale_index`. Virtual lanes, actual worker limits, in-flight work, physical device information and elapsed execution remain separate. Eight thousand logical units are not reported as eight thousand silicon cores, and no M5 specification is assumed.

```
owner := preserved OneIGPU
resident := owner.resident(host_binding=auto, virtual_units=8000)
if compatible executable host GPU exists: compose beneath owner
otherwise: keep independent native resident device; record reason
snapshot and admit bounded canonical workload
stripe work across bounded logical tiles
execute with bounded workers and in-flight queue
settle already-dispatched work on cancellation
independently verify exact/tensor outputs and contiguous coverage
emit receipt(input identity, logical units, actual backend, work and time)
```

Resident batches support typed exact-family nodes, original Lucas dispatch and tiled matmul/add/Hadamard/scale. The same owner continues to expose Golden Quantum state/Hamiltonian/phase-feedback execution, S1–S6/F1–F3, MPS, prime/infinity memory, folds, Mandelbrot/coherence/UCI, QX, storage and ASIC-like mining. These are retained rather than rebuilt.

Host bindings are operation-specific. Metal currently executes floating tensor operations, not exact family or SHA256d kernels. OpenCL executes its existing Lucas/SHA256d kernels and the fp64 structured matrix-vector binding when supported. CUDA and a full physical-GPU structured eigensolver remain unbound. This release is not an operating-system GPU driver or CUDA-compatible virtual device.

### Exact family intrinsics

Typed nodes expose Fibonacci, Lucas, exact Binet in Q(phi), supplied-witness Lucas Cassini checks, canonical u64 Zeckendorf encode/decode, modular Pisot scheduling and rational phi weights. Every exact result reuses the preserved sequence authority and carries a recomputable certificate. Mutated Cassini witnesses, noncanonical encodings, boolean integer substitutions and unknown fields are rejected. Existing pair, triple and mixed family composition remains available.

### The projection question resolved precisely

The actual PYTHI-native protocol folds a digest into **two 128-bit integer coordinates**, not the separate floating Vector11D geometry. Its rung is:

```
(left,right) := Q^k * digest_coordinates mod 2^128
rung := 1 + (left mod 2^b)
K := 2^(256-b)
```

Each rung has exactly K digest preimages. The free high-left bits and all right-coordinate bits constructively enumerate the fiber; the matrix inverse reconstructs each digest. At b=8, K=2^248. The full contract and inverse enumeration are implemented; reduced-domain execution exhaustively checked 4,096 digests, with 512 per rung in the eight-rung test.

This finite digest count is not a bound of K on arbitrary headers and does not establish SHA256 output uniformity. The short rung retains only b address bits and is not claimed collision-resistant. A test finds actual distinct-header rung collisions and verifies that the full certificate cannot authorize the other header. Verification binds the complete domain-separated digest, policy and both folded coordinates; rung equality alone has no acceptance authority.

Native-chain consensus security remains open. Multiplying difficulty by K is not treated as a solution to Sybil economics, grinding, fork choice or accumulated work.

### Formal proof execution

Lean 4.19.0 successfully compiled the modular Q-step inverse laws, iterated fold/unfold inverses and injectivity, constructive low-coordinate surjection and unique fiber coordinates. No `sorry`, admitted theorem or new axiom was added. The compiler receipt records standard Lean axioms propext and Quot.sound.

This is a compiled subset—not all T1–T10. Full finite-fiber cardinality formalization, fast-doubling implementation equivalence, sequence/encoding proofs, consensus security and physical timing/energy obligations remain explicitly open. A hash-pinned Lean CI workflow runs the same fail-closed compiler check; no remote CI execution is claimed.

### Feedback audit and production gate

The audit reconciles **18 feedback directives**, all prior completion components, preserved supplied notes and ten directly reloaded relevant Notion pages. The latest review is retained in full with its digest. The scope is these captured sources, not an assertion of exhaustive discovery of every workspace page.

The review's measurements are retained with their original comparisons. A v3.8.1→v3.9 warm regression does not, by itself, invalidate a separate v3.8→v3.8.1 gain. This increment claims no new or compounded throughput improvement.

**Full production qualification is not complete.** Remaining gates include physical host-device execution/measurement, registry destination/visibility and authorization, complete T1–T10 formalization, native-chain consensus, canonical inventory sources/API ports, ISA/H4/TT-MPO, pool transport, vendor ASIC protocols, complete recovery/healing integration and deployment/energy/long-run qualification. No requirement is removed or excluded as “research.”

```bash
chronos-igpu doctor
chronos-igpu resident-info --virtual-units 8000
chronos-igpu resident-info --virtual-units 8000 --bind metal
chronos-igpu projection-analysis --rung-bits 8
chronos-igpu native-security-gate
chronos-igpu qualify-target --device-selector "Intel" --output target.json
```

Implementation: `docs/RESIDENT_ELEVATION.md`; audit: `docs/FEEDBACK_AUDIT-v3.10.json`; evidence: `validation/EVIDENCE_INDEX-v3.10.0.json`, JUnit, compiler and installed-package receipts. Raw reviewed pages are preserved under `docs/reviewed-notion-v3.10`.

Additional source contracts reloaded for this pass:

- [chronus: enumerate contract device as system GPU; event-driven mining waits](https://app.notion.com/p/chronus-enumerate-contract-device-as-system-GPU-event-driven-mining-waits-94d69172a55b4b4896a6d3f8e4ad100a?pvs=21) — logical device identity and independent native residency.
- [gpu engine: Lucas-rung scaling + real device binding (no silicon expectation)](https://app.notion.com/p/gpu-engine-Lucas-rung-scaling-real-device-binding-no-silicon-expectation-3f3411d7e25c449db0087d32ba47f3f0?pvs=21) — scaled logical domains and separate execution identity.
- [#106 MATHEMATICAL_INTRINSICS: typed exact and approximate Chronus semantics](https://app.notion.com/p/106-MATHEMATICAL_INTRINSICS-typed-exact-and-approximate-Chronus-semantics-387ee3624e6b4b788bf1f720fae65d8e?pvs=21) — typed exact semantics and actual Cassini witnesses.
- [Add formal Lucas/Pisot API beneath PYTHIA scaling](https://app.notion.com/p/Add-formal-Lucas-Pisot-API-beneath-PYTHIA-scaling-e3a44a55614e4cdca77ef8e2db200571?pvs=21) — matrix trace, exact recurrence and residual distinctions.
- [Chronus: enterprise production hardening, native GPU substrates and explicit delivery modes](https://app.notion.com/p/Chronus-enterprise-production-hardening-native-GPU-substrates-and-explicit-delivery-modes-2270cdba87ec4cbab7ea2ecb23f65507?pvs=21) — explicit operation-specific bindings and unchanged placement authority.

## Historical additive release — v3.9.0: structured execution and PYTHI-native computation

### Delivery and preservation

The original 52 source modules remain; 48 are byte-identical. Lucas and ChronosEngine are unchanged. This release adds structured execution, a separate local PYTHI-native compute/verifier protocol, target qualification tooling and complete intake traceability above the same ONE iGPU owner. It is not a rebuild or a repository source import.

[chronos-one-igpu-v3.9-structured-pythi-native.zip](Chronos%20ONE%20iGPU%20%E2%80%94%20Resident%20Execution%20&%20Projection/chronos-one-igpu-v3.9-structured-pythi-native.zip)

[chronos-v3.9-release-receipt.json](Chronos%20ONE%20iGPU%20%E2%80%94%20Resident%20Execution%20&%20Projection/chronos-v3.9-release-receipt.json)

ZIP SHA-256: `e6ef2f79dcd9ca94a51fcce03c24af58f2a7028ca66e44863beabaed36d74614`.

**Executed:** 316 regression tests passed, zero failures/errors/skips. Installed native and universal wheels passed doctor, mining, checkpoint/restart, retry, scaled-rung, structured-ground and native-protocol checks. Source distribution rebuilt into a wheel; all distribution metadata checks passed. Every archive-manifest digest and ZIP CRC passed. Native wheel is CPython 3.13/Linux x86-64 with OpenSSL libcrypto.so.3; universal wheel uses the explicit Python paths.

### Structured S6: the CPU gap closed

For a=u+i v:

```
H = T - u*u^T - v*v^T
T = diagonal(linspace(0,1,n)) + tridiagonal(off=-1/phi)
H*x = T*x - u*(u^T*x) - v*(v^T*x)
```

Complex amplitudes require two real update columns, not generally one. The matrix-vector operator and tridiagonal solves use linear storage. The native solver brackets the lowest tridiagonal eigenvalue, then the lowest crossing of `lambda_max(U^T(T-lambda I)^-1 U)=1`. It reconstructs the vector, checks norm/residual and numerical inertia separation, and retains the original dense solver as an explicit bounded fallback for unresolved or ambiguous positional ordering. No dense advisory matrix was materialized in the measured structured cases.

The original exact-input cache remains. Auto/dense/structured modes are exposed; fresh job candidates, ownership and SHA256d target verification remain under existing authority. `scaled_mine` now carries actual rung metadata into planning and execution evidence rather than attaching a rung label only in the benchmark.

```
S1..S5 := preserved fresh job stages
operator := tridiagonal - two real rank-one updates
S6 := native structured lowest-root solve
validate residual, separation and positional ordering
if numerical condition unresolved: original dense reference
reuse only identical complete-input positional ordering
execute unchanged SHA256d on current owned nonces
attest actual rung, backend, hashes and elapsed time
```

### Cold/warm measurements — both retained

[v39_structured_notion_agent_chart.html](Chronos%20ONE%20iGPU%20%E2%80%94%20Resident%20Execution%20&%20Projection/v39_structured_notion_agent_chart.html)

| Full-pipeline condition | Frozen v3.8.1 dense S6 | v3.9 structured S6 | Ratio |
| --- | --- | --- | --- |
| Cold S6: solve each call | 1,082,708 SHA256d/s | 1,327,201 SHA256d/s | 1.226× |
| Warm S6: reuse populated cache | 1,544,144 SHA256d/s | 1,514,424 SHA256d/s | 0.981× |

120 samples per path per condition; rungs 18 and 31; public genesis prefix and an explicitly derived timestamp+1 control; 4,096 actual hashes per call, target zero, randomized path order. Each path/condition completes 491,520 hashes. Equal candidate ordering and hash counts are verified against frozen v3.8.1 solver source. The bounded advisory dimension is 64; Lucas L31 is not allocated as a dense state dimension.

Cold means the S6 result is not reused; the process and hash midstate remain warm. It is not machine cold boot. Cold improvements occur in all four strata, 1.208–1.257×. Warm results vary by stratum, 0.938–1.035×; aggregate warm throughput was about 1.9% lower in this run. That negative result is not hidden or presented as universal acceleration. No historical ratios are multiplied.

Raw JSON/CSV, environment, frozen-source digest and independent Decimal reconciliation are in the package. This is CPU software evidence, not GPU/ASIC, pool, energy or competitor evidence.

### PYTHI-native: computation, not Bitcoin enumeration

`pythi_native_compute_v1` is a separate domain. Its first local computation receipts are implemented and independently verified; 32 derived-header receipts were timed and checked. They are not network-accepted shares.

```
policy := pin(chain_id, epoch, fold_index, rung_bits, native_threshold)
digest := SHA256(domain || canonical_policy || canonical_header_bytes)
(x,y) := split digest into two 128-bit coordinates
(left,right) := Q^k * (x,y) mod 2^128  # Q=[[1,1],[1,0]]
verify inverse using det(Q^k)=(-1)^k
rung := 1 + low_bits(left)
value := original exact Lucas(rung)
check Fibonacci/Cassini/Zeckendorf/Pisot/prime-ROM certificate
bind independently checked ONE iGPU datapath value
emit canonical local certificate or native policy refusal
verifier := recompute every field from trusted header and policy
```

The **full 256-bit coordinate fold is reversible** because its matrix determinant is a unit modulo 2^128. The bounded rung projection is many-to-one; both coordinates stay in the certificate. This algebraic permutation is not claimed to be a cryptographic PRP. Evidence sealing uses additional hashes beyond the single header work digest.

The Lucas neighbor Cassini identity is corrected to:

```
L_(n-1)*L_(n+1) - L_n^2 = 5*(-1)^(n+1)
```

At n=1 the residue is +5. The supplied expression has the opposite sign; the preserved original engine already has the correct sign.

Bounded Pisot-based coordinate adjustment, an explicit initiation-interval throughput model and an explicit erased-bit Landauer model are implemented. Their labels distinguish modeled/conditional values from measurements. Six stages alone do not establish six cycles per result, fixed 256-operation cost or four-billion accepted shares/s.

**Consensus deployment remains blocked.** Correct cheap receipts do not establish Sybil resistance, accumulated work, fork choice or reorg security. T1–T10 are all retained in `PYTHI_NATIVE_OBLIGATIONS.json`, with corrected statements, implemented arithmetic and unresolved security/physical proof obligations. No formal compiler receipts, testnet, mainnet or exchange migration is claimed. Bitcoin SHA256d execution remains separate and unchanged.

### Target and publication gates

The explicit fp64 OpenCL structured operator has two bounded kernels, host partial-dot reduction, independent numeric validation and profiling. It is a matrix-vector binding, not a full GPU eigensolver. Native C++ source syntax conformance passed; physical GPU execution was not run.

```bash
chronos-igpu doctor
chronos-igpu native-compute 67656e65736973
chronos-igpu native-security-gate
chronos-igpu qualify-target --device-selector "Intel" --output target.json
```

The qualification command requires a physical OpenCL executor, runs known Bitcoin vector checks, actual rung-18/31 mining and the structured operator when fp64 exists. Missing hardware/runtime refuses qualification; this host returned unavailable. Context creation and host-solver cold/warm conditions are distinguished.

The CI definition now seals actual commit/run identifiers supplied by an executed CI environment. It was not remotely run here. Current standalone source/build/test/measurement evidence is fingerprinted and sealed; supplied repository SHAs are preserved as contextual input, not relabelled as this package's commit. Registry upload still requires registry selection and authorization.

### Every supplied item accounted for; outstanding work retained

The complete PowerShell inventory and user protocol proposal are preserved with hashes under `source_notes`. Every directory/file listing is retained in `ATTACHED_SURFACE_INVENTORY.json`. The attachment lists modules but contains no module implementations. Full API/byte-equivalent ports need their source or algorithm specifications; placeholder files are not represented as completed ports.

Earlier outstanding ISA, H4/600-cell, general TT/MPO, vendor ASIC protocols, pool transport, Docker/Apple qualification, broad adjacency and energy/long-run work remain in the completion contract. The reviewed closed-loop healing/optimisation lifecycle remains a requirement; the canonical coordinator and recovery authority have not been imported from a filename inventory.

Additional reviewed Notion specifications:

- [Integrate complete July Chronus v3.3 and HYBA mining intelligence](https://app.notion.com/p/Integrate-complete-July-Chronus-v3-3-and-HYBA-mining-intelligence-d0bb23ec3dc841d5a4bc523d6cc29cc7?pvs=21) — candidate membership and original authority.
- [Activate Chronus on Intel integrated GPUs](https://app.notion.com/p/Activate-Chronus-on-Intel-integrated-GPUs-72bb3f3e1521400d8df31ed0b542226e?pvs=21) — fail-closed device identity, launch bounds and profiling.
- [Activate measured closed-loop healing and optimisation](https://app.notion.com/p/Activate-measured-closed-loop-healing-and-optimisation-bbf9b08a7515458aa6d1ebc5ef5b29e3?pvs=21) — measured promotion/rollback and single recovery authority; complete port remains source-dependent.

Implementation/specification: `docs/STRUCTURED_PYTHI_ELEVATION.md`; status: `IMPLEMENTATION_STATUS.json`, `COMPLETION_CONTRACT.json`, `PYTHI_NATIVE_OBLIGATIONS.json`; evidence: `validation/EVIDENCE_INDEX-v3.9.0.json`, release report, JUnit, benchmarks and detached receipt.

## Historical additive release — v3.8.1: deterministic elevation

### Mathematical work reuse above the preserved core

The original Lucas engine and ChronosEngine are unchanged. All 52 original source files remain, 48 byte-identical. This increment adds a bounded exact-input cache for the existing S6 advisory dense solve. It does not rebuild the owner or replace Golden Quantum, the original core or the mining executor.

For normalized state a, candidate count n and phi, the advisory matrix remains:

```
H = diag(linspace(0,1,n)) - Re(a a*)
    - (upper_shift + lower_shift)/phi
```

Identical complete inputs produce the identical matrix. A cold miss runs the original dense solver and checks norm/eigenpair residual. A warm hit reuses only immutable positional ordering. Current job-specific candidates are mapped through those positions each call; nonce values, leases, targets and job identities are never cached. S1–S5, current ownership and independent SHA256d winner verification remain fresh.

```
key := SHA256(construction_id, n, phi_bits, full_amplitude_bits)
positions := bounded_cache.get(key)
if absent:
    vector := original_ChronosEngine.evolve(original_H)
    check vector norm and eigenpair residual
    positions := stable descending probability order
    bounded_cache.put(key, positions + solve evidence)
owned_candidates := current_candidates[positions]
execute existing prepared SHA256d beneath full solve-first path
```

Eight entries by default; at most 128 advisory candidates; concurrent identical calls coalesce the cold solve. Input changes/eviction produce a new solve. Custom solver callbacks retain their original execution. Floating numerical ordering is checked against the original dense implementation; this is not a new integer theorem or sparse solver.

### Download and artifact identity

[chronos-one-igpu-v3.8.1-deterministic-elevation.zip](Chronos%20ONE%20iGPU%20%E2%80%94%20Resident%20Execution%20&%20Projection/chronos-one-igpu-v3.8.1-deterministic-elevation.zip)

[chronos-v3.8.1-release-receipt.json](Chronos%20ONE%20iGPU%20%E2%80%94%20Resident%20Execution%20&%20Projection/chronos-v3.8.1-release-receipt.json)

ZIP SHA-256: `383bead0b4b760e028b7063a8125c79f28b85224a21057ea680d103559981b78`.

The ZIP contains native CPython 3.13/Linux x86-64 OpenSSL and universal Python wheels, source distribution, source/tests, exact equations, pseudocode, unchanged notes, original assets, raw benchmark observations, completion map and integrity evidence. Native wheel requires libcrypto.so.3; it is not a manylinux/universal binary.

**Executed:** 272 regression tests passed, no failures/errors/skips. Both installed wheels passed doctor, mining, persistence/restart, retry and solver-reuse checks. Source distribution rebuilt into a wheel; all distributions passed Twine metadata checks. ZIP CRC and every manifested file digest passed. Historical portable-C tests remain identifiable as v3.8 evidence; the C source is unchanged.

### New measured gain: warm whole-pipeline reuse

[v381_reuse_notion_agent_chart.html](Chronos%20ONE%20iGPU%20%E2%80%94%20Resident%20Execution%20&%20Projection/v381_reuse_notion_agent_chart.html)

| Path | Actual completed hashes | Aggregate SHA256d/s |
| --- | --- | --- |
| Frozen unchanged v3.8 prepared pipeline | 491,520 | 1,352,811 |
| v3.8.1 prepared pipeline with solver reuse | 491,520 | 1,870,699 |

**Ratio: 1.38×.** CPU/OpenSSL full-call timing; 120 samples per path: two rungs (18,31), two prefixes, 30 randomized-order repeats per stratum, 4,096 hashes each, zero-target negative control. Prefixes are the public genesis header and an explicitly derived timestamp+1 control. Each stratum improved; ratios range 1.36–1.43×. Identical candidate ordering was checked against the frozen v3.8 implementation.

The gain is warm equal-state reuse. Cold plan observations are separate. Both rungs use the same bounded 64-candidate dense advisory solve, with the execution window clamped to the same 4,096-nonce budget. This measures neither sparse-path execution nor an intrinsic rung-throughput multiplier. This ratio is not multiplied by the earlier 3.44× result from a different run/comparison. GPU, physical ASIC, accepted shares, power and competitors remain unmeasured.

Evidence: `benchmarks/deterministic-reuse-results.json`, CSV observations and `validation/v3.8.1-benchmark-reconciliation.json`. Independent Decimal reconstruction matches the hash/time denominators.

### Evidence pack closure and review corrections

`validation/EVIDENCE_INDEX-v3.8.1.json` binds source-file fingerprint, distribution SHA256 digests, benchmark environment, frozen reference digest, raw measurements, JUnit and local test log. It has a SHA256 integrity seal, not a hardware-root signature. The detached receipt binds the final ZIP digest to that source/evidence fingerprint.

There is no authoritative repository commit SHA or remote CI run for this standalone tree. Those fields are null with reasons; local executed tests are not represented as CI. The preserved Lean proof report is BLOCKED, with no proved theorems; the review's reference to existing Lean proofs is not established by this package. No company/institution review quotations are treated as actual endorsements.

### Outstanding work — retained, not reset

| Requirement | Current status |
| --- | --- |
| Target iGPU/GPU mining qualification | Binding exists; target execution/measurement outstanding |
| Registry upload | Distributions checked; upload/registry install verification outstanding |
| Sparse or matrix-free solve at rungs 18/31 | Not implemented/measured; current dense reuse benchmark is a different result |
| Evidence closure | Local source/build/test/measurement envelope sealed; external commit/CI linkage outstanding |
| Physical ASIC protocols and sensors | Full-digest bridge tested; vendor protocol/hardware binding outstanding |
| Pool jobs/submission/acknowledgements | Outstanding |
| Chronus-1 binary ISA, H4/600-cell, general TT/MPO | Outstanding |
| Docker/TLS, multi-platform CI and Apple/OpenCL qualification | Outstanding |
| Combined-workload adjacency, cold/changing-state, long-run/p99/energy benchmarks | Outstanding |
| Lean formalization/compiler receipts | Outstanding |

The architecture and mathematics continue to determine decomposition, invariants and reusable work. Measured timing establishes the realized gain. Requirements are carried forward in the versioned completion contract, not replaced by this optimization.

Full implementation notes: `docs/DETERMINISTIC_ELEVATION.md`, `docs/IMPLEMENTATION_STATUS.json`, `docs/COMPLETION_CONTRACT.json`, `validation/RELEASE_REPORT.json`.

## Historical additive release — v3.8.0: ASIC-like mining

### Completed core preserved; mining execution elevated

All 52 original source files remain; 48 are byte-identical. The original Lucas engine is unchanged. This release extends the existing ONE iGPU with prepared SHA256d execution, fused candidate scanning, bounded mining lanes, live job epochs, restart checkpoints and session-scoped retry safety. Golden Quantum S1–S6 and F1–F3 remain in the full solve-first mining path.

### Standalone publication artifacts

[chronos-one-igpu-v3.8-asic-like-mining.zip](Chronos%20ONE%20iGPU%20%E2%80%94%20Resident%20Execution%20&%20Projection/chronos-one-igpu-v3.8-asic-like-mining.zip)

The ZIP includes source, tests, pseudocode, reviewed Notion specifications, original assets, completion map, native and universal wheels, source distribution, reproducible benchmarks, raw observations and validation evidence. Native wheel: CPython 3.13/Linux x86-64 with OpenSSL libcrypto.so.3; not a universal or manylinux binary. The universal wheel has explicit hashlib execution. Source builds support portable C or an explicitly requested OpenSSL backend.

Archive SHA-256: `a6191113fcda46b906032542671ed45c244f9acb90639a3f47bb7d43a3ac7794`.

**Executed validation:** 263 tests passed, no failures/errors/skips; portable C mining tests separately passed all 46 tests. Both installed wheels passed doctor, exact-family CLI, negative and successful mining, checkpoint/restart and idempotent ABI retry checks. Source archive rebuilt into a wheel; all three distributions passed Twine metadata checks. Archive CRC and every manifested file hash passed.

**Publication:** Package artifacts are built and checked; no registry upload occurred. Physical ASIC/OpenCL/Apple hardware, Docker deployment and pool submission were not exercised. Remaining architecture requirements are still tracked, not discarded or described as completed.

### Exact compression math and fused execution

An 80-byte SHA256 first pass consumes two compression blocks; hashing its 32-byte digest consumes one. For N headers sharing their first 64 bytes, conventional independent execution uses 3N compression blocks. Preparing the common first-block midstate once uses **1+2N**. Rebinding the final 12 prefix bytes retains the common midstate; changing the first 64 bytes prepares a different entry.

The native loop releases the GIL and fuses nonce insertion, both hashes and little-endian uint256 target comparison. A negative batch returns completed-work metadata without materializing a Python digest for every nonce. Every reported winner is independently host-rehashed. Compression savings and output/dispatch savings are distinct from measured throughput.

```
owner := existing OneIGPU
owner.bind_mining_executor(prepared_SHA256d)
job := seal(prefix76, target_uint256, job_id, epoch)
ledger.activate(job)  # replacement epoch must increase
midstate := bounded_cache.prepare(prefix76[0:64])
context := midstate.rebind(prefix76[64:76])

full_solve_first_path:
    candidates := existing S1..S6, then F1..F3 as required
    for bounded batch of admitted owned candidates:
        completed, winner := fused_SHA256d_target_scan(context, batch, target)
        check batch coverage and winner ownership
        independently host_rehash winner before acceptance
    record actual completed hashes and whole-call elapsed time

scheduled_farm_path:
    partition lease into disjoint weighted lanes
    interleave bounded batches with bounded in-flight work
    check current epoch, deadline and cancellation before dispatch
    count and settle work already dispatched
    discard winners from a replaced job
    seal receipt(actual spans, completed count, resume cursor, backend)
    checkpoint receipt through original PRIME-DB

ABI retry:
    snapshot inputs; bind tenant + workload_id to request digest
    coalesce concurrent identical requests
    return independent copies of the cached receipt
    reject conflicting reuse; do not automatically repeat partial failures
```

### Runtime and service interfaces

- `configure_asic_like(require_native=True)` binds prepared execution beneath existing `mine`; S1–S6 remain active.
- `mine_asic` runs the scheduled farm API; it does not itself run S1–S6. Lanes, batches, in-flight tasks and receipt counts are bounded.
- `bind_asic_driver` validates an explicitly configured full-digest driver and independently checks its outputs. Vendor-specific candidate-only ASIC protocols are not yet implemented.
- `checkpoint_mining` / `restore_mining` use the existing durable owner and store.
- `asic_sha256d` is an admitted workload operation with job/lease/quota authority. Retry state is bounded and session-scoped, not durable global exactly-once execution.
- Service `--mining-backend reference|prepared|native` selects the executor; native mode fails closed when the extension is absent. Authenticated repeat requests and clean SIGTERM exit were tested.

### Adjacency benchmark: equal work, whole pipeline

[asic_v38_mining_notion_agent_chart.html](Chronos%20ONE%20iGPU%20%E2%80%94%20Resident%20Execution%20&%20Projection/asic_v38_mining_notion_agent_chart.html)

Same CPU host, fixed zero-target job, 4,096 nonces per sample, 30 randomized-order repeats per path, warmed preparation. Both full paths retain S1–S6, domain, target and budget.

| Scope | Reference | Prepared/native | Measured ratio |
| --- | --- | --- | --- |
| Whole solve-first pipeline | 411,369 SHA256d/s | 1,415,293 SHA256d/s | 3.44× |
| Compact scan only | 480,325 SHA256d/s | 6,610,561 SHA256d/s | 13.76× |

The kernel-only ratio is not the whole-miner ratio. These are repeated measurements of one fixed job on this CPU, not independent job-family, physical-ASIC, pool-accepted-share, power-efficiency or competitor results. Independent CSV/Decimal reconciliation verified the counters and elapsed-time denominators. Exact public Bitcoin genesis hash is included in correctness checks. Files: `benchmarks/asic-adjacency-results.json`, `benchmarks/asic-end-to-end-observations.csv` and `validation/asic-benchmark-reconciliation.json`.

### Documentation and public-technique provenance

[Integrate Chronus substrate across CPU, GPU, ASIC and Super ASIC mining](https://app.notion.com/p/Integrate-Chronus-substrate-across-CPU-GPU-ASIC-and-Super-ASIC-mining-8d32df49925d4ce69156788d361022a2?pvs=21) contributes the portable execution/verification contract; [Implement measured tensor, iGPU/GPU and ASIC runtime boundary](https://app.notion.com/p/Implement-measured-tensor-iGPU-GPU-and-ASIC-runtime-boundary-5829ab5530104d54a653589d6b3d56f1?pvs=21) contributes unchanged nonce ownership and measured execution; [Complete spec implementation: contracts, manifests, remote GPU, C++ artifacts](https://app.notion.com/p/Complete-spec-implementation-contracts-manifests-remote-GPU-C-artifacts-146c9259c8fc414480791539fd09d8b0?pvs=21) contributes sealed object and executor contracts. The package records all 24 reviewed Notion sources and preserves supplied notes verbatim.

`docs/PUBLIC_TECHNIQUES.json` distinguishes the published techniques actually applied: SHA256 block processing; bounded batch/pipeline patterns; fused hash/target work; conflicting-retry detection; and retained Apple MLX/Core ML bindings. Portable C execution is not represented as CUDA or XLA compilation. The named institutions and companies are an engineering quality reference, not participants or endorsers, and their entire know-how is not claimed to be incorporated.

Full instructions and implementation boundaries: `docs/ASIC_MINING.md`, `CHANGELOG-v3.8.md`, `docs/IMPLEMENTATION_STATUS.json` and `validation/RELEASE_REPORT.json`.

## Historical additive release — v3.7.0

### Preserve the completed core; elevate it

The supplied completed core remains the authority. All 52 original source files remain; 48 are byte-identical. Four export/facade/topology files are extended. The original lucas_engine.py is unchanged. No original source module is removed, and no replacement sequence engine is introduced.

This update adds exact family composition, Apple public-framework bindings, operator/publication tooling and concurrent evidence locking on top of the v3.6 integrated runtime.

### Publication artifacts

[chronos-one-igpu-v3.7-additive-release.zip](Chronos%20ONE%20iGPU%20%E2%80%94%20Resident%20Execution%20&%20Projection/chronos-one-igpu-v3.7-additive-release.zip)

[chronos_gpu-3.7.0-py3-none-any.whl](Chronos%20ONE%20iGPU%20%E2%80%94%20Resident%20Execution%20&%20Projection/chronos_gpu-3.7.0-py3-none-any.whl)

The ZIP contains the wheel, source distribution, source/tests, original core assets, unchanged supplied notes, source patch, equations, pseudocode, completion map, public-framework provenance and release evidence.

Archive SHA-256: `ddd22b6786452812988a50ce366ec830687a6d347281e8a24ab50dc5acde99d1`

**Executed:** 217 tests passed, 0 failures/errors/skips. Wheel and source distribution built; both passed Twine metadata validation. Installed wheel passed operator doctor, exact-family certificate verification and native neural-ranking checks. The source distribution rebuilt successfully into a wheel.

**Publication status:** Artifacts are ready to submit to a chosen registry; no registry upload has occurred. The supplied multi-OS/Python CI matrix is a delivered definition, not an executed matrix. Full-architecture production qualification remains incomplete: Apple/OpenCL target hardware and Docker deployment were not exercised here; the previously recorded ISA/600-cell/TT-MPO/pool gaps remain explicitly tracked below.

## Additive mathematical layer

The original `lucas_engine.py` remains the sequence authority. The added module uses that authority and the exact quadratic field Q(phi), not rounded phi values.

Write an element as a+b phi. From phi²=phi+1:

- product: `(a+b phi)(c+d phi) = (ac+bd) + (ad+bc+bd) phi`;
- conjugate: `(a+b)-b phi`;
- trace: `2a+b`;
- norm: `a²+ab-b²`.

For nonnegative n, `phi^n=(F_(n+1)-F_n)+F_n phi`. Its trace is L_n, and its norm is (-1)^n. Therefore `L_n²-5F_n²=4(-1)^n` is an exact cross-family check, not a floating proximity condition.

## Pair and three-way composition

A Fibonacci orbit stores `(F_n,F_(n+1))`. Multiplication of companion matrices gives:

```
F_(m+n)   = F_m F_(n+1) + (F_(m+1)-F_m) F_n
F_(m+n+1) = F_m F_n + F_(m+1) F_(n+1)
```

Three-way composition is associative: `(Q^a Q^b) Q^c = Q^a (Q^b Q^c)`. The module verifies the result against the supplied fast-doubling core. Mixed compositions of up to sixteen indexes are accepted within the bounded index/bit domain.

The triple-index consequences are executable checks:

```
L_(3n) = L_n³ - 3(-1)^n L_n
F_(3n) = F_n (L_n² - (-1)^n)
```

Binet representation, Lucas trace, norm/Pell-Cassini residue and Zeckendorf encodings are sealed into one certificate. Verification recomputes every declared field from the original exact core and rejects tampering. The certificate is an identity/replay record, not a claim of cryptographic proof-of-work.

## Engineering insight

These families are not unrelated constants multiplied together: they are representations and invariants of the same algebraic orbit. Combining them can give complementary exact checks and alternative composition paths. Three-way composition stays inside a two-dimensional exact coefficient space; it does not require constructing a three-dimensional amplitude array. This is a concrete storage/verification simplification to test against each workload, rather than an assumed throughput gain.

```python
from chronos import OneIGPU, PhiElement, FibonacciOrbit, FamilyCertificate
with OneIGPU() as gpu:
    certificate = gpu.family_certificate([10, 12, 15])
    assert FamilyCertificate.verify(certificate)
    assert certificate['combined_index'] == 37
```

## Apple public-framework extension

Apple’s published MLX design exposes unified memory, explicit CPU/GPU streams and lazy materialisation. The extension applies these through an optional MLX tensor adapter beneath the existing OneIGPU owner. Core ML model bindings expose the documented permitted compute-unit policies. These are public APIs and documented techniques, not private Apple designs or an affiliation claim.

- `MLXOverlay`: real floating tensor operations, explicit GPU stream, `mx.eval` before timing/receipt, host numeric validation. Exact sequence and SHA256d requests remain on compatible executors.
- `LinearNeuralRanker`: native dense/ReLU execution with supplied weights, stable candidate permutation and model digest. No trained Bitcoin prediction model is bundled.
- `CoreMLRanker`: bounded, optionally hash-pinned .mlmodel, named input/output and permitted compute units. Actual per-layer Neural Engine dispatch remains unknown unless supplied by target evidence.
- `gpu.neural_rank`: rejects invented, dropped or duplicated candidates; its ordering can enter the existing solver callback without changing job/lease/target authority.

Public sources: [MLX WWDC25](https://developer.apple.com/videos/play/wwdc2025/315/) and [Core ML compute units](https://developer.apple.com/documentation/coreml/mlcomputeunits).

## Publication and operator interface

```bash
python -m pip install chronos_gpu-3.7.0-py3-none-any.whl
chronos-igpu doctor
chronos-igpu family 10 12 15 > family.json
chronos-igpu verify-family family.json
```

The source package includes compatible dependency metadata, platform-marked Apple/OpenCL extras, full MIT license text preserving original authorship, authenticated service entry point, and Linux/Windows/macOS × Python 3.10–3.13 CI definition. Detailed instructions are in `docs/PUBLICATION.md` and target status is in `docs/IMPLEMENTATION_STATUS.json`.

The quality bar is the technical depth and discipline of the institutions named by the user. Their participation or endorsement is not asserted.

## Historical integrated release — v3.6.0

The attached standalone baseline has been elevated into one owning iGPU runtime. The logical device is independent of physical GPUs; physical OpenCL and authenticated remote executors compose beneath that same owner. Golden Quantum solve-first execution is enabled by default.

**Executed validation:** 189 tests passed; 0 failures, errors or skips. Installed-wheel smoke tests, packaged kernels/notes, persistent certified objects, ABI receipts, authenticated loopback dispatch, paradigm gates and archive-integrity checks passed. OpenCL Lucas and SHA256d source passed native C++ conformance; that is not a physical-GPU dispatch result.

**Completion status:** The integrated standalone core is delivered. This is not yet fully target-qualified production or complete repository parity. Physical OpenCL dispatch and Docker deployment were not run on this host. Direct vendor/ASIC/MMIO/RTL interfaces remain unbound; Chronus-1 binary ISA, H4/600-cell, general TT/MPO and pool transport remain not implemented in this release. These requirements are preserved explicitly in the completion map, not dropped or relabelled as research.

## Download current implementation

[chronos-one-igpu-v3.6-standalone-elevated.zip](Chronos%20ONE%20iGPU%20%E2%80%94%20Resident%20Execution%20&%20Projection/chronos-one-igpu-v3.6-standalone-elevated.zip)

The archive includes source, installable wheel, all 189 tests, pseudocode, implementation/completion map, 23-source manifest, four unedited supplied-note records, original native/math/graphics assets, Docker/service configuration, benchmark evidence and a source patch against the attached baseline.

Archive SHA-256: `15237edaa54a348bba3db7e7633a189f4f9da07cddeb01a5f2f02f4c43467ddc`

## Architecture and ownership

ONE logical `chronos_igpu` exists independently of any physical GPU. `OneIGPU` owns the exact core, Golden Quantum runtime, storage, planner, fabric and receipts. `SuperGPU` and `InfinityGPU` are compatibility aliases over this same owner, not additional GPUs.

Native execution uses host CPU/NumPy/hashlib. Physical host-GPU execution is composed through an OpenCL adapter; the adapter executes multi-limb Lucas and SHA256d kernels and reports the bound device. Authenticated remote host agents can bind to that same fabric. Native independence and physical-overlay capability are distinct, both represented in the contract.

## Core pseudocode

```
igpu := OneIGPU(mode=standalone, solve_first=true)
executor_inventory := igpu.compose()
plan := stream(base_items * exact_Lucas(scale_index), address_limit)
route := igpu.route(operation, scale_index)
admit(workload_id, tenant, budget, epoch, deadline, trust_class)

S1 := exact_pair_fold(candidates) + lossless_byte_fold + phi_phase_transform
S2 := job_epoch_bound_prime_gap_checkpoint(S1)
S3 := normalize_and_check_coherence(S1)
S4 := finite_Mandelbrot_boundary_rank(S3)
S5 := bounded_infinity_fold_interleave(S4)
S6 := Chronos_Hermitian_eigensolve(S5)
for candidate in S6:
    execute_exact_SHA256d_and_check_target(candidate)
if no verified result:
    F1 := GoldenQuantum_phi_feedback(actual_hash_oracle, remaining_budget)
    F2 := golden_stride_bijection(remaining_owned_nonces)
    F3 := remaining_owned_nonce_coverage
execute only admitted, disjoint owned work on the selected executor
host_recheck every device-reported successful candidate
receipt := bind(workload, logical_device, executor, capability, rung,
                partition, completed_work, elapsed_time, output_digest, trust)
seal_chain(receipt); optionally_HMAC_sign; retain_trusted_head
```

The Golden Quantum runtime is enabled by default. An explicitly disabled solve-first path exists only for a classical baseline. Quotas, epoch checks, deadlines, normalization, exact target checks and resource admission apply to both paths.

## Mathematical contracts

- Exact pair node stores `(sum=left+right, left)`; right is `sum-left`. Rationals preserve exact reconstruction. Selective restoration reads requested leaf pairs only; `scale()` operates directly on every folded pair.
- Exact Lucas, Fibonacci, Cassini, Zeckendorf and prime-address records retain integer authority. Binet/Pisot decimal projection carries an explicit residual and is not used as integer authority.
- `N_eff = min(base_items * L_n, address_limit - start)`. Declared ladder: 10, 12, 15, 18, 20, 31, 50, 76, 110. Scaling expands logical work windows and lane-aligned dispatch. Executed throughput is obtained from timed dispatches.
- Hamiltonian evolution is `exp(-i H t)` on bounded complex128 vectors with Hermitian validation. Golden phase feedback uses phi-derived phases, actual oracle masks and explicit oracle call counts.
- Eleven-dimensional norm is `sqrt(sum(phi**i * x_i**2))`; fold is `x/(1+sqrt(1+norm**2))`. Its inverse is `2*y/(1-norm(y)**2)`. Exact transport is separate: bit-preserving IEEE64 certificates encoded with Zeckendorf.
- The UCI registers physical constants as software kernel parameters; its h override binds normalized Hamiltonian evolution time. No receipt claims a change in the external physical constants.
- Large prime-gap indexes retain symbolic address expressions (including 2^100+) while resolved payloads are durable finite objects.

## Storage, folds and Docker

Default combined budget: 100,000,000,000 bytes. Example image reserve: 4,000,000,000 bytes, **a configured reserve rather than a measured build size**. A 10,000-bit basis witness occupies 1,250 payload bytes; packed records add 40 bytes before indexes, allocation, metadata and program traces. At 96 GB, the payload-only ceiling is 76.8 million, not a demonstrated usable capacity.

Witnesses are packed into content-addressed shards with a SQLite index and circuit-program trace. X/CNOT/SWAP basis-permutation execution records input, program and result addresses; replay independently verifies the program and result. Docker layers distribute the program; the volume holds cache shards. Representation dimension, folds/s, actual SHA256d/s and accepted pool shares are separate fields.

SCALE1–SCALE10 are tracked in `scaling_validation.py`: image budget; combined budget; native/overlay/pipeline availability; representation dimension; measured 10 EH/s floor; attestation; replay; trusted-head custody; observed genetic tuning; exact invariants. Unknown image size remains unknown. The supplied scaling derivation and its corrections remain verbatim under `docs/source_notes`; an earlier symbolic multiplier is not silently turned into executed hashes.

## Integration map

| Mechanism | Code | Status |
| --- | --- | --- |
| Single independent iGPU and physical host composition | `src/chronos/igpu/{facade,fabric,overlay,remote}.py` | IMPLEMENTED |
| Exact Lucas/Pisot/Zeckendorf/Cassini/Binet datapath | `src/chronos/lucas*; src/chronos/igpu/kernels/lucas256.cl` | IMPLEMENTED |
| Lucas ladder and scaled workload windows | `src/chronos/igpu/scaled_plan.py` | IMPLEMENTED |
| Golden Quantum Hamiltonian/state/oracles/search | `src/chronos/golden_quantum/{quantum_state,oracles,search}.py` | IMPLEMENTED |
| S1–S6 solve-first and F1–F3 fallback | `src/chronos/igpu/golden_runtime.py` | IMPLEMENTED |
| Exact pair fold, selective unfold and native scale | `src/chronos/igpu/exact_fold.py` | IMPLEMENTED |
| 1–3D phase transforms and byte folding | `src/chronos/golden_quantum/data_folding.py` | IMPLEMENTED |
| Prime-gap persistence, Infinity Fold, large logical addresses | `src/chronos/golden_quantum/{memory,infinity_fold}.py; src/chronos/igpu/store.py` | IMPLEMENTED |
| Mandelbrot stabilization and coherence | `src/chronos/golden_quantum/{mandelbrot,coherence}.py` | IMPLEMENTED |
| UCI parameters and Hamiltonian binding | `src/chronos/golden_quantum/uci.py` | IMPLEMENTED |
| Tensor, MPS, original graphics/theory/academic math | `src/chronos/igpu/tensor_runtime.py; src/chronos/{engine,academic,theory}` | IMPLEMENTED |
| 11D phi geometry and exact transport certificates | `src/chronos/igpu/geometry11d.py` | IMPLEMENTED |
| QX command buffer, weak measurement and barrier/descriptor execution | `src/chronos/igpu/qx.py` | IMPLEMENTED |
| Certified MLA ingestion and five retrieval views | `src/chronos/igpu/contracts.py` | IMPLEMENTED |
| virtual_igpu_v1, tenants, admission, daemon/client | `src/chronos/igpu/{virtual_abi,service,remote}.py` | IMPLEMENTED |
| GPU SHA256d, unchanged target and host candidate verification | `src/chronos/igpu/kernels/sha256d.cl; src/chronos/igpu/fabric.py` | IMPLEMENTED |
| Swarm partition, vertical bounds, temporal pipeline | `src/chronos/igpu/control.py; src/chronos/igpu/overlay.py` | IMPLEMENTED |
| Guardian, genetic optimization and floor evaluator | `src/chronos/igpu/{control,scaling_validation}.py` | IMPLEMENTED |
| 100GB witness cache, attestation and replay | `src/chronos/igpu/witness_cache.py` | IMPLEMENTED |
| Hash-chain custody and optional HMAC evidence | `src/chronos/igpu/golden_runtime.py` | IMPLEMENTED |
| Paradigm thesis, schedule conformance and chaos | `src/chronos/paradigm` | IMPLEMENTED |
| Baseline and folded-witness benchmark | `benchmarks/run_standalone_elevation.py` | IMPLEMENTED |
| Production packaging and shutdown | `Dockerfile; compose.yaml; src/chronos/igpu/service.py` | IMPLEMENTED_TARGET_VALIDATION_PENDING |
| Native vendor/ASIC/MMIO/RTL execution and real sensor stack | `src/chronos/igpu/fabric.py` | UNBOUND_TARGET_INTERFACES |
| Repository-specific Chronus-1 binary ISA, H4/600-cell fabric and TT/MPO extensions | `docs/SOURCE_MANIFEST.json` | NOT_IMPLEMENTED_IN_THIS_RELEASE |
| Pool network job/acknowledgement transport | `src/chronos/golden_quantum/mining.py` | NOT_IMPLEMENTED_IN_THIS_RELEASE |

## Actual execution and remaining target checks

The release includes software tests, native C++ conformance of the OpenCL source, the public Bitcoin genesis-vector benchmark, an authenticated loopback service/client test, and the executable paradigm report. See `validation/RELEASE_REPORT.json`, JUnit XML and benchmark JSON for the executed results.

Physical OpenCL dispatch was not executed on this host: no compatible platform was available. Docker build, TLS container deployment, vendor/ASIC/MMIO/RTL binding, pool transport, hardware-root attestation and power sensors were not validated here. The explicit nonimplemented entries in the map are retained rather than called complete. This ZIP is not the original repository binary ISA/600-cell/TT-MPO implementation.

The baseline native source, graphics and academic/theory code are retained. Original source APIs already in the ZIP remain available. New formulas are explicit standalone implementations from the reviewed specifications; they are not represented as byte-for-byte canonical repository imports.

## Usage and verification

```bash
python -m pip install .
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m chronos.paradigm
PYTHONPATH=src python benchmarks/run_standalone_elevation.py --size 256 --runs 5
```

```python
from chronos import OneIGPU
from chronos.golden_quantum import NonceLease
with OneIGPU(db_path="prime.db") as gpu:
    exact = gpu.dispatch([10, 12, 15, 18, 20]); exact.verify()
    plan = gpu.scaled_plan(base_items=256, scale_index=15)
    folded = gpu.fold_exact([1, 2, 3, 4])
    assert folded.unfold_partial([0, 3]) == (1, 4)
    outcome = gpu.mine(bytes(76), 0, NonceLease(0, 256), max_evaluations=256)
    inventory = gpu.compose()

# Explicit physical host composition; fail closed if the device is unavailable.
# Requires a configured host OpenCL ICD and pyopencl (package extra [opencl]).
with OneIGPU(mode="host_gpu_overlay", require_accelerator=True) as gpu:
    result = gpu.dispatch([15]); result.verify()
```

### Authenticated service

Provide `CHRONOS_SERVICE_TOKEN` privately (minimum 32 characters). No token is embedded. Local-only execution:

```bash
python -m chronos.igpu.service --host 127.0.0.1 --db-path ./state/prime.db
```

`compose.yaml` requires `CHRONOS_TLS_DIR` with `cert.pem` and `key.pem`, readable by UID 10001; the certificate must cover the healthcheck host `127.0.0.1`. It also requires the private token. Non-loopback binds reject absent TLS. The included policy TOML is a constructor/CLI configuration reference, not an automatically loaded config file. Before deployment measure image size, set the cache image reserve to that measured figure, check certificates, validate mounted storage permissions and run target conformance. Pin the Python base image by digest in your deployment.

## Provenance and single record

`SOURCE_MANIFEST.json` lists all reviewed sources and how each was used. `source_notes/MANIFEST.json` hashes every unedited supplied note. The consolidated Notion record mirrors this implementation, pseudocode, map, validation and remaining target checks. No GitHub/repository retrieval is required to install or run this standalone package.

## Reviewed source index

- [Golden Quantum Search Framework — Formal Verification & Benchmarking Package](../Golden%20Quantum%20Search%20Framework%20%E2%80%94%20Formal%20Verificat%204c570b8df65342089342464e2d12f11e.md) — Golden Quantum module/class inventory, executable math interfaces and historical suite provenance.
- [Golden Quantum Framework: Architecture & Evolution](https://app.notion.com/p/Golden-Quantum-Framework-Architecture-Evolution-449671c29bc14fd1a3c1509696f6a0dc?pvs=21) — Independent iGPU, optional host composition, capability routing, partitions and evidence.
- [Golden Quantum — Research Advancement & Institutional Validation Roadmap](https://app.notion.com/p/Golden-Quantum-Research-Advancement-Institutional-Validation-Roadmap-c79745a4c61e4210933751d9931e1f65?pvs=21) — Benchmark budgets, equal-work controls and deployment checks.
- [PYTHIA Mining-First Wiring Checklist](https://app.notion.com/p/PYTHIA-Mining-First-Wiring-Checklist-cbf3cbd3cb764b66a8798ba45da76dc6?pvs=21) — Default S1–S6 solve-first with F1–F3 fallback and target authority.
- [PYTHIA Production Cut Plan — P0/P1/P2 Fixes Applied](https://app.notion.com/p/PYTHIA-Production-Cut-Plan-P0-P1-P2-Fixes-Applied-20b5c5f70ad347afa294831fc2d11dc9?pvs=21) — Actual counters, configuration, non-root deployment, shutdown.
- [feat: integrate audited Golden Quantum research framework](https://app.notion.com/p/feat-integrate-audited-Golden-Quantum-research-framework-dcae4ac6af404ac08cba81c24fd955f2?pvs=21) — Bounded finite math, exact digest authority and quotas.
- [Build canonical Chronus Virtual iGPU runtime](https://app.notion.com/p/Build-canonical-Chronus-Virtual-iGPU-runtime-c4a55c294db54fd883df6d86b0af0120?pvs=21) — Versioned standalone ABI, tenant admission and receipts.
- [chronus: close post-#94 iGPU findings — alias gating, iGPU classification, kernel launch bounds](https://app.notion.com/p/chronus-close-post-94-iGPU-findings-alias-gating-iGPU-classification-kernel-launch-bounds-8adb993db02248f28834ddc4665fba00?pvs=21) — iGPU identity classification and kernel launch bounds.
- [chronus/measurement: 11-layer iGPU tech-stack measurement — attested, replayable, nothing fabricated](https://app.notion.com/p/chronus-measurement-11-layer-iGPU-tech-stack-measurement-attested-replayable-nothing-fabricated-e8445dcc18634837a90bf854f4faf082?pvs=21) — Elapsed work evidence, replay and explicit unknown sensor fields.
- [Implement measured tensor, iGPU/GPU and ASIC runtime boundary](https://app.notion.com/p/Implement-measured-tensor-iGPU-GPU-and-ASIC-runtime-boundary-5829ab5530104d54a653589d6b3d56f1?pvs=21) — Tensor APIs and unchanged certified nonce coverage.
- [fix(pythia): restore canonical mining authority and full intelligence arsenal](https://app.notion.com/p/fix-pythia-restore-canonical-mining-authority-and-full-intelligence-arsenal-a2a875e3a1ac48bf9d690324b9ed17af?pvs=21) — Authority/context retained; standalone virtual ABI is not represented as the original Chronus-1 binary ISA.
- [Port quantum_compute_substrate v0.4.2 — PULVINI + 1000-qubit MPS + X-Infinity tensor (verified 1,488 tests)](https://app.notion.com/p/Port-quantum_compute_substrate-v0-4-2-PULVINI-1000-qubit-MPS-X-Infinity-tensor-verified-1-488-76422392396e4a6cae6cfc0b7bbfe5cc?pvs=21) — Exact pair folding/selective unfolding plus baseline MPS retained; encoding explicitly specified.
- [audit: quantum truth, tensor safety, and real QPU boundary](https://app.notion.com/p/audit-quantum-truth-tensor-safety-and-real-QPU-boundary-30e4c84b11844b418461a92c326b3492?pvs=21) — Hermitian/unitary checks and opt-in lossy MPS admission.
- [feat(chronus): establish executable QX command contract](https://app.notion.com/p/feat-chronus-establish-executable-QX-command-contract-146747594c0a4ff98161301722c98341?pvs=21) — Executable standalone QX commands, descriptors and barriers.
- [Consolidate July Geodesic Tensor capabilities into Chronus/Tensor](https://app.notion.com/p/Consolidate-July-Geodesic-Tensor-capabilities-into-Chronus-Tensor-27dcb49a329c4118a5840cfde99c0faa?pvs=21) — One owning facade, bounded tensor APIs and partial unfolding.
- [Enterprise — standalone MLA1517 iGPU, PRIME-DB, and sovereign storage implementation](https://app.notion.com/p/Enterprise-standalone-MLA1517-iGPU-PRIME-DB-and-sovereign-storage-implementation-8efcce1164d24cdbaa4685c7d8d6164e?pvs=21) — Independent product packaging and service.
- [gpu engine: Lucas-rung scaling + real device binding (no silicon expectation)](https://app.notion.com/p/gpu-engine-Lucas-rung-scaling-real-device-binding-no-silicon-expectation-3f3411d7e25c449db0087d32ba47f3f0?pvs=21) — N_eff=base_items*L_n, declared ladder, domain clamp.
- [chronus: enumerate contract device as system GPU; event-driven mining waits](https://app.notion.com/p/chronus-enumerate-contract-device-as-system-GPU-event-driven-mining-waits-94d69172a55b4b4896a6d3f8e4ad100a?pvs=21) — Logical device independent of physical host; lane-aligned dispatch.
- [Super-GPU elevation gap-fill on the Chronus substrate](https://app.notion.com/p/Super-GPU-elevation-gap-fill-on-the-Chronus-substrate-b7dbabf8d788497487b3572ac8cd2e92?pvs=21) — Single-owner compose/route/execute.
- [Complete spec implementation: contracts, manifests, remote GPU, C++ artifacts](https://app.notion.com/p/Complete-spec-implementation-contracts-manifests-remote-GPU-C-artifacts-146c9259c8fc414480791539fd09d8b0?pvs=21) — Exact/folded/projection/proof/executable views, address and durable object custody.
- [Lucas/Pisot research: semantic precision contracts and falsification](https://app.notion.com/p/Lucas-Pisot-research-semantic-precision-contracts-and-falsification-0ba827811a9d4665873f8669c42f9550?pvs=21) — Multi-limb kernel, host exact verification.
- [#106 MATHEMATICAL_INTRINSICS: typed exact and approximate Chronus semantics](https://app.notion.com/p/106-MATHEMATICAL_INTRINSICS-typed-exact-and-approximate-Chronus-semantics-387ee3624e6b4b788bf1f720fae65d8e?pvs=21) — Integer/rational exactness separate from floating views.
- [Elevate Chronus into an evidence-bound portable compute substrate](https://app.notion.com/p/Elevate-Chronus-into-an-evidence-bound-portable-compute-substrate-bdca92422aaf46b4b712cf037a14a510?pvs=21) — Measured genetic promotion, bounded pipelines and execution evidence.

## Previous release — historical attachment

This v3.5 attachment is preserved as history, not as the current plan. Its prior CPU-only/default-off and repository-source dependency descriptions are superseded by the v3.6 implementation above.

[chronos-one-igpu-v3.5-golden-integrated.zip](Chronos%20ONE%20iGPU%20%E2%80%94%20Resident%20Execution%20&%20Projection/chronos-one-igpu-v3.5-golden-integrated.zip)