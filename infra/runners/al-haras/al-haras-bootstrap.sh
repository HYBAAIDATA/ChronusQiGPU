#!/usr/bin/env bash
# AL HARAS runner bootstrap. Runs once per runner cycle as `ExecStartPre=+` of
# chronus-sovereign-runner.service: as root, outside the unit's sandbox, before
# the runner registers. Any failure exits non-zero, so the unit does not start
# and no runner is registered.
#
#  1. Requires "bpf" in the kernel's active LSM list and sets
#     kernel.unprivileged_bpf_disabled=1 (the value cannot be cleared again
#     until reboot).
#  2. Checks every LSM object in /opt/al-haras/lsm against manifest.sha256.
#     The SHA-256 is computed over a private copy, and only that copy is loaded.
#  3. Loads and attaches each object with
#     `bpftool prog loadall <copy> <pin dir> autoattach` and requires every
#     pinned entry to be a bpf_link with attach type lsm_mac whose program type
#     is lsm. (When auto-attach is not possible, bpftool pins the unattached
#     program instead; such an entry is rejected because it enforces nothing.)
#  4. Replaces the contents of /opt/actions-runner with a copy of the
#     root-owned runner release in /opt/actions-runner-dist, so nothing a
#     previous job wrote into the runner directory reaches the next job.
#  5. Removes the links pinned by earlier invocations. This happens only after
#     steps 1-4 succeeded; on any failure the new links are removed instead.
#  6. Writes /run/al-haras/attestation (root:root 0644) for this systemd
#     INVOCATION_ID and boot_id, and prints it to the journal. The job-started
#     hook runs as github-runner, cannot read the root-only bpffs pins, and
#     verifies this file instead.
#
# Functions take their paths as arguments so tests can run them with stub
# tools (tests/test_al_haras_runner_scripts.py); main() passes the real paths.
set -euo pipefail

readonly RUNNER_USER=github-runner
readonly RUNNER_DIR=/opt/actions-runner
readonly RUNNER_DIST_DIR=/opt/actions-runner-dist
readonly LSM_DIR=/opt/al-haras/lsm
readonly MANIFEST=/opt/al-haras/lsm/manifest.sha256
readonly BPFFS=/sys/fs/bpf
readonly PIN_ROOT=/sys/fs/bpf/al_haras
readonly RUN_DIR=/run/al-haras
readonly ATTESTATION=/run/al-haras/attestation
readonly ATTESTATION_FORMAT=al-haras-attestation/1

MANIFEST_NAMES=()
MANIFEST_HASHES=()
LINK_RECORDS=()
STAGE_DIR=
NEW_PIN_DIR=
BOOTSTRAP_DONE=0

log() { printf '[AL HARAS bootstrap] %s\n' "$*"; }
die() { printf '[AL HARAS bootstrap] FATAL: %s\n' "$*" >&2; exit 1; }

