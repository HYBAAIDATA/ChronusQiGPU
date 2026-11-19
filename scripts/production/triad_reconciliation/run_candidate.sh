#!/bin/bash
# Usage: run_candidate.sh <sha>  — runs all local evidence on a clean worktree of <sha>
set -u
SHA=$1; D=${OUT:-/workspace/closeout-data/cand}; WT=/workspace/closeout-cand
rm -rf $D; mkdir -p $D
cd /workspace/chronus-closeout && git fetch -q origin && (git worktree remove --force $WT 2>/dev/null; true) && git worktree add -q --detach $WT $SHA
cd $WT
PY=/workspace/closeout-venv/bin/python
export PYTHONPATH=$WT/src:$WT
{ echo "sha=$(git rev-parse HEAD)"; $PY --version; uname -srm; $PY -c "import sqlite3;print('sqlite',sqlite3.sqlite_version)"; nproc; } > $D/env.txt 2>&1
( time $PY -m pytest -q -p no:cacheprovider --junitxml=$D/junit.xml -o junit_family=xunit2 > $D/pytest.txt 2>&1 ) 2> $D/pytest_time.txt; echo "pytest exit $?" >> $D/pytest.txt
$PY scripts/ci/triad_cross_checks.py --out $D/xchecks.json 2> $D/xchecks.err
$PY scripts/ci/test_execution_gate.py --suite main --junit $D/junit.xml > $D/test_execution_gate.txt 2>&1; echo "test_execution_gate exit=$?" > $D/gates_pre.txt
for g in "scripts/ci/no_dressing.py --baseline" scripts/ci/test_reality.py scripts/ci/quantum_naming.py scripts/ci/check_forbidden_claims.py; do $PY $g > /dev/null 2>&1; echo "$g exit=$?"; done > $D/gates.txt; cat $D/gates_pre.txt >> $D/gates.txt
# benchmarks on SHA-pinned public data (prepared with scikit-learn 1.8.0)
U=/workspace/closeout-data/uci/data
mkdir -p $D/bench/target
$PY benchmarks/real_workload_benchmark.py --manifest $U/manifest.yaml --custody-db $D/bench/custody.sqlite3 --output $D/bench/real_workload.json --depth 4 > $D/bench/real_workload.log 2>&1; echo "real_workload exit=$?" >> $D/gates.txt
$PY benchmarks/qualify_storage_performance.py --manifest $U/manifest.yaml --target-directory $D/bench/target --output $D/bench/storage.json > $D/bench/storage.log 2>&1; echo "storage exit=$?" >> $D/gates.txt
$PY scripts/benchmarks/run_public_uci_components.py --manifest $U/manifest.yaml --output $D/bench/components.json --depth 4 > $D/bench/components.log 2>&1; echo "components exit=$?" >> $D/gates.txt
# artifacts
rm -rf $D/dist && $PY -m build --outdir $D/dist . > $D/build.log 2>&1; echo "build exit=$?" >> $D/gates.txt
$PY -m twine check $D/dist/* >> $D/build.log 2>&1; echo "twine exit=$?" >> $D/gates.txt
(cd packages/turing && $PY -m build --outdir $D/dist . >> $D/build.log 2>&1); echo "turing build exit=$?" >> $D/gates.txt
(cd $D/dist && sha256sum * > SHA256SUMS)
# clean install of the built wheel into a fresh venv (dependency resolution + installed provenance)
rm -rf /tmp/cand-install && python3 -m venv /tmp/cand-install && /tmp/cand-install/bin/pip install -q $D/dist/hyba_chronus-*.whl > $D/install.log 2>&1; echo "clean install exit=$?" >> $D/gates.txt
/tmp/cand-install/bin/pip check >> $D/install.log 2>&1; echo "pip check exit=$?" >> $D/gates.txt
(cd /tmp && /tmp/cand-install/bin/python -c "import chronus,sys;print('installed', chronus.__version__, chronus.__file__)" >> $D/install.log 2>&1); echo "installed import exit=$?" >> $D/gates.txt
/tmp/cand-install/bin/pip show -f hyba-chronus | head -12 >> $D/install.log 2>&1
echo done
