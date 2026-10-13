# PYTHIA production API & service-communication contract

Generated from [`governance/api_registry.yaml`](../governance/api_registry.yaml) —
the machine-readable canonical registry — by `governance/render_api_contract.py`.
Do not edit by hand; change the registry and re-render.

The implementation is tested against this contract by
`tests/test_production_api_contract.py`: route parity, live HTTP voyages,
auth-class enforcement, reserved-namespace non-masquerade, internal
contracts, and mutation self-tests proving the gate detects drift.

Schema `pythia.api_registry/2` elevates this registry to the service
constitution: every interface carries authority, tier, SLO, dependency,
fallback, security, observability, lifecycle and evidence declarations.
`governance/service_fabric.yaml` holds the shared fabric (failure
taxonomy, dependency graph, journeys, SLOs, degradation matrix, recovery
objectives); `tests/test_service_constitution.py` enforces it.

## Canonical authority register

| Authority | Owns |
| --- | --- |
| EUCLID | intelligence orchestration |
| PYTHIA | predictive/causal intelligence, mining intelligence, final SearchPlan |
| TURING | independent VQC |
| KELLOGG | tensor capability |
| CHRONUS | heterogeneous execution |
| THESEUS | durable custody, integrity, continuity, records, recovery, provenance |
| OVID | representation/state transformation and transform lineage |
| SALAMANDER | bounded self-healing and optimisation |
| AL_HARAS | security, identity, capability, authorisation, governance |
| SHA256D_VERIFIER | candidate validity |
| POOL | external share acceptance |
| HYBA_DB | tenant-scoped ontology/query/projection persistence |

## Cross-cutting envelope

* Every HTTP response carries `X-Request-Id` — the caller's
  `X-Request-Id`/`X-Correlation-Id` is echoed when it is a sane token,
  otherwise a fresh id is minted. Denials are never exempt.
* JSON bodies carry `schema_version` where the entry declares one.
* Every mutating route is behind `OPERATOR_PRINCIPAL` or
  `AL_HARAS_SUBSCRIPTION`; guardian-mediated routes return signed
  denial receipts rather than bare error codes.
* `unavailable`/`not_configured`/`armed_no_device` are first-class
  honest states, never masked as success.

## Unauthenticated read-only operational truth

### `pythia.health` — PYTHIA

**Routes**

- `GET /api/v1/healthz`
- `GET /api/health`
- `GET /healthz`

| Field | Value |
| --- | --- |
| Capability | process liveness probe |
| Interface | HTTP_PUBLIC |
| Implementation | `chronus/mla1517_platform/python/control_api.py::_route_get` |
| Consumers | operator-console, load-balancer |
| Authority | PYTHIA |
| Reliability tier | R4 |
| Lifecycle | STABLE |
| SLO | `slo.projection.read` |
| Auth | NONE |
| Authorisation authority | none |
| Truth class | LIVENESS |
| Request | none |
| Response | {schema_version, status, generated_at} |
| Timeout | immediate |
| Idempotency | read-only |
| Retry | freely retryable |
| Failure semantics | process down = connection refused; never a body lie |
| Availability semantics | serving process implies live |
| Fallback policy | none — a live process is the truth; load balancer sees connection state |
| Dependencies | none |
| Security classification | PUBLIC_READ |
| Observability | golden_signals |
| Compatibility window | compatible within chronus.mla1517.status/1 |
| Support owner | PYTHIA |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | none |
| Custody | none |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py` |

### `pythia.readiness` — PYTHIA

**Routes**

- `GET /api/v1/readyz`
- `GET /readyz`

| Field | Value |
| --- | --- |
| Capability | declared dependency/config readiness |
| Interface | HTTP_PUBLIC |
| Implementation | `chronus/mla1517_platform/python/control_api.py::_route_get` |
| Consumers | operator-console, load-balancer |
| Authority | PYTHIA |
| Reliability tier | R4 |
| Lifecycle | STABLE |
| SLO | `slo.projection.read` |
| Auth | NONE |
| Authorisation authority | none |
| Truth class | READINESS |
| Request | none |
| Response | {schema_version, ready, reason, components{identity,boot_audit,worker_heartbeat_dir,guardian,runtime_config,stratum,remote_opencl,custody}, generated_at} |
| Timeout | immediate |
| Idempotency | read-only |
| Retry | freely retryable |
| Failure semantics | 503 {ready:false, reason} when identity/config not ready |
| Availability semantics | NOT hardware or pool-acceptance readiness |
| Fallback policy | component-level truth; missing component reports not-ready, never ready |
| Dependencies | `pythia.worker_heartbeat`, `pythia.boot_audit`, `al_haras.guardian` |
| Security classification | PUBLIC_READ |
| Observability | golden_signals |
| Compatibility window | compatible within chronus.mla1517.ready/1 |
| Support owner | PYTHIA |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | none |
| Custody | none |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py`, `chronus/mla1517_platform/python/test_phase4_api.py` |

### `pythia.ready_to_mine` — PYTHIA

**Routes**

- `GET /api/v1/ready-to-mine`
- `GET /ready-to-mine`

| Field | Value |
| --- | --- |
| Capability | domain readiness for mining start |
| Interface | HTTP_PUBLIC |
| Implementation | `chronus/mla1517_platform/python/control_api.py::status_payload` |
| Consumers | operator-console |
| Authority | PYTHIA |
| Reliability tier | R4 |
| Lifecycle | STABLE |
| SLO | `slo.projection.read` |
| Auth | NONE |
| Authorisation authority | none |
| Truth class | RUNTIME_OBSERVATION |
| Request | none |
| Response | {ready, reason, blockers, schema_version, generated_at} |
| Timeout | immediate |
| Idempotency | read-only |
| Retry | freely retryable |
| Failure semantics | 503 when not ready; reasons enumerated never faked |
| Availability semantics | requires observed pool transport + live worker |
| Fallback policy | reports blocked/unavailable truthfully; never substitutes a ready verdict |
| Dependencies | `stratum.v1`, `pythia.worker_heartbeat` |
| Security classification | PUBLIC_READ |
| Observability | golden_signals |
| Compatibility window | compatible within declared schema |
| Support owner | PYTHIA |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | none |
| Custody | none |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py`, `chronus/mla1517_platform/python/test_phase4_api.py` |

### `pythia.metrics` — PYTHIA

**Routes**

- `GET /api/v1/metrics`
- `GET /metrics`

| Field | Value |
| --- | --- |
| Capability | measured operational counters |
| Interface | HTTP_PUBLIC |
| Implementation | `chronus/mla1517_platform/python/control_api.py::metrics_payload` |
| Consumers | prometheus, operator-console |
| Authority | PYTHIA |
| Reliability tier | R4 |
| Lifecycle | STABLE |
| SLO | `slo.projection.read` |
| Auth | NONE |
| Authorisation authority | none |
| Truth class | RUNTIME_OBSERVATION |
| Request | none |
| Response | text/plain; version=0.0.4 (prometheus exposition) |
| Timeout | immediate |
| Idempotency | read-only |
| Retry | freely retryable |
| Failure semantics | counters only ever increase truthfully |
| Availability semantics | absent metric = not measured |
| Fallback policy | absent workers excluded; never zeroed fabrication |
| Dependencies | `pythia.worker_heartbeat`, `stratum.v1` |
| Security classification | PUBLIC_READ |
| Observability | golden_signals |
| Compatibility window | additive fields only within schema version |
| Support owner | PYTHIA |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | none |
| Custody | none |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py` |

### `pythia.static_spa` — PYTHIA

**Routes**

- `GET /*`

