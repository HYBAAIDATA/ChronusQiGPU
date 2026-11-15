#!/usr/bin/env bash
# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
#
# Start HYBA Mine: pre-flight first, then mining. Used in a terminal and by the
# launchd agent (ae.hybadata.mine). Extra arguments go to `hyba-mine start`,
# for example: bash scripts/mine/run.sh --backend igpu (or --prefer host for Metal)
#
# `hyba-mine start` always runs the full pre-flight (known-answer tests on real
# Bitcoin headers on the Chronus iGPU, operator approval, pool login present,
# ledger chain, live Stratum handshake) and refuses to mine if any check fails.
# Logs: ~/Library/Logs/HYBA-Mine/hyba-mine.log (rotated, 10 MB x 5).
set -uo pipefail

VENV="${HYBA_MINE_VENV:-$HOME/.hyba-mine/venv}"
export HYBA_MINE_LOG_DIR="${HYBA_MINE_LOG_DIR:-$HOME/Library/Logs/HYBA-Mine}"
mkdir -p "$HYBA_MINE_LOG_DIR"
HM="$VENV/bin/hyba-mine"
if [ ! -x "$HM" ]; then
  echo "HYBA Mine is not installed in $VENV; run: bash scripts/mine/setup_mac.sh" >&2
  exit 78
fi

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) run.sh: starting HYBA Mine (pre-flight, then mining)" >> "$HYBA_MINE_LOG_DIR/run.log"

# Keep the Mac awake while the miner runs (idle sleep always; system sleep on AC
# power). caffeinate watches this process id, which `exec` hands to the miner,
# so stop signals reach the miner directly and its exit status reaches launchd.
if [ -x /usr/bin/caffeinate ]; then
  /usr/bin/caffeinate -i -s -w $$ &
fi
exec "$HM" start "$@"
