# OVID / THESEUS / Chronus — production and enterprise-fork review

Date: 2026-10-04
Baseline: f51cef18784da84120cf69aa21a6a656590898fa
Verdict: HOLD production approval and certified enterprise promotion. A development fork remains possible if explicitly experimental, but it must not inherit production-ready status.
Evidence class: static source review. No runtime reproductions, pytest, package build, crash injection or physical device benchmarks performed in this review. GitHub check-runs lookup for PR #32 returned 403 Resource not accessible by personal access token. CI is UNKNOWN, not passing or failing based on that permission error.

## Scope and PR status

The open-PR query returned no open PRs before this review branch was created. PR #29 (CIaaS requirement audit), #30 (EUCLID production reachability), #31 (Chronos packaging/surface) and #32 (384-parameter VQC ansatz) are merged. Merging does not close their acceptance gates.

- #29: documentation-only requirement capture; no implementation closure.
- #30: description reports 109 cognition tests passed, 405 unittest tests passed with 7 skips, and 10 pre-existing import-audit findings. These are author-reported results, not fresh reviewer executions. Long-lived restart, held-out generalisation and production certification remain explicitly unestablished.
- #31: description records compile/TOML/package inspection and lists pytest/build as required CI. This review has not established installed-wheel acceptance or fresh rendering/device evidence.
- #32: description explicitly says targeted tests were not executed by that MCP session. No Chronus or Tensor kernel/compression gain is claimed. Fresh tests remain required.

Reviewed source: aethel/ovid.py, theseus.py, triad.py, storage.py; aethel/enterprise/custody.py, journal.py, authenticity.py, ovid_registry.py, adapters.py; aethel/enterprise_bridge.py; hyba_db/store.py; chronus/virtual_igpu/memory.py; tests/test_enterprise_custody_substrate.py; docs/enterprise_triad/00_authority_matrix.md and 06_acceptance_test_matrix.md. This is not a complete review of every PR or every repository module.

## Required target ownership

OVID owns authoritative durable stored state, representation custody, integrity, checkpoints and recovery. It must operate correctly without THESEUS or a Chronus device.

THESEUS owns rebuildable database/query/index/graph/ontology/semantic projections. It is rebuilt from OVID, not needed to establish authoritative stored-state existence or integrity. Its projection metadata must bind an OVID object/generation and source digest.

Chronus owns device execution, ephemeral residency, transfers and device-bound evidence. It is not the durable source of truth and cannot decide storage correctness merely by binding a device.

This is convergence of existing capability, not a ground-up rewrite: preserve and harden current custody/encoding/addressing implementations, move their ownership behind OVID contracts, compose THESEUS projections, and retain explicit migration adapters for legacy names.

## Findings and release gates

### R01 — BLOCKER: target ownership is inverted in both code and documentation

Sources: aethel/ovid.py, aethel/theseus.py, aethel/triad.py, aethel/enterprise/custody.py, docs/enterprise_triad/00_authority_matrix.md.

Ovid currently owns transforms only; Theseus and EnterpriseCustody own payloads, replicas, journals and healing. The authority matrix explicitly prohibits Ovid opening journals. The enterprise implementation therefore does not resolve the mismatch; it preserves it. hyba_db/store.py also stores physical/tensor payloads, requiring classification rather than treating all current state as rebuildable projections.

Closure: designate a single OVID durable custody root, inventory/migrate every authoritative store and prove OVID put/read/verify/recover with THESEUS disabled/deleted. Rebuild THESEUS entirely from OVID records and compare query/index/lineage outputs. A name-only rename is insufficient.

### R02 — BLOCKER: tenant namespace collisions and unvalidated record paths

Source: aethel/enterprise/custody.py::_safe_tenant, _primary_path, _replica_path, _validate_dict, put/get/delete.

_safe_tenant rewrites distinct tenant identifiers to the same directory (for example a/b and a?b both become a_b). record_id is interpolated into filesystem paths without validating a safe identifier or enforcing resolved-root containment. Envelope validation checks MAC/digest but does not bind env.tenant to self.tenant or env.record_id to the requested path. With shared accepted keys, these omissions weaken namespace isolation independently of cryptographic validity.

Closure: collision-free tenant identifiers, trusted principal-to-tenant mapping, strict bounded record IDs, containment and symlink defenses, explicit envelope tenant/record binding. Add collision, traversal, absolute-path, symlink and cross-tenant-copy tests. Do not describe tenant strings alone as authentication.

### R03 — BLOCKER: recovery does not establish a sealed commit boundary

Sources: aethel/enterprise/custody.py::put/recover/_load_envelope; aethel/enterprise/journal.py::recover.

put writes intent, primary, replica, then seal. recover discards the journal's returned sealed rows and scans files as authority. A crash after primary publication but before seal can leave an unsealed write discoverable on reopen; the valid primary may also overwrite/heal the replica. When both sides are valid but have different generations, _load_envelope prefers primary without reconciling commit history. HMAC validity is not evidence that a generation committed.

