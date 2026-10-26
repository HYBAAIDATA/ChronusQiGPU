# Chronus — HYBA Software-Defined GPU & Heterogeneous Execution Runtime

Chronus is HYBA's **software-defined quantum-from-maths GPU** and heterogeneous
execution computer. Its product identity is substrate- and hardware-agnostic:
CPU, iGPU, discrete GPU, cloud accelerator, FPGA/ASIC and future quantum hardware
are places the Chronus computation may execute; none is a prerequisite for
Chronus to exist.

Chronus is not a claim that software has fabricated physical silicon, and it is
not a physical QPU. "GPU" here names the Chronus compute product and execution
contract. Physical-device claims remain separate evidence about a particular run.

> **Product thesis:** Chronus can either operate as the GPU itself or enter an
> existing GPU/accelerator stack and scale/extend it. The same governed workload
> semantics, verification, provenance and custody survive both modes.

> **Start here:** §19 shows what Chronus has actually been measured doing on real data;
> §20 is the one-page map of where every Chronus-related piece lives.

## 0. Owner-approved two-mode product contract

Chronus has **two product modes**, separate from the backend that happens to
execute a run:

1. **Native Chronus GPU** (`native_chronus_gpu`; compatibility execution policy
   `standalone_software`) — **Chronus is the GPU.** The Virtual iGPU/runtime,
   mathematical engine, memory, scheduling, verification and evidence surfaces
   execute without requiring a host GPU. A CPU/reference adapter may host this
   mode today, but it is an implementation substrate, not the product identity
   and not a degraded fallback.
2. **Host-GPU augmentation** (`host_gpu_augmentation`; compatibility execution
   policy `preferred_accelerator`) — Chronus binds into an available,
   independently certified iGPU/GPU/accelerator and extends or scales that host
   while preserving the same Chronus workload contract.

This is the original **independent fabric OR scale your stack** architecture.
A missing GPU can gate the second mode; it can never make the first mode
unavailable. Likewise, device performance, power, thermal, hardware-rooted
attestation and physical execution claims remain per-device evidence gates.

The historical names are now one product lineage, not competing architectures:

- **Chronos GPU v2/v3.3** supplies the quantum-from-maths mathematical/graphics engine;
- **Chronus Virtual iGPU** supplies the software-defined GPU ABI/runtime/memory/evidence;
- **Chronus portable substrate** supplies device-neutral routing, delivery and control;
- **Chronus** is the canonical converged product containing those capabilities.

---

## 1. Canonical identity and ownership

The names matter because Chronus sits inside a larger computational organism.

| System | Canonical responsibility | Relationship to Chronus |
|---|---|---|
| **EUCLID** | Enterprise intelligence, planning, strategy and capability composition | May select Chronus when heterogeneous execution is appropriate |
| **TOE** | World, causal, counterfactual and futures modelling | Produces/consumes computational work; does not own device execution |
| **PYTHIA** | Predictive, causal and mining-domain specialist | May submit mining or analytical workloads to Chronus |
| **Turing** | HYBA Virtual Quantum Computer (VQC) | **Independent computer.** Turing may use Chronus for authorised classical kernels/substrate execution; Chronus does not own or absorb Turing |
| **Chronus** | Software-defined GPU, heterogeneous execution, native Virtual iGPU, host-accelerator augmentation, dispatch evidence | Owns this package/runtime boundary |
| **OVID** | Representation transformation / metamorphosis | May transform work/state before or after execution; **not durable custody** |
| **THESEUS** | Durable custody, integrity, replication, continuity and recovery of important state | Preserves state/results; **not the transformation owner** |
| **PULVINI** | Fold/representation mechanisms as established by the implementation | Can reduce/reshape the working representation used around execution; not silently owned by Chronus |
| **Geodesic/Search** | Search, indexing and search-space structure | Can change what work must be searched/executed; remains separately attributable |
| **Salamander** | Bounded health, healing, optimisation, promotion/rollback | Observes and remediates execution/runtime failures under governance |
| **AL HARAS** | Security, policy, governance, attestation and evidence gates | Governs Chronus actions and promotion of evidence |

### Direction of the Turing ↔ Chronus boundary

