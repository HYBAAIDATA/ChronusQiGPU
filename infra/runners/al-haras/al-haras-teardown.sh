#!/usr/bin/env bash
# AL HARAS runner teardown. Runs as `ExecStopPost=+` of
# chronus-sovereign-runner.service: as root, after the runner exited and
# systemd stopped every process left in the unit's cgroup. It also runs when
# the start failed. Each step runs even if an earlier one failed; the exit
# status is non-zero if any step failed.
#
#  1. Compares the LSM links recorded in /run/al-haras/attestation with the
#     kernel's current links (`bpftool -j link show id`) and logs the result to
#     the journal. This detects a link that was detached or replaced while the
#     job ran; it cannot prevent it.
#  2. Copies the runner's diagnostic logs (_diag/*.log, regular files under
#     64 MiB) to /var/log/al-haras/runner-diag/<INVOCATION_ID>/ (root-only)
#     and deletes copies older than AL_HARAS_DIAG_RETENTION_DAYS (default 14).
#  3. Deletes the contents of _work and the local registration files
#     (.runner, .credentials, .credentials_rsaparams). It does not call
#     `config.sh remove`; see the README section "Deregistration".
#  4. Deletes the attestation; the next invocation writes a new one.
# al-haras-bootstrap.sh replaces the whole runner directory before the next
# job, so this script only shortens how long job data stays on disk.
set -euo pipefail

readonly RUNNER_DIR=/opt/actions-runner
readonly ATTESTATION=/run/al-haras/attestation
readonly DIAG_ARCHIVE_ROOT=/var/log/al-haras/runner-diag
readonly DEFAULT_DIAG_RETENTION_DAYS=14

log() { printf '[AL HARAS teardown] %s\n' "$*"; }
warn() { printf '[AL HARAS teardown] WARNING: %s\n' "$*" >&2; }

json_uint() {
  local re="\"$2\":[[:space:]]*([0-9]+)"
  [[ $1 =~ $re ]] || return 1
  printf '%s\n' "${BASH_REMATCH[1]}"
}

# check_links ATTESTATION INVOCATION_ID
# 0 if every recorded link still exists with the recorded program id, or if
# there is no attestation (the bootstrap did not finish). 1 if a link changed
# or disappeared, or if the attestation belongs to another invocation.
check_links() {
  local file=$1 invocation=$2 line recorded= checked=0 changed=0
  local object prog link_id prog_id tag attach json live_prog
  if [[ ! -f $file ]]; then
    log "no attestation at ${file}; nothing to compare (the bootstrap did not finish)"
    return 0
  fi
  while IFS= read -r line || [[ -n $line ]]; do
    if [[ $line == invocation_id=* ]]; then
      recorded=${line#invocation_id=}
    fi
  done < "$file"
  if [[ $recorded != "$invocation" ]]; then
    warn "${file} belongs to invocation ${recorded:-<none>}, this is ${invocation}; links not compared"
    return 1
  fi
  while IFS= read -r line || [[ -n $line ]]; do
    if [[ $line != link=* ]]; then
      continue
    fi
    read -r object prog link_id prog_id tag attach <<< "${line#link=}"
    checked=$((checked + 1))
    if json=$(bpftool -j link show id "$link_id" 2>&1) \
      && live_prog=$(json_uint "$json" prog_id) && [[ $live_prog == "$prog_id" ]]; then
      log "link ${link_id} (${object}/${prog}, prog ${prog_id}, tag ${tag}) still attached"
    else
      warn "link ${link_id} (${object}/${prog}, prog ${prog_id}) is gone or now runs another program: ${json:-no output}"
      changed=$((changed + 1))
    fi
  done < "$file"
  log "${checked} recorded LSM link(s) compared with the kernel, ${changed} gone or changed"
  (( changed == 0 ))
}

# archive_diag DIAG_DIR ARCHIVE_ROOT INVOCATION_ID RETENTION_DAYS
archive_diag() {
  local diag=$1 root=$2 invocation=$3 days=$4 dest copied=0 failed=0 file
  if [[ ! $days =~ ^[0-9]+$ ]]; then
    warn "AL_HARAS_DIAG_RETENTION_DAYS='${days}' is not a whole number of days; using ${DEFAULT_DIAG_RETENTION_DAYS}"
    days=$DEFAULT_DIAG_RETENTION_DAYS
  fi
  mkdir -p -m 0700 -- "$root" || return 1
  if [[ -d $diag && ! -L $diag ]]; then
    dest=${root}/${invocation}
    mkdir -p -m 0700 -- "$dest" || return 1
    while IFS= read -r -d '' file; do
      if cp --preserve=timestamps -- "$file" "${dest}/"; then
        copied=$((copied + 1))
      else
        failed=$((failed + 1))
      fi
    done < <(find "$diag" -maxdepth 1 -type f -name '*.log' -size -64M -print0)
    log "copied ${copied} runner diagnostic log(s) to ${dest}"
  fi
  find "$root" -mindepth 1 -maxdepth 1 -type d -mtime "+${days}" -exec rm -rf -- {} + || failed=$((failed + 1))
  log "deleted diagnostic log copies older than ${days} day(s) under ${root}"
  (( failed == 0 ))
}

# scrub_runner_tree RUNNER_DIR
scrub_runner_tree() {
  local dir=$1 failed=0
  if [[ -d ${dir}/_work && ! -L ${dir}/_work ]]; then
    find "${dir}/_work" -xdev -mindepth 1 -delete || failed=1
  fi
  rm -f -- "${dir}/.runner" "${dir}/.credentials" "${dir}/.credentials_rsaparams" || failed=1
  log "deleted the contents of ${dir}/_work and the local registration files"
  (( failed == 0 ))
}

main() {
  local invocation=${INVOCATION_ID:-} status=0
  umask 077
  export LC_ALL=C
  PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

  if [[ ! $invocation =~ ^[0-9a-f]{32}$ ]]; then
    warn "INVOCATION_ID is missing or malformed"
    invocation=unknown-$(date +%s)
    status=1
  fi
  check_links "$ATTESTATION" "$invocation" || status=1
  archive_diag "${RUNNER_DIR}/_diag" "$DIAG_ARCHIVE_ROOT" "$invocation" \
    "${AL_HARAS_DIAG_RETENTION_DAYS:-$DEFAULT_DIAG_RETENTION_DAYS}" || { warn "archiving diagnostic logs failed"; status=1; }
  scrub_runner_tree "$RUNNER_DIR" || { warn "scrubbing ${RUNNER_DIR} failed"; status=1; }
  rm -f -- "$ATTESTATION" || status=1
  log "finished with status ${status}; Restart=always starts the next runner cycle"
  exit "$status"
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  main "$@"
fi