# require_trusted PATH OWNER_UID
# PATH exists, is not a symlink, is owned by OWNER_UID and is not writable by
# group or others.
require_trusted() {
  local path=$1 owner=$2 meta mode
  [[ -e $path && ! -L $path ]] || die "${path}: missing or a symlink"
  meta=$(stat -c '%u %a' -- "$path") || die "${path}: stat failed"
  [[ ${meta%% *} == "$owner" ]] || die "${path}: owner uid ${meta%% *}, expected ${owner}"
  mode=${meta##* }
  (( (8#${mode} & 8#022) == 0 )) || die "${path}: mode ${mode} is group- or world-writable"
}

# read_manifest MANIFEST
# sha256sum format: "<64 lowercase hex> <space or *><name>.o" per line. Names
# are limited to [A-Za-z0-9_-] because bpffs rejects pin names containing dots.
read_manifest() {
  local manifest=$1 line n=0
  local re='^([0-9a-f]{64}) [ *]([A-Za-z0-9_-]+\.o)$'
  local -A seen=()
  MANIFEST_NAMES=()
  MANIFEST_HASHES=()
  while IFS= read -r line || [[ -n $line ]]; do
    n=$((n + 1))
    if [[ -z $line ]]; then
      continue
    fi
    [[ $line =~ $re ]] \
      || die "${manifest}:${n}: expected '<sha256>  <name>.o' (lowercase hex; name characters [A-Za-z0-9_-])"
    [[ -z ${seen[${BASH_REMATCH[2]}]:-} ]] || die "${manifest}:${n}: duplicate entry ${BASH_REMATCH[2]}"
    seen[${BASH_REMATCH[2]}]=1
    MANIFEST_HASHES+=("${BASH_REMATCH[1]}")
    MANIFEST_NAMES+=("${BASH_REMATCH[2]}")
  done < "$manifest"
  (( ${#MANIFEST_NAMES[@]} > 0 )) || die "${manifest}: no entries"
}

# stage_and_verify_objects LSM_DIR STAGE_DIR OWNER_UID
# Every *.o in LSM_DIR must be listed in the manifest. Each listed object must
# be a trusted regular file; it is copied into STAGE_DIR and the copy's SHA-256
# must equal the manifest entry.
stage_and_verify_objects() {
  local lsm_dir=$1 stage=$2 owner=$3 i name src actual
  local -A listed=()
  for name in "${MANIFEST_NAMES[@]}"; do
    listed[$name]=1
  done
  for src in "$lsm_dir"/*.o; do
    if [[ ! -e $src && ! -L $src ]]; then
      continue
    fi
    [[ -n ${listed[${src##*/}]:-} ]] || die "${src}: not listed in the manifest"
  done
  for i in "${!MANIFEST_NAMES[@]}"; do
    name=${MANIFEST_NAMES[$i]}
    src=${lsm_dir}/${name}
    require_trusted "$src" "$owner"
    [[ -f $src ]] || die "${src}: not a regular file"
    cp -- "$src" "${stage}/${name}" || die "${src}: copy failed"
    actual=$(sha256sum -- "${stage}/${name}") || die "${name}: sha256sum failed"
    actual=${actual%% *}
    [[ $actual == "${MANIFEST_HASHES[$i]}" ]] \
      || die "${name}: SHA-256 ${actual} does not match the manifest entry ${MANIFEST_HASHES[$i]}"
    log "verified ${name} sha256=${actual}"
  done
}

# json_uint JSON KEY / json_str JSON KEY
# Value of the first "KEY" member of a single-object `bpftool -j` output.
json_uint() {
  local re="\"$2\":[[:space:]]*([0-9]+)"
  [[ $1 =~ $re ]] || return 1
  printf '%s\n' "${BASH_REMATCH[1]}"
}
json_str() {
  local re="\"$2\":[[:space:]]*\"([^\"]*)\""
  [[ $1 =~ $re ]] || return 1
  printf '%s\n' "${BASH_REMATCH[1]}"
}

# load_and_collect STAGE_DIR PIN_DIR
# Loads and auto-attaches every program of every verified object and records
# one LINK_RECORDS entry per pinned link:
#   "<object> <program> <link_id> <prog_id> <prog_tag> lsm_mac"
load_and_collect() {
  local stage=$1 pin_dir=$2 name obj_pin entry prog json link_id prog_id attach prog_type tag count
  LINK_RECORDS=()
  mkdir -p -- "$pin_dir" || die "${pin_dir}: mkdir failed"
  for name in "${MANIFEST_NAMES[@]}"; do
    obj_pin=${pin_dir}/${name%.o}
    bpftool prog loadall "${stage}/${name}" "$obj_pin" autoattach \
      || die "${name}: bpftool prog loadall ... autoattach failed"
    count=0
    for entry in "$obj_pin"/*; do
      if [[ ! -e $entry ]]; then
        continue
      fi
      prog=${entry##*/}
      [[ $prog =~ ^[A-Za-z0-9_]+$ ]] || die "${name}: unexpected pin name ${prog}"
      json=$(bpftool -j link show pinned "$entry" 2>&1) \
        || die "${name}/${prog}: pinned object is not an attached link (unattached program?): ${json}"
      link_id=$(json_uint "$json" id) || die "${name}/${prog}: no link id in: ${json}"
      prog_id=$(json_uint "$json" prog_id) || die "${name}/${prog}: no prog_id in: ${json}"
      attach=$(json_str "$json" attach_type) || die "${name}/${prog}: no attach_type in: ${json}"
      [[ $attach == lsm_mac ]] || die "${name}/${prog}: attach type ${attach}, expected lsm_mac"
      json=$(bpftool -j prog show id "$prog_id" 2>&1) \
        || die "${name}/${prog}: bpftool prog show id ${prog_id} failed: ${json}"
      prog_type=$(json_str "$json" type) || die "${name}/${prog}: no program type in: ${json}"
      [[ $prog_type == lsm ]] || die "${name}/${prog}: program type ${prog_type}, expected lsm"
      tag=$(json_str "$json" tag) || die "${name}/${prog}: no program tag in: ${json}"
      [[ $tag =~ ^[0-9a-f]{16}$ ]] || die "${name}/${prog}: malformed program tag ${tag}"
      LINK_RECORDS+=("${name} ${prog} ${link_id} ${prog_id} ${tag} ${attach}")
      count=$((count + 1))
      log "attached ${name}/${prog}: link ${link_id}, prog ${prog_id}, tag ${tag}"
    done
    (( count > 0 )) || die "${name}: bpftool pinned nothing under ${obj_pin}"
  done
}

# remove_stale_pins PIN_ROOT KEEP
# Unpins (and thereby detaches) the links of earlier invocations.
remove_stale_pins() {
  local root=$1 keep=$2 dir
  for dir in "$root"/*; do
    if [[ ! -e $dir || ${dir##*/} == "$keep" ]]; then
      continue
    fi
    rm -rf -- "$dir" || die "${dir}: could not remove earlier pins"
    log "removed earlier pins ${dir}"
  done
}

