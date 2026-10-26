# HYBA Enterprise Offerings & Capabilities

Top-tier enterprise infrastructure for sovereign, hyperscaler, and global deployments. Built on the Chronus · Theseus · Ovid triad — an exact, substrate-agnostic storage and compute substrate where every response carries a verifiable witness, every custody record is digest-pinned and self-healing, and no claim is made without measured evidence.

This document covers six enterprise offerings:

| Offering | Triad owner | Function | Code surface | GA status |
|---|---|---|---|---|
| **HYBA Resilient™** | Theseus | Digest-pinned, self-healing tier-0 custody store | `aethel.theseus.Theseus` | GA (software) |
| **HYBA Pulvini™ / Compress™** | Ovid | Lossless fold = working form; unfold at edge only | `aethel.ovid.Ovid` | GA (software) |
| **HYBA Accel™ / iGPU™** | Chronus | Authorized heterogeneous execution; fail-closed virtual iGPU | `chronus.device`, `chronus.virtual_igpu` | GA (software) |
| **HYBA Compass™** | Geodesic handoff | Multi-lens topological search boundary | `aethel.geodesic.GeodesicHandoff` | GA (handoff), [ROADMAP] (product API) |
| **HYBA Secure™** | AL HARAS | Governance envelope, claim boundaries, WORM audit | `al_haras/`, `aethel.enterprise.governance` | Partial (security core) |
| **HYBA Governance™** | Owner declarations | Rule 7 honest measurement, epistemic gates | `aethel.enterprise_bridge`, owner `CLAIM_BOUNDARY` | GA (discipline) |

## 1. Architecture & Tenancy

### Architecture

The Chronus · Theseus · Ovid triad is one system with separated authorities:

```text
  Chronus  ── Accel / iGPU compute owner (execution evidence only)
  Theseus  ── Pulvini custody + prime/phyllotaxis store (durable custody)
  Ovid     ── Pulvini metamorphosis (fold = working form)
  Geodesic ── Compass handoff (search not inside storage)
  AL HARAS ── Governance envelope (security boundary)
```

Authority matrix (non-absorption): Ovid transform only · Theseus custody only · Chronus accel only (digest-invariant) · Geodesic outside · AL HARAS security via hooks (evidence forward, not policy inside Theseus).

### Tenancy & isolation

Theseus custody is partitioned per tenant through `TheseusFileCustody` (`hyba_db.theseus_custody:TheseusFileCustody`):

- Each tenant maps to its own `EnterpriseCustody` under `<root>/<tenant>` (`aethel.enterprise.custody:EnterpriseCustody`)
- A custody identity from one tenant can never verify inside another
- A custody record id that does not resolve to an admitted `OperationalRecord` fails closed
- `OvidDataIndex` (`hyba_db.ovid_index:OvidDataIndex`) provides tenant-scoped views over rebuildable SQLite projection

There is no OS-level identity mapping, no Kerberos/SSPI integration, and no IAM profile in this codebase. Authentication is purely HMAC key-based.

### Resource quotas

`EnterpriseCustody` accepts a `quotas: Optional[Quotas]` parameter (`aethel.enterprise.custody:EnterpriseCustody.__init__`). Quota enforcement is present; specific quota limits and enforcement behavior are operator-configured, not hard-coded product SLAs.

## 2. HA/DR

### Replication strategy

Theseus maintains primary + replica copies for one-shot heal:

| Layer | Mechanism | Code | Claim scope |
|---|---|---|---|
| Primary + replica | In-process replica bytes | `aethel.theseus:Theseus.put` | Single-process |
| Durable block store | `AddressSpace` + Cassini ledger | `aethel.storage:AddressSpace` | Single root |
| WAL journal | `WriteAheadJournal` | `aethel.enterprise.custody` | Per-tenant root |
| Multi-root custody | `MultiRootCustody` (one root per node) | `aethel.enterprise.distributed:MultiRootCustody` | `[ROADMAP]` — `multi_root_multi_node_custody_software` |
| Multi-node cluster | `MultiNodeCluster` (Raft, n≥3) | `aethel.enterprise.distributed:MultiNodeCluster` | `[ROADMAP]` — `distributed_consensus_software_multi_node_local` |
| Cross-region DR | `CrossRegionDR` | `aethel.enterprise.distributed:CrossRegionDR` | `[ROADMAP]` — `cross_region_dr_software_simulated_regions` |