| Field | Value |
| --- | --- |
| Capability | operator SPA static assets |
| Interface | HTTP_PUBLIC |
| Implementation | `chronus/mla1517_platform/python/control_api.py::_static_or_404` |
| Consumers | browser |
| Authority | PYTHIA |
| Reliability tier | R4 |
| Lifecycle | STABLE |
| SLO | `slo.projection.read` |
| Auth | NONE |
| Authorisation authority | none |
| Truth class | LIVENESS |
| Request | none |
| Response | static file bytes |
| Timeout | immediate |
| Idempotency | read-only |
| Retry | freely retryable |
| Failure semantics | real 404 JSON for unrouted /api/*; SPA index only for app paths; path traversal contained to web_root |
| Availability semantics | files served exactly as built |
| Fallback policy | missing build reports 404 on assets; api paths never serve index |
| Dependencies | none |
| Security classification | PUBLIC_READ |
| Observability | none |
| Compatibility window | asset paths only |
| Support owner | PYTHIA |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | none |
| Custody | none |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py` |

## Operator-console surface

### `pythia.status` — PYTHIA

**Routes**

- `GET /api/v1/mla1517/status`

| Field | Value |
| --- | --- |
| Capability | operator runtime status projection |
| Interface | HTTP_OPERATOR |
| Implementation | `chronus/mla1517_platform/python/control_api.py::status_payload` |
| Consumers | frontend SystemFabricPanel, operator-console |
| Authority | PYTHIA |
| Reliability tier | R4 |
| Lifecycle | STABLE |
| SLO | `slo.projection.read` |
| Auth | NONE |
| Authorisation authority | none |
| Truth class | RUNTIME_OBSERVATION |
| Request | none |
| Response | {schema_version, backend, host, canonicalEngine, workers, stratum, ready_to_mine, generated_at} |
| Timeout | immediate |
| Idempotency | read-only |
| Retry | freely retryable |
| Failure semantics | worker states degrade to their honest last-known/disabled state |
| Availability semantics | device/backend fields reflect probes, not aspiration |
| Fallback policy | degrades to unavailable sections; no synthetic backend state |
| Dependencies | `pythia.worker_heartbeat`, `stratum.v1`, `pythia.boot_audit` |
| Security classification | PUBLIC_READ |
| Observability | golden_signals |
| Compatibility window | additive fields only within schema version |
| Support owner | PYTHIA |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | none |
| Custody | none |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py`, `chronus/mla1517_platform/python/test_phase4_api.py` |

### `pythia.config.read` — PYTHIA

**Routes**

- `GET /api/v1/config`

| Field | Value |
| --- | --- |
| Capability | redacted runtime configuration view |
| Interface | HTTP_OPERATOR |
| Implementation | `chronus/mla1517_platform/python/control_api.py::_config_public_payload` |
| Consumers | frontend RuntimeControlPanel, frontend SystemFabricPanel |
| Authority | PYTHIA |
| Reliability tier | R4 |
| Lifecycle | STABLE |
| SLO | `slo.projection.read` |
| Auth | NONE |
| Authorisation authority | none |
| Truth class | CONFIGURATION |
| Request | none |
| Response | runtime_config.public_view(cfg): pools redacted of passwords |
| Timeout | immediate |
| Idempotency | read-only |
| Retry | freely retryable |
| Failure semantics | pool passwords never serialised in the public view |
| Availability semantics | reflects declared config, not observed pool state |
| Fallback policy | secrets always redacted; missing config reports not_configured |
| Dependencies | `pythia.runtime_config_file` |
| Security classification | PUBLIC_READ |
| Observability | golden_signals |
| Compatibility window | additive fields only; secret keys never appear |
| Support owner | PYTHIA |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | none |
| Custody | none |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py` |

### `pythia.config.update` — PYTHIA

**Routes**

- `PUT /api/v1/config`

| Field | Value |
| --- | --- |
| Capability | operator runtime configuration mutation |
| Interface | HTTP_OPERATOR |
| Implementation | `chronus/mla1517_platform/python/control_api.py::_config_put` |
| Consumers | frontend RuntimeControlPanel |
| Authority | PYTHIA |
| Reliability tier | R1 |
| Lifecycle | STABLE |
| SLO | `slo.operator.mutation` |
| Auth | OPERATOR_PRINCIPAL |
| Authorisation authority | PYTHIA |
| Truth class | COMMAND_ACCEPTANCE |
| Request | subset of {pools, solvers, hashrate, window, campaign, live_submit}; unknown sections rejected |
| Response | {ok, applied:{spawned,retired,restarted,note?}, config} |
| Timeout | immediate |
| Idempotency | section-merge semantics; replaying the same body is a no-op |
| Retry | safe to retry identical body |
| Failure semantics | 400 unknown section / invalid value; 401/403 unauthenticated; closed when no key configured |
| Availability semantics | applied.note reports armed_no_device honestly |
| Fallback policy | invalid config rejected atomically; partial write never committed |
| Dependencies | `pythia.runtime_config_file`, `pythia.boot_audit` |
| Security classification | OPERATOR_AUTHENTICATED |
| Observability | audit_trail |
| Compatibility window | compatible within declared schema; unknown sections rejected |
| Support owner | PYTHIA |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | writes data/runtime_config.json; restarts running arms when a device is bound |
| Custody | append-only audit event runtime_config_applied |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py`, `chronus/mla1517_platform/python/test_control_auth.py` |

### `pythia.control.session` — PYTHIA

**Routes**

- `GET /api/v1/control/session`

| Field | Value |
| --- | --- |
| Capability | report server-authenticated principal for session |
| Interface | HTTP_OPERATOR |
| Implementation | `chronus/mla1517_platform/python/control_api.py::_control_session` |
| Consumers | frontend |
| Authority | PYTHIA |
| Reliability tier | R4 |
| Lifecycle | STABLE |
| SLO | `slo.projection.read` |
| Auth | OPERATOR_PRINCIPAL |
| Authorisation authority | PYTHIA |
| Truth class | COMMAND_ACCEPTANCE |
| Request | none |
| Response | {schema_version, ok, principal_id, role, source, generated_at} |
| Timeout | immediate |
| Idempotency | read-only |
| Retry | freely retryable |
| Failure semantics | 401 unauthenticated / 403 unauthorized |
| Availability semantics | reflects authenticated principal identity |
| Fallback policy | refusal never echoes bearer tokens; never infers identity locally |
| Dependencies | `pythia.boot_audit` |
| Security classification | OPERATOR_AUTHENTICATED |
| Observability | audit_trail |
| Compatibility window | compatible within declared schema |
| Support owner | PYTHIA |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | none |
| Custody | append-only audit event control_session or control_session_refused |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py`, `chronus/mla1517_platform/python/test_control_auth.py` |

### `pythia.system.map` — PYTHIA

**Routes**

- `GET /api/v1/system/map`

| Field | Value |
| --- | --- |
| Capability | system topology projection |
| Interface | HTTP_OPERATOR |
| Implementation | `chronus/mla1517_platform/python/system_fabric.py::forensic_map` |
| Consumers | frontend SystemFabricPanel |
| Authority | PYTHIA |
| Reliability tier | R4 |
| Lifecycle | STABLE |
| SLO | `slo.projection.read` |
| Auth | NONE |
| Authorisation authority | none |
| Truth class | RUNTIME_OBSERVATION |
| Request | none |
| Response | forensic map of subsystems with truth-class fields |
| Timeout | immediate |
| Idempotency | read-only |
| Retry | freely retryable |
| Failure semantics | unknown subsystems report unavailable, never invented |
| Availability semantics | reflects live probes (opencl count, mmio, credentials) |
| Fallback policy | map reflects declared registry, not invented services |
| Dependencies | `pythia.boot_audit` |
| Security classification | PUBLIC_READ |
| Observability | golden_signals |
| Compatibility window | additive fields only |
| Support owner | PYTHIA |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | none |
| Custody | none |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py` |

### `pythia.system.verify.read` — PYTHIA

**Routes**

- `GET /api/v1/system/verify`

| Field | Value |
| --- | --- |
| Capability | verification run status projection |
| Interface | HTTP_OPERATOR |
| Implementation | `chronus/mla1517_platform/python/system_fabric.py::verification_status` |
| Consumers | frontend SystemFabricPanel |
| Authority | PYTHIA |
| Reliability tier | R4 |
| Lifecycle | STABLE |
| SLO | `slo.projection.read` |
| Auth | NONE |
| Authorisation authority | none |
| Truth class | RUNTIME_OBSERVATION |
| Request | none |
| Response | per-component verification state machine |
| Timeout | immediate |
| Idempotency | read-only |
| Retry | freely retryable |
| Failure semantics | component states reported individually |
| Availability semantics | per-component states READY/DEGRADED/UNAVAILABLE/NOT_CONFIGURED/NOT_APPLICABLE/FAILED |
| Fallback policy | missing run reports not_found |
| Dependencies | `euclid.orchestration`, `pythia.boot_audit` |
| Security classification | PUBLIC_READ |
| Observability | golden_signals |
| Compatibility window | additive fields only |
| Support owner | PYTHIA |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | none |
| Custody | none |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py` |

### `pythia.system.verify.start` — PYTHIA

**Routes**

- `POST /api/v1/system/verify`

| Field | Value |
| --- | --- |
| Capability | start a system verification run |
| Interface | HTTP_OPERATOR |
| Implementation | `chronus/mla1517_platform/python/system_fabric.py::start_verification` |
| Consumers | frontend SystemFabricPanel |
| Authority | PYTHIA |
| Reliability tier | R1 |
| Lifecycle | STABLE |
| SLO | `slo.operator.mutation` |
| Auth | OPERATOR_PRINCIPAL |
| Authorisation authority | PYTHIA |
| Truth class | COMMAND_ACCEPTANCE |
| Request | {} |
| Response | {ok, state} |
| Timeout | immediate (runner is async) |
| Idempotency | 409 runner_busy while running |
| Retry | do not retry on 409; poll GET instead |
| Failure semantics | 409 runner_busy; 400 invalid; 401/403 unauthenticated |
| Availability semantics | acceptance only — not a pass claim |
| Fallback policy | busy state is a truthful conflict, not queued fiction |
| Dependencies | `euclid.orchestration`, `pythia.boot_audit` |
| Security classification | OPERATOR_AUTHENTICATED |
| Observability | audit_trail |
| Compatibility window | compatible within declared schema |
| Support owner | PYTHIA |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | starts the verification runner |
| Custody | audit event via runner record |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py` |

### `pythia.intelligence.status` — EUCLID

**Routes**

- `GET /api/v1/intelligence/status`
- `GET /api/v1/intelligence/cognition/status`

| Field | Value |
| --- | --- |
| Capability | EUCLID status projection |
| Interface | HTTP_OPERATOR |
| Implementation | `chronus/mla1517_platform/python/system_fabric.py::intelligence_status` |
| Consumers | frontend IntelligenceView |
| Authority | EUCLID |
| Reliability tier | R4 |
| Lifecycle | STABLE |
| SLO | `slo.projection.read` |
| Auth | NONE |
| Authorisation authority | none |
| Truth class | RUNTIME_OBSERVATION |
| Request | none |
| Response | intelligence status with first-class euclid_cognition projection; cognition/status returns pythia.euclid.cognition/1 directly |
| Timeout | immediate |
| Idempotency | read-only |
| Retry | freely retryable |
| Failure semantics | unavailable intelligence reports unavailable |
| Availability semantics | mirrors runner state |
| Fallback policy | unavailable EUCLID reports unavailable |
| Dependencies | `euclid.orchestration` |
| Security classification | PUBLIC_READ |
| Observability | golden_signals |
| Compatibility window | additive fields only |
| Support owner | EUCLID |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | none |
| Custody | none |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py` |

### `pythia.intelligence.selftest` — EUCLID

**Routes**

- `GET /api/v1/intelligence/selftest`
- `POST /api/v1/intelligence/selftest`

| Field | Value |
| --- | --- |
| Capability | EUCLID self-test status/run |
| Interface | HTTP_OPERATOR |
| Implementation | `chronus/mla1517_platform/python/system_fabric.py::selftest_status / start_selftest` |
| Consumers | frontend IntelligenceView, frontend SystemFabricPanel |
| Authority | EUCLID |
| Reliability tier | R2 |
| Lifecycle | STABLE |
| SLO | `slo.specialist` |
| Auth | GET: NONE; POST: OPERATOR_PRINCIPAL |
| Authorisation authority | PYTHIA |
| Truth class | GET: RUNTIME_OBSERVATION; POST: COMMAND_ACCEPTANCE |
| Request | POST {} |
| Response | runner status / {ok, state} |
| Timeout | immediate (async runner) |
| Idempotency | 409 runner_busy |
| Retry | poll GET; do not repost on 409 |
| Failure semantics | unavailable subsystem reports unavailable, not pass |
| Availability semantics | self-test verdict is the runner's real result |
| Fallback policy | self-test failure is a verdict, never masked |
| Dependencies | `euclid.orchestration`, `pythia.boot_audit` |
| Security classification | PUBLIC_READ |
| Observability | audit_trail |
| Compatibility window | compatible within declared schema |
| Support owner | EUCLID |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | POST starts the self-test runner |
| Custody | runner record |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py` |

### `pythia.intelligence.maintenance` — EUCLID

**Routes**

- `GET /api/v1/intelligence/maintenance`
- `POST /api/v1/intelligence/maintenance/start`
- `POST /api/v1/intelligence/maintenance/run`
- `POST /api/v1/intelligence/maintenance/stop`

| Field | Value |
| --- | --- |
| Capability | EUCLID maintenance status/run |
| Interface | HTTP_OPERATOR |
| Implementation | `chronus/mla1517_platform/python/system_fabric.py::self_repair_status, start_self_repair, run_self_repair_now, stop_self_repair` |
| Consumers | frontend IntelligenceView |
| Authority | EUCLID |
| Reliability tier | R2 |
| Lifecycle | STABLE |
| SLO | `slo.specialist` |
| Auth | GET: NONE; POST: OPERATOR_PRINCIPAL |
| Authorisation authority | PYTHIA |
| Truth class | GET: RUNTIME_OBSERVATION; POST: COMMAND_ACCEPTANCE |
| Request | {} |
| Response | {ok, state, detail?} |
| Timeout | immediate |
| Idempotency | start/run 409 runner_busy; stop idempotent |
| Retry | stop retryable; start/run not while busy |
| Failure semantics | 409 runner_busy |
| Availability semantics | diagnosis state is the real runner state |
| Fallback policy | maintenance outcome is truthful |
| Dependencies | `euclid.orchestration`, `pythia.boot_audit` |
| Security classification | PUBLIC_READ |
| Observability | audit_trail |
| Compatibility window | compatible within declared schema |
| Support owner | EUCLID |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | maintenance cycle (read-only diagnosis by default) |
| Custody | runner record |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py`, `chronus/mla1517_platform/python/test_phase4_api.py` |

### `pythia.intelligence.autonomous` — EUCLID

**Routes**

- `GET /api/v1/intelligence/autonomous`
- `POST /api/v1/intelligence/autonomous/trigger`

| Field | Value |
| --- | --- |
| Capability | EUCLID autonomous loop status/control |
| Interface | HTTP_OPERATOR |
| Implementation | `chronus/mla1517_platform/python/system_fabric.py::autonomous_supervisor_status, autonomous_supervisor.trigger_cycle` |
| Consumers | operator-console |
| Authority | EUCLID |
| Reliability tier | R2 |
| Lifecycle | STABLE |
| SLO | `slo.specialist` |
| Auth | GET: NONE; POST: OPERATOR_PRINCIPAL |
| Authorisation authority | PYTHIA |
| Truth class | GET: RUNTIME_OBSERVATION; POST: COMMAND_ACCEPTANCE |
| Request | POST {} |
| Response | supervisor status / trigger result |
| Timeout | supervisor cycle bound |
| Idempotency | serialised by supervisor lock |
| Retry | do not retry a trigger while a cycle is in flight |
| Failure semantics | error class surfaced, never silent |
| Availability semantics | reports real cycle outcome |
| Fallback policy | loop state is observed, not assumed |
| Dependencies | `euclid.orchestration` |
| Security classification | PUBLIC_READ |
| Observability | audit_trail |
| Compatibility window | compatible within declared schema |
| Support owner | EUCLID |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | POST runs one supervisor cycle synchronously |
| Custody | supervisor record |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py` |

### `pythia.intelligence.engineer` — EUCLID

**Routes**

- `GET /api/v1/intelligence/engineer/status`
- `POST /api/v1/intelligence/engineer/ask`

| Field | Value |
| --- | --- |
| Capability | EUCLID repo-engineer command |
| Interface | HTTP_OPERATOR |
| Implementation | `chronus/mla1517_platform/python/system_fabric.py::repo_engineer_status, start_repo_engineer` |
| Consumers | frontend IntelligenceView |
| Authority | EUCLID |
| Reliability tier | R2 |
| Lifecycle | STABLE |
| SLO | `slo.specialist` |
| Auth | GET: NONE; POST: OPERATOR_PRINCIPAL |
| Authorisation authority | PYTHIA |
| Truth class | COMMAND_ACCEPTANCE |
| Request | POST {prompt: 1..2000 chars} |
| Response | {ok, state} / readiness block |
| Timeout | immediate (async runner) |
| Idempotency | 409 runner_busy |
| Retry | do not retry on 409 |
| Failure semantics | 503 repo_engineer_not_configured with readiness detail; 400 invalid prompt |
| Availability semantics | NOT_CONFIGURED is a first-class answer |
| Fallback policy | not_configured is a first-class refusal |
| Dependencies | `euclid.orchestration` |
| Security classification | PUBLIC_READ |
| Observability | audit_trail |
| Compatibility window | compatible within declared schema |
| Support owner | EUCLID |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | dispatches a governed repo-engineer prompt (read-only execution) |
| Custody | runner record |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py`, `chronus/mla1517_platform/python/test_phase4_api.py` |

### `pythia.intelligence.cognition_solve` — EUCLID

**Routes**

- `POST /api/v1/intelligence/cognition/solve`

| Field | Value |
| --- | --- |
| Capability | EUCLID deterministic solve verdict |
| Interface | HTTP_OPERATOR |
| Implementation | `chronus/mla1517_platform/python/system_fabric.py::euclid_cognition_solve` |
| Consumers | operator-console |
| Authority | EUCLID |
| Reliability tier | R2 |
| Lifecycle | STABLE |
| SLO | `slo.specialist` |
| Auth | OPERATOR_PRINCIPAL |
| Authorisation authority | PYTHIA |
| Truth class | VERDICT |
| Request | {problem_id, goal, problem_class?, structure?[], observations?[], strategy?, initial_code?} |
| Response | {ok, available, ...cognition trace} |
| Timeout | episode bound |
| Idempotency | none — each call is a new episode |
| Retry | retryable; each retry is a distinct episode |
| Failure semantics | 503 {available:false} when EUCLID runtime unavailable; 400 missing problem_id/goal |
| Availability semantics | available:false is honest, not a failure mask |
| Fallback policy | unproven stays unproven |
| Dependencies | `euclid.orchestration` |
| Security classification | OPERATOR_AUTHENTICATED |
| Observability | golden_signals |
| Compatibility window | compatible within declared schema |
| Support owner | EUCLID |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | executes one EUCLID cognition episode |
| Custody | cognition trace in audit where durable |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py` |

### `pythia.agentic` — EUCLID

**Routes**

- `GET /api/v1/agentic/status`
- `POST /api/v1/agentic/start`
- `POST /api/v1/agentic/stop`

| Field | Value |
| --- | --- |
| Capability | agentic mining orchestration status/control |
| Interface | HTTP_OPERATOR |
| Implementation | `chronus/mla1517_platform/python/system_fabric.py::agentic_status, start_agentic, AGENTIC.stop` |
| Consumers | frontend SystemFabricPanel, frontend IntelligenceView |
| Authority | EUCLID |
| Reliability tier | R1 |
| Lifecycle | STABLE |
| SLO | `slo.mining.control` |
| Auth | GET: NONE; POST: OPERATOR_PRINCIPAL |
| Authorisation authority | PYTHIA |
| Truth class | GET: RUNTIME_OBSERVATION; POST: COMMAND_ACCEPTANCE |
| Request | start {count?: int (default 128), cycles?: int (default 3)} |
| Response | runner status / {ok, state} |
| Timeout | immediate (async) |
| Idempotency | start 409 runner_busy; stop idempotent |
| Retry | stop retryable |
| Failure semantics | 409 runner_busy |
| Availability semantics | runner state is truth |
| Fallback policy | no fabricated mining state; stopped stays stopped |
| Dependencies | `euclid.orchestration`, `pythia.worker_heartbeat`, `stratum.v1` |
| Security classification | PUBLIC_READ |
| Observability | audit_trail |
| Compatibility window | compatible within declared schema |
| Support owner | EUCLID |
| Runtime evidence | LOCAL_CROSS_SERVICE_EXECUTED |
| Side effects | starts/stops the agentic runner |
| Custody | runner record |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py` |

### `pythia.campaign` — EUCLID

**Routes**

- `GET /api/v1/campaign/status`
- `POST /api/v1/campaign/start`
- `POST /api/v1/campaign/stop`

| Field | Value |
| --- | --- |
| Capability | mining campaign status/control |
| Interface | HTTP_OPERATOR |
| Implementation | `chronus/mla1517_platform/python/system_fabric.py::campaign_status, start_campaign, CAMPAIGN.stop` |
| Consumers | frontend SystemFabricPanel |
| Authority | EUCLID |
| Reliability tier | R1 |
| Lifecycle | STABLE |
| SLO | `slo.mining.control` |
| Auth | GET: NONE; POST: OPERATOR_PRINCIPAL |
| Authorisation authority | PYTHIA |
| Truth class | GET: RUNTIME_OBSERVATION; POST: COMMAND_ACCEPTANCE |
| Request | {} |
| Response | runner status / {ok, state} |
| Timeout | immediate (async) |
| Idempotency | start 409 runner_busy; stop idempotent |
| Retry | stop retryable |
| Failure semantics | 409 runner_busy |
| Availability semantics | arm counters measured from live sidecars only |
| Fallback policy | campaign counters come from worker metrics only |
| Dependencies | `euclid.orchestration`, `pythia.worker_heartbeat` |
| Security classification | PUBLIC_READ |
| Observability | audit_trail |
| Compatibility window | compatible within declared schema |
| Support owner | EUCLID |
| Runtime evidence | LOCAL_CROSS_SERVICE_EXECUTED |
| Side effects | campaign runner applies config and retires/arms workers |
| Custody | campaign record |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py` |

### `pythia.stratum.status` — PYTHIA

**Routes**

- `GET /api/v1/stratum/status`

| Field | Value |
| --- | --- |
| Capability | stratum connectivity projection |
| Interface | HTTP_OPERATOR |
| Implementation | `chronus/mla1517_platform/python/control_api.py::stratum_status_payload` |
| Consumers | operator-console |
| Authority | PYTHIA |
| Reliability tier | R4 |
| Lifecycle | STABLE |
| SLO | `slo.projection.read` |
| Auth | NONE |
| Authorisation authority | none |
| Truth class | RUNTIME_OBSERVATION |
| Request | none |
| Response | {state, transport, subscribed, authorized, worker (redacted), job, submission, worker_live} |
| Timeout | immediate |
| Idempotency | read-only |
| Retry | freely retryable |
| Failure semantics | disconnected/configured states are explicit |
| Availability semantics | worker identity redacted; pool acceptance never implied by transport |
| Fallback policy | disconnected pool reports disconnected; reconnects are events |
| Dependencies | `stratum.v1` |
| Security classification | PUBLIC_READ |
| Observability | golden_signals |
| Compatibility window | additive fields only |
| Support owner | PYTHIA |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | none |
| Custody | none |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py` |

### `pythia.telemetry` — PYTHIA

**Routes**

- `GET /api/v1/telemetry/summary`
- `GET /api/v1/telemetry/events`
- `GET /api/v1/telemetry/ops`
- `GET /api/v1/telemetry/history`
- `GET /api/v1/telemetry/causal`
- `GET /api/v1/telemetry/session`

| Field | Value |
| --- | --- |
| Capability | operator telemetry snapshot |
| Interface | HTTP_OPERATOR |
| Implementation | `chronus/mla1517_platform/python/control_api.py::telemetry_summary_payload, telemetry_events_payload, ops_telemetry_payload, telemetry_history_payload, causal_events_payload, mining_session_payload` |
| Consumers | frontend TelemetryPanel, frontend ObservabilityView, frontend ops.ts |
| Authority | PYTHIA |
| Reliability tier | R4 |
| Lifecycle | STABLE |
| SLO | `slo.projection.read` |
| Auth | NONE |
| Authorisation authority | none |
| Truth class | RUNTIME_OBSERVATION |
| Request | query params n:int, kind:str |
| Response | pythia.telemetry_*/1 documents; unavailable blocks carry available:false + reason |
| Timeout | immediate |
| Idempotency | read-only |
| Retry | freely retryable |
| Failure semantics | absent streams are unavailable, never empty success |
| Availability semantics | distinguishes AVAILABLE/UNAVAILABLE/NOT_MEASURED |
| Fallback policy | stale/absent telemetry stays unavailable |
| Dependencies | `pythia.worker_heartbeat`, `stratum.v1` |
| Security classification | PUBLIC_READ |
| Observability | golden_signals |
| Compatibility window | additive fields only |
| Support owner | PYTHIA |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | none |
| Custody | none |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py`, `chronus/mla1517_platform/python/test_ops_telemetry.py` |

### `pythia.audit.tail` — PYTHIA

**Routes**

- `GET /api/v1/audit/tail`

| Field | Value |
| --- | --- |
| Capability | boot/ops audit tail projection |
| Interface | HTTP_OPERATOR |
| Implementation | `chronus/mla1517_platform/python/control_api.py::audit_tail_payload` |
| Consumers | frontend TelemetryPanel |
| Authority | PYTHIA |
| Reliability tier | R4 |
| Lifecycle | STABLE |
| SLO | `slo.projection.read` |
| Auth | NONE |
| Authorisation authority | none |
| Truth class | EVIDENCE |
| Request | query n:int (default 50) |
| Response | append-only audit tail |
| Timeout | immediate |
| Idempotency | read-only |
| Retry | freely retryable |
| Failure semantics | missing audit reports empty tail honestly |
| Availability semantics | reflects the boot audit log exactly |
| Fallback policy | missing log reads as empty tail |
| Dependencies | `pythia.boot_audit` |
| Security classification | PUBLIC_READ |
| Observability | evidence |
| Compatibility window | additive fields only |
| Support owner | PYTHIA |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | none |
| Custody | none |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py` |

