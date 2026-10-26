# Theseus & Ovid — Enterprise Database Technical Manual

Theseus and Ovid form the durable storage layer of the Chronus · Theseus · Ovid triad. Theseus is the self-healing prime-manifold storage owner — digest-pinned custody, Galois prime keys, Cassini anchors, sunflower phyllotaxis packing, one-shot heal from a redundant replica. Ovid is the metamorphosis owner — fold produces the working form; unfold materialises at the edge. Together they provide an enterprise-grade database surface for custody, integrity, transformation, and restart-replay.

Install theseus/ovid capability from the `aethel` package:

```python
from aethel import open_theseus, open_ovid, open_triad
```

## Overview

The Chronus · Theseus · Ovid triad is one system:

| Component | Owner | Responsibility | Code surface |
|---|---|---|---|
| **Chronus** | iGPU / execution | Authorized heterogeneous execution; execution evidence only — never a storage-correctness authority | `chronus.device`, `chronus.virtual_igpu` |
| **Theseus** | Durable custody | Digest-pinned custody, Galois prime keys, Cassini anchors, sunflower phyllotaxis packing, one-shot heal | `aethel.theseus.Theseus` |
| **Ovid** | Transformation | Fold = working form; unfold is egress only; declared transform contracts with exactness classification | `aethel.ovid.Ovid` |

Theseus is the ship that remains itself under replacement of parts: digest-pinned custody, Galois prime keys, Cassini/pv-lattice anchors, sunflower phyllotaxis packing, and one-shot heal from a redundant replica. Retrieval is not Theseus's job — geodesic search is handed off via `GeodesicHandoff`. Theseus stores and heals; the engine navigates.

Ovid owns encode/decode transformations for the triad:
- `metamorphose` / `fold_working` — bytes → folded working form (Zeckendorf)
- `materialise` / `unfold_egress` — folded form → bytes (edge only)

Compute and Theseus custody operate on the **folded** representation. Unfold is egress/materialisation, not the ambient store format.

Every transform Ovid offers is governed by a declared `TransformContract` carrying a mandatory exactness classification (`EXACT`, `BOUNDED_LOSS`, `APPROXIMATE`, `UNSUPPORTED`). `metamorphose` emits a `TransformLineage` — serializable transformation provenance suitable for Theseus durable custody — and `verify_equivalence` performs declared semantic-equivalence validation returning an explicit evidence state, never an inferred one.

## Opening Theseus and Ovid (Connection)

Theseus and Ovid are opened through the `aethel` package factory functions:

```python
from aethel import open_theseus, open_ovid, open_triad

# Open Ovid (fold metamorphosis owner)
ovid = open_ovid(max_fold_len=1_048_576)  # 1 MiB default

# Open Theseus in memory-only mode (healing within one process, no restart survival)
theseus = open_theseus(durable=False, ovid=ovid)

# Open Theseus with durable, restart-surviving custody
theseus = open_theseus(
    durable=True,
    durable_dir="/var/lib/hyba/theseus/tenant-1",
    ovid=ovid,
)

# Open the full Chronus · Theseus · Ovid triad façade
triad = open_triad(
    durable=True,
    durable_dir="/var/lib/hyba/theseus/tenant-1",
    bind_chronus=True,
)
```

Connection reference:

| Factory | Module:Function | Purpose | Durable |
|---|---|---|---|
| `open_ovid()` | `aethel.ovid:open_ovid` | Ovid metamorphosis owner | Stateless |
| `open_theseus()` | `aethel.theseus:open_theseus` | Theseus custody owner | Optional via `durable_dir` |
| `open_triad()` | `aethel.triad:open_triad` | Chronus·Theseus·Ovid façade | Via `durable`/`durable_dir` |
| `open_enterprise_store()` | `aethel.enterprise_bridge:open_enterprise_store` | Enterprise store kernel (triad wrapper) | Via `durable`/`bind_chronus` |

When `durable_dir` points at an existing tree containing `theseus_index.json`, `open_theseus` attaches and rebuilds the owner from the durable store (`Theseus.attach`, `aethel.theseus:Theseus.attach`). When the directory is empty or absent, a fresh owner is created on the first durable commit. A non-empty directory lacking a complete index, or an orphaned `durable/ledger.jsonl` journal, fails closed with an owner-reconciliation required error rather than silently creating fresh state.

