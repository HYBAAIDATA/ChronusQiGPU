#!/usr/bin/env bash
# CI dependency installer for the in-tree PYTHIA distributions.
#
# hyba-kellogg-tensor and chronos-one-igpu are not published to PyPI; they ship
# as in-tree packages. Install them from the checkout (Kellogg is staged the way
# packaging/kellogg-tensor stages it) together with TURING and the umbrella so
# dependency resolution never reaches out to PyPI for them.
#
# Usage:
#   scripts/ci_install.sh "<extras>"           # install umbrella with extras (e.g. "ml,dev,graph")
#   scripts/ci_install.sh ""                   # umbrella, no extras
#   scripts/ci_install.sh "<extras>" --no-root # only the substrate deps (turing/kellogg/chronos)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

EXTRAS="${1:-}"
shift || true
INSTALL_ROOT=1
DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --no-root) INSTALL_ROOT=0 ;;
    --dry-run) DRY_RUN=1 ;;
    *) echo "ci_install.sh: unknown option '$arg'" >&2; exit 2 ;;
  esac
done

# Build the in-tree Kellogg distribution from the repo's real package layout.
# A temporary staging directory breaks the package's relative path assumptions
# in packaging/kellogg-tensor/pyproject.toml (../../kellogg), which is exactly
# why the wheel build fails under CI.
KELLOGG_BUILD="./packaging/kellogg-tensor"

# Substrate distributions that are in-tree and never on PyPI.
SUBSTRATE=(
  "$KELLOGG_BUILD"
  ./chronus/packages/chronos-one-igpu
  ./turing_universal_quantum_computer
)

PIP_FLAGS=()
if [ "$DRY_RUN" -eq 1 ]; then
  PIP_FLAGS+=(--dry-run)
fi

if [ "$INSTALL_ROOT" -eq 1 ]; then
  if [ -n "$EXTRAS" ]; then
    TARGET=".["$EXTRAS"]"
  else
    TARGET="."
  fi
  python -m pip install "${PIP_FLAGS[@]}" "${SUBSTRATE[@]}" "$TARGET"
else
  python -m pip install "${PIP_FLAGS[@]}" "${SUBSTRATE[@]}"
fi
