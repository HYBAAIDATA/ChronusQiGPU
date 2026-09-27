# Aethel Disposition Report

Scope: `aethel/` package — disposition of the corrected architecture:
Storage = Fibonacci + Cassini, Encoding = Binet + Zeckendorf, Retrieval +
Search = the existing geodesic engine via `aethel.geodesic.GeodesicHandoff`.

Wiring: `aethel.hardened_unified_substrate` is the canonical façade;
`toe.hardened_unified_substrate` resolves to the *same module object*
(identity alias), so every existing consumer (`toe.system`,
`toe.manifold_bridge`, `Intelligence.agentic_mining`,
`Intelligence.autonomous_capabilities`, `Intelligence.chain_verification`)
transitively binds to aethel. `Intelligence.hardened_unified_substrate`
is a retired path per the toe/kellogg no-shims convention.

## Section A — Storage (Fibonacci + Cassini)

| Claim | Disposition | Evidence |
| --- | --- | --- |
| A1 Fibonacci address space, strictly increasing per writer | **MEASURED** | `test_a1_index_stream_strictly_increasing_fibonacci` — 20k writes; `aethel selftest --full` soak |
| A2 Cassini quadruple per transition; `verify_ledger` exact | **MEASURED** | `test_a2_ledger_verify_and_single_forged_quadruple`; selftest `storage_contract` |
| A3 Gap detection before retrieval | **MEASURED** | `test_a3_gap_detection_blocks_retrieval`; attach-time `SegmentMissing` |
| A4 Forged index/value rejected | **MEASURED** | `test_a4_forged_index_and_value_rejected`, `test_a4_duplicate_and_regressed_index_rejected` |
| A5 Bounded advance per write (`≤ max_step`) | **MEASURED** | `test_a5_bounded_advance_enforced`; `test_a6_concurrent_writers_disjoint_ranges` |
| A-ABI shared-memory seqlock parity with `mla1517_aethel` | **MEASURED** | `test_t6a/b/c/d/e` — header parsed from C source at test time; no hardcoded duplication |
| Manifold-layer heal rates under fault injection | **UNVERIFIED** | declared in `aethel.manifold`; no committed fault-injection artifact |

## Section B — Encoding (Binet + Zeckendorf)

| Claim | Disposition | Evidence |
| --- | --- | --- |
| B1 Zeckendorf uniqueness (non-adjacent, single decoding) | **MEASURED** | `test_b1_zeckendorf_uniqueness_non_adjacent`, `test_b1_folded_vectors_verify` |
| B2 `unfold(fold(x)) == x` byte-identical | **MEASURED** | `test_b2_roundtrip_byte_identical` (2k random payloads ≤1024 B), edge cases |
| B3 Binet closed form == recursive index, exact | **MEASURED** | `test_b3_binet_matches_recursive_exact`, n ∈ [0, 10⁴], Q(√5) exact arithmetic |
| B4 Domain boundary (`FoldDomainOverflow`, no truncation) | **MEASURED** | `test_b4_fold_domain_overflow_rejected`, `test_b4_malformed_vector_rejected`; determinism across fresh interpreters (`test_t4e`) |
| Encoding bound | **DECLARED** | O(log N) per value, ≤92-bit masks for uint64; measured curve 8 B/unit (`test_encoding_bound_is_logarithmic`). No "unlimited storage" claim is made. |

## Section C — Handoff (adapter only; engine contracts out of scope)

| Claim | Disposition | Evidence |
| --- | --- | --- |
| `to_manifold` produces engine-acceptable points | **MEASURED** | `tests/test_aethel_geodesic_handoff.py` (5 tests, kellogg engine path); `GeodesicHandoff` (search_crystal path) |
| `from_manifold` round-trips byte-identically | **MEASURED** | selftest `geodesic_handoff`; `from_manifold` digest gate |
| Engine invariants hold on the storage manifold | **MEASURED** | `check_engine_invariants()` runs `build_search_crystal` + `partition_interval` + `cassini_permutation` + `enumerate_nonces` *unchanged* — 32 faces, coverage complete, unimodular schedules, exact enumeration |
| Engine's OWN invariant checks reused, never reimplemented | **MEASURED** | `test_no_invariant_reimplementation_in_this_file` meta-guard; `test_no_standalone_search_engine` in `test_aethel_package.py` |
| BLOCKED items | none | both engine surfaces expose reusable invariant functions |

## CLI / selftest verdicts

- `python -m aethel selftest` → all checks PASS (storage contract,
  encoding contract, seqlock queue, C ABI agreement, geodesic handoff);
  exit 0 healthy, non-zero on failure.
- `fold` / `unfold` / `verify-address` / `verify-ledger` / `to-manifold`
  operate on a snapshot store (`--store`/`AETHEL_STORE`); corrupt or
  missing stores exit non-zero with typed diagnostics.

## Packaging / deployment

- `pyproject.toml`: `aethel` in `package-dir` and `packages`;
  `package-data` ships `py.typed` + contract docs.
- Docker: `pip install ".[hardware]"` in `Dockerfile` includes aethel;
  `python -m aethel selftest` is the container-level probe. The mmap ABI
  uses caller-supplied paths — a `/dev/shm` mount is required for
  POSIX-style shared regions and documented in `aethel/README.md`.

## Open items deferred to a future pass

1. **Soak scale**: declared 10⁶-write battery runs via
   `aethel selftest --full` and `AETHEL_TEST_WRITES` env; CI runs the
   reduced scale (values grow to ~200k digits at n=10⁶ — measured scale
   is documented honestly, not silently shrunk in claims).
2. **Manifold-layer fault-injection heal rates** — UNVERIFIED above.
3. **`GeodesicNavigator.query_geodesic`** opportunistically imports
   `Intelligence.pathfinder` — optional dependency, PROVISIONAL (H4
   fallback declared).
4. **`aethel.hardened_unified_substrate`** remains as the flat
   compatibility façade — INTERNAL.
5. `importlib.metadata.version("aethel")` unresolved until installed —
   runtime `__version__` is canonical.
