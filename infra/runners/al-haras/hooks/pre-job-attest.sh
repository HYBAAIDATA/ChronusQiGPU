#!/usr/bin/env bash
# AL HARAS job-started hook (ACTIONS_RUNNER_HOOK_JOB_STARTED). The runner runs
# it as github-runner, inside the unit's sandbox, after a job is assigned and
# before the job's first step ("Set up runner" in the job log). A non-zero exit
# makes GitHub mark the job failed without running its steps.
#
# github-runner cannot read the root-only bpffs pins, and with unprivileged BPF
# disabled it cannot query the kernel for programs. It therefore checks:
#  - live: "bpf" is in /sys/kernel/security/lsm and
#    kernel.unprivileged_bpf_disabled is 1;
#  - /run/al-haras/attestation, written by al-haras-bootstrap.sh, is a regular
#    root-owned file that is not group/world-writable (in such a directory) and
#    was written for this systemd invocation (INVOCATION_ID), this boot
#    (boot_id) and this kernel release;
#  - the attestation records the SHA-256 of the root-owned manifest
#    /opt/al-haras/lsm/manifest.sha256, lists exactly the manifest's objects
#    with the same SHA-256 values, and records at least one attached lsm_mac
#    link for every object.
# It then writes an unsigned JSON receipt containing the SHA-256 of the
# attestation, of the manifest and of every object to
# /opt/actions-runner/_work/_al_haras/pre-flight-receipt.json. Signing is up to
# the job; see the README section "Using the sovereign pool from a workflow".
#
# Functions take their inputs as arguments so tests can run them on fixture
# files (tests/test_al_haras_runner_scripts.py); main() reads the live values.
set -euo pipefail

readonly ATTESTATION=/run/al-haras/attestation
readonly ATTESTATION_FORMAT=al-haras-attestation/1
readonly MANIFEST=/opt/al-haras/lsm/manifest.sha256
readonly RECEIPT=/opt/actions-runner/_work/_al_haras/pre-flight-receipt.json
readonly RECEIPT_SCHEMA=al-haras-pre-flight-receipt/1
readonly ATTESTATION_KEYS="format invocation_id boot_id kernel_release generated_at lsm unprivileged_bpf_disabled bpftool manifest manifest_sha256 pin_dir"

declare -A ATT=()
declare -A ATT_OBJECTS=()
ATT_LINKS=()
MANIFEST_NAMES=()
MANIFEST_HASHES=()
VERIFIED_ATTESTATION=
ATTESTATION_SHA256=
MANIFEST_SHA256=
OBSERVED_OWNER=
OBSERVED_MODE=
OBSERVED_INVOCATION=
OBSERVED_BOOT=
OBSERVED_KERNEL=
OBSERVED_LSM=
OBSERVED_UNPRIV=

die() { printf '::error::[AL HARAS pre-job] %s\n' "$*"; exit 1; }

