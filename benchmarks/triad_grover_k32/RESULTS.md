# Triad Grover at k=32: offline benchmark on 500 verified mainnet headers

Script: `scripts/benchmarks/triad_grover_k32.py`. Each header goes through
`ProductionTriad.exact_grover_search` (`src/chronus/triad.py`), which uses the real
`OvidTransformService` and a SQLite WAL `DurableTheseusService` (`synchronous=FULL`).
The window is `[nonce - off, nonce - off + W)` with `off = sha256(header[:76])[:4] mod W`,
so the winner's position comes from the header only. Overfit windows start at `nonce + W`.
Runs use 8 worker processes, one SQLite file each. Box CPU: 8 vCPU, Python 3.13.5.
No network, no pool, no mining.

Counters are integers. Wall times are measured with `perf_counter_ns` and do not
affect any decision.

## Single-counter accounting (per header, mean over 500)

| | W = 4096 (N = 12) | W = 65536 (N = 16) |
|---|---|---|
| correct winner (nonce and block id) | 500 / 500 | 500 / 500 |
| fresh SHA-256d re-verification | 500 / 500 | 500 / 500 |
| marked states per window | exactly 1 (all 500) | exactly 1 (all 500) |
| Grover iterations (exact peak) | 50 | 201 |
| **Triad SHA-256d evaluations** (oracle hashes every state) | **4096** | **65536** |
| Triad SHA-256 compressions (2 per evaluation + 1 midstate + 3 confirm) | 8196 | 131076 |
| Linear scan evaluations to first hit (same oracle) | 2030.312 | 31537.896 |
| Linear compressions | 4064.624 | 63079.792 |
| Winner position in Lucas-Pisano order | 2037.726 | 32183.096 |
| Winner position in linear order | 2030.312 | 31537.896 |
| Headers where geodesic position < linear position | 243 / 500 | 249 / 500 |
| PR #168 standalone, distinct nonces hashed (same windows) | 2276.076 | 35021.496 |
| PR #168 standalone, lane compressions (rounds / 64) | 4346.533 | 66767.717 |

The oracle must evaluate every state in the window before any amplification
step, so the Triad path costs W SHA-256d evaluations per window. That is about 2x
the linear scan's expected cost (W/2 to first hit), and the same W in the overfit
windows. The scheduler leaves the expected winner position unchanged: it is a
permutation, and the mean position stays near W/2. PR #168's oracle is a
different implementation (bit-sliced, with cached rounds 0-2 and an H2 early abort),
so its compressions are not directly comparable with the hashlib midstate oracle.

## Wall time (ms per header, mean, under 8 parallel workers)

| | W = 4096 | W = 65536 |
|---|---|---|
| (a) pure two-amplitude Grover loop (exact Fractions, peak by stepping) | 1.608 | 28.725 |
| (b) full pipeline: stage + selective materialise + SHA-256d oracle + loop + N collapse commits + THESEUS receipts + fresh verify | 143.015 | 433.841 |
| linear scan to first hit (same oracle) | 3.113 | 50.220 |
| overfit window: full pipeline (no collapse commits) | 28.511 | 289.103 |
| overfit window: linear scan of the whole window | 6.193 | 100.465 |
| PR #168 standalone `unified_search` (pure-Python bit-sliced oracle) | 314.714 | 4258.194 |
| total wall, 500 headers (in + overfit + linear + restart pass) | 15.5 s | 61.6 s |

## THESEUS custody

| | W = 4096 | W = 65536 |
|---|---|---|
| shards persisted per header (stage + one per collapsed generator) | 13 | 17 |
| audit receipts per header | 14 | 18 |
| custodied frame bytes per header | 1846 | 2958 |
| reused shards (content-address hits) | 0 | 0 |
| journal continuity verified | 500 / 500 | 500 / 500 |
| restart: handles restored from a reopened SQLite file | 500 / 500 | 500 / 500 |

Sample `GROVER_TARGET_VERIFIED` receipts. Each journal entry hash was recomputed from
its journal row, the receipt body CRC-32C and SHA-256 were checked, and the tenant
chain was verified:

| W | height | nonce | journal entry hash | receipt body SHA-256 |
|---|---|---|---|---|
| 4096 | 976064 | 90468167 | b9038f266ebb89f84f3b5b594ff5632afe7dc8eb4c069c96ad3d2ccb9fa19d53 | 0cea830233894ae9ccea7e8ed879978dbbac95dea00ff96fb695048754822e14 |
| 4096 | 976063 | 1265527642 | 85b6f5d41e318a9de9ca6defe9b6b2d5db0dd84a7d1e2517c05a5216f09581c7 | 62b89992c7c21e95acf496b4fd9a6aa7e307387ccf261f8bfddd036964277f6c |
| 4096 | 976062 | 462700330 | 8652d616c0aeec9367b5d9164f947dcf0ec6fe9427d9cff9a134dcf0f7625574 | a0c6e5ad25b457369bdcd0434aeaa387ac42df9132ab504f771cd40720c8b7bd |
| 65536 | 976064 | 90468167 | 9c665ce9caeba3b918ce3ead411e16742282fba1a8a81590713fd7733afdab46 | 2b03f5a0c14ad313e31015fc31804966f7a6fc6ca67bd74227811833519a9d83 |
| 65536 | 976063 | 1265527642 | 17543fa3f64df08a565517a60bbf7235fe538f428673507d8927c318ce566e77 | 7168befbc4009e9ccdefd684b023ab517a6ff5978bf302f722189482aee8d325 |
| 65536 | 976062 | 462700330 | c19f931d8903e3af92d79c787c3a159360cb2a94d6b8acaa4700f4f8ee7deba2 | 85a31ae5fe80cc557e50d94285c95bbb468301d8a3b29148b417069a7483eebb |

Journal entry hashes include THESEUS's wall-clock `timestamp_ns`, so they differ
from run to run. Receipt bodies and their SHA-256 values are deterministic.

## Exactness checks

- Peaks: N=16, M=1 gives 3 iterations with P = 63001/65536, which equals sin²(7x) for
  sin x = 1/4 by the exact Chebyshev polynomial. N=4096 gives 50 and N=65536 gives 201.
- The `isqrt(N//M) + 2` step bound never cut the walk short for N = 2^D, D = 1..24,
  M in {1, 2, 3, 5}. At D=24, M=1 the peak is at 3216 with bound 4098.
- The two-amplitude state equals the full 2^D Fraction vector at every step for
  N in {4, 16, 64}.
- M_k has order exactly 2^(k-1) and det -1 for k in {8, 16, 32, 64}. The inverse
  is M_k - tr(M_k)·I.
