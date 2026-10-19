# Guardian critical-gap implementation status

This change introduces executable, fail-closed contracts for the review gaps. It does not turn unmeasured surfaces into evidence.

## Implemented in this branch

- Full typed Guardian conjunction over exactly 5 modes, 7 topologies, and 6 intelligence surfaces.
- `FAIL` or failed Cassini/Zeckendorf/chain/lineage integrity denies; `UNKNOWN`/`UNAVAILABLE`, high anomaly, or unmeasured attestation degrades.
- Signed verdicts with executable signature verification.
- Authenticated-principal derivation from verified mTLS, OIDC, or SPIFFE evidence; actor headers are not authentication.
- Provider-neutral asymmetric/HSM entitlement boundary with audience, validity, capability, replay, revocation, and active-key checks.
- Independent signed witness receipts requiring at least one external anchor.
- Frozen 11-axis logical schema and separate 64-byte transport descriptor. The descriptor uses three reserved `uint32` words because `uint64 + 14*uint32 = 64`; the one-reserved-word draft did not total 64 bytes.
- Framework-neutral mediation policy for all declared privileged endpoint families.

## Miner-only exact execution increment

- Durable SQLite folded-object store using the repository's exact PULVINI implementation.
- Operator compatibility registry, exact reconstruction check, explicit rehydration flag, signed proof receipt, and lineage extension.
- Exact diagonal Pisot truncation domain with bond-limit and residual accounting. General exact SVD is explicitly unsupported and fails closed. Non-zero truncation cannot claim exact trace preservation.

## Evidence

`python -m unittest discover -s tests -v`: 9 tests passed locally for the added modules. `compileall` passed.

## Still blocked / not claimed

- Existing `ALHaras.complete()` and every HTTP entry point are not yet switched to the new conjunction evaluator.
- Native C PRIME-DB admission still needs an ABI-compatible D4/D5/D7 recomputation design plus migration of existing native fixtures.
- General exact SVD over `Q(sqrt(5))` is not implemented.
- External SIEM/WORM/TPM anchors, hardware-backed keys, physical MLA1517 execution, and independent verification are not established by these tests.
- PR promotion remains blocked until visible CI, required owner approvals, conflict-free update, and all repository suites pass.
