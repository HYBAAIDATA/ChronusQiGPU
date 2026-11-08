#!/usr/bin/env bash
# Runs as root (PermissionsStartOnly) before the unprivileged runner starts.
# Loads and pins the AL HARAS eBPF/LSM programs the pre-job hook verifies.
set -euo pipefail

BPF_FS="/sys/fs/bpf/al_haras"
PROG_SRC="/opt/al-haras/lsm"

mkdir -p "${BPF_FS}/progs"
mountpoint -q /sys/fs/bpf || mount -t bpf bpf /sys/fs/bpf

# Lock out unprivileged BPF before any job code can execute.
sysctl -w kernel.unprivileged_bpf_disabled=1

# Load and pin each compiled AL HARAS LSM program (built out-of-band and
# shipped in the runner image; never compiled on the runner itself).
for prog in "${PROG_SRC}"/*.o; do
  name="$(basename "${prog}" .o)"
  if [[ ! -e "${BPF_FS}/progs/${name}" ]]; then
    bpftool prog load "${prog}" "${BPF_FS}/progs/${name}" type lsm
  fi
done

echo "[AL HARAS] bootstrap complete: $(ls -A "${BPF_FS}/progs" | wc -l) LSM programs pinned"
