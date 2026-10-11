# ASIC-like mining execution — additive v3.8

## Scope

The supplied completed exact core is retained. This enhancement adds prepared-job execution, fused ordered nonce scans, bounded parallel lanes, epoch cancellation, durable progress, configured-driver binding and retry-safe service calls beneath ONE iGPU.

The delivered native engine executes on CPU. It is ASIC-like in structure: prepare shared work once, stream nonces through a specialized datapath, compare the exact target in the datapath and return compact candidates. No physical ASIC is manufactured, discovered or benchmarked by this release.

## Exact prepared-work mathematics

An 80-byte Bitcoin header requires two SHA-256 compression blocks for its first hash; the 32-byte digest requires one block for the second hash. Within a fixed first 64-byte header block:

```text
midstate = Compress(SHA256_IV, header[0:64])
first_hash(nonce) = Compress(midstate, Pad(header[64:76] || LE32(nonce), 80 bytes))
SHA256d(nonce) = Compress(SHA256_IV, Pad(first_hash(nonce), 32 bytes))
```

Prepare the first block once. Each subsequent nonce executes two compression blocks rather than recomputing all three. For N candidates the prepared path executes `1+2N` blocks, compared with `3N` for an unprepared path. This is work reuse, not a change in SHA-256 or an inferred nonce-probability multiplier.

The exact prefix includes merkle tail, ntime and nBits. Tail/time rolling with an identical first block reuses the midstate and rebinds the tail. A version/extranonce/merkle change affecting the first block causes a new preparation. Target/job/epoch identity is sealed independently of the cache key; changing the target never bypasses identity or freshness checks.

## Implementation

- `native/sha256d_native.c`: bounded immutable prepared contexts; portable C and explicitly selected OpenSSL CPU backends; GIL released during actual hash batches; compact range and ordered-array scans.
- `asic_mining.PreparedSHA256d`: LRU first-block cache, prefix rebinding, exact native/hashlib-copy execution and declared backend identity.
- `fabric`: operation-specific mining adapter, fused ordered scans, exact actual completion count, complete negative-result validation and independent host candidate checking.
- `MiningJob` / `JobEpochLedger`: immutable prefix/target/id/epoch commitments; strict newer-epoch replacement; revoked epochs cannot re-enter the same ledger.
- `MiningFarm`: weighted disjoint lanes, interleaved bounded batches, bounded inflight queue, finish/count already dispatched work, live stale-job rejection, cancellation/deadline checks and contiguous progress cursor. Maximum 4096 batch receipts prevents output explosion.
- `checkpoint_mining` / `restore_mining`: validated receipt persistence through existing PRIME-DB, surviving close/reopen. Cursor and all completed batch spans are retained; a cursor alone is not permission to discard completed out-of-order spans.
- `ASICDriverBridge`: explicit executable driver registration, declared identity and full-digest host validation. No fabricated hardware enumeration. Candidate-only proprietary ASIC protocols are not silently treated as this full-digest interface.
- `virtual_igpu_v1` `asic_sha256d`: bounded job/lease/lane/batch workload, existing admission and custody envelope.
- `VirtualRuntime.execute_once`: tenant/workload-ID keyed session idempotency, sealed input snapshot, concurrent duplicate coalescing, conflicting input rejection, immutable cached receipts and no automatic retry after partial failure. Cache limits are explicit; restart/global exactly-once execution is not claimed.

## Main path preserves intelligence

```python
from chronos import OneIGPU
from chronos.golden_quantum import NonceLease

with OneIGPU() as gpu:
    gpu.configure_asic_like(require_native=True)
    result = gpu.mine(prefix_76_bytes, exact_target, NonceLease(start, stop, job_id, epoch),
                      max_evaluations=4096, current_epoch=epoch)
```

The existing S1–S6 solve-first planner still runs. Its bounded candidate order enters the native fused scanner; F3 covers the remaining owned domain within budget. Integer/fold/neural advice does not mutate target, job identity or ownership. Returned successes pass fabric host verification and the existing final host-verification boundary. Independent verification hashes are counted separately.

## Parallel lane path

