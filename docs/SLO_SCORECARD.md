# PYTHIA SLO scorecard

Generated from `governance/api_registry.yaml` + `governance/service_fabric.yaml` by `governance/render_service_fabric.py`. Do not edit by hand.

**Measurement honesty:** a target is not compliance. `measured`
reports the evidence class actually observed for that SLO in this
environment — `UNMEASURED` is a first-class answer, not a gap filled
with a claim.

| slo | tier | dimensions | targets | error budget | measured |
| --- | --- | --- | --- | --- | --- |
| `slo.cli` | R1 | fail-fast on misconfiguration, boot success under valid config | — | release-managed | LOCAL_TEST_PASSED |
| `slo.configuration` | R1 | atomic write success, invalid-reject correctness | — | release-managed | RECOVERY_EXECUTED |
| `slo.constitutional` | R0 | availability, verdict latency, denial evidence completeness | availability: fail-closed-by-design; denial_latency_p95: measured-locally | none — integrity failures are not budget-eligible | FAULT_INJECTION_EXECUTED |
| `slo.evidence` | R1 | append success, tail accuracy | — | release-managed | LOCAL_HTTP_E2E_EXECUTED |
| `slo.healing` | R3 | remediation success, postcondition verification, rollback success | postcondition_verification: required | release-managed | LOCAL_TEST_PASSED |
| `slo.mining.control` | R1 | command acceptance rate, job-to-plan latency, stale-job cancellation latency | command_acceptance: measured-locally | release-managed | FAULT_INJECTION_EXECUTED |
| `slo.mining.execution` | R1 | plan-to-execution latency, execution completion, verification completion | verification_pass: required-for-success | release-managed | LOCAL_HTTP_E2E_EXECUTED |
| `slo.mining.plan` | R1 | plan latency, plan validity | — | release-managed | UNMEASURED |
| `slo.mining.read` | R1 | availability, latency_p95 | — | release-managed | LOCAL_HTTP_E2E_EXECUTED |
| `slo.mining.telemetry` | R1 | sidecar freshness within ttl, counter accuracy | sidecar_ttl_s: 30 | release-managed | LOCAL_HTTP_E2E_EXECUTED |
| `slo.operator.mutation` | R1 | mutation acceptance truth, atomicity | — | release-managed | RECOVERY_EXECUTED |
| `slo.projection.read` | R4 | availability, latency_p95, freshness | — | release-managed | LOCAL_HTTP_E2E_EXECUTED |
| `slo.projection.stream` | R4 | event delivery, drop accounting | drops: always counted + reported | release-managed | RECOVERY_EXECUTED |
| `slo.remote_execution` | R1 | probe latency, scan completion, attestation validity | probe_timeout_s: 5; sha256d_timeout_s: 300 | release-managed | FAULT_INJECTION_EXECUTED |
| `slo.specialist` | R2 | availability reporting honesty, typed failure rate, result latency | — | release-managed | LOCAL_TEST_PASSED |
| `slo.stratum` | R1 | connectivity uptime, submission response latency, stale-job rejection | submit_response: literal-pool-verdict-only | release-managed | FAULT_INJECTION_EXECUTED |
| `slo.tenant_store` | R1 | operation success, cross-tenant isolation | cross_tenant_bleed: 0 | release-managed | LOCAL_TEST_PASSED |

## Interfaces per SLO

- `slo.cli`: `chronus.cli.remote_agent`, `pythia.cli.api`, `pythia.cli.miner`
- `slo.configuration`: `pythia.runtime_config_file`
- `slo.constitutional`: `al_haras.guardian`, `al_haras.security.evaluate`, `al_haras.security.status`, `al_haras.security.subscribe`, `namespace.admin`, `namespace.assembly`, `namespace.policy`, `namespace.quantum`, `namespace.recovery`, `namespace.scale`, `namespace.worker`, `theseus.custody`
- `slo.evidence`: `pythia.boot_audit`
- `slo.healing`: `salamander.control_plane`, `salamander.fault`
- `slo.mining.control`: `pythia.agentic`, `pythia.campaign`, `pythia.mining.control`
- `slo.mining.execution`: `chronus.execution`
- `slo.mining.plan`: `euclid.orchestration`
- `slo.mining.read`: `pythia.mining.evidence`
- `slo.mining.telemetry`: `pythia.worker_heartbeat`
- `slo.operator.mutation`: `pythia.config.update`, `pythia.system.verify.start`
- `slo.projection.read`: `legacy.api_health`, `pythia.audit.tail`, `pythia.config.read`, `pythia.control.session`, `pythia.gpu`, `pythia.hardware.status`, `pythia.health`, `pythia.intelligence.status`, `pythia.knowledge`, `pythia.metrics`, `pythia.readiness`, `pythia.ready_to_mine`, `pythia.static_spa`, `pythia.status`, `pythia.stratum.status`, `pythia.system.map`, `pythia.system.verify.read`, `pythia.telemetry`
- `slo.projection.stream`: `pythia.telemetry.stream`
- `slo.remote_execution`: `chronus.remote_opencl_v2`
- `slo.specialist`: `kellogg.tensor.capabilities`, `kellogg.tensor.execute`, `kellogg.tensor.runtime`, `ovid.transform`, `pythia.intelligence.autonomous`, `pythia.intelligence.cognition_solve`, `pythia.intelligence.engineer`, `pythia.intelligence.maintenance`, `pythia.intelligence.selftest`, `toe.collapse`, `turing.vqc_pipeline`
- `slo.stratum`: `stratum.v1`
- `slo.tenant_store`: `hyba_db.store`

## Error-budget policy

- **rule** — error budgets manage release cadence; they never excuse an R0 integrity failure or authorise fabricated success
- **on_exhausted** — freeze non-safety releases for the affected service until owner-approved recovery

## Recovery objectives (RTO/RPO)

| tier | RTO | RPO | replay | state source |
| --- | --- | --- | --- | --- |
| R0 | owner-approved after measurement — currently UNMEASURED | zero for committed records (append-only/content-addressed) | deterministic replay from records required | THESEUS store + boot audit |
| R1 | UNMEASURED — measure current recovery first | worker metrics granularity (sidecar ttl 30s) | session rebuild from pool notify stream; no replayed share submits | runtime_config_file + sidecars + pool session |
| R2 | UNMEASURED | per-request | replayable deterministic requests | caller request + THESEUS custody |
| R3 | UNMEASURED | per-remediation record | remediation steps re-verifiable | THESEUS evidence + control plane state |
| R4 | n/a — projections rebuild | n/a | n/a | authoritative services |