```text
Turing VQC workload / HYBA workload / PYTHIA workload / enterprise workload
                               |
                               v
                    governed execution request
                               |
                               v
                         CHRONUS
                route · bind · dispatch · verify
                               |
          +--------------------+--------------------+
          |                    |                    |
         CPU                  iGPU                 GPU
                                                   |
                               future FPGA / ASIC / cloud accelerator
```

Turing is **not** Chronus's generic compute substrate. Turing is the VQC. Chronus is the
heterogeneous execution architecture. A Turing implementation may call Chronus when a
VQC workload needs an authorised classical/device execution path; other systems may call
Chronus without involving Turing at all.

---

## 2. Chronus vs Chronos v3.3

The repository intentionally preserves two related names:

- `chronus/` — the canonical converged Chronus product/runtime.
- `chronus/v33/` — the historical **Chronos GPU mathematical engine v3.3**,
  now an integrated mathematical capability of Chronus rather than a separate product.
- top-level `chronos` — deprecated compatibility facade for historical imports.

There is **one Chronus product**. The v3.3 mathematical engine, Virtual iGPU runtime,
portable substrate/control plane and physical accelerator adapters are capability
lineages inside it. They do not create separate Chronus identities and do not redefine
the ownership of Turing, EUCLID, OVID, THESEUS, PULVINI or Geodesic.

---

## 3. What Chronus owns

Chronus owns the execution boundary required to answer four questions:

1. **What work was requested?**
2. **Which authorised substrate executed it?**
3. **Did execution preserve the workload's semantic/correctness contract?**
4. **What evidence proves the answer?**

Current or canonical responsibilities include:

- device census and capability discovery;
- explicit device/backend selection;
- substrate binding;
- resident execution and scheduling;
- Virtual iGPU contracts and adapters;
- mathematical-state/device-memory surfaces where implemented;
- tensor and native-kernel execution paths;
- topology-aware scheduling surfaces;
- Lucas/Pisot offering-level scale contracts;
- measured telemetry;
- dispatch provenance;
- attestation/evidence hooks;
- embedded and cloud-instance delivery modes;
- fail-closed handling when a requested hardware backend cannot bind.

Chronus **does not** own enterprise intelligence, durable state custody, general
representation transformation or the VQC identity.

---

## 4. Architecture

```text
                         HYBA COMPUTATIONAL ORGANISM

                 EUCLID / TOE / PYTHIA / TURING / APIs
                                |
                         capability request
                                |
                                v
                     AL HARAS governance gate
                                |
                                v
+-----------------------------------------------------------------------+
|                              CHRONUS                                  |
|                                                                       |
|  capability discovery  ->  device census  ->  execution planning     |
|           |                                      |                    |
|           +----------> scale / topology <---------+                    |
|                              |                                        |
|                              v                                        |
|                  backend / substrate binding                          |
|                              |                                        |
|       +-----------+----------+----------+-----------+                  |
|       |           |                     |           |                  |
|      CPU        OpenCL                CUDA        Metal               |
|                 iGPU/GPU               GPU         GPU                |
|       |           |                     |           |                  |
|       +-----------+----------+----------+-----------+                  |
|                              |                                        |
|                        real execution                                 |
|                              |                                        |
|                 verification / provenance                             |
+------------------------------+----------------------------------------+
                               |
             +-----------------+------------------+
             |                                    |
       THESEUS custody                    SALAMANDER health
             |                                    |
             +--------------------+---------------+
                                  |
                           evidence / learning
```

OVID, PULVINI and Geodesic may participate before, during or after execution when the
workload requires transformation, folded representation or structured search. Their
results remain independently attributable; integration is not ownership transfer.

---

## 5. Delivery and consumption

`chronus/delivery.py` defines two explicit delivery modes.

### Embedded

Chronus executes inside the customer's/container environment. The standalone
software runtime is a valid embedded product mode when its software gates are
met; locally available accelerators are additive execution lanes, not
prerequisites.

```text
application
   |
Chronus (in process)
   |
local CPU / iGPU / GPU
```

### Cloud instance

A Chronus runtime is deployed into the customer's chosen cloud and reached through the
verified remote protocol.

```text
customer application
       |
remote_opencl_v2
       |
Chronus instance in customer cloud
       |
authorised accelerator devices
```

