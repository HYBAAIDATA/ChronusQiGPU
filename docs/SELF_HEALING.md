# Self-healing: what exists, what runs, what is proven

Status as of 2026-11-19. This page is the source of truth for self-healing
claims in this repository. Each capability is graded on five separate
questions; a "yes" needs the named code or test.

| Capability | Implemented | Integrated | Runs automatically | Tested | Production-qualified |
|---|---|---|---|---|---|
| THESEUS Reed-Solomon repair (`chronus.storage.self_heal`, `DurableTheseusService`) | yes | yes: `ProductionTriad` open/read paths | yes: on open and on read (default `CHRONUS_SELF_HEALING_REPAIR=theseus`) | yes: `test_self_healing.py`, `test_self_healing_hardening.py` | no |
| Content-address verification of every repair | yes | yes | yes | yes | no |
| Atomic, crash-safe, concurrent, restart-safe repair | yes | yes | yes | yes: real process crash before COMMIT, `os._exit` after COMMIT, 8 processes on one file, 24 concurrent writers | no |
| Parity backfill for databases written before parity existed | yes | yes | yes: on open | yes | no |
| Batched syndrome decoder (numpy, exact) | yes | yes: all `reed_solomon.heal` callers and THESEUS | yes | yes: cross-checked against the Berlekamp-Welch reference on 0-11, 16 and 24 errors per block | no |
| Salamander-governed remediation of THESEUS faults (`chronus.integration.salamander_theseus`) | yes | yes, with the canonical Salamander package installed | no: `run_cycle()` is driven by the host or orchestrator schedule | yes, locally with the package (`test_salamander_theseus.py`); skipped in GitHub CI, which cannot install the private wheel | no |
| Repository / CI healing | no (exists in HYBAEnterprise, not here; see below) | no | no | no | no |
| Metadata, journal, SQLite page or whole-database repair | no | no | no | no | no |

**Authority boundary.** THESEUS storage repair (section 1) is a THESEUS
integrity function: Reed-Solomon parity correction of stored bytes, verified
against the content address. It is not Salamander and it is not "self-healing"
in the architectural sense. Salamander (section 3) is the remediation and
optimisation authority for the whole system; for storage it can take over the
decision to repair (`CHRONUS_SELF_HEALING_REPAIR=salamander`), but the repair
operation itself stays inside THESEUS (`repair_object`), and in that mode
THESEUS refuses `repair_object` unless an AL HARAS-authorised Salamander action
for that object is executing. In code: `chronus.storage.self_heal` and
`DurableTheseusService` hold no Salamander logic; `chronus.integration.salamander_theseus`
holds no repair logic.

Nothing on this page is production-qualified. Salamander's own
`outcome_evidence.unqualified_readiness()` lists the gates that are still open.

## 1. THESEUS storage repair

- **Mechanism:** every object stored in `DurableTheseusService` gets a
  Reed-Solomon parity sidecar (systematic RS(48, 32) over GF(257), table
  `object_parity`). When a payload fails its SHA-256 content address, on open
  (`verify_store`) or on read (`reconstruct`), the bytes are corrected from
  parity. The repair is accepted only if the corrected bytes hash to the
  content address.
- **Atomicity:** the corrected payload and its `REPAIRED` evidence row are
  written in one `BEGIN IMMEDIATE` transaction, after re-checking that the
  payload and sidecar did not change while decoding ran (decoding holds no
  lock or transaction). A process killed after the write-back but before
  COMMIT leaves the damaged bytes and no event; the next open repairs it
  (`test_crash_between_write_back_and_commit_rolls_back_then_heals`).
- **Durability:** WAL with `synchronous=FULL`. A repair committed by a process
  that then exits without closing is present on reopen.
- **Concurrency:** one decode per object per process (per-object lock,
  reference-counted and released after the last waiter);
  across processes the write transaction's re-check makes the second repairer
  a no-op. Eight processes opening one damaged file record exactly one
  `REPAIRED` event.