```python
from chronos import OneIGPU
from chronos.igpu import MiningJob, MiningFarm
from chronos.golden_quantum import NonceLease

job = MiningJob(prefix_76_bytes, exact_target, job_id, epoch)
farm = MiningFarm(lanes=4, batch_size=1024, max_inflight=8)
farm.ledger.activate(job)
with OneIGPU(db_path='prime.db') as gpu:
    result = gpu.mine_asic(job, NonceLease(start, stop, job_id, epoch), farm=farm,
                           max_evaluations=65536)
    checkpoint = gpu.checkpoint_mining(result)
```

The farm is an execution/scheduling API. It does not by itself run all S1–S6 planner stages; use `configure_asic_like` + `gpu.mine` for the integrated solve-first path. Physical lane count, configured CPU lanes and measured concurrent work are separate. Linear scaling is not assumed.

## Build and publication

```bash
# Portable C native build when a C compiler/Python headers are installed:
python -m pip install .
# Explicit optimized OpenSSL build (tested Linux; headers/libcrypto required):
CHRONOS_USE_OPENSSL=1 python -m pip install .
# Universal pure Python/hashlib-copy installation:
CHRONOS_DISABLE_NATIVE=1 python -m pip install .
```

The universal wheel requires no compiler and reports `hashlib_copy_midstate`. The supplied native wheel is the tested CPython 3.13 Linux x86-64 build, dynamically linked to system libcrypto.so.3; it is not a manylinux/macOS/Windows hardware qualification. Build from source on the target for native support; requiring native execution fails closed when it is unavailable.

```bash
chronos-igpu-service --host 127.0.0.1 --mining-backend prepared --db-path ./state/prime.db
```

Supply the private service token externally. `--mining-backend native` requires the extension. Docker files build native code in a separate stage and install the runtime crypto library. Docker image deployment was not executed on the release host.

## Measured adjacency, not inferred dominance

The benchmark uses the real Bitcoin genesis header, exact known digest, fixed nonce windows and a zero-target negative control. Thirty repeated batches of 4096 candidates per path are measured on one CPU host, with randomized path order. The whole-pipeline comparison keeps S1–S6, the same owned candidate domain and the same budget.

| Whole solve-first path | Executed SHA256d | Aggregate SHA256d/s |
|---|---:|---:|
| Existing reference path | 122,880 | 411,369 |
| Prepared native OpenSSL path | 122,880 | 1,415,293 |

Measured whole-pipeline ratio: **3.44×**. The compact scan kernel alone measured **13.76×** its matching Python scan baseline; this is not substituted for whole-miner throughput.

Adjacency checks cover first-block reuse across tail/time changes, invalidation when the first block changes, compact result movement, bounded lane scheduling, retry coalescing, stale-job cancellation and persistent progress. Lane results have one observation per lane count; no scaling law is inferred. The benchmark is repeated warm-work execution, not a claim across independent jobs, power budgets, pools, competitors or physical ASICs.

Evidence: `benchmarks/asic-adjacency-results.json`, `benchmarks/asic-adjacency-portable-c.json`, `validation/v3.8-junit.xml`, release report and independent CSV/Decimal reconciliation. Prior portable-C results are retained separately rather than overwritten as OpenSSL results.

## Public technique-to-code ledger

| Public source | Technique used | Actual implementation boundary |
|---|---|---|
| NIST FIPS 180-4 | Exact padding/compression/state continuation | Prepared SHA256d C and independent hashlib checks |
| NVIDIA CUDA best practices | Bounded asynchronous work and explicit completion | Portable lane/future scheduling; not a CUDA driver or pinned-transfer claim |
| OpenXLA fusion documentation | Avoid unnecessary intermediate materialisation | Native fused hash+target comparison; no XLA compiler dependency or ownership claim |
| AWS Builders Library | Idempotent retry identity | Session-bounded sealed request coalescing; not global exactly-once delivery |
| Microsoft Retry pattern | Avoid re-executing non-idempotent partial work | Failed request identity retained; explicit reconciliation/new request required |
| Apple MLX/Core ML | Explicit materialisation and declared execution policy | Existing v3.7 optional tensor/neural bindings retained; not a SHA256d Neural Engine claim |

Source URLs are in `PUBLIC_TECHNIQUES.json`. These are specific reviewed techniques, not an assertion that every research result or private design of the named organizations is included.