Closure: define linearisation and acknowledged-durability semantics; replay/reconcile sealed transactions and stage writes atomically. Fault-inject before/after every intent, file replace and seal, including divergent valid generations and deletes. Assert recovery is exactly the last committed generation, never a stale or uncommitted mixture.

### R04 — HIGH: journal tail repair is incomplete and rewrite can race

Source: aethel/enterprise/journal.py::recover; acceptance test A18.

Invalid JSON stops parsing, but the file is rewritten only if pending intents exist. A malformed tail with no pending intent can remain; later appended rows are then invisible to future parsing. Reading and rewriting use separate file-lock scopes, permitting a standalone recovery/append race. Rewrite uses write_text without durable atomic replacement/fsync. There are no explicit size/row/schema bounds in this journal.

Closure: one locked bounded parse-and-atomic-repair operation, preserve original evidence, validate intent/seal pairing and record schemas, and test repair followed by new commits and a second restart. A18 currently checks old payload readability, not tail removal or visibility of subsequent commits.

### R05 — HIGH: cross-process checks occur outside the durable critical section

Source: aethel/enterprise/custody.py::put/delete/backup/restore.

Generation selection, idempotency and quota decisions use per-instance memory before the cross-process lock is acquired. Two processes can decide from stale state and publish conflicting generations or exceed shared quota. get may heal without that process lock. Backup and restore use the instance lock but do not exclude other processes across the transaction. Restore destroys live directories before staging/validating the backup.

Closure: lock/reload/check/write/seal as one process-wide transaction; compare-and-swap generation; consistent backup snapshot; validated staged restore with atomic switch/rollback. Add genuinely simultaneous process writers, quota/idempotency conflict and backup-during-write tests. The existing multiprocessing test explicitly covers reopen only, not concurrent writers.

### R06 — HIGH: fsync and readiness are not sufficient for durability/integrity claims

Sources: aethel/enterprise/custody.py::_atomic_write_json/_append_event/recover/health/_load_envelope; aethel/triad.py::health.

Enterprise envelope replacement fsyncs its file but not the containing directory; provenance events are flushed but not fsynced or cryptographically chained by this path. read_only startup/get can still heal files and append recovery events. recover marks _ready=True despite skipped bad records, and successful healing of one replica clears a global _degraded flag even if unrelated records remain corrupt. Triad health treats any non-null device object as bound/ok and does not prove a measured dispatch.

Closure: state explicit durability/failure assumptions by OS/filesystem, persist directory entries, retain per-record unresolved failures, separate liveness/readiness/integrity/device certification, and guarantee declared read-only mode does not repair/write. Test mixed healthy/bad records and startup with unverified/unavailable hardware.

### R07 — BLOCKER: Chronus virtual memory can overwrite another tenant's handle

Source: chronus/virtual_igpu/memory.py::store/lookup/_retrieve_object.

Object IDs default to a payload content hash that excludes tenant. _objects and object file paths are keyed by object_id alone. A second tenant storing identical content replaces the first tenant's ownership record; caller-supplied object_id can replace an existing object without checking owner. Lookup checks ownership after the overwrite, not before. Store/retrieve paths also interpolate supplied IDs and artifact tenant/workload IDs without safe-root validation.

Closure: tenant-scoped handles and immutable ownership, safely shared content-addressed blobs only behind scoped references, owner-checked updates, strict path inputs, and rejection of caller-provided unverified digests. Test identical-content tenants, forged overwrite, path escape and cross-tenant retrieval after restart.

### R08 — HIGH: Chronus residency and persistence are metadata, not real memory custody

Source: chronus/virtual_igpu/memory.py::_load_index/store/migrate_residency/_evict_until/_retrieve_object.

migrate_residency changes counters/tier strings without allocating/copying/releasing device memory. _evict_until zeroes host counters but retains rec.payload in memory; it can still admit an object larger than the budget. Index reload silently ignores malformed data, trusts supplied sizes/ownership/content_id and restores alleged device residency after process restart without device reattachment. Retrieval does not recompute stored content hashes. lookup returns mutable internal records. There is no OVID persistence call in this file.

Closure: represent logical residency separately from verified physical allocations; real adapter transfers and release handles; enforce budget or fail; validate persisted digest/schema/tenant; restart as unbound until actual device residency is established. OVID owns durable objects, Chronus keeps a validated rebuildable cache. Test payload retention, oversize admission, tampered index/blob, forged identities and actual adapter transfers.

### R09 — HIGH: ontology-store graph reads bypass edge integrity checks

Source: hyba_db/store.py::traverse/topology/_components/get_edge.

traverse reads to_node/kind directly from SQL rather than using get_edge, which verifies edge attestation and content identity. topology/_components also consume unverified raw edges. A modified edge can affect the returned graph/navigation before full verify_database is invoked. Most public methods accept a tenant ID, but authentication/principal authority is external and not established by this store.