## Authentication and Authorization

### Authentication model

Theseus custody uses HMAC authenticity (not passwords). Each custody record is sealed with an HMAC key; there are no default secrets.

```python
from hyba_db import TheseusFileCustody

custody = TheseusFileCustody(
    root="/var/lib/hyba/custody",
    hmac_key=b"<32-byte-secret>",
    key_id="k1",
    require_authenticity=True,
    allow_insecure_dev_key=False,
)

record_id = custody.put_record(tenant_id="tenant-1", record=operational_record)
ok = custody.verify(tenant_id="tenant-1", record_id=record_id)
```

Authentication surface:

| Component | Mechanism | File:Class | Notes |
|---|---|---|---|
| Theseus custody | HMAC key per tenant | `hyba_db.theseus_custody:TheseusFileCustody` | No default secret; `hmac_key` required |
| Enterprise custody | HMAC + WAL journal + primary/replica | `aethel.enterprise.custody:EnterpriseCustody` | `require_authenticity` defaults True |
| Governance tokens | Ed25519 signed, single-use, 1–300s TTL | `aethel.enterprise.governance` | External host/officer issuance |
| Envelope integrity | SHA-256 provenance hash | `aethel.enterprise_bridge:provenance_hash` | Integrity, not authenticity |

### Identity-to-role mapping

Theseus custody is partitioned per tenant. Each tenant maps to its own `EnterpriseCustody` under `<root>/<tenant>`, so a custody identity from one tenant can never verify inside another. A custody record id that does not resolve to an admitted `OperationalRecord` fails closed.

There is no OS-level identity mapping (no Kerberos/SSPI equivalent in this codebase). Authentication is purely key-based: the caller presents the `hmac_key` bound to the custody root at construction. Do not fabricate OS credential integration — it is not implemented.

### Authorization

- **Admin tasks**: bind custody root, rotate HMAC key, configure quotas, set `require_authenticity`, attach/recover durable dir
- **User tasks**: `put_record`, `get`, `verify`, `fold`, `materialise`, `verify_equivalence`
- **Fail-closed**: missing key, wrong key, missing record, digest mismatch, unverifiable attach all raise or return `False`

### Transport security

Theseus/Ovid custody is a local filesystem substrate. There is no network transport, no TLS, no `gssencmode`, no IAM, and no Kerberos/GSSAPI in this codebase. Do not document transit encryption, IAM profiles, or Kerberos service principal registration — those are external concerns, not Theseus/Ovid features.

## Server and Connection Setup

### Durable directory binding

Production deployments bind Theseus to a real on-disk store:

```
durable_dir/
├── theseus_index.json     # record index (hash-chained, re-verified on attach)
└── durable/
    ├── ledger.jsonl       # Cassini-ledger journal
    └── blocks/            # Fibonacci-addressed block store
```

Every durable commit publishes the block store and record index under `durable_dir` before its receipt is issued — custody survives process exit. `AddressSpace.attach` re-verifies the durable journal and every block; `Theseus.attach` re-admits every record through the digest-verified heal path, so a torn or forged store fails closed at attach rather than on first read.

### Replication and healing policy

Theseus maintains primary + replica copies for one-shot heal:

| Policy | Setting | File:Class | Scope |
|---|---|---|---|
| Primary replica | 1 primary + 1 replica | `aethel.theseus:Theseus.put` | In-process replica |
| Durable block | `AddressSpace` with Cassini ledger | `aethel.storage:AddressSpace` | Fibonacci-addressed blocks |
| Heal sources | Replica → durable block → prime substrate | `aethel.theseus:Theseus._heal` | Ordered, fail-closed |
| Distributed multi-node | `MultiNodeCluster` (Raft, n≥3) | `aethel.enterprise.distributed:MultiNodeCluster` | `[ROADMAP]` — claim scope `distributed_consensus_software_multi_node_local`, not real WAN consensus |
| Cross-region DR | `CrossRegionDR` | `aethel.enterprise.distributed:CrossRegionDR` | `[ROADMAP]` — claim scope `cross_region_dr_software_simulated_regions`, not real multi-geo WAN |

### Chronus binding (execution evidence)

