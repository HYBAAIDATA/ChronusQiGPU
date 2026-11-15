# Chronus — Qualification and Claims Register

**Revision:** 15 November 2026 close-out branch. Source implementation, software verification, physical/deployment evidence and production admission remain separate states.

## Current claim register

| Claim | Implemented source | Exact-commit evidence | Current disposition |
| --- | --- | --- | --- |
| CO-001 Ed25519 signatures | `chronus.crypto.signers` | Current CI required | HELD until attested gate |
| CO-002 Dual Ed25519 + ML-DSA-65 | provider/verifier interfaces present | Current provider + interoperability evidence required | HELD until attested gate |
| RS-001 Signed receipt chain | receipt/chain implementations present | Current CI + replay evidence required | HELD until attested gate |
| RS-002 Deterministic durable replay | `chronus.storage.durable`, `chronus.triad` | New restart/corruption/journal tests added; CI run required | IMPLEMENTED — admission pending |
| FN-001 Customer-held external custody | provider interfaces exist, current remote providers still fall back locally | No current real external custody evidence | HELD |
| TRIAD durable local custody | `DurableTheseusService` | New current regressions added; CI run required | IMPLEMENTED — admission pending |
| OVID versioned transform/materialise | `chronus.ovid.transform` | New round-trip/digest tests added; CI run required | IMPLEMENTED — admission pending |
| CHRONUS selective tensor runtime | `chronus.tensor.folded_state`, `chronus.tensor.geodesic` | New migrated regressions added; CI run required | IMPLEMENTED — admission pending |
| Physical OpenCL tensor execution | `chronus.tensor.opencl_backend`, `chronus.kernels/tensor_ops.cl` | Current device-bound evidence unavailable on branch | IMPLEMENTED — hardware evidence open |
| Multi-region durability/failover | deployment-specific | No exact-current multi-region evidence | HELD |
| Regulatory/accreditation claims | none awarded by repository | external assessment required | HELD |

## Software-base qualification

The distributable `software-base` profile has a direct executable verifier in `scripts/ci/build_product_gates.py`. It evaluates the five mandatory gates from live software behavior rather than from labels or test counts:

- dual Ed25519 + ML-DSA-65 receipt verification;
- receipt tamper rejection;
- replay/reordering rejection;
- fail-closed claim-register validation;
- fresh-open THESEUS custody and journal continuity.

The product-gate JSON and the bounded test-evidence JSON are attested independently. `scripts/ci/evaluate_attested.py` binds both to the same commit/run and emits the profile verdict. A successful software-base verdict does **not** promote the external customer-held custody claim; that claim remains held until a deployment profile supplies its own verified external-custody fact.

## Gate binding

The executable claim mapping in `chronus.core.claims.CLAIM_GATES` binds claims to mandatory gates. A non-PASS gate or absent verified attestation keeps the associated claim held.

Mandatory gates:
- `CO-SIGN`
- `RS-RECEIPT`
- `RS-REPLAY`
- `FN-CLAIMS`
- `FN-CUSTODY`

## Release publication

`scripts/ci/require_release_qualification.py` is invoked before build/publication from `.github/workflows/release.yml`. It requires:

1. a successful full `CI` push run for the exact release commit on `main`;
2. a successful qualification push run for that same commit;
3. a verified GitHub attestation for the qualification verdict bound to the selected run;
4. `status=PASS`, no blockers, all mandatory gates PASS and the required claims for the declared profile supported;
5. verified ML-DSA-65 software signing and THESEUS custody facts for the declared profile.

A tag on an unqualified commit is therefore blocked before distribution build.

## Custody policy

Production qualification no longer depends on the caller supplying the string `azure-managed-hsm`. A provider label is not evidence.

`FN-CUSTODY` must be supported by an attested gate artifact that proves the actual custody mechanism required by the selected deployment profile. The current cloud/Vault/PKCS#11 compatibility providers still use local fallback behavior and therefore cannot independently satisfy that gate.

## Evidence ownership

GitHub Actions generates test and qualification evidence for the exact commit. The downstream evaluator verifies the artifact identity and GitHub attestation. Product-gate status is consumed only from a separately attested gate document tied to the same commit/run identity.

A successful unit test suite establishes its tested software scope; it does not automatically award a physical backend, deployment, security, availability or regulatory claim.

## Historical evidence

Historical tests and benchmark records are preserved in `evidence/migration/chronus_historical_evidence_register.json`. Their original results remain visible but do not become exact-current release evidence without rerun or explicit reconciliation.
