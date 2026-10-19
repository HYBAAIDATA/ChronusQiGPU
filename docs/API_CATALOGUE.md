# PYTHIA service constitution — API catalogue

Generated from `governance/api_registry.yaml` + `governance/service_fabric.yaml` by `governance/render_service_fabric.py`. Do not edit by hand.

Schema `pythia.api_registry/2` — 64 interfaces, every one
carrying the §2 constitution fields: capability, canonical authority,
consumer, contract, dependencies, reliability tier, SLO, timeout,
retry, idempotency, fallback, security classification, custody,
observability, lifecycle, support owner, runtime evidence.

## R0 — 

_if unavailable, the affected privileged operation stops_

| api_id | owner | type | lifecycle | slo | consumers |
| --- | --- | --- | --- | --- | --- |
| `al_haras.guardian` | AL_HARAS | INTERNAL_PYTHON | STABLE | `slo.constitutional` | control_api privileged preflight, security/evaluate route |
| `al_haras.security.evaluate` | AL_HARAS | HTTP_PRIVILEGED | STABLE | `slo.constitutional` | operator-console, internal preflight |
| `al_haras.security.status` | AL_HARAS | HTTP_PRIVILEGED | STABLE | `slo.constitutional` | operator-console |
| `al_haras.security.subscribe` | AL_HARAS | HTTP_PRIVILEGED | STABLE | `slo.constitutional` | operator-console |
| `namespace.admin` | AL_HARAS | RESERVED_NAMESPACE | RESERVED | `slo.constitutional` | future admin console |
| `namespace.assembly` | AL_HARAS | RESERVED_NAMESPACE | RESERVED | `slo.constitutional` | future assembly control |
| `namespace.policy` | AL_HARAS | RESERVED_NAMESPACE | RESERVED | `slo.constitutional` | future policy service |
| `namespace.quantum` | TURING | RESERVED_NAMESPACE | RESERVED | `slo.constitutional` | future operator TURING surface |
| `namespace.recovery` | AL_HARAS | RESERVED_NAMESPACE | RESERVED | `slo.constitutional` | future recovery control |
| `namespace.scale` | AL_HARAS | RESERVED_NAMESPACE | RESERVED | `slo.constitutional` | future scale control |
| `namespace.worker` | AL_HARAS | RESERVED_NAMESPACE | RESERVED | `slo.constitutional` | future worker control |
| `theseus.custody` | THESEUS | INTERNAL_PYTHON | STABLE | `slo.constitutional` | PYTHIA, TURING, CHRONUS, OVID, KELLOGG, SALAMANDER, AL_HARAS, EUCLID |

## R1 — 

__

| api_id | owner | type | lifecycle | slo | consumers |
| --- | --- | --- | --- | --- | --- |
| `chronus.cli.remote_agent` | CHRONUS | CLI | STABLE | `slo.cli` | operators deploying remote GPU agents |
| `chronus.execution` | CHRONUS | INTERNAL_PYTHON | STABLE | `slo.mining.execution` | PYTHIA mining runtime, TURING workloads, control plane workers |
| `chronus.remote_opencl_v2` | CHRONUS | WIRE_PROTOCOL | STABLE | `slo.remote_execution` | chronus.delivery cloud_instance, hybrid solver |
| `euclid.orchestration` | EUCLID | INTERNAL_PYTHON | STABLE | `slo.mining.plan` | control_api cognition/solve, mining support |
| `hyba_db.store` | HYBA_DB | INTERNAL_PYTHON | STABLE | `slo.tenant_store` | SALAMANDER projection verification, enterprise projections |
| `pythia.agentic` | EUCLID | HTTP_OPERATOR | STABLE | `slo.mining.control` | frontend SystemFabricPanel, frontend IntelligenceView |
| `pythia.boot_audit` | PYTHIA | FILE/ARTIFACT_CONTRACT | STABLE | `slo.evidence` | control_api audit/tail, operators |
| `pythia.campaign` | EUCLID | HTTP_OPERATOR | STABLE | `slo.mining.control` | frontend SystemFabricPanel |
| `pythia.cli.api` | PYTHIA | CLI | STABLE | `slo.cli` | operators, systemd/containers |
| `pythia.cli.miner` | PYTHIA | CLI | STABLE | `slo.cli` | operators |
| `pythia.config.update` | PYTHIA | HTTP_OPERATOR | STABLE | `slo.operator.mutation` | frontend RuntimeControlPanel |
| `pythia.mining.control` | PYTHIA | HTTP_PRIVILEGED | STABLE | `slo.mining.control` | frontend SystemFabricPanel (operator action), operator-console |
| `pythia.mining.evidence` | PYTHIA | HTTP_PRIVILEGED | STABLE | `slo.mining.read` | operator-console, frontend MiningEvidencePanel |
| `pythia.runtime_config_file` | PYTHIA | FILE/ARTIFACT_CONTRACT | STABLE | `slo.configuration` | control_api config routes, workers on (re)spawn |
| `pythia.system.verify.start` | PYTHIA | HTTP_OPERATOR | STABLE | `slo.operator.mutation` | frontend SystemFabricPanel |
| `pythia.worker_heartbeat` | PYTHIA | FILE/ARTIFACT_CONTRACT | STABLE | `slo.mining.telemetry` | control_api status/telemetry/mining.evidence, campaign counters |
| `stratum.v1` | POOL | WIRE_PROTOCOL | STABLE | `slo.stratum` | agentic-mining worker |

## R2 — 

_unavailability never causes another subsystem to impersonate the missing authority_

