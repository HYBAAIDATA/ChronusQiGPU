# aethel — Storage & Encoding Contract

Version covered: `aethel.__version__` (single source of truth in
`aethel/__init__.py`). Every claim is labeled **MEASURED** (executed test or
instrumented run in this repo), **DECLARED** (asserted and enforced by
construction, not separately benchmarked), or **UNVERIFIED** (written in
code, not yet exercised).

Architecture: **Storage = Fibonacci + Cassini. Encoding = Binet +
Zeckendorf. Retrieval + Search = the geodesic engine** — already built and
proven (`Intelligence.search_crystal.PoincareCassiniSearchEngine`, the same
engine that orders the Bitcoin nonce space, plus the `kellogg.traversal`
32-face frame walk). Aethel does not implement retrieval or search; it
hands the engine a well-formed storage manifold through
`aethel.geodesic.GeodesicHandoff`. There is no Section C here: the engine's
own contracts are declared and tested in its own modules.

---

## Section A — Storage (Fibonacci + Cassini)

The address space is the Fibonacci sequence. Block `k` committed by a
writer occupies index `n_k` and is addressed by `F_{n_k}`
(`aethel.storage.AddressSpace`, `aethel.storage.CassiniLedger`).

### A1. Address space — Fibonacci-indexed, monotonic

- **MEASURED**: `AddressSpace.write` produces strictly increasing
  Fibonacci indices per writer and `address.value == fibonacci(index)`
  exactly (`tests/test_aethel_storage.py::test_a1_index_stream_strictly_increasing_fibonacci`,
  20k writes; soak scale in `aethel selftest --full`).
- **DECLARED**: `FibonacciAddress.__post_init__` enforces
  `value == fibonacci(index)` and `index >= 1` — a forged address object
  cannot be constructed.
- Failure mode: `InvalidAddress` at write/register time. Recovery: the
  write is rejected before the ledger is touched; retry with a legal
  index.

### A2. Cassini ledger — the address-stream integrity invariant

- **MEASURED**: every committed transition appends the quadruple
  `(F_{n-1}, F_n, F_{n+1}, (-1)^n)`; `CassiniLedger.verify_ledger()`
  returns True iff every quadruple satisfies
  `F_{n-1}·F_{n+1} − F_n² = (−1)^n`, every recorded value equals the true
  `fibonacci(index)`, the global write sequence is contiguous, and each
  writer's index stream strictly increases
  (`test_a2_ledger_verify_and_single_forged_quadruple` — a single forged
  quadruple flips the verdict to False).
- **DECLARED**: Cassini validates the *address stream* — it proves the
  indices are a genuine Fibonacci walk. It is not, and is never presented
  as, a payload-integrity check (payload integrity is the per-entry
  SHA-256 digest).
- Failure mode: `InvalidAddress`/`GapDetected` via `check_consistent`;
  `verify_ledger()` returns False for audit callers. Recovery: replay
  stops at the first corrupt position; the journal can be truncated to the
  last consistent prefix by an operator.

### A3. Gap detection

- **MEASURED**: removing one index from the stream makes every subsequent
  `read()` raise `GapDetected` before any payload is returned
  (`test_a3_gap_detection_blocks_retrieval`).
- **DECLARED**: attach-time replay raises `SegmentMissing` when a ledger
  entry has no block file — a partial store is never silently served.
- Recovery: restore the missing block or truncate the journal to the last
  consistent prefix; `attach` then verifies.

### A4. Forgery detection

- **MEASURED**: `register(index, value, payload)` raises `InvalidAddress`
  for any `(index, value)` pair not on the true Fibonacci sequence —
  including a genuine Fibonacci value bound to the wrong index — and for
  duplicate/regressed indices (`test_a4_forged_index_and_value_rejected`,
  `test_a4_duplicate_and_regressed_index_rejected`).
- Recovery: drop the forged write; the ledger is untouched.

### A5. Bounded write

- **MEASURED**: a single write advances the index by `advance ∈
  [1, max_step]` (default `max_step = 4`); exceeding the bound raises
  `InvalidAddress` (`test_a5_bounded_advance_enforced`).
- **DECLARED**: concurrent writers operate through `fork(writer=…)` on
  disjoint ranges over the shared ledger; the global write sequence stays
  contiguous (`test_a6_concurrent_writers_disjoint_ranges`).

### A-ABI. Shared-memory region (`aethel.shm`)

- **MEASURED**: `AethelQueue` is byte-compatible with
  `chronus/mla1517_platform/host/mla1517_aethel.{c,h}` — all seven constants
  are parsed out of the C headers at test time and compared
  (`tests/test_aethel_concurrency.py::test_t6e_c_abi_agreement_parses_header`).
