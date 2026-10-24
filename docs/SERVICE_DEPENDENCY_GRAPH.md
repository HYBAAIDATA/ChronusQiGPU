# PYTHIA service dependency graph

Generated from `governance/api_registry.yaml` + `governance/service_fabric.yaml` by `governance/render_service_fabric.py`. Do not edit by hand.

Machine-readable source: `dependency_graph.edges` in
`governance/service_fabric.yaml`. `tests/test_service_constitution.py`
enforces that each interface's registry `dependencies` and the graph
edges are the same set — a dependency cannot exist in one and not the
other.

## Edges

| caller | callee | contract | availability | retry | failure propagation |
| --- | --- | --- | --- | --- | --- |
| `pythia.readiness` | `pythia.worker_heartbeat` | sidecar metrics files | SOFT | read-only | readiness degraded not failed |
| `pythia.readiness` | `pythia.boot_audit` | append-only JSONL tail | SOFT | read-only | readiness degraded |
| `pythia.readiness` | `al_haras.guardian` | guardian mediation availability | SOFT | none | readiness reports degraded component |
| `pythia.ready_to_mine` | `stratum.v1` | pool connectivity observation | SOFT | read-only | domain-readiness false |
| `pythia.ready_to_mine` | `pythia.worker_heartbeat` | worker sidecars | SOFT | read-only | domain-readiness false |
| `pythia.metrics` | `pythia.worker_heartbeat` | metrics sidecars | SOFT | read-only | counters reflect only live workers |
| `pythia.metrics` | `stratum.v1` | pool session counters | SOFT | read-only | connectivity false |
| `pythia.status` | `pythia.worker_heartbeat` | metrics sidecars | SOFT | read-only | degraded projection |
| `pythia.status` | `stratum.v1` | pool session state | SOFT | read-only | degraded projection |
| `pythia.status` | `pythia.boot_audit` | audit tail | SOFT | read-only | degraded projection |
| `pythia.config.read` | `pythia.runtime_config_file` | redacted config read | HARD | read-only | NOT_CONFIGURED |
| `pythia.config.update` | `pythia.runtime_config_file` | atomic config write | HARD | never auto-retry mutation | CUSTODY_FAILURE or INVALID_REQUEST |
| `pythia.config.update` | `pythia.boot_audit` | audit append | HARD | none | INTERNAL_ERROR |
| `pythia.control.session` | `pythia.boot_audit` | audit append | HARD | none | INTERNAL_ERROR |
| `pythia.system.map` | `pythia.boot_audit` | audit context | SOFT | read-only | degraded projection |
| `pythia.system.verify.read` | `euclid.orchestration` | verification run state | SOFT | read-only | NOT_APPLICABLE |
| `pythia.system.verify.read` | `pythia.boot_audit` | audit tail | SOFT | read-only | degraded |
| `pythia.system.verify.start` | `euclid.orchestration` | start verification run | HARD | never auto-retry start; idempotency via run id | DEPENDENCY_UNAVAILABLE |
| `pythia.system.verify.start` | `pythia.boot_audit` | audit append | HARD | none | INTERNAL_ERROR |
| `pythia.intelligence.status` | `euclid.orchestration` | intelligence state read | SOFT | read-only | DEPENDENCY_UNAVAILABLE section |
| `pythia.intelligence.selftest` | `euclid.orchestration` | selftest dispatch/read | HARD for POST | read-only GET; POST no auto-retry | DEPENDENCY_UNAVAILABLE |
| `pythia.intelligence.selftest` | `pythia.boot_audit` | audit append | HARD | none | INTERNAL_ERROR |
| `pythia.intelligence.maintenance` | `euclid.orchestration` | maintenance dispatch/read | HARD for POST | read-only GET; POST no auto-retry | DEPENDENCY_UNAVAILABLE |
| `pythia.intelligence.maintenance` | `pythia.boot_audit` | audit append | HARD | none | INTERNAL_ERROR |
| `pythia.intelligence.autonomous` | `euclid.orchestration` | autonomous loop state/control | HARD for POST | read-only GET; POST no auto-retry | DEPENDENCY_UNAVAILABLE |
| `pythia.intelligence.engineer` | `euclid.orchestration` | engineer dispatch | HARD | no auto-retry; idempotency via request id | NOT_CONFIGURED or DEPENDENCY_UNAVAILABLE |
| `pythia.intelligence.cognition_solve` | `euclid.orchestration` | deterministic solve verdict | HARD | no auto-retry; verdict is deterministic per input | DEPENDENCY_UNAVAILABLE |
| `pythia.agentic` | `euclid.orchestration` | agentic mining orchestration | HARD for POST | no auto-retry on control POST | DEPENDENCY_UNAVAILABLE |
| `pythia.agentic` | `pythia.worker_heartbeat` | worker sidecars | SOFT | read-only | degraded projection |
| `pythia.agentic` | `stratum.v1` | pool session state | SOFT | read-only | degraded projection |
| `pythia.campaign` | `euclid.orchestration` | campaign state/control | HARD for POST | no auto-retry on control POST | DEPENDENCY_UNAVAILABLE |
| `pythia.campaign` | `pythia.worker_heartbeat` | worker metrics counters | SOFT | read-only | degraded projection |
| `pythia.mining.control` | `al_haras.guardian` | subscription authorisation + signed denial receipt | HARD | deny is never retried by the client layer | FORBIDDEN or DEPENDENCY_UNAVAILABLE |
| `pythia.mining.control` | `pythia.worker_heartbeat` | worker control via supervisor | HARD | no auto-retry on stop/start | DEPENDENCY_UNAVAILABLE or EXECUTION_FAILURE |
| `pythia.mining.control` | `stratum.v1` | pool session for mining ops | SOFT for status paths | reconnect bounded; mining.submit never auto-retried | DEPENDENCY_UNAVAILABLE or EXTERNAL_REJECT |
| `pythia.mining.control` | `theseus.custody` | durable mining evidence custody | HARD where durable evidence is required | content-addressed put is idempotent | CUSTODY_FAILURE |
| `pythia.mining.evidence` | `al_haras.guardian` | subscription authorisation | HARD | none | FORBIDDEN or DEPENDENCY_UNAVAILABLE |
| `pythia.mining.evidence` | `pythia.worker_heartbeat` | mining evidence sidecars | HARD for evidence claim | read-only | DEPENDENCY_UNAVAILABLE |
| `pythia.stratum.status` | `stratum.v1` | pool connectivity read | SOFT | read-only | degraded projection |
| `pythia.telemetry` | `pythia.worker_heartbeat` | metrics sidecars | SOFT | read-only | degraded projection |
| `pythia.telemetry` | `stratum.v1` | pool session state | SOFT | read-only | degraded projection |
| `pythia.telemetry.stream` | `pythia.worker_heartbeat` | metrics sidecars polled per tick | SOFT | stream reconnect is client-side | degraded stream |
| `pythia.telemetry.stream` | `stratum.v1` | pool session state per tick | SOFT | none | degraded stream |
| `pythia.audit.tail` | `pythia.boot_audit` | append-only JSONL tail | SOFT | read-only | degraded projection |
| `pythia.knowledge` | `euclid.orchestration` | knowledge projection | SOFT | read-only | degraded projection |
| `pythia.gpu` | `chronus.execution` | device inventory observation | SOFT | read-only | degraded projection |
| `pythia.hardware.status` | `chronus.execution` | hardware observation | SOFT | read-only | degraded projection |
| `al_haras.security.status` | `al_haras.guardian` | guardian posture read | HARD | none | DEPENDENCY_UNAVAILABLE |
| `al_haras.security.status` | `hyba_db.store` | tenant-scoped security state | HARD | io retry per store policy | DEPENDENCY_UNAVAILABLE |
| `al_haras.security.subscribe` | `al_haras.guardian` | subscription issuance via authority | HARD | issuance is idempotent per subject | FORBIDDEN or NOT_CONFIGURED |
| `al_haras.security.subscribe` | `hyba_db.store` | tenant subscription records | HARD | io retry per store policy | DEPENDENCY_UNAVAILABLE |
| `al_haras.security.evaluate` | `al_haras.guardian` | authorisation verdict | HARD | none | FORBIDDEN or DEPENDENCY_UNAVAILABLE |
| `al_haras.security.evaluate` | `hyba_db.store` | tenant policy state | HARD | io retry per store policy | DEPENDENCY_UNAVAILABLE |
| `kellogg.tensor.capabilities` | `al_haras.guardian` | subscription authorisation | HARD | none | FORBIDDEN or DEPENDENCY_UNAVAILABLE |
| `kellogg.tensor.capabilities` | `kellogg.tensor.runtime` | capability enumeration | HARD for capabilities claim | read-only | DEPENDENCY_UNAVAILABLE |
| `kellogg.tensor.execute` | `al_haras.guardian` | subscription authorisation | HARD | none | FORBIDDEN or DEPENDENCY_UNAVAILABLE |
| `kellogg.tensor.execute` | `kellogg.tensor.runtime` | validated tensor operation | HARD | replayable pure computation | EXECUTION_FAILURE or DEPENDENCY_UNAVAILABLE |
| `kellogg.tensor.execute` | `theseus.custody` | durable result custody | HARD where durable | content-addressed put idempotent | CUSTODY_FAILURE |
| `toe.collapse` | `al_haras.guardian` | subscription authorisation | HARD | none | FORBIDDEN or DEPENDENCY_UNAVAILABLE |
| `toe.collapse` | `euclid.orchestration` | collapse verdict computation | HARD | deterministic per input | DEPENDENCY_UNAVAILABLE or VERIFICATION_FAILURE |
| `salamander.fault` | `salamander.control_plane` | fault/remediation dispatch | HARD | no auto-retry; remediation idempotent per fault id | DEPENDENCY_UNAVAILABLE |
| `salamander.fault` | `theseus.custody` | remediation evidence custody | HARD | content-addressed put idempotent | CUSTODY_FAILURE |
| `namespace.policy` | `al_haras.guardian` | boundary denial | HARD | none | FORBIDDEN |
| `namespace.worker` | `al_haras.guardian` | boundary denial | HARD | none | FORBIDDEN |
| `namespace.recovery` | `al_haras.guardian` | boundary denial | HARD | none | FORBIDDEN |
| `namespace.admin` | `al_haras.guardian` | boundary denial | HARD | none | FORBIDDEN |
| `namespace.quantum` | `al_haras.guardian` | boundary denial | HARD | none | FORBIDDEN |
| `namespace.scale` | `al_haras.guardian` | boundary denial | HARD | none | FORBIDDEN |
| `namespace.assembly` | `al_haras.guardian` | boundary denial | HARD | none | FORBIDDEN |
| `turing.vqc_pipeline` | `theseus.custody` | certificate + result custody when durable | HARD when custody requested | content-addressed put idempotent | CUSTODY_FAILURE |
| `ovid.transform` | `theseus.custody` | transform lineage custody | HARD when durable | content-addressed put idempotent | CUSTODY_FAILURE |
| `kellogg.tensor.runtime` | `theseus.custody` | tensor provenance custody | HARD when durable | content-addressed put idempotent | CUSTODY_FAILURE |
| `chronus.execution` | `theseus.custody` | execution receipt custody | HARD where durable | content-addressed put idempotent | CUSTODY_FAILURE |
| `chronus.execution` | `chronus.remote_opencl_v2` | remote backend import/execution | SOFT — remote is an optional lane | probe_first_reachable rotates; circuit breaker bounds persistent failure | DEPENDENCY_UNAVAILABLE for remote lane only |
| `al_haras.guardian` | `hyba_db.store` | tenant-scoped subscription/policy state | HARD — guardian fails closed without state | io retry per store policy | DEPENDENCY_UNAVAILABLE => denied |
| `salamander.control_plane` | `theseus.custody` | healing evidence custody | HARD | content-addressed put idempotent | CUSTODY_FAILURE |
| `euclid.orchestration` | `turing.vqc_pipeline` | VQC execution selection | SOFT — plan-dependent | plan selects authorised alternative on typed unavailability | typed DEPENDENCY_UNAVAILABLE to plan |
| `euclid.orchestration` | `kellogg.tensor.runtime` | tensor operation selection | SOFT — plan-dependent | plan selects authorised alternative on typed unavailability | typed DEPENDENCY_UNAVAILABLE to plan |
| `euclid.orchestration` | `ovid.transform` | representation transform | SOFT — plan-dependent | deterministic per contract | typed failure to plan |
| `euclid.orchestration` | `chronus.execution` | workload dispatch | HARD for selected plan | stale plan rejected; no blind retry | EXECUTION_FAILURE or DEPENDENCY_UNAVAILABLE |
| `euclid.orchestration` | `theseus.custody` | plan/decision custody | HARD where durable | content-addressed put idempotent | CUSTODY_FAILURE |
| `legacy.api_health` | `pythia.health` | alias of canonical liveness | HARD | freely retryable | DEPENDENCY_UNAVAILABLE |
| `pythia.cli.api` | `pythia.boot_audit` | boot audit emission | SOFT — boot continues with degraded audit only if policy allows | none | startup evidence gap recorded |
| `pythia.cli.miner` | `stratum.v1` | pool session for mining | HARD for mining | bounded reconnect; submit never auto-retried | DEPENDENCY_UNAVAILABLE or EXTERNAL_REJECT |
| `chronus.cli.remote_agent` | `chronus.remote_opencl_v2` | serves the remote protocol | n/a | n/a — it is the server | connection refused |

