# PYTHIA resilience matrix

Generated from `governance/api_registry.yaml` + `governance/service_fabric.yaml` by `governance/render_service_fabric.py`. Do not edit by hand.

## Reliability tiers

| tier | meaning | rule |
| --- | --- | --- |
| R0 |  | if unavailable, the affected privileged operation stops |
| R1 |  |  |
| R2 |  | unavailability never causes another subsystem to impersonate the missing authority |
| R3 |  |  |
| R4 |  | loss of R4 must not corrupt R0-R2 semantics |

## Failure classes

| class | default HTTP | retryable | meaning |
| --- | --- | --- | --- |
| `INVALID_REQUEST` | 400 | False | request fails schema/shape validation |
| `UNAUTHORISED` | 401 | False | missing/invalid credentials |
| `FORBIDDEN` | 403 | False | authenticated but not authorised; AL HARAS deny |
| `DEPENDENCY_UNAVAILABLE` | 503 | True | declared dependency is down; bounded retry allowed |
| `TIMEOUT` | 504 | True | bounded wait exceeded; timeout never becomes success |
| `CONTRACT_MISMATCH` | 422 | False | response/result violates the declared contract |
| `VERSION_UNSUPPORTED` | 400 | False | unknown or unsupported schema/protocol major |
| `STALE` | 409 | True | job/request superseded by a newer generation |
| `INTEGRITY_FAILURE` | 500 | False | digest/proof/equivalence check failed |
| `CUSTODY_FAILURE` | 500 | False | THESEUS custody could not be taken or verified |
| `EXECUTION_FAILURE` | 500 | False | backend execution failed truthfully |
| `VERIFICATION_FAILURE` | 500 | False | certificate/proof verification failed |
| `EXTERNAL_REJECT` | 502 | False | external authority (pool) rejected |
| `RATE_LIMITED` | 429 | True | request rejected by a declared limit |
| `NOT_CONFIGURED` | 503 | False | capability exists but is not configured |
| `NOT_APPLICABLE` | 400 | False | operation not applicable to current state |
| `INTERNAL_ERROR` | 500 | False | unexpected failure; evidence retained |
| `NOT_FOUND` | 404 | False | no declared route/resource at this path |

## Circuit breakers

| dependency | implementation | states | rule |
| --- | --- | --- | --- |
| `chronus.remote_opencl_v2` | `chronus/mla1517/remote_gpu.py::RemoteCircuitBreaker` | CLOSED, OPEN, HALF_OPEN | prevents repeated failing calls; grants no fallback authority; re-verification still applies to every result |
| `stratum.v1` | `chronus/mla1517_platform/python/manifold_pool_coordinator.py::ManifoldPoolCoordinator (reconnect_delay budget, stale-work rejection)` | CLOSED, OPEN | submit gate stays closed through reconnect storms |

## Bulkheads

| resource | separation | proof |
| --- | --- | --- |
| HTTP worker threads | ThreadingHTTPServer threads are request-scoped; SSE consumers hold one thread each and are capped client-side; mining never waits on HTTP threads | `tests/test_fault_injection.py telemetry storm vs mining independence` |
| remote execution lane | remote_opencl_v2 failures are isolated to the remote lane; local solver lanes unaffected | `chronus/mla1517_platform/python/test_remote_gpu.py` |
| tenant quotas | hyba_db is tenant-scoped; cross-tenant bleed is a defect class tested in the store contract | `tests/test_production_api_contract.py::test_hyba_db_store_contract` |
| durable custody | THESEUS writes are independent of specialist computation failures; a failed TURING workload cannot block custody | `tests/test_fault_injection.py` |

## Backpressure

| interface | type | capacity | drop policy | exposed |
| --- | --- | --- | --- | --- |
| `pythia.telemetry.stream` | stream | per-client thread | non-authoritative events may be skipped under overload; drops are counted and exposed | ['dropped_count', 'window', 'reason'] |
| | authoritative rule | | never silently drop authoritative events | |
| `pythia.worker_heartbeat` | filesystem queue (sidecar files) | one file per worker | stale files excluded; nothing silently dropped | ['staleness', 'exclusion'] |
| `stratum.v1` | wire queue | — | stale jobs rejected by generation, not dropped silently | ['stale_count in worker metrics'] |

## Graceful-degradation matrix

