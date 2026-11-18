#!/usr/bin/env bash
# Compile formal/GL2Mod256.lean (core Lean, no Mathlib) with its pinned toolchain and
# fail closed on proof placeholders or any axiom beyond Lean's standard three.
set -euo pipefail
cd "$(dirname "$0")"
TOOLCHAIN="leanprover/lean4:v4.36.0"   # `grind` is not available in lean/'s v4.15.0
file=GL2Mod256.lean
if grep -En '\b(sorry|admit)\b|^\s*axiom\b' "$file"; then
  echo "Found a proof placeholder or axiom declaration in $file" >&2
  exit 1
fi
probe=$(mktemp -d)/GL2Mod256Axioms.lean
cp "$file" "$probe"
names=$(grep -Eo '^theorem [A-Za-z0-9_]+' "$file" | awk '{print $2}')
count=$(printf '%s\n' "$names" | grep -c . || true)
for n in $names; do printf '#print axioms GL2Mod256.%s\n' "$n" >> "$probe"; done
output=$(lean "+$TOOLCHAIN" "$probe" 2>&1)
printf '%s\n' "$output"
reported=$(printf '%s\n' "$output" | grep -Ec "^'GL2Mod256\.[A-Za-z0-9_]+' (does not depend on any axioms|depends on axioms: \[)" || true)
if [ "$reported" -ne "$count" ]; then
  echo "Expected an axiom report for $count theorems, got $reported" >&2
  exit 1
fi
if printf '%s\n' "$output" | grep -E 'depends on axioms' | grep -Ev 'depends on axioms: \[((propext|Classical\.choice|Quot\.sound)(, )?)+\]$'; then
  echo 'A theorem depends on a non-standard axiom (sorryAx or a declared axiom)' >&2
  exit 1
fi
echo "GL2Mod256: $count theorems kernel-checked; axioms limited to propext/Classical.choice/Quot.sound."
