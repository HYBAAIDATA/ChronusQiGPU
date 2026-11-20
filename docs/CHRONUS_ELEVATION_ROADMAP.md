# Chronus Elevation Roadmap

> **15 Nov close-out update:** The generic fleet CUDA adapter remains probe/gate-only, but the maintained tensor package now has explicit fail-closed CUDA C and Metal/MLX execution backends, alongside the OpenCL tensor backend. These tensor routes are implemented software surfaces; physical performance and promotion remain device-evidence gated. Durable THESEUS custody and the OVID transform/materialisation contract are now implemented under the canonical triad. See [TRIAD_PRODUCTION_CLOSEOUT.md](production/TRIAD_PRODUCTION_CLOSEOUT.md).

**Product owner:** HYBA Data
**Original roadmap date:** 2026-10-08
**Audited and elevated:** 2026-11-13
**Source baseline:** `89aa86851eb3b56cd8d4276a3d847d9bc66b64d4`
**Status:** active engineering roadmap; not a release decision or hardware qualification

## 0. Executive decision

Retain the elevation objective, but execute it on the active `src/chronus/fleet` architecture. The October plan refers to `aethel/chronus.py`, `chronus/virtual_igpu`, and `chronus/seam/scale.py`; those paths are not present in the audited source tree. Recreating them would produce a competing scheduler and duplicate evidence semantics.

Chronus owns admission, kernel/version negotiation, exact route applicability, tile scheduling, execution records, verification, recovery, topology, entitlement, and receipts. Vendor SDKs are optional execution routes, not the architecture's identity.

This revision **replaces rather than deletes** every proposed expansion surface:

- invalid evidence becomes an explicit `NOT_RUN`, `UNAVAILABLE`, or `NOT_MEASURED` record with a promotion gate;
- legacy paths map to their active replacements;
- role and memory proposals remain visible, but cannot bypass kernel correctness or finite-resource accounting;
- consortium resources remain research projections and are never summed into physical fleet capacity;
- Bitcoin mining remains an in-house treasury activity, not a customer product.

### Evidence vocabulary

| Label | Meaning |
|---|---|
| **Implemented** | Source exists; this alone is not a passing test or release claim. |
| **Locally checked** | The exact checks in §8 ran on this working tree. It is not independent CI or hardware qualification. |
| **Reported** | A worker, OS, driver, or device supplied the value. It is not necessarily measured or coordinator-verified. |
| **Measured** | A timed execution produced the value, with its workload, route, and time window. |
| **Projected** | A design envelope or roadmap target; excluded from physical capacity and performance claims. |
| **Unavailable / NOT_RUN** | No qualifying execution occurred. The absence remains visible rather than being replaced by simulated success. |

## 1. Audit findings and dispositions

| Original item | Finding | Elevated disposition |
|---|---|---|
| **2.1 Aethel CU configuration** | The named Aethel implementation is absent. Active host discovery and logical-lattice configuration already exist in `chronus.fleet.capacity` and `chronus.fleet.lattice`. | **Replaced and locally closed.** Use discovered host CPU/memory reports and configured logical rungs; do not invent SM counts. Host capacity now reaches join, status, and signed device receipts. |
| **2.2 Fleet scheduler** | `FleetCoordinator`, `LeaseScheduler`, exact tile partitioning, expiring leases, stealing, recovery, and per-device receipts already exist. The generic fleet schedules kernel tiles; nonce partition logic is workload-specific. | **Retain and harden.** Do not build a second coordinator. Join order now uses a deterministic sequence even when timestamps tie. Physical multi-host performance remains unmeasured here. |
| **2.3 Adapters** | Reference and NumPy SIMD routes are active; native SIMD is optional; Metal and OpenCL kernels exist but were not run on their physical GPUs in this audit; CUDA is probe-only. ROCm, oneAPI, Azure, and GCP are not active fleet routes. | **Partially implemented.** Preserve every backend as a gated roadmap row. Promotion requires a real kernel, known-answer tests, exact output checks, and raw device evidence. |
| **2.4 Heterogeneous roles** | Arbitrary institution-style role labels would add a weaker parallel authority beside kernel/version and `Kernel.accepts()` exact applicability. | **Replace the mechanism, retain the objective.** Kernel capability is the current routing contract. Add operator-declared placement constraints only for a concrete workload that kernel eligibility cannot express; never infer institutional or hardware authority from a role string. |
| **2.5 Memory tiers** | Commercial storage entitlement in `phase.py` is not physical memory. Host memory and OpenCL device memory probes are separate from remote allocation. | **Retain as a four-tier research contract with explicit states.** Report finite local values; do not declare unbounded remote memory or usable quantum RAM. No memory tier changes scheduling without an implemented allocator and enforcement tests. |
| **Effective capacity** | Logical lanes, physical compute units, entitlement, calibrated rate, and measured throughput were at risk of being conflated. | **Keep separate fields and sources.** Never advertise `4 adapters = 4x throughput`; measure the complete fleet workload instead. |
| **Elevation evidence** | The legacy Mode B path copied a CPU hash and could emit accelerator `PASS`/`MEASURED` from a device probe. The CSV derived p95 as `1.5 x p50` and included unexecuted environment timings. | **Locally closed.** Mode B executes the CPU reference with an explicit not-implemented reason. CSV rows contain only single-run timings actually taken locally; Docker/Azure remain as `NOT_RUN` gates. |