| dependency | on unavailable | affected | impersonation allowed |
| --- | --- | --- | --- |
| `theseus.custody` | durable authoritative operation stops | pythia.mining.control, turing.vqc_pipeline, ovid.transform, kellogg.tensor.runtime, kellogg.tensor.execute, chronus.execution, salamander.control_plane, salamander.fault, euclid.orchestration | False |
| `al_haras.guardian` | privileged operation stops — guardian-mediated routes deny | pythia.mining.control, pythia.mining.evidence, al_haras.security.status, al_haras.security.subscribe, al_haras.security.evaluate, kellogg.tensor.capabilities, kellogg.tensor.execute, toe.collapse, namespace.policy, namespace.worker, namespace.recovery, namespace.admin, namespace.quantum, namespace.scale, namespace.assembly | False |
| `turing.vqc_pipeline` | return typed unavailable to PYTHIA/EUCLID plan; plan may select another authorised lane | euclid.orchestration | False |
| `kellogg.tensor.runtime` | tensor-dependent operation unavailable or authorised alternative expressly selected | euclid.orchestration, kellogg.tensor.capabilities, kellogg.tensor.execute | False |
| `ovid.transform` | transform-dependent operation reports typed failure to the plan | euclid.orchestration | False |
| `chronus.execution` | execution-dependent operation fails bounded; no fake execution | euclid.orchestration, pythia.gpu, pythia.hardware.status | False |
| `chronus.remote_opencl_v2` | remote lane reports unavailable; local lanes continue; circuit breaker bounds retries | chronus.execution | False |
| `stratum.v1` | preserve state, bounded reconnect, invalidate stale work correctly | pythia.mining.control, pythia.stratum.status, pythia.telemetry, pythia.telemetry.stream, pythia.metrics, pythia.status, pythia.ready_to_mine, pythia.agentic, pythia.cli.miner | False |
| `euclid.orchestration` | intelligence surfaces report unavailable; control POSTs refused | pythia.intelligence.status, pythia.intelligence.selftest, pythia.intelligence.maintenance, pythia.intelligence.autonomous, pythia.intelligence.engineer, pythia.intelligence.cognition_solve, pythia.agentic, pythia.campaign, pythia.knowledge, pythia.system.verify.read, pythia.system.verify.start, toe.collapse | False |
| `hyba_db.store` | tenant-scoped security state unavailable → guardian posture fails closed | al_haras.guardian, al_haras.security.status, al_haras.security.subscribe, al_haras.security.evaluate | False |
| `pythia.worker_heartbeat` | worker-derived surfaces degrade to unavailable sections; counters never fabricated | pythia.readiness, pythia.ready_to_mine, pythia.metrics, pythia.status, pythia.mining.control, pythia.mining.evidence, pythia.telemetry, pythia.telemetry.stream, pythia.agentic, pythia.campaign | False |
| `pythia.boot_audit` | audit reads show empty tail; mutations that must audit fail rather than proceed silently | pythia.readiness, pythia.status, pythia.audit.tail, pythia.system.map, pythia.config.update, pythia.intelligence.selftest, pythia.intelligence.maintenance, pythia.system.verify.start, pythia.cli.api | False |
| `pythia.runtime_config_file` | config surfaces report not_configured; updates reject atomically | pythia.config.read, pythia.config.update | False |
| `salamander.control_plane` | fault remediation commands refuse; healing stops, it does not improvise | salamander.fault | False |
| `pythia.health` | the serving process itself is down; every surface fails by connection refusal, never a body lie | legacy.api_health | False |

## Timeout & retry policy

- **rules** — ['never auto-retry an irreversible operation whose outcome is unknown', 'never auto-retry mining.submit unless protocol semantics make the duplicate safe', 'duplicate custody requests are deterministic/idempotent (content-addressed put)', 'read-only queries may use controlled bounded retry', {'retry storms are impossible': 'bounded attempts + backoff + jitter'}, 'timeout never becomes success']
- **defaults** — read: {'max_attempts': 3, 'backoff': 'exponential', 'jitter': True}; mutation: {'max_attempts': 1, 'idempotency': 'required-for-any-retry'}; irreversible: {'max_attempts': 1}
- **http_idempotency** — header: Idempotency-Key; behaviour: mutating POST/PUT routes honour a caller Idempotency-Key — a repeated key inside the retention window returns the recorded outcome without re-executing the mutation; retention_window_s: 300; implementation: chronus/mla1517_platform/python/control_api.py::_IDEMPOTENCY_RECORDS

## Health model

| surface | semantics |
| --- | --- |
| `LIVENESS` | process serving — pythia.health |
| `READINESS` | declared dependency/config readiness — pythia.readiness components |
| `DEPENDENCY_HEALTH` | per-component truth inside readiness (guardian, boot_audit, worker_heartbeat_dir, stratum, theseus where mounted) |
| `DOMAIN_READINESS` | capability readiness — pythia.ready_to_mine |
| `rule` | never collapse these into healthy=true |

