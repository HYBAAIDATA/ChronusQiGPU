# Enterprise Chronus · Theseus · Ovid Custody Substrate

**Governance:** Veritas Integritas · Rule 7 (Strict Honest Measurement)  
**Package:** `aethel.enterprise`  
**Claim scope:** *enterprise_custody_software_single_root* — single-process, single-root software custody with primary+replica files, write-ahead journal, HMAC authenticity, and measured telemetry. **Not** a distributed hyperscaler, multi-region cluster, or Solutions API.

## Authority (non-absorption)

| Owner | Authority | Must not |
| :--- | :--- | :--- |
| **Ovid** | Transform only (fold/unfold, versioned metamorphosis) | Own durable bytes, policy, or accel |
| **Theseus** | Custody only (put/get/delete, heal, journal, replicas) | Own transform semantics or security policy |
| **Chronus** | Acceleration only (optional CPU/iGPU path) | Change digests, own custody, or redefine fold |
| **Geodesic** | Outside triad — Intelligence handoff | Be absorbed into Theseus/Ovid/Chronus |
| **AL HARAS** | Security authority (hooks, evidence, deny) | Live *inside* Theseus as embedded policy |

Theseus may **forward evidence** to AL HARAS via optional hooks. It must not implement guardian policy locally.

## Document index

| File | Topic |
| :--- | :--- |
| [00_authority_matrix.md](00_authority_matrix.md) | Owner boundaries, non-absorption |
| [01_storage_consistency.md](01_storage_consistency.md) | Atomicity, visibility, crash, concurrency, heal |
| [02_schema_version_lineage.md](02_schema_version_lineage.md) | `format_version`, `ovid_transform_version` |
| [03_provenance_authenticity.md](03_provenance_authenticity.md) | SHA-256 integrity vs HMAC authenticity |
| [04_degradation_modes.md](04_degradation_modes.md) | Health / read-only / fail-closed table |
| [05_migration_classification.md](05_migration_classification.md) | Repo store classification |
| [06_acceptance_test_matrix.md](06_acceptance_test_matrix.md) | A1–A20 acceptance locks |
| [07_failure_model.md](07_failure_model.md) | Typed errors |

## Runtime entry

```python
from aethel.enterprise import compose, EnterpriseCustody, CompositionRoot

root = compose(path, tenant="default", hmac_key=b"...")
root.put(b"payload", record_id="r1")
```

Lifecycle: recover Theseus **before** consumers; stop/flush consumers before closing custody.

## Related

- Parent bridge: [`docs/ENTERPRISE_CAPABILITY_BRIDGE.md`](../ENTERPRISE_CAPABILITY_BRIDGE.md)
- Software triad façade: `aethel.triad` / `aethel.open_triad`
- Capabilities: `aethel/capabilities.json` → `enterprise_custody_software_single_root`

## Measured evidence (this workspace)

- Package: `aethel.enterprise`
- Tests: `tests/test_enterprise_custody_substrate.py` (+ triad + bridge suite)
- Evidence class: **MEASURED** for single-root software custody including:
  - versioned Ovid Zeckendorf working form
  - Theseus primary+replica + WAL recover
  - HMAC authenticity vs SHA-256 integrity
  - multi-thread concurrency + multi-process attach/reopen
  - heal, backup/restore, quotas, read-only, hook deny
  - light endurance (50 ops) with telemetry counters
- **Not measured here:** multi-node replication, hyperscaler fleet, hardware Chronus rooflines, Solutions API.



## Evidence boundary / Not proven

**Proven in this package (scoped):** `enterprise_custody_software_single_root` —
versioned folded working form, restart/replay, primary+replica healing, HMAC authenticity,
schema rejection, backup/restore, quotas/fail-closed storage exhaustion, thread concurrency,
multi-process attach/reopen, read-only/degradation behavior, telemetry honesty and
composition-root lifecycle.

**Not proven:** distributed consensus, simultaneous multi-root/multi-node custody,
cross-region DR, hyperscaler fleet soak, Chronus hardware performance, Solutions API
production readiness, or enterprise-wide HYBA certification.

Fifty operations is **light endurance (50 ops)** only — not soak evidence.
