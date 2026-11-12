# Chronus iGPU fleet: many machines, one Chronus iGPU

Copyright (c) 2026 HYBA Software Ltd. All rights reserved. Chronus is a HYBA Data product.

**Status:** implemented and tested on one Linux host (Mode A routes, three worker processes, one killed mid-job). The Apple Metal and OpenCL routes are implemented but have not yet run on Apple or OpenCL GPU silicon; on each machine they must pass their known-answer self-test before they receive work. No throughput figure in this document is a measurement: real figures come from `chronus-fleet bench` and the receipts on your own machines.

## What it is

Chronus is HYBA's iGPU, a software-defined GPU. The fleet lets any set of machines act as **one Chronus iGPU**: Andre's MacBook and iMac, other laptops and servers. One machine runs the **coordinator**; every machine that lends silicon runs a **worker**. Callers submit a work unit through `FleetExecutor.submit()` or `chronus-fleet run` and receive one result and one signed receipt, as if a single device had done the work.

```
 caller ──submit──▶ coordinator ──leases──▶ worker (MacBook: Metal GPU)
   ▲                 │  lattice    ◀─results── worker (iMac: Metal GPU)
   │                 │  scheduler  ──leases──▶ worker (iMac: SIMD, Mode A)
   └──result+receipt─┤  verifier   ◀─results── worker (server: OpenCL GPU)
                     │  recovery
                     └─ ledger + ML-DSA-65 signer
```

A job goes through these steps:

1. **Stripe.** The work unit's kernel says how many independent items it holds. The resident scheduling lattice (`ResidentConfig`, 80, 800 or 8,000 virtual units) cuts the items into at most that many tiles, using the repository's existing `ResidentLogicalScheduler`.
2. **Lease.** Tiles are grouped and leased to workers in proportion to each worker's measured throughput (HERMES-style). Idle workers steal from the tails of other queues, nearest first on the H4 600-cell crossbar. Leases expire unless heartbeats renew them.
3. **Execute.** Each worker runs its tiles on the requested route, or with `auto` on its fastest self-tested route that can compute the tile exactly. Each tile returns a timed execution record.
4. **Verify.** Tiles are recomputed on the deterministic pure-Python reference on a secret sample, at least once per device per job, and whenever two results disagree.
5. **Recover.** If a worker dies, leaves, lets a lease expire or reports a failure, its unfinished tiles are re-run on survivors and checked blind (spec P2c).
6. **Receipt.** The merged result gets a receipt: SHA-256 digests, every device's measured contribution, the verification and recovery record, the backend record (requested, detected, preference, executed, reason) and the tier entitlement in force at admission. The receipt digest is anchored in the AL HARAS anchor ledger and the receipt is signed with ML-DSA-65.

## Capacity vocabulary

Four words are kept apart everywhere: in code, status output, receipts and here.

| Word | Meaning | Source |
|---|---|---|
| **Tier** | A commercial tier: the provisioned entitlement in force (Tier 1: 1,024 logical warps). Provisioning, never a performance claim. Demand beyond it can scale under a signed grant. | `chronus.fleet.phase`, `chronus.fleet.scale` |
| **Backend** | Where a tile runs, chosen by the operator: `igpu` (the Chronus iGPU, ours), `metal` / `opencl` / `cuda` (the host GPU), `simd` / `reference` (single Chronus engines). | `chronus.fleet.backends` |
| **Discovered** | What a probe found: a route is present, with the device as the driver reports it. `measured: false`. | `DeviceAdapter.probe()` |
| **Verified** | The route reproduced every applicable known answer, hash for hash, whole and split into tiles. | `DeviceAdapter.self_test()` |
| **Measured** | Throughput from timed runs on that machine, with start and finish timestamps. | `DeviceAdapter.measure()`, execution records |

## The honesty rules, and where they are enforced

