# Chronus GPU packaging and PYTHIA fleet

Owner declarations D12–D14 govern: software capacity is finite; customers can use
independent Chronus or augment host GPUs. Manual host binding is optional.

## Existing mathematical contracts

| Responsibility | Existing implementation | Package connection |
|---|---|---|
| Execution scaling | `chronus/igpu/scaled_plan.py`, `lucas/pisot.py` | Lucas rung bounds admitted work; exact Pisot conjugate bound is retained in the tier manifest. Measured throughput is reported separately. |
| Storage addressing and integrity | `aethel/storage.py`: `AddressSpace`, `CassiniLedger`; `aethel/fibonacci.py` | Existing Fibonacci/Cassini address store remains available. Tier payload budgets use Fibonacci page counts, validated by Cassini witnesses and independent exact Binet evaluation. |
| Folded representation | `aethel/encoding.py`, `aethel/zeckendorf.py`, `aethel/enterprise/ovid_registry.py` | OVID's existing transform v1 folds/unfolds admitted bytes exactly. Report raw and actual folded payload bytes; some data expands. |
| Runtime composition | `chronus/triad.py`, `aethel/enterprise/ovid_state.py` | Chronus executes; OVID owns authenticated durable records/checkpoints; THESEUS rebuilds discovery from verified OVID records. |

Fibonacci address space does not create physical RAM. A Fibonacci budget is an
admission limit; the underlying enterprise envelope still uses its existing file
format and record IDs. This release does not silently migrate historical
`aethel.triad` stores. Their Fibonacci/Cassini storage and fold contracts remain
readable. The new OVID profile reuses the existing enterprise authentication,
replicas, folding and WAL formats; its ownership is explicit.

## Technical tiers

These defaults are editable deployment configuration, with no prices or SLA set.
Limits apply to one package/fleet instance, not to all independently started
processes or deployments. Commercial entitlement enforcement remains AL HARAS.

| Tier | Maximum logical workers | Lucas rung | Maximum items/request (32 × L_n) | Resident payload budget | Folded primary payload budget (F_n × MiB) | Stored records |
|---|---:|---:|---:|---:|---:|---:|
| Starter | 1 | 10 | 3,936 | 16 MiB | F10 = 55 MiB | 1,000 |
| Pro | 4 | 15 | 43,648 | 64 MiB | F13 = 233 MiB | 10,000 |
| Fleet | 12 | 20 | 484,064 | 256 MiB | F16 = 987 MiB | 100,000 |

Input JSON limits are 1/4/16 MiB. Algorithm-specific bounds still apply, including
transform-v1's 1 MiB raw fold domain. The memory limit accounts resident payloads;
it is not an OS RSS/cgroup limit. Stored-payload quotas exclude replicas, journals,
checkpoints, metadata and execution caches. Provision disk space and deployment
limits for those explicitly. Adding workers divides the fleet's storage/resident
budgets; it does not multiply the purchased budget. Each instance admits one
active request; a local PYTHIA fleet runs bounded shards concurrently.

No tier promises exponential speed, infinite capacity, a fixed hash rate or a
compression ratio. `chronus-gpu tiers` emits the exact algebraic witnesses.
`storage_measurements` reports observed raw/folded bytes; fleet receipts report
actual SHA256d evaluations and elapsed time.

## Installable package

Build the shared distributions and the module-free GPU package:

```bash
uv build --wheel --out-dir wheelhouse
uv build turing_universal_quantum_computer --wheel --out-dir wheelhouse
uv build packaging/kellogg-tensor --wheel --out-dir wheelhouse
uv build packaging/chronus-gpu --wheel --out-dir wheelhouse
python -m pip install --find-links wheelhouse hyba-chronus-gpu==1.0.0
```

`hyba-chronus-gpu` depends on the shared implementation; it does not vendor a second
Chronus, TURING or Kellogg. Install optional host runtimes only for the selected
adapter. Independent software execution needs no GPU device or binding.

```bash
chronus-gpu tiers
chronus-gpu capacity --root ./capacity --tenant example --tier starter --mode independent
chronus-gpu capacity --root ./capacity --tenant example --tier pro --mode host
chronus-pythia-fleet --root ./fleet --tenant pythia --tier pro --workers 4 --items 256
```

The fleet command runs synthetic, pool-free work. Its output is measured execution
evidence. The library's `PythiaFleet.grind_target_batch` accepts PYTHIA's existing
ordered nonce batches: it does not create a new search planner, Stratum client or
share-acceptance authority. All workers use the prepared SHA256d specialization.

## Fleet lifecycle and custody

The local fleet reuses `FleetScheduler`, `WorkerIdentity` and `WorkLease`. Each
worker is one logical iGPU. Partitions are disjoint positional slices of the
submitted nonce sequence. Results retain ordered-first-winner semantics even
when shards finish out of order; hash accounting sums actual evaluations across
all launched shards. Logical workers can share the same physical host/GPU;
worker count does not establish physical fan-out or independent failure domains.

OVID records the lease intent before dispatch, each verified execution envelope,
and the aggregate completion. THESEUS queries can rebuild after index deletion.
Lost workers, stale leases and failed custody produce no aggregate success.
Fences rotate after every batch, bounding active lease/history residency. A new
process uses fresh random fencing tokens. Interrupted OVID mutations remain
marked uncertain and require explicit reconciliation; blind retry is blocked.
Private local HMAC keys are created with owner-only permissions, or applications
may provide a managed key. Back up keys with the authoritative OVID directory.

This is an executable local fleet package. Multi-host placement, RDMA transport,
central billing, distributed entitlements and production deployment qualification
remain separate work. Existing live-submission identity and approval gates are
unchanged; creating a capacity package supplies no live pool authority.
