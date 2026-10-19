# aethel — Failure Modes

Every failure belongs to exactly one tier: **S\*** storage
(Fibonacci/Cassini), **E\*** encoding (Binet/Zeckendorf), or **H\***
handoff (the adapter to the geodesic engine). No failure is attributed to
"retrieval" or "search" — those are the engine's modes, documented in the
engine's own modules. There is no silent corruption path.

## Storage (S*)

| ID | Trigger | Symptom | Recovery | Test |
| --- | --- | --- | --- | --- |
| S1 | Cassini ledger corruption (forged quadruple, forged value, regression) | `check_consistent` raises `InvalidAddress`; `verify_ledger()` → False; all reads gated | replay stops at first corrupt position; truncate journal to last consistent prefix | `test_a2_ledger_verify_and_single_forged_quadruple` |
| S2 | Missing index in the stream (gap) | `GapDetected` before any payload returns | restore the block or truncate journal; `attach` re-verifies | `test_a3_gap_detection_blocks_retrieval` |
| S3 | Forged Fibonacci index/value at write time | `InvalidAddress` at `write`/`register`; ledger untouched | reject the write; correct the caller | `test_a4_forged_index_and_value_rejected` |
| S4 | Shared-memory region absent at attach | `SegmentMissing` — no silent create | create the region via `AethelQueue(path, n)` first | `test_t6d_missing_segment_is_typed` |
| S5 | ABI version / magic / size mismatch on mapped region | `AbiVersionMismatch` / `AethelError` at open | rebuild the region with the current ABI | `test_t6e_c_abi_agreement_parses_header` |
| S6 | Writer crash mid-update (seq left odd) | `read()` → None (never torn); next `commit` advances past the dead sequence | automatic on next commit | `test_t6b_writer_crash_mid_update` |
| S7 | Corrupt ledger journal at attach | `AethelError` at `attach` — never truncated silently | restore journal from snapshot/backup | `test_t6d_corrupt_journal_fails_closed` |
| S8 | D10 seal ∉ {+1,−1} at commit | `commit()` → `None`; record dropped, slot untouched | fix the producer's seal field | `aethel selftest` seqlock check |
| S9 | Block digest mismatch, malformed/truncated journal, unsafe path, or storage bound exceeded | typed storage failure; replay/read exposes no payload | inspect and preserve the store; run explicit prefix recovery only after backup | `tests/test_aethel_fault_injection.py` |
| S10 | Snapshot interrupted before journal replace | prior journal remains authoritative; newly written orphan blocks are ignored | retry snapshot or restore a verified backup | `test_snapshot_crash_before_journal_publish_keeps_old_snapshot` |
| S11 | Queue closed, oversized slot count, ABI mismatch, or lock failure | typed error; no access beyond the mapped region | reopen a correctly sized, owned region and use cooperating Aethel clients | `tests/test_aethel_concurrency.py` |

## Encoding (E*)

| ID | Trigger | Symptom | Recovery | Test |
| --- | --- | --- | --- | --- |
| E1 | `len(payload) > max_fold_len` | `FoldDomainOverflow` — no silent truncation | shard the payload below `MAX_FOLD_LEN` | `test_b4_fold_domain_overflow_rejected` |
| E2 | Zeckendorf representation non-unique/adjacent | `ZeckendorfInvariantError` — declared unreachable; its appearance means corruption | treat as data corruption; re-fold from source | `test_b4_malformed_vector_rejected` |
| E3 | Binet/recursive index divergence | declared unreachable — would break `test_b3` on every run | none required; the test asserts it cannot happen | `test_b3_binet_matches_recursive_exact` |
| E4 | Punch-dispatched encode with host absent | NumPy path runs; `stage_evidence` records `"cpu"` | none — declared fallback, honestly labeled | `aethel.manifold.measure_throughput` |

## Handoff (H*)

| ID | Trigger | Symptom | Recovery | Test |
| --- | --- | --- | --- | --- |
| H1 | Engine rejects adapter-produced point (schema violation) | engine's own `ValueError`/`ArithmeticError` propagates — not swallowed | fix the mapping, not the engine | `test_aethel_geodesic_handoff.py` |
| H2 | `from_manifold` round-trip mismatch (key/position/index disagreement) | `HandoffRejection` | re-derive the point via `to_manifold` | `check_engine_invariants()` in selftest |
| H3 | `Intelligence.search_crystal` / `pathfinder` not importable | `EngineUnavailable` — the handoff is declared, never faked | install/restore the engine modules | `selftest` reports UNVERIFIED, not PASS |
| H4 | Pathfinder unavailable, non-convergent, or unable to resolve a stored payload | with `allow_fallback=True`, exact delegation to `query()` is recorded with a bounded reason; with false, `EngineUnavailable` | inspect `query_evidence`; disable fallback when policy requires the engine | `tests/test_aethel_fault_injection.py` |

## Non-goals (explicitly out of scope)

- Retrieval/search correctness is the geodesic engine's contract —
  `Intelligence.search_crystal` and `kellogg.traversal` own it; aethel
  inherits it through the adapter and never restates it.
- SHA-256 is an unkeyed integrity digest, not cryptographic authenticity.
- Multi-process queue safety applies only to writers/readers using the
  cooperating native or Python API and its advisory file lock; direct mmap
  mutations are unsupported. The seqlock itself is not lock-free.
- No unit test is a substitute for full-scale soak, target hardware parity,
  container, or deployment-filesystem evidence; see `capabilities.json`.
