# PYTHIA fault-injection evidence

Generated from `governance/api_registry.yaml` + `governance/service_fabric.yaml` by `governance/render_service_fabric.py`. Do not edit by hand.

Each row is a declared injection. `status: EXECUTED` means the named
proof test runs the injection against the live seam and asserts the
expected behaviour. Unavailable environments are declared, never
painted green.

| scenario | target | injection | expected | proof | status |
| --- | --- | --- | --- | --- | --- |
| `fi.guardian.deny_mutation` | `al_haras.guardian` | privileged POST arrives with no subscription credentials | signed denial receipt, failure_class FORBIDDEN or UNAUTHORISED, zero mutation committed | `tests/test_fault_injection.py::WireFaultInjectionTests.test_fi_guardian_deny_mutation | EXECUTED |
| `fi.theseus.custody_absent` | `theseus.custody` | custody store not mounted in the serving environment | custody component reports not_mounted; no false custody completion | `tests/test_fault_injection.py::WireFaultInjectionTests.test_fi_theseus_custody_absent | EXECUTED |
| `fi.stratum.disconnect` | `stratum.v1` | configured pool endpoint is unreachable | stratum component reports disconnected; no fabricated mining progress | `tests/test_fault_injection.py::WireFaultInjectionTests.test_fi_stratum_disconnect | EXECUTED |
| `fi.remote_gpu.breaker_opens` | `chronus.remote_opencl_v2` | remote endpoint unreachable for consecutive calls | RemoteCircuitBreaker opens at threshold; calls fail fast DEPENDENCY_UNAVAILABLE; no fallback authority is granted | `tests/test_fault_injection.py::CircuitBreakerTests.test_fi_remote_gpu_breaker_opens | EXECUTED |
| `fi.remote_gpu.half_open_probe` | `chronus.remote_opencl_v2` | endpoint still dead when recovery timeout elapses | exactly one half-open probe is admitted; failure re-opens the breaker | `tests/test_fault_injection.py::CircuitBreakerTests.test_fi_remote_gpu_half_open_probe | EXECUTED |
| `fi.request.duplicate` | `pythia.control_api` | identical Idempotency-Key submitted twice inside the retention window | recorded outcome replayed with idempotent_replay; no re-execution | `tests/test_fault_injection.py::WireFaultInjectionTests.test_fi_request_duplicate | EXECUTED |
| `fi.request.oversized` | `pythia.control_api` | request body beyond _TOE_MAX_BODY_BYTES | 413 with failure_class INVALID_REQUEST | `tests/test_fault_injection.py::WireFaultInjectionTests.test_fi_request_oversized | EXECUTED |
| `fi.request.malformed_json` | `pythia.control_api` | invalid JSON body on a mutating route | 400 with failure_class INVALID_REQUEST | `tests/test_fault_injection.py::WireFaultInjectionTests.test_fi_request_malformed_json | EXECUTED |
| `fi.request.broken_correlation` | `pythia.control_api` | malformed correlation id in request headers | id replaced by a minted one — never trusted as-is | `tests/test_service_constitution.py::ConstitutionWireTests.test_correlation_envelope_is_complete | EXECUTED |
| `fi.backend.unconfigured` | `kellogg.tensor.runtime` | specialist backend not configured in this environment | routes report NOT_CONFIGURED/DEPENDENCY_UNAVAILABLE — no fabricated specialist answer | `tests/test_fault_injection.py::WireFaultInjectionTests.test_fi_backend_unconfigured | EXECUTED |
| `fi.telemetry.reordered` | `pythia.telemetry.stream` | client replays a stale last_seq cursor | only events with seq > last_seq are emitted; reordered/duplicate frames never re-delivered | `tests/test_fault_injection.py::WireFaultInjectionTests.test_fi_telemetry_reordered | EXECUTED |
| `fi.turing.unavailable` | `turing.vqc_pipeline` | TURING pipeline absent from the serving environment | consumers receive typed unavailable — no turing answer is fabricated | `tests/test_fault_injection.py::WireFaultInjectionTests.test_fi_turing_refusal | EXECUTED |
| `fi.m3.runtime` | `chronus.remote_opencl_v2` | M3 hardware acceleration path | — | `none | M3_UNAVAILABLE |

**12/13 scenarios EXECUTED** — the rest are declared
`M3_UNAVAILABLE` (no M3 device in this environment).