### Failover protocol

Failover is operator-driven through `Theseus.attach(directory)` (`aethel.theseus:Theseus.attach`), which:
1. Re-verifies the durable address space journal
2. Re-parses the record index
3. Checks owner identity
4. Validates integer metadata and phyllotaxis sites
5. Confirms index/ledger consistency
6. Re-admits every record through digest-verified heal

A store that cannot re-admit a record fails closed at attach. There is no automatic failover, no leader election exposed as a product feature, and no RPO/RTO target published in this codebase.

### Backup/restore

Backup is `Theseus.snapshot(directory)` (`aethel.theseus:Theseus.snapshot`), which publishes the durable block store and record index. Restore is `Theseus.attach(directory)`. There is no `pg_dump`/`pg_restore` equivalent.

## 3. Security & Compliance

### Encryption

- **At rest**: Custody records are stored on the local filesystem under `<root>/<tenant>/`. Directory permissions are validated (`aethel.storage:_validate_directory` requires mode 0o700, owner-only). No transparent data encryption or disk-level encryption is implemented in this codebase.
- **In transit**: Theseus/Ovid is a local filesystem substrate. There is no network transport, no TLS, no `gssencmode`, no IAM, and no Kerberos/GSSAPI. Transit encryption is an external concern, not a Theseus/Ovid feature.

### Key management

- HMAC key is provided by the caller at custody construction (`hmac_key` parameter); no default secret exists
- `EnterpriseCustody` supports `previous_hmac_keys` for key rotation
- Governance tokens use Ed25519 signed, single-use admission with 1–300s TTL (`aethel.enterprise.governance`); the issuer private key must be kept outside the operational actor and service process in production
- Envelope integrity uses SHA-256 provenance hash (`aethel.enterprise_bridge:provenance_hash`) — integrity, not authenticity

### Audit logs

- `EnterpriseCustody` writes a WAL journal (`journal/wal.jsonl`) and provenance events (`provenance/events.jsonl`) per tenant root
- `EvidenceTelemetry` (`aethel.enterprise.telemetry`) provides telemetry emission
- AL HARAS (`al_haras/`) provides WORM/append-only audit surfaces — core present, not full institutional ABAC product
- `emit_envelope` (`aethel.enterprise_bridge:emit_envelope`) emits `truth_class` + `provenance_hash` on responses

### Compliance posture

No SOC2, GDPR, HIPAA, or other compliance certification is claimed in this codebase. Rule 7 (Strict Honest Measurement) governs: code + measured tests, not marketing briefs. `theorem_proven` remains False until independent review. Do not fabricate compliance certifications.

### Access control

- `access_contract` and `require_access_contract` parameters on `EnterpriseCustody` — access granted by explicitly supplied contract; absence is declared, not hidden
- AL HARAS governs permission and residency; `E.GOV.ABAC` is [ROADMAP]/EXTERNAL — full attribute-based access control product lives in the Intelligence enterprise repo

## 4. Observability

### Metrics

| Owner | Metrics source | Metrics |
|---|---|---|
| Theseus | `aethel.theseus:Theseus.metrics` | `put_ok`, `put_reject`, `get_ok`, `get_miss`, `heal_ok`, `heal_fail` |
| Ovid | `aethel.ovid:Ovid.metrics` | `fold_ok`, `fold_reject`, `unfold_ok`, `unfold_reject`, `equivalence_pass`, `equivalence_fail` |
| Triad | `aethel.triad:Triad.metrics` | Aggregates Theseus + Ovid metrics |
| Capability catalogue | `aethel.enterprise_bridge:CAPABILITIES` | READY/PARTIAL/EXTERNAL/ABSENT/STRETCH counts per capability ID |