### Mathematical and capacity corrections

1. **Hilbert dimensions multiply under tensor products.** Ten 32-dimensional factors give `32^10 = (2^5)^10 = 2^50`, not `2^640`. A `2^640` tensor product requires ten `2^64`-dimensional factors. SPMD lane count is not a Hilbert dimension. Neither expression is a Chronus memory or throughput claim, and Chronus does not materialize that joint state.
2. **Nominal bandwidth is not effective fleet bandwidth.** A sum of driver-reported link rates may be labelled `reported_aggregate_nameplate_bandwidth` only. `effective_aggregate_bandwidth` requires a synchronized, repeatable fleet measurement including transport and contention.
3. **Remote capacity is never unbounded.** Every implemented allocation needs a finite configured limit, source, units, and failure state.
4. **Deterministic eligibility needs contract tests, not a 95% target.** If placement constraints are added, every admitted placement must satisfy them; statistical role-selection accuracy is not the acceptance metric.
5. **Detection has no meaningful `>= 2x accuracy` target without labeled ground truth.** Acceptance instead requires exact fixtures, valid platform fallbacks, malformed-input rejection, and explicit unknown values.

## 2. Active implementation map

| Concern | Active source | Replacement for the October path |
|---|---|---|
| Host CPU and memory discovery | `src/chronus/fleet/capacity.py` | Aethel CU detection; logical CPUs and memory are not SMs |
| Logical scheduling lattice | `src/chronus/fleet/lattice.py` | Configurable 80 / 800 / 8,000 logical units, not physical cores |
| Adapter probes and self-tests | `src/chronus/fleet/adapters.py` | `virtual_igpu/adapters.py` capability manifest |
| Fleet coordination | `src/chronus/fleet/coordinator.py`, `scheduler.py` | Proposed new fleet coordinator |
| Workload eligibility | `src/chronus/fleet/kernels.py`, `workunit.py` | Role-only negotiation is subordinate to exact kernel applicability |
| Execution and verification evidence | `src/chronus/fleet/receipts.py`, `verification.py` | Per-device evidence ledger and same-hash checks |
| Entitlement and scaling | `src/chronus/fleet/phase.py`, `scale.py` | Commercial/storage entitlement, not measured physical capacity |
| OpenCL / Metal / CUDA | `src/chronus/fleet/opencl.py`, `metal.py`, `cuda.py` | Vendor adapter integration points |
| Mining-specific partitioning | `src/chronus/execution/mining.py` and internal treasury tooling | Generic fleet code does not claim nonce consensus authority |

## 3. Gaps closed in this working-tree revision

### 3.1 Evidence repair

