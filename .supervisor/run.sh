#!/usr/bin/env bash
# Supervisor workbench run 1: inventory, branch/PR audit, symbol map,
# root-script references, BLOCKER patch status, and the test baseline on main.
set +e
cd "$GITHUB_WORKSPACE" || exit 1
git fetch -q origin '+refs/heads/*:refs/remotes/origin/*'
git fetch -q origin '+refs/pull/*/head:refs/remotes/pr/*'
git checkout -q -B probe origin/main
MAIN=$(git rev-parse HEAD)
echo "$MAIN" > "$OUT/main_sha.txt"
python "$SUP/inventory.py" "$OUT" > "$OUT/inventory_log.txt" 2>&1
echo "inventory exit=$?" >> "$OUT/inventory_log.txt"

# Branches and pull requests relative to main
{
for ref in $(git for-each-ref --format='%(refname:short)' refs/remotes/origin refs/remotes/pr | grep -v -E 'origin/HEAD$|^origin$'); do
  echo "================ $ref $(git rev-parse --short "$ref")"
  echo "-- ahead of main: $(git rev-list --count origin/main.."$ref")  behind main: $(git rev-list --count "$ref"..origin/main)"
  git log --format='%h %ad %an %s' --date=iso-strict origin/main.."$ref" | head -40
  echo "-- diff --stat (merge-base...ref)"
  git diff --stat=200 origin/main..."$ref" | tail -n 80
done
} > "$OUT/branches_and_prs.txt" 2>&1

# BLOCKER patches: are they applied on main?
{
for p in BLOCKER_MILLENIEIEUM_1.patch BLOCKER_MILLENIEIEUM_2.patch BLOCKER_TOE_1.patch; do
  echo "================ $p"
  git log --format='%h %ad %an %s' --date=iso-strict -- "$p" | head -5
  echo "-- files touched:"; grep -E '^(\+\+\+|---) ' "$p" | sort -u
  if git apply --check "$p" 2>/dev/null; then echo "STATUS: applies cleanly forward (NOT applied on main)";
  elif git apply -R --check "$p" 2>/dev/null; then echo "STATUS: reverse-applies cleanly (ALREADY applied on main)";
  else echo "STATUS: neither forward nor reverse applies cleanly (diverged)"; git apply --check -v "$p" 2>&1 | tail -n 15; fi
done
} > "$OUT/blocker_patches.txt" 2>&1

# Test baseline on main (README/STATUS evidence rule: commit, environment, command, result)
python -m pip install -q --upgrade pip > "$OUT/pip_install.txt" 2>&1
python -m pip install -q -e '.[dev]' >> "$OUT/pip_install.txt" 2>&1
echo "pip exit=$?" >> "$OUT/pip_install.txt"
{
  echo "commit: $MAIN"
  echo "date_utc: $(date -u +%FT%TZ)"
  echo "runner: $(uname -srm) / $(lsb_release -ds 2>/dev/null)"
  echo "python: $(python -c 'import sys;print(sys.version.replace(chr(10)," "))')"
  echo "command: python -m pytest -q"
} > "$OUT/test_env.txt"
python -m pip freeze > "$OUT/pip_freeze.txt" 2>&1
start=$(date -u +%s)
CHRONUS_WORKLOAD_DB_PATH="$RUNNER_TEMP/chronus-tests.sqlite3" timeout 2700 python -m pytest -q -p no:cacheprovider -rfE --tb=line --continue-on-collection-errors > "$OUT/pytest_main_full.txt" 2>&1
code=$?
echo "pytest exit=$code seconds=$(( $(date -u +%s) - start ))" >> "$OUT/pytest_main_full.txt"
grep -E '^(FAILED|ERROR) |^=+ .*(passed|failed|error)|pytest exit=' "$OUT/pytest_main_full.txt" | tail -n 300 > "$OUT/pytest_main_summary.txt"
tail -n 3 "$OUT/pytest_main_full.txt" >> "$OUT/test_env.txt"

# packages/turing has its own project: run its tests in isolation too
if [ -f packages/turing/pyproject.toml ]; then
  python -m venv "$RUNNER_TEMP/tv" && . "$RUNNER_TEMP/tv/bin/activate"
  python -m pip install -q pytest > /dev/null 2>&1
  python -m pip install -q -e packages/turing > "$OUT/pytest_packages_turing.txt" 2>&1
  (cd packages/turing && timeout 900 python -m pytest -q -p no:cacheprovider -rfE --tb=line) >> "$OUT/pytest_packages_turing.txt" 2>&1
  echo "pytest exit=$?" >> "$OUT/pytest_packages_turing.txt"
  deactivate
fi
