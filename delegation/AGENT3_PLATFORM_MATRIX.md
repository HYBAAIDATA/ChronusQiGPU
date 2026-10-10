# Devin Agent Lane — Platform packages + full matrix (Agent 3)

You are one of four agents building/qualifying HYBA distributions for first publication.
Your lane: **SALAMANDER package + `hyba-pythia-mining-runtime` + the full test matrix
and gate scripts on current main**. The integrator merges lane branches, freezes the
RC, and reruns final gates on the frozen SHA.

## Ground truth (do not re-derive)

- Repo checkout: `/Users/demouser/Desktop/PhiEnterprise` (remote
  `https://github.com/PhiEnterprise/PhiEnterprise.git` — **fetch/push BLOCKED, no
  credentials. The old PAT was pasted in chat and is treated as compromised. NEVER push.**)
- Branch `main` @ `e7e17560bb4983a1c84c3d3a5f9e1da3b238ca16`, clean tree.
- macOS arm64, CLT installed. System `python3` is 3.9 — **never use it**.
  Use `~/.local/bin/uv`; CPython 3.12.15 is already installed.
- Shared dep-wheel exchange: **`/tmp/pythia-dist/`** — use wheels already there;
  deposit yours too. `hyba_kellogg_tensor-1.0.0` is present.
- Your matrix run is the BASELINE on current main, not the RC verdict. Label it so.

## Setup

```bash
export PATH="$HOME/.local/bin:$PATH"
cd /Users/demouser/Desktop/PhiEnterprise
git worktree add ../PhiEnterprise-platform -b lane/platform-matrix
cd ../PhiEnterprise-platform
uv venv --seed --python 3.12 .venv
.venv/bin/python -m pip install -q build wheel twine pytest
# then install the repo's real test deps:
.venv/bin/python -m pip install -q -r requirements.txt  # adjust if it pins wrong
mkdir -p /tmp/pythia-dist artifacts/platform-lane
```

## Version scheme (owner-delegated)

First-public version is `1.0.0` for every distribution.
`chronus/mla1517_platform/pyproject.toml` (`hyba-pythia-mining-runtime`) is `0.3.0` →
bump to `1.0.0`. `packaging/salamander` already declares `1.0.0` — leave it.

## Tasks

### T1. SALAMANDER — `hyba-salamander-self-healing==1.0.0`
- `packaging/salamander/` has `build_and_verify.py`, `installed_smoke.py`, `tests/`,
  `MANIFEST.in`, `RELEASE.md`. Read them, then run the full verify script.
- Boundary: ships `salamander*` + `al_haras*` (AL HARAS is bundled, not separate).
- Require `VERIFIED`; copy `packaging/salamander/dist/*` → `/tmp/pythia-dist/`.

### T2. `hyba-pythia-mining-runtime==1.0.0` (chronus/mla1517_platform)
- Bump version `0.3.0` → `1.0.0` in `chronus/mla1517_platform/pyproject.toml`.
- Check its deps (e.g. `hyba-turing-vqc>=1.0`) — pull missing in-tree wheels from
  `/tmp/pythia-dist`; if `hyba-turing-vqc` is absent build it:
  `.venv/bin/python -m build turing_universal_quantum_computer` then copy its dist
  to `/tmp/pythia-dist` (note: TURING's formal release gate is CI's, not yours).
- Build wheel+sdist; `twine check`; boundary scan (ships `mla1517*` surface);
  clean-venv install from findlinks; import sweep; copy to `/tmp/pythia-dist/`.

### T3. Baseline full matrix (background, big — start EARLY)
```bash
.venv/bin/python -m pytest -q --junitxml=artifacts/platform-lane/full-matrix.xml \
  tests/ 2>&1 | tee artifacts/platform-lane/full-matrix.log
```
Handoff says ~4867 tests collected on this suite. Report collected count,
pass/fail/error/skip counts, and the failing test list. Do NOT fix tests outside
your lane — classify each failure:
`NEW_REGRESSION | BASELINE_IDENTICAL | INFRASTRUCTURE | PLATFORM_UNSUPPORTED |
EVIDENCE_UNAVAILABLE` with one line of evidence each.
A zero-collect or runner-infra failure = `CI_UNAVAILABLE`, not pass/fail.

### T4. Gate scripts (application profile only — NOT live)
```bash
.venv/bin/python scripts/m5_transfer_preflight.py --execute \
  --output artifacts/platform-lane/m5-transfer-preflight.json
.venv/bin/python scripts/euclid_v17_integration_gate.py \
  --output artifacts/platform-lane/euclid-v17.json
.venv/bin/python scripts/m3_evidence_pack.py \
  --out artifacts/platform-lane/m3-evidence
.venv/bin/python scripts/production_preflight.py --profile application --strict \
  --output artifacts/platform-lane/app-preflight.json
```
- Inspect each exit code AND its JSON. A gate that can't run for missing
  env/secrets/hardware = report `BLOCKED(what's missing)` — do NOT fabricate
  env vars, tokens, or approvals.
- `production_preflight --profile live` is FORBIDDEN (needs real M3/pool creds).
- The `physical_gpu` gate is expected RED: OpenCL `unified_punch_kernel` fails to
  build on macOS → CPU fallback. Confirm the failure mode matches; do not attempt
  a Metal port (that's a separate QC_HOLD item the integrator is tracking).

### T5. Dep sanity for downstream lanes
`pip check` inside your worktree venv after installing requirements; note any
numpy/sympy conflicts (known issue: root `requirements-lock.txt` vs
chronos-one-igpu pins). Report exact conflicting specifiers — do not silently
upgrade pins.

## Hard rules
- Commit ONLY on `lane/platform-matrix` in YOUR worktree. Conventional commits.
  Never touch the shared checkout, `main`, or other lanes' files
  (root `pyproject.toml` is Agent 1's — hands off).
- `publishable` stays `false`; no twine upload, no push, no GitHub release.
- No live-submit, no pool credentials, no `HYBA_ENABLE_LIVE_SHARE_SUBMIT`,
  no `--submit`. Shadow/test evidence only.
- No claims: GPU execution, pool acceptance, self-healing labels without measured
  action. CPU evidence labelled CPU.
- No secrets in files/logs/commits.
- Never weaken a check, skip a mandatory test, or fabricate a result.
  Report blockers precisely.

## Deliverable (return to integrator)
`artifacts/platform-lane/EVIDENCE.md` + JSON containing:
- worktree SHA + lane branch + commits; `git status` clean/dirty
- per distribution: name, version, wheel+sdist paths, sha256, verdict JSON paths
- matrix: collected/passed/failed/skipped counts + classified failure list
- gate results: each script's exit code + verdict field + blocker details
- dep conflicts found
- explicit `LANE_STATUS: PASS | BLOCKED(<reason>)`
