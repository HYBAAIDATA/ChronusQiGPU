# 9 October 2026 — PYTHIA / OVID / THESEUS M3 recovery release gate

Status: **CODE CANDIDATE — NOT PRODUCTION QUALIFIED** until this exact branch's tests, installed artifacts and fresh-process voyage execute and the owner approves promotion.

## Authority preserved

- PYTHIA owns mining semantics, pool evidence, SearchPlan correctness.
- EUCLID owns intelligence orchestration; TOE is higher-order reasoning.
- OVID owns optional versioned, independently checked transformation/materialisation, not durable authority.
- THESEUS owns authoritative durable custody, journal, recovery and provenance.
- Geodesic owns rebuildable index/search projections.
- AL HARAS owns identity, security admission and release authorisation.
- CHRONUS executes; TURING supplies VQC capability; SALAMANDER heals within an authorised boundary.

## Active path

`chronus/mla1517_platform/python/mining_runtime.py:_main_async`
→ `M3PythiaProductionMiningCoordinator` → `CausalLedger`
→ `MiningStorageRecorder.from_env`
→ `hyba_db.file_registry` (`mining_lifecycle`, `file_versions`, `file_provenance`)
→ `TheseusFileCustody` (`aethel.enterprise.EnterpriseCustody`).

On the optional exact OVID path, `MiningStorageRecorder._receipt` uses
`OvidTransformPlane.fold_into` with verified unfold equivalence and lineage.
The original receipt is still custodied; its transform is a separate child.
No transform or index ownership is silently reassigned.

## Environment gates

`PYTHIA_M3_REQUIRED=1` turns on fail-closed M3. Set
`PYTHIA_STORAGE_DB`, `PYTHIA_STORAGE_ROOT`,
`PYTHIA_STORAGE_CUSTODY_ROOT`, `PYTHIA_STORAGE_TENANT` and
`PYTHIA_STORAGE_INTEGRITY_KEY_HEX`, `PYTHIA_STORAGE_CUSTODY_KEY_HEX`.
Keys must be separately managed secrets; never put actual values in logs,
GitHub artifacts or instructions. Strict mode requires a **preprovisioned**
tenant and fully configured AL HARAS authorisation.

`PYTHIA_STORAGE_OVID_EXACT=1` opts into a version-declared exact transform.
Leave disabled until explicitly approved for the deployment; disabled is
an explicit gate outcome, not successful transform evidence.

Strict restart verifies SQLite, chain HMAC/digests, CAS reconciliation, persisted
receipts and parent history; previous job evidence remains historical only.
The miner requires a **fresh** Stratum job identity before strict mining
transitions and synchronous, new-identity proof custody before submission.

## Reproducible acceptance checks

Run on a clean complete exact-head checkout, using the same interpreter as
the installed service. Keep JUnit and logs associated with SHA and platform:

```bash
python -m pytest -q tests/test_m3_storage_voyage.py tests/test_m3_runtime_closure.py
python -m pytest -q tests/test_hyba_file_registry.py
python scripts/check_storage_registry.py
python scripts/m3_evidence_pack.py --out evidence/m3_storage_gate
python scripts/euclid_v17_integration_gate.py
```

The file registry test may have a different current filename: resolve it
from the actual repository, do not interpret a missing test as PASS.
Complete negative cases: interrupted custody/receipt, replay idempotency,
payload conflict, bad HMAC, tenant isolation, missing parent, corrupt blob,
wrong version, stale session, denial of AL HARAS, absent pool acknowledgement,
unsupported backend, and OVID exact/unfold mismatch.

**Fresh-process** proof must start a new OS process against the same durable
storage; reopening objects inside one Python process is not enough.

## Evidence scopes that must remain separate

1. Source-controlled change and local unit tests.
2. Full installed wheels in an isolated environment, plus wheel-from-sdist.
3. Exact-head CI test artifacts and Linux/macOS hardware matrices.
4. Actual software end-to-end pool loopback, retained independent SHA256d.
5. Physical M5/Metal/iGPU execution with exact device-bound receipts.
6. External pool accepted share, only when genuine and owner-authorised.

Until all applicable gates pass: `NOT_CERTIFIED / QC_HOLD`. No CI or
production acceptance is inferred from the existence of source files,
historic screenshots, shadow CPU hashrates or internal test simulations.

Owner-gated decisions: mandatory OVID transformation policy, any change
to Geodesic index ownership, ontology/schema meaning or production promotion.
