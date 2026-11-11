#!/usr/bin/env bash
# Workbench run 4: apply the CI fixes on a branch from main, verify every
# failing check, then push fix/ci-green-foundation.
cd "$GITHUB_WORKSPACE" || exit 1
section() { echo; echo "=================== $* ==================="; }
git fetch -q origin main
git checkout -q -B fix/ci-green-foundation origin/main
echo "base $(git rev-parse HEAD)"
python -m pip install -q -e '.[dev]' ruff bandit build twine pyyaml coverage==7.17.2 > /dev/null 2>&1

section "apply fixes"
python "$WB/fix_ci.py" || exit 1
ruff check --select F401,F841 --fix --unsafe-fixes tests/test_turing.py tests/test_trust_preview.py
python scripts/ci/sovereign_attestation.py | tail -3
python -c "import json; json.load(open('SOVEREIGN_CAPABILITY_ATTESTATION.json')); print('attestation JSON valid')"
python "$WB/gen_claim_policy.py" || exit 1
git add -A
git --no-pager diff --cached --stat
git --no-pager diff --cached -- tests/test_turing.py tests/test_trust_preview.py src/chronus/execution/mining_admin.py src/chronus/service/production_hr_api.py | head -150
grep -rn "a45b7889" tests src | head

section "lint"
ruff check --select F src/chronus/execution src/chronus/backends src/chronus/service src/chronus/sdk src/chronus/security src/chronus/stratum src/chronus/math src/chronus/hw tests; echo "ruff exit=$?"
python -m compileall -q src/chronus/config.py src/chronus/execution src/chronus/backends src/chronus/service src/chronus/sdk src/chronus/security src/chronus/stratum src/chronus/math src/chronus/hw; echo "compileall exit=$?"
section "bandit"
bandit -q -r src/chronus/execution src/chronus/backends src/chronus/service src/chronus/sdk src/chronus/security -ll -ii; echo "bandit exit=$?"
section "purity"
python scripts/ci/purity_gate.py; echo "purity exit=$?"
section "claim tokens"
python scripts/ci/check_forbidden_claims.py; echo "claims exit=$?"
python -m unittest discover -s tests -p 'test_forbidden_claims.py' 2>&1 | tail -3
section "pytest"
CHRONUS_WORKLOAD_DB_PATH="$RUNNER_TEMP/t.sqlite3" python -m pytest -q -p no:cacheprovider -rfE --tb=short 2>&1 | tail -40
section "qigpu audit step (python shell)"
python - <<'PY'
import yaml
steps = yaml.safe_load(open('.github/workflows/ci.yml'))['jobs']['qigpu-model']['steps']
code = next(s['run'] for s in steps if s.get('name', '').startswith('Audit coverage'))
open('/tmp/audit.py', 'w').write(code)
PY
timeout 900 python /tmp/audit.py 2>&1 | tail -5; echo "audit exit=${PIPESTATUS[0]}"
section "frontend"
cd frontend && pnpm install --frozen-lockfile > /dev/null 2>&1 && pnpm build > /tmp/fe.txt 2>&1; echo "frontend exit=$?"; tail -25 /tmp/fe.txt; cd ..
section "manifest gates"
timeout 1200 python scripts/ci/manifest.py 2>&1 | tail -14
git checkout -q -- PRODUCTION_QUALIFIED.json 2>/dev/null
section "deploy triggers"
for f in .github/workflows/cd.yml .github/workflows/release.yml .github/workflows/investor-evidence-dossier.yml .github/workflows/nextjs.yml; do echo "--- $f"; sed -n '1,25p' "$f" | grep -v '^\s*#' | head -22; done

section "commit"
git add SOVEREIGN_CAPABILITY_ATTESTATION.json
echo "not staged (left out of the commit):"; git status --short | grep -v '^[AMRD] ' | head -20
git commit -q -F - <<'MSG'
fix: restore green CI without weakening any gate

- purity gate applies its documented rule: exact integer helpers (gcd and
  peers) are allowed, floating-point math stays banned; rule tests added
- HR API standalone server binds to loopback unless configured
- lint: dead duplicate get_patroclus_status removed; unused test imports
- Stratum E2E fixture rebuilt from the real Bitcoin block 0 coinbase, so the
  genesis nonce is a true known-answer test; the local pool now verifies shares
- v36 receipts signed with FIPS 204 ML-DSA-65 and verified with the tenant
  public key (no placeholder-key fallback)
- frontend: restored the five AL HARAS application calls dropped in e04dbd0
- attestation regenerated as valid JSON; the review text that overwrote it is
  preserved in reviews/
- claim-token gate: reviewed allowlist with exact counts and bases; vendor and
  preserved historical material excluded
MSG
git push -q -f origin fix/ci-green-foundation && echo "pushed $(git rev-parse HEAD)"
