#!/usr/bin/env bash
# Workbench run 1: read-only investigation of the failing checks on main.
cd "$GITHUB_WORKSPACE" || exit 1
git fetch -q origin main
git checkout -q -B probe origin/main
echo "HEAD $(git rev-parse HEAD)"

section() { echo; echo "=================== $* ==================="; }

section "purity_gate.py"
cat scripts/ci/purity_gate.py

section "elevation.py 40-70"
sed -n '40,70p' src/chronus/execution/elevation.py

section "production_hr_api.py 205-225"
sed -n '205,225p' src/chronus/service/production_hr_api.py

section "test_behavioral_sovereign_attestation.py"
cat tests/test_behavioral_sovereign_attestation.py

section "SOVEREIGN_CAPABILITY_ATTESTATION.json head"
head -c 1500 SOVEREIGN_CAPABILITY_ATTESTATION.json

section "v36 I3 context"
grep -n "I3" src/chronus/chronus_gpiu-v36.py | head -20
sed -n '5985,6012p' src/chronus/chronus_gpiu-v36.py

section "master_e2e_engine.py 430-480"
sed -n '430,480p' src/chronus/execution/master_e2e_engine.py

python -m pip install -q -e '.[dev]' > /dev/null 2>&1
section "pytest gatekeeper + simulate (long tb)"
python -m pytest -q -p no:cacheprovider --tb=long -x tests/test_master_e2e_orchestrators.py 2>&1 | tail -60
python -m pytest -q -p no:cacheprovider --tb=long "tests/test_patroclus_myrmidon_master.py::TestIntegrationAndE2E::test_api_patroclus_simulate_endpoint" 2>&1 | grep -vE '^\s*$' | tail -60

section "claim token scan"
python scripts/ci/check_forbidden_claims.py 2>&1 | sed 's/: prohibited token/ ::/' | awk -F' :: ' '{print $2" "$1}' | sort | head -400
python scripts/ci/check_forbidden_claims.py 2>&1 | wc -l
python -m unittest discover -s tests -p 'test_forbidden_claims.py' 2>&1 | tail -5

section "frontend type errors (all)"
cd frontend && pnpm install --frozen-lockfile > /dev/null 2>&1
pnpm exec tsc --noEmit -p . 2>&1 | head -80
grep -n "static async\|static [a-zA-Z]*(" lib/api-client.ts | head -60
sed -n '100,140p' app/governance/page.tsx
cd ..

section "wc"
wc -l src/chronus/execution/mining_admin.py src/chronus/service/routers/mining_admin.py frontend/app/governance/page.tsx frontend/lib/api-client.ts tests/test_mining_admin.py tests/test_patroclus_myrmidon_master.py src/chronus/execution/master_e2e_engine.py