The modes do **not** silently fall back into one another. A requested backend that cannot
bind must remain unavailable rather than being represented as successful execution on a
different substrate.

### Distribution direction

The packaging programme is intentionally moving toward independently provable artifacts
rather than one opaque package. Target boundaries include:

- `chronus-core` — runtime/contracts and substrate-independent core;
- `chronus-igpu` — iGPU/device-specific execution surfaces;
- `chronus-tensor` — tensor execution capabilities;
- Chronos v3.3 maths packaged as part of the appropriate Chronus distribution boundary;
- `turing-universal-quantum-computer` — **separate VQC package**, not a Chronus rename.

A target package name is not evidence that the package has already been published. The
release/package manifest is authoritative for what exists in a given release.

---

## 6. Execution backends

Chronus treats backend names as factual execution substrates, not product identities.

Current code contains/probes execution surfaces including:

- CPU/reference execution;
- OpenCL;
- CUDA/CuPy where implemented and bindable;
- Metal/MLX where implemented and bindable;
- Virtual iGPU/fabric surfaces;
- remote accelerator execution through the explicit cloud delivery contract.

Future or environment-dependent paths such as ROCm, oneAPI, FPGA, ASIC or additional
cloud accelerators remain **gated until the implementation and hardware evidence exist**.

A discovered GPU does not prove a GPU workload ran. A requested backend must bind,
execute, verify and emit evidence before the corresponding execution claim is promoted.

---

## 7. Scale law: Lucas / Pisot

Offering-level scale policy lives in `chronus/seam/scale.py`.

- **Lucas** values provide integer resource/batch/envelope stops.
- **Pisot / φ** structures are used only where the corresponding algorithm/contract
  actually uses them.
- Effective capacity is a logical work envelope, not a fabricated device count.

```text
effective envelope ~= physical_units × L_n / L_ref
```

Rule 7 is non-negotiable:

- ladder stop != measured throughput;
- `work_items` != hashrate;
- logical effective capacity != physical GPU count;
- Lucas/Pisot mathematical structure != generic or quantum speedup;
- projected performance != measured performance.

The repository's root `claims.yaml` is authoritative for claim promotion. In particular,
a generic **"Lucas/Pisot quantum speedup"** and a generic **"exponential speedup"** are
not valid Chronus claims unless a new, specifically scoped claim is separately established
through the claims/release process.

Lucas/Pisot may still produce real benefits in individual algorithms — for example
partitioning, recurrence evaluation, discrepancy, addressing, convergence or data
movement — but each benefit must be measured and attributed to the actual mechanism.

---

## 8. Chronos v3.3 mathematical / graphics capabilities

The `chronus/v33/` engine provides the mathematical/graphics research surface contained
inside Chronus. The executable capability manifest is the authoritative inventory.
Capability families include, subject to their individual evidence status:

- QSDL parsing/compilation;
- manifold construction and topology;
- Hamiltonian construction/evolution/solves;
- rendering/reconstruction;
- real deterministic supersampling;
- memory and mathematical-state surfaces;
- compression/representation adapters;
- tensor-network and MPS/TT/MPO-related surfaces;
- academic/theory domains;
- capability audit and executable completeness checks;
- benchmark/test harnesses.

Do not promote a capability from "present in the manifest" to "hardware-measured" merely
because it imports or passes a software test.

---

## 9. Rendering baseline currently in the repository

The current main-branch render elevation artifact records, on its identified Linux host:

| Workload | Measured result | Evidence state |
|---|---:|---|
| 8K, 1 sample/pixel | **2.6835 s** | Host-measured CPU/reference path |
| 8K, 4 samples/pixel | **11.1646 s** | Host-measured CPU/reference path |
| 8K demo hit contract | **1,832,112 / 33,177,600** | Deterministic geometry regression contract |
| CuPy GPU lane | **Unavailable on that host** | No GPU wall time is inferred |

Raw artifact: `chronus/v33/benchmarks/render_elevation_results.json`.

The 1-spp render elevation preserved the validated scene contract while reducing host wall
time relative to the earlier reference implementation. The 4-spp path performs real
deterministic sub-pixel sampling rather than reporting supersampling metadata without
executing it.

