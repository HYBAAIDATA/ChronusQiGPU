# Packs, versioning, observability, and gate publication

## Implemented

- Shared signed PackManifest contract, Financial Services Industry Pack 1.0.0, four starter Assurance Packs, deterministic composition, and signed gap reports.
- Core change classification (MAJOR/MINOR/PATCH), forward-only schema migration steps, explicit v1→v2 and v2→v3 helpers, out-of-band ABI version checks, and compatibility predicates.
- Tenant-bound common metrics and traces, proof-cost accounting, measured-only resource truth, ten dashboard panels, constrained queries, and signed evidence export.
- Shared `make/gates.mk`, uniform file-backed gate results, eleven thin gate wrappers, roll-up enforcement, artifact upload, and GitHub Checks/status publication.
- The evidence workflow has `checks: write` and `statuses: write`; it publishes each result and then fails the workflow if any gate is FAIL/ERROR.

## Current local gate outcome

PASS: ABI, schema freeze, promotion manifest, claim register, envelope verification, import audit, refuted-claim scan.

SKIP (not evidence): cross-backend conformance and full resilience suite because required independent backends/tests are absent.

FAIL (honest blockers): Rule 7 no-float because the current exact math path contains an explicit `float` type check; privileged-path audit because no complete runtime mediation inventory exists.

A SKIP does not advance promotion. A published workflow is expected to remain failing until these blockers are fixed or formally re-scoped with approved evidence.

## ABI correction

The frozen 64-byte descriptor does not contain an independent version word. ABI version is therefore supplied out-of-band to `check_abi(version, buffer)`. Reading `buffer[0:4]` as a version would reinterpret D1 and corrupt the contract.

## Repository boundary

No `mla1517-core` repository currently exists. Its workflow is supplied only as an extraction template; it is not represented as installed or operational.

## Required repository configuration

- `GITHUB_TOKEN`: workflow-provided, with checks/statuses write permissions.
- `MLA1517_HSM_KEY_REF`: required at pilot for assembly signing.
- `MLA1517_IDP_ISSUER`: required at pilot for entitlement issuer integration.
- `MLA1517_WITNESS_KEY`: required at pilot for independently administered witness signing.
- A self-hosted OpenCL runner label/configuration is required for strict hardware CI.