- `run_mode_b()` retains Mode B but always records the CPU-reference route because this legacy deterministic workload has no OpenCL kernel. A present device produces `OPENCL_EXECUTION_NOT_IMPLEMENTED`; an absent one produces `OPENCL_UNAVAILABLE`. Both produce `device_run=NOT_RUN` and `hashrate=NOT_RUN`.
- The CPU result is recomputed independently and compared with Mode A; it is no longer copied forward as proof of accelerator execution.
- The legacy quantum-walk API remains available but is explicitly a **classical deterministic walk**, with no quantum-semantics or accelerator-speedup claim. TURING remains the canonical complex-Hilbert-space mathematics package.
- `backend_matrix.csv` retains local Mode A/B rows and Docker/Azure control rows. The original `t_p50/p95` column remains in its original position but is explicitly `NOT_MEASURED`; appended fields carry actual single-run `perf_counter` wall time, timing basis, and device-probe state. Controls are `NOT_RUN`, `NOT_MEASURED`, and carry explicit environment gates.
- The OpenCL probe checks GPU devices across all platforms rather than treating any device on the first platform as GPU evidence.

### 3.2 Resource provenance

- `discover_host()` now uses `/proc/meminfo` when available and a platform memory probe otherwise, including `GlobalMemoryStatusEx` on Windows. Unknown memory stays `None`; its source is explicit.
- Every worker includes host CPU affinity, cgroup bound, available CPU count, total memory, and memory source in its join payload.
- The coordinator validates this payload before admission, marks it `measured: false` and **worker-reported / not independently verified**, then exposes it in node status and each signed device receipt.
- These values describe capacity only. They do not set scheduling weights, prove available free memory, or establish hardware attestation.

### 3.3 Deterministic fleet admission

- Each node receives a monotonically increasing coordinator-local join sequence.
- Downgrade rebalance removes the newest joined node first; waiting-node readmission uses the oldest sequence first.
- Timestamp ties therefore cannot reverse admission order or make test outcomes nondeterministic.

## 4. Backend capability and promotion matrix

| Backend / environment | Current source state | Evidence in this audit | Promotion gate |
|---|---|---|---|
| Pure Python reference | Implemented | Locally exercised | Retain as exact reference; no acceleration claim |
| NumPy SIMD / Chronus iGPU Mode A | Implemented | Locally exercised | Record actual route and timed contribution |
| Native C++ SIMD | Optional implemented route | Hardware/library-dependent tests only | Load identified library; known answers and tile parity |
| Intel / other OpenCL GPU | Kernels and adapter implemented | **Not executed on OpenCL GPU silicon here** | Device/driver identity, all applicable known answers, exact fleet result, raw receipt |
| Apple Metal (MLX / PyObjC) | Kernels and adapter implemented | CPU stand-in arithmetic tests only; **not executed on Apple GPU silicon here** | Identified Apple device, both applicable engines as supported, known answers and raw receipt |
| NVIDIA CUDA | Generic fleet route remains probe-only; explicit tensor CUDA C backend is implemented in `src/chronus/tensor/cuda_backend.py` | Software route present; physical device not evidenced here | Identified CUDA device, parity, current timings and raw receipt before promotion |
| AMD ROCm | No active fleet route | **Unavailable / NOT_RUN** | New route contract, real kernels, known answers, hardware receipt |
| Intel oneAPI | No active fleet route | **Unavailable / NOT_RUN** | New route contract, real kernels, known answers, hardware receipt |
| Docker control | Environment row retained | `DOCKER_ENVIRONMENT_NOT_EXECUTED` | Build and run the declared container; retain image digest and raw log |
| Azure GPU | Environment row retained; no active adapter | `AZURE_ADAPTER_NOT_IMPLEMENTED` | Authenticated configured resource, finite manifest, real execution and cloud evidence |
| GCP GPU | Roadmap row retained; no active adapter | **Unavailable / NOT_RUN** | Authenticated configured resource, finite manifest, real execution and cloud evidence |
| Photonic / quantum hardware | No execution backend | **Theoretical / NOT_RUN** | External owner evidence and a separately reviewed execution contract; never emulate success |

No route is promoted because an SDK imports, a device string exists, or a CPU result matches itself. Explicitly named unavailable routes fail closed in the fleet. `auto` fallback must preserve the actual executed route and reason.

## 5. Elevated delivery phases

### Phase 0 — Evidence integrity (local implementation complete; broader qualification open)