- **Content address:** unchanged by construction (repair is accepted only if
  `sha256(bytes) == object_id`); records, objects and journal rows are
  byte-identical before and after repair (tested).
- **Fail closed:** damage beyond 8 bytes in a 32-byte block, a changed length,
  a missing or tampered sidecar, or an object without parity raises
  `StorageIntegrityError`. The damaged bytes are never overwritten with a
  guess, and a repeated identical failure is recorded once (`UNREPAIRABLE`).
- **Existing databases:** the parity tables are created on open. Verified
  objects that have no sidecar get one on open (`PARITY_BACKFILLED` event per
  object, batches of 256, re-checked under the write lock, at most
  `CHRONUS_SELF_HEALING_BACKFILL_LIMIT` per open). Objects above the
  size limit stay unprotected and fail closed.
- **Repair authority:** `CHRONUS_SELF_HEALING_REPAIR=theseus` (default)
  repairs in place. `salamander` makes THESEUS detect and diagnose only
  (`DETECTED` event); a repairable object stays quarantined (reads fail
  closed) until the Salamander control plane runs an AL HARAS-authorised
  repair through `DurableTheseusService.repair_object`, which THESEUS refuses
  unless the bound Salamander authority has an authorised action for that
  object in flight. A quarantined object does not block opening (journal
  continuity skips its bytes while it is still diagnosed repairable) and is
  recorded once as `DETECTED`, not once per read. Salamander acts only on
  objects its tenant (or its own evidence tenant) holds a record for; others
  are counted as out of scope with no object IDs or tenant names in the
  report. One remediation authority is bound per store per process. Unrepairable damage still fails closed at open in
  both modes.
- **Bounds:** up to 8 corrupted bytes per 32-byte block. Not covered: changed
  length, metadata/journal rows, SQLite page corruption (`PRAGMA
  integrity_check` fails closed), lost database or disk. Parity sits in the
  same file, so this does not replace replication or backups.
- **Configuration:** `CHRONUS_SELF_HEALING=1|0` (default `1`);
  `CHRONUS_SELF_HEALING_MAX_BYTES` (default 262144, capped at 1 MiB);
  `CHRONUS_SELF_HEALING_REPAIR=theseus|salamander`;
  `CHRONUS_SELF_HEALING_BACKFILL_LIMIT` (default 1024 legacy objects given
  parity per open, so a large old store does not stall startup);
  `DurableTheseusService(path, self_healing=..., repair_authority=...)`.
- **Visibility:** `evidence()["self_healing"]`, `self_heal_events()`,
  `scan_integrity()`, `diagnose_object()`.

## 2. Performance (measured)

The decoder used to be Berlekamp-Welch per block in pure Python. It is now a
batched syndrome decoder in numpy (`reed_solomon.decode_blocks`): syndromes of
all blocks in one matrix product, healthy blocks accepted without decoding,
damaged blocks decoded together (vectorised Berlekamp-Massey, Chien search,
Forney), and every corrected word re-checked to have zero syndromes before the
SHA-256 check. Arithmetic is exact int64 modulo 257. No accelerator was used:
the repository's OpenCL/CUDA tensor backends require a provisioned GPU and
refuse otherwise, and the CPU path already removes the bottleneck.

Hardware: Intel Xeon (8 logical CPUs), Linux 6.12, Python 3.13.5, numpy
2.5.5, SQLite 3.46.1. Raw results:
`benchmarks/acceleration/self_healing_raw.json` (after) and
`benchmarks/acceleration/self_healing_before_raw.json` (PR #176 head
`8c203917`, before). Reproduce with
`python benchmarks/acceleration/self_healing_benchmark.py`.

Medians; before = PR #176 head `8c203917`, after = `7a87ec10`. Every
repaired result was checked byte-for-byte and against its SHA-256.

