# Required external artifacts

The following artifacts must be supplied by the responsible owners and must
not be filled with synthetic or locally inferred values:

- `owner-approval.json`
- `device-certificate.json`
- `benchmark.json`
- `sbom.json`
- `provenance.json`
- `rollback-plan.json`
- `ci-verdict.json`
- `attestation-verification-receipt.json`

The authoritative release verifier requires the CI verdict and attestation to
be produced by the hosted workflow and bound to the exact source commit. The
remaining artifacts require their stated owner, provider, or deployment
environment. Until all are present and independently checked, the decision is
HOLD.

