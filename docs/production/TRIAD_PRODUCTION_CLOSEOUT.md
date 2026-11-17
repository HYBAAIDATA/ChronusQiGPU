# Chronus–OVID–THESEUS Production Close-Out

**Status:** definitive source posture for the close-out branch. Production admission remains exact-commit evidence gated until the branch CI and mandatory product-gate attestations complete.

## 1. Canonical triad

The maintained platform has one execution-and-data triad:

| Authority | Production responsibility | Maintained implementation |
| --- | --- | --- |
| **CHRONUS** | workload execution, backend selection, fleet scheduling, tensor execution, verification and execution receipts | `src/chronus/execution/`, `src/chronus/fleet/`, `src/chronus/tensor/` |
| **OVID** | versioned reversible representation transforms and materialisation contracts | `src/chronus/ovid/transform.py` |
| **THESEUS** | durable custody, content integrity, continuity, restart recovery and provenance journal | `src/chronus/storage/durable.py` |

The triad is composed in `src/chronus/triad.py`. The older in-process `TheseusService` and `OVIDStorage` remain compatibility helpers; they are not the production custody path.

## 2. Production code elevated in this close-out

### THESEUS durable custody

`DurableTheseusService` uses SQLite WAL with full synchronous commits, foreign-key enforcement, bounded busy handling, digest verification, tenant-scoped records, append-only hash-chained journal entries and restart verification.

The service:
- fails closed on corrupt object bytes or broken journal continuity;
- verifies the database on open;
- supports checkpointing;
- preserves tenant isolation after restart;
- serialises concurrent writes through transactional admission;
- exposes explicit evidence and storage statistics.

This is a durable single-root custody implementation. Multi-region replication is not inferred from local durability and remains a deployment-specific qualification.

### OVID representation contract

`OvidTransformService` provides a versioned, reversible working representation and verified materialisation. Each representation carries source and representation digests plus the exact transformation contract and version.

OVID does not self-designate as the durable system of record. Resulting representations are committed to THESEUS through the production triad.

### CHRONUS tensor/runtime elevation

The July Geodesic/Tensor capabilities have been reconciled into maintained Chronus namespaces rather than restored as a competing runtime:

- `ExactFoldState`: reversible resident representation with genuine selective byte/row materialisation;
- `PhiTensorCore`: shape-safe add, Hadamard, scale, rectangular matrix multiply, Kronecker product and reduction;
- `GeodesicScheduler`: deterministic locality-aware ready ordering;
- `MetricTensor`: distance, step and walk operations;
- `PhiMemoryHierarchy`: dtype-preserving resident states and selective row loads;
- `TopologicalIntegrityGate`: verifies actual operation outputs against an independent expected output;
- `PhiGPU` / `HybridGPU`: compatibility execution facades with actual backend reporting and fail-closed accelerator requests;
- `EnergyModel`: compares only caller-supplied measured energy values; no built-in savings claim;
- `ProfiledHybridRouter`: selects only from verified observed route timings;
- `FoldedInferencePilot`: materialises only requested weight rows and reports actual bytes touched;
- `OpenCLTensorBackend`, `CUDATensorBackend` and `MetalTensorBackend`: explicit physical routes with no implicit CPU fallback. Each route becomes eligible only after device discovery, kernel readiness and a known-answer self-test.

The physical routes are implemented code, not current performance evidence. A device-specific run is required before any physical performance claim.

## 3. Production admission

Production status cannot be created by a source constant, provider name, local test suite or historical report.

The mandatory gates are:

- `CO-SIGN`
- `RS-RECEIPT`
- `RS-REPLAY`
- `FN-CLAIMS`
- `FN-CUSTODY`

`src/chronus/core/facade.py` now delegates to the evidence-based qualification contract. `scripts/ci/manifest.py` produces local software evidence only and no longer embeds a signing key or awards production status. `scripts/ci/build_product_gates.py` directly executes the five software-base product verifiers. The qualification workflow independently attests both the bounded test evidence and product-gate evidence; `scripts/ci/evaluate_attested.py` binds them to the same commit/run and produces an attested profile verdict.

Publication is independently fail-closed. `scripts/ci/require_release_qualification.py` requires a successful full `CI` push run and a successful qualification push run for the exact release commit on `main`, then re-verifies the qualification verdict attestation before the release workflow builds anything.

A vendor name cannot satisfy custody. The `FN-CUSTODY` gate must contain the actual verified custody evidence required by the selected deployment profile.

## 4. Test and benchmark migration

Historical test/benchmark records from the Notion engineering record and the ChatGPT Library are retained in:

- `evidence/migration/chronus_historical_evidence_register.json`
- `docs/production/TEST_AND_BENCHMARK_PROVENANCE.md`

Historical passes are not silently carried forward as current release evidence. Where the capability is present in the maintained tree, the register maps it to its current source/tests; where an old device result is release-relevant, the register marks a current exact-commit rerun or reconciliation requirement.

## 5. Current close-out test surface

Focused current regressions added by this close-out:

```bash
python -m pytest -q \
  tests/test_triad_production.py \
  tests/test_triad_capability_manifest.py \
  tests/test_geodesic_tensor_migration.py \
  tests/test_qualification.py \
  tests/test_attested_evaluator.py \
  tests/test_product_gates.py \
  tests/test_release_gate.py
```

The full repository suite, package build, security scans, CodeQL, frontend build and existing qualification workflows remain required on the exact close-out commit.

## 6. Release rule

The definitive release rule is:

> **Production-admitted = current source + current tests + exact-commit attested mandatory gates + environment-specific evidence for every advertised physical/deployment capability.**

A capability may be implemented and software-verified while a physical backend or deployment profile remains unavailable. That state is reported explicitly; it does not reduce the implemented software capability and it does not manufacture external evidence.

## 7. Evidence files

- Capability contract: `capabilities/triad_production_manifest.json`
- Historical migration register: `evidence/migration/chronus_historical_evidence_register.json`
- Current qualification contract: `src/chronus/core/qualification.py`
- Product-gate builder: `scripts/ci/build_product_gates.py`
- Current evidence evaluator: `scripts/ci/evaluate_attested.py`
- Release verifier: `scripts/ci/require_release_qualification.py`
- Deployment profile contract: `capabilities/deployment_profiles.json`
- Current fleet contract: `docs/fleet/FLEET.md`
- Current acceleration evidence: `capabilities/acceleration_report.md`

## 8. Integrated durable shard protection (17 Nov 2026)

The optional `ProductionTriad.protect_payload` / `recover_protected_payload`
methods now route through `chronus.storage.protected.ProtectedTheseusService`.
THESEUS holds the manifest and journal entry; bounded immutable files retain
2–32 shards, with one XOR parity retained under the existing custody authority.
An actual single shard-file loss can be reconstructed after reopening the
service; two losses fail closed. This preserves OVID and the original
put/materialise contract, and makes no whole-device loss or physical IOPS claim.

Source and test details: `docs/production/PROTECTED_THESEUS_INTEGRATION.md`.
Artifact-to-commit reconciliation is available in the maintained
`scripts/reconcile_benchmarks.py` without running substitute workloads or
promoting held claims.
