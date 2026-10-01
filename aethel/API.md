# aethel — Public API Surface

Stability levels: **STABLE** (frozen signature + semantics, changes need a
version bump), **PROVISIONAL** (shipped, may evolve), **INTERNAL**
(importable but not part of the contract).

`aethel.__version__` in `aethel/__init__.py` is the single source of
truth; no other module declares a version string.

## STABLE

### Storage (Fibonacci + Cassini)

| Symbol | Module | Contract |
| --- | --- | --- |
| `AddressSpace` | `aethel.storage` | `write(payload, advance=1) -> FibonacciAddress`; `register(index, value, payload)`; `read(address) -> bytes`; `verify() -> bool`; `fork(writer)`; `snapshot(dir)` / `attach(dir)`; `address_of(value)` / `address_of_index(index)` |
| `CassiniLedger` | `aethel.storage` | `append(index, digest, writer=, value=) -> LedgerEntry`; `verify_ledger() -> bool`; `check_consistent()` raises; `index_of(index)` |
| `FibonacciAddress` | `aethel.storage` | immutable `(index, value)`; forged pairs unconstructible |
| `LedgerEntry` | `aethel.storage` | `(seq, index, value, quadruple, digest, writer)` |
| `fibonacci` / `fibonacci_index` / `is_fibonacci` | `aethel.fibonacci` | exact fast-doubling arithmetic |
| `cassini_quadruple` / `cassini_holds` | `aethel.fibonacci` | the `(F_{n-1}, F_n, F_{n+1}, (-1)^n)` witness |

### Encoding (Binet + Zeckendorf)

| Symbol | Module | Contract |
| --- | --- | --- |
| `fold` | `aethel.encoding` | `bytes -> ZeckendorfVector`; `FoldDomainOverflow` beyond `max_fold_len` |
| `unfold` | `aethel.encoding` | `ZeckendorfVector -> bytes`; `ZeckendorfInvariantError` on malformed vectors |
| `ZeckendorfVector` | `aethel.encoding` | `blocks`, `total_bytes`, `verify()`, `folded_units` |
| `BinetIndex` | `aethel.fibonacci` | `BinetIndex(n).value` — exact closed form in Q(√5); `BinetIndex.of(v)` raises on non-Fibonacci values |
| `binet_fibonacci` / `binet_approx` | `aethel.fibonacci` | exact Q(√5) evaluation / Decimal diagnostic |
| `HardenedZeckendorfCodec` | `aethel.zeckendorf` | `encode/decode/verify_non_adjacent` — F_93 lane, full uint64 |
| `apply_zeckendorf_compression` / `reverse_zeckendorf_expansion` | `aethel.zeckendorf` | `bytes -> SparseTopology` / `SparseTopology -> bytes`; lossless |
| `SparseTopology` | `aethel.zeckendorf` | non-adjacent-bit mask container |
| `MAX_FOLD_LEN` / `encoding_domain` | `aethel.encoding` | the declared domain |

### Geodesic handoff — the ONLY engine interface (STABLE, versioned)

| Symbol | Module | Contract |
| --- | --- | --- |
| `GeodesicHandoff` | `aethel.geodesic` | `to_manifold(address) -> ManifoldPoint`; `from_manifold(point) -> bytes`; `retrieve(key) -> bytes`; `engine()`; `storage_interval()`; `check_engine_invariants()`; `navigate(point)`; `version` |
| `ManifoldPoint` | `aethel.geodesic` | `(position, index, key, vector)` — engine-space coordinate |

The adapter imports `Intelligence.search_crystal` and
`Intelligence.pathfinder` lazily and reimplements nothing. Engine-side
schema validation (header length, interval bounds) is the engine's own.

### Shared-memory ABI

| Symbol | Module | Contract |
| --- | --- | --- |
| `AethelQueue` | `aethel.shm` | `commit(state64) -> Optional[int]`; `read(slot, retries=8)`; `attach(path, n)` raises `SegmentMissing`; `flush/close`; context manager |
| `AethelRecord` | `aethel.shm` | `(slot_id, sequence, state)` snapshot |
| ABI constants | `aethel.constants` | `STATE_BYTES`, `AETHEL_ABI_VERSION`, `AETHEL_MAGIC`, `AETHEL_HEADER_BYTES`, `AETHEL_SLOT_STRIDE`, `AETHEL_D7_OFFSET`, `AETHEL_D10_OFFSET` |

### Typed errors

`AethelError` base; `InvalidAddress`, `GapDetected`, `SegmentMissing`,
`AbiVersionMismatch` (storage); `EncodingError`, `FoldDomainOverflow`,
`ZeckendorfInvariantError` (encoding); `HandoffRejection`,
`EngineUnavailable` (handoff) — `aethel.errors`.

### Legacy substrate façade (wiring surface)

| Symbol | Module | Contract |
| --- | --- | --- |
| `UnifiedSubstrate` (`HardenedUnifiedSubstrate`) | `aethel.unified` | façade over compute layers + manifold; what `toe.hardened_unified_substrate` resolves to |
| `PrimeStorageManifold` | `aethel.manifold` | `ingest_sync`, `read_payload` (digest-verified, `None` on corruption), `query`, `measure_throughput` |
| `ChronusContext` | `aethel.gpu` | `project_and_collapse_pv`; `require_gpu=True` refuses silent CPU fallback |
| `CassiniVerifier` | `aethel.cassini` | `verify(n)`, `verify_identity(n)`, `verify_with_values`, `verify_matrix` |
| `GaloisPrimeSubstrate` / `PrimeCell` | `aethel.primes` | composite keys in GF(2⁶¹−1) |
| constants | `aethel.constants` | `DIM`, `PHI`, `PSI`, `SQRT5`, `LUCAS_15/20/31`, `MODULUS_Q`, `PRIMES_25` |

## PROVISIONAL

| Symbol | Notes |
| --- | --- |
| `GeodesicNavigator` | `query`/`query_geodesic`/`batch_project`; prefers `Intelligence.pathfinder.Pathfinder`, falls back to bisection |
| `SelfHealingSubstrate` | `trigger(node)` — re-anchor to nearest Cassini-valid integer |
| `ManifoldCurvature` / `ManifoldSector` | curvature/sector enums |
| compute layers | `VirtualSM`, `ComputeUnitPool`, `VirtualWarp`, `SPMDExecutor`, micro-kernel library, distributed actors, `DependencyDAG` |
| punch opcodes | `PUNCH_ZECKENDORF_ENCODE`, `PUNCH_ZECKENDORF_DECODE`, `PUNCH_MANIFOLD_COMPUTE` |
| `run_selftest` | `aethel.selftest` — structured verdict; `python -m aethel selftest` exits non-zero on any failure |

## INTERNAL

- `aethel.hardened_unified_substrate` — flat re-export façade; `toe` and
  `Intelligence` import paths resolve to it. Do not import in new code.
- `aethel.punch` — lazy punch-host binding.
- `AddressSpace._blocks`, `CassiniLedger.entries` — same-package-trust
  internals used by `geodesic.py` and tests.

## Explicitly not part of this package

- Retrieval/search: the geodesic engines (`Intelligence.search_crystal`,
  `kellogg.traversal`) — consumed via the adapter, never restated.
- Mining / Stratum / consensus — aethel is storage + encoding only.
- Double-SHA256, target comparison, `kellogg/`, `toe/` internals.