`open_triad(bind_chronus=True)` attempts to bind the Chronus one-iGPU device for execution evidence. Chronus is optional: if it cannot be bound, the triad degrades gracefully and reports `chronus: unbound` in health output. Chronus never changes canonical digests or correctness to obtain throughput.

## Client Tools

Theseus/Ovid expose programmatic client surfaces, not a SQL shell or `psql`-equivalent:

| Client tool | Module:Class/Function | Operation |
|---|---|---|
| Theseus custody | `aethel.theseus:Theseus` | put, get, heal, verify, attach, snapshot |
| Ovid metamorphosis | `aethel.ovid:Ovid` | metamorphose, materialise, verify_equivalence, round_trip |
| Triad façade | `aethel.triad:Triad` | put, get, fold, materialise, verify, geodesic |
| Enterprise custody | `aethel.enterprise.custody:EnterpriseCustody` | put_record, get_record, verify, tenant isolation |
| File-plane custody | `hyba_db.theseus_custody:TheseusFileCustody` | put_record, verify, open_tenant, close |
| Ovid data index | `hyba_db.ovid_index:OvidDataIndex` | files, knowledge, mining, verify, organisation_digest |
| Capability report | `aethel.enterprise_bridge:report` | Machine-readable READY/PARTIAL/EXTERNAL status |
| Envelope emission | `aethel.enterprise_bridge:emit_envelope` | truth_class + provenance_hash |

There is no `pg_dump`/`pg_restore`/`psql` equivalent in this codebase. Backup/restore is via `Theseus.snapshot` + `Theseus.attach`.

## Operations

### Theseus — put (commit)

`Theseus.put` commits payload through the pipeline: Ovid fold → prime key → phyllotaxis → Theseus custody.

```python
record = theseus.put(
    payload=b"...",
    durable=True,
    curvature=ManifoldCurvature.GOLDEN_DENSE,
)
```

Commit stages (`aethel.theseus:Theseus.put`):
1. **Ovid fold** — bytes metamorphosed into `FoldedWorkingForm`; must pass `verify()`
2. **Cassini anchor** — deterministic anchor in 90-slot manifold domain from content digest; Cassini identity must hold
3. **Prime key commit** — Galois prime substrate commits anchor + uuid + data (`aethel.primes:GaloisPrimeSubstrate.commit`)
4. **Phyllotaxis packing** — sunflower/Vogel site from anchor; lane routing uses phyllotaxis, not manifold sector enum
5. **Durable write** — when `durable=True`, payload written to `AddressSpace` and verified
6. **Replica** — primary + replica copies kept for one-shot heal
7. **Publish** — when `durable_dir` bound, block store + record index published before receipt issued

### Theseus — get (read with heal)

`Theseus.get` reads a payload by uuid, healing once on digest failure and failing closed thereafter:

```python
data = theseus.get(record.uuid)
```

Heal order (`aethel.theseus:Theseus._heal`):
1. **Replica** — replica copy checked against record digest
2. **Durable AddressSpace** — Fibonacci-addressed block re-read and verified
3. **Prime substrate reconstruct** — best-effort retrieval from Galois prime substrate

If no source reproduces the committed digest, `get` raises `TheseusError` and increments `heal_fail`.

### Theseus — verify

`Theseus.verify` walks every record, re-reading each through the digest-verified heal path and checking the durable `AddressSpace`. Returns `False` on any mismatch or unreadable record.

### Theseus — attach (rebuild from durable store)

```python
theseus = Theseus.attach("/var/lib/hyba/theseus/tenant-1")
```

`attach` (`aethel.theseus:Theseus.attach`) re-verifies the durable address space journal, re-parses the record index, checks owner identity, validates integer metadata and phyllotaxis sites, confirms index/ledger consistency, and re-admits every record through digest-verified heal. A store that cannot re-admit a record fails closed at attach.

### Ovid — fold and materialise

```python
form = ovid.metamorphose(b"payload bytes", parents=("run-42",))
raw = ovid.materialise(form)
assert raw == b"payload bytes"
```

`metamorphose` (`aethel.ovid:Ovid.metamorphose`) rejects non-bytes input, folds via the Zeckendorf codec (subject to `max_fold_len`), verifies the folded vector, and emits a `TransformLineage` with input/output hashes, exactness class, producer, and parent lineage. `materialise` verifies the working form before unfolding and refuses on digest/length mismatch.

