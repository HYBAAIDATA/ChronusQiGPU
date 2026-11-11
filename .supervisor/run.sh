#!/usr/bin/env bash
# Supervisor workbench run 6+ (idempotent; every push to the workbench re-runs it).
#  1. Branch upkeep: delete branches whose pull requests are merged (only when
#     GitHub reports the PR merged and the branch still points at the PR head);
#     create feat/geodesic-11d from main when absent; list open PRs.
#  2. Staged work under .supervisor/stage/<name>/ (files/, MANIFEST.tsv,
#     DELETE.txt, COMMIT_MSG.txt) is applied to its target branch with git
#     (deletions included) after merging main, every blob SHA is checked, the
#     CI-equivalent gates run, and the branch is pushed only if all pass.
#     A stage already present on its branch is skipped.
set +e
cd "$GITHUB_WORKSPACE" || exit 1
git fetch -q origin '+refs/heads/*:refs/remotes/origin/*'
REPO="$GITHUB_REPOSITORY"

# 1. Branch upkeep -----------------------------------------------------------
{
for pair in "29:chore/turing-packaging-consolidation-20261111" "30:feat/hendrix-structured-search"; do
  pr="${pair%%:*}"; br="${pair#*:}"
  merged=$(gh api "repos/$REPO/pulls/$pr" --jq '.merged' 2>&1)
  head=$(gh api "repos/$REPO/pulls/$pr" --jq '.head.sha' 2>&1)
  tip=$(git rev-parse -q --verify "origin/$br")
  if [ "$merged" = "true" ] && [ -n "$tip" ] && [ "$tip" = "$head" ]; then
    git push -q origin --delete "$br" && echo "deleted (PR #$pr merged, head $head): $br"
  else
    echo "kept $br: merged=$merged pr_head=$head branch_tip=${tip:-absent}"
  fi
done
for b in feat/geodesic-11d; do
  if git rev-parse -q --verify "origin/$b" >/dev/null; then echo "exists: $b $(git rev-parse "origin/$b")"
  else git push -q origin "$(git rev-parse origin/main):refs/heads/$b" && echo "created from main: $b $(git rev-parse origin/main)"; fi
done
git fetch -q origin '+refs/heads/*:refs/remotes/origin/*'
echo "== open pull requests"
gh api "repos/$REPO/pulls?state=open&per_page=50" --jq '.[] | "#\(.number) \(.head.ref) -> \(.base.ref) \(.head.sha[0:7]) draft=\(.draft) \(.title)"'
echo "== branch heads"
git for-each-ref --format='%(refname:short) %(objectname:short)' refs/remotes/origin | grep -v HEAD
} > "$OUT/branches.txt" 2>&1

# 2. Staged work -------------------------------------------------------------
stage_present() { [ -f "$SUP/stage/$1/MANIFEST.tsv" ]; }

stage_done() {  # every staged blob present on the checkout and every deletion done
  local ST="$SUP/stage/$1" sha path
  while IFS=$'\t' read -r sha path; do
    [ -z "$path" ] && continue
    [ -f "$path" ] && [ "$(git hash-object "$path")" = "$sha" ] || return 1
  done < "$ST/MANIFEST.tsv"
  if [ -f "$ST/DELETE.txt" ]; then
    while read -r path; do [ -n "$path" ] && [ -e "$path" ] && return 1; done < "$ST/DELETE.txt"
  fi
  return 0
}

apply_stage() {  # returns 0 committed, 1 error
  local ST="$SUP/stage/$1" sha path got bad=0 extra
  cp -a "$ST/files/." .
  if [ -f "$ST/DELETE.txt" ]; then
    while read -r path; do [ -n "$path" ] && [ -e "$path" ] && git rm -q -r -- "$path" && echo "deleted: $path"; done < "$ST/DELETE.txt"
  fi
  while IFS=$'\t' read -r sha path; do
    [ -z "$path" ] && continue
    got=$(git hash-object "$path" 2>/dev/null)
    [ "$got" = "$sha" ] || { echo "BLOB MISMATCH $path expected=$sha got=$got"; bad=1; }
  done < "$ST/MANIFEST.tsv"
  [ "$bad" = 0 ] || { echo "stage $1: blob mismatch"; return 1; }
  git add -A
  git diff --cached --name-only | sort > "$RUNNER_TEMP/changed.txt"
  { cut -f2 "$ST/MANIFEST.tsv"; [ -f "$ST/DELETE.txt" ] && cat "$ST/DELETE.txt"; } | grep . | sort -u > "$RUNNER_TEMP/expected.txt"
  extra=$(comm -23 "$RUNNER_TEMP/changed.txt" "$RUNNER_TEMP/expected.txt")
  [ -z "$extra" ] || { echo "stage $1: unexpected changed paths:"; echo "$extra"; return 1; }
  git commit -q -F "$ST/COMMIT_MSG.txt" || { echo "stage $1: commit failed"; return 1; }
  echo "stage $1 committed $(git rev-parse HEAD) ($(wc -l < "$RUNNER_TEMP/changed.txt") paths)"
  return 0
}