**Completed replacement:** truthful Mode B records, single-run timing labels, retained `NOT_RUN` controls, classical-walk classification, and regression tests for a false hardware-present probe.

**Remaining gate:** run equivalent checks in CI on the exact candidate commit and preserve raw outputs. This does not alter the repository's current **NOT QUALIFIED** release decision.

### Phase 1 — Configuration and detection (local implementation complete)

**Completed replacement:** platform memory fallback and provenance; validated worker capacity records in join/status/receipts; deterministic join ordering under timestamp ties.

**Next elevation:**

1. Add available-memory and cgroup-memory limits where supported; do not substitute total memory for free memory.
2. Add per-route memory limits only from identified OS/driver fields, with `reported` provenance.
3. Exercise discovery on Linux, macOS, and Windows runners and retain platform-specific raw records.
4. Treat malformed or inconsistent records as admission errors before any tier or topology mutation.

**Acceptance:** every field has units, source, and unknown state; invalid fixtures fail before side effects; no logical-lattice value is presented as a physical core count.

### Phase 2 — Fleet execution and recovery (architecture implemented; physical expansion open)

**Retain:** generic kernel tiling, disjoint ranges produced by each kernel, capability-weighted leases, exact output verification, recovery, and per-device receipts.

**Next elevation:**

1. Run two to four **physical machines** with heterogeneous supported routes, recording machine/device/driver identities and exact source commit.
2. Demonstrate disjoint work and exact merged output for every participating route; retain all failures and recoveries.
3. Measure end-to-end throughput, transport, contention, and failure recovery separately. Report distributions from repeated runs, not synthetic p95 values.
4. For internal mining workloads, use the mining workload's nonce partition and SHA256d verification contracts; fleet scheduling never changes proof-of-work validity.

**Acceptance:** no silent fallback, no duplicate accepted tile ownership, exact output, per-device evidence, and measured—not assumed—scaling. Four adapters are not a 4x capacity claim.

### Phase 3 — Heterogeneous work placement (objective retained; mechanism gated)

The proposed roles remain a useful vocabulary for analysis: `data_ingest`, `tensor_compute`, `verification`, `photonic`, `ai_training`, and `general`. They are **not implemented hardware properties** and must not be inferred from institution names or product labels.

Current authority is stronger: a node must offer the exact kernel/version on a self-tested route, and the kernel must accept that route and tile. Measured throughput may weight eligible work; it cannot make an ineligible route eligible.

**Replacement path when a concrete workload requires more:**

1. Write the placement requirement that exact kernel eligibility cannot express—for example, data residency or an operator-approved verification-only node.
2. Add an explicit, bounded `placement_policy` to `WorkUnit` and an operator-declared policy record to node join. Do not overload authentication roles or trust classes.
3. Include requested policy, matched policy, and refusal reason in leases and receipts. Coordinator validation occurs before admission; workers recheck before execution.
4. Fail closed when no eligible node matches. Optional fallback must be explicitly requested and recorded, never hidden by `general`.
5. Test every allowed and denied combination, including stale policies, waiting/quarantined nodes, recovery, and replayed work-unit digests.

**Acceptance:** 100% of contract-test placements satisfy the policy; no unsupported role routes work; role labels never constitute hardware-rooted attestation.

### Phase 4 — Memory tiers (research model retained; local reporting elevated)

| Tier | Original projection | Current replacement and state | Promotion requirement |
|---|---|---|---|
| **Tier 0 — device memory** | 2 TB HBM4 per pad | OpenCL reports `global_memory_bytes` where present; Metal exposes device/unified-memory metadata where supported. No HBM4 capacity is claimed. | Identified device report plus allocation-enforcement tests and finite per-job budget |
| **Tier 1 — host DRAM** | 20 TB shared pool | `HostCapacity.memory_bytes` reports total host memory and source in join/status/receipts. It is not free memory or a shared pool. | Available/limited memory probes, cgroup handling, allocator accounting, pressure and recovery tests |
| **Tier 2 — remote/cloud** | 1 EB / unbounded remote | **Not implemented.** Docker/Azure/GCP rows remain `NOT_RUN`; no remote tier may be used for admission. | Authenticated backend, finite configured quota, latency/failure semantics, durability scope, audit trail |
| **Tier 3 — quantum memory** | Quantum RAM / coherent capacity | **Theoretical only; excluded from capacity arithmetic.** TURING owns finite-dimensional quantum mathematics, not a physical QRAM claim. | Separate scientific and hardware evidence; never a scheduler fallback |

