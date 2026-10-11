# v3.11 — PYTHIA-issued resident Hendrix execution

This increment preserves the supplied Lucas engine, solver, golden mathematics,
PRIME-DB, mining primitives and prior architecture. It adds execution of sealed
PYTHIA Hendrix plans through the real M32 / 11D / H4 dual-600 geometry.

- Immutable, versioned geometry and execution transport, exact M15 restoration.
- O(600) resident shard state and bounded vectorized positional execution.
- Actual prepared SHA256d batches, independent candidate verification, literal
  hash counters, plan/geometry/order identities and operation-scoped timings.
- OpenCL positional kernel and reusable device buffers with exact host parity.
  No physical execution/throughput is claimed without real device measurement.
- Thread-serialized resident execution entrypoints; bounded four-entry caches.
- Installable namespace `chronos_one_igpu`, avoiding the canonical PhiMiner
  repository's existing `chronos` package. Original `src/chronos` source is
  retained for lineage and source-compatibility regression checks, but is not
  installed by this distribution. Use `from chronos_one_igpu import OneIGPU`
  for the installed v3.11 product. CLI names remain unchanged.

The canonical mining bridge is in PhiMiner `chronus/one_igpu_mining.py`.
PYTHIA issues the plan; Chronus executes it. These APIs do not submit to a pool.
Physical H4 logical positions do not mean 600 physical cores or devices.