| Rule (manifesto) | Enforcement |
|---|---|
| Never claim physical cores for logical rungs | Virtual units are labelled "scheduling lattice: logical virtual units, not physical cores" in the lattice, the status and every receipt (`physical_cores_claimed: 0`). Warps and lanes are logical units in every tier entitlement. |
| `measured` stays false until silicon registers | Probe records carry `measured: false`. Only timed runs (`measure()`, execution records) carry `measured: true`, and each has timestamps. Scheduling weights come only from those runs; a machine with no measurement weighs 1 and is shown as unmeasured. |
| Never emulate silently | A requested route that is absent, or whose self-test failed, raises `DeviceUnavailableError`. The coordinator refuses a job naming a route no live node has verified ("failing closed"), and refuses any result whose `executed_route` differs from an explicitly requested route. A route's silicon is fixed (`metal` and `opencl` are GPU; `reference`, `simd` and `cpp-simd` are CPU), so CPU work cannot be reported as GPU work. MLX is refused unless Metal is available to it, and CPU OpenCL devices are never used for the OpenCL route. |
| Receipts for everything | Every job ends with a signed, ledger-anchored receipt. Incidents, fabric snapshots, tier changes, scale events and scale grants are anchored in the ledger too. |

Mode A is the Chronus iGPU, HYBA's software-defined GPU on the resident lattice (`igpu`, with its engines `cpp-simd`, `simd` and `reference`): a first-class GPU route. Mode B is the host's own GPU (`metal`, `opencl`, `cuda`). Each record names its mode, its backend and the physical silicon under it.

## Backends: detected, then chosen by option

Every run detects the backends the machine offers (probe, then the known-answer self-test) and selects one from an explicit option:

| Option | Meaning |
|---|---|
| `--backend auto` (default) | detect, then choose by `--prefer` |
| `--backend igpu\|metal\|opencl\|cuda\|simd\|reference` | exactly that backend; absent or failing its self-test means fail closed |
| `--prefer ours` (default) | the Chronus iGPU, even when the host has its own GPU |
| `--prefer host` | the host GPU (Metal, OpenCL or CUDA) when present and self-tested; otherwise the Chronus iGPU, with the reason recorded |

The option drives the choice; measured throughput never reorders it. `chronus-fleet join`, `bench` and `run` take both options; a work unit may carry `prefer` to steer `auto` on every worker, otherwise each worker's own `--prefer` applies. Every tile record, receipt and receipt ledger anchor carries `requested_backend`, `detected_backends`, `preference`, `executed_backend` and `fallback_reason`, and each join is anchored with the machine's selection. `cuda` is a probe of `cupy` or `numba.cuda` (only when importable); no kernel has a CUDA implementation yet, so it fails closed.

## Routes

| Route | Silicon / mode | Present when | Built-in kernels |
|---|---|---|---|
| `reference` | CPU / A | always (pure Python, exact integers) | all |
| `simd` | CPU / A | NumPy importable (vector units: AVX2, NEON) | all |
| `cpp-simd` | CPU / A | `libchronus_igpu` built and found (`CHRONUS_NATIVE_LIB_PATH`) | `m15_fold`, `m15_unfold`, `dual_space_query` |
| `metal` | GPU / B | macOS, with MLX (Apple Silicon) or PyObjC Metal | MLX: `m15_*`, `dual_space_query`, `gf_matvec` (p ≤ 2^16); PyObjC: `m15_*` |
| `opencl` | GPU / B | pyopencl and an OpenCL GPU device | `m15_*` (packaged `m15_fold.cl`, digest-pinned), `pv_lattice_fold` (existing `opencl_pv` backend) |

Built-in kernels reuse existing Chronus code:

- `m15_fold` / `m15_unfold`: the M15 matrix from `chronus.execution.native_simd`.
- `dual_space_query`: q^T x on folded data without unfolding it.
- `gf_matvec`: exact F_p arithmetic with the reference from `chronus.hendrix.PrimeField`.
- `pv_lattice_fold`: Z[φ] scaling from `chronus.backends.lattice`.

