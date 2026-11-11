#!/usr/bin/env bash
# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
#
# HYBA Mine: one-command setup for a new Mac (Apple Silicon).
# HYBA Mine is HYBA's internal treasury mining runtime; it is not a product.
#
#   bash scripts/mine/setup_mac.sh [--pool viabtc|braiins|nicehash|ckpool] [--no-autostart] [--no-start]
#
# What it does, in order:
#   1. checks for Homebrew (offers the official installer if it is missing);
#   2. installs python@3.12 with Homebrew;
#   3. creates ~/.hyba-mine/venv and installs Chronus (hyba-chronus), HYBA Mine
#      (hyba-mine) and the Metal bindings (pyobjc-framework-Metal);
#   4. asks for the pool and stores the pool login in the macOS Keychain
#      (typed here, never written to the repository or the logs);
#   5. asks for the operator approval to mine on this Mac;
#   6. runs the pre-flight (known-answer tests on real Bitcoin headers on the
#      Chronus iGPU, login present, live Stratum handshake);
#   7. starts mining: as a launchd agent (auto-start at login) or in this window.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATE_ROOT="$HOME/.hyba-mine"
VENV="${HYBA_MINE_VENV:-$STATE_ROOT/venv}"
BIN="$STATE_ROOT/bin"
LOG_DIR="${HYBA_MINE_LOG_DIR:-$HOME/Library/Logs/HYBA-Mine}"
POOL=""
AUTOSTART="ask"
START="yes"

while [ $# -gt 0 ]; do
  case "$1" in
    --pool) POOL="${2:-}"; shift 2 ;;
    --no-autostart) AUTOSTART="no"; shift ;;
    --autostart) AUTOSTART="yes"; shift ;;
    --no-start) START="no"; shift ;;
    -h|--help) sed -n '2,21p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 64 ;;
  esac
done

say() { printf '\n==> %s\n' "$*"; }
die() { printf '\nHYBA Mine setup stopped: %s\n' "$*" >&2; exit 1; }
ask_yes() {  # ask_yes "question" default(Y|N)
  local answer
  read -r -p "$1 " answer || true
  answer="${answer:-$2}"
  [[ "$answer" =~ ^[Yy] ]]
}

[ "$(uname -s)" = "Darwin" ] || die "this setup script is for macOS"
[ -f "$REPO/pyproject.toml" ] && [ -d "$REPO/packages/hyba_mine" ] || die "run it from a Chronusv2 checkout (scripts/mine/setup_mac.sh)"
if [ "$(uname -m)" != "arm64" ]; then
  say "This Mac reports $(uname -m), not Apple Silicon. Setup continues; the self-test decides which Chronus iGPU lane runs."
fi

say "1/7 Homebrew"
BREW=""
for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew; do
  [ -x "$candidate" ] && { BREW="$candidate"; break; }
done
if [ -z "$BREW" ]; then
  echo "Homebrew is not installed. The official installer is:"
  echo '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
  if ask_yes "Run it now (it asks for your Mac password)? [y/N]" N; then
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  else
    die "install Homebrew, then run this script again"
  fi
  for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    [ -x "$candidate" ] && { BREW="$candidate"; break; }
  done
  [ -n "$BREW" ] || die "Homebrew was not found after the installer finished"
fi
eval "$("$BREW" shellenv)"
echo "Homebrew: $BREW"

say "2/7 Python 3.12"
"$BREW" list --versions python@3.12 >/dev/null 2>&1 || "$BREW" install python@3.12
PY="$("$BREW" --prefix python@3.12)/bin/python3.12"
[ -x "$PY" ] || die "python3.12 not found at $PY"
"$PY" --version

say "3/7 Virtual environment and packages ($VENV)"
mkdir -p "$STATE_ROOT" "$BIN" "$LOG_DIR"
chmod 700 "$STATE_ROOT"
[ -x "$VENV/bin/python" ] || "$PY" -m venv "$VENV"
"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install --quiet -e "$REPO"
"$VENV/bin/python" -m pip install --quiet --no-deps -e "$REPO/packages/hyba_mine"
"$VENV/bin/python" -m pip install --quiet "pyobjc-framework-Metal>=10.3"
ln -sf "$VENV/bin/hyba-mine" "$BIN/hyba-mine"
HM="$VENV/bin/hyba-mine"
"$HM" --version

say "4/7 Pool and pool login (stored in the macOS Keychain)"
if [ -z "$POOL" ]; then
  echo "HYBA Mine mines only on: viabtc, braiins, nicehash, ckpool"
  read -r -p "Pool for this Mac [viabtc]: " POOL || true
  POOL="${POOL:-viabtc}"
fi
case "$POOL" in viabtc|braiins|nicehash|ckpool) ;; *) die "unknown pool '$POOL'";; esac
"$HM" pools | awk -v p="$POOL" '$1 == p {show=1; print; next} /^[a-z]/ {show=0} show'
echo "Use a different worker name on each Mac (for example .macbook and .imac)."
"$HM" login "$POOL" --store keychain
"$HM" pool use "$POOL" >/dev/null

say "5/7 Operator approval"
"$HM" approve

say "6/7 Pre-flight (self-test on real Bitcoin headers, login, live pool handshake)"
if ! "$HM" preflight --pool "$POOL"; then
  echo
  echo "Pre-flight failed; mining is blocked. The lines marked FAIL above say why."
  if ask_yes "If only the Metal lane failed, mine on the Chronus iGPU (our software-defined GPU) instead? [y/N]" N; then
    "$HM" preflight --pool "$POOL" --backend igpu || die "the Chronus iGPU pre-flight failed too; see the FAIL lines above"
    "$HM" config --backend igpu --prefer ours >/dev/null
  else
    die "fix the FAIL lines and run: $BIN/hyba-mine preflight"
  fi
fi

say "7/7 Start mining"
if [ "$AUTOSTART" = "ask" ]; then
  if ask_yes "Start HYBA Mine automatically at login and run it in the background now? [Y/n]" Y; then
    AUTOSTART="yes"
  else
    AUTOSTART="no"
  fi
fi
if [ "$AUTOSTART" = "yes" ]; then
  "$HM" autostart enable --run-script "$REPO/scripts/mine/run.sh"
  echo
  echo "HYBA Mine is running in the background (launchd agent ae.hybadata.mine)."
  echo "  Status:       $BIN/hyba-mine status      or open http://127.0.0.1:8765/"
  echo "  Switch pool:  $BIN/hyba-mine pool use <viabtc|braiins|nicehash|ckpool>"
  echo "  Stop:         $BIN/hyba-mine stop        (add --disable-autostart to remove the agent)"
  echo "  Logs:         $LOG_DIR"
elif [ "$START" = "yes" ]; then
  echo "Mining in this window. Status page: http://127.0.0.1:8765/  Stop: Ctrl-C (or hyba-mine stop)."
  exec /bin/bash "$REPO/scripts/mine/run.sh"
else
  echo "Setup complete. Start with: bash $REPO/scripts/mine/run.sh"
fi
