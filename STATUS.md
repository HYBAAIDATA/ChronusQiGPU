# ChronusQiGPU — production and release status

**Product / release decision: NOT QUALIFIED. Publication remains held.**

Review: 2026-11-15. Repository: `HYBAAIDATA/ChronusQiGPU`.
Baseline inspected: `main` at `dc920a82c38ee408fb9698d3206631139f9d0d97`. This page is an audit snapshot, **not** a live status API or release certificate.

## What is verified

- The repository contains real source and GitHub Actions pipelines; some reference, frontend, container and hardware-description checks pass. This is implementation/CI evidence, not physical-device or production acceptance.
- The baseline was red. The full-package CI, evidence and storage workflows failed at the reviewed SHA. A blank HYBA Mine workflow also produced failed runs.
- PR [#86](https://github.com/HYBAAIDATA/ChronusQiGPU/pull/86) consolidates source/CI baseline repair; [#83](https://github.com/HYBAAIDATA/ChronusQiGPU/pull/83) addresses cross-process SQLite cold start; [#72](https://github.com/HYBAAIDATA/ChronusQiGPU/pull/72) addresses offline-validated Braiins endpoint configuration; [#85](https://github.com/HYBAAIDATA/ChronusQiGPU/pull/85) closes the unsafe release-publication pathway **when merged and verified**.
- Local gate results and source-level checks must remain separate from GitHub-attested, exact-commit qualification. The legacy H1-H6 manifest and the historical `PRODUCTION_QUALIFIED.json` are **not** release authority.

## Outstanding qualification evidence

- Exact release-commit CI verdict and independently verified attestation: **UNAVAILABLE** until produced by the required workflow.
- Conformant signing, secure remote key custody, independent security review and signed approval: **UNAVAILABLE**.
- Physical-device correctness and reference differential, sustained soak/recovery and deployment controls: **UNAVAILABLE**.
- Literal Stratum pool acknowledgement and accepted-share evidence, where live mining is claimed: **UNAVAILABLE**.
- Production operations, rollback, support and customer acceptance evidence: **UNAVAILABLE**.

A passing pull-request suite removes a software regression; it does not change the product decision above. Do not publish or claim certification, FIPS 204 conformance, physical GPU performance, customer deployment or live mining without their own evidence and approved release.

## Authoritative references

- [Release blocker review, 15 November 2026](docs/release-blocker-audit-2026-11-15.md)
- [Release decision](RELEASE_DECISION_MCKINSEY_TECH.md)
- [Qualification and claims register](docs/QUALIFICATION_AND_CLAIMS.md)
- [Claim audit](docs/claim-audit.md)
- [GitHub Actions](https://github.com/HYBAAIDATA/ChronusQiGPU/actions)

Historical `STATUS.md` language asserting “100% PRODUCTION QUALIFIED” is withdrawn; it was not bound to the current branch, commit and runtime acceptance requirements.