### Ovid — equivalence validation

```python
verdict = ovid.verify_equivalence(source, form)
# verdict.equivalent == True, verdict.state == EvidenceState.PASS
```

Materialises the form and compares byte-exactly against the source. A refused materialise or mismatched payload is `FAIL`, never an exception smuggled as a pass.

### Ovid — round trip

```python
form, out = ovid.round_trip(payload)
assert out == payload
```

### Triad façade

The `Triad` façade composes Theseus + Ovid (+ Chronus) under a declared storage profile:

```python
record = triad.put(payload, durable=True)      # Theseus custody
data = triad.get(record.uuid)                   # Theseus custody read
form = triad.fold(payload)                      # Ovid fold
raw = triad.materialise(form)                   # Ovid materialise
ok = triad.verify()                             # Theseus verify
```

The enterprise profile (`THESEUS_CUSTODY_PROFILE`) binds custody to Theseus and transformation to Ovid, with no automatic migration from the legacy Ovid-root profile. The legacy profile (`LEGACY_OVID_PROFILE`) is explicitly separate and never dual-written or silently migrated.

### Scheduled jobs and maintenance

Theseus does not ship a cron-style scheduler. Operational maintenance maps to these routines:

| Maintenance task | Theseus/Ovid equivalent | Cadence | Failure mode |
|---|---|---|---|
| Integrity verification | `theseus.verify()` | On-demand / scheduled by operator | Returns `False` on mismatch |
| Heal exercise | `theseus.get(uid)` (triggers heal on digest failure) | On-demand | Raises `TheseusError` if all heal sources fail |
| Durable publish | Every durable commit publishes to `durable_dir` before receipt | Per commit | Fails closed if `durable_dir` not bound |
| Attach / replay | `Theseus.attach(directory)` | After restore / process restart | Fails closed on index/ledger mismatch |
| Ovid index verification | `ovid_index.verify(tenant_id)` | On-demand | Fails closed on missing indexes or invalid content hashes |
| Organisation digest | `ovid_index.organisation_digest(tenant_id)` | Replay check | Digest over complete ordered OVID view |

Re-indexing / re-folding is not a background job; Ovid folds are deterministic and immutable once committed. There is no `cron.schedule`/`cron.alter_job`/`cron.unschedule` equivalent in this codebase. Scheduled maintenance is operator-driven.

## Features

| Feature | Theseus | Ovid |
|---|---|---|
| Digest-pinned custody | SHA-256 digest bound to every record | Source digest bound to working form |
| Self-heal | Replica → durable block → prime substrate | N/A (Ovid folds deterministic) |
| Restart survival | `durable_dir` publish + attach rebuild | Stateless; reconstitutes from fold |
| Tenant isolation | Per-tenant `EnterpriseCustody` | Tenant-scoped `OvidDataIndex` |
| Transform provenance | `TransformLineage` travels with `FoldedWorkingForm` | Declared `TransformContract` per transform |
| Exactness classification | N/A | `EXACT` / `BOUNDED_LOSS` / `APPROXIMATE` / `UNSUPPORTED` |
| Equivalence evidence | N/A | `EquivalenceVerdict` with explicit `EvidenceState` |
| Phyllotaxis packing | Sunflower/Vogel golden-angle placement | N/A |
| Galois prime keys | `GaloisPrimeSubstrate` commit/retrieve | N/A |
| Cassini anchors | Cassini identity verified at every anchor | N/A |
| Geodesic handoff | `GeodesicHandoff` for engine navigation | N/A |
| Metrics | `put_ok`, `put_reject`, `get_ok`, `get_miss`, `heal_ok`, `heal_fail` | `fold_ok`, `fold_reject`, `unfold_ok`, `unfold_reject`, `equivalence_pass`, `equivalence_fail` |
| Health report | `health()` with status, phyllotaxis constant, durable binding | `health()` with status, contract version, transform count |

## Debugging and Health Checks

### Theseus health

```python
h = theseus.health()
```

Status is `ok` when the golden-angle constant verifies; `degraded` otherwise. Returns `owner`, `status`, `records`, `phyllotaxis_constant_ok`, `durable`, `metrics`, `claim_boundary`, `production_surface`.

