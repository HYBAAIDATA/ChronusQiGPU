# PYTHIA API elevation — second-pass final gate

Generated from `governance/api_registry.yaml` + `governance/service_fabric.yaml` by `governance/render_service_fabric.py`. Do not edit by hand.

| gate | verdict | evidence |
| --- | --- | --- |
| A API constitution — every interface carries §2 fields | PASS | `tests/test_service_constitution.py` + registry schema `pythia.api_registry/2` |
| B Dependency graph machine+human readable | PASS | `service_fabric.yaml dependency_graph` + `docs/SERVICE_DEPENDENCY_GRAPH.md`; deps↔edges equality enforced |
| C Resilience matrix — tiers, breakers, bulkheads, backpressure, degradation | PASS | `docs/RESILIENCE_MATRIX.md` rendered from fabric; breakers resolve to real implementations |
| D SLO scorecard — measured only | PASS | `docs/SLO_SCORECARD.md`; measured column reports observed evidence classes (1 SLOs UNMEASURED), no compliance claimed |
| E Fault-injection evidence | PASS | 12/13 scenarios EXECUTED; M3 rows declared M3_UNAVAILABLE |
| F Recovery evidence | PASS | 5/6 scenarios EXECUTED; RTO/RPO declared UNMEASURED where not measured |
| G Contract drift report | PASS | `docs/CONTRACT_DRIFT_REPORT.md` — zero unexplained divergence enforced by the constitution suite |
| H M3 API evidence pack | GATED | No M3 hardware in this environment — recorded as M3_UNAVAILABLE, never simulated |
| Frozen authority register | PASS | `authority_register` unchanged; FROZEN_AUTHORITY_REGISTER gate intact |
| No masquerading subsystem | PASS | `impersonation_allowed: false` on every degradation row; reserved namespaces deny at the boundary |
| Failure taxonomy on the wire | PASS | `failure_taxonomy` enum == fabric enum; every error body carries `failure_class` (live-asserted) |
| Correlation envelope | PASS | X-Request-Id/X-Correlation-Id/X-Causation-Id emitted on every response incl. denials |
| Idempotency for mutating HTTP | PASS | Idempotency-Key replay, 300s window, `_IDEMPOTENCY_RECORDS` |
| Circuit breaker on remote execution | PASS | `RemoteCircuitBreaker` OPEN/HALF_OPEN/CLOSED exercised against a dead endpoint |
| Contract mutation gate | PASS | `ConstitutionMutationGateTests` — tampered copies surface violations |
| Consumer-driven contract checks | PASS | `ConsumerContractTests` |
| Rendered docs byte-locked | PASS | `--check` modes of both renderers asserted in the contract suite |

**Gated items:** M3 evidence requires M3 hardware — absent here, so the
gate is honestly GATED rather than claimed.