### `pythia.knowledge` — EUCLID

**Routes**

- `GET /api/v1/knowledge`

| Field | Value |
| --- | --- |
| Capability | knowledge projection |
| Interface | HTTP_OPERATOR |
| Implementation | `chronus/mla1517_platform/python/control_api.py::knowledge_payload` |
| Consumers | operator-console |
| Authority | EUCLID |
| Reliability tier | R4 |
| Lifecycle | STABLE |
| SLO | `slo.projection.read` |
| Auth | NONE |
| Authorisation authority | none |
| Truth class | RUNTIME_OBSERVATION |
| Request | none |
| Response | knowledge fabric state |
| Timeout | immediate |
| Idempotency | read-only |
| Retry | freely retryable |
| Failure semantics | unavailable knowledge fabric reports unavailable |
| Availability semantics | honest |
| Fallback policy | unavailable corpus reports unavailable |
| Dependencies | `euclid.orchestration` |
| Security classification | PUBLIC_READ |
| Observability | golden_signals |
| Compatibility window | additive fields only |
| Support owner | EUCLID |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | none |
| Custody | none |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py` |

### `pythia.gpu` — CHRONUS

**Routes**

- `GET /api/v1/gpu`

| Field | Value |
| --- | --- |
| Capability | GPU inventory observation |
| Interface | HTTP_OPERATOR |
| Implementation | `chronus/mla1517_platform/python/control_api.py::gpu_payload` |
| Consumers | operator-console |
| Authority | CHRONUS |
| Reliability tier | R4 |
| Lifecycle | STABLE |
| SLO | `slo.projection.read` |
| Auth | NONE |
| Authorisation authority | none |
| Truth class | RUNTIME_OBSERVATION |
| Request | none |
| Response | {available, count, devices, opencl_device_count, ...} |
| Timeout | probe bound |
| Idempotency | read-only (cached) |
| Retry | freely retryable |
| Failure semantics | probe failure degrades to unavailable substrate — never raises, never invents |
| Availability semantics | no device = available:false, count:0 |
| Fallback policy | absent devices report absent — never fabricated |
| Dependencies | `chronus.execution` |
| Security classification | PUBLIC_READ |
| Observability | golden_signals |
| Compatibility window | additive fields only |
| Support owner | CHRONUS |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | OpenCL enumeration probe (cached 30s) |
| Custody | none |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py`, `chronus/mla1517_platform/python/test_control_api_gpu_truth.py` |

