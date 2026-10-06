# Production API & service-communication evidence pack

Scope: canonical API registry, contract enforcement gate, live voyages,
clean-environment execution, and installed-artifact verification on branch
`devin/1791302173-api-service-closure` (baseline `f50f2e9`).

## Evidence classes observed

| Class | Status | Where |
| --- | --- | --- |
| SOURCE_PRESENT | yes | all 60 registry entries map to real `implementation_path`s (AST/inspect-verified) |
| SOURCE_WIRED | yes | route parity AST-extracts the dispatch tables of `control_api.py`; internal contracts bind to `salamander.control_plane`, `theseus`, `ovid`, `turing…pipeline`, `tensor` |
| LOCAL_TEST_PASSED | yes | `tests/test_production_api_contract.py`: 43 tests / 59 subtests (post-close-out head `ed3e3df`) |
| LOCAL_HTTP_E2E_EXECUTED | yes | ThreadingHTTPServer voyages on `127.0.0.1:0` — healthz, readyz, telemetry summary/history/events/ops/causal, system map/verify, metrics, security status, config GET/PUT, guardian-mediated mining + tensor + toe routes with minted subscription tokens |
| LOCAL_CROSS_SERVICE_EXECUTED | yes | TOE collapse voyage produces Theseus-anchored custody records; Theseus/Ovid/Salamander contracts exercised through their real typed calls |
| INSTALLED_ARTIFACT_EXECUTED | yes | `governance/installed_artifact_acceptance.py` — 12/12 on wheel-installed `pythia-api` console script from a neutral cwd; imports resolve from `site-packages` only |
| CI_EXECUTED | **TESTED (manual)** | GitHub Actions still registers `runner_id=0` on head `ed3e3df` (18 checks scheduled, every probed job log `BlobNotFound` — no runner ever executed a step): `CI_UNAVAILABLE — RUNNER DID NOT EXECUTE`. Per the close-out directive the manual equivalent ran locally: `pytest tests/test_production_api_contract.py` green on Python 3.11.9, 3.12.10, 3.13.12 — `evidence/phase_2a/ci_manual_3.1*.txt`, classification in `evidence/phase_2a/ci_status.json` |
| LIVE_POOL_OBSERVED | not claimed | no live pool session on this host |
| PHYSICAL_DEVICE_OBSERVED | not claimed | no mining device bound on this host; voyages accept `armed_no_device`/honest-negative outcomes |
| PERFORMANCE_MEASURED | not claimed | out of scope |
| POOL_ACCEPTANCE_OBSERVED | not claimed | `mining.submit` acceptance is established only by a literal pool response, which did not occur |

## Gates and what they prove

| Gate | Command | Proves |
| --- | --- | --- |
| Contract suite | `python -m pytest tests/test_production_api_contract.py -x -q` | registry integrity → route parity → HTTP voyages → internal contracts → mutation self-tests |
| Docs sync | `python governance/render_api_contract.py --check` | `docs/PYTHIA_API_CONTRACT.md` + `docs/openapi.yaml` regenerate **byte-for-byte** identical to the committed files (read-bytes compare; write-bytes render — CRLF write on Windows had made convergence impossible) |
| Mutation self-test | `MutationGateTests` + `GeneratedDocRoundTripTests` inside the suite | A: removing a declared route, B: adding an undeclared handler, C: adding a handler under a reserved prefix, plus a one-byte drift in either generated doc — each fails the gate |
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

## Registry ↔ handler parity — three directions

| Direction | Check | Verdict |
| --- | --- | --- |
| A — every declared concrete HTTP route has a handler | `test_implemented_surface_equals_declared_surface` (missing == []) | PASS — 58 declared == 58 implemented |
| B — every handler has a registry entry | same test (extra == []) | PASS |
| C — every `RESERVED_NAMESPACE` entry has NO handler | `test_reserved_namespaces_have_no_implementation` — prefix behind guardian AND no served route beneath | PASS — 7 reserved prefixes, none served |

Mutation self-tests prove each direction fires (see `evidence/phase_2a/mutation_selftests.xml`).

## Open items — resolved

| Item | Status |
| --- | --- |
| Reserved-prefix handler | CLOSED — Direction C + mutation self-test (`test_gate_detects_a_handler_under_a_reserved_prefix`) |
| `X-Request-Id` sane definition | CLOSED — stated at `_REQUEST_ID_RE` (1–128 chars, alphanumeric lead, then `[A-Za-z0-9._:@-]`); `test_correlation_envelope_rejects_malformed_ids` asserts malformed ids mint over the wire, never echo — `evidence/phase_2a/xrequestid_policy.txt` |
| SALAMANDER authority grep | CLOSED — `grep -Rni "OvidRecordIdentity\|TheseusProjection"` over the tree: zero occurrences (both symbols originate on the unmerged M3 branch); no stale copies — `evidence/phase_2a/salamander_authority_grep.txt` |

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
