# Chronus V2 — Definitive Implementation and Release Contract

**Revision:** 15 November 2026 close-out branch.

This contract describes the maintained implementation and the release behavior that must hold before production admission.

## 1. Maintained production surfaces

- `src/chronus/core/qualification.py`: mandatory evidence-gated production admission.
- `src/chronus/core/facade.py`: compatibility facade that cannot self-certify.
- `scripts/ci/build_product_gates.py`: executable software-base product gates.
- `scripts/ci/evaluate_attested.py`: exact-commit test/gate attestation evaluator.
- `scripts/ci/require_release_qualification.py`: exact-main CI/qualification release gate.
- `scripts/ci/manifest.py`: local software evidence generator; never production authority.
- `src/chronus/triad.py`: CHRONUS–OVID–THESEUS composition.
- `src/chronus/ovid/transform.py`: versioned reversible transform/materialisation.
- `src/chronus/storage/durable.py`: durable THESEUS custody and continuity.
- `src/chronus/tensor/`: maintained tensor execution and explicit physical backends.

## 2. Qualification rules

A mandatory gate may return PASS, FAIL, NOT_RUN, BLOCKED or UNQUALIFIED. Only PASS receives production credit.

Mandatory product gates:
- `CO-SIGN`
- `RS-RECEIPT`
- `RS-REPLAY`
- `FN-CLAIMS`
- `FN-CUSTODY`

An empty gate set cannot qualify. A provider name cannot qualify. A local HMAC or repository-generated label cannot qualify. Product-gate evidence is generated separately from test evidence, attested independently, and bound to the same commit/run by the evaluator. The `software-base` profile can qualify the distributable software without promoting external custody, multi-region, physical-performance or customer-deployment claims. Other deployment profiles require their own environment evidence under `capabilities/deployment_profiles.json`.

## 3. Custody and restart behavior

THESEUS owns the durable record. The production local implementation uses SQLite WAL, full synchronous commits, object digest verification, tenant-scoped records and a hash-chained journal.

Acceptance includes:
- fresh-open reconstruction;
- corruption rejection;
- journal continuity;
- concurrent writer safety;
- tenant isolation after restart;
- checkpoint evidence.

Multi-region replication, RTO/RPO and external key custody are separate deployment gates.

## 4. OVID behavior

OVID owns representation transformation and materialisation. Every production representation is versioned and digest-bound. Materialisation must verify the encoded representation and reconstructed source.

OVID does not receive durable-custody credit.

## 5. Tensor/backends

The software reference route supports explicit tensor operations and reports the actual backend used.

Physical routes are additive and fail closed:
- OpenCL GPU: `chronus.tensor.opencl_backend`
- NVIDIA CUDA: `chronus.tensor.cuda_backend`
- Apple Metal/MLX: `chronus.tensor.metal_backend`

No physical route can be promoted from package import, device name or CPU fallback. Device evidence must include exact source, driver/runtime identity, input/output parity and current timings.

## 6. Evidence preservation

Historical tests and benchmark records are retained in `evidence/migration/chronus_historical_evidence_register.json`. They are regression/provenance records, not current release passes.

## 7. Required current test commands

Focused close-out:

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

Full repository CI is required on the exact candidate commit. A release tag is accepted only when the exact `main` commit already has both a successful full `CI` push run and a successful attested qualification push run; missing provenance blocks publication.

## 8. Release classification

- **PRODUCTION_ADMITTED** — exact-current CI and every mandatory attested product gate PASS for the declared profile.
- **SOFTWARE_VERIFIED** — current software tests pass but one or more deployment/product gates remain open.
- **UNQUALIFIED** — a mandatory gate fails or supporting attestation is invalid.
- **EVIDENCE_GATED** — source is present but exact-current gate execution is not yet complete.

No other label overrides these states.
