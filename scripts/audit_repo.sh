#!/usr/bin/env bash
# scripts/audit_repo.sh — read-only pre-stage audit. Prints findings, exits 0.
set -uo pipefail

section() { printf '\n== %s ==\n' "$1"; }

section "branch"
git rev-parse --abbrev-ref HEAD
git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || echo "NO UPSTREAM"

section "tracked but ignored (should be none)"
git ls-files -ci --exclude-standard

section "untracked, including ignored"
git status --porcelain=v1 -uall | grep '^??' || echo "none"

section "files over 512KB"
git ls-files -z | xargs -0 -r ls -l 2>/dev/null \
  | awk '$5 > 524288 {printf "%8.1fKB %s\n", $5/1024, $9}' | sort -rn

section "largest tracked files"
git ls-files -z | xargs -0 -r ls -l 2>/dev/null \
  | sort -k5 -n | tail -10 | awk '{printf "%8.1fKB %s\n", $5/1024, $9}'

section "secret-shaped strings"
git grep -nEI 'ghp_[A-Za-z0-9]{36}|sk-[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY|AccountKey=|client_secret\s*=' \
  -- . ':!*.lock' || echo "none"

section "env files"
git ls-files | grep -E '(^|/)\.env' || echo "none tracked"

section "line endings not LF in the index"
git ls-files --eol | grep -v 'i/lf' | grep -v 'i/-text' || echo "all LF"

section "conflict markers"
git grep -nE '^(<<<<<<<|>>>>>>>|=======)$' -- . || echo "none"

section "TODO/FIXME/HACK"
git grep -cE 'TODO|FIXME|HACK' -- '*.py' | sort -t: -k2 -rn | head -10 || echo "none"

section "config presence"
for f in pyproject.toml .gitignore .gitattributes pytest.ini .flake8 ruff.toml \
         .github/workflows; do
  [ -e "$f" ] && echo "present: $f" || echo "MISSING: $f"
done

section "local config vs CI"
git ls-files '.github/workflows/*' | while read -r wf; do
  grep -hoE '(ruff|flake8|pytest|mypy)[^ ]*' "$wf" 2>/dev/null | sort -u \
    | sed "s|^|$wf: |"
done || echo "no workflows"

section "gitignore coverage"
for d in __pycache__ .pytest_cache .ruff_cache .mypy_cache dist build .venv; do
  git check-ignore -q "$d" 2>/dev/null && echo "ignored: $d" || echo "NOT IGNORED: $d"
done

section "executable bits on scripts"
git ls-files -s scripts/ | awk '$1=="100755"{print $4}' || true

printf '\n== audit complete ==\n'