verify() {  # $1 = output prefix; sets GATES_OK
  local P=99 R1=99 R2=99 C=99 TW=99 CL1=99 CL2=99 TI=99 TC=99 HEADSHA
  HEADSHA=$(git rev-parse HEAD); GATES_OK=0
  python -m venv "$RUNNER_TEMP/v_$1" && . "$RUNNER_TEMP/v_$1/bin/activate"
  python -m pip install -q --upgrade pip > /dev/null 2>&1
  python -m pip install -q -e '.[dev]' ruff build twine > "$OUT/$1_install.txt" 2>&1; echo "install exit=$?" >> "$OUT/$1_install.txt"
  { echo "commit: $HEADSHA"; echo "date_utc: $(date -u +%FT%TZ)"; echo "runner: $(uname -srm)"; echo "python: $(python -V 2>&1)"; echo "command: python -m pytest -q"; } > "$OUT/$1_evidence.txt"
  CHRONUS_WORKLOAD_DB_PATH="$RUNNER_TEMP/$1.sqlite3" timeout 2400 python -m pytest -q -p no:cacheprovider -rfE --tb=short > "$OUT/$1_pytest.txt" 2>&1
  P=$?; echo "pytest exit=$P" >> "$OUT/$1_pytest.txt"; tail -n 3 "$OUT/$1_pytest.txt" >> "$OUT/$1_evidence.txt"
  ruff check --select F src/chronus/execution src/chronus/backends src/chronus/service src/chronus/sdk src/chronus/security src/chronus/stratum src/chronus/math src/chronus/hw tests > "$OUT/$1_lint.txt" 2>&1; R1=$?
  ruff check --select F src/chronus/hermes src/chronus/ovid src/chronus/theseus src/chronus/geodesic src/chronus/igpu packages/turing/src scripts/ci/check_wheels.py scripts/ci/check_no_temporary_workflows.py >> "$OUT/$1_lint.txt" 2>&1; R2=$?
  python -m compileall -q src/chronus packages/turing/src >> "$OUT/$1_lint.txt" 2>&1; C=$?
  python scripts/ci/check_no_temporary_workflows.py >> "$OUT/$1_lint.txt" 2>&1; TW=$?
  echo "ruff ci=$R1 ruff new=$R2 compileall=$C temp-workflows=$TW" >> "$OUT/$1_lint.txt"
  python -m unittest discover -s tests -p 'test_forbidden_claims.py' > "$OUT/$1_claims.txt" 2>&1; CL1=$?
  python scripts/ci/check_forbidden_claims.py >> "$OUT/$1_claims.txt" 2>&1; CL2=$?
  echo "claims unittest=$CL1 scan=$CL2" >> "$OUT/$1_claims.txt"
  rm -rf dist
  { python -m build --outdir dist/chronus . > "$RUNNER_TEMP/b1.txt" 2>&1; echo "build hyba-chronus exit=$?"; tail -n 2 "$RUNNER_TEMP/b1.txt"
    python -m build --outdir dist/turing packages/turing > "$RUNNER_TEMP/b2.txt" 2>&1; echo "build hyba-turing exit=$?"; tail -n 2 "$RUNNER_TEMP/b2.txt"
    python -m twine check dist/chronus/* dist/turing/*; echo "twine exit=$?"
    python scripts/ci/check_wheels.py dist/chronus dist/turing; echo "wheel check exit=$?"; } > "$OUT/$1_build.txt" 2>&1
  local BOK=0; grep -q 'build hyba-chronus exit=0' "$OUT/$1_build.txt" && grep -q 'build hyba-turing exit=0' "$OUT/$1_build.txt" \
    && grep -q 'twine exit=0' "$OUT/$1_build.txt" && grep -q 'wheel check exit=0' "$OUT/$1_build.txt" && BOK=1
  { for s in purity_gate.py test_the_tests.py; do echo "== $s"; timeout 900 python "scripts/ci/$s" > "$RUNNER_TEMP/step.txt" 2>&1; c=$?; tail -n 6 "$RUNNER_TEMP/step.txt"; echo "$s exit=$c"; done; } > "$OUT/$1_purity.txt" 2>&1
  git checkout -q -- . ; git clean -fdq -e dist
  deactivate
  python -m venv "$RUNNER_TEMP/vt_$1" && . "$RUNNER_TEMP/vt_$1/bin/activate"
  python -m pip install -q dist/turing/*.whl 'pytest>=8' > "$OUT/$1_turing_pkg.txt" 2>&1; echo "install exit=$?" >> "$OUT/$1_turing_pkg.txt"
  local W="$RUNNER_TEMP/turing-isolated-$1"; rm -rf "$W"; mkdir -p "$W"; cp -r packages/turing/tests "$W/tests"; cp tests/test_turing.py "$W/tests/test_exact_layer.py"
  (cd "$W" && timeout 1200 python -m pytest -q -p no:cacheprovider -rfE --tb=short tests) >> "$OUT/$1_turing_pkg.txt" 2>&1; TI=$?
  echo "turing pytest exit=$TI" >> "$OUT/$1_turing_pkg.txt"
  (cd "$W" && python -c "import sys, turing, turing.exact; assert 'site-packages' in turing.__file__; assert 'chronus' not in sys.modules; print('ok', turing.__file__, turing.__version__)") >> "$OUT/$1_turing_pkg.txt" 2>&1; TC=$?
  deactivate
  git checkout -q -- . ; git clean -fdq
  echo "gates $1 @ $HEADSHA: pytest=$P ruff_ci=$R1 ruff_new=$R2 compileall=$C temp_workflows=$TW claims=$CL1/$CL2 builds_twine_wheelcheck=$BOK turing_isolated=$TI turing_import=$TC"
  if [ "$P" = 0 ] && [ "$R1" = 0 ] && [ "$R2" = 0 ] && [ "$C" = 0 ] && [ "$TW" = 0 ] && [ "$CL1" = 0 ] && [ "$CL2" = 0 ] && [ "$BOK" = 1 ] && [ "$TI" = 0 ] && [ "$TC" = 0 ]; then GATES_OK=1; fi
}

# process_branch <prefix> <branch> <create-from-main 0|1> <require-path|-> <stage>...
process_branch() {
  local prefix="$1" br="$2" create="$3" req="$4"; shift 4
  local any=0 s changed=0 start
  for s in "$@"; do stage_present "$s" && any=1; done
  [ "$any" = 1 ] || { echo "$prefix: no stage present; skipped"; return 0; }
  if git rev-parse -q --verify "origin/$br" >/dev/null; then git checkout -q -B "$br" "origin/$br"
  elif [ "$create" = 1 ]; then git checkout -q -B "$br" origin/main; echo "$prefix: $br will be created from main"
  else echo "$prefix: $br does not exist; nothing done"; return 1; fi
  start=$(git rev-parse HEAD); echo "$prefix: $br head before $start"
  if [ "$req" != "-" ] && [ ! -e "$req" ]; then echo "$prefix: required $req is not on $br yet; nothing done"; return 1; fi
  local pending=0
  for s in "$@"; do stage_present "$s" && ! stage_done "$s" && pending=1; done
  [ "$pending" = 1 ] || { echo "$prefix: all stages already on $br; nothing to do"; return 0; }
  if ! git merge-base --is-ancestor origin/main HEAD; then
    if ! git merge -q --no-edit origin/main > "$OUT/${prefix}_merge.txt" 2>&1; then
      echo "$prefix: merge of main conflicted; nothing pushed"; git diff --name-only --diff-filter=U >> "$OUT/${prefix}_merge.txt"; git merge --abort; return 1
    fi
    echo "$prefix: merged main $(git rev-parse --short origin/main)"
  fi
  for s in "$@"; do
    stage_present "$s" || continue
    if stage_done "$s"; then echo "$prefix: stage $s already present"; continue; fi
    apply_stage "$s" || { echo "$prefix: nothing pushed"; return 1; }
  done
  git log --stat --format='%H%n%s' "$start..HEAD" > "$OUT/${prefix}_commits.txt"
  verify "$prefix"
  if [ "$GATES_OK" = 1 ]; then
    if git push -q origin "HEAD:refs/heads/$br"; then echo "$prefix: PUSHED $br $(git rev-parse HEAD)"; else echo "$prefix: push failed (branch moved?)"; fi
  else echo "$prefix: a gate failed; nothing pushed"; fi
}

{
process_branch turing feat/turing-exact-algorithms 0 packages/turing/tests/test_turing_clifford.py tensor
git checkout -q -- . 2>/dev/null; git clean -fdq 2>/dev/null
process_branch geodesic feat/geodesic-11d 1 - geodesic
git checkout -q -- . 2>/dev/null; git clean -fdq 2>/dev/null
process_branch partner feat/partner-distribution 0 packages/hyba-client/pyproject.toml partner-hardening
} > "$OUT/stages.txt" 2>&1
git checkout -q -- . 2>/dev/null; git clean -fdq 2>/dev/null