### `pythia.hardware.status` — CHRONUS

**Routes**

- `GET /api/v1/hardware/status`

| Field | Value |
| --- | --- |
| Capability | hardware status observation |
| Interface | HTTP_OPERATOR |
| Implementation | `chronus/mla1517_platform/python/control_api.py::hardware_status_payload` |
| Consumers | operator-console |
| Authority | CHRONUS |
| Reliability tier | R4 |
| Lifecycle | STABLE |
| SLO | `slo.projection.read` |
| Auth | NONE |
| Authorisation authority | none |
| Truth class | RUNTIME_OBSERVATION |
| Request | none |
| Response | {execution.backend, mining_device.bound, opencl.device_count, physical_gpu_count, salamander state} |
| Timeout | immediate |
| Idempotency | read-only |
| Retry | freely retryable |
| Failure semantics | armed_no_device is honest; no fabricated GPU counts |
| Availability semantics | device truth only |
| Fallback policy | unmeasured hardware reports unmeasured |
| Dependencies | `chronus.execution` |
| Security classification | PUBLIC_READ |
| Observability | golden_signals |
| Compatibility window | additive fields only |
| Support owner | CHRONUS |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | none |
| Custody | none |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py` |

### `salamander.fault` — SALAMANDER

**Routes**

- `POST /api/v1/salamander/fault`

| Field | Value |
| --- | --- |
| Capability | SALAMANDER fault/remediation command |
| Interface | HTTP_OPERATOR |
| Implementation | `chronus/mla1517_platform/python/control_api.py::_salamander_fault` |
| Consumers | frontend lib/audit.ts escalation |
| Authority | SALAMANDER |
| Reliability tier | R3 |
| Lifecycle | STABLE |
| SLO | `slo.healing` |
| Auth | OPERATOR_PRINCIPAL |
| Authorisation authority | PYTHIA |
| Truth class | COMMAND_ACCEPTANCE |
| Request | {kind?, source?, detail?, at?} |
| Response | {ok, recorded} |
| Timeout | immediate |
| Idempotency | each report is a distinct event |
| Retry | retryable (distinct events) |
| Failure semantics | fields sanitised/bounded; never silently dropped |
| Availability semantics | recorded:true means persisted to audit, not remediated |
| Fallback policy | bounded remediation; rollback on failed postcondition |
| Dependencies | `salamander.control_plane`, `theseus.custody` |
| Security classification | OPERATOR_AUTHENTICATED |
| Observability | audit_trail+evidence |
| Compatibility window | compatible within declared schema |
| Support owner | SALAMANDER |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | append-only audit event salamander_fault + prometheus counter |
| Custody | boot audit log |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py` |

## AL HARAS guardian-mediated surface

### `pythia.mining.control` — PYTHIA

**Routes**

- `POST /api/v1/mining/start`
- `POST /api/v1/mining/stop`
- `POST /api/v1/mining/switch`
- `POST /api/v1/mining/elevate`
- `POST /api/v1/mining/escalate`

| Field | Value |
| --- | --- |
| Capability | guardian-mediated mining start/stop/control |
| Interface | HTTP_PRIVILEGED |
| Implementation | `chronus/mla1517_platform/python/control_api.py::_mining_start, _mining_stop, _mining_switch, _mining_elevate, _mining_escalate` |
| Consumers | frontend SystemFabricPanel (operator action), operator-console |
| Authority | PYTHIA |
| Reliability tier | R1 |
| Lifecycle | STABLE |
| SLO | `slo.mining.control` |
| Auth | AL_HARAS_SUBSCRIPTION |
| Authorisation authority | AL_HARAS |
| Truth class | COMMAND_ACCEPTANCE |
| Request | start/stop {}; switch {pool}; elevate {target_hs}; escalate {arms} |
| Response | {ok, reason?\\|workers?\\|applied?\\|config?\\|retired?} |
| Timeout | immediate (workers spawn async) |
| Idempotency | start/stop idempotent; switch/elevate/escalate converge to declared config |
| Retry | safe to retry identical intent; do not retry a rejected command |
| Failure semantics | 400 invalid body; guardian denial receipt; ok:false + reason when no mining device (honest refuse, not a 500) |
| Availability semantics | armed_no_device is a first-class honest state |
| Fallback policy | guardian deny = zero mutation; unavailable dependency refuses the command |
| Dependencies | `al_haras.guardian`, `pythia.worker_heartbeat`, `stratum.v1`, `theseus.custody` |
| Security classification | GUARDIAN_MEDIATED |
| Observability | audit_trail+evidence |
| Compatibility window | compatible within declared schema |
| Support owner | PYTHIA |
| Runtime evidence | LOCAL_CROSS_SERVICE_EXECUTED |
| Side effects | start: arms supervised workers; stop: retires them; switch: rewrites pool selection and disarms live_submit; elevate/escalate: config merge + arm restart |
| Custody | append-only audit events mining_start/mining_stop/mining_pool_switch; guardian_mediated evidence per call |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py`, `chronus/mla1517_platform/python/test_control_auth.py` |

### `pythia.mining.evidence` — PYTHIA

**Routes**

- `GET /api/v1/mining/evidence`

| Field | Value |
| --- | --- |
| Capability | guardian-mediated mining evidence surface |
| Interface | HTTP_PRIVILEGED |
| Implementation | `chronus/mla1517_platform/python/control_api.py::mining_evidence_payload` |
| Consumers | operator-console, frontend MiningEvidencePanel |
| Authority | PYTHIA |
| Reliability tier | R1 |
| Lifecycle | STABLE |
| SLO | `slo.mining.read` |
| Auth | AL_HARAS_SUBSCRIPTION |
| Authorisation authority | AL_HARAS |
| Truth class | RUNTIME_OBSERVATION |
| Request | none |
| Response | heartbeat-derived mining evidence incl. euclid_support snapshot |
| Timeout | immediate |
| Idempotency | read-only |
| Retry | freely retryable |
| Failure semantics | absent worker evidence reports unavailable fields, never zeros |
| Availability semantics | publishes only after Stratum connects; stale/absent sidecar stays honest |
| Fallback policy | no sidecar evidence = unavailable, not zeros |
| Dependencies | `al_haras.guardian`, `pythia.worker_heartbeat` |
| Security classification | GUARDIAN_MEDIATED |
| Observability | evidence |
| Compatibility window | additive fields only |
| Support owner | PYTHIA |
| Runtime evidence | LOCAL_CROSS_SERVICE_EXECUTED |
| Side effects | none |
| Custody | none (evidence is produced by the worker, not this route) |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py` |

### `al_haras.security.status` — AL_HARAS

**Routes**

- `GET /api/v1/security/status`

| Field | Value |
| --- | --- |
| Capability | AL HARAS security posture |
| Interface | HTTP_PRIVILEGED |
| Implementation | `chronus/mla1517_platform/python/control_api.py::security_status_payload` |
| Consumers | operator-console |
| Authority | AL_HARAS |
| Reliability tier | R0 |
| Lifecycle | STABLE |
| SLO | `slo.constitutional` |
| Auth | AL_HARAS_SUBSCRIPTION |
| Authorisation authority | AL_HARAS |
| Truth class | RUNTIME_OBSERVATION |
| Request | none |
| Response | {capability, subscription_url, ...} or signed denial |
| Timeout | immediate |
| Idempotency | read-only |
| Retry | freely retryable |
| Failure semantics | signed denial receipt; 503 guardian_dependency_unavailable when AL HARAS absent |
| Availability semantics | denial is evidence, not an error mask |
| Fallback policy | none — unavailable = denied posture, never permissive |
| Dependencies | `al_haras.guardian`, `hyba_db.store` |
| Security classification | GUARDIAN_MEDIATED |
| Observability | audit_trail |
| Compatibility window | compatible within declared schema |
| Support owner | AL_HARAS |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | none |
| Custody | guardian_mediated audit event |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py`, `tests/test_al_haras_pythia_wiring.py` |

### `al_haras.security.subscribe` — AL_HARAS

**Routes**

- `GET /api/v1/security/subscribe`

| Field | Value |
| --- | --- |
| Capability | subscription issuance/configuration |
| Interface | HTTP_PRIVILEGED |
| Implementation | `chronus/mla1517_platform/python/control_api.py::_route_get /api/v1/security/subscribe` |
| Consumers | operator-console |
| Authority | AL_HARAS |
| Reliability tier | R0 |
| Lifecycle | STABLE |
| SLO | `slo.constitutional` |
| Auth | AL_HARAS_SUBSCRIPTION |
| Authorisation authority | AL_HARAS |
| Truth class | CONFIGURATION |
| Request | none |
| Response | {product, capability, subscription_required, subscription_url} |
| Timeout | immediate |
| Idempotency | read-only |
| Retry | freely retryable |
| Failure semantics | propagates security/status failure verbatim |
| Availability semantics | honest |
| Fallback policy | misconfigured authority refuses to issue |
| Dependencies | `al_haras.guardian`, `hyba_db.store` |
| Security classification | GUARDIAN_MEDIATED |
| Observability | audit_trail+evidence |
| Compatibility window | compatible within declared schema |
| Support owner | AL_HARAS |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | none |
| Custody | guardian_mediated audit event |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py` |

### `al_haras.security.evaluate` — AL_HARAS

**Routes**

- `POST /api/v1/security/evaluate`

