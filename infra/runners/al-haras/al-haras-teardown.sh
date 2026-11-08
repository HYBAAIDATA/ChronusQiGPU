#!/usr/bin/env bash
# Runs as root after the ephemeral runner process exits.
set -euo pipefail

# Final workspace scrub (in case the post-job hook was bypassed) and removal
# of the runner registration so no stale runner entry lingers in GitHub.
rm -rf /opt/actions-runner/_work/* 2>/dev/null || true
rm -f /tmp/al_haras_pre_flight_receipt_* 2>/dev/null || true

if [[ -x /opt/actions-runner/config.sh ]]; then
  sudo -u github-runner /opt/actions-runner/config.sh remove --token "${RUNNER_REMOVE_TOKEN:-}" 2>/dev/null || true
fi

echo "[AL HARAS] teardown complete; systemd will re-register a fresh ephemeral runner"
