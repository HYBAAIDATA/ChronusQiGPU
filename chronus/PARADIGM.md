# Chronus iGPU Paradigm

**Home of the HYBA accelerated plane.**  
Old M3 paths were the test bed. This tree is where the stack lives.

License posture for claims: MIT · Python 3.10+ · Veritas Integritas · **Rule 7: Strict Honest Measurement** · 11D substrate active.

---

## Strategic thesis

> Modern enterprise computing pays the **Raw-State Tax** — repeated data movement,
> uncompressed memory staging, and brute-force re-embedding.
>
> HYBA cut: **The Folded Form is the Working Form.**
>
> Exact, invertible algebraic folding → lossless tier-0 density, multi-lens search
> over folded state, and sovereign attestation — without destructive truncation.

Chronus is the hardware-facing half of that cut. Turing remains compute.
Lucas/Pisot remains the universal scale law. Intelligence is one consumer of that
law, not its owner.

---

## The paradigm in one card

| # | Law |
|---|-----|
| 1 | Quantum / compute from **mathematics** — substrate agnostic. |
| 2 | Intelligence **emerged** on the fixed backend; product names are optional labels. |
| 3 | **Lucas/Pisot scales everything** — memory, speed, search, quantum, workers, audit, Chronus batches, every front. |
| 4 | **Exponential memory** via fold-first custody + Lucas budgets. |
| 5 | **Exponential speed** via Lucas partitions + Pisot convergence + near-state dispatch. |
| 6 | Run **independent** (Chronus Virtual iGPU fabric) **or** **scale the customer GPU stack**. |
| 7 | Effective capacity is **maths-bounded** (`L_n` ratio envelope), not SKU fantasy. |
| 8 | **This repository is domicile**; M3 demonstrated the envelope. |
| 9 | **HYBA Intelligence** funds the line under Rule 7 — products on the same math. |
| 10 | One backend · any front · same scale law · no change. |

---

## Two independent scalers, one ladder

```text
LUCAS  (hardware / resource dimension)
  L_n = exact integer
  multiplies and partitions: cores, workers, batches, memory budgets,
  thread slices, search windows, parallel lanes
  → resource schedule climbs with the rung

PISOT  (convergence / quantum dimension)
  φ > 1, |ψ| < 1
  |ψ|^n collapses drift; walks and solvers waste fewer steps
  → quality / convergence climbs with the same rung

TOGETHER
  rung index ∈ Chronus / Turing ladder stops
  every domain: resolve_scale(domain, n) or Chronus scale_job / effective_capacity
  intelligence is on the ladder — it does not own the ladder
```

Canonical offering policy: `chronus/seam/scale.py`  
Integer Lucas/Pisot identities: Turing + `frontend/src/lib/lucas_pisot_separate.ts`

---

## Exponential memory · exponential speed

| Axis | Mechanism | Bound |
|------|-----------|--------|
| Memory | Pulvini / substrate fold + Virtual Memory Plane commits evidence folded; Lucas budgets size the envelope | fold density + `L_n` — not raw DRAM cosplay |
| Speed | Lucas work partitions + Pisot convergence + Chronus near-state / device dispatch | maths + measured device path under Rule 7 |

**Folded form = working form** kills the raw-state tax at the source:
consumers operate on invertible folded state; tier-0 density is algebraic, not
lossy truncation marketed as compression.

---

## Independent fabric **or** scale your stack

| Mode | Meaning |
|------|---------|
| **Independent** | Chronus Virtual iGPU (`chronus/virtual_igpu/`): ABI, adapters, attestation, folded memory plane — full control plane without waiting on a customer census. |
| **Scale your stack** | Same contracts over the customer CUDA / OpenCL / Metal / XPU census: probe → negotiate → run at a ladder stop → evidence in custody. Their GPUs; our scale law. |

One mathematics. Two deployment verbs. No second backend.

---

## Effective capacity (Rule 7)

Physical inventory stays physical. The scale contract publishes a **logical work
envelope**, never a fake device count and never a hashrate.

```text
effective ≈ physical_units × L_n / L_ref     # integer ratio envelope
physical_units  = real census (cards, tiles, or negotiated units)
L_n             = Lucas value at ladder stop n
L_ref           = reference rung (see chronus.seam.scale)
```

API (offering-level, not a throughput oracle):

