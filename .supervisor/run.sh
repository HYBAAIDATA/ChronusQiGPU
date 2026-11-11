#!/usr/bin/env bash
# Supervisor workbench run 2: focused audit for the migration map.
set +e
cd "$GITHUB_WORKSPACE" || exit 1
git fetch -q origin '+refs/heads/*:refs/remotes/origin/*'
git fetch -q origin '+refs/pull/25/head:refs/remotes/pr/25' '+refs/pull/26/head:refs/remotes/pr/26' '+refs/pull/27/head:refs/remotes/pr/27' '+refs/pull/28/head:refs/remotes/pr/28'
git checkout -q -B probe origin/main
S() { echo; echo "=================== $* ==================="; }
EXCL='^(archive|chronus_source_backup|vendor|frontend/node_modules)/'
{
S "main"; git log -3 --format='%H %ad %s' --date=iso-strict origin/main
S "branches (ahead/behind main, merged?)"
for b in $(git for-each-ref --format='%(refname:short)' refs/remotes/origin refs/remotes/pr | grep -v -E 'origin/HEAD$|^origin$'); do
  echo "-- $b $(git rev-parse --short $b) ahead=$(git rev-list --count origin/main..$b) behind=$(git rev-list --count $b..origin/main) last=$(git log -1 --format='%ad %s' --date=short $b)"
  git log --format='   %h %s' origin/main..$b | head -8
done
S "merged into main"; git branch -r --merged origin/main
} > "$OUT/a_branches.txt" 2>&1

{
S "definitions in current code (excluding archive/backup/vendor/tests)"
git ls-files '*.py' | grep -v -E "$EXCL" | grep -v -E '^tests/' | xargs grep -n -i -E '^\s*(class|def) +\w*(geodesic|theseus|ovid|polytope|600|cell|hopf|myrmidon|patroclus|phalanx|galois|f257|oracle|tensor|igpu|gpiu|hermes|hendrix|grover|fourier|phyllotax|fold|search|gatekeeper|endian)' 2>/dev/null | cut -c1-200 | head -400
} > "$OUT/b_definitions.txt" 2>&1