| Field | Value |
| --- | --- |
| Capability | AL HARAS authorisation verdict |
| Interface | HTTP_PRIVILEGED |
| Implementation | `chronus/mla1517_platform/python/control_api.py::_route_post → pythia_guardian_api().evaluate` |
| Consumers | operator-console, internal preflight |
| Authority | AL_HARAS |
| Reliability tier | R0 |
| Lifecycle | STABLE |
| SLO | `slo.constitutional` |
| Auth | AL_HARAS_SUBSCRIPTION |
| Authorisation authority | AL_HARAS |
| Truth class | VERDICT |
| Request | {operation, resource, payload?, observation?} |
| Response | guardian decision receipt {allowed, ...} (signed denial on refuse) |
| Timeout | guardian bound |
| Idempotency | evaluation is pure — safe to repeat |
| Retry | retryable |
| Failure semantics | 400 malformed; 503 guardian_dependency_unavailable; signed denial ladder |
| Availability semantics | dependency failure is 503, never an implicit deny/allow |
| Fallback policy | fail closed; no verdict means denied |
| Dependencies | `al_haras.guardian`, `hyba_db.store` |
| Security classification | GUARDIAN_MEDIATED |
| Observability | audit_trail+evidence |
| Compatibility window | compatible within declared schema |
| Support owner | AL_HARAS |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | guardian evaluation is audited |
| Custody | decision evidence retained by AL HARAS |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py`, `tests/test_al_haras_pythia_wiring.py`, `chronus/mla1517_platform/python/test_control_auth.py` |

### `kellogg.tensor.capabilities` — KELLOGG

**Routes**

- `GET /api/v1/tensor/capabilities`

| Field | Value |
| --- | --- |
| Capability | KELLOGG capability surface |
| Interface | HTTP_PRIVILEGED |
| Implementation | `chronus/mla1517_platform/python/control_api.py::tensor_capabilities_payload → tensor.api.default_runtime().capabilities()` |
| Consumers | operator-console |
| Authority | KELLOGG |
| Reliability tier | R2 |
| Lifecycle | STABLE |
| SLO | `slo.specialist` |
| Auth | AL_HARAS_SUBSCRIPTION |
| Authorisation authority | AL_HARAS |
| Truth class | RUNTIME_OBSERVATION |
| Request | none |
| Response | runtime honest capability catalogue |
| Timeout | immediate |
| Idempotency | read-only |
| Retry | freely retryable |
| Failure semantics | unavailable runtime surfaces unavailable catalogue entries |
| Availability semantics | backend lists are probed, not declared |
| Fallback policy | unavailable device reports unavailable |
| Dependencies | `al_haras.guardian`, `kellogg.tensor.runtime` |
| Security classification | GUARDIAN_MEDIATED |
| Observability | golden_signals |
| Compatibility window | compatible within declared schema |
| Support owner | KELLOGG |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | none |
| Custody | guardian_mediated audit event |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py`, `tests/test_tensor_runtime.py` |

### `kellogg.tensor.execute` — KELLOGG

**Routes**

- `POST /api/v1/tensor/execute`

| Field | Value |
| --- | --- |
| Capability | KELLOGG tensor execution |
| Interface | HTTP_PRIVILEGED |
| Implementation | `chronus/mla1517_platform/python/control_api.py::_tensor_execute → TensorRuntime.execute` |
| Consumers | operator-console |
| Authority | KELLOGG |
| Reliability tier | R2 |
| Lifecycle | STABLE |
| SLO | `slo.specialist` |
| Auth | AL_HARAS_SUBSCRIPTION |
| Authorisation authority | AL_HARAS |
| Truth class | VERDICT |
| Request | {operation, inputs?\\|operands?\\|tensors?, dtype?, backend?, depth?, out?, request_id?} |
| Response | {schema_version:tensor.execute/1, ...record, values?} |
| Timeout | operation bound |
| Idempotency | request_id correlates; execution itself is not deduplicated |
| Retry | retryable read-type ops; mutating store ops are replayed under caller's request_id |
| Failure semantics | 400 invalid body/unknown operation; guardian denial; dtype/shape validation fails closed |
| Availability semantics | result cannot masquerade as mining proof or VQC authority |
| Fallback policy | typed failure; fallback only when caller plan permits |
| Dependencies | `al_haras.guardian`, `kellogg.tensor.runtime`, `theseus.custody` |
| Security classification | GUARDIAN_MEDIATED |
| Observability | golden_signals+evidence |
| Compatibility window | compatible within declared schema |
| Support owner | KELLOGG |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | executes a bounded tensor operation; takes custody of named tensors |
| Custody | THESEUS when the operation is durable (store_tensor); guardian_mediated audit event |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py`, `tests/test_tensor_runtime.py` |

### `toe.collapse` — EUCLID

**Routes**

- `POST /api/v1/toe/collapse`

| Field | Value |
| --- | --- |
| Capability | EUCLID collapse verdict |
| Interface | HTTP_PRIVILEGED |
| Implementation | `chronus/mla1517_platform/python/control_api.py::_route_post → toe.bridge.TOEBridge.predict` |
| Consumers | operator-console |
| Authority | EUCLID |
| Reliability tier | R2 |
| Lifecycle | STABLE |
| SLO | `slo.specialist` |
| Auth | AL_HARAS_SUBSCRIPTION |
| Authorisation authority | AL_HARAS |
| Truth class | VERDICT |
| Request | {data: {...}} (non-empty object, ≤4 MiB) |
| Response | {schema_version, generated_at, guardian_receipt, execution_evidence, ...per-section available results} |
| Timeout | bridge bound |
| Idempotency | pure — safe to repeat |
| Retry | retryable |
| Failure semantics | 400 empty/malformed; 413 oversize; signed denial; per-section available:false instead of fabrication |
| Availability semantics | each bridge section reports available honestly |
| Fallback policy | unproven stays unproven |
| Dependencies | `al_haras.guardian`, `euclid.orchestration` |
| Security classification | GUARDIAN_MEDIATED |
| Observability | golden_signals |
| Compatibility window | compatible within declared schema |
| Support owner | EUCLID |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | runs the bridge prediction (tomography, causal analysis, tensor witness) |
| Custody | execution evidence + guardian receipt returned and audited |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py` |

## Event streams

### `pythia.telemetry.stream` — PYTHIA

**Routes**

- `GET /api/v1/telemetry/stream`