### Ovid health

```python
h = ovid.health()
```

Returns `owner`, `status`, `max_fold_len`, `metrics`, `claim_boundary`, `contract_version`, `transforms` (declared/local count), `production_surface`.

### Triad health

```python
h = triad.health()
```

Returns `triad`, `status`, `production_surface`, `production_qualified` (always `False` until publication sequence executed), `storage_profile`, `custody`, `one_igpu`, `owners`, `theseus_claim`, `ovid_claim`.

### Folded working form verification

`FoldedWorkingForm.verify()` (`aethel.ovid:FoldedWorkingForm.verify`) checks:
- Owner is `ovid`
- Digest is valid 64-hex SHA-256
- Sparse topology present
- Vector verifies
- `folded_units` matches vector
- `raw_len` non-negative and matches `vector.total_bytes`
- Unfold length equals `raw_len`
- Unfold SHA-256 equals committed digest
- Lineage output digest matches working form digest

Any failure returns `False` (never raises).

### Capability report

```python
from aethel.enterprise_bridge import report
rep = report()
```

Returns `EnterpriseCapabilityReport` with READY/PARTIAL/EXTERNAL/ABSENT/STRETCH status per capability ID. `production_ready` is always `False` at report level.

## Troubleshooting

| Error or symptom | What to check |
|---|---|
| `uncertain custody commit` | A durable commit is in flight but not yet published. Reattach or run owner reconciliation before new commits. |
| `unknown uuid` | The uuid has no record in this owner; check caller supplied id returned by `put`. |
| `digest mismatch or missing payload; heal failed` | All three heal sources failed. Store may be torn — attach to known-good durable dir or reconcile. |
| `orphaned custody journal` | `durable/ledger.jsonl` exists without complete `theseus_index.json`. Preserve all files; owner reconciliation required. |
| `non-empty custody directory lacks a complete index` | Durable dir partially initialised. Reconcile before opening. |
| `golden-angle constant failed first-principles check` | Phyllotaxis invariant failed — do not proceed; substrate integrity problem. |
| `Cassini identity failed at n=<anchor>` | Cassini invariant failed at computed anchor — math/substrate bug, not data corruption. |
| `FoldDomainOverflow` | Payload exceeds `max_fold_len` (1 MiB default). Shard upstream — folding never truncates. |
| `ZeckendorfInvariantError` | Folded vector failed non-adjacency or decode verification — treat as corruption, not retryable. |
| `custody index/journal mismatch` | Record index and durable ledger disagree — owner reconciliation required. |
| `production_qualified: False` | Publication sequence not executed; informational, not a runtime block. |

## Theseus & Ovid vs. Standalone Database Systems

| Capability | Theseus & Ovid (HYBA storage substrate) | Standalone databases (PostgreSQL, MySQL, MongoDB, etc.) |
|---|---|---|
| Data model | Folded working form (Zeckendorf) → durable custody blocks | Rows, documents, key-value, graphs |
| Query language | None — geodesic handoff to engine; Ovid index for tenant-scoped views | SQL, NoSQL query languages |
| Integrity | SHA-256 digest per record + Cassini invariant + phyllotaxis | Checksums, transactions, foreign keys (varies) |
| Self-heal | Replica → durable block → prime substrate | Replication, backups, PITR (engine-dependent) |
| Restart survival | `durable_dir` publish + `attach` rebuild | WAL, snapshots, crash recovery |
| Tenancy | Per-tenant `EnterpriseCustody` isolation | Databases, schemas, roles, RLS |
| Transform provenance | `TransformLineage` with exactness classification | Not native; application-level audit logs |
| Exactness guarantee | Declared `EXACT` transforms proven byte-exact | ACID transactions (engine-dependent) |
| Storage authority | Theseus = custody; Ovid = transformation; Chronus = execution evidence | Single engine owns storage and query |
| Hardware binding | Chronus one-iGPU for execution evidence (optional) | Driver-dependent GPU/accelerator support |
| Fail-closed | Every integrity check fails closed; no silent fallbacks | Varies; autocommit/silent truncation possible |
| Geodesic search | `GeodesicHandoff` → engine; not reimplemented in Theseus | Native indexes and query planners |
| Cloud providers | Self-hosted file-plane custody; tenant-scoped | Managed instances (RDS, Aurora, Cloud SQL, Atlas) |