| Measurement | Before | After | Speed-up |
|---|---|---|---|
| Healthy read, 256 KiB (`reconstruct`) | 0.77 ms | 0.65 ms | (no decode either way) |
| Corrupted read, 256 KiB, 8 bad bytes in every block (65,536 bytes corrected) | 43.46 s | 79.9 ms | 544x |
| Corrupted read, 64 KiB, worst case | 10.51 s | 22.8 ms | 461x |
| Corrupted read, 4 KiB, worst case | 834 ms | 3.9 ms | 214x |
| Corrupted read, 256 KiB, one bad byte | 237 ms | 10.1 ms | 24x |
| Startup recovery: open 200 x 64 KiB objects, 20 damaged at the bound | 216.98 s | 0.48 s | 456x |
| Open, same store, no damage | 0.094 s | 0.057 s | |
| Concurrent repair, 8 threads x 4 reads of one damaged 256 KiB object | 41.5 s wall, 1 repair | 0.13 s wall, 1 repair | 322x |
| Concurrent repair, 8 processes opening one damaged 256 KiB file | 61.7 s wall, 1 repair | 0.26 s wall, 1 repair | 238x |
| Decoder only, 256 KiB worst case (reference Berlekamp-Welch vs batched) | 41.6 s | 84.7 ms | 491x |
| Parity encode, 256 KiB | about 0.2 s | 2.3 ms | |
| Healthy-block check, 256 KiB (syndromes only) | | 7.6 ms | |

Over one minute for 256 KiB was the worst case before; it is now under
0.1 s on the same machine.

## 3. Salamander

