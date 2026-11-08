#!/usr/bin/env bash
set -euo pipefail

echo "::group::[AL HARAS] Post-Job Scrub"

# Preserve the pre-flight receipt for the job's attestation step, then scrub
# everything else the job left behind in writable paths.
WORK_DIR="${GITHUB_WORKSPACE:-/opt/actions-runner/_work}"
if [[ -d "${WORK_DIR}" ]]; then
  find "${WORK_DIR}" -mindepth 1 -maxdepth 1 -not -name '_temp' -exec rm -rf {} + 2>/dev/null || true
fi

# Scrub world-writable temp residue except AL HARAS receipts (attested in-job).
find /tmp -mindepth 1 -maxdepth 1 \
  -not -name 'al_haras_pre_flight_receipt_*' \
  -user github-runner -exec rm -rf {} + 2>/dev/null || true

sync
echo "[AL HARAS] Post-job scrub complete."
echo "::endgroup::"
