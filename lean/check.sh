#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
lean --version
lake --version
lake build
output=$(lake env lean Tests/Smoke.lean)
printf '%s\n' "$output"
count=$(printf '%s\n' "$output" | grep -Fc 'does not depend on any axioms' || true)
standard=$(printf '%s\n' "$output" | grep -Fc 'depends on axioms: [propext]' || true)
if [ "$count" -ne 3 ] || [ "$standard" -ne 5 ]; then
  echo 'Unexpected theorem axiom report' >&2
  exit 1
fi
if grep -REn '\b(sorry|admit|axiom)\b' Chronus.lean Chronus Tests; then
  echo 'Found a proof placeholder or axiom declaration' >&2
  exit 1
fi
echo 'Lean smoke checks passed (3 closed identities axiom-free; 5 universal laws depend only on propext).'
# GL(2, Z/256Z) transform proofs live outside this Lake package (newer toolchain for `grind`).
bash ../formal/check_gl2.sh
