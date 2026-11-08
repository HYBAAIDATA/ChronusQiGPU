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