| Field | Value |
| --- | --- |
| Capability | SSE telemetry stream |
| Interface | EVENT_STREAM |
| Implementation | `chronus/mla1517_platform/python/control_api.py::_telemetry_stream` |
| Consumers | frontend ops.ts EventSource |
| Authority | PYTHIA |
| Reliability tier | R4 |
| Lifecycle | STABLE |
| SLO | `slo.projection.stream` |
| Auth | NONE |
| Authorisation authority | none |
| Truth class | RUNTIME_OBSERVATION |
| Request | none |
| Response | text/event-stream frames {type:ops, seq, ops, new_events} + : keepalive |
| Timeout | bounded ~120 ticks then clean close |
| Idempotency | read-only; client resumes from last_seq |
| Retry | EventSource auto-reconnect; seq resumes |
| Failure semantics | connection close is clean; staleness surfaced client-side |
| Availability semantics | frames carry the honest ops payload |
| Fallback policy | dropped events are counted and reported, never silent |
| Dependencies | `pythia.worker_heartbeat`, `stratum.v1` |
| Security classification | PUBLIC_READ |
| Observability | golden_signals |
| Compatibility window | additive event fields only |
| Support owner | PYTHIA |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | none |
| Custody | none |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_production_api_contract.py` |

## Reserved namespaces (no implementation, by design)

### `namespace.policy` — AL_HARAS

**Routes**

- `* /api/v1/policy/`

| Field | Value |
| --- | --- |
| Capability | reserved /api/v1/policy namespace |
| Interface | RESERVED_NAMESPACE |
| Implementation | `chronus/mla1517_platform/python/control_api.py::_PRIVILEGED_PREFIXES` |
| Consumers | future policy service |
| Authority | AL_HARAS |
| Reliability tier | R0 |
| Lifecycle | RESERVED |
| SLO | `slo.constitutional` |
| Auth | AL_HARAS_SUBSCRIPTION |
| Authorisation authority | AL_HARAS |
| Truth class | VERDICT |
| Request | none |
| Response | guardian denial receipt or {"error":"not_found"} |
| Timeout | immediate |
| Idempotency | n/a |
| Retry | n/a |
| Failure semantics | real 404 past the boundary |
| Availability semantics | never implies an implemented endpoint |
| Fallback policy | deny at boundary; reserved never masquerades |
| Dependencies | `al_haras.guardian` |
| Security classification | GUARDIAN_MEDIATED |
| Observability | audit_trail |
| Compatibility window | n/a — no implementation |
| Support owner | AL_HARAS |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | none |
| Custody | denial receipts audited |
| Stability | reserved |
| Deprecation | RESERVED_NAMESPACE |
| Tests | `tests/test_production_api_contract.py` |

### `namespace.worker` — AL_HARAS

**Routes**

- `* /api/v1/worker/`

| Field | Value |
| --- | --- |
| Capability | reserved /api/v1/worker namespace |
| Interface | RESERVED_NAMESPACE |
| Implementation | `chronus/mla1517_platform/python/control_api.py::_PRIVILEGED_PREFIXES` |
| Consumers | future worker control |
| Authority | AL_HARAS |
| Reliability tier | R0 |
| Lifecycle | RESERVED |
| SLO | `slo.constitutional` |
| Auth | AL_HARAS_SUBSCRIPTION |
| Authorisation authority | AL_HARAS |
| Truth class | VERDICT |
| Request | none |
| Response | guardian denial receipt or {"error":"not_found"} |
| Timeout | immediate |
| Idempotency | n/a |
| Retry | n/a |
| Failure semantics | real 404 past the boundary |
| Availability semantics | never implies an implemented endpoint |
| Fallback policy | deny at boundary; reserved never masquerades |
| Dependencies | `al_haras.guardian` |
| Security classification | GUARDIAN_MEDIATED |
| Observability | audit_trail |
| Compatibility window | n/a — no implementation |
| Support owner | AL_HARAS |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | none |
| Custody | denial receipts audited |
| Stability | reserved |
| Deprecation | RESERVED_NAMESPACE |
| Tests | `tests/test_production_api_contract.py` |

### `namespace.recovery` — AL_HARAS

**Routes**

- `* /api/v1/recovery/`

| Field | Value |
| --- | --- |
| Capability | reserved /api/v1/recovery namespace |
| Interface | RESERVED_NAMESPACE |
| Implementation | `chronus/mla1517_platform/python/control_api.py::_PRIVILEGED_PREFIXES` |
| Consumers | future recovery control |
| Authority | AL_HARAS |
| Reliability tier | R0 |
| Lifecycle | RESERVED |
| SLO | `slo.constitutional` |
| Auth | AL_HARAS_SUBSCRIPTION |
| Authorisation authority | AL_HARAS |
| Truth class | VERDICT |
| Request | none |
| Response | guardian denial receipt or {"error":"not_found"} |
| Timeout | immediate |
| Idempotency | n/a |
| Retry | n/a |
| Failure semantics | real 404 past the boundary |
| Availability semantics | never implies an implemented endpoint |
| Fallback policy | deny at boundary; reserved never masquerades |
| Dependencies | `al_haras.guardian` |
| Security classification | GUARDIAN_MEDIATED |
| Observability | audit_trail |
| Compatibility window | n/a — no implementation |
| Support owner | AL_HARAS |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | none |
| Custody | denial receipts audited |
| Stability | reserved |
| Deprecation | RESERVED_NAMESPACE |
| Tests | `tests/test_production_api_contract.py` |

### `namespace.admin` — AL_HARAS

**Routes**

- `* /api/v1/admin/`

| Field | Value |
| --- | --- |
| Capability | reserved /api/v1/admin namespace |
| Interface | RESERVED_NAMESPACE |
| Implementation | `chronus/mla1517_platform/python/control_api.py::_PRIVILEGED_PREFIXES` |
| Consumers | future admin console |
| Authority | AL_HARAS |
| Reliability tier | R0 |
| Lifecycle | RESERVED |
| SLO | `slo.constitutional` |
| Auth | AL_HARAS_SUBSCRIPTION |
| Authorisation authority | AL_HARAS |
| Truth class | VERDICT |
| Request | none |
| Response | guardian denial receipt or {"error":"not_found"} |
| Timeout | immediate |
| Idempotency | n/a |
| Retry | n/a |
| Failure semantics | real 404 past the boundary |
| Availability semantics | never implies an implemented endpoint |
| Fallback policy | deny at boundary; reserved never masquerades |
| Dependencies | `al_haras.guardian` |
| Security classification | GUARDIAN_MEDIATED |
| Observability | audit_trail |
| Compatibility window | n/a — no implementation |
| Support owner | AL_HARAS |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | none |
| Custody | denial receipts audited |
| Stability | reserved |
| Deprecation | RESERVED_NAMESPACE |
| Tests | `tests/test_production_api_contract.py` |

### `namespace.quantum` — TURING

**Routes**

- `* /api/v1/quantum/`

| Field | Value |
| --- | --- |
| Capability | reserved /api/v1/quantum namespace |
| Interface | RESERVED_NAMESPACE |
| Implementation | `chronus/mla1517_platform/python/control_api.py::_PRIVILEGED_PREFIXES` |
| Consumers | future operator TURING surface |
| Authority | TURING |
| Reliability tier | R0 |
| Lifecycle | RESERVED |
| SLO | `slo.constitutional` |
| Auth | AL_HARAS_SUBSCRIPTION |
| Authorisation authority | AL_HARAS |
| Truth class | VERDICT |
| Request | none |
| Response | guardian denial receipt or {"error":"not_found"} |
| Timeout | immediate |
| Idempotency | n/a |
| Retry | n/a |
| Failure semantics | real 404 past the boundary — TURING's canonical interface is INTERNAL_PYTHON VQCPipeline, not REST |
| Availability semantics | never implies a REST TURING service exists |
| Fallback policy | deny at boundary; reserved never masquerades |
| Dependencies | `al_haras.guardian` |
| Security classification | GUARDIAN_MEDIATED |
| Observability | audit_trail |
| Compatibility window | n/a — no implementation |
| Support owner | TURING |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | none |
| Custody | denial receipts audited |
| Stability | reserved |
| Deprecation | RESERVED_NAMESPACE |
| Tests | `tests/test_production_api_contract.py` |

### `namespace.scale` — AL_HARAS

**Routes**

- `* /api/v1/scale/`

| Field | Value |
| --- | --- |
| Capability | reserved /api/v1/scale namespace |
| Interface | RESERVED_NAMESPACE |
| Implementation | `chronus/mla1517_platform/python/control_api.py::_PRIVILEGED_PREFIXES` |
| Consumers | future scale control |
| Authority | AL_HARAS |
| Reliability tier | R0 |
| Lifecycle | RESERVED |
| SLO | `slo.constitutional` |
| Auth | AL_HARAS_SUBSCRIPTION |
| Authorisation authority | AL_HARAS |
| Truth class | VERDICT |
| Request | none |
| Response | guardian denial receipt or {"error":"not_found"} |
| Timeout | immediate |
| Idempotency | n/a |
| Retry | n/a |
| Failure semantics | real 404 past the boundary |
| Availability semantics | never implies an implemented endpoint |
| Fallback policy | deny at boundary; reserved never masquerades |
| Dependencies | `al_haras.guardian` |
| Security classification | GUARDIAN_MEDIATED |
| Observability | audit_trail |
| Compatibility window | n/a — no implementation |
| Support owner | AL_HARAS |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | none |
| Custody | denial receipts audited |
| Stability | reserved |
| Deprecation | RESERVED_NAMESPACE |
| Tests | `tests/test_production_api_contract.py` |

### `namespace.assembly` — AL_HARAS

**Routes**

- `* /api/v1/assembly/`

| Field | Value |
| --- | --- |
| Capability | reserved /api/v1/assembly namespace |
| Interface | RESERVED_NAMESPACE |
| Implementation | `chronus/mla1517_platform/python/control_api.py::_PRIVILEGED_PREFIXES` |
| Consumers | future assembly control |
| Authority | AL_HARAS |
| Reliability tier | R0 |
| Lifecycle | RESERVED |
| SLO | `slo.constitutional` |
| Auth | AL_HARAS_SUBSCRIPTION |
| Authorisation authority | AL_HARAS |
| Truth class | VERDICT |
| Request | none |
| Response | guardian denial receipt or {"error":"not_found"} |
| Timeout | immediate |
| Idempotency | n/a |
| Retry | n/a |
| Failure semantics | real 404 past the boundary |
| Availability semantics | never implies an implemented endpoint |
| Fallback policy | deny at boundary; reserved never masquerades |
| Dependencies | `al_haras.guardian` |
| Security classification | GUARDIAN_MEDIATED |
| Observability | audit_trail |
| Compatibility window | n/a — no implementation |
| Support owner | AL_HARAS |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | none |
| Custody | denial receipts audited |
| Stability | reserved |
| Deprecation | RESERVED_NAMESPACE |
| Tests | `tests/test_production_api_contract.py` |

## Internal typed Python contracts

### `turing.vqc_pipeline` — TURING

- `VQCRequest → validation → representation → exact execution → PipelineReport {verdict, stages, certificate, witness, custody, replay}`

| Field | Value |
| --- | --- |
| Capability | independent VQC execution + certificate |
| Interface | INTERNAL_PYTHON |
| Implementation | `turing_universal_quantum_computer/turing_universal_quantum_computer/pipeline.py::VQCPipeline.run(VQCRequest)` |
| Consumers | PYTHIA, EUCLID |
| Authority | TURING |
| Reliability tier | R2 |
| Lifecycle | STABLE |
| SLO | `slo.specialist` |
| Auth | TYPED_CALL |
| Authorisation authority | AL_HARAS (caller-side mediation where privileged) |
| Truth class | EVIDENCE |
| Request | VQCRequest dataclass (program \\| qasm, shots, seed, verify_unitary, custody, replay) |
| Response | PipelineReport dataclass — verdict PASS/FAIL/REFUSED/GATED; certificate dict when issued |
| Timeout | execution bound by request |
| Idempotency | deterministic per request |
| Retry | replayable; certificates verify |
| Failure semantics | invalid program/unknown gate/representation or backend mismatch raise; tampered certificate fails verification |
| Availability semantics | unavailable backends report unavailable, never substitute |
| Fallback policy | typed failure; unavailable backend reports unavailable; no impersonation |
| Dependencies | `theseus.custody` |
| Security classification | INTERNAL_TYPED |
| Observability | evidence |
| Compatibility window | compatible within turing.vqc/1 |
| Support owner | TURING |
| Runtime evidence | LOCAL_TEST_PASSED |
| Side effects | computation certificate issued and re-verified; THESEUS custody when durable |
| Custody | certificate + result to THESEUS where durable |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_turing_production_pipeline.py` |

### `theseus.custody` — THESEUS

- `put(payload) → TheseusRecord / get(uuid) / record(uuid) / verify() / snapshot(dir) / lookup_digest(digest) / get_working_form(uuid)`

| Field | Value |
| --- | --- |
| Capability | durable custody/integrity/provenance store |
| Interface | INTERNAL_PYTHON |
| Implementation | `aethel/theseus.py::Theseus (open_theseus)` |
| Consumers | PYTHIA, TURING, CHRONUS, OVID, KELLOGG, SALAMANDER, AL_HARAS, EUCLID |
| Authority | THESEUS |
| Reliability tier | R0 |
| Lifecycle | STABLE |
| SLO | `slo.constitutional` |
| Auth | TYPED_CALL |
| Authorisation authority | THESEUS validates the custody contract; producer owns semantics |
| Truth class | EVIDENCE |
| Request | typed methods; TheseusRecord |
| Response | bytes / TheseusRecord / bool / snapshot dict |
| Timeout | io bound |
| Idempotency | put is content-addressed; replay is stable |
| Retry | io retry per store policy |
| Failure semantics | TheseusError on contract violation; corrupt records heal or fail closed |
| Availability semantics | missing record is a miss, never a fabricate |
| Fallback policy | none — custody failure stops the dependent operation |
| Dependencies | none |
| Security classification | INTERNAL_TYPED |
| Observability | evidence |
| Compatibility window | content-addressed records are append-stable |
| Support owner | THESEUS |
| Runtime evidence | LOCAL_TEST_PASSED |
| Side effects | durable record writes; healing of corrupt records where configured |
| Custody | self — it IS the custody boundary |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_aethel_storage.py`, `tests/test_enterprise_custody_substrate.py` |

### `ovid.transform` — OVID

- `metamorphose / verify_equivalence / round_trip / materialise / transform_contract / contract_report`

| Field | Value |
| --- | --- |
| Capability | representation/state transformation + lineage |
| Interface | INTERNAL_PYTHON |
| Implementation | `aethel/ovid.py::Ovid (open_ovid)` |
| Consumers | PYTHIA, CHRONUS, EUCLID, THESEUS producers |
| Authority | OVID |
| Reliability tier | R2 |
| Lifecycle | STABLE |
| SLO | `slo.specialist` |
| Auth | TYPED_CALL |
| Authorisation authority | OVID (transformation only — never custody) |
| Truth class | EVIDENCE |
| Request | TransformContract declaration; input representation |
| Response | FoldedWorkingForm / TransformLineage / EquivalenceVerdict |
| Timeout | transform bound |
| Idempotency | lineage_id is execution-unique by construction |
| Retry | replayable; equivalence re-verifies |
| Failure semantics | unknown transform / unsupported version / inconsistent contract / tampered output fail closed |
| Availability semantics | UNSUPPORTED contracts never execute |
| Fallback policy | equivalence failure is a verdict; no silent approximate substitute |
| Dependencies | `theseus.custody` |
| Security classification | INTERNAL_TYPED |
| Observability | evidence |
| Compatibility window | compatible within declared schema |
| Support owner | OVID |
| Runtime evidence | LOCAL_TEST_PASSED |
| Side effects | emits execution-unique TransformLineage; durable lineage goes to THESEUS |
| Custody | THESEUS for durable lineage |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_ovid_contracts.py` |

### `kellogg.tensor.runtime` — KELLOGG

- `capabilities / store_tensor / execute / read_tensor`

