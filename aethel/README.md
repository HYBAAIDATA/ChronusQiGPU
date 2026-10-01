# aethel — PYTHIA topological storage substrate

`aethel` is the consolidated, first-class Aethel storage package. It owns
everything that was previously scattered across the historical
`hardened_unified_substrate` monolith (canonical at
`toe/hardened_unified_substrate.py`, aliased through
`Intelligence/hardened_unified_substrate`, frozen in
`legacy/AETHEL_Subsystem/`) plus a pure-Python implementation of the
shared-memory ingestion ABI previously only available in C
(`chronus/mla1517_platform/host/mla1517_aethel.{c,h}`).

The package is deliberately decoupled from mining operations. It requires
only NumPy; OpenCL punch hosts are optional and resolved lazily or
injected via `punch_host=`.

## Layout

| Module | Contents |
| --- | --- |
| `aethel.constants` | `DIM`, `PHI`, `PSI`, `SQRT5`, `LUCAS_*`, `MODULUS_Q`, `PRIMES_25` |
| `aethel.cassini` | `CassiniVerifier` — `L_n² − 5F_n² = 4(−1)ⁿ`, matrix form, precomputed-value form |
| `aethel.zeckendorf` | `HardenedZeckendorfCodec` (F_93, full uint64), `SparseTopology`, `apply_zeckendorf_compression` / `reverse_zeckendorf_expansion`, punch opcodes |
| `aethel.primes` | `GaloisPrimeSubstrate`, `PrimeCell` — composite keys in `GF(2⁶¹−1)` |
| `aethel.compute` | `VirtualSM`, `ComputeUnitPool`, `VirtualWarp`, `SPMDExecutor`, `OptimizedTensorMicroKernel`, `RTCoreMicroKernel`, `MicroKernelLibrary`, `DistributedActor`, `CollectiveOps`, `DistributedDataflowGraph`, `DAGNode`, `DependencyDAG` |
| `aethel.gpu` | `ChronusContext` — pv-lattice projection, GPU or identical CPU path |
| `aethel.manifold` | `PrimeStorageManifold`, `TopologicalTensor`, `ManifoldCurvature`, `ManifoldSector`, `GeodesicNavigator`, `SelfHealingSubstrate` |
| `aethel.unified` | `UnifiedSubstrate` (alias `HardenedUnifiedSubstrate`) |
| `aethel.shm` | `AethelQueue`, `AethelRecord` — mmap seqlock slot queue, ABI v1, `attach()` fails closed with `SegmentMissing` |
| `aethel.fibonacci` | exact fast-doubling `fibonacci`/`lucas`, `fibonacci_index`, `is_fibonacci`, `cassini_quadruple`/`cassini_holds`, `binet_fibonacci` (exact Q(√5) closed form), `BinetIndex` |
| `aethel.encoding` | `fold`/`unfold`, `ZeckendorfVector`, `MAX_FOLD_LEN` — Binet+Zeckendorf payload encoding |
| `aethel.storage` | `AddressSpace`, `CassiniLedger`, `FibonacciAddress`, `LedgerEntry` — Fibonacci-indexed store, Cassini address-stream integrity |
| `aethel.geodesic` | `GeodesicHandoff`, `ManifoldPoint` — the ONLY interface to the geodesic engine (`Intelligence.search_crystal`); nothing is reimplemented |
| `aethel.errors` | typed failures: `InvalidAddress`, `GapDetected`, `SegmentMissing`, `AbiVersionMismatch`, `FoldDomainOverflow`, `ZeckendorfInvariantError`, `HandoffRejection`, `EngineUnavailable` |
| `aethel.selftest` | `run_selftest()` — structured verdict over the whole contract battery |
| `aethel.costs` | measured CPU/memory cost accounting (`process_time_ns` deltas, never simulated) |
| `aethel.hardened_unified_substrate` | flat façade re-exporting the complete legacy import surface |

## Architecture

