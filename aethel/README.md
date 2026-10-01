# aethel — PYTHIA topological storage substrate

`aethel` is the canonical standalone storage and encoding substrate. Its
storage, encoding, and shared-memory ABI do not depend on mining or search
engines. Compatibility façades and narrow adapters expose selected APIs to
legacy consumers; they do not own Aethel's data model. The package includes a
pure-Python implementation of the shared-memory ingestion ABI
(`mla1517_platform_v3.4/host/mla1517_aethel.{c,h}`).

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
| `aethel.gpu` | `TensorCoreGPU_Context` — pv-lattice projection, GPU or identical CPU path |
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

**Geodesic search** is a provisional external-engine adapter. `GeodesicHandoff`
maps blocks to engine points and back; it does not own or reproduce an engine.
Fallback to the manifold's bisection query is explicit in telemetry and is not
an equivalence or performance claim.

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
- **Persistent snapshots**: bounded block files are fsynced and atomically
  replaced before the journal is atomically published and its directory
  fsynced. Replay validates the complete journal and each block digest before
  exposing a payload. This is a per-file, journal-last commit protocol, not a
  claim of transactional behavior on every filesystem.
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

Cooperating Python and native writers/readers serialize through an advisory
file lock; the seqlock remains a torn-record check, not a lock-free guarantee.
Writers must use the Aethel APIs and same backing file for this guarantee.
`flush()`/`close()` request mmap flush and `fsync`; commits are visible to other
processes immediately but are not promised durable until flush/close completes.

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
python -m aethel health
python -m aethel selftest
python -m aethel readiness
```

`health` is a liveness response. `selftest` validates executable software
contracts. `readiness` also evaluates `capabilities.json` and remains
`not_ready` while external hardware, soak, or deployment evidence is required.

## CLI

```
python -m aethel [--store DIR] fold <input>
python -m aethel [--store DIR] unfold <index-or-address>
python -m aethel [--store DIR] verify-address <index>
python -m aethel [--store DIR] verify-ledger
python -m aethel [--store DIR] to-manifold <index-or-address>
python -m aethel selftest [--full]
python -m aethel readiness
python -m aethel --store DIR backup --destination BACKUP_DIR
python -m aethel --store DIR restore --source BACKUP_DIR
python -m aethel --store DIR recover --truncate-to-last-consistent-prefix
```

`health` exits 0 while the process is alive. `readiness` exits 2 while any
production evidence gate is open; selftest exits non-zero on FAIL or
UNVERIFIED. Recovery always writes a journal backup before truncation.
Store directory: `--store` flag or `AETHEL_STORE` (default `./aethel_store`).
Payloads are limited to 16 MiB, indices to 20,000 and journals to 256 MiB by
default; these bounds avoid uncontrolled allocations and decimal-index growth.
The million-write soak is configurable with `AETHEL_SELFTEST_WRITES` and
`AETHEL_SELFTEST_ROUNDTRIPS` but requires multiple bounded address spaces.

```bash
python -m pytest tests/test_aethel_storage.py tests/test_aethel_encoding.py \
    tests/test_aethel_concurrency.py tests/test_aethel_geodesic_handoff.py \
    tests/test_aethel_package.py
```