{
S "tensor package imports"; for f in src/chronus/tensor/*.py; do echo "-- $f $(wc -l < $f) lines"; grep -n -E '^\s*(from|import) ' $f | head -25; done
S "who imports chronus.tensor"; git grep -n -E 'chronus\.tensor|from \.tensor|from \.\.tensor' -- ':!archive' ':!chronus_source_backup' | head -40
S "cpp tree and tensor/igpu mentions"; git ls-files cpp | xargs wc -c; git grep -n -i -E 'tensor|gpiu|igpu|opencl' -- cpp | head -40
S "OpenCL / iGPU runtime modules"; git grep -l -E 'pyopencl|opencl' -- 'src/*.py' | head -30; git ls-files src/chronus/backends src/chronus/kernels src/chronus/hw
S "production_hr_api*: root vs src"; for f in production_hr_api.py production_hr_api-v2.py; do echo "-- $f"; cat $f; done
S "test refs to root modules"; grep -n -E 'production_hr_api|al_haras_topological_os|sys\.path|spec_from_file_location|chronus_live_miner' tests/test_enhanced_tensor_representation_v2.py tests/test_security_full_coverage.py src/chronus/execution/master_e2e_engine.py | head -40
} > "$OUT/c_tensor_igpu.txt" 2>&1

{
S "apply_ovid_patch.py history"; git log --all --format='%h %ad %an %s' --date=short --stat -- apply_ovid_patch.py | head -30
S "any *ovid* path ever"; git log --all --name-only --format= | grep -i ovid | sort -u | head -30
S "chronus.security.ovid public surface"; grep -n -E '^\s*(class|def) ' src/chronus/security/ovid.py | head -40; head -30 src/chronus/security/ovid.py
S "storage.theseus public surface"; grep -n -E '^\s*(class|def) ' src/chronus/storage/theseus.py | head -40; head -25 src/chronus/storage/theseus.py
S "v36 geodesic/theseus/ovid definitions"; grep -n -i -E '^\s*class \w*(geodesic|theseus|ovid|phyllotax|fold)' src/chronus/chronus_gpiu-v36.py | head -30; grep -n -i -E 'def \w*geodesic' src/chronus/chronus_gpiu-v36.py | head -20
S "600-cell / polytope implementations"; git grep -n -i -E '600|hopf|vertices_count|polytope_dimension|icosian' -- 'src/*.py' | head -60
S "F_257 search and oracle modules"; wc -l src/chronus/math/f257_search.py src/chronus/quantum/*.py src/chronus/execution/geometric_galois_miner.py src/chronus/ns_dec.py src/chronus/orchestration/euclid.py; sed -n '1,120p' src/chronus/math/f257_search.py
} > "$OUT/d_ovid_theseus_geodesic_galois.txt" 2>&1

{
S "geometric_galois_miner head"; sed -n '1,80p' src/chronus/execution/geometric_galois_miner.py
S "quantum/grover.py"; sed -n '1,80p' src/chronus/quantum/grover.py
S "geometric_polychoron head"; sed -n '1,60p' src/chronus/quantum/geometric_polychoron.py
} > "$OUT/e_search_sources.txt" 2>&1

{
S "root qigpu scripts: docstrings and classes"
for f in qigpu_acceleration_system.py qigpu_unified__acceleration_system.py qigpu_master_tour_de_force.py qudit_qec.py chronus_live_miner.py read_cov.py; do
  echo "-- $f ($(wc -l < $f) lines)"; sed -n '1,25p' $f; grep -n -E '^class |^def |__main__' $f | head -60
done
S "acceleration package"; git ls-files src/chronus/acceleration tests/acceleration benchmarks evidence/acceleration reviews work_orders capabilities
S "capabilities"; for f in $(git ls-files capabilities); do echo "-- $f"; head -40 $f; done
S "work orders: owners/assignees"; for f in work_orders/*; do echo "-- $f"; grep -n -i -E 'owner|agent|assign|status|branch|^#' $f | head -40; done
S "diff root master e2e vs src"; diff <(tr -d '\r' < chronus_master_end_to_end_engine.py) <(tr -d '\r' < src/chronus/execution/master_e2e_engine.py) | grep -c -E '^[<>]'; diff <(tr -d '\r' < chronus_master_end_to_end_engine.py) <(tr -d '\r' < src/chronus/execution/master_e2e_engine.py) | head -80
} > "$OUT/f_root_scripts.txt" 2>&1

{
S "Dockerfile"; cat Dockerfile
S "docker-compose.yml"; cat docker-compose.yml
S "Makefile"; cat Makefile
S ".dockerignore"; cat .dockerignore
S ".gitignore"; cat .gitignore
S "workflow path references"; git grep -n -E 'pasted-text|acceleration|tests/|scripts/ci|src/chronus|harness|PYTHONPATH|--cov=' -- .github/workflows | cut -c1-220 | head -80
S "purity gate scope"; sed -n '1,80p' scripts/ci/purity_gate.py
S "manifest/attestation path refs"; git grep -n -E 'chronus_quantum_igpu|chronus-quantum-igpu' -- ':!archive' ':!chronus_source_backup' | head -30
S "packages/turing"; cat packages/turing/pyproject.toml; cat packages/turing/src/turing/__init__.py; sed -n '1,50p' packages/turing/src/turing/state.py; sed -n '1,30p' packages/turing/src/turing/gates.py
S "src/turing exports"; cat src/turing/__init__.py
S "src/chronus top level"; git ls-files src/chronus | awk -F/ 'NF>3{print $3} NF==3{print "(file) "$3}' | sort | uniq -c | sort -rn
} > "$OUT/g_build_ci_packages.txt" 2>&1

{
S "references to paths that move in phase 2"
for p in 'src/chronus/tensor' 'chronus\.tensor' 'src/chronus/acceleration' 'chronus\.acceleration' 'src/turing' 'from turing' 'import turing' 'chronus\.security\.ovid' 'chronus\.storage\.theseus' 'exact_primitive_library' 'qudit_qec' 'qigpu_' 'BLOCKER_' 'chronus-k8s-deployment' 'ARTIFACT_SUMMARY' 'apply_ovid_patch' 'read_cov'; do
  echo "-- $p"; git grep -n -E "$p" -- ':!archive' ':!chronus_source_backup' ':!vendor' ':!filelist.txt' ':!tree_output.txt' ':!cov_output.txt' ':!build_ci_failed.log' | cut -c1-200 | head -30
done
} > "$OUT/h_move_references.txt" 2>&1
