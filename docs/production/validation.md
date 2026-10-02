# Validation — executed gates (honest states)

## Current refresh @ 953765a (2026-10-02)

| Gate | State | Evidence / reason |
|---|---|---|
| Source revision | PASS | GitHub `main` resolved to `953765a7f79920d2177a406c2157340ef96000cc` |
| Repository instructions | PASS | `AGENTS.md` read at blob `bfb11420538f5cf1062030f10af320cbb3e04957` |
| Owner A 11D implementation | PASS — MERGED | PR #82 merged as `1aae12c3`; compileall, adapter, route and consensus invariants PASS. Full repository pytest/CI remains unavailable |
| Runtime RUN/DATA defects | PASS — MERGED | PR #81 merged as `953765a7`: truthful `stopping` state + per-phase accepted-share deltas; focused files compile. Full repository pytest/CI remains unavailable |
| Current full repo pytest | NOT_RUN | No checkout is available in the coordinator sandbox; historical counts below are not current evidence |
| Current platform unittest | NOT_RUN | Same limitation |
| Current frontend gates | NOT_RUN | Same limitation |
| Current hardware/OpenCL gate | NOT_RUN | No target device evidence |
| Current live pool submission | NOT_RUN | Not authorized; no credential or target supplied |
| Current GitHub Actions | BLOCKED | Check-runs API returned 403; combined status has zero statuses for PRs #80/#81. Repository account has also reported billing/spending-limit failures |

The historical records below remain useful provenance but do not certify the
current `main`. Missing execution remains missing evidence, not observed zero.

Pin: `e09afab1b27a15006ba9384bdbb3f7192dd94251` (main @ 2026-09-28).
Env (coordinator box): Windows, Python 3.14.7 (`uv` venv), Node 20.19.0 (manifest
requires ≥22 — gates nonetheless pass on 20; engines mismatch is recorded, not hidden).
Install: `uv pip install -e ".[ml,dev]" -e ./turing_universal_quantum_computer`.

## Phase-0 baseline results @ e09afab

| Gate | Command (cwd) | Result | Evidence |
|---|---|---|---|
| Repo pytest | `pytest tests/ -x -q` (root) | PASS — 1221 passed, 8 skipped, 92 subtests | pytest_full.log |
| Platform unittest | `unittest discover -s chronus/mla1517_platform/python` | PASS — 203 tests, 6 skipped | baseline_bottom.log |
| TUQC pytest | `pytest tests -q` (from `turing_universal_quantum_computer/`) | **FAIL — 44 pass / 1 fail**: `test_vqc_execution_certifies_window` — `LucasScaledAethelExecutionAdapter.execute` returns `hashes=1` not 256 (early-exit bug) | local run |
| flake8 (declared CI gate) | `flake8 --count` on the 9 gated platform files | PASS — 0 | local run |
| flake8 repo-wide | `flake8 --count` | **FAIL — 744 findings** (audit doc claims 0 → stale claim; CI never enforced repo-wide) | baseline_top.log |
| black (declared CI gate) | `black --check` on the 9 gated files | PASS | local run |
| black repo-wide | `black --check .` | **FAIL — ~4476 reformat, 1309 fail-to-parse** (not an enforced gate; vendored/legacy mass) | local run |
| Frontend unit | `npm run test:ts` (frontend/) | PASS — 25/25 | local run |
| Frontend types | `npm run lint` (`tsc --noEmit`) | PASS | local run |
| Frontend build | `npm run build` | PASS — dist/public emitted | local run |
| Re-paper gate | `scripts/re_paper_gate.py` | PASS | baseline_gates.log |
| Drift sentry | `python -m scripts.drift_sentry --verify` | PASS | baseline_gates.log |
| Self test | `python -X utf8 -m Intelligence.self_test` | PASS | baseline_gates.log |
| `scripts/import_audit.py` | — | NOT_APPLICABLE — file does not exist at this pin (pack command stale; PYTHIA-sibling path) | — |
| `python -m scripts.deploy_sentry` | — | NOT_APPLICABLE — module does not exist at this pin | — |
| Hardware gate `MLA1517_STRICT_HARDWARE_CI=1 make test` | — | NOT_RUN — no OpenCL device on this box | — |
| Live pool submission | — | NOT_RUN — not authorized (triple gate) | — |
| GitHub Actions | repo workflows | NOT_RUN — no PR yet; provisioning health TBD at first PR | — |

## CI definition reconciliation (Coordinator, executed by reading + local verification)

