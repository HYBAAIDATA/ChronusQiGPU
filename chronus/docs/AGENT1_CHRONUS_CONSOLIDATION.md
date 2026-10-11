# Devin Agent Lane — CHRONUS consolidation (Agent 1)

You are one of four agents building/qualifying HYBA distributions for first publication.
Your lane: **CHRONUS three-plane consolidation + umbrella surgery + dep rename/re-version**.
The integrator merges lane branches, freezes the RC, and dispatches release workflows.

## Ground truth (do not re-derive)

- Repo checkout: `/Users/demouser/Desktop/PhiEnterprise` (remote
  `https://github.com/PhiEnterprise/PhiEnterprise.git` — **fetch/push BLOCKED, no
  credentials. The old PAT was pasted in chat and is treated as compromised. NEVER push.**)
- Branch `main` @ `e7e17560bb4983a1c84c3d3a5f9e1da3b238ca16`, clean tree.
- macOS arm64, CLT installed. System `python3` is 3.9 — **never use it**.
  Use `~/.local/bin/uv`; CPython 3.12.15 is already installed (`uv python list`).
- Shared dep-wheel exchange: **`/tmp/pythia-dist/`** — copy every wheel+sdist you build
  there; check there FIRST before building any in-tree dependency yourself.
  `hyba_kellogg_tensor-1.0.0` is already present (also in `packaging/kellogg-tensor/dist/`).
- First read `packaging/HYBA_PUBLICATION_CATALOG.md` and
  `packaging/chronus-igpu/pyproject.toml` header comments — they encode the approved split.

## Setup

```bash
export PATH="$HOME/.local/bin:$PATH"
cd /Users/demouser/Desktop/PhiEnterprise
git worktree add ../PhiEnterprise-chronus -b lane/chronus-consolidation
cd ../PhiEnterprise-chronus
uv venv --seed --python 3.12 .venv
.venv/bin/python -m pip install -q build wheel twine pytest
mkdir -p /tmp/pythia-dist artifacts/chronus-lane
```

## Owner-delegated decisions (already made — implement, do not re-ask)

1. **First-public version is `1.0.0` for every distribution.** Dev versions
   (3.3.0, 3.11.3rc2, 0.1.0, 0.3.0) were never publicly published; no compat break.
2. **CHRONOS ONE public name is `hyba-chronos-one-igpu`**
   (per `packaging/publication_catalog.json`); legacy name `chronos-one-igpu` retires.
   Import namespace `chronos_one_igpu` stays unchanged.
3. **Three-plane `chronus` boundary** (already encoded in
   `packaging/chronus-igpu/pyproject.toml` comments — it IS the owner-approved split):
   - `chronus/__init__.py` facade + `chronus/v33/` → `hyba-chronos-mathematics`
   - rest of `chronus/` (virtual_igpu, measurement, seam, resident_hendrix, h4_600,
     exact_geometry, one_igpu_mining, readiness, detect, fabric, ...) + `lucas/` →
     `hyba-chronus-igpu`
   - `chronus/mla1517/` → `hyba-pythia-mining` (umbrella)
   - `chronus/mla1517_platform/` → `hyba-pythia-mining-runtime` (another lane owns it)
   **Do NOT delete source folders.** The old "v33/virtual_igpu dedupe" note is
   superseded — consolidation here means the distribution boundary, not source removal.

## Tasks (in order)

### T1. `hyba-chronos-mathematics` → 1.0.0
- `packaging/chronos-core/pyproject.toml`: version `3.3.0` → `1.0.0`.
- Run `.venv/bin/python packaging/chronos-core/build_and_verify.py`; require `VERIFIED`.
- Copy `packaging/chronos-core/dist/*` to `/tmp/pythia-dist/`.

### T2. `hyba-chronos-one-igpu` rename + 1.0.0
- `packages/chronos-one-igpu/pyproject.toml` (and `setup.py` if it pins name/version):
  name → `hyba-chronos-one-igpu`, version `3.11.3rc2` → `1.0.0`.
- Keep `chronos_one_igpu` import package unchanged.
- Build: `.venv/bin/python -m build packages/chronos-one-igpu`; `twine check` both
  artifacts; copy `packages/chronos-one-igpu/dist/*` to `/tmp/pythia-dist/`.
- Record the old→new name mapping in your evidence packet.

