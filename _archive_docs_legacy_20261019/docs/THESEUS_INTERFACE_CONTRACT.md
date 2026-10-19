# THESEUS Interface Contract (Agent B)

Durable custody / operational-record / continuity / recovery / provenance
service for the HYBA triad programme. Agents A (Chronus), C (OVID), D
(Turing), Tensor, PYTHIA, Salamander, AL HARAS, and approved EUCLID/TOE
workflows write operational records through this surface.

Authority: THESEUS preserves meaning; producers own meaning. THESEUS never
re-adjudicates record semantics, never transforms payloads, never searches or
indexes (Geodesic builds rebuildable projections), never defines security
policy (AL HARAS supplies contracts; THESEUS enforces them and fails closed).

## Import paths

New modules are not yet re-exported through `aethel.enterprise.__init__`
(package `__init__` is outside this agent's edit scope — tracked as a
cross-agent dependency). Import directly:

```python
from aethel.enterprise.custody import EnterpriseCustody, compose
from aethel.enterprise.records import (
    OperationalRecord, ProducerRegistry, ProducerContract,
    EVIDENCE_STATES, ProducerAdmissionError, ContractValidationError,
    DependencyMismatchError,
)
from aethel.enterprise.checkpoint import (
    CheckpointIntegrityError, CheckpointUnavailableError,
)
from aethel.enterprise.retention import RetentionPolicy
from aethel.enterprise.hooks import (
    SecurityHook, AllowAllHook, DenyingHook, AlHarasEvidenceAdapter,
)
```

## Writing a record — `put_record`

```python
record = OperationalRecord(
    record_id="matmul-run-42",            # stable producer-assigned id
    producer="chronus",                    # registered producer name
    producer_version="2.1.0",
    schema_version=1,                      # producer contract version
    kind="execution_evidence",
    payload=b"...",                        # opaque bytes
    evidence_state="MEASURED",             # PASS|FAIL|MEASURED|GATED|UNAVAILABLE|MISSING|REFUTED
    timestamp=..., sequence=7, epoch="e3",
    lineage=("parent-record-id",),
    correlation_ids={"run_id": "...", "workload_id": "..."},
    dependencies={"ovid_transform": 1},
    meta={...},
)
env = custody.put_record(record, idempotency_key="run-42")
```

Admission is fail-closed and contract-only:

- unregistered producer → `ProducerAdmissionError`
- schema_version outside the producer's admitted window → `ProducerAdmissionError`
- invalid evidence_state → `ContractValidationError`
- declared digest ≠ SHA-256(payload) → `ContractValidationError`
- dependency not satisfiable / unverifiable → `DependencyMismatchError`

A `FAIL`/`GATED`/`UNAVAILABLE`/`REFUTED` record IS stored — evidence state
is data, not a gate. Custody preserves it verbatim.

## Reading — `get`, `get_record`, `list_records`

```python
payload = custody.get(record_id)            # ingress bytes, integrity-verified
record  = custody.get_record(record_id)     # full OperationalRecord
rows    = custody.list_records()            # verified inventory w/ producer meta
```

## Access enforcement (AL HARAS boundary)

A stored record does not create authority to access it. Supply either:

```python
custody = compose(root, hmac_key=key,
    access_contract=lambda tenant, action, rid, meta: allowed(...))
# or a hook implementing before_get/before_delete (+ before_put)
# strict mode: absent contract => denied
custody = compose(root, hmac_key=key, require_access_contract=True)
```

Denials raise `AuthorityBoundaryError` and emit an `access_deny` provenance
event. `health()["access_contract"]` reports `callable|hook|none` — never
hidden.

## Durability lifecycle

- `checkpoint(label)` → integrity-verified snapshot (manifest HMAC + per-file
  digests); `verify_checkpoint(id)` → `{status: PASS|FAIL, ...}`;
  `list_checkpoints()`; `rollback(id)` — refuses interrupted/forged/corrupt
  checkpoints (`CheckpointUnavailableError` / `CheckpointIntegrityError`).
- `recover()` runs at open; `recovery_report()` returns
  `{records_verified, records_unrecoverable, pending_revalidation,
  journal_sealed_ops, dangling_intents_dropped}`.
- **Semantic revalidation handoff**: after recovery every record is listed in
  `pending_revalidation[producer]` until its producer calls
  `custody.semantic_revalidated(record_id, verdict="...", producer="...")`.
- `verify_replay()` — deterministic fold of the sealed WAL vs verified store;
  `replay(dest_custody)` — replays the sealed op stream into a second custody
  and verifies reconstructed digests.
- `enforce_retention()` — apply a declared `RetentionPolicy(max_age_seconds,
  max_records)` through journaled deletes.
- `custody_evidence(record_id)` — complete evidence chain: integrity,
  primary/replica states, envelope manifest, MAC verdict, journal ops,
  provenance events, checkpoint membership, pending-revalidation state.
- `backup(dest)` / `restore(src)` — unverified snapshot copies (checkpoints
  are the verified path).

## Production composition

`aethel.enterprise.lifecycle.CompositionRoot` is the ordered lifecycle:
custody recovers before consumers start; consumers halt before close.

```python
root_ = CompositionRoot(root, hmac_key=key, hook=al_haras_hook)
custody = root_.start()
root_.readiness()   # {"ready": bool, "custody": health, ...}
root_.stop()
```

## What producers must revalidate after recovery

THESEUS guarantees byte-identical, digest/MAC-verified, journal-ordered
restoration. It does NOT guarantee that a recovered record is still
semantically valid for the producer — schema migrations, revoked trust, or
evolved contracts are the producer's call. Wire your recovery path to drain
`pending_revalidation` and call `semantic_revalidated` per record.