Closure: integrity-verified projection reads or verified snapshot publication; bind projections to OVID generations; explicit authorization adapter. Tamper an edge without altering its attestation and assert traversal/topology reject it. Test tenant authentication separately from row scoping.

### R10 — HIGH: store resource and numeric-validation boundaries need strengthening

Source: hyba_db/store.py::_pack_vector/write_tensor/attest/verify_attestation.

write_tensor applies int() to dimensions, accepting fractional inputs by truncation. _pack_vector accepts finite float64 values then multiplies by SCALE before round; very large finite values can overflow that derived operation. Direct attest calls do not reserve quota for their rows/details. Verification recursively walks a tenant-wide parent chain, risking recursion failure on long legitimate histories and repeated expensive traversal.

Closure: strict non-bool integral dimensions, explicit numeric ranges/scale overflow handling, bounded admission for all record types, iterative/cached verified traversal with invalidation and measured long-chain performance. Test these as storage and tenant-denial-of-service boundaries.

### R11 — HIGH: basic triad durability and folded-working-form claims are overstated

Sources: aethel/theseus.py::put/snapshot/open_theseus; aethel/ovid.py::FoldedWorkingForm.verify.

The basic triad labels AddressSpace presence durable, but acknowledged put stays in memory until explicit snapshot; the Theseus path has no corresponding attach/reconstruction of its record index in the inspected file. put materialises incoming folded forms and stores raw bytes in _payloads/_replicas/AddressSpace, contradicting its folded-working-form custody wording. FoldedWorkingForm.verify does not verify digest, owner or sparse witness; materialise supplies the stronger digest/length check.

Closure: mark legacy/basic surface accurately; route production acknowledgement to the hardened OVID root, prove fresh-process record-ID recovery, persist the actual folded representation if promised, and enforce all public working-form invariants. AddressSpace itself has useful bounded replay, private-file checks and file/directory fsync; preserve those capabilities rather than replace them.

### R12 — MEDIUM/HIGH evidence: acceptance tests contain non-discriminating checks

Source: tests/test_enterprise_custody_substrate.py.

A1's digest assertion uses 'or True'; the endurance telemetry check also uses 'or True'. A13 constructs and raises EngineUnavailable directly rather than invoking production geodesic composition. A18 only verifies a previous payload survives a broken tail. The Chronus acceleration parity test toggles a flag; custody.put records the flag but does not execute a device kernel. Fifty operations are correctly described as light endurance, not soak.

Closure: remove vacuous assertions, call production routes, mutate witnesses to prove negative assertions detect defects, and add crash-window/long-chain/concurrent-process/adversarial tenant tests. Device parity requires actual dispatch identity and reference comparison, not flag equality.

## Strengths to retain

- AddressSpace validates true Fibonacci addresses, content digests and bounded replay, and uses private filesystem entries plus fsync-based snapshot publication.
- Enterprise custody requires explicit authenticity keys, supports previous-key verification and validates ingress digests through versioned transforms.
- OntologyStore uses SQLite transactions, WAL, synchronous=FULL, composite tenant foreign keys, content identities and HMAC attestations.
- Enterprise bridge now labels its capability catalogue declarative and refuses whole-system production_ready=true.
- Chronus remains optional for custody correctness; hardware absence must not destroy authoritative storage.

These are foundations worth converging; none eliminates the blockers above.

## Enterprise fork checklist

1. Freeze source commit and a component/dependency/provenance manifest. No automatic production promotion from merged PR status or catalogue READY.
2. Converge current custody primitives behind OVID authority; place database/graph/query projections behind THESEUS and bind both to Chronus through explicit measured adapters.
3. Close R02/R03/R07 before production multi-tenancy or authoritative-state deployment; close the remaining high-severity gates for the declared deployment scope.
4. Run unit/invariant/integration, two-process concurrency, power/crash windows, replica divergence, long-chain, quota, tenant and backup/restore tests on the final merged commit. Required tests must not disappear behind skip/xfail; hardware-unavailable evidence is separately labelled.
5. Build wheel/image and test in a clean offline environment. Enterprise import/execution must not load BTC/pool/wallet/credential/submission paths. Do not fork datasets, secrets or deployment state.
6. Prove THESEUS can be deleted/rebuilt without losing authoritative OVID records, and OVID works with Chronus disabled. Device acceleration may change timing, never canonical results/digests.
7. Produce device-specific Chronus evidence, real adapter transfer/residency evidence and sustained-load results where those capabilities are included. No physical-device claim from metadata alone.
8. Attach signed/verified acceptance artifacts, dataset/environment/device fingerprints and rollback/recovery runbooks to the source manifest. Fork verified reusable capability; retain historical and experimental capability with explicit provenance rather than silently deleting it.

No fork, merge, source rewrite or runtime deployment was performed by this review.
