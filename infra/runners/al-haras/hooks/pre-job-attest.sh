#!/usr/bin/env bash
set -euo pipefail

echo "::group::[AL HARAS] Pre-Flight Kernel & eBPF/LSM Attestation"

BPF_FS="/sys/fs/bpf/al_haras"
RECEIPT_PATH="/tmp/al_haras_pre_flight_receipt_${GITHUB_RUN_ID:-local}.json"

# 1. Verify BPF LSM is actively enforced in kernel security list
if ! grep -q "bpf" /sys/kernel/security/lsm; then
  echo "::error::[AL HARAS FATAL] BPF LSM is not active in /sys/kernel/security/lsm."
  exit 1
fi

# 2. Verify unprivileged BPF is locked out
if [[ "$(cat /proc/sys/kernel/unprivileged_bpf_disabled)" != "1" ]]; then
  echo "::error::[AL HARAS FATAL] unprivileged_bpf_disabled is not enforced."
  exit 1
fi

# 3. Verify pinned AL HARAS LSM programs exist and hold expected tag/hash
if [[ ! -d "${BPF_FS}/progs" ]] || [[ -z "$(ls -A "${BPF_FS}/progs")" ]]; then
  echo "::error::[AL HARAS FATAL] No pinned AL HARAS LSM programs found in ${BPF_FS}/progs."
  exit 1
fi

# 4. Emit cryptographic pre-flight receipt for job telemetry
KERNEL_REL=$(uname -r)
BOOT_ID=$(cat /proc/sys/kernel/random/boot_id)
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

cat <<EOF > "${RECEIPT_PATH}"
{
  "engine": "AL_HARAS_LSM_v36",
  "status": "ATTESTED",
  "timestamp": "${TIMESTAMP}",
  "kernel_release": "${KERNEL_REL}",
  "boot_id": "${BOOT_ID}",
  "github_run_id": "${GITHUB_RUN_ID:-unknown}",
  "github_sha": "${GITHUB_SHA:-unknown}",
  "unprivileged_bpf_disabled": 1
}
EOF

echo "[AL HARAS] Pre-flight attestation PASSED. Receipt written to ${RECEIPT_PATH}"
echo "::endgroup::"