### Logs

- `aethel.storage` uses `logging.getLogger("aethel.storage")`
- `EvidenceTelemetry` (`aethel.enterprise.telemetry`) provides evidence telemetry
- No structured log aggregation, log shipping, or log retention product is implemented

### Traces / health endpoints

| Endpoint | Module:Function | Returns |
|---|---|---|
| Theseus health | `aethel.theseus:Theseus.health` | `owner`, `status`, `records`, `phyllotaxis_constant_ok`, `durable`, `metrics`, `claim_boundary`, `production_surface` |
| Ovid health | `aethel.ovid:Ovid.health` | `owner`, `status`, `max_fold_len`, `metrics`, `claim_boundary`, `contract_version`, `transforms`, `production_surface` |
| Triad health | `aethel.triad:Triad.health` | `triad`, `status`, `production_surface`, `production_qualified`, `storage_profile`, `custody`, `one_igpu`, `owners` |
| Capability report | `aethel.enterprise_bridge:report` | `EnterpriseCapabilityReport` with per-capability status |
| Envelope | `aethel.enterprise_bridge:emit_envelope` | `schema`, `truth_class`, `payload`, `generated_at`, `source`, `provenance_hash` |

No distributed tracing, OpenTelemetry, or Prometheus integration is implemented in this codebase.

## 5. Service Levels

No SLAs, response times, uptime targets, or support channels are published in this codebase. Do not invent SLAs.

| Support aspect | Status |
|---|---|
| SLA / uptime target | Not published — do not invent |
| Response time target | Not published — do not invent |
| Support channel | Not published — do not invent |
| Production certification | `production_ready` is always `False` at `EnterpriseCapabilityReport` level (`aethel.enterprise_bridge:EnterpriseCapabilityReport`) |
| Software readiness | Measured via `assert_hyba_gpu_software_ready` (`chronus.hyba_offering:assert_hyba_gpu_software_ready`) and triad/custody tests |

External gaps explicitly listed (not silent):
- `live_opencl_device_measurement` — hardware measurement is an external gate
- `hardware_rooted_attestation_keys` — attestation keys are external
- `real_pool_ack_truth_class` — real pool acknowledgement is external

## 6. Deployment Surface

| Entry point | Module:Function/Class | Key config params | GA status |
|---|---|---|---|
| Open Theseus | `aethel.theseus:open_theseus` | `durable`, `durable_dir`, `ovid` | GA (software) |
| Open Ovid | `aethel.ovid:open_ovid` | `max_fold_len` | GA (software) |
| Open Triad | `aethel.triad:open_triad` | `durable`, `durable_dir`, `bind_chronus`, `storage_profile` | GA (software) |
| Enterprise store | `aethel.enterprise_bridge:open_enterprise_store` | `durable`, `bind_chronus` | GA (software) |
| Enterprise custody | `aethel.enterprise.custody:EnterpriseCustody` | `root`, `tenant`, `hmac_key`, `quotas`, `hook`, `read_only` | GA (software single-root) |
| Composition root | `aethel.enterprise.lifecycle:CompositionRoot` | `root`, `tenant`, `hmac_key`, `chronus_accel` | GA (software) |
| File-plane custody | `hyba_db.theseus_custody:TheseusFileCustody` | `root`, `hmac_key`, `key_id`, `require_authenticity`, `allow_insecure_dev_key` | GA (software) |
| Ovid data index | `hyba_db.ovid_index:OvidDataIndex` | `store` | GA (software) |
| Capability report | `aethel.enterprise_bridge:report` | `include` (CapStatus filter) | GA (software) |
| Envelope emission | `aethel.enterprise_bridge:emit_envelope` | `payload`, `truth_class`, `capability_id`, `extra` | GA (software) |
| Smoke put/get | `aethel.enterprise_bridge:smoke_measured_put` | `payload` | GA (software) |
| Multi-node cluster | `aethel.enterprise.distributed:MultiNodeCluster.bootstrap` | `n_nodes>=3`, `base_root`, `hmac_key` | [ROADMAP] — software local, not WAN |
| Cross-region DR | `aethel.enterprise.distributed:CrossRegionDR` | Simulated regions | [ROADMAP] — simulated, not real multi-geo WAN |
| Hyperscaler soak | `aethel.enterprise.distributed:HyperscalerSoak` | Local fleet | [ROADMAP] — local fleet, not infinite cloud |
| Chronus perf probe | `aethel.enterprise.distributed:ChronusPerfProbe` | Honest CPU/accel | [ROADMAP] — never invents device FLOPS |
| Solutions API facade | `aethel.enterprise.distributed:SolutionsAPI` | In-process software facade | [ROADMAP] — not `/api/v1/solutions` product |
| Hyba cert gate | `aethel.enterprise.distributed:HybaEnterpriseCertificate` | Software certification gate | [ROADMAP] — gate, not certification authority |

