# Console field-to-owner wiring

Base inspected: `4f71b5647e5cacd053e9a9d545ab5f26d38b4f34`. Candidate changes preserve Python as the only control/status service. All paths below are relative to the configured `VITE_PYTHIA_PYTHON_API_URL`. Labels, spacing and user inputs are not runtime measurements.

## Shared read path

`App → useConsole → apiFetch → control_api.Handler._route_get → status_payload / console_sources_payload`. Only session confirmation uses the access helper directly. Children receive snapshots; none has a separate polling timer or pool-selector config fetch.

| UI fields / component | Endpoint and exact payload region | Current producer / owner | Missing / evidence treatment |
|---|---|---|---|
| Header principal/role/allowed/reason | `/api/v1/control/session` principal_id, role, authenticated | server principal map / security boundary | No browser-inferred CEO |
| Header service state/device | status generated_at, ready_to_mine, device surface | canonical PYTHIA/Chronus service | No EUCLID_ONLINE inference; missing device = not reported |
| Readiness card | status.ready_to_mine.ready/reason; stratum pool identity only if present | control_api readiness predicate | No readiness recomputation in UI |
| Stratum state/transport/subscribed/authorized/generation/job age/job ID/fingerprint/target/difficulty | status.stratum | PYTHIA/Chronus Stratum owner | No connection inference from omitted fields |
| Submission stages/submitted/accepted/rejected/unknown/disconnects | status.stratum.submission and supplied counters | exact hasher/Stratum/pool acknowledgement | Last accepted submission, not historical total, drives accepted stage |
| Stratum profile/endpoint/worker/password availability | status identity/stratum profile | configured canonical runtime | No endpoint constructed from undefined host/port; secrets not invented |
| Engine product/path/backend/execution/hashrate basis/exact ladder | status engine fields | Chronus canonical engine | Only supplied backend labels; no inferred acceleration |
| Solver arms/lanes/solvers/partition | status arms/solver fields | Chronus/PYTHIA execution configuration | Missing bounds/workers not replaced with 1/32/600 |
| Runtime pools/target/bounds/arms/live submit | status.runtime | canonical RuntimeConfig | Writes do not optimistically replace status; offline or missing config disables fieldset |
| Verification runner | status.console.verification | system_fabric.verification_status | Owner document only; not new proof |
| Selftest runner | status.console.selftest | system_fabric.selftest_status | No invented module count or PASS |
| Agentic workflow | status.console.agentic | system_fabric.agentic_status / agentic mining | Supervised state; no second actuator introduced |
| Campaign | status.console.campaign | system_fabric.campaign_status / pool campaign | Configured phase labels not performance claims |
| Subsystem map / Manifold | status.console.fabric | _fabric_map_payload / system fabric | Backend map, not simulated geometry or discovery |
| Telemetry live/session/history | status.console.telemetry + audit | telemetry_summary_payload / audit_tail_payload | Null/failure not numerical zero |
| Intelligence / cognition lenses | status.console.intelligence + cognition | system_fabric.intelligence_status / euclid_cognition_status | TOE/EUCLID content only when actual producer supplies it; not direct VQC qualification |
| Supervised workers | status worker records | canonical control plane | No synthetic workers |
| OpenCL device surface | status device/GPU owner data | Chronus/OpenCL adapter | No hardware present/qualified inference from HTTP success |
| Evidence availability/stages/receipt | `/api/v1/mining/evidence` | existing mining evidence producer + independent AL HARAS preflight | Separate CEO + tenant subscription. Optional receipt_id/tenant_id/payload_digest/result_digest/evidence_status displayed only when supplied |
| Audit records | status.console.audit | audit_tail_payload(30) | Backend raw inspection, not a certified tenant export; export unavailable |
| Source/time/error labels | status generated_at + each section's own data; transport outcomes | producer/HTTP layer | Source label is not cryptographic attestation |

`console_sources_payload` returns a failed section as null and `unavailable[section]` exception type. It does not replace it with a synthetic success. The outer schema remains `chronus.mla1517.status/1` with an additive `console` field; installed-client compatibility still needs full-service testing.

## Existing mutations (not exercised against a live miner here)

SystemFabricPanel retains POST `/api/v1/system/verify`, `/api/v1/intelligence/selftest`, `/api/v1/agentic/start`, `/api/v1/agentic/stop`, `/api/v1/campaign/start`, `/api/v1/campaign/stop`, `/api/v1/mining/start`, `/api/v1/mining/stop`, `/api/v1/mining/switch`, `/api/v1/mining/elevate`, `/api/v1/mining/escalate`. RuntimeControlPanel retains PUT `/api/v1/config` for pools, target, arms and live-submit. The source of truth is the server response and the subsequent shared snapshot; the browser does not claim actuator acknowledgement from a button click. Existing guardian prefixes remain independent. The client prefix list now includes `tensor` to match the server boundary.

## Read authorization compatibility change

Exact console read paths in `_CEO_READ_PATHS` now require a current server-mapped CEO before producing data: status aliases, config, audit tail, Stratum status, telemetry summary/history/causal/events/ops/session/stream and websocket telemetry. Mining evidence additionally retains guardian checks; its CEO bearer is in a separate header. Legacy shared admin-key identity remains operator, not CEO. Unrelated public GETs do not automatically receive control credentials. This is an intentional compatibility change requiring existing automation/proxy/client qualification. The exact-route checks are not a full service-wide read-surface security certification; readiness/metrics and other routes require separate audit.

## Product bindings: do not invent edges

| Product / authority | Binding established by this tranche | Still unavailable / not qualified |
|---|---|---|
| PYTHIA mining | canonical control/Stratum/status/receipt display | Live share submit + pool ack proof |
| Chronus | runtime/device/solver surfaces | Device-bound execution, acceleration and full caller compatibility |
| TOE | owner-supplied intelligence/agentic documents only | Direct per-capability receipts/learning/ordering lift in this UI |
| EUCLID | owner-supplied cognition section | Separate gateway health/role journeys and production qualification |
| SALAMANDER | existing fabric/runtime documents when published | Direct seven-stage healer receipt wiring and live recovery drill |
| Agentic mining | existing supervised agentic status/actions | Live bounded-action/feedback qualification |
| Kellogg | no new direct qualified console endpoint | Math/tensor receipts; not inferred from presence in map |
| Ovid | no new direct qualified console endpoint | Transform/materialisation receipts and API acceptance |
| Theseus | no new direct qualified console endpoint | Tenant custody/export/recovery receipts and durability qualification |
| PULVINI | no new direct qualified console endpoint | Folding receipts; not assigned custody responsibilities |
| TURING VQC | separate app preserved, no new MLA-derived VQC truth | Registry/installed-package execution and runtime qualification |

Full portfolio readiness is not claimed by this console tranche.
