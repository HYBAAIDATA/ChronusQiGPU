# Chronus release decision

**Status: NOT QUALIFIED. Any prior “GO,” “PRODUCTION_QUALIFIED,” or equivalent release decision is withdrawn.**

Review date: 2026-11-08  
Source reviewed: `a2768d11847de113d26535e33cfe9d4a79a009db` on `main`  
Review type: static source and documentation review; tests and deployments were not run.

## Decision basis

The repository contains a CPU reference implementation, service code, experimental adapters, and demo/simulated flows. This review did not establish a release-gate suite with current passing evidence, a production deployment, independent security assessment, physical accelerator results, regulatory authorization, or customer acceptance. Critical security labels in older documentation overstate the source: ML-DSA is not conformant, STARK/FRI soundness is not established, and KMS/HSM abstractions do not demonstrate real remote key custody. See the [claim-by-claim audit](docs/claim-audit.md).

| Gate | Current disposition |
|---|---|
| Reproducible release tests tied to this commit | Not demonstrated; not run in this review |
| Cryptographic conformance and independent security review | Not met / not demonstrated |
| Real KMS/HSM integration and key-custody evidence | Not demonstrated |
| Production deployment, reliability, and tenant isolation | Not demonstrated |
| Physical accelerator correctness and benchmark evidence | Not demonstrated |
| Compliance authorization/certification | Not demonstrated |
| Customer acceptance and operational support | Not demonstrated |
| Frontend build and live data integration | Not verified; apparent unresolved API-client import requires checking |

## Restrictions

Do not describe Chronus as production-qualified, certified, FIPS-compliant, independently audited, customer-deployed, or performance-validated. Do not reuse historical test counts, tenant counts, pricing, savings, valuations, or benchmark numbers as current evidence. Do not imply a McKinsey/Accenture affiliation or joint venture.

A future release decision requires a defined acceptance plan, verified current CI and build outputs, security and cryptographic review, real infrastructure and hardware evidence where applicable, documented operational controls, and approval by accountable owners. No gate is inferred as passed from the existence of source code or a workflow definition.

## Recheck — 15 November 2026

The original 8 November decision remains in force. A [repository and Actions recheck](docs/release-blocker-audit-2026-11-15.md) found failed baseline jobs, a blank HYBA Mine workflow, a release workflow that was not yet guarded by an independently verified commit-matched PASS verdict, and a legacy local-qualification generator with unsupported product-status and measurement fields.

Software correction PRs exist for the CI baseline (#86), SQLite initialization (#83), mining endpoint validation (#72), and attested release gate (#85). Their existence, test descriptions or success on a non-main head are **not** merge, production or release evidence. The full suite and review findings must be resolved on the exact heads and the resulting `main` commits.

The root `STATUS.md` and `PRODUCTION_QUALIFIED.json` now withdraw the old production assertion, while the legacy manifest generator records only local checks and never signs an unsupported production verdict. The separate attested `ci-verdict.json` qualification workflow is the required release authority; even its successful evaluation workflow is not a PASS unless its contents actually say PASS and are independently attested.

**Disposition remains NOT QUALIFIED / NO PUBLICATION.** Outstanding runtime, device, managed-key custody, independent security, live-pool and owner-approval artifacts remain unavailable until supplied and verified.
