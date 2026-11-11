#!/usr/bin/env bash
# Workbench run 6: read-only probe for the HYBA Mine gate and the docs refresh.
cd "$GITHUB_WORKSPACE" || exit 1
section() { echo; echo "=================== $* ==================="; }
git fetch -q origin main
git checkout -q -B probe origin/main
echo "main $(git rev-parse HEAD)"

section "test fixtures"
sed -n '1,45p' tests/test_mining_admin.py
echo '-----'
sed -n '55,80p' tests/test_patroclus_myrmidon_master.py

section "auth: token to tenant"
grep -n "def authenticate" -A 30 src/chronus/service/auth.py 2>/dev/null | head -45
grep -rn "CHRONUS_TENANT_TOKENS\|X-Tenant-ID\|x-tenant-id" src/chronus/service/*.py | head -12

section "mining router head"
sed -n '1,48p' src/chronus/service/routers/mining_admin.py

section "docs changed by #29"
git show --stat --format='%h %s' daa1a36 -- README.md docs AGENTS.md RELEASE_DECISION_MCKINSEY_TECH.md STATUS.md | tail -25

section "README.md (current)"
cat README.md

section "STATUS.md head"
sed -n '1,12p' STATUS.md

section "docs/system-update/README.md"
cat docs/system-update/README.md

section "claim policy entries for docs I may edit"
python - <<'PY'
import json
p = json.load(open('scripts/ci/claim_token_policy.json'))
for e in p['allowlist']:
    if e['path'].startswith(('docs/IGPU', 'docs/agents', 'README', 'STATUS', 'docs/claim', 'docs/system-update', 'RELEASE')):
        print(e)
PY
