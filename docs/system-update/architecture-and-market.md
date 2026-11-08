# Architecture and market assumptions

**Status:** repository-level description, not a deployment record or market validation. Source review snapshot: `a2768d11847de113d26535e33cfe9d4a79a009db`, 2026-11-08.

## Implementation that is present

Chronusv2 contains Python reference workloads for selected exact-math/Lucas-PV operations, service/API code, an SDK, and local persistence code. The default execution route is CPU reference code. An opt-in OpenCL adapter and other execution abstractions are present, but no physical accelerator execution or performance advantage was verified. SQLite is the default local workload store; this is not a distributed or highly available service. Additional components include in-memory or synthetic demonstration paths.

See the [current implementation assessment](current-state-assessment.md) for boundaries and the [claim audit](../claim-audit.md) for claim-by-claim dispositions.

## Product and market statements

Previously documented office locations, customer segments, sovereign deployments, partner status, pricing, savings, and market-size estimates are strategic assertions, not independently verified facts. They should not be stated as actual customers, deployments, validated demand, revenue, or market opportunity without primary evidence and appropriate review. No McKinsey/Accenture relationship or joint venture is asserted.

## Release posture

Chronusv2 is not release-qualified. The contents of this repository do not establish production operations, regulatory certification, enterprise security, external key custody, sound STARK/FRI verification, conformant FIPS-204 ML-DSA, or benchmarked hardware performance. Do not rely on old release/benchmark reports; they have been superseded or withdrawn.