## Enterprise Boundaries — What Is NOT Claimed

A top-tier infrastructure company states its limits explicitly:

1. **No SQL interface** — Theseus/Ovid are programmatic APIs, not a SQL database; no `psql`, `pg_dump`, or query planner
2. **No network transport** — Local filesystem substrate only; no TLS, IAM, Kerberos, or GSSAPI
3. **No OS identity mapping** — Authentication is HMAC key-based only; no Kerberos/SSPI integration
4. **No cron scheduler** — Maintenance is operator-driven; no `pg_cron`-equivalent
5. **Folded form ≠ infinite storage** — Capacity bounded by `max_fold_len`, address index limits, durable dir capacity
6. **Chronus ≠ hash preimage oracle** — No hash-strike; mining accept authority remains sha256d target
7. **Millennium solvers ≠ solved Clay problems** — Engines/demos, not Clay conjecture resolutions
8. **Multi-node consensus ≠ real WAN** — `MultiNodeCluster` claim scope is `distributed_consensus_software_multi_node_local`, not real multi-geo consensus
9. **Cross-region DR ≠ real multi-geo** — `CrossRegionDR` claim scope is `cross_region_dr_software_simulated_regions`, not real multi-geo WAN
10. **Solutions API ≠ `/api/v1/solutions`** — `SolutionsAPI` is an in-process software facade; the 18-endpoint product API is external (Intelligence repo)

## Deployment Surface

| Entry point | Module:Function/Class | Config | GA status |
|---|---|---|---|
| Open Theseus | `aethel.theseus:open_theseus` | `durable`, `durable_dir`, `ovid` | GA (software) |
| Open Ovid | `aethel.ovid:open_ovid` | `max_fold_len` | GA (software) |
| Open Triad | `aethel.triad:open_triad` | `durable`, `durable_dir`, `bind_chronus`, `storage_profile` | GA (software) |
| Enterprise store | `aethel.enterprise_bridge:open_enterprise_store` | `durable`, `bind_chronus` | GA (software) |
| Enterprise custody | `aethel.enterprise.custody:EnterpriseCustody` | `root`, `tenant`, `hmac_key`, `quotas`, `hook` | GA (software single-root) |
| Composition root | `aethel.enterprise.lifecycle:CompositionRoot` | `root`, `tenant`, `hmac_key`, `chronus_accel` | GA (software) |
| File-plane custody | `hyba_db.theseus_custody:TheseusFileCustody` | `root`, `hmac_key`, `key_id`, `require_authenticity` | GA (software) |
| Ovid data index | `hyba_db.ovid_index:OvidDataIndex` | `store` | GA (software) |
| Capability report | `aethel.enterprise_bridge:report` | `include` (CapStatus filter) | GA (software) |
| Envelope emission | `aethel.enterprise_bridge:emit_envelope` | `payload`, `truth_class`, `capability_id`, `extra` | GA (software) |
| Smoke put/get | `aethel.enterprise_bridge:smoke_measured_put` | `payload` | GA (software) |
| Multi-node cluster | `aethel.enterprise.distributed:MultiNodeCluster` | `n_nodes>=3`, `base_root`, `hmac_key` | [ROADMAP] — software local, not WAN |
| Cross-region DR | `aethel.enterprise.distributed:CrossRegionDR` | Simulated regions only | [ROADMAP] — simulated, not real WAN |
| Hyperscaler soak | `aethel.enterprise.distributed:HyperscalerSoak` | Local fleet only | [ROADMAP] — local fleet, not infinite cloud |
| Chronus perf probe | `aethel.enterprise.distributed:ChronusPerfProbe` | Honest CPU/accel only | [ROADMAP] — never invents device FLOPS |
| Solutions API facade | `aethel.enterprise.distributed:SolutionsAPI` | In-process software facade | [ROADMAP] — not `/api/v1/solutions` product |
| Hyba cert gate | `aethel.enterprise.distributed:HybaEnterpriseCertificate` | Software certification gate | [ROADMAP] — gate, not certification authority |

Verified with: `python -c "from aethel import open_theseus, open_ovid, open_triad; from aethel.enterprise_bridge import report, emit_envelope, smoke_measured_put; print('imports OK')"`
