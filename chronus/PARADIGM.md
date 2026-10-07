# Chronus iGPU Paradigm

**Home of the HYBA software-defined quantum-from-maths GPU and accelerated execution plane.**  
Old M3 paths were the test bed. This tree is where the Chronus runtime stack lives.

License posture for claims: MIT · Python 3.10+ · Veritas Integritas · **Rule 7: Strict Honest Measurement** · 11D substrate active.

---

## Strategic thesis

> Modern enterprise computing pays a **Raw-State Tax** — repeated data movement,
> unnecessary materialisation, memory staging and brute-force re-embedding.
>
> HYBA thesis: **The Folded Form can be the Working Form** where the representation
> contract is exact and the workload can operate on it directly.
>
> Exact/invertible algebraic folding, structured search and evidence-backed execution
> can reduce work or movement without pretending that mathematical structure creates
> physical hardware that does not exist.

Chronus is HYBA's **software-defined GPU and heterogeneous execution plane**. It is
substrate- and hardware-agnostic: a CPU, iGPU, GPU or future accelerator may host a
Chronus run without becoming the Chronus product identity. Turing is the independent
HYBA Virtual Quantum Computer (VQC). Turing may use Chronus for authorised substrate
execution, but neither system owns or replaces the other.
Lucas/Pisot provides mathematical structure and scale contracts where actually implemented;
intelligence is a consumer of those contracts, not their owner.

---

## The paradigm in one card

| # | Law |
|---|-----|
| 1 | Quantum / compute from **mathematics** may be substrate-agnostic, but the actual execution substrate must always be reported. |
| 2 | Intelligence and compute are separate authorities: EUCLID decides; Chronus executes; Turing is the VQC. |
| 3 | **Lucas/Pisot can structure scale** — memory budgets, batches, search windows, workers and other domains only where the implemented contract uses them. |
| 4 | Folded working representations must prove exactness/reconstruction and include all metadata in claimed density gains. |
| 5 | Speed claims come from measured reductions in work, movement, latency or convergence — never from the Lucas/Pisot name alone. |
| 6 | **Native Chronus GPU**: Chronus is the GPU itself; **host-GPU augmentation**: Chronus enters and scales/extends the customer's certified GPU/accelerator stack. |
| 7 | Effective capacity is **maths-bounded** (`L_n` ratio envelope), not SKU fantasy. |
| 8 | **This repository is domicile**; M3 was a historical proof bed. |
| 9 | Evidence gates govern every product/research claim. |
| 10 | One execution contract can target multiple substrates without pretending they are equivalent. |

---

## Two mathematical structures, one governed scale contract

```text
LUCAS  (resource / integer dimension)
  L_n = exact integer
  may size and partition: workers, batches, memory budgets,
  thread slices, search windows and parallel lanes
  → resource schedule follows explicit ladder stops

PISOT / φ  (convergence / sequence dimension)
  φ > 1, |ψ| < 1
  may provide useful discrepancy/convergence/recurrence structure
  → any claimed advantage remains algorithm- and benchmark-specific

TOGETHER
  rung/index contracts may be consumed by Chronus, Turing or other HYBA domains
  when the relevant implementation explicitly uses them
```

Canonical Chronus offering policy: `chronus/seam/scale.py`.

The repository root `claims.yaml` is the release authority. In particular, the existing
refutation of generic **Lucas/Pisot quantum speedup** and prohibition on generic
**exponential speedup** remain binding. A narrower algorithm-specific benefit may still be
established, but it requires its own proof/benchmark/evidence chain.

---

## Folded working form · measured execution

| Axis | Mechanism | Required evidence |
|------|-----------|-------------------|
| Representation | PULVINI / approved fold representation | exactness, metadata-inclusive size, reconstruction cost, downstream effect |
| Search | Geodesic / other structured search where applicable | correctness, preprocessing, query/update cost, scaling curve |
| Execution | Chronus dispatch / device binding | actual substrate, useful work, correctness, latency/throughput |
| Scale | Lucas/Pisot contracts where implemented | explicit algorithmic role plus measured effect |

**Folded form = working form** is valuable only when consumers can operate on that form
without silently re-materialising the raw state or weakening semantics. Benchmark both the
representation and the downstream computation.

---

## Independent fabric **or** scale your stack

| Mode | Meaning |
|------|---------|
| **Native Chronus GPU** | Chronus Virtual iGPU + mathematical engine: ABI, runtime, scheduling, memory, verification and evidence execute without requiring a host GPU. |
| **Host-GPU augmentation** | Chronus enters a customer CUDA / OpenCL / Metal / XPU stack: probe → negotiate → bind → execute → verify → evidence, extending/scaling that host. |

One Chronus product; multiple execution substrates. No silent substitution and no
backend may become the product identity.

---

## Effective capacity (Rule 7)

Physical inventory stays physical. The scale contract may publish a **logical work
envelope**, never a fake device count and never a hashrate.