```python
from chronus.seam.scale import compute_effective_capacity, effective_capacity

# Structured envelope (preferred in code)
cap = compute_effective_capacity(physical_units=80, ladder_index=15)

# Dict form for telemetry / audit payloads
effective_capacity(80, ladder_index=15)
```

### M3 witness class (historical test bed)

On the M3 path in the prior research line, a physical inventory on the order of
**80** GPUs was operated under the Lucas/Pisot contract such that the **effective
capacity / schedule envelope** sat in the **~800-class** band — **limited by the
mathematics of the rung**, not by inventing cards.

That run was the **proof bed**. **Chronus in this repository is home.**

Rule 7 fences (non-negotiable):

- Ladder stop ≠ advertised TH/s or pool hashrate.
- `work_items` / batch size = ladder stop; not a measured throughput claim.
- `effective` is a scale-contract envelope; physical count is unchanged.
- Measured dispatches are measured; projections stay labelled projections.
- Unavailable hardware stays unavailable.

See `RULE7_NOTE` and `EffectiveCapacity` in `chronus/seam/scale.py`.

---

## Where the stack lives

```text
HYBA Intelligence (commercial / research vehicle)
        │
        ▼
┌────────────── Chronus (canonical iGPU offering) ──────────────┐
│  device census · resident execution · Virtual iGPU            │
│  ABI · adapters · attestation · VirtualMemoryPlane            │
│  seam/scale.py → Lucas/Pisot offering-level policy            │
└──────────────────────────┬────────────────────────────────────┘
                           │ Turing = compute
                           ▼
┌────────────── Fixed mathematical backend ─────────────────────┐
│  TOE seat · φ / Fib / Lucas / Pisot · 11D · Binet spine       │
│  scale law sizes hardware, search, quantum, memory,           │
│  workers, audit, tensor, curriculum — EVERYTHING              │
└──────────────────────────┬────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
   Pulvini (fold)    Compass (lenses)   Governance (AL HARAS)
   Cortex (fold-train)  Solutions API    Enterprise surfaces
```

**Chronus owns:** route, state, device policy, punch/kernels, topology bindings,
telemetry, fleet composition, dispatch provenance, attestation, Virtual iGPU.

**Turing owns:** mathematical computation Chronus invokes. Chronus does not
rename, wrap, or absorb Turing.

**External ops boundary:** live pool protocols, worker credentials, reward and
accounting workflows stay outside this intelligence/iGPU domicile unless an
approved integration contract says otherwise.

---

## Five pillars → one spine

| Pillar | Role in this paradigm |
|--------|------------------------|
| **Pulvini** | Lossless fold — working form, not archive form |
| **Compass** | Multi-lens search over folded state |
| **Accel / iGPU (Chronus)** | Near-state dispatch; independent fabric or customer iron |
| **Cortex** | Train / optimize in the fold |
| **Governance** | Attestation, ABAC, WORM — Rule 7 evidence path |

All five hang on the same Binet / Lucas / Pisot spine. Pillars are skins; the
scale law is not optional per product.

---

## HYBA Intelligence (why the research gets paid)

**Strategic infrastructure intelligence** for sovereign data centers, hyperscalers,
and global enterprises — shipped on this substrate:

- 11D decision coordinates (state, causal, audit, value, ops, proof planes)
- Solutions API and enterprise services as **fronts** on one backend
- Millennium-class engines as **first-principles solvers / demos** under Rule 7
  (not marketing closures of open Clay problems)
- MRI / unimodular and other deep-tech surfaces as domain fronts, same math
- Claims ledger and evidence boundaries govern every published figure

Research climbs the ladder. Product sits on the ladder. Measurement stays honest.

---

## Doctrine (final)

```text
RAW-STATE TAX          → killed by fold-first working form
LUCAS / PISOT          → universal scaler of everything
CHRONUS                → iGPU home (this repo)
VIRTUAL iGPU           → independent fabric
SCALE YOUR STACK       → same contracts on customer census
EFFECTIVE CAPACITY     → L_n envelope, Rule 7 safe
M3 80 → ~800 CLASS     → witness, not a SKU press release
HYBA INTELLIGENCE      → commercial vehicle for the line
ONE BACKEND            → any front, maths-limited only
```

When in doubt: read `chronus/seam/scale.py`, run the Chronus truth contract in
`README.md`, and refuse any claim that turns a ladder stop into cosplay throughput.