### T3. `hyba-chronus-igpu` pins + verification
- `packaging/chronus-igpu/pyproject.toml`:
  `hyba-chronos-mathematics>=3.3.0` → `>=1.0`; `chronos-one-igpu>=3.11.3rc2` →
  `hyba-chronos-one-igpu>=1.0`.
- `packaging/chronus-igpu/build_and_verify.py`: update `_dep_wheels` key/glob
  (`chronos_one_igpu` → `hyba_chronos_one_igpu`) and the `INSTALLED_CHECK`
  reqs assertion (`chronos-one-igpu` → `hyba-chronos-one-igpu`).
- Run `.venv/bin/python packaging/chronus-igpu/build_and_verify.py`; require `VERIFIED`.
- Copy `packaging/chronus-igpu/dist/*` to `/tmp/pythia-dist/`.

### T4. Umbrella surgery — root `pyproject.toml` (`hyba-pythia-mining`)
- version `0.1.0` → `1.0.0`.
- Package selection: **drop** `lucas*` and all `chronus.*` **except**
  `chronus.mla1517*`; do NOT ship `chronus/__init__.py` (facade belongs to
  `hyba-chronos-mathematics`; umbrella relies on it as a dep).
- dependencies: `chronos-one-igpu>=3.11.3rc2` → `hyba-chronos-one-igpu>=1.0`;
  **add** `hyba-chronus-igpu>=1.0` and `hyba-chronos-mathematics>=1.0`.
- Build the umbrella wheel+sdist, `twine check`, copy to `/tmp/pythia-dist/`.

### T5. Cross-repo pin sweep
`grep -rn "chronos-one-igpu\|chronos-mathematics\|chronus-igpu" --include="*.toml" --include="*.txt" --include="*.cfg" --include="*.yml" --include="*.yaml" .`
- Update pins inside your lane's file set and shared build files
  (`requirements*.txt`, `config/`).
- For pins inside OTHER lanes' manifests (`packaging/theseus|ovid|toe|euclid-engine|salamander`,
  `chronus/mla1517_platform`), DO NOT edit — list them in your evidence packet.

### T6. Co-installation proof (the critical gate)
Clean venv in /tmp; install ALL wheels from `/tmp/pythia-dist`
(`--find-links /tmp/pythia-dist`), then `pip check`. From OUTSIDE any checkout, `python -I`:
- `import chronus` resolves via the `hyba-chronos-mathematics` facade
- `chronus.v33`, `chronus.virtual_igpu`, `chronus.mla1517`, `lucas` each import and
  each module's `__file__` sits under the EXPECTED wheel's site-packages
- RECORD ownership: no two dists own the same path (script it; collisions must be 0)
- Umbrella-bound modules fail closed with ModuleNotFoundError where deps absent.

### T7. Focused tests (in your worktree)
```bash
.venv/bin/python -m pytest -q --junitxml=artifacts/chronus-lane/tests.xml \
  tests/test_exact_geometry.py tests/test_resident_hendrix.py \
  tests/test_chronus_h4_600_mining.py tests/test_golden_stride.py \
  tests/test_c_poincare_golden_11d.py tests/test_a_lucas_math.py \
  tests/test_canonical_mining_search_doctrine.py
.venv/bin/python scripts/check_canonical_mining_search.py || true
```
Zero collected tests = failure. Do not modify tests to pass.

## Hard rules
- Commit ONLY on `lane/chronus-consolidation` in YOUR worktree. Conventional commits.
  Never touch the shared checkout, `main`, or other lanes' files.
- `publishable` stays `false`; no twine upload, no push, no GitHub release.
- No claims of GPU execution, pool acceptance, or QPU. CPU evidence labelled CPU.
- No secrets in files/logs/commits (grep for `ghp_`, `pypi-`, `PRIVATE KEY` before commit).
- If a gate fails: fix the real defect in your lane or report `BLOCKED` with evidence.
  Never weaken a check, skip a mandatory test, or fabricate a result.

## Deliverable (return to integrator)
`artifacts/chronus-lane/EVIDENCE.md` + JSON containing:
- worktree SHA + lane branch + commits; `git status` clean/dirty
- per distribution: name, version, wheel+sdist paths, sha256, verdict JSON paths
- co-install proof: pip check output, per-module owner-wheel map, RECORD collisions (must be 0)
- test counts (collected/passed/failed), failing test names
- cross-lane pins needing integrator edits
- the exact rename map applied (chronos-one-igpu → hyba-chronos-one-igpu)
- explicit `LANE_STATUS: PASS | BLOCKED(<reason>)`