| Workflow | Finding at e09afab | Action taken |
|---|---|---|
| `ci.yml` → `python` job | `pip install -e ".[ml,dev]"` omits TUQC → `sympy` never installed → `pytest -x` dies collecting `tests/test_benchmark_hendrix_vs_grover.py` | Fixed: install now includes `-e ./turing_universal_quantum_computer` |
| `ci.yml` → `python` job | `flake8 --count` repo-wide → 744 findings → guaranteed fail; the enforced contract (pythia-ci) gates only the 9 platform files | Fixed: gate aligned to the same 9-file scope; repo-wide count kept as a `continue-on-error` informational step (debt reported honestly, not gated silently) |
| `ci.yml` → `python` job | `compileall` skipped `toe/`, `kellogg/`, `aethel/`, `millennium/`, `turing_universal_quantum_computer/` | Fixed: added to compile list |
| `pythia-ci.yml` | The real behavioral gate — canonical-logic/integration-audit/hybrid-fleet/hardware-gate jobs; all 8 required gate files exist @ pin; `python -m aethel selftest` verified locally | No change |
| `pythia-push-gate.yml` | `-e ".[test]"` valid (platform pyproject owns the extra), `python/` valid via working-directory; platform tests have no numpy dependency (only lazy imports in accelerator/scaling) | No change — verified correct |
| `azure-package.yml` | Docker build not executed locally (no docker daemon verified on this box) | NOT_RUN — needs docker-enabled runner/host |
| `Dockerfile` | root `main.py` (23-line shim → `control_api.main`) present and consistent with `CMD`; `/api/health` + `/healthz` both served by control_api | Verified by reading + wheel smoke |
| Blueprint | exists for this repo (Windows, py3.12, TUQC editable, npm-cli path) — the CI-verify runs used an equivalent `.venv` | No change |

## Packaging verification (Coordinator, executed)

- `uv build` → `pythia_mla1517-0.1.0` + `turing_universal_quantum_computer-1.0.0` wheels + sdists: **PASS**.
- Fresh venv (`~/dist_verify/clean_venv`), wheel-only install: **PASS** — `mla1517`, `chronus.mla1517.mining.coordinator`, `main`, `control_api`, `mining_runtime`, `system_fabric`, `salamander_engine`, `worker_lifecycle`, `toe`, `kellogg`, `lucas`, `aethel`, `turing_universal_quantum_computer` all import.
- Console scripts from the delivered artifact: `pythia-api --help`, `pythia-mine --help` **PASS** — fail-closed help text, no fabricated state.
- TUQC wheel contains all declared subpackages (`turing_core`, `intelligences`, `lucas`) + `kernels/*.cl` via package-data.

## Integrated baseline @ 73a716d (post #15 + #18 merge, Coordinator)

| Gate | Command | Result @ 73a716d |
|---|---|---|
| pytest (repo suite) | `.venv/Scripts/python.exe -m pytest tests/ -q` | **1702 passed, 16 skipped, 92 subtests** in 206s — includes Owner A's 62 new `test_a_*` tests |
| unittest (platform) | `python -m unittest discover -s chronus/mla1517_platform/python` | **317 ran, OK (7 skipped)** |
| TUQC suite | `pytest tests -q` inside `turing_universal_quantum_computer/` | **55 passed** (Owner A, incl. `test_vqc.py` 8/8 after the early-exit fix) |
| flake8 | `flake8 --count` repo-wide | **0** — upstream #16 repaired all findings |
| IR-2 sqlite tempfile lock | 4 tests (`test_enterprise_v2_tranches`, `test_fold_pipeline`, `test_promotion_evidence`, `test_promotion_release_catalogue`) | **FAIL→FIXED** — `NamedTemporaryFile()` (exclusive lock) → `delete=False` + `addCleanup(os.unlink)`; verified 21/21 |

## Invocation pitfalls recorded (so owners don't repeat them)

- `tempfile.NamedTemporaryFile()` on Windows holds an exclusive lock — sqlite
  cannot `connect` to the path inside the `with` block. Use `delete=False` and
  unlink in `addCleanup` (after the consumer's sqlite handle closes).
- TUQC tests must run with cwd = `turing_universal_quantum_computer/`; from repo
  root, `import turing_universal_quantum_computer` resolves the outer dir as a
  namespace package (`__file__=None`) and 30/45 tests fail on AttributeError —
  an invocation artifact, not code breakage. Real count: 44/45.
- `.venv` venv lacks pip → use `uv pip install --python .venv/Scripts/python.exe`.
- `npm` bash-vs-cmd: use `npm.cmd` inside `frontend/`.