# refresh_runner_tree DIST DEST USER OWNER_UID
# Empties DEST (without crossing mount points) and copies DIST into it. Every
# non-symlink entry of DIST must be owned by OWNER_UID and not group- or
# world-writable.
refresh_runner_tree() {
  local dist=$1 dest=$2 user=$3 owner=$4 bad
  [[ $dest == /?* && $dest != "$dist" ]] || die "refusing to refresh ${dest}"
  require_trusted "$dist" "$owner"
  [[ -x ${dist}/run.sh && -x ${dist}/config.sh ]] || die "${dist}: no unpacked actions runner (run.sh, config.sh)"
  bad=$(find "$dist" \( ! -uid "$owner" -o -perm /022 \) ! -type l -print -quit) || die "${dist}: find failed"
  [[ -z $bad ]] || die "${dist}: ${bad} is not owned by uid ${owner} or is group/world-writable"
  [[ -d $dest && ! -L $dest ]] || die "${dest}: missing or a symlink (create it as shown in the README)"
  find "$dest" -xdev -mindepth 1 -delete || die "${dest}: could not be emptied (mount point inside?)"
  cp -a --reflink=auto -- "${dist}/." "${dest}/" || die "copying ${dist} to ${dest} failed"
  chown -R -- "${user}:${user}" "$dest" || die "chown ${dest} failed"
  log "runner directory ${dest} replaced with a copy of ${dist}"
}

