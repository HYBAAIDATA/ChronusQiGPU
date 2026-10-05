# Chronus

**Chronus is HYBA's canonical iGPU offering. Turing is compute.**

Chronus owns the hardware-facing product/runtime boundary: device census and
selection, resident execution, mathematical-state memory, punch/kernels,
M32/H4 topology bindings, measured telemetry, fleet composition, dispatch
provenance and attestation.

Turing remains the mathematical computation substrate Chronus invokes. Chronus
does not rename, wrap, or absorb Turing.

**Paradigm (full doctrine):** [`PARADIGM.md`](./PARADIGM.md) — folded form is the
working form; Lucas/Pisot scales everything; independent Virtual iGPU **or**
scale the customer GPU stack; maths-limited effective capacity; this tree is
home (M3 was the test bed).

## Runtime boundary

```text
Turing computation
      |
      v
Chronus route / state / device policy
      |
      +--> OpenCL integrated GPU
      +--> OpenCL discrete GPU
      +--> CUDA / Metal capability surfaces where implemented
      +--> Chronus Virtual iGPU fabric (independent plane)
      +--> explicit CPU reference/fallback where permitted
      |
      v
measured telemetry + attestation
```

OpenCL, CUDA, Metal, GPU and integrated GPU remain factual backend/hardware
terms. They are not competing HYBA product identities.

## Scale law (Lucas / Pisot)

Chronus offering-level policy lives in `chronus/seam/scale.py`.

- Batch / `work_items` sizes **snap to ladder stops** — not hashrate multipliers.
- **Lucas** sizes the hardware/resource envelope (`L_n` integer budgets and partitions).
- **Pisot** governs convergence drift on the same rung index.
- The ladder scales **everything** that asks the contract (memory, workers,
  search windows, virtual plane budgets, audit metadata) — intelligence included,
  nothing privileged.

### Effective capacity (Rule 7)

Physical census is never rewritten. The contract publishes a **logical work
envelope**:

```text
effective ≈ physical_units × L_n / L_ref    # integer ratio; not a device mint
```

```python
from chronus.seam.scale import compute_effective_capacity, effective_capacity

compute_effective_capacity(80, ladder_index=15)  # EffectiveCapacity
effective_capacity(80, ladder_index=15)          # audit-safe dict
```

**M3 witness class:** physical inventory on the order of 80 GPUs under the scale
contract produced a **~800-class effective envelope**, bounded by mathematics
(`L_n`), not by inventing cards. That path was the proof bed; **this repository
is domicile**.

Never report ladder stops, `work_items`, or `effective` as measured TH/s or as
a fake GPU count. See `RULE7_NOTE` in `seam/scale.py` and [`PARADIGM.md`](./PARADIGM.md).

## Deployment verbs

| Mode | Meaning |
|------|---------|
| **Independent** | `chronus/virtual_igpu/` — ABI, adapters, attestation, folded memory plane. |
| **Scale your stack** | Same contracts over customer CUDA/OpenCL/Metal/XPU census; their iron, our ladder. |

## Truth contract

Chronus reports what ran. Measured dispatches are measured, projected figures
stay labelled projections, and unavailable hardware remains unavailable. In the
mining path, SHA-256d target verification remains the sole acceptance authority.

Historical Chronos/Chronus design targets such as fixed 8K frame times,
"perfect GI", "infinite resolution", O(1) search, or fixed PULVINI compression
ratios are not promoted as measured capabilities here unless reproducible tests
produce that evidence.

## Migration rule

**Chronus** (`chronus/`) is the product iGPU offering — import that for device,
virtual_igpu, scale, and MLA1517 surfaces.

**Chronos GPU maths** live under `chronus/v33/` (engine v3.3). A thin deprecated
top-level `chronos` package re-exports `chronus.v33` so older `import chronos`
paths keep working (emits `DeprecationWarning`). Prefer:

```python
from chronus.v33 import ChronosEngine, M32Manifold
```

The operator’s older root drop was Chronos GPU **v2**; it is archived at
`legacy/chronos_gpu_v2_drop/` (provenance only — do not import). Integration
record: `docs/CHRONOS_DROP_INTEGRATION.md`. Other historical trees under
`legacy/` remain provenance only.

Page ↔ tree checklist for Chronos GPU maths elevation: `chronus/v33/docs/PAGE_CHECKLIST.md`.