| Field | Value |
| --- | --- |
| Capability | KELLOGG tensor runtime contract |
| Interface | INTERNAL_PYTHON |
| Implementation | `tensor/api.py::default_runtime → tensor/runtime.py::TensorRuntime` |
| Consumers | control_api tensor.execute, EUCLID where authorised |
| Authority | KELLOGG |
| Reliability tier | R2 |
| Lifecycle | STABLE |
| SLO | `slo.specialist` |
| Auth | TYPED_CALL |
| Authorisation authority | KELLOGG owns tensor capability only |
| Truth class | VERDICT |
| Request | bounded operation + shapes + dtype |
| Response | execution record {path, output\\|output_digest, receipt: tensor.receipt/1, truth_class, dtype} |
| Timeout | operation bound |
| Idempotency | per request_id correlation |
| Retry | read-type ops retryable |
| Failure semantics | shape/dtype/unknown-op validation fails closed |
| Availability semantics | result is tensor evidence only — never mining proof or VQC authority |
| Fallback policy | typed failure; caller chooses authorised alternative |
| Dependencies | `theseus.custody` |
| Security classification | INTERNAL_TYPED |
| Observability | evidence |
| Compatibility window | compatible within declared schema |
| Support owner | KELLOGG |
| Runtime evidence | LOCAL_TEST_PASSED |
| Side effects | tensor execution; custody of stored tensors |
| Custody | THESEUS when durable |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_tensor_runtime.py` |

### `chronus.execution` — CHRONUS

- `execution request → backend selection → backend → receipt/provenance`

| Field | Value |
| --- | --- |
| Capability | heterogeneous execution contract |
| Interface | INTERNAL_PYTHON |
| Implementation | `chronus backend registry / execution router (chronus/)` |
| Consumers | PYTHIA mining runtime, TURING workloads, control plane workers |
| Authority | CHRONUS |
| Reliability tier | R1 |
| Lifecycle | STABLE |
| SLO | `slo.mining.execution` |
| Auth | TYPED_CALL |
| Authorisation authority | CHRONUS |
| Truth class | EVIDENCE |
| Request | workload + requested backend |
| Response | receipt {requested_backend, actual_backend, result, provenance} |
| Timeout | workload bound |
| Idempotency | per execution id |
| Retry | fail closed on unavailable requested backend unless explicitly authorised fallback policy applies |
| Failure semantics | requested_backend ≠ actual_backend is always explicit; unavailable backend fails closed |
| Availability semantics | never silently substitutes a backend |
| Fallback policy | backend unavailability is explicit; re-derived verification is the receipt |
| Dependencies | `theseus.custody`, `chronus.remote_opencl_v2` |
| Security classification | INTERNAL_TYPED |
| Observability | evidence |
| Compatibility window | compatible within declared schema |
| Support owner | CHRONUS |
| Runtime evidence | LOCAL_TEST_PASSED |
| Side effects | real backend execution |
| Custody | execution receipt to THESEUS where durable |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_backend_registry.py`, `chronus/mla1517_platform/python/test_execution_receipt.py` |

### `al_haras.guardian` — AL_HARAS

- `evaluate(headers{authorization,x-hyba-tenant,x-hyba-actor}, body{operation,resource,payload,observation})`

| Field | Value |
| --- | --- |
| Capability | guardian mediation for privileged operations |
| Interface | INTERNAL_PYTHON |
| Implementation | `chronus/mla1517_platform/python/al_haras_pythia.py::pythia_guardian_api().evaluate(headers, body)` |
| Consumers | control_api privileged preflight, security/evaluate route |
| Authority | AL_HARAS |
| Reliability tier | R0 |
| Lifecycle | STABLE |
| SLO | `slo.constitutional` |
| Auth | AL_HARAS_SUBSCRIPTION |
| Authorisation authority | AL_HARAS |
| Truth class | VERDICT |
| Request | guardian evaluate envelope |
| Response | (HTTPStatus, decision receipt) — denial receipts are signed |
| Timeout | immediate |
| Idempotency | evaluation is pure |
| Retry | retryable |
| Failure semantics | full denial ladder (missing/malformed credential, wrong tenant/actor, insufficient capability, expired/revoked, guardian unavailable, dependency unavailable) — handler never executes before decision |
| Availability semantics | dependency failure is 503 not an implicit allow |
| Fallback policy | deny closed; mediated routes return signed denial receipts |
| Dependencies | `hyba_db.store` |
| Security classification | GUARDIAN_MEDIATED |
| Observability | audit_trail+evidence |
| Compatibility window | compatible within declared schema |
| Support owner | AL_HARAS |
| Runtime evidence | LOCAL_TEST_PASSED |
| Side effects | audit evidence per decision |
| Custody | AL HARAS audit trail |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_al_haras_pythia_wiring.py`, `chronus/mla1517_platform/python/test_control_auth.py` |

### `salamander.control_plane` — SALAMANDER

- `observe / discover / qualify / chronus_envelope / admit / execute / recover / verify_theseus_custody / verify_ovid_transform / verify_projection / api_snapshot`

| Field | Value |
| --- | --- |
| Capability | SALAMANDER healing control plane |
| Interface | INTERNAL_PYTHON |
| Implementation | `salamander/control_plane.py::AutonomicControlPlane` |
| Consumers | salamander_engine worker, control plane |
| Authority | SALAMANDER |
| Reliability tier | R3 |
| Lifecycle | STABLE |
| SLO | `slo.healing` |
| Auth | TYPED_CALL |
| Authorisation authority | SALAMANDER orchestrates; never alters subsystem ownership |
| Truth class | EVIDENCE |
| Request | typed models (HealthObservation, ActionRequest, RecoveryPlan, TheseusRecordIdentity, OvidTransformEvidence, RebuildableProjection) |
| Response | HealthDecision / ActionResult / ActionVerification / api_snapshot dict |
| Timeout | per-action bounds + recovery deadline |
| Idempotency | ActionRequest.idempotency_key required and enforced |
| Retry | bounded by circuit breaker + recovery budget |
| Failure semantics | FailClosed on contract violation; unverified action is never recovery proof |
| Availability semantics | UNKNOWN/UNAVAILABLE are first-class health states |
| Fallback policy | bounded remediation with postcondition verification and rollback |
| Dependencies | `theseus.custody` |
| Security classification | INTERNAL_TYPED |
| Observability | evidence |
| Compatibility window | compatible within declared schema |
| Support owner | SALAMANDER |
| Runtime evidence | LOCAL_TEST_PASSED |
| Side effects | bounded remediation via registered actuators + independent verifiers |
| Custody | hash-chained EvidenceLedger; durable events to THESEUS |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_salamander_autonomic.py`, `tests/test_b_salamander_recovery.py` |

### `euclid.orchestration` — EUCLID

- `typed handoffs to PYTHIA/TURING/KELLOGG/SALAMANDER preserving request identity, correlation id, tenant, actor, authority, provenance, custody linkage`

| Field | Value |
| --- | --- |
| Capability | EUCLID intelligence orchestration |
| Interface | INTERNAL_PYTHON |
| Implementation | `euclid/ runtime + chronus/mla1517_platform/python/system_fabric.py::euclid_cognition_solve` |
| Consumers | control_api cognition/solve, mining support |
| Authority | EUCLID |
| Reliability tier | R1 |
| Lifecycle | STABLE |
| SLO | `slo.mining.plan` |
| Auth | TYPED_CALL |
| Authorisation authority | EUCLID orchestrates; specialist semantics stay with the specialist |
| Truth class | VERDICT |
| Request | cognition episode request |
| Response | episode trace {available, ...} |
| Timeout | episode bound |
| Idempotency | per episode id |
| Retry | retryable as new episode |
| Failure semantics | unavailable specialist propagates available:false |
| Availability semantics | EUCLID never duplicates the specialist algorithm |
| Fallback policy | specialist unavailability returns to the plan; no service impersonates another |
| Dependencies | `turing.vqc_pipeline`, `kellogg.tensor.runtime`, `ovid.transform`, `chronus.execution`, `theseus.custody` |
| Security classification | INTERNAL_TYPED |
| Observability | evidence |
| Compatibility window | compatible within declared schema |
| Support owner | EUCLID |
| Runtime evidence | LOCAL_TEST_PASSED |
| Side effects | orchestrates specialist calls |
| Custody | evidence bundle / THESEUS where durable |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `chronus/mla1517_platform/python/test_euclid_core.py`, `chronus/mla1517_platform/python/test_euclid_cognition_entrypoint.py` |

### `hyba_db.store` — HYBA_DB

- `tenant-scoped ontology/query/projection persistence; verify_database()`