## Per-interface view

- `al_haras.guardian` (R0): depends on `hyba_db.store`; depended on by `al_haras.security.evaluate`, `al_haras.security.status`, `al_haras.security.subscribe`, `kellogg.tensor.capabilities`, `kellogg.tensor.execute`, `namespace.admin`, `namespace.assembly`, `namespace.policy`, `namespace.quantum`, `namespace.recovery`, `namespace.scale`, `namespace.worker`, `pythia.mining.control`, `pythia.mining.evidence`, `pythia.readiness`, `toe.collapse`
- `al_haras.security.evaluate` (R0): depends on `al_haras.guardian`, `hyba_db.store`; depended on by —
- `al_haras.security.status` (R0): depends on `al_haras.guardian`, `hyba_db.store`; depended on by —
- `al_haras.security.subscribe` (R0): depends on `al_haras.guardian`, `hyba_db.store`; depended on by —
- `chronus.cli.remote_agent` (R1): depends on `chronus.remote_opencl_v2`; depended on by —
- `chronus.execution` (R1): depends on `theseus.custody`, `chronus.remote_opencl_v2`; depended on by `euclid.orchestration`, `pythia.gpu`, `pythia.hardware.status`
- `chronus.remote_opencl_v2` (R1): depends on —; depended on by `chronus.cli.remote_agent`, `chronus.execution`
- `euclid.orchestration` (R1): depends on `turing.vqc_pipeline`, `kellogg.tensor.runtime`, `ovid.transform`, `chronus.execution`, `theseus.custody`; depended on by `pythia.agentic`, `pythia.campaign`, `pythia.intelligence.autonomous`, `pythia.intelligence.cognition_solve`, `pythia.intelligence.engineer`, `pythia.intelligence.maintenance`, `pythia.intelligence.selftest`, `pythia.intelligence.status`, `pythia.knowledge`, `pythia.system.verify.read`, `pythia.system.verify.start`, `toe.collapse`
- `hyba_db.store` (R1): depends on —; depended on by `al_haras.guardian`, `al_haras.security.evaluate`, `al_haras.security.status`, `al_haras.security.subscribe`
- `kellogg.tensor.capabilities` (R2): depends on `al_haras.guardian`, `kellogg.tensor.runtime`; depended on by —
- `kellogg.tensor.execute` (R2): depends on `al_haras.guardian`, `kellogg.tensor.runtime`, `theseus.custody`; depended on by —
- `kellogg.tensor.runtime` (R2): depends on `theseus.custody`; depended on by `euclid.orchestration`, `kellogg.tensor.capabilities`, `kellogg.tensor.execute`
- `legacy.api_health` (R4): depends on `pythia.health`; depended on by —
- `namespace.admin` (R0): depends on `al_haras.guardian`; depended on by —
- `namespace.assembly` (R0): depends on `al_haras.guardian`; depended on by —
- `namespace.policy` (R0): depends on `al_haras.guardian`; depended on by —
- `namespace.quantum` (R0): depends on `al_haras.guardian`; depended on by —
- `namespace.recovery` (R0): depends on `al_haras.guardian`; depended on by —
- `namespace.scale` (R0): depends on `al_haras.guardian`; depended on by —
- `namespace.worker` (R0): depends on `al_haras.guardian`; depended on by —
- `ovid.transform` (R2): depends on `theseus.custody`; depended on by `euclid.orchestration`
- `pythia.agentic` (R1): depends on `euclid.orchestration`, `pythia.worker_heartbeat`, `stratum.v1`; depended on by —
- `pythia.audit.tail` (R4): depends on `pythia.boot_audit`; depended on by —
- `pythia.boot_audit` (R1): depends on —; depended on by `pythia.audit.tail`, `pythia.cli.api`, `pythia.config.update`, `pythia.control.session`, `pythia.intelligence.maintenance`, `pythia.intelligence.selftest`, `pythia.readiness`, `pythia.status`, `pythia.system.map`, `pythia.system.verify.read`, `pythia.system.verify.start`
- `pythia.campaign` (R1): depends on `euclid.orchestration`, `pythia.worker_heartbeat`; depended on by —
- `pythia.cli.api` (R1): depends on `pythia.boot_audit`; depended on by —
- `pythia.cli.miner` (R1): depends on `stratum.v1`; depended on by —
- `pythia.config.read` (R4): depends on `pythia.runtime_config_file`; depended on by —
- `pythia.config.update` (R1): depends on `pythia.runtime_config_file`, `pythia.boot_audit`; depended on by —
- `pythia.control.session` (R4): depends on `pythia.boot_audit`; depended on by —
- `pythia.customer.health` (R4): depends on —; depended on by —
- `pythia.gpu` (R4): depends on `chronus.execution`; depended on by —
- `pythia.hardware.status` (R4): depends on `chronus.execution`; depended on by —
- `pythia.health` (R4): depends on —; depended on by `legacy.api_health`
- `pythia.intelligence.autonomous` (R2): depends on `euclid.orchestration`; depended on by —
- `pythia.intelligence.cognition_solve` (R2): depends on `euclid.orchestration`; depended on by —
- `pythia.intelligence.engineer` (R2): depends on `euclid.orchestration`; depended on by —
- `pythia.intelligence.maintenance` (R2): depends on `euclid.orchestration`, `pythia.boot_audit`; depended on by —
- `pythia.intelligence.selftest` (R2): depends on `euclid.orchestration`, `pythia.boot_audit`; depended on by —
- `pythia.intelligence.status` (R4): depends on `euclid.orchestration`; depended on by —
- `pythia.knowledge` (R4): depends on `euclid.orchestration`; depended on by —
- `pythia.metrics` (R4): depends on `pythia.worker_heartbeat`, `stratum.v1`; depended on by —
- `pythia.mining.control` (R1): depends on `al_haras.guardian`, `pythia.worker_heartbeat`, `stratum.v1`, `theseus.custody`; depended on by —
- `pythia.mining.evidence` (R1): depends on `al_haras.guardian`, `pythia.worker_heartbeat`; depended on by —
- `pythia.readiness` (R4): depends on `pythia.worker_heartbeat`, `pythia.boot_audit`, `al_haras.guardian`; depended on by —
- `pythia.ready_to_mine` (R4): depends on `stratum.v1`, `pythia.worker_heartbeat`; depended on by —
- `pythia.runtime_config_file` (R1): depends on —; depended on by `pythia.config.read`, `pythia.config.update`
- `pythia.static_spa` (R4): depends on —; depended on by —
- `pythia.status` (R4): depends on `pythia.worker_heartbeat`, `stratum.v1`, `pythia.boot_audit`; depended on by —
- `pythia.stratum.status` (R4): depends on `stratum.v1`; depended on by —
- `pythia.substrate.latency` (R4): depends on —; depended on by —
- `pythia.system.map` (R4): depends on `pythia.boot_audit`; depended on by —
- `pythia.system.verify.read` (R4): depends on `euclid.orchestration`, `pythia.boot_audit`; depended on by —
- `pythia.system.verify.start` (R1): depends on `euclid.orchestration`, `pythia.boot_audit`; depended on by —
- `pythia.telemetry` (R4): depends on `pythia.worker_heartbeat`, `stratum.v1`; depended on by —
- `pythia.telemetry.stream` (R4): depends on `pythia.worker_heartbeat`, `stratum.v1`; depended on by —
- `pythia.worker_heartbeat` (R1): depends on —; depended on by `pythia.agentic`, `pythia.campaign`, `pythia.metrics`, `pythia.mining.control`, `pythia.mining.evidence`, `pythia.readiness`, `pythia.ready_to_mine`, `pythia.status`, `pythia.telemetry`, `pythia.telemetry.stream`
- `salamander.control_plane` (R3): depends on `theseus.custody`; depended on by `salamander.fault`
- `salamander.fault` (R3): depends on `salamander.control_plane`, `theseus.custody`; depended on by —
- `salamander.veritas.status` (R3): depends on —; depended on by —
- `stratum.v1` (R1): depends on —; depended on by `pythia.agentic`, `pythia.cli.miner`, `pythia.metrics`, `pythia.mining.control`, `pythia.ready_to_mine`, `pythia.status`, `pythia.stratum.status`, `pythia.telemetry`, `pythia.telemetry.stream`
- `theseus.custody` (R0): depends on —; depended on by `chronus.execution`, `euclid.orchestration`, `kellogg.tensor.execute`, `kellogg.tensor.runtime`, `ovid.transform`, `pythia.mining.control`, `salamander.control_plane`, `salamander.fault`, `turing.vqc_pipeline`
- `toe.collapse` (R2): depends on `al_haras.guardian`, `euclid.orchestration`; depended on by —
- `turing.vqc_pipeline` (R2): depends on `theseus.custody`; depended on by `euclid.orchestration`

