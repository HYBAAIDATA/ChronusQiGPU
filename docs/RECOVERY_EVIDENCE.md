# PYTHIA recovery evidence

Generated from `governance/api_registry.yaml` + `governance/service_fabric.yaml` by `governance/render_service_fabric.py`. Do not edit by hand.

| scenario | target | injection | expected | proof | status |
| --- | --- | --- | --- | --- | --- |
| `rc.restart.clean` | `pythia.control_api` | control API restarted over the same state directory | readiness/stratum/custody components report the same honest post-restart truth; no state invented | `tests/test_stateful_recovery.py::StatefulRecoveryTests.test_rc_restart_clean | EXECUTED |
| `rc.partial_write.config` | `pythia.runtime_config_file` | runtime config file contains truncated/corrupt JSON | config surface reports the corruption; readiness degrades honestly; no crash, no silent default | `tests/test_stateful_recovery.py::StatefulRecoveryTests.test_rc_partial_write_config | EXECUTED |
| `rc.duplicate_delivery` | `pythia.control_api` | same mutating request re-delivered inside the idempotency window | replay returns the recorded outcome without re-execution | `tests/test_stateful_recovery.py::StatefulRecoveryTests.test_rc_duplicate_delivery | EXECUTED |
| `rc.reordered_delivery` | `pythia.telemetry.stream` | event cursor rewound (stale last_seq) | seq-gated emission — duplicates are not re-sent | `tests/test_stateful_recovery.py::StatefulRecoveryTests.test_rc_reordered_delivery | EXECUTED |
| `rc.atomic_write.ports` | `pythia.control_api` | shared port file rewritten while readers race it | tmp+os.replace atomic publication; readers never see a torn write | `tests/test_stateful_recovery.py::StatefulRecoveryTests.test_rc_atomic_write_ports | EXECUTED |
| `rc.m3.recovery` | `chronus.remote_opencl_v2` | M3 host failover | — | `none | M3_UNAVAILABLE |

## Resilience maturity

- **LEVEL_0** — unknown
- **LEVEL_1** — implemented
- **LEVEL_2** — monitored
- **LEVEL_3** — tested recovery
- **LEVEL_4** — fault-injected / resilient by design

Target: R0/R1 critical journeys at LEVEL_3 minimum, LEVEL_4 where safely testable

_an interface is not resilient merely because it has a retry loop_