Commercial `Tier.storage_tb` entitlement remains a separate provisioning control. It is not Tier 0/1 physical memory, measured storage, durability, or proof that the capacity exists.

**Acceptance:** every implemented allocation carries finite bytes, tier, source, owner, and success/failure state; unsupported tiers remain unavailable; audit completeness means all required fields are present on every allocation, not a subjective percentage.

### Phase 5 — Vendor and cloud adapters (external execution gates)

Preserve the CUDA, ROCm, oneAPI, Metal, Azure, GCP, and photonic paths, but implement them independently against the active adapter/kernel contract.

Each adapter promotion requires:

1. an identified exact source commit and dependency/toolchain versions;
2. physical device or configured cloud-resource identity and driver/runtime metadata;
3. real kernels with whole/tiled known-answer parity and route-specific refusal tests;
4. end-to-end fleet output equality and per-device signed receipts;
5. explicit behavior for unavailable, denied, degraded, failed, and recovered states;
6. a reproducible benchmark protocol before any throughput or comparative claim; and
7. independent review for security, attestation, conformance, or release claims.

No cloud credentials are to be committed. No adapter may report success from a manifest, emulated response, or CPU fallback.

## 6. Consortium research mapping — retained, corrected, and bounded

The institution names below reproduce the supplied research vocabulary only. **They do not assert a partner, customer, deployment, endorsement, resource commitment, or other relationship.** CERN, MIT, Caltech, Princeton, Stanford, Oxford, Cambridge, and any shared facility are external to this implementation unless separate owner-approved evidence establishes otherwise.

| Projection aspect | Research design envelope | Honest Chronus mapping |
|---|---|---|
| Institutions | Seven named institutions plus shared infrastructure | Adapter/worker ownership labels at most; no institutional affiliation or trust is inferred |
| Pads and topology | Ten pads, full mesh, 45 edges | Logical execution topology only; current H4 crossbar is a distinct graph and is not a ten-pad physical deployment |
| Hilbert dimension | `2^640 = (2^64)^10` | Mathematically valid only for ten `2^64`-dimensional factors. Ten 32-dimensional factors instead give `2^50`. TURING owns tensor mathematics; Chronus schedules supported classical kernels |
| Interconnect | 1.2 PB/s optical, 10 PB/s trigger, RDMA, entanglement | No such throughput or physical link is implemented. Report per-route measured transport only; entanglement is not a network transport metric |
| Memory | 1 EB remote, 20 TB DRAM, 2 TB/pad, QRAM | Design envelopes only; see the four memory tiers in Phase 4. Unbounded and theoretical values are excluded from fleet totals |
| CPU / GPU / neural / photonic cores | Heterogeneous institutional core counts | OS/driver-reported values where implemented; otherwise `UNKNOWN`/`NOT_RUN`. Logical warps and lanes are not physical cores |
| Roles | CERN ingest, MIT fabrication, Caltech/Stanford tensor/photonics, Oxford/Princeton quantum, Cambridge photonics/statistics | Illustrative workload responsibilities only. Exact kernel eligibility is authoritative; placement policy is a future gated contract |
| GHZ / entanglement | Ten-pad cluster state | Not materialized by Chronus. TURING finite-dimensional mathematics does not establish physical entanglement, hardware execution, or advantage |
| Authority | Institution-scoped measurement bases and hardware roots | Current signed receipts and route evidence only; no hardware-rooted attestation or institution-scoped authority is claimed |

### Capacity reporting rule

Every future capacity report must separate:

- `reported_physical`: finite values from an identified OS/driver/device source;
- `logical_scheduling`: lattice units, warps, lanes, and tiles;
- `provisioned_entitlement`: commercial/storage limits from the active tier or grant;
- `calibrated_rate`: a timed qualification run on identified lanes;
- `measured_execution`: work and time from actual execution records;
- `design_envelope`: a finite planning assumption, never added to physical capacity; and
- `theoretical`: excluded from operational totals.

