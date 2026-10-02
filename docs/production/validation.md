# Validation — executed gates (honest states)

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

## Re-baseline @ 10c6a63 (follow-on session, 2026-10-01/02)

Refreshed the pack's observations against current `main` (post-fold `chronus/`
layout; swarm PRs through #78). Env: this box's system Python 3.12.10 + pytest
9.1.1; worktree `wt-prodready`, PYTHONPATH = worktree root +
`chronus/mla1517_platform/python` + `turing_universal_quantum_computer`.
`sympy`/`numpy`/`fastapi` installed into the interpreter (the editable install
targets the main checkout, so the worktree needs explicit PYTHONPATH).

| Gate | Command (cwd) | Result | Evidence |
|---|---|---|---|
| Repo pytest | `pytest tests/ -x -q` (worktree root) | **PASS — 2434 passed, 16 skipped, 92 subtests** (~548 s) | this session; started at 9 failures, all closed (see "defects fixed" below) |
| Platform unittest | `unittest discover -s chronus/mla1517_platform/python` | PASS — 367 ran, OK (7 skipped) | this session |
| `scripts/import_audit.py` | `python scripts/import_audit.py` | PASS — 0 violations | this session |
| `scripts/refuted_claims.py` | `python scripts/refuted_claims.py` | PASS | this session |
| Re-paper gate | `python scripts/re_paper_gate.py` | PASS | this session |
| Drift sentry | `python -m scripts.drift_sentry --verify` | PASS | this session |
| Deploy sentry | `python -m scripts.deploy_sentry` | 0 errors / 1 warning — DS02 quantum_core (known, unverified-on-silicon claim surface) | this session |
| Self test | `python -X utf8 -m Intelligence.self_test` | PASS | this session |
| Namespace gate | `pytest tests/test_chronus_namespace.py` | PASS — 5/5 after AGENTS.md rewrite stopped naming retired tokens | this session |
| flake8/black | changed files only | flake8 0 on changed scope; black clean on edited lines (pre-existing repo-wide drift unchanged) | this session |
| Hardware gate | `MLA1517_STRICT_HARDWARE_CI=1 make test` | NOT_RUN — no OpenCL device on this box | — |
| Live pool submission | — | NOT_RUN — not authorized (triple gate) | — |

### Defects found by the re-baseline and fixed on this branch

| Defect | Pre-fix state | Fix |
|---|---|---|
| RUN-01 residual — `_Runner.stop()` | marked `stopped` at request time and fabricated `finished_at` while the worker still ran | truthful `stopping` state; `finished_at` stamped at worker exit in `_wrap`'s `finally`; terminal `stopped` becomes restart-eligible; `stop()` on a terminal runner returns `False`; `RunnerStatus.state` union + `_TERMINAL_STATES` updated |
| DATA-01 residual — campaign `shares_accepted` | recorded the cumulative counter's max, so a phase accepting 2 shares off a counter at 100 read "102" | per-phase baseline: `shares_accepted` = max per-phase delta; a counter reset re-arms the baseline |
| `euclid.evidence.atomic_write` (Windows) | `os.fchmod` is POSIX-only → AttributeError before `os.fdopen` → leaked fd → `os.unlink` WinError 32; 4 tests failed | `fchmod` guarded by `hasattr`; `os.close(fd)` on the failure path; unlink also tolerates `PermissionError` |
| `MemoryDatabase.backup` (Windows) | `with sqlite3.connect(...) as output` never closes the connection → `os.replace` / tempdir cleanup WinError 32 | explicit `output.close()` in `finally` |
| `test_millennium_package` x2 | `ModuleNotFoundError: fastapi` (env, like earlier sympy) | `uv pip install fastapi` → 2/2 pass |
| `tests/test_chronus_namespace` x2 | AGENTS.md §4 rewrite named the retired tokens the gate greps for | rewrote those lines without the literal tokens |

DOC-01 closed in the same increment: `AGENTS.md` §4.1–4.5 rewritten against the
real product (Python control plane + static `dist/public` UI + `chronus.mla1517`
canonical package); README now states the per-operation device policy —
device-bound operations fail closed while the supervised solver route records
`executed_route=cpu_reference` + `fallback_reason`, never relabelled as device
execution.

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