# write_attestation PATH INVOCATION_ID BOOT_ID KERNEL_RELEASE LSM_LIST
#                   UNPRIVILEGED_BPF_DISABLED BPFTOOL_VERSION MANIFEST PIN_DIR
# One key=value per line; "object" and "link" repeat. Written to PATH.new and
# renamed, so readers see either no file or a complete one.
write_attestation() {
  local path=$1 invocation=$2 boot=$3 kernel=$4 lsm=$5 unpriv=$6 bpftool_version=$7 manifest=$8 pin_dir=$9
  local tmp=${1}.new manifest_sha i record
  manifest_sha=$(sha256sum < "$manifest") || die "${manifest}: sha256sum failed"
  manifest_sha=${manifest_sha%% *}
  bpftool_version=${bpftool_version//[[:cntrl:]]/}
  {
    printf 'format=%s\n' "$ATTESTATION_FORMAT"
    printf 'invocation_id=%s\n' "$invocation"
    printf 'boot_id=%s\n' "$boot"
    printf 'kernel_release=%s\n' "$kernel"
    printf 'generated_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'lsm=%s\n' "$lsm"
    printf 'unprivileged_bpf_disabled=%s\n' "$unpriv"
    printf 'bpftool=%s\n' "${bpftool_version:-unknown}"
    printf 'manifest=%s\n' "$manifest"
    printf 'manifest_sha256=%s\n' "$manifest_sha"
    printf 'pin_dir=%s\n' "$pin_dir"
    for i in "${!MANIFEST_NAMES[@]}"; do
      printf 'object=%s %s\n' "${MANIFEST_NAMES[$i]}" "${MANIFEST_HASHES[$i]}"
    done
    for record in "${LINK_RECORDS[@]}"; do
      printf 'link=%s\n' "$record"
    done
  } > "$tmp" || die "${tmp}: write failed"
  chmod 0644 -- "$tmp"
  mv -f -- "$tmp" "$path" || die "${path}: rename failed"
}

cleanup() {
  if [[ -n $STAGE_DIR ]]; then
    rm -rf -- "$STAGE_DIR"
  fi
  if [[ $BOOTSTRAP_DONE != 1 && -n $NEW_PIN_DIR ]]; then
    rm -rf -- "$NEW_PIN_DIR"
  fi
}

main() {
  local invocation=${INVOCATION_ID:-} lsm unpriv boot kernel bpftool_help bpftool_version
  umask 022
  export LC_ALL=C
  PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

  [[ $EUID -eq 0 ]] || die "must run as root (ExecStartPre=+ in chronus-sovereign-runner.service)"
  [[ $invocation =~ ^[0-9a-f]{32}$ ]] || die "INVOCATION_ID is missing or malformed; start this through systemd"
  getent passwd "$RUNNER_USER" > /dev/null || die "user ${RUNNER_USER} does not exist"

  install -d -o root -g root -m 0755 -- "$RUN_DIR"
  rm -f -- "$ATTESTATION" "${ATTESTATION}.new"

  # $(cat ...) rather than $(< ...): under set -e a failed $(< file) exits
  # before the "|| die" handler can report which file was missing.
  lsm=$(cat -- /sys/kernel/security/lsm 2> /dev/null) || die "cannot read /sys/kernel/security/lsm (securityfs not mounted?)"
  [[ ",${lsm}," == *,bpf,* ]] || die "BPF LSM is not active (lsm=${lsm}); boot with bpf in the lsm= list"

  printf '1\n' > /proc/sys/kernel/unprivileged_bpf_disabled || die "cannot set kernel.unprivileged_bpf_disabled=1"
  unpriv=$(cat -- /proc/sys/kernel/unprivileged_bpf_disabled 2> /dev/null) || die "cannot read kernel.unprivileged_bpf_disabled"
  [[ $unpriv == 1 ]] || die "kernel.unprivileged_bpf_disabled reads ${unpriv} after writing 1"

  if ! mountpoint -q "$BPFFS"; then
    mount -t bpf -o mode=0700 bpf "$BPFFS" || die "cannot mount bpffs on ${BPFFS}"
  fi
  [[ $(stat -f -c %T "$BPFFS") == bpf_fs ]] || die "${BPFFS} is not a bpf filesystem"

  command -v bpftool > /dev/null || die "bpftool not found"
  bpftool_help=$(bpftool prog help 2>&1 || true)
  [[ $bpftool_help == *autoattach* ]] \
    || die "this bpftool has no 'autoattach' option; it could pin but not attach the LSM programs"
  bpftool_version=$(bpftool version 2> /dev/null || true)
  bpftool_version=${bpftool_version%%$'\n'*}

  require_trusted "$LSM_DIR" 0
  require_trusted "$MANIFEST" 0
  read_manifest "$MANIFEST"

  STAGE_DIR=${RUN_DIR}/stage
  NEW_PIN_DIR=${PIN_ROOT}/${invocation}
  trap cleanup EXIT
  rm -rf -- "$STAGE_DIR"
  install -d -o root -g root -m 0700 -- "$STAGE_DIR"
  stage_and_verify_objects "$LSM_DIR" "$STAGE_DIR" 0

  mkdir -p -m 0700 -- "$PIN_ROOT"
  rm -rf -- "$NEW_PIN_DIR"
  load_and_collect "$STAGE_DIR" "$NEW_PIN_DIR"

  refresh_runner_tree "$RUNNER_DIST_DIR" "$RUNNER_DIR" "$RUNNER_USER" 0

  # Only now drop the previous invocation's links: if anything above failed,
  # the cleanup trap removed the new links and the previous ones stay attached.
  remove_stale_pins "$PIN_ROOT" "$invocation"

  boot=$(cat -- /proc/sys/kernel/random/boot_id 2> /dev/null) || die "cannot read the boot_id"
  kernel=$(uname -r)
  write_attestation "$ATTESTATION" "$invocation" "$boot" "$kernel" "$lsm" "$unpriv" \
    "$bpftool_version" "$MANIFEST" "$NEW_PIN_DIR"
  BOOTSTRAP_DONE=1
  log "${#MANIFEST_NAMES[@]} object(s) verified, ${#LINK_RECORDS[@]} LSM link(s) attached; ${ATTESTATION}:"
  cat -- "$ATTESTATION"
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  main "$@"
fi
