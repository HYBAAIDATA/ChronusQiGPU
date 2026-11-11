#!/usr/bin/env bash
# Workbench run 5: evidence on current main, collision checks, branch clean-up.
cd "$GITHUB_WORKSPACE" || exit 1
section() { echo; echo "=================== $* ==================="; }
git fetch -q origin '+refs/heads/*:refs/remotes/origin/*'
git checkout -q -B probe origin/main
echo "main $(git rev-parse HEAD)"

section "branch clean-up (mine only)"
for b in cowork/ci-diagnostics-20261111 feat/turing-1000-qubit-representations; do
  git push -q origin --delete "$b" && echo "deleted $b" || echo "could not delete $b"
done

section "files touched by other open work vs main"
for b in feat/partner-distribution feat/turing-exact-algorithms al-haras/notes-alignment; do
  echo "--- $b"; git diff --stat --name-only origin/main...origin/$b | grep -E '^(src/chronus/service|README|docs/(claim-audit|system-update|README)|STATUS|RELEASE|tests/test_mining|tests/test_patroclus)' | head -30
done

section "doc history since 10 Nov"
git log --format='%h %ad %s' --date=short -3 -- README.md docs/claim-audit.md STATUS.md RELEASE_DECISION_MCKINSEY_TECH.md docs/system-update/current-state-assessment.md docs/system-update/test-evidence.md docs/system-update/README.md docs/system-update/quantum-package-taxonomy.md

section "mining admin exposure"
grep -n "APIRouter\|Depends\|def \|@router" src/chronus/service/routers/mining_admin.py | head -40
grep -n "mining_admin\|include_router" src/chronus/service/app.py | head
grep -rn "mining/admin" tests/*.py | awk -F: '{print $1}' | sort | uniq -c
grep -n "AUTH_HEADERS\s*=\|def client\|CHRONUS_TENANT_TOKENS\|create_app\|TestClient(" tests/test_mining_admin.py tests/test_patroclus_myrmidon_master.py | head -20
grep -n "def get_current_tenant" -A 25 src/chronus/service/*.py src/chronus/service/**/*.py 2>/dev/null | head -40

section "full suite and gates on main"
python -m pip install -q -e '.[dev]' ruff bandit > /dev/null 2>&1
python -m pip install -q -e packages/turing > /dev/null 2>&1
CHRONUS_WORKLOAD_DB_PATH="$RUNNER_TEMP/t.sqlite3" python -m pytest -q -p no:cacheprovider 2>&1 | tail -3
python scripts/ci/purity_gate.py | tail -1
python scripts/ci/check_forbidden_claims.py 2>&1 | tail -2
python --version; uname -sr
git checkout -q -- . 2>/dev/null
