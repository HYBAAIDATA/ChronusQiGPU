#!/usr/bin/env bash
# Supervisor workbench run 3: merged-branch clean-up (PR #28 only), evidence on
# main, and the TURING/packaging consolidation branch with full verification.
set +e
cd "$GITHUB_WORKSPACE" || exit 1
git fetch -q origin '+refs/heads/*:refs/remotes/origin/*'
BR=chore/turing-packaging-consolidation-20261111
GIT_BOT=(-c user.name="github-actions[bot]" -c user.email="41898282+github-actions[bot]@users.noreply.github.com")

# 1. Delete only the branch of the merged PR #28 (owner rule), if fully in main.
{
b=fix/ci-green-foundation
if git rev-parse -q --verify "origin/$b" >/dev/null; then
  if git merge-base --is-ancestor "origin/$b" origin/main; then
    git push -q origin --delete "$b" && echo "deleted (merged via PR #28): $b"
  else echo "kept (not fully in main): $b"; fi
else echo "absent: $b"; fi
echo "other branches untouched by design"
} > "$OUT/branch_cleanup.txt" 2>&1

# 2. Evidence on main after PR #28.
git checkout -q -B main-evidence origin/main
MAIN=$(git rev-parse HEAD)
python -m venv "$RUNNER_TEMP/vmain" && . "$RUNNER_TEMP/vmain/bin/activate"
python -m pip install -q --upgrade pip > /dev/null 2>&1
python -m pip install -q -e '.[dev]' > "$OUT/main_install.txt" 2>&1; echo "install exit=$?" >> "$OUT/main_install.txt"
{ echo "commit: $MAIN"; echo "date_utc: $(date -u +%FT%TZ)"; echo "runner: $(uname -srm) / $(lsb_release -ds 2>/dev/null)"; echo "python: $(python -V 2>&1)"; echo "command: python -m pytest -q"; } > "$OUT/main_evidence.txt"
CHRONUS_WORKLOAD_DB_PATH="$RUNNER_TEMP/m.sqlite3" timeout 1800 python -m pytest -q -p no:cacheprovider -rfE --tb=line > "$OUT/main_pytest.txt" 2>&1
echo "pytest exit=$?" >> "$OUT/main_pytest.txt"
tail -n 3 "$OUT/main_pytest.txt" >> "$OUT/main_evidence.txt"
python -m pip freeze > "$OUT/main_freeze.txt" 2>&1
deactivate
git checkout -q -- . ; git clean -fdq

# 3. Consolidation branch.
git checkout -q -B "$BR" origin/main
python "$SUP/migrate.py" > "$OUT/migrate_log.txt" 2>&1
MIG=$?
echo "migrate exit=$MIG" >> "$OUT/migrate_log.txt"
if [ "$MIG" -ne 0 ]; then echo "migration failed; nothing committed or pushed" >> "$OUT/migrate_log.txt"; exit 0; fi
git add -A
git "${GIT_BOT[@]}" commit -q -m "chore: one TURING package and internal distribution metadata" \
  -m "Supervisor consolidation, 11 Nov 2026 (TURING and packaging scope). Moves src/turing into packages/turing as turing.exact so only one top-level turing package exists; archives root diagnostic outputs, the TURING source snapshots and the root API wrappers unchanged; adds chronus.hermes, chronus.ovid, chronus.theseus, chronus.geodesic and chronus.igpu (with chronus.igpu.tensor) as re-export namespaces; renames the distribution hyba-chronus 37.0.0.dev0 with the Private :: Do Not Upload classifier and bundles TURING; raises the cryptography floor to 47.0 for ML-DSA; adds repository-layout tests and a temporary-workflow merge gate script. Nothing is deleted."
HEADSHA=$(git rev-parse HEAD)
git show --stat --format='%H%n%s' HEAD > "$OUT/migrate_commit.txt"
git push -q -f origin "$BR" && echo "pushed $BR $HEADSHA" > "$OUT/push.txt" || echo "push failed" > "$OUT/push.txt"