These are **baselines**, not the final Chronus performance envelope. Device-bound GPU/iGPU
measurements, power, thermal behaviour and the wider claim-validation programme remain
separate evidence gates.

---

## 10. Benchmark philosophy — no artificial "peer"

We do **not** currently nominate a single direct competitor for Chronus.

Chronus deliberately crosses categories that conventional products usually separate:

- heterogeneous runtime;
- device/accelerator abstraction;
- Virtual iGPU/fabric;
- mathematical compute engine;
- topology/scale policy;
- representation-aware execution;
- evidence/provenance contract.

That makes a single "Chronus vs Product X" benchmark scientifically weak. Instead, every
Chronus capability is compared with the **strongest appropriate adjacent reference class**.
The purpose is not to find an easy opponent. The purpose is to establish the cost and
benefit of the Chronus layer relative to the best conventional way to perform the same
work.

### Benchmark comparator matrix

| Chronus capability | Primary reference/control | Adjacent market/reference class | What must be compared |
|---|---|---|---|
| Heterogeneous dispatch | Same kernel executed directly without Chronus | CUDA, ROCm/HIP, oneAPI/SYCL, OpenCL, Metal-class native runtimes | latency, launch overhead, throughput, semantics, provenance overhead |
| Intel/other iGPU execution | CPU reference + same iGPU through the most native available path | Intel OpenCL/oneAPI-class stack; vendor-native iGPU execution | useful work/s, bytes moved, memory, power, correctness |
| NVIDIA GPU execution | CPU/reference + direct native kernel | CUDA/CuPy/OptiX-class execution depending on workload | end-to-end work, not theoretical device peak |
| AMD GPU execution | CPU/reference + direct native kernel | ROCm/HIP-class execution | same workload, same precision, same quality |
| Apple GPU execution | CPU/reference + direct native path | Metal/MLX-class execution | same workload, same precision, same quality |
| Rendering | Frozen Chronus reference renderer + converged ground truth | production raster/ray/path-tracing reference engines (e.g. Embree/Cycles/OptiX-class where semantically comparable) | frame time **and** radiance/image/temporal error |
| Tensor compute | NumPy/BLAS reference and direct device library | BLAS/CuPy/PyTorch/JAX/vendor tensor libraries as applicable | correctness, latency, throughput, memory, transfer cost |
| PULVINI/folded state | raw representation | exact/lossless compressors such as zstd/gzip plus domain-native representation | all metadata bytes, reconstruction, latency, working-set reduction |
| Geodesic/search | brute-force exact search | bisect/tree/index methods and ANN/HNSW/FAISS-class methods only when semantics match | accuracy, query cost, preprocessing, update cost, memory, scaling |
| Mining kernels | frozen sequential/reference SHA256d | direct CPU/GPU hashing kernel on identical work | bit-exactness, hashes/s, joules/hash, setup/transfer cost |
| Virtual iGPU/fabric | direct device access | conventional virtual-GPU/device-sharing approaches | isolation, provisioning, overhead, utilisation, evidence/attestation |
| Turing workload acceleration | Turing reference representation/backend | direct CPU/GPU implementation of the same underlying kernel | Turing owns the VQC result; Chronus is judged only on substrate execution |

Names in the adjacent column are **reference classes, not assertions of product equivalence
or direct competition**.

### Market comparison rule

Use three labels in external competitive work:

1. **Direct peer** — only if another product has materially equivalent architectural scope.
2. **Adjacent platform** — solves part of the same problem (CUDA, ROCm, oneAPI, Metal,
   virtual-GPU platforms, render engines, etc.).
3. **Benchmark control** — the implementation used to measure whether Chronus adds value.

Until a genuine direct peer is identified, the honest position is:

> **Chronus has no nominated one-to-one benchmark peer; it is benchmarked capability by
> capability against the strongest conventional reference for the same work.**

This is harder than choosing a weak competitor and is therefore the preferred scientific
and commercial standard.

---

## 11. What we measure

Every serious benchmark should capture the dimensions relevant to that workload.
Performance without correctness/quality is incomplete.

### Compute

