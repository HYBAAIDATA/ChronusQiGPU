# Chronus — HYBA Heterogeneous Compute & Virtual iGPU Runtime

Chronus is HYBA's **hardware-facing heterogeneous execution and acceleration plane**.
It turns governed computational work into measured execution on available silicon while
preserving the semantic contract of the workload and recording what actually ran.

Chronus is not a claim that a new physical GPU already exists, and it is not a physical
QPU. It is the runtime, device, virtual-iGPU, scheduling, provenance and acceleration
architecture through which HYBA workloads can use CPU, integrated GPU, discrete GPU and
future accelerator substrates.

> **Product thesis:** use the hardware that exists, change how work is represented and
> scheduled, prove what executed, and promote only those mathematical or hardware
> advantages that survive reproducible measurement.

---

## 1. Canonical identity and ownership

The names matter because Chronus sits inside a larger computational organism.

| System | Canonical responsibility | Relationship to Chronus |
|---|---|---|
| **EUCLID** | Enterprise intelligence, planning, strategy and capability composition | May select Chronus when heterogeneous execution is appropriate |
| **TOE** | World, causal, counterfactual and futures modelling | Produces/consumes computational work; does not own device execution |
| **PYTHIA** | Predictive, causal and mining-domain specialist | May submit mining or analytical workloads to Chronus |
| **Turing** | HYBA Virtual Quantum Computer (VQC) | **Independent computer.** Turing may use Chronus for authorised classical kernels/substrate execution; Chronus does not own or absorb Turing |
| **Chronus** | Heterogeneous execution, acceleration, device policy, Virtual iGPU, dispatch evidence | Owns this package/runtime boundary |
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

- `chronus/` — the canonical HYBA hardware-facing product/runtime plane.
- `chronus/v33/` — the **Chronos GPU mathematical engine v3.3** retained inside the
  Chronus product tree.
- top-level `chronos` — deprecated compatibility facade for historical imports.

The v3.3 mathematical engine currently exposes a substantial audited software surface
(see `chronus/v33/CAPABILITY_MANIFEST.json` and `docs/CHRONUS_V33_FULL_CONVERGENCE.md`).
It is one computational capability inside the wider Chronus execution product; it does
not redefine the ownership of Turing, EUCLID, OVID, THESEUS, PULVINI or Geodesic.

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

Chronus executes inside the customer's/container environment and binds directly to
locally available accelerator surfaces.

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

Chronus should not initially be described as merely "another GPU".

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
