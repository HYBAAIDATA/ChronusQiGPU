#!/usr/bin/env bash
# Workbench run 2: root causes for the remaining failures.
cd "$GITHUB_WORKSPACE" || exit 1
git fetch -q origin main
git checkout -q -B probe origin/main
echo "HEAD $(git rev-parse HEAD)"
section() { echo; echo "=================== $* ==================="; }
python -m pip install -q -e '.[dev]' > /dev/null 2>&1

section "v36 MLDSASigner"
grep -n "class MLDSASigner" -A 45 src/chronus/chronus_gpiu-v36.py | head -70
grep -n "receipt_sig" src/chronus/chronus_gpiu-v36.py | head -12

section "sovereign_attestation.py (structure)"
grep -n "def \|STANDARD\|standard\|QUALIFIED\|DIFC\|Five Eyes\|ATTESTATION_SECRET_KEY\|json.dump\|OUTPUT\|open(" scripts/ci/sovereign_attestation.py | head -60

section "manifest.py (structure)"
grep -n "SECRET\|QUALIFIED\|def \|status\|open(\|run_cmd\|Gate" scripts/ci/manifest.py | head -50

section "gatekeeper"
grep -rn "def pre_submit_gatekeeper" -A 22 src/chronus | head -30
grep -rn "def check_share_difficulty_exact" -A 22 src/chronus | head -30
grep -n "set_difficulty\|difficulty" src/chronus/execution/master_e2e_engine.py | head -20
grep -n "def \|class " src/chronus/execution/master_e2e_engine.py | head -40
git log --format='%h %ad %s' --date=short -6 -- src/chronus/execution/master_e2e_engine.py src/chronus/stratum src/chronus/execution/gateway.py

section "simulate traceback"
python - <<'PY'
import traceback, inspect, asyncio
try:
    from chronus.execution.mining_admin import MiningAdminEngine
    e = MiningAdminEngine.get_instance()
    fn = getattr(e, 'simulate_patroclus_session', None)
    print('fn', fn)
    r = fn() if fn else None
    if inspect.iscoroutine(r):
        r = asyncio.run(r)
    print(str(r)[:400])
except Exception:
    traceback.print_exc()
PY
grep -n "simulate" -A 25 src/chronus/service/routers/mining_admin.py | head -45

section "mining page lastMinedBlock"
grep -n "lastMinedBlock\|setLastMined\|LastMined" frontend/app/mining/page.tsx | head
sed -n '990,1002p' frontend/app/mining/page.tsx

section "backend for governance applications"
grep -rln -i "agentic\|orbital\|cbdc\|tisa\|zk_neural" src/chronus --include=*.py | head -20
grep -rn -i "@router\.\(get\|post\).*\(agentic\|orbital\|cbdc\|tisa\|zk\|sheaf\|frontier\|application\)" src/chronus/service | head -20
for c in $(git log --format=%h -12 -- frontend/lib/api-client.ts); do echo "$c $(git log -1 --format='%ad %s' --date=short $c) methods=$(git show $c:frontend/lib/api-client.ts | grep -c 'executeAgenticSheafTurn\|processCBDCCrossBorderSettlement')"; done
for c in $(git log --format=%h -12 -- frontend/app/governance/page.tsx); do echo "gov $c $(git log -1 --format='%ad %s' --date=short $c)"; done

section "api-client.ts"
cat frontend/lib/api-client.ts

section "claim-token contexts in current files"
for f in docs/qigpu/pasted-text.txt docs/system-update/mining-and-accelerators.md evidence/acceleration/capability-report.md evidence/acceleration/findings_tensor_baseline.md evidence/cyclotomic/exact-mps-prototype.md reviews/acceleration_review.md scripts/ci/regional_failover_burst_test.py src/chronus/tensor/charter.py src/chronus/tensor/exact_mps.py src/turing/physics/cayley.py src/turing/stabilizer/tableau.py tests/test_falsifiable_tensor.py src/chronus/tensor/evolution.py src/chronus/service/production_hr_api_v2.py src/chronus/tensor/adaptive_contraction.py src/chronus/tensor/enhanced_representation.py src/chronus/chronus_gpiu-v36.py artifacts/qigpu/exact_library/qudit_qec.py docs/FINOPS_AND_COMMERCIAL_ROI_BRIEF.md; do
  echo "--- $f"; grep -n -i -o -E ".{0,70}(infinite|exponential|unlimited|100x).{0,40}" "$f" | head -6
done

section "test_forbidden_claims.py"
cat tests/test_forbidden_claims.py
