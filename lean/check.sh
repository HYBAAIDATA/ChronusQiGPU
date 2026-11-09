#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
lean --version
lake --version
lake build
output=$(lake env lean Tests/Smoke.lean)
printf '%s\n' "$output"
count=$(printf '%s\n' "$output" | grep -Fc 'does not depend on any axioms' || true)
if [ "$count" -ne 3 ]; then
  echo 'Unexpected theorem axiom report' >&2
  exit 1
fi
if grep -REn '\b(sorry|admit|axiom)\b' Chronus.lean Chronus Tests; then
  echo 'Found a proof placeholder or axiom declaration' >&2
  exit 1
fi
echo 'Lean smoke checks passed (3 closed identities; no declared axioms).'