# 4. Verification of the branch.
python -m venv "$RUNNER_TEMP/vbr" && . "$RUNNER_TEMP/vbr/bin/activate"
python -m pip install -q --upgrade pip > /dev/null 2>&1
python -m pip install -q -e '.[dev]' ruff build twine > "$OUT/v_install.txt" 2>&1; echo "install exit=$?" >> "$OUT/v_install.txt"
{ echo "commit: $HEADSHA"; echo "date_utc: $(date -u +%FT%TZ)"; echo "runner: $(uname -srm) / $(lsb_release -ds 2>/dev/null)"; echo "python: $(python -V 2>&1)"; echo "command: python -m pytest -q"; } > "$OUT/v_evidence.txt"
CHRONUS_WORKLOAD_DB_PATH="$RUNNER_TEMP/b.sqlite3" timeout 1800 python -m pytest -q -p no:cacheprovider -rfE --tb=short > "$OUT/v_pytest.txt" 2>&1
echo "pytest exit=$?" >> "$OUT/v_pytest.txt"
tail -n 3 "$OUT/v_pytest.txt" >> "$OUT/v_evidence.txt"
{
  ruff check --select F src/chronus/execution src/chronus/backends src/chronus/service src/chronus/sdk src/chronus/security src/chronus/stratum src/chronus/math src/chronus/hw tests; echo "ruff (CI scope) exit=$?"
  ruff check --select F src/chronus/hermes src/chronus/ovid src/chronus/theseus src/chronus/geodesic src/chronus/igpu packages/turing/src; echo "ruff (new paths) exit=$?"
  python -m compileall -q src/chronus packages/turing/src; echo "compileall exit=$?"
  python scripts/ci/check_no_temporary_workflows.py; echo "temporary-workflow gate exit=$?"
} > "$OUT/v_lint.txt" 2>&1
{ for s in purity_gate.py test_the_tests.py sovereign_attestation.py manifest.py; do echo "== $s"; timeout 900 python "scripts/ci/$s" > "$RUNNER_TEMP/step.txt" 2>&1; c=$?; tail -n 40 "$RUNNER_TEMP/step.txt"; echo "$s exit=$c"; done; } > "$OUT/v_purity.txt" 2>&1
{ python -m unittest discover -s tests -p 'test_forbidden_claims.py' -v; echo "claims unittest exit=$?"; python scripts/ci/check_forbidden_claims.py; echo "claims scan exit=$?"; } > "$OUT/v_claims.txt" 2>&1
{
  rm -rf dist
  python -m build > "$RUNNER_TEMP/b1.txt" 2>&1; echo "build hyba-chronus exit=$?"; tail -n 4 "$RUNNER_TEMP/b1.txt"
  python -m build packages/turing --outdir dist/turing > "$RUNNER_TEMP/b2.txt" 2>&1; echo "build hyba-turing exit=$?"; tail -n 4 "$RUNNER_TEMP/b2.txt"
  python -m twine check dist/*.whl dist/*.tar.gz dist/turing/*; echo "twine exit=$?"
  python - <<'PY'
import glob, zipfile
for whl in sorted(glob.glob("dist/*.whl") + glob.glob("dist/turing/*.whl")):
    names = zipfile.ZipFile(whl).namelist()
    tops = sorted({n.split("/")[0] for n in names if not n.endswith(".dist-info/") })
    print(whl, "files:", len(names), "top-level:", [t for t in tops if not t.endswith(".dist-info")])
    print("   turing/exact:", sum(n.startswith("turing/exact/") for n in names), "files; chronus/:", sum(n.startswith("chronus/") for n in names))
    meta = [n for n in names if n.endswith("METADATA")]
    if meta:
        text = zipfile.ZipFile(whl).read(meta[0]).decode()
        print("   ", [l for l in text.splitlines() if l.startswith(("Name:", "Version:", "Classifier: Private"))])
PY
} > "$OUT/v_build.txt" 2>&1
{ PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/acceleration/test_fourier.py --cov=chronus.acceleration.fourier --cov-branch --cov-fail-under=90; echo "fourier exit=$?"; PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/acceleration/test_state.py --cov=chronus.acceleration.state --cov-branch --cov-fail-under=90; echo "state exit=$?"; } > "$OUT/v_acceleration.txt" 2>&1
{ python -m unittest discover -s tests -p 'test_capacity_harness.py'; echo "harness exit=$?"; python -m unittest discover -s tests -p 'test_capacity_artifact_verifier.py'; echo "verifier exit=$?"; python -m unittest discover -s tests -p 'test_trust_preview.py'; echo "trust exit=$?"; python scripts/ci/verify_capacity_artifacts.py; echo "artifacts exit=$?"; } > "$OUT/v_storage.txt" 2>&1
{ grep -n -E "float|complex|TOLERANCE|cmath|numpy|math\." src/chronus/acceleration/*.py | head -40
  python - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, "scripts/ci")
try:
    import purity_gate as g
except SystemExit:
    print("purity_gate exits on import; survey skipped")
    raise SystemExit(0)
for root in ["packages/turing/src/turing/exact", "packages/turing/src/turing", "src/chronus/acceleration", "src/chronus/tensor"]:
    found = []
    for p in sorted(Path(root).rglob("*.py")):
        found += g.scan_file(p)
    print(root, "purity findings:", len(found))
    print("\n".join(found[:12]))
PY
} > "$OUT/v_purity_survey.txt" 2>&1
deactivate

# 5. TURING distribution on its own (isolated install, its own pytest config).
python -m venv "$RUNNER_TEMP/vt" && . "$RUNNER_TEMP/vt/bin/activate"
python -m pip install -q ./packages/turing 'pytest>=8' > "$OUT/v_turing_pkg.txt" 2>&1; echo "install exit=$?" >> "$OUT/v_turing_pkg.txt"
(cd packages/turing && timeout 900 python -m pytest -q -p no:cacheprovider -rfE --tb=short) >> "$OUT/v_turing_pkg.txt" 2>&1
echo "turing pytest exit=$?" >> "$OUT/v_turing_pkg.txt"
(cd "$RUNNER_TEMP" && python -c "import turing, turing.exact; print(turing.__file__); print(turing.exact.__file__, turing.__version__)") >> "$OUT/v_turing_pkg.txt" 2>&1
deactivate

git status --porcelain > "$OUT/v_status_after.txt"
git checkout -q -- . ; git clean -fdq