- cold/warm latency;
- p50 / p95 / p99 where meaningful;
- sustained throughput;
- work-item count;
- CPU/GPU utilisation where measurable;
- compilation and kernel-launch overhead;
- host/device transfer bytes;
- peak working memory;
- energy/work where physical telemetry exists.

### Rendering

- frame time / FPS;
- samples per pixel;
- radiance error against converged reference;
- PSNR / SSIM / MS-SSIM where useful;
- perceptual metrics such as LPIPS only as supplemental evidence;
- geometry/depth/normal correctness;
- temporal stability, flicker and ghosting;
- memory/data movement;
- energy/frame where measured.

### Search

- correctness / precision / recall according to semantics;
- work/comparison count;
- query latency;
- preprocessing/index-build cost;
- update cost;
- memory;
- scaling curve across problem sizes.

### Representation / PULVINI

- source bytes;
- folded/compressed bytes;
- **all required metadata bytes**;
- exactness/reconstruction error;
- fold/reconstruction latency;
- working-set change;
- bytes moved;
- downstream compute effect.

### Mining

- bit-exact SHA256d verification;
- hashes/s on matched work;
- valid/invalid candidate semantics;
- accepted/rejected/stale pool responses only when a real pool provides them;
- scheduler and transfer overhead;
- joules/hash where measured.

---

## 12. Evidence states

Chronus keeps evidence states separate.

| State | Meaning |
|---|---|
| **MEASURED** | A valid artifact contains the relevant measurement |
| **GATED** | The claim has a defined promotion gate that has not yet been satisfied |
| **UNMEASURED** | The capability/claim exists but no applicable measurement currently exists |
| **UNAVAILABLE** | Required hardware/instrumentation/backend was not available on the measuring host |
| **MISSING** | A required implementation/test/artifact does not yet exist |
| **REFUTED** | Evidence contradicts the claim under its stated scope |
| **PROHIBITED** | The project claim register forbids external promotion of the claim |

`Unavailable`, `Unmeasured` and `Missing` are not interchangeable.

The canonical root claim register is `claims.yaml`; capability-specific evidence may add
more granular ledgers but must not silently weaken the root contract.

---

## 13. Benchmark integrity rules

A Chronus performance result is not accepted if the comparison hides any of the following:

- warm-cache asymmetry;
- unequal quantities of useful work;
- precision/dtype changes;
- silent approximation;
- dropped metadata or reconstruction cost;
- favourable-only scene/input selection;
- different early termination conditions;
- setup cost on only one side;
- asynchronous GPU timing errors;
- fastest-run cherry-picking;
- benchmark code whose semantics differ materially from production code.

Every benchmark should capture repository commit, environment, dependency versions,
hardware/device identity, workload/configuration and raw samples sufficient for another
engineer to reproduce the result.

---

## 14. Current claims and active validation

Historical Chronos positioning contains ambitious claims concerning areas such as:

- 8–16 ms 8K frame time;
- global illumination quality;
- continuous/resolution-independent representation;
- mathematical supersampling;
- PULVINI fold ratios;
- Geodesic search scaling;
- first-principles/Hamiltonian simulation;
- bandwidth/memory reduction.

These are not deleted because they are ambitious. They are converted into testable claim
contracts. A claim is promoted when the mathematics, implementation, matched baseline,
quality/correctness measurement and required physical-device evidence support it.

The validation programme deliberately preserves negative results. Knowing where a
representation, algorithm or backend loses is necessary for evidence-backed runtime
selection.

---

## 15. The commercial position

Chronus should not be reduced to a physical-GPU backend. It is the software-defined GPU product; physical GPUs are optional host substrates or augmentation targets.

The stronger position is:

> **Chronus is HYBA's software-defined heterogeneous compute architecture: an execution
> fabric that can inhabit existing silicon today, prove the substrate that performed the
> work, and provide the evidence needed to decide which mathematical representation,
> algorithm and backend should be used next.**

The initial iGPU programme is therefore both a product surface and a proof of the wider
architecture. If the evidence later justifies dedicated FPGA/ASIC/HYBA-native silicon,
Chronus becomes the software/runtime continuity layer from current hardware into that
future hardware.

---

## 16. Quick use

### Inspect delivery

