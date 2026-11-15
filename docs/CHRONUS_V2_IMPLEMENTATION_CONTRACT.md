# Chronus V2 — Implementation and Security Contract

**Source:** User-supplied Chronus V2 closeout implementation, 14 November 2026. This document describes the intended code and acceptance behavior; it does not claim the code has been deployed.

## Proposed source layout

- `src/chronus/core/facade.py`: real qualification gates, manifest serialization and exit code.
- `src/chronus/security/canonical.py`: deterministic, float-rejecting JSON serialization.
- `src/chronus/security/signers.py`: Ed25519 signing and verification; ML-DSA-65 explicitly non-conformant until implemented.
- `src/chronus/security/receipts.py`: signed hash-chained receipts and tamper detection.
- `src/chronus/security/kms.py`: explicit local-memory, file and unavailable PKCS#11 providers.
- `scripts/ci/purity_gate.py`: bounded source-scope scan with visible coverage.
- `tests/test_signers.py`, `tests/test_receipts.py`, `tests/test_facade.py`: regression tests.

## Qualification facade

Proposed gates: G1 signing algorithm conformance; G2 receipt round-trip, chain and tamper rejection; G3 canonical JSON determinism and float rejection; G4 purity scan over declared scope; G5 supported-claim evidence and reviewer presence.

A gate exception is a failure, never an implicit skip. An empty gate set must **not** qualify. Qualification must depend on all mandatory gates passing and on absence of blockers. The manifest must identify each gate, exact result, scope, timestamp, revision and evidence. No constant `PRODUCTION_QUALIFIED` or hardcoded invariant count is admissible.

## Cryptography and canonical bytes

Ed25519 implementation must be verified against RFC 8032 known-answer vectors, malformed signatures and public keys, subgroup/canonical-encoding edge cases, and an independent well-maintained cryptographic implementation. A passing self-test alone does not establish implementation security. Prefer a maintained vetted cryptographic library over a bespoke cryptographic implementation in production.

The proposed JSON function sorts keys, uses compact separators and rejects floats. **It is not automatically RFC 8785 conformant**; Unicode, number handling, type restrictions and canonicalization interoperability require separate qualification.

ML-DSA-65 and PKCS#11/HSM are **not implemented in the supplied source**. Their availability must be represented as false or fail-closed. Do not silently substitute Ed25519 for an ML-DSA policy requirement.

## Receipt and custody

Receipt fields include workload ID, tenant ID, result digest, node ID, sequence, issuance time, key ID, schema version, predecessor digest and backend. The signature covers a digest of canonical receipt bytes. Verification must reject payload tampering, signature tampering, sequence gaps, predecessor mismatch and untrusted keys.

The supplied in-memory receipt log is not durable custody. Production requires persistence, crash recovery, key rotation, offline verification with public keys, and replay from a new process. THESEUS remains the custody authority.

## Key providers

Local-memory keys are ephemeral; file keys persist but are not HSM-backed. File-provider implementation must defend against path traversal, symlinks, insecure file permissions, races and partial writes. PKCS#11 must fail closed until actually integrated.

## Purity scan

The proposed scan covers `execution/`, `backends/`, `storage/`, `security/`, and `quantum/` under `src/chronus/`. The scanner must report the actual directories and number of files scanned. A clean scan of this scope is **not** a clean scan of the entire product. Missing scope directories must fail.

## Proposed test commands

```bash
python -m pytest tests/test_signers.py tests/test_receipts.py tests/test_facade.py -q --tb=short
python -m chronus.core.facade
```

These commands are **not yet executable in this repository** until the corresponding modules and tests are committed.

## Acceptance gates

**PASS** = executed with retained evidence. **FAIL** = contradicted requirement. **NOT_RUN** = not executed. **BLOCKED** = missing prerequisite. A release is not qualified when a mandatory gate is FAIL, NOT_RUN or BLOCKED. The supplied expectation of four passes and one ML-DSA failure is a prediction, **not** a measured result.