# trusted_path PATH OWNER_UID
# PATH exists, is not a symlink, is owned by OWNER_UID and is not writable by
# group or others. Leaves the observed owner and mode in OBSERVED_OWNER/MODE.
trusted_path() {
  local path=$1 owner=$2 meta mode
  [[ -e $path && ! -L $path ]] || die "${path}: missing or a symlink"
  meta=$(stat -c '%u %a' -- "$path") || die "${path}: stat failed"
  [[ ${meta%% *} == "$owner" ]] || die "${path}: owner uid ${meta%% *}, expected ${owner}"
  mode=${meta##* }
  (( (8#${mode} & 8#022) == 0 )) || die "${path}: mode ${mode} is group- or world-writable"
  OBSERVED_OWNER=${meta%% *}
  OBSERVED_MODE=$mode
}

# read_manifest MANIFEST (same format and rules as al-haras-bootstrap.sh)
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
    [[ $line =~ $re ]] || die "${manifest}:${n}: malformed manifest line"
    [[ -z ${seen[${BASH_REMATCH[2]}]:-} ]] || die "${manifest}:${n}: duplicate entry ${BASH_REMATCH[2]}"
    seen[${BASH_REMATCH[2]}]=1
    MANIFEST_HASHES+=("${BASH_REMATCH[1]}")
    MANIFEST_NAMES+=("${BASH_REMATCH[2]}")
  done < "$manifest"
  (( ${#MANIFEST_NAMES[@]} > 0 )) || die "${manifest}: no entries"
}

# parse_attestation FILE -> ATT, ATT_OBJECTS, ATT_LINKS
parse_attestation() {
  local file=$1 line n=0 key value name
  local object_re='^([A-Za-z0-9_-]+\.o) ([0-9a-f]{64})$'
  local link_re='^([A-Za-z0-9_-]+\.o) ([A-Za-z0-9_]+) (0|[1-9][0-9]*) (0|[1-9][0-9]*) ([0-9a-f]{16}) ([a-z_]+)$'
  local -A seen_links=()
  ATT=()
  ATT_OBJECTS=()
  ATT_LINKS=()
  while IFS= read -r line || [[ -n $line ]]; do
    n=$((n + 1))
    [[ $line == *=* ]] || die "${file}:${n}: not a key=value line"
    key=${line%%=*}
    value=${line#*=}
    case $key in
      object)
        [[ $value =~ $object_re ]] || die "${file}:${n}: malformed object record"
        name=${BASH_REMATCH[1]}
        [[ -z ${ATT_OBJECTS[$name]:-} ]] || die "${file}:${n}: duplicate object ${name}"
        ATT_OBJECTS[$name]=${BASH_REMATCH[2]}
        ;;
      link)
        [[ $value =~ $link_re ]] || die "${file}:${n}: malformed link record"
        [[ -z ${seen_links[${BASH_REMATCH[3]}]:-} ]] || die "${file}:${n}: duplicate link id ${BASH_REMATCH[3]}"
        seen_links[${BASH_REMATCH[3]}]=1
        ATT_LINKS+=("$value")
        ;;
      *)
        [[ " ${ATTESTATION_KEYS} " == *" ${key} "* ]] || die "${file}:${n}: unknown key '${key}'"
        [[ -z ${ATT[$key]+set} ]] || die "${file}:${n}: duplicate key ${key}"
        ATT[$key]=$value
        ;;
    esac
  done < "$file"
  for key in $ATTESTATION_KEYS; do
    [[ -n ${ATT[$key]:-} ]] || die "${file}: missing ${key}"
  done
}

# verify_attestation ATTESTATION MANIFEST OWNER_UID INVOCATION_ID BOOT_ID
#                    KERNEL_RELEASE LIVE_LSM_LIST LIVE_UNPRIVILEGED_BPF_DISABLED
verify_attestation() {
  local file=$1 manifest=$2 owner=$3 invocation=$4 boot=$5 kernel=$6 lsm=$7 unpriv=$8
  local before after i name record object prog link_id prog_id tag attach
  local -A linked=()

  [[ ",${lsm}," == *,bpf,* ]] || die "BPF LSM is not active: /sys/kernel/security/lsm is '${lsm}'"
  [[ $unpriv == 1 ]] || die "kernel.unprivileged_bpf_disabled is '${unpriv}', expected 1"
  [[ $invocation =~ ^[0-9a-f]{32}$ ]] \
    || die "INVOCATION_ID is missing or malformed; this hook must run under chronus-sovereign-runner.service"

  trusted_path "${manifest%/*}" "$owner"
  trusted_path "$manifest" "$owner"
  trusted_path "${file%/*}" "$owner"
  trusted_path "$file" "$owner"
  [[ -f $file ]] || die "${file}: not a regular file"

  before=$(sha256sum < "$file") || die "${file}: sha256sum failed"
  parse_attestation "$file"
  after=$(sha256sum < "$file") || die "${file}: sha256sum failed"
  [[ $before == "$after" ]] || die "${file} changed while it was being read"
  ATTESTATION_SHA256=${after%% *}

  [[ ${ATT[format]} == "$ATTESTATION_FORMAT" ]] \
    || die "attestation format '${ATT[format]}', expected ${ATTESTATION_FORMAT}"
  [[ ${ATT[invocation_id]} == "$invocation" ]] \
    || die "attestation was written for invocation ${ATT[invocation_id]}; this runner runs in invocation ${invocation}"
  [[ ${ATT[boot_id]} == "$boot" ]] || die "attestation boot_id ${ATT[boot_id]} differs from this boot (${boot})"
  [[ ${ATT[kernel_release]} == "$kernel" ]] \
    || die "attestation kernel ${ATT[kernel_release]} differs from the running kernel ${kernel}"
  [[ ${ATT[unprivileged_bpf_disabled]} == 1 ]] || die "attestation records unprivileged_bpf_disabled=${ATT[unprivileged_bpf_disabled]}"
  [[ ",${ATT[lsm]}," == *,bpf,* ]] || die "attestation records an LSM list without bpf: ${ATT[lsm]}"
  [[ ${ATT[manifest]} == "$manifest" ]] || die "attestation refers to manifest ${ATT[manifest]}, expected ${manifest}"

  MANIFEST_SHA256=$(sha256sum < "$manifest") || die "${manifest}: sha256sum failed"
  MANIFEST_SHA256=${MANIFEST_SHA256%% *}
  [[ ${ATT[manifest_sha256]} == "$MANIFEST_SHA256" ]] \
    || die "manifest SHA-256 is ${MANIFEST_SHA256}; the attestation recorded ${ATT[manifest_sha256]}"
  read_manifest "$manifest"

  (( ${#ATT_OBJECTS[@]} == ${#MANIFEST_NAMES[@]} )) \
    || die "attestation lists ${#ATT_OBJECTS[@]} object(s); the manifest lists ${#MANIFEST_NAMES[@]}"
  for i in "${!MANIFEST_NAMES[@]}"; do
    name=${MANIFEST_NAMES[$i]}
    [[ ${ATT_OBJECTS[$name]:-} == "${MANIFEST_HASHES[$i]}" ]] \
      || die "object ${name}: attestation has '${ATT_OBJECTS[$name]:-none}', manifest has ${MANIFEST_HASHES[$i]}"
  done

  (( ${#ATT_LINKS[@]} > 0 )) || die "attestation records no attached LSM link"
  for record in "${ATT_LINKS[@]}"; do
    read -r object prog link_id prog_id tag attach <<< "$record"
    [[ -n ${ATT_OBJECTS[$object]:-} ]] || die "link ${link_id} belongs to ${object}, which is not in the manifest"
    [[ $attach == lsm_mac ]] || die "link ${link_id} (${object}/${prog}) has attach type ${attach}, expected lsm_mac"
    linked[$object]=$(( ${linked[$object]:-0} + 1 ))
  done
  for name in "${MANIFEST_NAMES[@]}"; do
    (( ${linked[$name]:-0} > 0 )) || die "object ${name}: no attached LSM link recorded"
  done

  VERIFIED_ATTESTATION=$file
  OBSERVED_INVOCATION=$invocation
  OBSERVED_BOOT=$boot
  OBSERVED_KERNEL=$kernel
  OBSERVED_LSM=$lsm
  OBSERVED_UNPRIV=$unpriv
}

json_escape() {
  local s=$1
  s=${s//\\/\\\\}
  s=${s//\"/\\\"}
  s=${s//$'\t'/\\t}
  s=${s//$'\n'/\\n}
  s=${s//$'\r'/\\r}
  s=${s//[[:cntrl:]]/}
  printf '%s' "$s"
}

# write_receipt PATH
# JSON receipt built from the verified attestation, the values observed at job
# start and the job's GitHub default variables. Requires verify_attestation.
write_receipt() {
  local path=$1 tmp=${1}.new key sep name record object prog link_id prog_id tag attach
  [[ -n $VERIFIED_ATTESTATION ]] || die "write_receipt called before verify_attestation"
  mkdir -p -m 0700 -- "${path%/*}" || die "${path%/*}: mkdir failed"
  {
    printf '{\n'
    printf '  "schema": "%s",\n' "$RECEIPT_SCHEMA"
    printf '  "generated_at": "%s",\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf '  "attestation_path": "%s",\n' "$(json_escape "$VERIFIED_ATTESTATION")"
    printf '  "attestation_sha256": "%s",\n' "$ATTESTATION_SHA256"
    printf '  "attestation_owner_uid": %s,\n' "$OBSERVED_OWNER"
    printf '  "attestation_mode": "%s",\n' "$OBSERVED_MODE"
    printf '  "attestation": {\n'
    sep=
    for key in $ATTESTATION_KEYS; do
      printf '%s    "%s": "%s"' "$sep" "$key" "$(json_escape "${ATT[$key]}")"
      sep=$',\n'
    done
    printf '\n  },\n'
    printf '  "objects": [\n'
    sep=
    for name in "${MANIFEST_NAMES[@]}"; do
      printf '%s    {"name": "%s", "sha256": "%s"}' "$sep" "$name" "${ATT_OBJECTS[$name]}"
      sep=$',\n'
    done
    printf '\n  ],\n'
    printf '  "lsm_links": [\n'
    sep=
    for record in "${ATT_LINKS[@]}"; do
      read -r object prog link_id prog_id tag attach <<< "$record"
      printf '%s    {"object": "%s", "program": "%s", "link_id": %s, "prog_id": %s, "prog_tag": "%s", "attach_type": "%s"}' \
        "$sep" "$object" "$prog" "$link_id" "$prog_id" "$tag" "$attach"
      sep=$',\n'
    done
    printf '\n  ],\n'
    printf '  "observed_at_job_start": {\n'
    printf '    "invocation_id": "%s",\n' "$(json_escape "$OBSERVED_INVOCATION")"
    printf '    "boot_id": "%s",\n' "$(json_escape "$OBSERVED_BOOT")"
    printf '    "kernel_release": "%s",\n' "$(json_escape "$OBSERVED_KERNEL")"
    printf '    "lsm": "%s",\n' "$(json_escape "$OBSERVED_LSM")"
    printf '    "unprivileged_bpf_disabled": "%s",\n' "$(json_escape "$OBSERVED_UNPRIV")"
    printf '    "manifest_sha256": "%s"\n' "$MANIFEST_SHA256"
    printf '  },\n'
    printf '  "github": {\n'
    printf '    "repository": "%s",\n' "$(json_escape "${GITHUB_REPOSITORY:-}")"
    printf '    "run_id": "%s",\n' "$(json_escape "${GITHUB_RUN_ID:-}")"
    printf '    "run_attempt": "%s",\n' "$(json_escape "${GITHUB_RUN_ATTEMPT:-}")"
    printf '    "job": "%s",\n' "$(json_escape "${GITHUB_JOB:-}")"
    printf '    "sha": "%s",\n' "$(json_escape "${GITHUB_SHA:-}")"
    printf '    "workflow_ref": "%s",\n' "$(json_escape "${GITHUB_WORKFLOW_REF:-}")"
    printf '    "runner_name": "%s"\n' "$(json_escape "${RUNNER_NAME:-}")"
    printf '  }\n'
    printf '}\n'
  } > "$tmp" || die "${tmp}: write failed"
  mv -f -- "$tmp" "$path" || die "${path}: rename failed"
}

main() {
  local lsm unpriv boot kernel
  export LC_ALL=C
  umask 077
  echo "::group::[AL HARAS] Pre-job check of the kernel/LSM attestation"
  trap 'echo "::endgroup::"' EXIT

  # $(cat ...) rather than $(< ...): under set -e a failed $(< file) exits
  # before the "|| die" handler can emit the ::error:: annotation.
  lsm=$(cat -- /sys/kernel/security/lsm 2> /dev/null) || die "cannot read /sys/kernel/security/lsm (securityfs not mounted?)"
  unpriv=$(cat -- /proc/sys/kernel/unprivileged_bpf_disabled 2> /dev/null) || die "cannot read kernel.unprivileged_bpf_disabled"
  boot=$(cat -- /proc/sys/kernel/random/boot_id 2> /dev/null) || die "cannot read the boot_id"
  kernel=$(uname -r)

  verify_attestation "$ATTESTATION" "$MANIFEST" 0 "${INVOCATION_ID:-}" "$boot" "$kernel" "$lsm" "$unpriv"
  write_receipt "$RECEIPT"
  echo "[AL HARAS] invocation ${OBSERVED_INVOCATION}: ${#MANIFEST_NAMES[@]} manifest object(s), ${#ATT_LINKS[@]} attached LSM link(s) recorded"
  echo "[AL HARAS] attestation sha256 ${ATTESTATION_SHA256}; unsigned receipt written to ${RECEIPT}"
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  main "$@"
fi