**Storage** is Fibonacci + Cassini: `AddressSpace` places blocks on the
Fibonacci sequence; every transition appends a Cassini quadruple
`(F_{n-1}, F_n, F_{n+1}, (−1)ⁿ)` to `CassiniLedger`, which detects forged
indices, gaps, duplicates and regressions before any read is served.

**Encoding** is Binet + Zeckendorf: `fold` maps payload bytes to
non-adjacent-Fibonacci masks (unique by Zeckendorf's theorem); `unfold`
restores them byte-identically. `binet_fibonacci` is evaluated exactly in
Q(√5) and cross-checked against the recursive index (B3).

**Retrieval and search** are the geodesic engine — already built, already
proven, the same engine that orders the Bitcoin nonce space. Aethel does
not reimplement it: `GeodesicHandoff` maps blocks to engine points and
back, and `check_engine_invariants()` runs the engine's own coverage and
unimodularity checks against the storage interval.

## Invariants enforced

- **Cassini gate**: curved-storage anchors must satisfy
  `L_n² − 5F_n² = 4(−1)ⁿ`; `AethelQueue.commit` admits only states whose
  D10 seal is exactly `±1`.
- **Lossless fold**: `reverse_zeckendorf_expansion(apply_zeckendorf_compression(x)) == x`
  for arbitrary bytes; masks always satisfy the non-adjacent-bits rule.
- **Digest-pinned reads**: every manifold payload stores its SHA-256 at
  ingest; reads verify, attempt one self-heal from a redundant copy
  (sparse topology → prime-exponent substrate → raw payload), re-verify,
  and return `None` rather than corrupt bytes.
- **Honest backend evidence**: `stage_evidence` records which backend
  (`opencl:gpu` / `opencl:cpu` / `cpu`) physically ran encode/index/decode;
  fold ratios are measured, never asserted.

## Shared-memory ABI

`aethel.shm.AethelQueue` is byte-compatible with the C region:

```
header 0x40:  u64 magic 0x4D4C413135313741 ("MLA1517A"), u32 version=1,
              u32 slot_count, u64 reserved[6]
slot[i] 0x80: u64 sequence (seqlock) | u8 state[64] | pad
route: slot = le_u32(state[28:32]) % slot_count
gate:  le_i32(state[40:44]) ∈ {+1, −1}
```

```python
from aethel import AethelQueue

with AethelQueue("/dev/shm/aethel.region", slot_count=20) as q:
    slot = q.commit(state64)          # None when the Cassini gate rejects
    rec = q.read(slot)                # None when empty/unstable
```

On POSIX the same backing file is interoperable with `libmla1517`
producers (`mla1517_drain_vault_to_aethel`, `mla1517_aethel_commit`).

## Compatibility

`toe.hardened_unified_substrate` is an identity-preserving alias of
`aethel.hardened_unified_substrate`: both paths resolve to the same
module object, so every existing toe/Intelligence consumer binds to this
package. `Intelligence.hardened_unified_substrate` is a retired path per
the toe/kellogg no-shims convention.

## Deployment

`/dev/shm` (or any caller-supplied writable path) hosts the ABI region —
deployment manifests should mount a sized `shm` for POSIX shared-memory
interoperation with `libmla1517`. In containers, verify with:

```bash
python -m aethel selftest
```

## CLI

```
python -m aethel [--store DIR] fold <input>
python -m aethel [--store DIR] unfold <index-or-address>
python -m aethel [--store DIR] verify-address <index>
python -m aethel [--store DIR] verify-ledger
python -m aethel [--store DIR] to-manifold <index-or-address>
python -m aethel selftest [--full]
```

Exit code 0 on health, non-zero on any corruption or missing segment.
Store directory: `--store` flag or `AETHEL_STORE` (default `./aethel_store`).

```bash
python -m pytest tests/test_aethel_storage.py tests/test_aethel_encoding.py \
    tests/test_aethel_concurrency.py tests/test_aethel_geodesic_handoff.py \
    tests/test_aethel_package.py
```