A kernel that a route cannot compute exactly (for example an int64 overflow on `simd`) is declined for that tile. With `auto`, the next verified route runs it and the record gives the reason; with an explicit route, the tile fails closed.

## Tiers with the option to scale

The spec's four phases are commercial tiers. Each carries a provisioned entitlement; entitlements are provisioning, never performance claims.

| Tier | Entitlement (logical warps × 32 lanes) | Storage entitlement | Connectors needed |
|---|---|---|---|
| Tier 1 | 1,024 (32,768 lanes) | 100 TB | `fleet-http` |
| Tier 2 | 10,000 (320,000 lanes) | 1,000 TB | `fleet-http`, `fleet-tls` |
| Tier 3 | 40,000 (1,280,000 lanes) | 10,000 TB | `fleet-http`, `fleet-tls` |
| Tier 4 | 160,000 (5,120,000 lanes) | 100,000 TB | `fleet-http`, `fleet-tls` |
| Scale | set per contract: an explicit figure, at least Tier 4's | set per contract | `fleet-http`, `fleet-tls` |

Demand is checked on every join, every job and every 2-second fabric tick. A machine joining at 8,000 virtual units occupies 250 logical warps, so at Tier 1 four machines use 1,000 of the 1,024. When demand goes beyond the current tier's entitlement, the fleet:

1. records a scale event (demand, entitlement, next tier, timestamp) and anchors it in the ledger;
2. admits the work if a valid scale grant authorises a tier that covers it, moving to the lowest such tier;
3. otherwise queues it and reports `scale available: Tier N+1`. A fifth Mac joins and waits (heartbeating, no leases) rather than being turned away; a job stays `queued`. Both are admitted the moment a grant covers them.

A **scale grant** is the coordinator owner's ML-DSA-65 signature (the same v36 signer and key as the receipts) over a tier or a Scale contract figure, and an expiry. Grants from any other key, for another fleet, altered after signing or expired are rejected. When a grant expires the fleet moves down to the highest tier still authorised and the newest machines wait. <!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:bcaaaaf3e87d8b2a9e0fdb35cdce8e8afa981c89cd069f9d6d835ec72ed73efe -->

**Downgrade** is always possible: `tier set` to a lower tier retires grants above it and moves the newest machines back to the queue. The signed selection caps the original authorization at the lower tier through its existing expiry. Retired upper-tier authority cannot be reused to scale back up. A new valid Scale contract can increase an existing Scale fleet when it covers demand.

<!-- /coderabbit-ai-generated:v1 -->

```bash
chronus-fleet tier status --coordinator https://<imac>.local:8740 --tls-ca ...   # tier, entitlement, demand, scale available
chronus-fleet tier grant --tier 2 --expires 30d                                   # owner, on the coordinator
chronus-fleet tier set --tier 2                                                   # owner, on the coordinator: move now
chronus-fleet tier set --tier 1                                                   # owner: downgrade
chronus-fleet tier grant --tier scale --warps 500000 --storage-tb 250000 --contract <ref> --expires 365d
```

`tier grant` and `tier set` sign a document into `~/.chronus/fleet/tier/`; the running coordinator applies it within one fabric tick. Tier 2 and above need TLS (`coordinator --tls`). Decisions on the spec's placeholders are in [DECISIONS.md](DECISIONS.md).

## Verification and blind-check recovery

- **Same-hash checks.** A secret HMAC sample (default 1 in 8) of tiles, plus at least one tile per device per job, is recomputed on the reference. Workers cannot tell which tiles will be checked. On a mismatch the reference output replaces the device's, the device is quarantined, and every other tile it produced in the job is recomputed.
- **Blind check (P2c).** When a worker fails, channel A rebuilds its unfinished work on survivors from the faulted state alone and commits to the outputs. Only then does channel B draw a random verification set and check it on the reference. Channel A never sees that set. The receipt records the incident, the recovery path, the commitment, the size and digest of the verification set, and whether recovery took one cycle.