```text
effective envelope ≈ physical_units × L_n / L_ref
physical_units       = real census (cards, tiles, or negotiated units)
L_n                  = Lucas value at ladder stop n
L_ref                = reference rung (see chronus.seam.scale)
```

API:

```python
from chronus.seam.scale import compute_effective_capacity, effective_capacity

cap = compute_effective_capacity(physical_units=80, ladder_index=15)
effective_capacity(80, ladder_index=15)
```

### M3 witness class (historical test bed)

On the M3 research path, a physical inventory on the order of **80** GPUs was operated
under the scale contract with a logical/effective scheduling envelope in an **~800-class**
band. That is a historical scale-contract witness, not a claim that 80 physical devices
became 800 physical devices and not a throughput number.

Rule 7 fences:

- ladder stop ≠ advertised TH/s or pool hashrate;
- `work_items` / batch size ≠ measured throughput;
- `effective` ≠ physical GPU count;
- hardware presence ≠ hardware execution;
- measured dispatches are measured; projections remain labelled projections;
- unavailable hardware remains unavailable.

See `RULE7_NOTE` and `EffectiveCapacity` in `chronus/seam/scale.py`.

---

## Where the stack lives

```text
EUCLID / TOE / PYTHIA / TURING / enterprise workloads
        │
        │ governed compute request
        ▼
┌────────────────────── CHRONUS ────────────────────────────────┐
│ software-defined GPU · heterogeneous execution · Virtual iGPU │
│ routing · binding · topology · telemetry · provenance         │
│ seam/scale.py → offering-level resource policy                │
└──────────────────────────┬────────────────────────────────────┘
                           │
          ┌────────────────┼─────────────────┐
          ▼                ▼                 ▼
         CPU              iGPU              GPU
                                            │
                                 future FPGA / ASIC / cloud

TURING is a separate VQC that may use Chronus for authorised substrate execution.
OVID owns representation transformation.
THESEUS owns durable custody/continuity/recovery.
PULVINI and Geodesic retain separately attributable representation/search roles.
AL HARAS governs; Salamander heals/optimises within bounded authority.
```

**Chronus owns:** route, device policy, substrate binding, resident execution,
Virtual iGPU, topology-aware scheduling, telemetry, dispatch provenance and attestation.

**Turing owns:** the VQC execution model, quantum/VQC algorithms and VQC results. Turing
may call Chronus for an underlying classical/device execution path; Chronus does not
rename, wrap or absorb Turing.

**External ops boundary:** live pool protocols, worker credentials, reward and accounting
workflows remain outside Chronus unless an approved integration contract explicitly wires
them.

---

## Five cooperating surfaces, clear ownership

| Surface | Role in this paradigm |
|--------|------------------------|
| **PULVINI** | Fold/representation mechanisms where exactness is established |
| **Geodesic/Search** | Structured search/indexing; does not become custody |
| **Chronus** | Heterogeneous execution and acceleration |
| **OVID** | Transformation / metamorphosis of representations |
| **THESEUS** | Durable custody, integrity, continuity and recovery |

AL HARAS provides governance/evidence gates. Salamander provides bounded health and
optimisation. EUCLID remains the intelligence authority. These roles cooperate; they do
not become skins over one hidden owner.

---

## Benchmark posture

Chronus does not need an artificial single competitor.

For each capability, benchmark against the strongest semantically comparable reference:

- direct CPU/device execution without Chronus;
- CUDA / ROCm / oneAPI / OpenCL / Metal-class native runtimes;
- production raster/ray/path-tracing reference engines for rendering;
- NumPy/BLAS and device tensor libraries for tensor workloads;
- raw state plus exact compressors such as zstd/gzip for representation claims;
- brute-force/tree/index/ANN controls for search when semantics match;
- frozen SHA256d reference execution for mining kernels;
- conventional virtual-GPU/device-sharing approaches for Virtual iGPU overhead/isolation.

The canonical comparator framework and evidence rules live in `chronus/README.md`.

---

## Doctrine

```text
RAW-STATE TAX          → reduce only when evidence shows less work/movement
LUCAS / PISOT          → mathematical structure, not generic speedup
CHRONUS                → heterogeneous execution / Virtual iGPU home
TURING                  → independent VQC; may use Chronus execution
OVID                    → transformation
THESEUS                 → durable custody
PULVINI                 → fold/representation
GEODESIC                → search/index structure
NATIVE CHRONUS GPU      → Chronus is the GPU; no host GPU prerequisite
HOST-GPU AUGMENTATION   → same Chronus contract scales/extends customer hardware
EFFECTIVE CAPACITY      → L_n envelope, Rule 7 safe
MEASURED EVIDENCE       → required before promotion
```

When in doubt: read `chronus/README.md`, `chronus/seam/scale.py` and the root
`claims.yaml`. Prefer a smaller proved statement over a larger unevidenced one — then
build the evidence required to make the larger statement true.