| api_id | owner | type | lifecycle | slo | consumers |
| --- | --- | --- | --- | --- | --- |
| `kellogg.tensor.capabilities` | KELLOGG | HTTP_PRIVILEGED | STABLE | `slo.specialist` | operator-console |
| `kellogg.tensor.execute` | KELLOGG | HTTP_PRIVILEGED | STABLE | `slo.specialist` | operator-console |
| `kellogg.tensor.runtime` | KELLOGG | INTERNAL_PYTHON | STABLE | `slo.specialist` | control_api tensor.execute, EUCLID where authorised |
| `ovid.transform` | OVID | INTERNAL_PYTHON | STABLE | `slo.specialist` | PYTHIA, CHRONUS, EUCLID, THESEUS producers |
| `pythia.intelligence.autonomous` | EUCLID | HTTP_OPERATOR | STABLE | `slo.specialist` | operator-console |
| `pythia.intelligence.cognition_solve` | EUCLID | HTTP_OPERATOR | STABLE | `slo.specialist` | operator-console |
| `pythia.intelligence.engineer` | EUCLID | HTTP_OPERATOR | STABLE | `slo.specialist` | frontend IntelligenceView |
| `pythia.intelligence.maintenance` | EUCLID | HTTP_OPERATOR | STABLE | `slo.specialist` | frontend IntelligenceView |
| `pythia.intelligence.selftest` | EUCLID | HTTP_OPERATOR | STABLE | `slo.specialist` | frontend IntelligenceView, frontend SystemFabricPanel |
| `toe.collapse` | EUCLID | HTTP_PRIVILEGED | STABLE | `slo.specialist` | operator-console |
| `turing.vqc_pipeline` | TURING | INTERNAL_PYTHON | STABLE | `slo.specialist` | PYTHIA, EUCLID |

## R3 — 

__

| api_id | owner | type | lifecycle | slo | consumers |
| --- | --- | --- | --- | --- | --- |
| `salamander.control_plane` | SALAMANDER | INTERNAL_PYTHON | STABLE | `slo.healing` | salamander_engine worker, control plane |
| `salamander.fault` | SALAMANDER | HTTP_OPERATOR | STABLE | `slo.healing` | frontend lib/audit.ts escalation |
| `salamander.veritas.status` | SALAMANDER | HTTP_OPERATOR | STABLE | `slo.projection.read` | operator-console, veritas-monitor |

## R4 — 

_loss of R4 must not corrupt R0-R2 semantics_

| api_id | owner | type | lifecycle | slo | consumers |
| --- | --- | --- | --- | --- | --- |
| `legacy.api_health` | PYTHIA | LEGACY | LEGACY | `slo.projection.read` | older monitors |
| `pythia.audit.tail` | PYTHIA | HTTP_OPERATOR | STABLE | `slo.projection.read` | frontend TelemetryPanel |
| `pythia.config.read` | PYTHIA | HTTP_OPERATOR | STABLE | `slo.projection.read` | frontend RuntimeControlPanel, frontend SystemFabricPanel |
| `pythia.control.session` | PYTHIA | HTTP_OPERATOR | STABLE | `slo.projection.read` | frontend |
| `pythia.customer.health` | PYTHIA | HTTP_PUBLIC | STABLE | `slo.projection.read` | customer-monitoring, external-probes |
| `pythia.gpu` | CHRONUS | HTTP_OPERATOR | STABLE | `slo.projection.read` | operator-console |
| `pythia.hardware.status` | CHRONUS | HTTP_OPERATOR | STABLE | `slo.projection.read` | operator-console |
| `pythia.health` | PYTHIA | HTTP_PUBLIC | STABLE | `slo.projection.read` | operator-console, load-balancer |
| `pythia.intelligence.status` | EUCLID | HTTP_OPERATOR | STABLE | `slo.projection.read` | frontend IntelligenceView |
| `pythia.knowledge` | EUCLID | HTTP_OPERATOR | STABLE | `slo.projection.read` | operator-console |
| `pythia.metrics` | PYTHIA | HTTP_PUBLIC | STABLE | `slo.projection.read` | prometheus, operator-console |
| `pythia.readiness` | PYTHIA | HTTP_PUBLIC | STABLE | `slo.projection.read` | operator-console, load-balancer |
| `pythia.ready_to_mine` | PYTHIA | HTTP_PUBLIC | STABLE | `slo.projection.read` | operator-console |
| `pythia.static_spa` | PYTHIA | HTTP_PUBLIC | STABLE | `slo.projection.read` | browser |
| `pythia.status` | PYTHIA | HTTP_OPERATOR | STABLE | `slo.projection.read` | frontend SystemFabricPanel, operator-console |
| `pythia.stratum.status` | PYTHIA | HTTP_OPERATOR | STABLE | `slo.projection.read` | operator-console |
| `pythia.substrate.latency` | PYTHIA | HTTP_OPERATOR | STABLE | `slo.projection.read` | operator-console, applet-latency-monitor |
| `pythia.system.map` | PYTHIA | HTTP_OPERATOR | STABLE | `slo.projection.read` | frontend SystemFabricPanel |
| `pythia.system.verify.read` | PYTHIA | HTTP_OPERATOR | STABLE | `slo.projection.read` | frontend SystemFabricPanel |
| `pythia.telemetry` | PYTHIA | HTTP_OPERATOR | STABLE | `slo.projection.read` | frontend TelemetryPanel, frontend ObservabilityView, frontend ops.ts |
| `pythia.telemetry.stream` | PYTHIA | EVENT_STREAM | STABLE | `slo.projection.stream` | frontend ops.ts EventSource, WebSocket telemetry clients |