```python
from chronus.delivery import DeliveryMode, probe_delivery

embedded = probe_delivery(DeliveryMode.EMBEDDED)
print(embedded.as_dict())
```

### Use the Chronos v3.3 mathematical engine

```python
from chronus.v33 import ChronosEngine, M32Manifold
```

### Run the v3.3 benchmark suite

```bash
python -m chronus.v33.benchmarks.run_benchmarks
```

### Run tests

```bash
pytest tests/test_chronus_v33 tests/test_chronos_facade.py -q
```

Consult the current test/package manifests for the complete release gate; the command
above is the v3.3 mathematical-engine slice, not the entire enterprise test suite.

---

## 17. Source-of-truth map

| Topic | Source |
|---|---|
| Chronus product/runtime | `chronus/` |
| Delivery modes | `chronus/delivery.py` |
| Scale/effective-capacity policy | `chronus/seam/scale.py` |
| GPU capability/truth boundaries | `chronus/GPU_CAPABILITY_MANIFEST.json` |
| Virtual iGPU | `chronus/virtual_igpu/` |
| Chronos mathematical engine | `chronus/v33/` |
| v3.3 executable capability inventory | `chronus/v33/CAPABILITY_MANIFEST.json` |
| v3.3 benchmark methodology/results | `chronus/v33/benchmarks/`, `chronus/v33/docs/BENCHMARKS.md` |
| Repository claim authority | `claims.yaml` |
| Full-system architecture | enterprise/whole-system architecture documentation as maintained by the repository |

---

## 18. Non-negotiable truth contract

Chronus reports what ran.

- Hardware presence is not hardware execution.
- Dispatch is not acceleration.
- Acceleration is not semantic correctness.
- Quantum terminology is not physical-QPU execution.
- Lucas/Pisot structure is not generic speedup.
- Representation ratio is not automatically physical memory reduction.
- A render that is faster but materially worse is not an unqualified win.
- A projection is not a measurement.
- A missing instrument produces `UNAVAILABLE`, not a guessed number.

The ambition of Chronus is intentionally high. The evidence standard is equally high.

---

## 19. Measured capabilities (software execution, real data)

Produced by `python scripts/chronus_capability_probe.py` at commit `3b456aa`; the raw artifact
is `evidence/chronus/capability_probe_3b456aa.json`. Everything below ran on one host:
Intel Xeon @ 2.10 GHz, 4 logical CPUs, 15.7 GB RAM, Python 3.13, **no GPU runtime present**
(`pyopencl`, `cupy`, `mlx`, `torch` all absent). Only the software (CPU) adapter exists here, so
nothing in this section is a hardware claim. Rates are single-process wall-clock over the **full
submit path** (admission, execution, independent control-plane recompute, receipt, evidence
ledger), not kernel peaks.

**Real data.** Three Bitcoin block headers (heights 0, 1 and 125,552), accepted only because
SHA-256d of each reproduces its published block hash, plus this repository's own files.
Dense numeric kernels use seeded *synthetic* matrices (no real dataset is shipped); they are
labelled as such.

| Capability | Result on this host |
|---|---|
| Reproduce real blocks through the Virtual iGPU | All 3 real nonces recovered from a 3,000-nonce window; digests equal the published block hashes; control-plane recompute `match` (~4 ms each) |
| PYTHIA production route (`chronus_batch`) on the same blocks | Real nonce found in a 1,200-nonce Hendrix-ordered window for all 3 (1,192 / 1,132 / 67 hashes before the hit, 15–43 ms); every candidate host-verified; recorded `SOFTWARE_VERIFIED`, never hardware |
| SHA-256d throughput, verified | ~0.43–0.45 M hashes/s end-to-end (100k–1M nonces/workload) vs ~1.15 M/s for a bare single-core `hashlib` loop; the gap is the independent recompute and receipts |
| Exact integer transforms | Lucas L(10000) 3.3 ms, Pisot n=10,000 4.7 ms, φⁿ n=1,474 0.7 ms; all verified `match` |
| Fold / unfold on real bytes | 24,594 B (this README + 3 headers) -> 110,474 B folded (**4.49x larger**); round-trip exact. The aethel fold is a representation transform here, **not compression** |
| Tensor `matmul`, float64, synthetic | 64² 39 ms, 256² 261 ms, 512² 1.04 s end-to-end, all verified against the `tensor` layer; max error vs NumPy 0.0. End-to-end 0.01–0.26 GFLOP/s: JSON serialisation and verification dominate, so this is **not** a compute peak |
| Complex GEMV, 128, synthetic | 24 ms, verified |
| Control plane | Cheapest workload median 0.59 ms, p95 0.90 ms; receipt identity binding ok; evidence ledger reloads (216 records) with hash-chain intact |
| THESEUS custody (required) | Commit + verify median 11.4 ms (HMAC file custody); fresh-process recovery covered by `tests/test_chronus_theseus_restart_contract.py` |
| Built-in `chronus.measurement` harness | Memory/compute/cache/interconnect topology, roofline, hashrate, tensor, MPS/TT/MPO, stress, throttle, regression and replay stages run; **power, thermal, energy and perf-per-watt are `UNAVAILABLE`** (no sensors) |