## Security

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:a30a6d37348552169794dcfc8d5df700ffa5acc6f994677606ec58ba1b420360 -->

- **Shared fleet token.** At least 32 characters; 256-bit by default from `chronus-fleet init`. It is stored in `~/.chronus/fleet/token` with mode 600 and is never sent over the network. It authenticates onboarding and client submissions. Each worker receives its own random credential during authenticated join; heartbeats, leases, results and leave calls require that credential. The shared token cannot impersonate a joined worker. Coordinators and workers must be upgraded together and workers must rejoin after coordinator restart. Node credentials stay in memory and are absent from status, receipts and logs.

<!-- /coderabbit-ai-generated:v1 -->
- **Mutual HMAC-SHA256.** Every request is MACed (method, path, node, timestamp, nonce, body digest), and every response is MACed over the request's nonce. The coordinator rejects replays and clock skew beyond 5 minutes. A worker rejects a coordinator that cannot MAC its answers.
<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:9927a0cf6cac287ee02dfd578d5216afc6377142fa61b134756cbf0c8c4aae7d -->

- **TLS.** Required whenever clients or coordinators use a non-loopback address, at every tier. `init --tls-host` creates a self-signed certificate; workers pin it with `--tls-ca`. Plain HTTP is limited to loopback testing. Tier 2 and above retain their TLS connector requirement.

<!-- /coderabbit-ai-generated:v1 -->
- **Receipt signing.** ML-DSA-65 through the existing v36 `MLDSASigner` (pyca/cryptography, OpenSSL). One key per fleet, stored as a seed with mode 600. There is no KMS or HSM custody.
- **Kernels.** Workers run only kernels registered on their own machine; the coordinator cannot send code.

## Running it

Andre's Macs: follow [MAC_SETUP.md](MAC_SETUP.md) command by command. In short:

```bash
chronus-fleet init --tls-host "$(scutil --get LocalHostName).local"          # iMac, once
chronus-fleet coordinator --host 0.0.0.0 --port 8740 --tls                    # iMac
chronus-fleet join --coordinator https://<imac>.local:8740 \
    --tls-ca ~/.chronus/fleet/tls/coordinator-cert.pem                        # each Mac: Chronus iGPU (default)
chronus-fleet join ... --prefer host                                          # or: the Mac's GPU (Metal)
chronus-fleet status --coordinator https://<imac>.local:8740 --tls-ca ...     # anywhere
chronus-fleet bench                                                           # any machine
chronus-fleet run --coordinator https://<imac>.local:8740 --tls-ca ... --kernel m15_fold --size 16MiB
```

On one machine, without a network:

```python
from chronus.fleet import FleetExecutor, WorkUnit

with FleetExecutor.embedded("~/.chronus/fleet-local", local_workers=2) as fleet:
    result = fleet.submit(WorkUnit(kernel="m15_fold", payload=bytes(range(256)) * 64))
    print(result.receipt["devices"])
```

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:a8f0c7bf9b4d39c15a8e595d57a40c6256209c914f5a711a27b1059e1f871469 -->

## Shutdown and transport budgets

Shutdown stops admission and marks unfinished jobs failed, signaling waiters
before transport and verification stop. Replay capacity fails closed rather
than evicting still-valid nonces. HTTP connections have a 15-second absolute
deadline, including TLS and request parsing, and at most 64 active handlers.
Client response bodies are limited to 64 MiB by default; direct API callers can
set a different positive `max_response_bytes`. Existing request-body limits
still apply. A ledger append failure makes that writer unusable until reopened
and verified, preventing cached sequence reuse after failed durability.

## Python API

<!-- /coderabbit-ai-generated:v1 --> for other HYBA systems

