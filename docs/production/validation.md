# Validation — executed gates (honest states)

Pin: `e09afab1b27a15006ba9384bdbb3f7192dd94251` (main @ 2026-09-28).
Env (coordinator box): Windows, Python 3.14.7 (`uv` venv), Node 20.19.0 (manifest
requires ≥22 — gates nonetheless pass on 20; engines mismatch is recorded, not hidden).
Install: `uv pip install -e ".[ml,dev]" -e ./turing_universal_quantum_computer`.

## Phase-0 baseline results @ e09afab

| Gate | Command (cwd) | Result | Evidence |
|---|---|---|---|
| Repo pytest | `pytest tests/ -x -q` (root) | PASS — 1221 passed, 8 skipped, 92 subtests | pytest_full.log |
| Platform unittest | `unittest discover -s mla1517_platform_v3.4/python` | PASS — 203 tests, 6 skipped | baseline_bottom.log |
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

## Invocation pitfalls recorded (so owners don't repeat them)

- TUQC tests must run with cwd = `turing_universal_quantum_computer/`; from repo
  root, `import turing_universal_quantum_computer` resolves the outer dir as a
  namespace package (`__file__=None`) and 30/45 tests fail on AttributeError —
  an invocation artifact, not code breakage. Real count: 44/45.
- `.venv` venv lacks pip → use `uv pip install --python .venv/Scripts/python.exe`.
- `npm` bash-vs-cmd: use `npm.cmd` inside `frontend/`.
