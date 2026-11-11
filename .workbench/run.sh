#!/usr/bin/env bash
# Workbench run 3: context for the fixes.
cd "$GITHUB_WORKSPACE" || exit 1
git fetch -q origin main
git checkout -q -B probe origin/main
echo "HEAD $(git rev-parse HEAD)"
section() { echo; echo "=================== $* ==================="; }
V=src/chronus/chronus_gpiu-v36.py

section "v36 signing helpers"
grep -n "def sign_ed25519\|def verify_ed25519" -A 16 $V | head -50
sed -n '2306,2328p' $V
sed -n '3088,3097p' $V
grep -n "class ExactRing" -A 14 $V | head -20
git log --format='%h %ad %s' --date=short -4 -- $V
c=$(git log -G'ed25519' --format=%h -1 -- $V); echo "last ed25519 change: $c"; git show $c -- $V | grep -n "^[-+].*ed25519" | head -20

section "master_e2e helpers + mock server"
sed -n '42,115p' src/chronus/execution/master_e2e_engine.py
sed -n '252,362p' src/chronus/execution/master_e2e_engine.py
c=$(git log --format=%h -1 -- src/chronus/execution/master_e2e_engine.py); echo "last change $c"; git show $c -- src/chronus/execution/master_e2e_engine.py | grep -n "^[-+]" | head -80

section "governance methods in 0d564c4"
git show 0d564c4:frontend/lib/api-client.ts | grep -n -A7 "executeAgenticSheafTurn\|transmitOrbitalTelemetry\|executeZkNeuralProveAndVerify\|processCBDCCrossBorderSettlement\|executeTISAMicrocode" | head -70
grep -n "APIRouter(\|prefix=" src/chronus/service/routers/al_haras.py | head -5
grep -rn "include_router" src/chronus/service/*.py | head -30

section "lastMinedBlock history"
git log -S'lastMinedBlock' --format='%h %ad %s' --date=short -- frontend/app/mining/page.tsx
for c in $(git log -S'lastMinedBlock' --format=%h -- frontend/app/mining/page.tsx); do echo "== $c"; git show $c:frontend/app/mining/page.tsx | grep -n "lastMinedBlock\|LastMinedBlock" | head -6; done
grep -n "useState" frontend/app/mining/page.tsx | head -30

section "token contexts (remaining)"
for f in frontend/app/mining/page.tsx exact_primitive_library-v3.py qigpu_acceleration_system.py docs/IGPU_MANIFESTO.md; do echo "--- $f"; grep -n -i -o -E ".{0,60}(infinite|exponential|unlimited|100x).{0,40}" "$f" | head -5; done
for f in artifacts/qigpu/manifest_*.json; do echo "--- $f $(grep -o -i 'exponential' $f | wc -l)"; done

section "lint lines"
sed -n '585,592p;612,620p' tests/test_turing.py
sed -n '1,8p' tests/test_trust_preview.py
sed -n '90,100p;205,216p' src/chronus/execution/mining_admin.py

section "ci.yml qigpu audit step"
grep -n "Audit coverage by public function" -A 3 .github/workflows/ci.yml
