# Checkpoint verification integrity — 14 October 2026

Source inspected: PhiEnterprise1/EuclidPhiEnterprise main 6688e83c22d36dc16dfd5516e9e7d81959c84438.

## Implemented

- Every load and direct-mapping verification checks the manifest schema, seal, required sections, source revision and policy version.
- Verification uses an isolated finite-JSON snapshot, preventing later caller mutation from changing the verified mapping.
- Learner checkpoint hashes must be valid lowercase SHA-256 commitments.
- Supplied or recorded evidence paths require a hash and a matching existing file. A hash without a path is refused unless an explicit relocation path is supplied.
- Checkpoint-only verification explicitly returns evidence_verified=false. It is not a training-quality or promotion result.

A manifest hash is corruption detection, not a digital signature or deployment approval. The change preserves existing runtime and learning ownership; it does not introduce another learner or custody service.

## Executed evidence

The exact new dependency-free validator and regression file were exercised locally, without a model or pool test double:

```text
python -m unittest discover -s tests -p test_checkpoint_manifest_integrity.py -v
Ran 12 tests — OK
python -m compileall -q euclid tests
PASS
```

## Not executed

- Full package-import and checkpoint_manifest integration suite: NOT_RUN.
- Existing real-learner training/readiness and mining suites: NOT_RUN.
- Full repository CI and installed-package tests: NOT_RUN.
- Fresh-process trained checkpoint deployment and mining: NOT_RUN.
- Live pool connectivity, submission and acceptance: NOT_RUN.

The sandbox clone attempt failed with 'Could not resolve host: github.com'. Repository reads and writes used the authenticated GitHub MCP directly. That failure does not prevent this push, but limits checkout-wide local verification. This is one implemented integrity correction, not completion of the full intelligence-training/mining-readiness programme.
