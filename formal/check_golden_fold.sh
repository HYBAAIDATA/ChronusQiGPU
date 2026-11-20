#!/usr/bin/env bash
# Compile formal/GoldenFold.lean (core Lean, no Mathlib) with its pinned toolchain and
# fail closed on proof placeholders or any axiom beyond Lean's standard three.
#
# Declarations are enumerated by Lean itself (every theorem in namespace GoldenFold in
# the elaborated environment, private and attributed ones included), so a source
# spelling such as `@[simp] theorem` or `private theorem` cannot escape the axiom audit.
#
# Env: GOLDEN_LEAN_FILE (default GoldenFold.lean), LEAN_BIN (a lean binary of the pinned
# version; default: elan's `lean +leanprover/lean4:v4.36.0`).
set -euo pipefail
cd "$(dirname "$0")"
TOOLCHAIN="leanprover/lean4:v4.36.0"   # `grind` is not available in lean/'s v4.15.0
file=${GOLDEN_LEAN_FILE:-GoldenFold.lean}
if [ -n "${LEAN_BIN:-}" ]; then lean_cmd=("$LEAN_BIN"); else lean_cmd=(lean "+$TOOLCHAIN"); fi
if grep -En '\b(sorry|admit)\b|^\s*axiom\b' "$file"; then
  echo "Found a proof placeholder or axiom declaration in $file" >&2
  exit 1
fi
if grep -En '^\s*import\b' "$file"; then
  echo "$file must stay core-only (no imports) for this probe" >&2
  exit 1
fi
probe_dir=$(mktemp -d)
trap 'rm -rf "$probe_dir"' EXIT
probe=$probe_dir/GoldenFoldAxioms.lean
{
  echo 'import Lean'
  cat "$file"
  cat <<'LEAN'

open Lean in
#eval show CoreM Unit from do
  let env ← getEnv
  let mut names : Array Name := #[]
  for (n, c) in env.constants.map₂.toList do
    let u := (privateToUserName? n).getD n
    if (`GoldenFold).isPrefixOf u then
      match c with
      | .axiomInfo _ => IO.println s!"GOLDENAXIOMDECL {u}"
      | .thmInfo _ => if !u.isInternalDetail then names := names.push n
      | _ => pure ()
  names := names.qsort (fun a b => a.toString < b.toString)
  IO.println s!"GOLDENDECLS {names.size}"
  for n in names do
    let axs ← collectAxioms n
    IO.println s!"GOLDENDECL {(privateToUserName? n).getD n} AXIOMS {axs.toList}"
LEAN
} > "$probe"
if output=$("${lean_cmd[@]}" "$probe" 2>&1); then
  printf '%s\n' "$output"
else
  rc=$?
  printf '%s\n' "$output" >&2
  exit "$rc"
fi
if printf '%s\n' "$output" | grep -E '^GOLDENAXIOMDECL '; then
  echo 'An axiom is declared in namespace GoldenFold' >&2
  exit 1
fi
total=$(printf '%s\n' "$output" | sed -n 's/^GOLDENDECLS \([0-9][0-9]*\)$/\1/p')
reported=$(printf '%s\n' "$output" | grep -c '^GOLDENDECL ' || true)
if [ -z "$total" ] || [ "$reported" -ne "$total" ] || [ "$total" -eq 0 ]; then
  echo "Lean did not report an axiom set for every GoldenFold theorem ($reported of ${total:-?})" >&2
  exit 1
fi
# every theorem spelled in the source (any modifiers/attributes) must be in Lean's list
for n in $(grep -Eo '^\s*(@\[[^]]*\]\s*)*((private|protected|noncomputable)\s+)*theorem\s+[A-Za-z0-9_.]+' "$file" | awk '{print $NF}'); do
  if ! printf '%s\n' "$output" | grep -Eq "^GOLDENDECL GoldenFold\.${n//./\\.} AXIOMS"; then
    echo "Source theorem $n missing from Lean's enumeration" >&2
    exit 1
  fi
done
if printf '%s\n' "$output" | grep -E '^GOLDENDECL ' | grep -Ev 'AXIOMS \[((propext|Classical\.choice|Quot\.sound)(, (propext|Classical\.choice|Quot\.sound))*)?\]$'; then
  echo 'A theorem depends on a non-standard axiom (sorryAx, Lean.ofReduceBool or a declared axiom)' >&2
  exit 1
fi
echo "GoldenFold: $total theorems (Lean-enumerated) kernel-checked; axioms limited to propext/Classical.choice/Quot.sound."