**Recovered, not rewritten.** The canonical implementation is the
`salamander/` package in `hybadatadevops1/HYBAEnterprise` (main
`bc444dc9`, consolidated in `59ec71ec` "SALAMANDER: consolidate the strongest
implementation", 2026-11-12), documented there in
`docs/v2/09_SALAMANDER_SELF_HEALING.md` and shipped as the internal wheel
`hyba-salamander-self-healing` 1.0.0 (`packaging/salamander`). Older copies:
`HYBAAIDATA/PhiEnterprise` `salamander/` (stops at `7f91cc8f`, 2026-10-26,
missing `recovery_learning`, `runtime_learning`, `enterprise_intelligence`,
`gate_recovery_verifier`); the EUCLID-side engines `Intelligence/salamander*.py`
and `chronus/mla1517_platform/python/salamander_*.py` in both repositories
(repository and mining healing, not the control-plane package).

The package is HYBA-proprietary (`Private :: Do Not Upload`) and is **not
vendored** into this repository. `chronus.integration.salamander_theseus`
imports it when installed and raises `SalamanderUnavailable` otherwise.

**Closed loop for storage faults** (`SalamanderTheseusRemediation.run_cycle`):

| Step | Owner | Code |
|---|---|---|
| Observe, Detect | THESEUS | `scan_integrity()`; Salamander `plane.observe()` health decision |
| Diagnose | THESEUS | `diagnose_object()`: HEALTHY / REPAIRABLE / UNREPAIRABLE |
| Select remediation | Salamander | `RecoveryPlan` with a `RESTORE_CUSTODY` step and a `ROLLBACK` step; unrepairable findings are escalated to a person, never actuated |
| Authorise | AL HARAS | `build_authorized_control_plane`: signed subscription token, guardian policy, single-use grant |
| Execute | Chronus (THESEUS operation) | registered handler calls `repair_object()` |
| Verify | independent | fresh read-only SQLite connection (percent-encoded `file:` URI) re-hashes the payload |
| Accept or rollback | Salamander | unverified repair triggers the rollback step, which independently confirms THESEUS left no partial write |
| Retain evidence | THESEUS | every hash-chained ledger record is stored as a content-addressed THESEUS object (tenant `salamander-evidence`); AL HARAS keeps its own audit chain |
| Continue monitoring | EUCLID / host | `run_cycle()` is called on the orchestrator's schedule; the per-target recovery budget bounds repeats |

Tested locally with the wheel built and verified by HYBAEnterprise's own
`packaging/salamander/build_and_verify.py` (`artifact_verified: true`,
`production_qualified: false`): authorised repair with full ledger and
evidence in THESEUS, AL HARAS denial blocks execution, unrepairable damage is
escalated without actuation, and the recovery budget stops repeated
remediation. GitHub CI skips these tests because the private wheel cannot be
installed there.

## 4. Repository and CI healing

No CI auto-repair exists in this repository. The authorised mechanisms found
in `hybadatadevops1/HYBAEnterprise` (identical copies in
`HYBAAIDATA/PhiEnterprise`) are EUCLID/Salamander library code, not CI jobs:

- `Intelligence/isolated_repair.py`: 12-stage repair loop (observe, diagnose,
  propose, authorise, isolate in a temporary copy, apply, validate, probe,
  compare with baseline, commit or roll back, record, learn). The defect must
  reproduce before a repair is admitted, the candidate must pass an external
  validator, and protected tests and authority files are excluded.
- `Intelligence/repository_review.py`: read-only review over a host-approved
  path/hash manifest.
- `Intelligence/salamander_agentic.py` + `salamander_transaction.py`:
  source-repair through a `RepairTransaction` and host-configured validator.
- `.github/workflows/salamander-outcome-boundary.yml`: contract tests and
  planted-defect mutation checks for the Salamander package (not a repair job).

None of these modify code autonomously, and they are not wired here: doing so
means copying proprietary HYBAEnterprise source into this repository (public
while CI runs) or packaging `Intelligence/` as an internal wheel. That is an
owner decision and is tracked as open.

## 5. Healing names that are not the mechanism

- `MiningAdminEngine.execute_dsw_heal` (and `/v1/mining/admin` heal,
  `sdk.heal_mining_anomaly`): clears the flag set by `inject_anomaly`;
  returns `"repair_performed": false`.
- `DSW1CycleInstantonCobordism.heal_trace`: sets every value to the mean; it
  does not recover original values.
- `DSWInstantonSelfHealer` in `src/chronus/chronus_gpiu-v36.py`: used to XOR
  byte 0 twice and always report success. It now protects the trace with
  RS(48, 32), injects a real fault, decodes, and reports success only if the
  repaired bytes match the trace's SHA-256 (`test_legacy_dsw_healer_*`). When
  the check cannot run (package not importable, trace over 1 MiB) it returns
  `None` and the monolith prints "I27 NOT RUN", never PASS; the I28 matrix,
  which depends on it, then also returns `None` and prints "I28 NOT RUN".
  Still open (not changed here): in the same file, Gate 3 ("Invariant
  Preservation I1-I28") is a hard-coded `"status": "PASS"` dict in three
  places and does not reflect the result of `run_invariant_tests`.

### Reed-Solomon and the DSW instanton research

The research specification (`docs/specifications/CHRONUS_GPIU_v3.0_SPECIFICATION.md`,
`docs/AUDIT_AND_PROOF_DOSSIER.md`) describes Donaldson-Seiberg-Witten
instanton healing as restoring sheaf consensus, `ker(L_F) = H^0`, on a 4D
execution lattice in one clock cycle with no rollback and with charge
conservation. The AL HARAS claims register
(`docs/security/AL_HARAS_NOTES_RECONCILIATION.md`) lists that claim as
**Elevating**, with Reed-Solomon trace repair as the code today. Reed-Solomon
is a classical error-correcting code: it delivers the observable property
"corrupted bytes are corrected from redundancy without restoring a
checkpoint", within 8 bytes per 32-byte block. It is not an implementation of
gauge-theoretic instanton or monopole mathematics, it has no 4D lattice or
one-cycle property, and it should not be described as the DSW architecture.

## 6. Not implemented

- Metadata, journal, SQLite page and whole-database repair (needs replication
  or backup restore).
- More than 8 damaged bytes per 32-byte block, or length changes.
- Repository/CI healing in this repository (section 4).
- Continuous Salamander monitoring as a service (the loop exists; scheduling
  it is the orchestrator's job and is not configured here).
