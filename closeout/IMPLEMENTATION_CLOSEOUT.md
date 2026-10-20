# Production closeout implementation tranche — HOLD

Base: `2bc45bd4f9c45a29fea00aa1f6ed34222ed58f07`. Branch: `fix/trio-journal-memory-closeout-20261020`. This patch does not certify the whole system or permit publication. No production/rollback tag, merge, deployment, live-pool connection, registry upload or hosted CI dispatch was performed.

## Implemented

- `aethel/enterprise/journal.py`: one lock across bounded parse, evidence preservation and atomic repair; repair incomplete tail even with no dangling intent; unique transaction/seal/schema checks; file and directory fsync; reentrant lock and failure cleanup.
- `chronus/virtual_igpu/memory.py`: recomputed content identities, immutable tenant handles, detached payloads, bounded canonical handle lookup, guarded blob/artifact paths, persisted schema/blob validation; correct canonical migration accounting; reject unsupported physical residency and legacy tenantless migration; persisted physical labels restart UNBOUND.
- `scripts/run_closeout_qualification.py`: full-clean-checkout preflight, explicit claims command, sampled source manifests, isolated pytest basetemps/JUnit, skip/xfail review, exact arena count, fresh Chronus report capture, no production approval authority.

## Executed evidence

64 new scoped tests passed normally and under optimized Python: 33 journal, 22 memory, 9 runner refusal/contract cases. These are not Arena 100, the v17 suites, Sprint 1's separate 154, whole-system fault injection, physical-device or mining performance tests. Real source modules are loaded directly via importlib; full package initializers/dependency closure are not exercised.

Negative controls against pinned original source: journal 3 failed/1 passed/29 deselected; memory 20 failed/2 passed. Initial journal run failed because basetemp's parent did not exist; that environment setup error and its log are retained. Optimized run has the standard pytest warning about assertions outside rewritten test modules.

`release-evidence/closeout-tranche-20261020/` contains the actual logs, JUnit, patch diffs and pinned-blob provenance. It is a partial source snapshot, NOT an actual clean ROOT baseline/tag/identity. All task statuses and named-owner gaps are in `task_status.json`.

## Intentional compatibility changes requiring review

Arbitrary physical-device residency strings now raise NotImplementedError, not fictitious allocated bytes. Legacy migrate(object_id, adapter) refuses missing caller tenant. Existing callers and package suites must be checked before merge. Invalid persisted indexes fail closed rather than silently loading empty; operators need migration/quarantine procedures. Journal parsing limits require an owner-approved rotation/retention policy, and evidence-file retention limits remain operational work. POSIX durability tests do not certify Windows power-loss behavior. Filesystem containment checks are not a full hostile local-process/TOCTOU security boundary; digest checks are not authenticated HMAC provenance.

## Explicitly not completed

R01/R03/R05 full custody authority, sealed crash matrix and process-wide generation/CAS/backup/restore; full R02/R06; real R08 transfer/release binding and facade persistence; fresh ontology acceptance; EUCLID/Chronus suites; pool recovery and four-hour heartbeat; installed-product ABI/schema parity; license/legal sign-offs; actual rollback drill. R09's source path is already attested and was not patched by rote.

Nine source records remain distinct enterprise products. PULVINI is primarily folding. Mining is an optional workload, never the portfolio's purpose. `contract_audit.md` and `missing_signatures.json` enumerate unresolved groups without inventing executable APIs. `reports/licenses.md` is BLOCKED, not an inventory. `runbooks/prod_rollback.md` is unexercised.

## Reproduce scoped tests

```sh
python -m pytest tests/test_journal_closeout_recovery.py tests/test_memory_closeout_boundaries.py tests/test_closeout_runner_contract.py -p no:cacheprovider --basetemp=/absolute/outside/root/scoped-tests --junitxml=/absolute/outside/root/scoped.xml -ra -q
```

Use a fresh isolated environment. The attached runner requires a full checkout and the actual repository claims-gate command. Its output stays REVIEW_REQUIRED even after reruns; it cannot grant production approval. Preserve branch protections and paid-CI deferral. Owner/supervisor sign-offs remain mandatory.