- **MEASURED**: seqlock semantics — odd sequence = write in flight, even
  non-zero = stable; concurrent commit/read produces no torn records
  (`test_t6a`), a crashed writer's odd sequence is discarded and recovered
  (`test_t6b`).
- Failure modes: `SegmentMissing` on attach to an absent region;
  `AbiVersionMismatch` on a stale region; D10 seal ∉ {±1} drops the
  record at commit.

### A6. Overhead accounting (`aethel.costs`)

- **MEASURED**: `OverheadMeter` records per-operation CPU time
  (`time.process_time_ns`), wall time (`time.perf_counter_ns`), and
  payload bytes for `CassiniLedger.append` / `check_consistent` /
  `index_of`, `AddressSpace.write` / `register` / `read` / `snapshot`,
  `AethelQueue.commit` / `read`, and
  `PrimeStorageManifold.ingest_sync` / `read_payload` / `query` /
  `measure_throughput`. Exposed via `*.overhead_report()`;
  `UnifiedSubstrate.stats()` embeds the manifold report
  (`tests/test_aethel_overhead.py`).
- **DECLARED**: `structural_bytes()` is a floor — `sys.getsizeof` over
  the live containers; allocator slack, page tables, and per-thread OS
  state are not counted. `AethelQueue.structural_bytes` is exact: the
  mapped region size (`AETHEL_HEADER_BYTES + slot_count * 0x80`).
- **MEASURED**: `measure_alloc(fn)` reports the tracemalloc peak
  attributable to a single call — real allocation, not an estimate.
- **DECLARED**: a ledger shared by `fork()` writers aggregates every
  writer's append cost into the one ledger meter; each `AddressSpace`
  meters only its own writes. The meter's own cost is two clock reads
  per instrumented op (~50–100 ns) — always-on, never alters behavior.

---

## Section B — Encoding (Binet + Zeckendorf)

Payload bytes fold into `ZeckendorfVector`: one Zeckendorf mask per 8-byte
chunk, each mask the unique sum of non-consecutive Fibonacci numbers.
`aethel.encoding.fold` / `unfold` are the codec boundary.

### B1. Uniqueness (Zeckendorf's theorem)

- **MEASURED**: every emitted mask satisfies non-adjacency
  (`mask & (mask << 1) == 0`) and decodes to exactly its input
  (`test_b1_zeckendorf_uniqueness_non_adjacent`, 2k random uint64s).
- **MEASURED**: every `fold()` output self-verifies
  (`test_b1_folded_vectors_verify`).

### B2. Round trip

- **MEASURED**: `unfold(fold(x)) == x` byte-identical for random payloads
  of length 1–1024, including the empty payload and single-byte edges
  (`test_b2_roundtrip_byte_identical`, `test_b2_edge_cases`).

### B3. Binet consistency

- **MEASURED**: `binet_fibonacci(n)` — Binet's closed form evaluated
  exactly in Q(√5) — equals the recursive `fibonacci(n)` to integer
  equality for `n ∈ [0, 10⁴]` (`test_b3_binet_matches_recursive_exact`).
  Two independent algorithms; agreement is a real cross-check, not a
  tautology.

### B4. Domain boundary

- **MEASURED**: `fold` rejects `len(payload) > max_fold_len` (default
  `MAX_FOLD_LEN = 1 MiB`) with `FoldDomainOverflow` — no silent
  truncation, no silent extension (`test_b4_fold_domain_overflow_rejected`,
  `test_b4_malformed_vector_rejected`).
- **MEASURED**: encoding is deterministic across fresh interpreter
  sessions (`test_t4e_determinism_across_interpreters`).
- **DECLARED — no unlimited-storage claim**: the bound is O(log N) per
  value (Zeckendorf masks are ≤ 92 bits for uint64 inputs); the measured
  curve is linear in payload length — 8 bytes per folded unit
  (`test_encoding_bound_is_logarithmic`).

---

## Handoff boundary (declared, not a section-claim)

`aethel.geodesic.GeodesicHandoff` is the **only** interface between aethel
and the geodesic engine. `to_manifold(address) -> ManifoldPoint` maps a
committed block to an engine-space position plus a 76-byte routing key;
`from_manifold(point) -> bytes` resolves a point back through the ledger
to payload bytes with full integrity re-verification. The engine's own
invariants (`build_search_crystal`, `partition_interval`,
`cassini_permutation`, `enumerate_nonces`, `CoverageCertificate.verify`)
are imported and run against the storage interval unchanged — see
`tests/test_aethel_geodesic_handoff.py` and `check_engine_invariants()`.
Aethel reimplements none of it.
