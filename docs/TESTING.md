# Testing

How to run every gate, and what "pass" means. A PASS is only real if the test
actually executed — never inferred from source. See the baseline matrix in
`docs/PRODUCTION_READINESS_AUDIT.md` §3.

## Commands

```bash
pip install -e ".[ml,dev]"        # deps (needs sympy for [ml])
python -m pytest tests/ -x -q     # root suite: 593 passed, 1 skipped
python -m unittest discover -s mla1517_platform_v3.4/python  # platform: 130 tests
python -m flake8 --count          # lint (.flake8 config): 0 findings
python -m compileall Intelligence core_engine legacy/python_backend experiments scripts tests mla1517_platform_v3.4
npm ci && npm run lint && npm run build   # tsc + vite
```

## Hardware gate (requires device)

```bash
MLA1517_STRICT_HARDWARE_CI=1 MLA1517_GPU_BACKEND=opencl make test
```

A missing device must produce unavailable/failed-closed — never converted to pass.

## Skips

Pre-existing environment guards skip when no device/OpenCL is present
(6 in the platform suite, 1 in root). These are honest skips, not failures.

## Coverage of the audit's required cases

| Requirement | Where verified |
|---|---|
| Endpoint parsing incl. TLS schemes | `test_host_hardware.py::PureProtocolTests.test_endpoint_parser` + `test_endpoint_parser_schemes` |
| Missing credentials → fail-closed | `tests/test_startup_contract.py::test_stratum_alias_conflict_is_fail_closed` |
| Credentials never in public view/logs | `tests/test_startup_contract.py::test_identity_public_view_contains_no_password` |
| Share validation (bool result, ack) | `tests/test_stratum_live_session.py` |
| Live-submit env gate | `mining/stratum_bridge.py::is_live_submit_approved` + tests |
| Proof-checked submit only | `manifold_pool_coordinator.submit_candidate` (SHA256d-checked before submit) |
| No hashrate fabrication | `control_api.status_payload` + API tests |

## CI parity

`.github/workflows/ci.yml` runs the same commands above; the hardware-gate job
emits an explicit NOT_RUN when no device is attached (matching BLOCKED status).
