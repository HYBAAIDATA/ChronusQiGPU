# PYTHIA M3 storage/database closure

This document describes the implemented file plane. It is a closure contract,
not a replacement for the authority model.

## Authority boundaries

- **THESEUS** is durable custody, records, continuity, integrity, recovery and provenance.
- **hyba_db** is the tenant-scoped ontology/query/projection surface; it extends the existing store and does not replace THESEUS.
- **OVID** transforms representations and records transform lineage; it is not the evidence store.
- **AL HARAS** authorises identities, capabilities and policy.
- **PYTHIA** owns mining intelligence and the final `SearchPlan`.
- **CHRONUS** owns heterogeneous execution; TURING and KELLOGG are supporting authorities.
- **SALAMANDER** records bounded healing and optimisation.

The canonical inventory is `governance/storage_registry.yaml`. The archaeology
probe is discovery evidence only. Unknown durable surfaces are release blockers.

## File taxonomy and identity

The registry adds `file_objects` (logical identity), `file_versions`
(immutable content versions), `file_events` (append-only lifecycle),
`file_links` (tenant-scoped semantic links), and `file_intents` (recoverable
write protocol). A path is never the identity. Versions are addressed by
SHA-256 content and stored under `<root>/<tenant>/<file-class>/<sha-prefix>/<sha>`.
Renames and relocation preserve object identity; identical bytes may be
content-deduplicated without merging semantic identity.

Every authoritative version has a producer, schema/evidence state, digest,
size, storage URI, and THESEUS custody record. Version mutations create a new
version. Corrections are events, not rewrites.

## Commit and recovery protocol

The write sequence is: declare intent, write/fsync a temporary artifact,
finalise the content-addressed blob, register the object/version, bind custody,
create domain links, append the completion event, and expose the result.
Cross-store atomicity is represented by the intent row. On interruption,
`recover_intents` deterministically marks a matching registered blob `RECOVERED`
or leaves the intent `QUARANTINED`; it never fabricates historical provenance.
Unresolved intents are reported by reconciliation.

## Domain and mining chain

File versions can link to local mining records and external adapter references;
cross-tenant links fail closed. Mining records are first-class and cannot be
collapsed into a generic share:

`job -> search_plan -> lease -> execution -> candidate_verification -> verified_proof -> submission -> pool_outcome -> learning/recovery`

A failed candidate cannot become a proof. A submission requires a proof, and a
pool outcome requires a submission. Pool acceptance is never inferred locally.
Evidence classes such as `LOCAL_E2E_EXECUTED`, `CI_UNAVAILABLE`,
`PHYSICAL_DEVICE_OBSERVED`, and `POOL_ACCEPTANCE_OBSERVED` remain distinct;
`CI_UNAVAILABLE` is neither pass nor fail.

## Reconciliation and verification

Run the taxonomy validator:

```text
python scripts/check_storage_registry.py
```

Run tenant reconciliation (the key can also be supplied through
`HYBA_INTEGRITY_KEY_HEX`):

```text
python scripts/reconcile_storage.py --db path/to/store.sqlite --root path/to/artifacts --tenant TENANT --integrity-key-hex HEX
```

Reconciliation checks registered blobs, hashes, sizes, tenant-scoped custody,
semantic links, and unregistered files. It returns non-zero for unresolved
violations. When a custody adapter or explicit custody record is supplied, the
machine-readable reconciliation report is itself registered as a custodied
artifact; otherwise the report explicitly says `artifact_registered=false`.

Database verification includes the file plane and mining-chain invariants.
Missing data is `UNAVAILABLE`; no optimistic status is emitted.

## Custody, transforms and production wiring

- `hyba_db/theseus_custody.py` — a real THESEUS custody adapter: per-tenant
  HMAC-tagged records on disk, tamper-detecting `verify()`, `revoke()` for
  retire. A version without a `custody_record_id` is never reported
  verified; reconciliation `passed` requires `custody_checked > 0` and
  `custody_unverified = 0`. With no custody adapter wired the gate fails
  closed rather than trusting `0 = PASS`.
- `hyba_db/ovid_transform.py` — `OvidTransformPlane`: transcode/render/roll/
  fold transforms, each with an `exactness` contract (`exact`, `lossy` only
  with an explicit policy, `offered`/`requested` as candidate proof states),
  a `receipt_json` audited against the written artifact, and a fail-closed
  `equivalence` verdict (`equivalent` requires exactness and at least one
  verified equivalence step). Promotion state derives from `TRANSFORMED` vs
  `EQUIVALENT` events — a version can never promote without the recorded
  step.
- `chronus/mla1517/mining/storage_recorder.py` — `MiningStorageRecorder`,
  attached to `CausalLedger` via `set_observer`, projects every real mining
  transition (candidate_offer / candidate_verified / submission_sent /
  resolved / pruned / rejected) into the registry: domain record + file
  version + custody + link. `_mining_stage` uses the real acceptance keys
  (`accepted`, `pool_result`, `verification`, `result`) so it does not
  misclassify the causal lifecycle. `MiningRuntime` wires it when
  `PYTHIA_STORAGE_DB`/`PYTHIA_STORAGE_ROOT`/`PYTHIA_INTEGRITY_KEY_HEX` are
  set; absent config leaves mining untouched.
- `hyba_db/module_adapter.py` — `ModuleEvidenceAdapter` for TURING, EUCLID,
  SALAMANDER, OVID, OVIDBIS, ATHENA, HELIOS, THESEUS, VULCAN, AL HARAS,
  KELLOGG, PYTHIA, CHRONUS, STRATUM, FILE_PLANE, MINING_CONTROL: `emit()`
  writes bytes through the registry under the module's real producer name.

## Observability

`FileRegistry.stats(tenant_id=None)` returns per-tenant measured numbers:
`file_objects_by_class`, `file_versions`, `custody_checked`,
`custody_unverified`, `uncustodied_versions`, `events`, `unresolved_intents`,
`orphan_records`, `orphan_versions`, `unlinked_versions`, `transforms`,
`quota_used_records`, `quota_used_blob_bytes`. CLI:

```text
python scripts/storage_status.py --db path/to/store.sqlite --root path --tenant TENANT --integrity-key-hex HEX
```

## Existing stores and migration

`FileRegistry.import_existing` registers the current digest, original path,
classification and known semantic owner of pre-M3 stores without inventing
historical timestamps or lineage — implemented and exercised in
`tests/test_m3_bootstrap_adapters.py`.

## Evidence pack

```text
python scripts/m3_evidence_pack.py --out evidence/m3_storage_gate
```

Runs the four M3 test files, provisions a tenant end-to-end (put → custody →
OVID lineage → replay → reconcile → stats), digests every touched file, and
writes a `pack.json` bound to the current commit SHA plus a companion
`pack.sha256`.

The storage gate is closed only after the implementation and acceptance
commands have executed on an exact commit, including corruption, orphan,
failpoint, tenant-isolation, restart/replay, OVID-lineage and installed-artifact
checks. GitHub Actions unavailability is recorded as `CI_UNAVAILABLE`, not as a
pass or a fail.