Aggregate only like quantities with compatible units and sources. Any aggregate throughput or bandwidth claim needs an end-to-end measurement and raw evidence.

## 7. Acceptance scorecard and governance

| Roadmap surface | Replaced success criterion | Current disposition |
|---|---|---|
| Evidence integrity | Hardware-present probes cannot create device execution or speedup records; no fabricated percentiles or unexecuted timings | Locally checked; CI/hardware qualification open |
| Host detection | CPU/memory fields have source and unknown state; malformed values fail before admission side effects | Locally checked on Windows fixtures; cross-platform CI open |
| Resource receipts | Join, status, and signed device receipt preserve the same labeled host record | Locally checked |
| Fleet ordering | Newest-first downgrade and oldest-first readmission remain correct under timestamp ties | Locally checked |
| Multi-device execution | Exact output and disjoint work on at least two identified physical routes; all fallbacks explicit | Local multi-worker tests exist; physical heterogeneous gate open |
| Role/placement constraints | If implemented, every allowed/denied contract case is deterministic and receipted | Design gate; not implemented |
| Memory tiers | Every allocation has finite budget, source, tier, and failure evidence | Tier 0/1 partial reporting; allocator and remote tiers open |
| Vendor/cloud routes | Real kernel plus physical/configured-environment conformance evidence | External gates; no promotion |

The Universal Principle Map objectives are preserved as follows: representation truth through typed quantities; evidence separation through the vocabulary above; unchanged workload validity oracles; finite resource accounting; immutable mathematical constants; deterministic work/receipt digests; explicit fallback; and measurement before promotion.

These are engineering controls, not proof of production readiness, performance, security effectiveness, compliance, customer use, or release qualification.

## 8. Local verification record

This record applies to the **working tree containing this roadmap revision**, based on commit `89aa86851eb3b56cd8d4276a3d847d9bc66b64d4`. Because the changes are not a commit, this is not a commit-linked release attestation.

Environment: local Windows Python 3.12 virtual environment. The following complete fleet/elevation selection ran on 2026-11-13:

```powershell
$tests = Get-ChildItem -LiteralPath 'tests' -File -Filter 'test_fleet_*.py' |
  ForEach-Object { $_.FullName }
.venv\Scripts\python.exe -m pytest -q $tests tests/test_chronus_elevation.py
```

Result: **188 passed, 3 skipped in 24.56 seconds**. The count is the complete selection, not a sum of earlier focused runs. A negative unauthenticated TLS transport test logged a rejected-connection traceback while the test passed; it is not a successful secure-channel attestation.

One skip is the POSIX-only owner-mode assertion on Windows. A Windows token-file write/read test replaces platform compatibility coverage, but **Windows ACL restriction was not assessed**. The other two skips are a POSIX-only `fchmod` failure-path test and a POSIX-process-signals test. No skipped result is counted as hardware evidence.

Additional checks:

- focused evidence/resource/coordinator suite: **42 passed** before the full selection;
- tier/order/evidence regression selection after the join-sequence repair: **47 passed** before the full selection;
- `compileall` over `src/chronus/fleet` and `src/chronus/execution/elevation.py`: passed;
- `git diff --check`: passed on the delivered working tree; not inferred from test success.

Not run: independent CI, Apple Metal silicon, OpenCL GPU silicon, CUDA/ROCm/oneAPI kernels, Azure/GCP execution, a physical multi-host fleet, comparative benchmarks, hardware-rooted attestation, security accreditation, or release qualification.

## 9. Controlling references

- [Fleet architecture and evidence rules](fleet/FLEET.md)
- [Fleet design decisions](fleet/DECISIONS.md)
- [Repository claim audit](claim-audit.md)
- [Current release decision: NOT QUALIFIED](../STATUS.md)
- [Quantum package taxonomy and TURING boundary](system-update/quantum-package-taxonomy.md)
- [HYBA packaging boundaries](directives/PACKAGING.md)

If older elevation notes conflict with this revision, the current claim audit, release decision, taxonomy, and this source-backed roadmap control. Historical projections remain research inputs, not current capabilities.
