#!/usr/bin/env bash
# EUCLID-CORE / PYTHIA — unified container entrypoint.
#
# One `docker compose up` starts the full pipeline:
#   1. node dist/server.cjs — primary process: HTTP API, stratum socket,
#      mining runtime (tensor → iGPU → advisor → SHA-256d), compute fabric.
#      It spawns the Python algebraic advisor sidecar on :3001 itself.
#   2. python3 main.py      — Intelligence stack: Agentic Mining, Salamander
#      self-healing loop (30s cycle), TOE, Aethel substrate. Supervised with
#      restart-on-exit: process-level Salamander supervision.
#
# Node exiting stops the container (compose restart policy owns the outer
# loop). Python exiting only restarts the Python co-process — the mining
# path degrades gracefully (advisor fallback = sequential scheduling),
# matching the fail-degraded architecture.
#
# Env:
#   EUCLID_PYTHON_STACK=true|false    run the Python Intelligence co-process (default true)
#   EUCLID_PYTHON_RESTART_DELAY_S=N   delay between Python restarts (default 5)
#   PYTHON_BIN=python3                interpreter override
set -u

PY_STACK="${EUCLID_PYTHON_STACK:-true}"
PY_BIN="${PYTHON_BIN:-python3}"
PY_DELAY="${EUCLID_PYTHON_RESTART_DELAY_S:-5}"
PY_SUPERVISOR_PID=""
NODE_PID=""

if [ "$PY_STACK" = "true" ]; then
  (
    while true; do
      echo "[entrypoint] starting Intelligence stack ($PY_BIN main.py)"
      "$PY_BIN" main.py
      rc=$?
      echo "[entrypoint] Intelligence stack exited (rc=$rc) — restarting in ${PY_DELAY}s"
      sleep "$PY_DELAY"
    done
  ) &
  PY_SUPERVISOR_PID=$!
fi

node dist/server.cjs &
NODE_PID=$!

shutdown() {
  echo "[entrypoint] shutdown requested"
  [ -n "$PY_SUPERVISOR_PID" ] && kill "$PY_SUPERVISOR_PID" 2>/dev/null
  [ -n "$NODE_PID" ] && kill "$NODE_PID" 2>/dev/null
  exit 0
}
trap shutdown TERM INT

# Node is the primary process: its exit code becomes the container's.
wait "$NODE_PID"
exit $?