### Version matrix

| Component | Package | Version source |
|---|---|---|
| Aethel substrate | `aethel` | `aethel.__init__:__version__ = "1.0.0"` |
| Theseus custody | `aethel.theseus` | Part of `aethel` 1.0.0 |
| Ovid metamorphosis | `aethel.ovid` | Part of `aethel` 1.0.0 |
| Enterprise custody | `aethel.enterprise.custody` | Part of `aethel` 1.0.0 |
| Enterprise bridge | `aethel.enterprise_bridge` | Part of `aethel` 1.0.0 |
| Theseus file custody | `hyba_db.theseus_custody` | Part of `hyba-ovid-data-organisation==1.0.0` (proposed) |
| Ovid data index | `hyba_db.ovid_index` | Part of `hyba-ovid-data-organisation==1.0.0` (proposed) |
| Chronus offering | `chronus.hyba_offering` | Part of `hyba-theseus-storage==1.0.0` (proposed) |

Distribution names `hyba-theseus-storage` and `hyba-ovid-data-organisation` are proposed, not qualified or published (`packaging/theseus/README.md`, `packaging/ovid/README.md`).

## Enterprise Boundaries — What Is NOT Claimed

1. **No SQL interface** — Programmatic API only; no `psql`, `pg_dump`, or query planner
2. **No network transport** — Local filesystem substrate; no TLS, IAM, Kerberos, or GSSAPI
3. **No OS identity mapping** — HMAC key-based authentication only
4. **No cron scheduler** — Maintenance is operator-driven; no `pg_cron`-equivalent
5. **Folded form ≠ infinite storage** — Capacity bounded by `max_fold_len`, address index limits, durable dir capacity
6. **Chronus ≠ hash preimage oracle** — No hash-strike; mining accept authority remains sha256d target
7. **Millennium solvers ≠ solved Clay problems** — Engines/demos, not Clay resolutions
8. **Multi-node consensus ≠ real WAN** — `MultiNodeCluster` claim scope is software multi-node local, not real multi-geo consensus
9. **Cross-region DR ≠ real multi-geo** — `CrossRegionDR` claim scope is simulated regions, not real multi-geo WAN
10. **Solutions API ≠ `/api/v1/solutions`** — `SolutionsAPI` is an in-process software facade; the 18-endpoint product API is external (Intelligence repo)
11. **No SOC2/GDPR/HIPAA certification** — Not claimed; do not invent
12. **No SLA/uptime target** — Not published; do not invent

## Verified imports

```python
python -c "
from aethel import open_theseus, open_ovid, open_triad
from aethel.enterprise_bridge import report, emit_envelope, smoke_measured_put
from aethel.enterprise.custody import EnterpriseCustody
from aethel.enterprise.lifecycle import CompositionRoot
from hyba_db import TheseusFileCustody, OvidDataIndex
print('imports OK')
"
```

**Owner approval required.** No deployment, release, or live work is authorized by this document alone.
