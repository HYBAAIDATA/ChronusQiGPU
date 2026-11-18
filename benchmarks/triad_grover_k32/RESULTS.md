# Triad Grover at k=32: offline benchmark on 500 verified mainnet headers

## Provenance

| | |
|---|---|
| measured source | `3b4a8db506fd32a31c7f85f2e7cd7dca5db22144` (branch `feat/grok-triad-grover`) |
| input | `tests/vectors/mainnet_975565_976064.json` at `0ef3443a` (branch `data/mainnet-headers-975565-976064`), sha256 `3db2d4a97543f8ae786691a193eff8cf6b7e5922208beff05340c3f08413cc76`, heights 975565-976064 |
| raw per-header outputs | `raw_w4096.json`, `raw_w65536.json` in this folder (each records the SHA-256 of the full script output) |
| qualification record | `PRODUCTION/evidence/triad_grover_qualification.json` |
| command | `python scripts/benchmarks/triad_grover_k32.py --headers tests/vectors/mainnet_975565_976064.json --window-bits {12,16} --workers 8 --state <dir> --out <file>` |
| host | 8 vCPU box, CPython 3.13, fresh venv with `pip install -e '.[dev]'`; local run, not hosted CI |

These are local measurements. They are not attested, and they make no production or
hardware claim.

Script: `scripts/benchmarks/triad_grover_k32.py`. Each header goes through
`ProductionTriad.exact_grover_search` (`src/chronus/triad.py`). That path uses the real
`OvidTransformService` and a SQLite WAL `DurableTheseusService` (`synchronous=FULL`).
The target is decoded from the header's own nBits. The window is
`[nonce - off, nonce - off + W)` with `off = sha256(header[:76])[:4] mod W`, so the
header alone fixes where the winner sits. Overfit windows start at `nonce + W`. Each of
the 8 worker processes has its own SQLite file. No network, no pool, no mining.

All counters are integers. Wall times come from `perf_counter_ns` and are recorded
only; no decision depends on them.

## Single-counter accounting (per header, mean over 500)

| | W = 4096 (N = 12) | W = 65536 (N = 16) |
|---|---|---|
| correct winner (nonce and block id) | 500 / 500 | 500 / 500 |
| fresh SHA-256d re-verification (before any custody write) | 500 / 500 | 500 / 500 |
| Grover iterations (exact peak) | 50 | 201 |
| **Triad SHA-256d evaluations** (oracle hashes every state) | **4096** | **65536** |
| Triad SHA-256 compressions (2 per evaluation + 1 midstate + 3 confirm) | 8196 | 131076 |
| Linear scan evaluations to first hit (same oracle) | 2030.312 | 31537.896 |
| Linear compressions | 4064.624 | 63079.792 |
| Winner position in Lucas-Pisano order | 2037.726 | 32183.096 |
| Winner position in linear order | 2030.312 | 31537.896 |
| Headers where geodesic position < linear position | 243 / 500 | 249 / 500 |
| overfit windows with a winner found | 0 / 500 | 0 / 500 |

The oracle has to evaluate every state in the window before any amplification
step, so the Triad path costs W SHA-256d evaluations per window. That is about twice
the linear scan's expected cost (W/2 to the first hit), and the overfit windows cost
the same W. The scheduler does not move the expected winner position: it is a
permutation, so the mean position stays near W/2.

## Wall time (ms per header, mean, under 8 parallel workers)

| | W = 4096 | W = 65536 |
|---|---|---|
| (a) pure two-amplitude Grover loop (exact Fractions, peak by stepping) | 1.614 | 26.570 |
| (b) full pipeline: stage + selective materialise + SHA-256d oracle + loop + fresh verify + N collapse commits + THESEUS receipts | 150.465 | 412.540 |
| linear scan to first hit (same oracle) | 3.035 | 45.810 |
| overfit window: full pipeline (no collapse commits) | 49.786 | 288.590 |
| overfit window: linear scan of the whole window | 6.084 | 93.321 |
| total wall, 500 headers (in + overfit + linear + restart pass), s | 17.1 | 59.1 |

## THESEUS custody

| | W = 4096 | W = 65536 |
|---|---|---|
| shards persisted per header (stage + one per collapsed generator) | 13 | 17 |
| audit receipts per header | 14 | 18 |
| custodied frame bytes per header | 1846.000 | 2958.000 |
| tenant journals recomputed from SQLite (hash chain) | 500/500 | 500/500 |
| GROVER_TARGET_VERIFIED receipts present in their chain | 500/500 | 500/500 |
| receipt bodies passing the CRC-32C + SHA-256 attestation check | 500/500 | 500/500 |
| restart: handles restored from a reopened SQLite file | 500 / 500 | 500 / 500 |

Sample `GROVER_TARGET_VERIFIED` receipts (receipt schema `chronus.triad-grover-receipt/2`,
probability encoded as `hex-fraction/1`):

| W | height | nonce | journal entry hash | receipt body SHA-256 |
|---|---|---|---|---|
| 4096 | 976064 | 90468167 | 57aaa298608e6c33aca94e022336d830b8626734aeadff54f69f89e929369653 | 2554c8f4070ff8658ea73120d543ce7ddb8cd40c10496353dcbc8e6b9fde8102 |
| 4096 | 976063 | 1265527642 | f401c0a7cf938b542c08b96b88d6107063e1142547bcda58d3bf5a3f74175edd | e5e5e5575b911d4c46a0bcb0fc82262da70aac061dbc497a79757b0c57b2552b |
| 4096 | 976062 | 462700330 | bf4a4d22273e93dc9dd5da6a4e72ad91072a333f2a538edf3267d02a1b57eb5c | ccf9b4bf5e972684bf1e9c6af6de0dc7dd94447780b027c3ad0aa92e2d2dae27 |
| 65536 | 976064 | 90468167 | 0ddbfa009b25a0170787eb39f80db2e6b16a6e75739526159bc1e08bdbabaf00 | 1ae95f4ef0bd87a9b99b21e864053e8e252c171ecdbb0991fc8f64c0ce381746 |
| 65536 | 976063 | 1265527642 | ba6d55856fe369b51840d5b6ccaa295d195d99a48b6d131785a681dca7cc2bec | 55833e119258fe994a521595592148386f3dc07c15cc6407ecd5d6a349207bee |
| 65536 | 976062 | 462700330 | 252878e0100034dd5cf4d4ffcd82cb5e624d1ff3e47dc97437c9da8c559f011b | 786587a6179305a270e245f0c9678e936b7c7d03318c06e7ed013ad4ccf25b82 |

Journal entry hashes include THESEUS's wall-clock `timestamp_ns`, so they change on every
run. Receipt bodies and their SHA-256 values are deterministic for a given source commit.

## Exactness checks

- Peaks: N=16, M=1 peaks at 3 iterations with P = 63001/65536, which equals sin²(7x)
  for sin x = 1/4 by the exact Chebyshev polynomial. N=4096 peaks at 50 and N=65536 at 201.
- The `isqrt(N//M) + 2` step bound never cut the walk short for N = 2^D, D = 1..24,
  M in {1, 2, 3, 5}. At D=19, M=1 the peak is at 568, and its probability denominator
  2^19331 exceeds Python's 4300-digit decimal limit. That is why receipts use hex.
- The two-amplitude state equals the full 2^D Fraction vector at every step for
  N in {4, 16, 64}.
- M_k has order exactly 2^(k-1) and det -1 for k in {8, 16, 32, 64}. The inverse is
  M_k - tr(M_k)·I.
