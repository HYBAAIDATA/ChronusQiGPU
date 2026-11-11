#!/usr/bin/env bash
# Supervisor workbench (idempotent; every push to the workbench re-runs it).
#  1. Branch upkeep: create feat/geodesic-11d from main when absent; list open
#     pull requests and branch heads.
#  1b. Full-history search of every branch for earlier Shor, period-finding,
#     order-finding and phase-estimation code (paths and contents).
#  2. Staged work under .supervisor/stage/<name>/ (files/, optional files.b64/,
#     EMPTY.txt and DELETE.txt, MANIFEST.tsv, COMMIT_MSG.txt) is applied in order to its
#     target branch after merging main, every blob SHA is checked, each stage
#     becomes one commit carrying a "Supervisor-Stage: <name> <id>" trailer,
#     the CI-equivalent gates run, and the branch is pushed only if all pass.
#     A stage whose trailer is already on the branch is skipped.
set +e
cd "$GITHUB_WORKSPACE" || exit 1
git fetch -q origin '+refs/heads/*:refs/remotes/origin/*'
REPO="$GITHUB_REPOSITORY"

# 1. Branch upkeep -----------------------------------------------------------
{
for b in feat/geodesic-11d; do
  if git rev-parse -q --verify "origin/$b" >/dev/null; then echo "exists: $b $(git rev-parse "origin/$b")"
  else git push -q origin "$(git rev-parse origin/main):refs/heads/$b" && echo "created from main: $b $(git rev-parse origin/main)"; fi
done
git fetch -q origin '+refs/heads/*:refs/remotes/origin/*'
echo "== open pull requests"
gh api "repos/$REPO/pulls?state=open&per_page=50" --jq '.[] | "#\(.number) \(.head.ref) -> \(.base.ref) \(.head.sha[0:7]) draft=\(.draft) \(.title)"'
echo "== branch heads"
git for-each-ref --format='%(refname:short) %(objectname:short) %(committerdate:iso8601)' refs/remotes/origin | grep -v HEAD
} > "$OUT/branches.txt" 2>&1

# 1b. Full-history search (only when the workbench commit subject contains [history]) ---
if git log -1 --format=%s | grep -qF '[history]'; then
{
PAT='shor|period[_ -]?find|order[_ -]?find|continued[_ -]?fraction|modular[_ -]?exponent|phase[_ -]?estimation'
echo "== paths matching shor / period / order finding / qpe / phase estimation, in any commit on any branch"
git log --all --format='commit %h %ad %an: %s' --date=iso --name-status --diff-filter=ADR \
  | awk '/^commit /{c=$0; next} NF{ if (tolower($0) ~ /shor|period.?find|order.?find|qpe|phase.?estim/) print c " | " $0 }' | sort -u | head -300
echo
echo "== branch tips: Python files whose content matches (case-insensitive)"
for ref in $(git for-each-ref --format='%(refname:short)' refs/remotes/origin | grep -v HEAD); do
  hits=$(git grep -I -i -l -E "$PAT" "$ref" -- '*.py' 2>/dev/null | sed "s|^$ref:||" | head -80)
  [ -n "$hits" ] && { echo "-- $ref"; echo "$hits"; }
done
echo
echo "== commits on any branch whose Python diff adds or removes matching lines"
timeout 1200 git log --all --regexp-ignore-case -G "$PAT" --format='%h %ad %an: %s' --date=iso -- '*.py' | head -300
echo "search exit=$?"
} > "$OUT/history_shor.txt" 2>&1
fi

# 2. Staged work -------------------------------------------------------------
stage_present() { [ -f "$SUP/stage/$1/MANIFEST.tsv" ] && [ -f "$SUP/stage/$1/COMMIT_MSG.txt" ]; }
stage_id() { sha256sum "$SUP/stage/$1/MANIFEST.tsv" | cut -c1-16; }
stage_done() { git log --format=%B HEAD | grep -qx "Supervisor-Stage: $1 $(stage_id "$1")"; }

apply_stage() {  # returns 0 committed, 1 error
  local ST="$SUP/stage/$1" sha path got bad=0 extra f
  [ -d "$ST/files" ] && cp -a "$ST/files/." .
  if [ -d "$ST/files.b64" ]; then
    while read -r f; do
      mkdir -p "$(dirname "${f%.b64}")"
      base64 -d "$ST/files.b64/$f" > "${f%.b64}" || { echo "stage $1: cannot decode $f"; return 1; }
    done < <(cd "$ST/files.b64" && find . -type f -name '*.b64' | sed 's|^\./||')
  fi
  if [ -f "$ST/EMPTY.txt" ]; then
    while read -r path; do [ -n "$path" ] && mkdir -p "$(dirname "$path")" && : > "$path"; done < "$ST/EMPTY.txt"
  fi
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
  { cat "$ST/COMMIT_MSG.txt"; printf '\nSupervisor-Stage: %s %s\n' "$1" "$(stage_id "$1")"; } > "$RUNNER_TEMP/msg.txt"
  git commit -q -F "$RUNNER_TEMP/msg.txt" || { echo "stage $1: commit failed"; return 1; }
  echo "stage $1 committed $(git rev-parse HEAD) ($(wc -l < "$RUNNER_TEMP/changed.txt") paths)"
  return 0
}

verify() {  # $1 = output prefix; sets GATES_OK
  local P=99 R1=99 R2=99 C=99 TW=99 CL1=99 CL2=99 TI=99 TC=99 HEADSHA BOK=0
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
  grep -q 'build hyba-chronus exit=0' "$OUT/$1_build.txt" && grep -q 'build hyba-turing exit=0' "$OUT/$1_build.txt" \
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

# process_branch <prefix> <branch> <create-from-main 0|1> <require-path|-> <stage>...  (stages apply in order)
process_branch() {
  local prefix="$1" br="$2" create="$3" req="$4"; shift 4
  local s start avail=() pending=0
  for s in "$@"; do
    if stage_present "$s"; then avail+=("$s"); else echo "$prefix: stage $s not present yet; it and any later stage wait"; break; fi
  done
  [ "${#avail[@]}" -gt 0 ] || { echo "$prefix: no stage present; skipped"; return 0; }
  if git rev-parse -q --verify "origin/$br" >/dev/null; then git checkout -q -B "$br" "origin/$br"
  elif [ "$create" = 1 ]; then git checkout -q -B "$br" origin/main; echo "$prefix: $br will be created from main"
  else echo "$prefix: $br does not exist; nothing done"; return 1; fi
  start=$(git rev-parse HEAD); echo "$prefix: $br head before $start"
  if [ "$req" != "-" ] && [ ! -e "$req" ]; then echo "$prefix: required $req is not on $br yet; nothing done"; return 1; fi
  for s in "${avail[@]}"; do stage_done "$s" || pending=1; done
  [ "$pending" = 1 ] || { echo "$prefix: stages ${avail[*]} already on $br; nothing to do"; return 0; }
  if ! git merge-base --is-ancestor origin/main HEAD; then
    if ! git merge -q --no-edit origin/main > "$OUT/${prefix}_merge.txt" 2>&1; then
      echo "$prefix: merge of main conflicted; nothing pushed"; git diff --name-only --diff-filter=U >> "$OUT/${prefix}_merge.txt"; git merge --abort; return 1
    fi
    echo "$prefix: merged main $(git rev-parse --short origin/main)"
  fi
  for s in "${avail[@]}"; do
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
process_branch partner feat/partner-distribution 0 - partner-c3 partner-hardening
} > "$OUT/stages.txt" 2>&1
git checkout -q -- . 2>/dev/null; git clean -fdq 2>/dev/null
