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
| A1 Fibonacci address space, strictly increasing per writer | **MEASURED** | `test_a1_index_stream_strictly_increasing_fibonacci` — 20k bounded indices |
| A2 Cassini quadruple per transition; `verify_ledger` exact | **MEASURED** | `test_a2_ledger_verify_and_single_forged_quadruple`; selftest `storage_contract` |
| A3 Gap detection before retrieval | **MEASURED** | `test_a3_gap_detection_blocks_retrieval`; attach-time `SegmentMissing` |
| A4 Forged index/value rejected | **MEASURED** | `test_a4_forged_index_and_value_rejected`, `test_a4_duplicate_and_regressed_index_rejected` |
| A5 Bounded advance per write (`≤ max_step`) | **MEASURED** | `test_a5_bounded_advance_enforced`; `test_a6_concurrent_writers_disjoint_ranges` |
| A-ABI layout and constants | **MEASURED** | C headers parsed at test time; Python/native ABI compile checked |
| A-ABI cooperating multi-process readers/writers | **MEASURED** | `test_python_writers_are_serialized_across_processes`; native C uses the same advisory file lock; hardware interop remains external |
| Atomic snapshot/replay, digest rejection and operator prefix recovery | **MEASURED** | `tests/test_aethel_fault_injection.py`; journal-last publication and verified-prefix recovery |
| Manifold repair and fail-closed outcomes | **MEASURED** | `test_manifold_heals_digest_verified_copy_and_fails_closed_without_one`; one deterministic repair plus one unrecoverable case |

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
| `to_manifold` produces engine-acceptable points | **PROVISIONAL** | `tests/test_aethel_geodesic_handoff.py`; engine/package availability and deployed-engine semantics are separate evidence gates |
| `from_manifold` round-trips byte-identically | **MEASURED** | selftest `geodesic_handoff`; `from_manifold` digest gate |
| Engine invariants hold on the storage manifold | **MEASURED** | `check_engine_invariants()` runs `build_search_crystal` + `partition_interval` + `cassini_permutation` + `enumerate_nonces` *unchanged* — 32 faces, coverage complete, unimodular schedules, exact enumeration |
| Engine's OWN invariant checks reused, never reimplemented | **MEASURED** | `test_no_invariant_reimplementation_in_this_file` meta-guard; `test_no_standalone_search_engine` in `test_aethel_package.py` |
| BLOCKED items | none | both engine surfaces expose reusable invariant functions |

## CLI / selftest verdicts

- `python -m aethel health` → liveness only.
- `python -m aethel selftest` → structured software checks; missing optional
  engine/C headers remain UNVERIFIED, not PASS.
- `python -m aethel readiness` → fails closed while the capability manifest
  has external evidence gates; software unit tests do not set production
  readiness.
- `fold` / `unfold` / `verify-address` / `verify-ledger` / `to-manifold` /
  `backup` / `restore` / `recover`
  operate on a snapshot store (`--store`/`AETHEL_STORE`); corrupt or
  missing stores exit non-zero with typed diagnostics.

## Packaging / deployment

- `pyproject.toml`: `aethel` in `package-dir` and `packages`;
  `package-data` ships `py.typed`, contract docs and `capabilities.json`.
- Root distribution metadata is named `pythia-mla1517`; because it is not an
  `aethel` distribution, Aethel's runtime version resolver falls back to its
  source version. A standalone `aethel` distribution's valid metadata takes
  precedence.
- Docker: `pip install ".[hardware]"` in `Dockerfile` includes aethel;
  `python -m aethel selftest` is the container-level probe. The mmap ABI
  uses caller-supplied paths — a `/dev/shm` mount is required for
  POSIX-style shared regions and documented in `aethel/README.md`.

## Open items deferred to a future pass

1. **Full soak**: the harness is configurable through
   `AETHEL_SELFTEST_WRITES`/`AETHEL_SELFTEST_ROUNDTRIPS`, with a one-million
   total-write ceiling and bounded per-space indices. Only focused/reduced
   software runs are appropriate for CI; million-write and long-duration
   resource/soak evidence remains external.
2. **`GeodesicNavigator.query_geodesic`** remains PROVISIONAL. It records why
   it uses the documented bisection fallback; no result equivalence to the
   optional Pathfinder is claimed.
3. **OpenCL/Chronus hardware parity, container and deployment filesystem
   behavior** require target-environment evidence.
4. **`aethel.hardened_unified_substrate`** remains as the flat
   compatibility façade — INTERNAL.
5. Payload SHA-256 is unkeyed integrity, not authenticity. There is no
   quantum-speedup, unlimited-storage, compression-ratio, throughput or
   heal-rate claim.

The machine-readable claim ledger is `aethel/capabilities.json`; its
`production_ready` field remains false until external evidence is supplied.