`FleetExecutor.submit(work_unit)` returns `FleetResult(output, receipt, check)`. It returns only after the receipt has been verified against the coordinator key pinned at connection, the result bytes against the signed digest and the work unit against its digest. The fleet holds no domain logic. A system such as HYBA Mine supplies its own kernel (a subclass of `chronus.fleet.Kernel` with an exact `run_reference`, optional `run_simd` or `run_metal`, a `merge` and known answers), installs it on every machine, and names its module in `CHRONUS_FLEET_KERNELS`:

```python
# on every machine: export CHRONUS_FLEET_KERNELS=hyba_mine.fleet_kernels
from chronus.fleet import FleetExecutor, WorkUnit

fleet = FleetExecutor("https://<imac>.local:8740", token_file="~/.chronus/fleet/token",
                      tls_ca="~/.chronus/fleet/tls/coordinator-cert.pem", name="hyba-mine")
result = fleet.submit(WorkUnit(kernel="<kernel registered by the caller>", payload=data, params=params))
```

The fleet stripes the kernel's items across machines, so a caller's index range (a search window, for example) is split, run, verified and merged without the fleet knowing what it is.

## Files

| Path | Purpose |
|---|---|
| `src/chronus/fleet/adapters.py`, `metal.py`, `opencl.py` | device adapters: probe, self-test, execute, measure |
| `src/chronus/fleet/kernels.py` | kernel contract, built-in kernels, known answers, plugin registry |
| `src/chronus/fleet/lattice.py` | resident scheduling lattice (80 / 800 / 8,000) |
| `src/chronus/fleet/phase.py` | tiers and their entitlements, the Scale tier, `TIER_GATE` (the spec's `PHASE_GATE`) |
| `src/chronus/fleet/scale.py` | signed scale grants, tier selections and scale events |
| `src/chronus/fleet/backends.py` | backend detection and selection (`--backend`, `--prefer`) |
| `src/chronus/fleet/cuda.py` | CUDA probe (fails closed; no CUDA kernels yet) |
| `src/chronus/fleet/scheduler.py`, `crossbar.py` | leases, stealing, pools; H4 crossbar (P2) |
| `src/chronus/fleet/verification.py`, `recovery.py` | same-hash checks; blind-check recovery (P2a–P2c) |
| `src/chronus/fleet/ledger.py`, `signing.py`, `receipts.py` | AL HARAS anchor ledger (P10); ML-DSA-65; receipts |
| `src/chronus/fleet/auth.py`, `transport.py` | token, mutual HMAC, TLS; HTTP server and client |
| `src/chronus/fleet/coordinator.py`, `worker.py`, `executor.py`, `cli.py` | the fleet itself, the API and `chronus-fleet` |
| `src/chronus/fleet/value_share.py` | P7a/P7b/P11 value-share reconciliation (Tier 4 and Scale) |
| `src/chronus/kernels/m15_fold.cl` | OpenCL M15 pair kernel |
| `tests/test_fleet_*.py` | unit, fail-closed, tier and scale, backend selection, embedded and multi-process tests |

Run the tests with `python -m pytest -q tests/test_fleet_*.py`, or `python -m unittest discover -s tests -t . -p "test_fleet*.py"`.

## What is not claimed

- No figure here is a benchmark. Throughput appears only in `bench` output and receipts, for the machine and moment they record.
- The Metal (MLX, PyObjC) and OpenCL routes have not yet run on Apple or OpenCL GPU silicon. The MLX kernels' integer arithmetic was checked under 32-bit semantics with a NumPy stand-in for `mlx.core`, not on a GPU.
- The ledger is a local, tamper-evident hash chain. It is not replicated, not distributed and not a blockchain.
- The fleet does not provide KMS or HSM key custody, multi-tenant isolation, or an SLA.
- Fleet transfers go over HTTP(S) on your network. Within one machine, MLX and Metal use unified memory; across machines, each tile's bytes are sent once.
