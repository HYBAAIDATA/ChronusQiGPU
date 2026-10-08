# chronos-core

Chronos GPU — the mathematical quantum graphics engine (Chronos v3.3 maths).

`chronos-core` publishes the Chronos mathematics plane as a standalone
distribution: M32 manifold, QSDL compiler, Hamiltonian library, layered QAOA
evolution engine, ray-traced reconstruction with real supersampling, and the
theory/academic domains. Import requires only numpy — never OpenCL, CUDA, or
Metal. The GPU substrate lane is opt-in (`pip install chronos-core[gpu]`)
and fail-closed: an explicit backend request that cannot bind raises; it is
never silently substituted with a CPU path.

Source of truth: the [PhiMiner monorepo](https://github.com/QuantumPhiRedux/PhiMiner)
(`chronus/v33`). This scaffold is the packaging contract; the monorepo
distribution `pythia-mla1517` stays canonical until the CI wheel-build
verification protocol in `packaging/README.md` passes.

```python
from chronus.v33.engine import ChronosEngine

engine = ChronosEngine()
result = engine.render("scene sunset { ... }")
print(result.energy)
```

Every performance claim is tracked in the machine-checkable claim ledger:
`chronus/v33/benchmarks/claims.py` (MEASURED / GATED / UNMEASURED).

## Resident iGPU and M5 packaging distinction

This package intentionally ships only the v3.3 mathematics plane. Its boundary
excludes `chronus.m5_ultra`, virtual iGPU, delivery and product readiness. It is
not a complete standalone resident Chronus distribution.

The M5-integrated resident release candidate is built from
[`packages/chronos-one-igpu`](../../packages/chronos-one-igpu/README.md),
distribution `chronos-one-igpu`, import `chronos_one_igpu`. That wheel includes
a byte-parity-checked copy of the canonical M5 descriptor and binds it to the
existing resident runtime. It does not turn modelled M5/AI/quantum specifications
into physical execution evidence. Neither package is promoted to production
merely because it builds; current-head evidence and the relevant release gates
remain required.
