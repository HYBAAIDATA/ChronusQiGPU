#!/usr/bin/env bash
# Supervisor workbench run 4: fixes found by run 3 on the consolidation branch
# (a non-compiling fragment shipped in the wheel, TURING shipped by two
# wheels, two unused imports), the TURING specification and wheel check, full
# verification, and push targets for the sub-agent branches.
set +e
cd "$GITHUB_WORKSPACE" || exit 1
git fetch -q origin '+refs/heads/*:refs/remotes/origin/*'
BR=chore/turing-packaging-consolidation-20261111
GIT_BOT=(-c user.name="github-actions[bot]" -c user.email="41898282+github-actions[bot]@users.noreply.github.com")

# 1. Push targets for sub-agent work, created from main only when absent.
{
for b in feat/turing-exact-algorithms feat/partner-distribution; do
  if git rev-parse -q --verify "origin/$b" >/dev/null; then echo "exists: $b $(git rev-parse "origin/$b")"
  else git push -q origin "$(git rev-parse origin/main):refs/heads/$b" && echo "created from main: $b $(git rev-parse origin/main)"; fi
done
} > "$OUT/branches.txt" 2>&1

# 2. Fixes on the consolidation branch.
git checkout -q -B "$BR" "origin/$BR"
sha256sum "$SUP/SPECIFICATION.md" > "$OUT/spec_sha.txt" 2>&1
python "$SUP/fix4.py" "$SUP" > "$OUT/fix_log.txt" 2>&1
FIX=$?
echo "fix exit=$FIX" >> "$OUT/fix_log.txt"
if [ "$FIX" -ne 0 ]; then echo "fixes failed; nothing pushed" >> "$OUT/fix_log.txt"; exit 0; fi
git add -A
git "${GIT_BOT[@]}" commit -q -m "chore: ship only code that compiles, and TURING in one distribution" \
  -m "Run 3 verification of this branch found four defects, fixed here. src/chronus/core/trust_ledger.py (added in e04dbd0) cannot compile and nothing imports it, so it moves unchanged to archive/fragments with a README explaining how to restore it. hyba-chronus no longer bundles TURING, which ships only as hyba-turing: both wheels carried turing/, so installing both would overwrite files. The Dockerfile stops copying TURING, which the API does not import. Two unused imports are removed. Adds the TURING suite specification (packages/turing/docs/SPECIFICATION.md), scripts/ci/check_wheels.py (private classifier, disjoint top-level packages, every shipped module compiles, no working files) and two layout tests."
HEADSHA=$(git rev-parse HEAD)
git show --stat --format='%H%n%s' HEAD > "$OUT/fix_commit.txt"
git push -q origin "HEAD:$BR" && echo "pushed $BR $HEADSHA" > "$OUT/push.txt" || echo "push failed" > "$OUT/push.txt"

# 3. Verification of the branch head.
python -m venv "$RUNNER_TEMP/vbr" && . "$RUNNER_TEMP/vbr/bin/activate"
python -m pip install -q --upgrade pip > /dev/null 2>&1
python -m pip install -q -e '.[dev]' ruff build twine > "$OUT/v_install.txt" 2>&1; echo "install exit=$?" >> "$OUT/v_install.txt"
{ echo "commit: $HEADSHA"; echo "date_utc: $(date -u +%FT%TZ)"; echo "runner: $(uname -srm) / $(lsb_release -ds 2>/dev/null)"; echo "python: $(python -V 2>&1)"; echo "command: python -m pytest -q"; } > "$OUT/v_evidence.txt"
CHRONUS_WORKLOAD_DB_PATH="$RUNNER_TEMP/b.sqlite3" timeout 1800 python -m pytest -q -p no:cacheprovider -rfE --tb=short > "$OUT/v_pytest.txt" 2>&1
echo "pytest exit=$?" >> "$OUT/v_pytest.txt"
tail -n 3 "$OUT/v_pytest.txt" >> "$OUT/v_evidence.txt"
{
  ruff check --select F src/chronus/execution src/chronus/backends src/chronus/service src/chronus/sdk src/chronus/security src/chronus/stratum src/chronus/math src/chronus/hw tests; echo "ruff (CI scope) exit=$?"
  ruff check --select F src/chronus/hermes src/chronus/ovid src/chronus/theseus src/chronus/geodesic src/chronus/igpu packages/turing/src scripts/ci/check_wheels.py scripts/ci/check_no_temporary_workflows.py; echo "ruff (new paths) exit=$?"
  python -m compileall -q src/chronus packages/turing/src; echo "compileall exit=$?"
  python scripts/ci/check_no_temporary_workflows.py; echo "temporary-workflow gate exit=$?"
} > "$OUT/v_lint.txt" 2>&1
{ python -m unittest discover -s tests -p 'test_forbidden_claims.py'; echo "claims unittest exit=$?"; python scripts/ci/check_forbidden_claims.py; echo "claims scan exit=$?"; } > "$OUT/v_claims.txt" 2>&1
{
  rm -rf dist
  python -m build --outdir dist/chronus . > "$RUNNER_TEMP/b1.txt" 2>&1; echo "build hyba-chronus exit=$?"; tail -n 2 "$RUNNER_TEMP/b1.txt"
  python -m build --outdir dist/turing packages/turing > "$RUNNER_TEMP/b2.txt" 2>&1; echo "build hyba-turing exit=$?"; tail -n 2 "$RUNNER_TEMP/b2.txt"
  python -m twine check dist/chronus/* dist/turing/*; echo "twine exit=$?"
  python scripts/ci/check_wheels.py dist/chronus dist/turing; echo "wheel check exit=$?"
} > "$OUT/v_build.txt" 2>&1
{ for s in purity_gate.py test_the_tests.py; do echo "== $s"; timeout 900 python "scripts/ci/$s" > "$RUNNER_TEMP/step.txt" 2>&1; c=$?; tail -n 6 "$RUNNER_TEMP/step.txt"; echo "$s exit=$c"; done
  echo "== tracked files changed by the gates"; git status --porcelain; echo "== diff stat"; git diff --stat; echo "== whitespace-insensitive diff of src"; git diff --ignore-all-space --ignore-cr-at-eol --stat -- src; git diff --ignore-all-space --ignore-cr-at-eol -- src | head -80
} > "$OUT/v_purity.txt" 2>&1
git checkout -q -- . ; git clean -fdq -e dist
deactivate

# 4. TURING distribution alone: installed wheel, tests copied out of the tree.
python -m venv "$RUNNER_TEMP/vt" && . "$RUNNER_TEMP/vt/bin/activate"
python -m pip install -q dist/turing/*.whl 'pytest>=8' > "$OUT/v_turing_pkg.txt" 2>&1; echo "install exit=$?" >> "$OUT/v_turing_pkg.txt"
W="$RUNNER_TEMP/turing-isolated"; mkdir -p "$W"; cp -r packages/turing/tests "$W/tests"; cp tests/test_turing.py "$W/tests/test_exact_layer.py"
(cd "$W" && timeout 900 python -m pytest -q -p no:cacheprovider -rfE --tb=short tests) >> "$OUT/v_turing_pkg.txt" 2>&1
echo "turing pytest exit=$?" >> "$OUT/v_turing_pkg.txt"
(cd "$W" && python -c "import sys, turing, turing.exact; print(turing.__file__, turing.__version__); print('chronus imported:', 'chronus' in sys.modules)") >> "$OUT/v_turing_pkg.txt" 2>&1
deactivate

git status --porcelain > "$OUT/v_status_after.txt"
git checkout -q -- . ; git clean -fdq