| Field | Value |
| --- | --- |
| Capability | tenant-scoped ontology/query persistence |
| Interface | INTERNAL_PYTHON |
| Implementation | `hyba_db/store.py::OntologyStore (verify_database)` |
| Consumers | SALAMANDER projection verification, enterprise projections |
| Authority | HYBA_DB |
| Reliability tier | R1 |
| Lifecycle | STABLE |
| SLO | `slo.tenant_store` |
| Auth | TENANT_SCOPED |
| Authorisation authority | producer contract |
| Truth class | VERDICT |
| Request | store/verify calls |
| Response | verify verdict {valid\\|ok, projection_sha256, ...} |
| Timeout | io bound |
| Idempotency | verify is pure |
| Retry | retryable |
| Failure semantics | drift detected against projection_sha256 |
| Availability semantics | projection validity is a producer fact, not THESEUS/OVID |
| Fallback policy | tenant failure never bleeds across tenant boundary |
| Dependencies | none |
| Security classification | TENANT_SCOPED |
| Observability | evidence |
| Compatibility window | compatible within declared schema |
| Support owner | HYBA_DB |
| Runtime evidence | LOCAL_TEST_PASSED |
| Side effects | projection persistence |
| Custody | durable anchor in THESEUS |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_salamander_autonomic.py` |

## External wire protocols

### `stratum.v1` — POOL

- `mining.subscribe → mining.authorize → mining.notify (+ set_difficulty) → job → mining.submit → literal pool result`

| Field | Value |
| --- | --- |
| Capability | Stratum V1 pool wire protocol |
| Interface | WIRE_PROTOCOL |
| Implementation | `chronus/mla1517_platform/python/manifold_pool_coordinator.py::StratumClient` |
| Consumers | agentic-mining worker |
| Authority | POOL |
| Reliability tier | R1 |
| Lifecycle | STABLE |
| SLO | `slo.stratum` |
| Auth | WIRE_TOKEN |
| Authorisation authority | POOL |
| Truth class | VERDICT |
| Request | JSON-RPC Stratum V1 methods |
| Response | literal pool replies; submit result is a boolean verdict |
| Timeout | per-request transport timeout |
| Idempotency | mining.submit is NEVER auto-retried — an unknown prior outcome cannot be safely replayed without protocol idempotency |
| Retry | subscribe/authorize/notify handling retry via reconnect; submit only by explicit canonical resubmission policy |
| Failure semantics | StratumProtocolError/StratumAuthorizationError; malformed reply/duplicate or unknown request id/job replacement all handled explicitly |
| Availability semantics | pool acceptance is established ONLY by the literal pool response — never by socket write or local SHA256d pass |
| Fallback policy | bounded reconnect; stale work rejected; submit never auto-retried |
| Dependencies | none |
| Security classification | WIRE_CREDENTIAL |
| Observability | evidence |
| Compatibility window | stratum.v1 protocol |
| Support owner | POOL |
| Runtime evidence | LOCAL_CROSS_SERVICE_EXECUTED |
| Side effects | submits shares only via the SHA256d proof boundary |
| Custody | submission/pool-outcome evidence in worker metrics |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `chronus/mla1517_platform/python/test_pool_only_mining.py`, `tests/test_b_pool_outcomes.py` |

### `chronus.remote_opencl_v2` — CHRONUS

- `GET /v1/health; GET /v1/devices; GET /v1/telemetry; POST /v1/ladder; POST /v1/sha256d`

| Field | Value |
| --- | --- |
| Capability | remote OpenCL execution wire protocol |
| Interface | WIRE_PROTOCOL |
| Implementation | `chronus/mla1517/remote_gpu.py (client) + chronus/mla1517/remote_gpu_agent.py (server)` |
| Consumers | chronus.delivery cloud_instance, hybrid solver |
| Authority | CHRONUS |
| Reliability tier | R1 |
| Lifecycle | STABLE |
| SLO | `slo.remote_execution` |
| Auth | WIRE_TOKEN |
| Authorisation authority | CHRONUS |
| Truth class | EVIDENCE |
| Request | remote_opencl_v2 envelopes; sha256d window ≤2^24 nonces, batch ≤2^20 |
| Response | {protocol: remote_opencl_v2, ...}; attestation token binds sha256d results to the job |
| Timeout | DEFAULT_TIMEOUT_S=5 probes; SHA256D_DEFAULT_TIMEOUT_S=300 scans |
| Idempotency | ladder/sha256d are pure computations — replay safe |
| Retry | probe_first_reachable rotates endpoints; results always re-verified |
| Failure semantics | wrong protocol version rejected; tampered results fail re-verification; unreachable/deviceless endpoints report honest unavailability — no fabricated devices, no silent fallback |
| Availability semantics | imported devices are measured, never declared |
| Fallback policy | circuit breaker on persistent failure; results always re-verified |
| Dependencies | none |
| Security classification | WIRE_CREDENTIAL |
| Observability | evidence |
| Compatibility window | remote_opencl_v2 protocol version |
| Support owner | CHRONUS |
| Runtime evidence | LOCAL_CROSS_SERVICE_EXECUTED |
| Side effects | remote device execution |
| Custody | re-derived exact verification is the evidence |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `chronus/mla1517_platform/python/test_remote_gpu.py`, `chronus/tests/test_chronus_delivery.py`, `tests/test_remote_hasher.py` |

## File and artifact contracts

### `pythia.worker_heartbeat` — PYTHIA

- `write/read <worker>.metrics.json (+ .bin HMAC-signed heartbeat)`

| Field | Value |
| --- | --- |
| Capability | worker metrics sidecar contract |
| Interface | FILE/ARTIFACT_CONTRACT |
| Implementation | `worker_lifecycle.HeartbeatReader + mining_runtime metrics sidecars` |
| Consumers | control_api status/telemetry/mining.evidence, campaign counters |
| Authority | PYTHIA |
| Reliability tier | R1 |
| Lifecycle | STABLE |
| SLO | `slo.mining.telemetry` |
| Auth | HMAC_SIDECAR |
| Authorisation authority | PYTHIA |
| Truth class | RUNTIME_OBSERVATION |
| Request | n/a |
| Response | metrics.json {state, ready, counters, job, submission, mining_evidence?}; .bin signed by PYTHIA_IDENTITY_HMAC_SECRET |
| Timeout | n/a |
| Idempotency | last-writer-wins per worker file |
| Retry | readers tolerate missing/stale files as unavailable |
| Failure semantics | stale sidecar belongs to a killed arm — excluded from counters |
| Availability semantics | absent file = worker not reporting, never zeros |
| Fallback policy | stale sidecar excluded from counters |
| Dependencies | none |
| Security classification | HMAC_SIDECAR |
| Observability | evidence |
| Compatibility window | additive fields only within pythia.worker_metrics/1 |
| Support owner | PYTHIA |
| Runtime evidence | LOCAL_TEST_PASSED |
| Side effects | file writes per heartbeat tick; clean exit removes the sidecar |
| Custody | sidecar staleness TTL 30s default (PYTHIA_METRICS_SIDECAR_TTL_S) |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `chronus/mla1517_platform/python/test_phase4_api.py` |

### `pythia.boot_audit` — PYTHIA

- `append-only JSONL audit events`

| Field | Value |
| --- | --- |
| Capability | append-only boot/ops audit log |
| Interface | FILE/ARTIFACT_CONTRACT |
| Implementation | `startup_contract.AppendOnlyAudit` |
| Consumers | control_api audit/tail, operators |
| Authority | PYTHIA |
| Reliability tier | R1 |
| Lifecycle | STABLE |
| SLO | `slo.evidence` |
| Auth | FILESYSTEM |
| Authorisation authority | PYTHIA |
| Truth class | EVIDENCE |
| Request | n/a |
| Response | JSONL events {event, at, fields...} |
| Timeout | n/a |
| Idempotency | append-only |
| Retry | n/a |
| Failure semantics | missing log reads as empty tail |
| Availability semantics | exact log contents only |
| Fallback policy | append-only; readers see exact log |
| Dependencies | none |
| Security classification | FILESYSTEM |
| Observability | evidence |
| Compatibility window | additive event fields only within pythia.boot_audit/1 |
| Support owner | PYTHIA |
| Runtime evidence | LOCAL_TEST_PASSED |
| Side effects | append-only writes |
| Custody | self |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_startup_contract.py` |

### `pythia.runtime_config_file` — PYTHIA

- `atomic JSON read/write`

| Field | Value |
| --- | --- |
| Capability | runtime configuration artifact |
| Interface | FILE/ARTIFACT_CONTRACT |
| Implementation | `runtime_config.load/save/public_view` |
| Consumers | control_api config routes, workers on (re)spawn |
| Authority | PYTHIA |
| Reliability tier | R1 |
| Lifecycle | STABLE |
| SLO | `slo.configuration` |
| Auth | FILESYSTEM |
| Authorisation authority | PYTHIA |
| Truth class | CONFIGURATION |
| Request | n/a |
| Response | declared config; public_view redacts pool passwords |
| Timeout | n/a |
| Idempotency | save is idempotent per content |
| Retry | n/a |
| Failure semantics | ValueError on invalid config |
| Availability semantics | secrets never serialised to public view |
| Fallback policy | invalid config fails boot closed |
| Dependencies | none |
| Security classification | FILESYSTEM |
| Observability | evidence |
| Compatibility window | compatible within declared schema |
| Support owner | PYTHIA |
| Runtime evidence | LOCAL_TEST_PASSED |
| Side effects | durable config writes |
| Custody | config is declaration, not observation |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `chronus/mla1517_platform/python/test_phase4_api.py` |

## Command-line entrypoints

### `pythia.cli.api` — PYTHIA

- `python main.py --host H --port P --web-root DIR`

| Field | Value |
| --- | --- |
| Capability | control API process entrypoint |
| Interface | CLI |
| Implementation | `main.py → chronus/mla1517_platform/python/control_api.py::main (console script pythia-api)` |
| Consumers | operators, systemd/containers |
| Authority | PYTHIA |
| Reliability tier | R1 |
| Lifecycle | STABLE |
| SLO | `slo.cli` |
| Auth | ENVIRONMENT |
| Authorisation authority | PYTHIA |
| Truth class | LIVENESS |
| Request | argparse flags |
| Response | process exit codes; stdout log |
| Timeout | n/a |
| Idempotency | boot lock makes a second instance fail fast |
| Retry | n/a |
| Failure semantics | StartupConfigError → nonzero exit with reason; RestartBudgetExhausted → fail loud |
| Availability semantics | fails fast on absent/placeholder worker identity |
| Fallback policy | misconfiguration exits non-zero with reason |
| Dependencies | `pythia.boot_audit` |
| Security classification | ENVIRONMENT |
| Observability | evidence |
| Compatibility window | flags stable within major version |
| Support owner | PYTHIA |
| Runtime evidence | INSTALLED_ARTIFACT_EXECUTED |
| Side effects | starts the control plane + workers per env gates |
| Custody | boot lock + audit log |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `tests/test_startup_contract.py`, `chronus/mla1517_platform/python/test_startup_optional_services.py` |

### `pythia.cli.miner` — PYTHIA

- `pythia-mine [flags]`

| Field | Value |
| --- | --- |
| Capability | headless miner entrypoint |
| Interface | CLI |
| Implementation | `chronus/mla1517_platform/python/mining_runtime.py::main (console script pythia-mine)` |
| Consumers | operators |
| Authority | PYTHIA |
| Reliability tier | R1 |
| Lifecycle | STABLE |
| SLO | `slo.cli` |
| Auth | ENVIRONMENT |
| Authorisation authority | PYTHIA |
| Truth class | LIVENESS |
| Request | argparse flags |
| Response | process exit codes |
| Timeout | n/a |
| Idempotency | n/a |
| Retry | n/a |
| Failure semantics | fail-closed on absent device/pool identity |
| Availability semantics | honest |
| Fallback policy | missing worker identity fails fast |
| Dependencies | `stratum.v1` |
| Security classification | ENVIRONMENT |
| Observability | evidence |
| Compatibility window | flags stable within major version |
| Support owner | PYTHIA |
| Runtime evidence | LOCAL_TEST_PASSED |
| Side effects | headless stratum miner (fail-closed without device/credentials) |
| Custody | worker metrics + audit |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `chronus/mla1517_platform/python/test_pool_only_mining.py` |

### `chronus.cli.remote_agent` — CHRONUS

- `python -m chronus.mla1517.remote_gpu_agent`

| Field | Value |
| --- | --- |
| Capability | remote GPU agent entrypoint |
| Interface | CLI |
| Implementation | `chronus/mla1517/remote_gpu_agent.py` |
| Consumers | operators deploying remote GPU agents |
| Authority | CHRONUS |
| Reliability tier | R1 |
| Lifecycle | STABLE |
| SLO | `slo.cli` |
| Auth | WIRE_TOKEN |
| Authorisation authority | CHRONUS |
| Truth class | LIVENESS |
| Request | argparse flags |
| Response | process exit codes; serves /v1/* remote_opencl_v2 |
| Timeout | n/a |
| Idempotency | n/a |
| Retry | n/a |
| Failure semantics | fails closed on no device |
| Availability semantics | advertises only measured devices |
| Fallback policy | unreachable auth/config fails fast |
| Dependencies | `chronus.remote_opencl_v2` |
| Security classification | WIRE_CREDENTIAL |
| Observability | evidence |
| Compatibility window | flags stable within major version |
| Support owner | CHRONUS |
| Runtime evidence | LOCAL_TEST_PASSED |
| Side effects | serves verified remote device execution |
| Custody | none (verification is client-side) |
| Stability | stable |
| Deprecation | CANONICAL |
| Tests | `chronus/mla1517_platform/python/test_remote_gpu.py` |

## Legacy compatibility aliases

### `legacy.api_health` — PYTHIA

**Routes**

- `GET /api/health`

| Field | Value |
| --- | --- |
| Capability | legacy health alias |
| Interface | LEGACY |
| Implementation | `control_api.py::_route_get` |
| Consumers | older monitors |
| Authority | PYTHIA |
| Reliability tier | R4 |
| Lifecycle | LEGACY |
| SLO | `slo.projection.read` |
| Auth | NONE |
| Authorisation authority | none |
| Truth class | LIVENESS |
| Request | none |
| Response | same as pythia.health |
| Timeout | immediate |
| Idempotency | read-only |
| Retry | freely retryable |
| Failure semantics | same as canonical |
| Availability semantics | same as canonical |
| Fallback policy | alias of canonical health |
| Dependencies | `pythia.health` |
| Security classification | PUBLIC_READ |
| Observability | golden_signals |
| Compatibility window | frozen surface until retirement approval |
| Support owner | PYTHIA |
| Runtime evidence | LOCAL_HTTP_E2E_EXECUTED |
| Side effects | none |
| Custody | none |
| Stability | frozen |
| Deprecation | COMPATIBILITY_ALIAS |
| Tests | `tests/test_production_api_contract.py` |

## Mining authority

`chronus/mla1517/mining/stratum_adapter.py` is the proof boundary. It
consumes a live subscription and `mining.notify` job, constructs the
coinbase, Merkle root, 80-byte header, and SHA256d digest, and returns
`mining.submit` parameters only after the negotiated target check
succeeds. The frontend is not a mining client: it must not contain
Stratum methods, Bitcoin hashing, target comparisons, synthetic pool
acknowledgements, or fabricated hashrate values.
