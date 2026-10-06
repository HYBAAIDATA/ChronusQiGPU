# Production API & service-communication evidence pack

Scope: canonical API registry, contract enforcement gate, live voyages,
clean-environment execution, and installed-artifact verification on branch
`devin/1791302173-api-service-closure` (baseline `f50f2e9`).

## Evidence classes observed

| Class | Status | Where |
| --- | --- | --- |
| SOURCE_PRESENT | yes | all 60 registry entries map to real `implementation_path`s (AST/inspect-verified) |
| SOURCE_WIRED | yes | route parity AST-extracts the dispatch tables of `control_api.py`; internal contracts bind to `salamander.control_plane`, `theseus`, `ovid`, `turing…pipeline`, `tensor` |
| LOCAL_TEST_PASSED | yes | `tests/test_production_api_contract.py`: 37 tests / 59 subtests |
| LOCAL_HTTP_E2E_EXECUTED | yes | ThreadingHTTPServer voyages on `127.0.0.1:0` — healthz, readyz, telemetry summary/history/events/ops/causal, system map/verify, metrics, security status, config GET/PUT, guardian-mediated mining + tensor + toe routes with minted subscription tokens |
| LOCAL_CROSS_SERVICE_EXECUTED | yes | TOE collapse voyage produces Theseus-anchored custody records; Theseus/Ovid/Salamander contracts exercised through their real typed calls |
| INSTALLED_ARTIFACT_EXECUTED | yes | `governance/installed_artifact_acceptance.py` — 12/12 on wheel-installed `pythia-api` console script from a neutral cwd; imports resolve from `site-packages` only |
| CI_EXECUTED | **CI_UNAVAILABLE** | GitHub Actions runners currently report runner_id=0/steps=0 on the inspected baseline; local clean-env runs are a separate evidence class and are not upgraded to CI evidence |
| LIVE_POOL_OBSERVED | not claimed | no live pool session on this host |
| PHYSICAL_DEVICE_OBSERVED | not claimed | no mining device bound on this host; voyages accept `armed_no_device`/honest-negative outcomes |
| PERFORMANCE_MEASURED | not claimed | out of scope |
| POOL_ACCEPTANCE_OBSERVED | not claimed | `mining.submit` acceptance is established only by a literal pool response, which did not occur |

## Gates and what they prove

| Gate | Command | Proves |
| --- | --- | --- |
| Contract suite | `python -m pytest tests/test_production_api_contract.py -x -q` | registry integrity → route parity → HTTP voyages → internal contracts → mutation self-tests |
| Docs sync | `python governance/render_api_contract.py --check` | `docs/PYTHIA_API_CONTRACT.md` + `docs/openapi.yaml` are byte-identical regenerations of the registry |
| Mutation self-test | `MutationGateTests` inside the suite | removing a declared route or adding an undeclared one makes `_parity_diff` non-empty — the gate detects drift in both directions |
| Clean environment | fresh `git worktree` checkout, same pytest command | contract suite passes on a pristine tree: 37 passed, 59 subtests |
| Installed artifact | `python -m venv` outside repo → `pip install ./turing_universal_quantum_computer .` → `governance/installed_artifact_acceptance.py` | 12/12 checks; liveness, correlation mint/echo, readiness components, telemetry, signed guardian denials, reserved-namespace fail-closed, restart determinism |

## Production API completion matrix

| Service/API | Contract | Implemented | Wired | HTTP/transport tested | Cross-service tested | Installed artifact | Runtime-observed | Verdict |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Control/health | yes | yes | yes | yes (voyage) | n/a | yes | yes | CLOSED |
| Config | yes | yes | yes | yes (GET/PUT voyages, denied write) | n/a | yes | yes | CLOSED |
| PYTHIA mining | yes | yes | yes | yes (subscription-token voyages; denied without token) | via TOE evidence path | yes (fail-closed path) | yes (honest `no device`) | CLOSED |
| Stratum | yes | yes | yes | yes (status endpoint + internal adapter contract) | adapter↔target contract | n/a | status only | CLOSED — no live pool |
| AL HARAS | yes | yes | yes | yes (guardian deny/allow ladder, signed denials) | mediates privileged surface | yes | yes | CLOSED |
| TURING | yes | yes | yes | via tensor/TOE path | VQCPipeline typed contract | yes | yes | CLOSED |
| KELLOGG | yes | yes | yes | yes (capabilities/execute voyages) | tensor.receipt/1 contract | yes | yes | CLOSED |
| CHRONUS local | yes | yes | yes | yes (discovery/status) | internal contract | yes | yes | CLOSED |
| CHRONUS remote | yes | yes | yes | existing loopback suite (`tests/test_remote_hasher.py`) | — | n/a | — | CLOSED locally |
| THESEUS | yes | yes | yes | via custody path | put/get/record/verify/snapshot contracts | yes | yes | CLOSED |
| OVID | yes | yes | yes | via transform path | working-form contract | yes | yes | CLOSED |
| SALAMANDER | yes | yes | yes | yes (fault endpoint voyage) | ActionRegistry/typed contract | yes | yes | CLOSED |
| EUCLID handoffs | yes | yes | yes | yes (agentic/campaign/status voyages) | runner contract | yes | yes | CLOSED |
| telemetry/SSE | yes | yes | yes | yes (summary/history/events/ops/causal + stream contract) | — | yes | yes | CLOSED |
| storage/file API | yes | yes | yes | boot audit JSONL + Theseus file contracts | — | n/a | yes | CLOSED |

## OpenAPI decision

`docs/openapi.yaml` is **generated, not authored**: it renders every declared
concrete HTTP route from the registry with its auth scheme, truth class,
api_id and deprecation state. The registry remains the canonical contract;
the OpenAPI document is a derived view — the sync gate fails if they drift.
Body schemas stay in the registry's `request_schema`/`response_schema`
fields rather than being duplicated into OpenAPI components (single source
of truth).

## Defects found and fixed during closure

1. **Refused POST aborted the connection** — a denied POST with a body
   left the socket mid-read; Windows surfaced `WinError 10053`.
   `control_api.py` now drains the request body before refused/404
   responses (`_discard_request_body`).
2. **No correlation envelope** — responses now always carry
   `X-Request-Id` (echoing sane caller ids, minting otherwise).
3. **Readiness was a single boolean** — `/api/v1/readyz` and `/readyz`
   now report per-component truth (`identity`, `boot_audit`,
   `worker_heartbeat_dir`, `guardian`) so a degraded component cannot hide
   inside `ready: true`.
4. **Authority semantic drift** — SALAMANDER/THESEUS/OVID docstring and
   test language corrected: SALAMANDER orchestrates; THESEUS owns
   custody/records/provenance; OVID owns transformation/lineage only.

## Not claimed

- No physical mining device, live pool session, or share acceptance was
  observed; the registry and doc say so rather than faking availability.
- CI evidence is unavailable on the current infrastructure; when runners
  return, rerun the same suite remotely before upgrading classification.
