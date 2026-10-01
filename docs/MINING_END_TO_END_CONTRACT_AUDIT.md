# Mining workflow end-to-end contract audit

Audit baseline: `main` at `995354dcc81a73e86e279277f583207901ce9be8`.

Scope: the canonical production path from configuration and process startup
through Stratum V1 negotiation, work identity, nonce leasing, CPU/OpenCL
execution, independent proof checking, submission, persistence, failover,
shutdown, and CI. Legacy/research miners were checked only to confirm that
they are not the canonical entry point.

## Outcome

No path was found that can turn QOps, geometry, a Lucas label, a Cassini seal,
or accelerator telemetry into an accepted share. A share still requires:

1. a pool-issued job and subscription;
2. a negotiated share target;
3. a complete 80-byte Bitcoin header;
4. an executed double-SHA-256 digest;
5. an independent host-side target recheck; and
6. a literal pool `mining.submit` acceptance.

The review found six concrete contract defects. This change fixes all six and
adds regression coverage.

## Contract graph

| Stage | Canonical implementation | Contract | Audit result |
|---|---|---|---|
| Entry point | `chronus/mla1517_platform/python/main.py`, `mining_runtime.py` | one canonical runtime; cooperative SIGINT/SIGTERM shutdown | Pass |
| Configuration | `startup_contract.py`, `runtime_config.py`, `pool_catalog.py`, `mining_runtime.pool_endpoints` | enabled pools only; per-pool identity; allowlisted endpoints | Fixed: disabled pools were still dialed |
| Connection | `production_transport.py`, `manifold_pool_coordinator.StratumClient` | bounded connect/write/request queues and failover | Fixed: request timeout could terminate the worker instead of reconnecting |
| Subscription | `StratumProofAdapter` | validated extranonce1 and extranonce2 width | Pass |
| Authorization | `StratumClient.connect` | literal boolean authorization; per-pool credentials | Pass |
| Target transition | `StratumProofAdapter.handle_message` | `set_difficulty` applies to the next job | Fixed: active jobs were being retroactively retargeted |
| Extranonce transition | `StratumProofAdapter.handle_message` | changed extranonce invalidates templates built under the old subscription | Fixed |
| Job lifecycle | `StratumProofAdapter`, `StratumRuntimeState` | `clean_jobs=True` invalidates old work; `False` retains it | Fixed: non-clean prior jobs were stored but unusable |
| Header assembly | `stratum_adapter.py` | exact coinbase, branch order, word-swapped prevhash, little-endian fields | Pass |
| Work identity | `coordinator.WorkIdentity` | session, generation, fingerprint, target generation and lease must agree | Pass |
| Nonce allocation | `nonce_lease.py`, `search_plan.py`, dispatch certificate | non-overlapping bounded leases and sealed deterministic order | Pass |
| CPU/OpenCL execution | `execution_router.py`, `bitcoin_hasher.py`, `hash_pipeline.py` | actual hashes only; explicit backend; CPU fallback labelled | Pass with hardware evidence still required |
| Proof boundary | `hash_pipeline.py`, `stratum_adapter.py`, `pow.py` | independent SHA-256d and target recheck | Fixed: two boundary checks used removable Python `assert` statements |
| Stale work | coordinator identity recheck | changed session/job/target work is never submitted | Pass |
| Submission | coordinator submission lock and `MiningSession` | durable-before-write, serialized submit, boolean verdict | Pass |
| Unknown outcome | `MiningSession` | unknown is never resubmitted | Pass |
| Duplicate suppression | `MiningSession.already_submitted` | accepted, rejected and unknown submissions are not repeated | Pass |
| Block candidate gate | `MiningSession`, chain observers | block candidates wait for independently observed chain progress | Pass; pool-only evidence is explicitly weaker |
| Persistence | `MiningSession._save` | exclusive process lock, fsync, atomic replace, bounded logs | Pass |
| Failover | `ProductionMiningCoordinator` | all endpoints attempted; full outage uses bounded exponential backoff | Pass |
| Backpressure | `ProductionStratumClient` | bounded queue, enqueue/write/request timeouts | Pass |
| Shutdown | runtime/coordinator `finally` blocks | cancel precompute, close pool, stop bridge, close telemetry/session | Pass |
| CI | `mining-production-network.yml` | protocol, lifecycle, transport and proof-boundary regressions | Expanded |

## Repaired defects

### 1. Retargeting issued work — high

`mining.set_difficulty` updated every existing job. Stratum V1 difficulty
changes belong to the next `mining.notify`. Retroactive mutation could cause
valid historical work to be rejected locally or work to be tested against a
target the pool did not assign to that job.

### 2. Extranonce transition retained incompatible jobs — high

`mining.set_extranonce` changed the subscription but retained job templates.
Those templates were constructed under the previous coinbase contract. The
adapter now clears them and waits for a fresh notify.

### 3. Explicitly disabled pools remained in failover — high

Runtime configuration sorted disabled pools after enabled pools but still
dialed them. Explicit `enabled: false` entries are now excluded.

### 4. Request timeout could stop the runtime — high availability

Submission/request timeouts were made durable as unknown outcomes but were not
treated as reconnectable transport failures by both execution loops. They now
close the failed session and enter the existing bounded failover policy.

### 5. Proof checks depended on Python assertions — medium

Header and target lengths in two hash-pipeline entry points used `assert`.
`python -O` removes assertions. They are now unconditional `ValueError`
contracts.

### 6. `clean_jobs=False` was not honored by the proof adapter — medium

Prior jobs were retained in the job map but `_job_for` rejected every job
except the latest. The adapter now honors non-clean retention. The canonical
coordinator remains intentionally stricter and rechecks current generation
before network submission.

## Evidence completed

- Stratum adapter suite: 15/15 passed.
- Proof-boundary regression suite: 2/2 passed.
- Modified production modules compile successfully.
- CI now includes adapter transitions, share lifecycle, pool-only operation,
  and optimized-mode proof-boundary validation.

## Evidence still required before production certification

The code audit cannot substitute for external execution evidence:

1. one real pool-accepted share from the bounded smoke test;
2. an OpenCL run on the intended device with the built-in hashlib self-check;
3. a forced live failover between the selected production pools;
4. restart recovery after killing the worker during `mining.submit`;
5. a sustained soak demonstrating stable accepted/rejected/unknown/stale
   accounting; and
6. for mainnet block-candidate policy, preferably an independent Bitcoin Core
   observer rather than pool-only chain evidence.

Until those six items are recorded, the correct status is **code-contract
audited, external production evidence pending**.