**Scale math (independently verified, 119 tests in `tests/test_chronus_scale_math_independent.py`).**
Lucas numbers match an independent recurrence to n=10,000 and the Fibonacci/Cassini identities;
the ladder literals (L10=123 ... L76=7,639,424,778,862,807) are exact; delta15 = phi^-15 = 7.3314e-4;
`effective = physical * L_n // L_10` matches a from-scratch implementation and is monotone. Three
behaviours are pinned because they are easy to misread:

1. Below rung 10 a non-zero fleet can round to **0** effective capacity (1 unit at rung 9 -> 0).
2. `memory_budget_bytes` never goes below the base allocation, even for rungs under L10.
3. The Pisot drift step is exact (<2e-12 vs a 120-digit reference) but decays to ~0 for m >~ 60, so
   `pisot_wind` is a one-step observational rotation for small m, not an ergodic orbit.

**Not measured, not claimed:** any GPU/accelerator execution or performance; multi-core or fleet
scaling; hardware-rooted attestation; pool acknowledgement or accepted shares; the governed
1e19 H/s hashrate ceiling (an engineering ceiling in `runtime_config`; this host sustains ~4.5e5 H/s
through the verified path).

---

## 20. One Chronus: where everything lives

| Piece | Home | Role |
|---|---|---|
| Product, device, fabric, scale law | `chronus/` | Canonical Chronus |
| **Execution plane** | `chronus/virtual_igpu/` | The single execution seam (`virtual_igpu_v1`): workloads, adapters, admission policy hook, receipts, evidence ledger, THESEUS custody hook, control-plane verifier |
| Mining execution | `chronus/mla1517/`, `chronus/mla1517_platform/` | PYTHIA's route into Chronus (`chronus` backend lane, `chronus_batch` route); control API |
| Measurement | `chronus/measurement/`, `scripts/chronus_capability_probe.py` | Attested measurements; the probe behind §19 |
| Chronos v3.3 maths engine | `chronus/v33/` | Retained inside Chronus |
| `chronos` (top-level) | `chronos/` | **Deprecated import facade -> `chronus.v33`**, zero logic; kept for the documented compatibility policy, its tests and `packaging/chronos-core` |
| Tensor semantics | `tensor/` | **Independent logical layer** (contracts, router, verification, receipts). Chronus is an execution backend under it; `tensor` never imports `chronus`; the Virtual iGPU delegates tensor-result verification to `tensor.verification` |
| Exact maths / VQC | `kellogg/`, `turing_universal_quantum_computer/` | Bridged lazily by `tensor`; Turing stays the independent VQC |
| Hybrid hasher / scheduler / vendors | `hyba/` | Still outside `chronus/` (used by the H4/600 route); moving it is a staged follow-up, not done |
| Execution backends | `gpu/` | `gpu.tensor` is a deprecated shim over `tensor` |

## 21. Exact GPIU integration

The Virtual iGPU ABI exposes `quantum_program`, `exact_graph`, `grid_geometry`
and `modular_geometry`. TURING retains quantum semantics; Kellogg retains exact
tensor mathematics. See [GPIU execution and all twenty closure gates](../docs/CHRONUS_GPIU_EXECUTION.md)
for inputs, budgets, verification, and outstanding implementation.
