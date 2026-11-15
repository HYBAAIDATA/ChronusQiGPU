#!/usr/bin/env bash
# Run inside an OpenLane 2023.09.07 environment with the design mounted.
set -euo pipefail
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
flow=${OPENLANE_FLOW:-/openlane/flow.tcl}
if [[ ! -f "$flow" ]]; then
  echo "BLOCKED: OpenLane flow not found at $flow" >&2
  exit 2
fi
if [[ -z "${PDK_ROOT:-}" || ! -d "$PDK_ROOT/sky130A" ]]; then
  echo 'BLOCKED: PDK_ROOT/sky130A unavailable' >&2
  exit 2
fi
if [[ ! -f "$here/../zeckendorf_alu_32lane.sv" ]]; then
  echo 'BLOCKED: RTL source unavailable' >&2
  exit 2
fi
exec "$flow" -design "$here/zeckendorf"
