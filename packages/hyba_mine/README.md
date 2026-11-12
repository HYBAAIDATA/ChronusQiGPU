<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:9d78dcdfe62f28d1181094f003ac6ab36b6b12b3ec58ae0037c8f83f353980f9 -->

# HYBA Mine

HYBA Mine is HYBA's internal, private treasury mining runtime. It is not a product, not a service and never customer-facing. It consumes the Chronus platform; Chronus and the HYBA products never import it, and nothing in this package is wired into a customer surface.

For setting up a Mac, read [`docs/mine/MAC_QUICKSTART.md`](../../docs/mine/MAC_QUICKSTART.md).

## What it does

One runtime, one loop per work unit:

1. **Stratum V1** (`stratum.py`): `mining.subscribe`, `mining.authorize`, `mining.notify`, `mining.set_difficulty`, `mining.set_extranonce`, `mining.submit`, `client.reconnect`, `mining.ping`; plain TCP or `stratum+ssl` with certificate and host-name verification; reconnect with a doubling back-off across the pool's published endpoints (also after 300 s of pool silence, which catches a connection lost while the Mac slept; `client.reconnect` never redirects to an unlisted host); jobs bound to a connection generation and extranonce epoch, so `clean_jobs`, a reconnect or a new extranonce makes earlier jobs stale.
2. **Job to header** (`work.py`): `chronus.execution.stratum.build_header_prefix` builds the 76-byte prefix the device hashes.
3. **Canonical plan** (`plan.py`): PYTHIA itinerary of disjoint (extranonce2, position range) units, Hendrix traversal of the 256 lanes of each window in the F_257 generator order (`chronus.hendrix.GF257`), and the golden-stride bijection `nonce = offset + index * 0x9E3779B9 (mod 2^32)` from `chronus.execution.elevation`. Offset and lane rotation come from SHA-256 of the header prefix, so the order is job-bound and replays identically. Units are whole windows; the runtime doubles or halves a unit so it takes about half a second of device time, and each unit starts where the previous one ended.
4. **Backends** (`igpu.py`, `metal.py`, `bist.select_lane`): every run detects the Mac's backends and selects one from `--backend auto|igpu|metal|opencl|cuda|simd|reference` and `--prefer ours|host` (default `ours`). `ours` runs the Chronus iGPU (Mode A, HYBA's software-defined GPU, a first-class GPU route) even where the Mac has a GPU; `host` runs Metal on the Apple GPU when it passes its known-answer tests. A named backend runs exactly there or fails closed (`opencl`, `cuda`, `simd` and `reference` have no local lane). `requested_route`, `executed_route` and `fallback_reason` (`chronus.execution.elevation.Route`) plus `requested_backend`, `detected_backends`, `preference` and `executed_backend` are recorded in pre-flight, session and work records. `hyba-mine backends` shows the detection and the choice. The Metal kernel reuses the SHA-256 core of `chronus/kernels/sha256d_search.cl` and the host preprocessing of `OpenCLSha256dMinerBackend.build_kernel_args`.
5. **Result integrity**: a device result is accepted only if it covers the whole unit, its probe digest equals the host's SHA-256d of a plan-chosen candidate, and every hit lies on the plan. Otherwise the lane is faulty and mining stops.
6. **Host recheck before every submit**: `chronus.stratum.gatekeeper.LocalPreSubmitGatekeeper` rebuilds the header from the job fields through an independent code path and compares SHA-256d with the exact share target. Duplicates are dropped.
7. **Literal pool outcome**: the pool's reply is stored as received. Accepted means `result` is `true` and `error` is null; anything else is rejected; no reply means unacknowledged.
8. **Ledger** (`ledger.py`): append-only JSON lines with a SHA-256 hash chain: sessions, pre-flight, connections, difficulty, jobs, measured work, shares, pool replies, faults and pool switches.
9. **Measured hashrate** (`status.py`): executed candidates divided by device time from `work` records, plus the effective rate over the wall-clock time those records cover; "not measured" when there are none.

## Rules the code enforces

- Pools: ViaBTC, Braiins, NiceHash and ckpool only (`pools.py`); no profile asks a pool for a lower difficulty.
- The pool's acknowledgement is the only witness of a share.
- No job, no hashing. No stored login, no connection. No operator approval (`hyba-mine approve`), no mining. A pool that rejects the login is blocked until a new login is stored.
- Any failed pre-flight check blocks mining (`bist.py`): pool in catalogue and not blocked, approval, login present, ledger chain, plan invariants, known-answer tests on six real Bitcoin headers (mainnet blocks 0, 1, 2, 100000, 125552 and the regtest genesis), and a live Stratum handshake.
- Logins live in the macOS Keychain (service `HYBA-Mine`) or a 0600 file outside any git work tree. They never reach the ledger, the logs or the console; every log handler redacts registered login text as a backstop.

## Console

- `hyba-mine status` (or `--json`): route, measured hashrate, current job, shares submitted, accepted and rejected (pool replies only), uptime and pool, all computed from the ledger.
- Local page at `http://127.0.0.1:8765/` with the same values and a pool switch.
- `hyba-mine pool use <pool>` switches the pool of a running miner between work units.

## iGPU fleet

`dispatch.FleetDispatcher` uses the fleet's public API (`hyba-mine start --fleet on [--fleet-coordinator URL --fleet-token-file FILE --fleet-tls-ca CERT]`): `FleetExecutor.submit(chronus.fleet.WorkUnit) -> FleetResult`, whose ML-DSA-65 receipt the executor has already verified. The unit names HYBA Mine's kernel plugin, `hyba_mine.fleet_kernel` (`hyba_mine.nonce_window` v1), registered on every fleet machine with `CHRONUS_FLEET_KERNELS=hyba_mine.fleet_kernel`: payload = the 76-byte header prefix; params = target, plan parameters, lane table, position range and probe offset (no pool identity or login). The fleet holds no mining logic: it stripes the positions, verifies tiles against the plugin's reference and its pinned genesis known answer, and signs the receipt. The unit's route is the requested backend (`auto` lets each fleet machine's own selection decide, steered by `--prefer`). The result passes the same integrity checks as a local lane.

## Tests

```
PYTHONPATH=src:packages/hyba_mine/src python -m unittest discover -s packages/hyba_mine/tests -t packages/hyba_mine/tests
```

The suite runs a share-verifying in-process pool built on `chronus.execution.master_e2e_engine.LocalStratumTestServer` (the real block 0 coinbase fixture), plain and TLS.

Copyright (c) 2026 HYBA Software Ltd. All rights reserved.

## Reliability and recovery

TLS policy `prefer` uses only the published TLS endpoints when the pool has any.
A TLS failure does not silently downgrade the session. TCP-only profiles still
use their published TCP endpoints; `require` refuses those profiles and `off`
explicitly selects TCP.

Unanswered requests expire after 60 seconds and pending requests and pool pushes
are bounded. Each connection resets its difficulty; a rejection block belongs
to its pool and survives switching to another pool. State and control changes
use process locks and atomic private file replacement.

Ledger writers handle short writes. An unterminated fragment is preserved and
followed by a hash-bound `tail_recovery` record on the next append. A malformed
complete record fails verification. Recovery never truncates history.

Keychain writes send an encoded command through `security -i` standard input,
keeping login values out of process arguments. This interface has regression
coverage with a synthetic tool; native Keychain and launchd still require a Mac.
`hyba-mine autostart enable --no-start` writes the agent for the next login without
starting it immediately, and preserves `HYBA_MINE_VENV` in its environment.


<!-- /coderabbit-ai-generated:v1 -->