#!/usr/bin/env bash
# AL HARAS ephemeral runner registration. Runs as `ExecStartPre=+` of
# chronus-sovereign-runner.service, after al-haras-bootstrap.sh has replaced
# /opt/actions-runner with a fresh copy of the runner release.
#
# It starts as root only to read /etc/al-haras/runner.env (root-owned, no
# group/other access), which holds the registration token. The token is kept
# out of the unit's Environment= because the runner passes its environment on
# to every job step. config.sh refuses to run as root ("Must not run with
# sudo"), so it runs as github-runner via setpriv with a minimal environment.
# The token is handed over in ACTIONS_RUNNER_INPUT_TOKEN, which the runner
# reads and then removes from its environment, rather than on the command line
# where any local user could read it from /proc.
#
# Registration is --ephemeral: GitHub de-registers the runner after its one job
# (see the README section "Deregistration").
set -euo pipefail

readonly RUNNER_USER=github-runner
readonly RUNNER_DIR=/opt/actions-runner
readonly ENV_FILE=/etc/al-haras/runner.env
readonly ENV_KEYS="RUNNER_CFG_TOKEN REPO_URL RUNNER_LABELS RUNNER_GROUP RUNNER_NAME"
readonly DEFAULT_REPO_URL=https://github.com/hybadatadevops1/Chronusv2
readonly DEFAULT_LABELS=sovereign,al-haras-enforced

declare -A CFG=()
CONFIG_ARGS=()

log() { printf '[AL HARAS register] %s\n' "$*"; }
die() { printf '[AL HARAS register] FATAL: %s\n' "$*" >&2; exit 1; }

# read_env_file FILE OWNER_UID
# KEY=VALUE lines (one pair of matching single or double quotes around VALUE is
# removed), '#' comments and blank lines. Only the keys in ENV_KEYS are
# accepted. FILE must be a regular file owned by OWNER_UID without group or
# other permissions.
read_env_file() {
  local file=$1 owner=$2 meta line n=0 key value
  local re='^([A-Z][A-Z0-9_]*)=(.*)$'
  [[ -f $file && ! -L $file ]] || die "${file}: missing, not a regular file, or a symlink"
  meta=$(stat -c '%u %a' -- "$file") || die "${file}: stat failed"
  [[ ${meta%% *} == "$owner" ]] || die "${file}: owner uid ${meta%% *}, expected ${owner}"
  (( (8#${meta##* } & 8#077) == 0 )) || die "${file}: mode ${meta##* } allows group/other access; use 0600"
  CFG=()
  while IFS= read -r line || [[ -n $line ]]; do
    n=$((n + 1))
    line=${line%$'\r'}
    if [[ $line =~ ^[[:space:]]*(#.*)?$ ]]; then
      continue
    fi
    [[ $line =~ $re ]] || die "${file}:${n}: expected KEY=VALUE"
    key=${BASH_REMATCH[1]}
    value=${BASH_REMATCH[2]}
    if [[ $value =~ ^\"(.*)\"$ || $value =~ ^\'(.*)\'$ ]]; then
      value=${BASH_REMATCH[1]}
    fi
    [[ " ${ENV_KEYS} " == *" ${key} "* ]] || die "${file}:${n}: unsupported key ${key} (supported: ${ENV_KEYS})"
    CFG[$key]=$value
  done < "$file"
}

# build_config_args SHORT_HOSTNAME EPOCH_SECONDS -> CONFIG_ARGS
# The token is validated here but never placed in CONFIG_ARGS.
build_config_args() {
  local host=$1 epoch=$2 url labels name group
  [[ -n ${CFG[RUNNER_CFG_TOKEN]:-} ]] || die "RUNNER_CFG_TOKEN is not set in ${ENV_FILE}"
  [[ ${CFG[RUNNER_CFG_TOKEN]} =~ ^[[:graph:]]+$ ]] || die "RUNNER_CFG_TOKEN contains whitespace or control characters"
  url=${CFG[REPO_URL]:-$DEFAULT_REPO_URL}
  labels=${CFG[RUNNER_LABELS]:-$DEFAULT_LABELS}
  name=${CFG[RUNNER_NAME]:-sovereign-${host}-${epoch}}
  group=${CFG[RUNNER_GROUP]:-}
  [[ $url =~ ^https://[^[:space:]]+$ ]] || die "REPO_URL must be an https:// URL without spaces"
  [[ $labels =~ ^[A-Za-z0-9._-]+(,[A-Za-z0-9._-]+)*$ ]] || die "RUNNER_LABELS must be comma-separated labels of [A-Za-z0-9._-]"
  [[ $name =~ ^[A-Za-z0-9._-]+$ ]] || die "runner name '${name}' must match [A-Za-z0-9._-]+"
  CONFIG_ARGS=(--unattended --url "$url" --name "$name" --labels "$labels" --work _work
    --ephemeral --disableupdate --replace)
  # Runner groups exist only for organizations and enterprises; config.sh fails
  # if the named group does not exist, so --runnergroup is passed only when set.
  if [[ -n $group ]]; then
    CONFIG_ARGS+=(--runnergroup "$group")
  fi
}

# run_config UID GID: config.sh as the runner user, minimal environment.
# The subshell drops every inherited exported variable first; the working
# variables use a private prefix so that loop cannot remove them.
run_config() {
  local uid=$1 gid=$2
  (
    __al_haras_token=${CFG[RUNNER_CFG_TOKEN]}
    __al_haras_cmd=(setpriv "--reuid=${uid}" "--regid=${gid}" --init-groups --no-new-privs --
      ./config.sh "${CONFIG_ARGS[@]}")
    while IFS= read -r __al_haras_name; do
      unset "$__al_haras_name" 2> /dev/null || true
    done < <(compgen -e)
    export PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8 HOME=$RUNNER_DIR USER=$RUNNER_USER LOGNAME=$RUNNER_USER
    export ACTIONS_RUNNER_INPUT_TOKEN=$__al_haras_token
    cd -- "$RUNNER_DIR" || exit 1
    exec "${__al_haras_cmd[@]}"
  )
}

main() {
  local uid gid host
  umask 077
  PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

  [[ $EUID -eq 0 ]] || die "must start as root (ExecStartPre=+); config.sh itself runs as ${RUNNER_USER}"
  uid=$(id -u "$RUNNER_USER") || die "user ${RUNNER_USER} does not exist"
  gid=$(id -g "$RUNNER_USER") || die "user ${RUNNER_USER} has no primary group"
  read_env_file "$ENV_FILE" 0
  host=$(uname -n)
  build_config_args "${host%%.*}" "$(date +%s)"

  [[ -x ${RUNNER_DIR}/config.sh ]] || die "${RUNNER_DIR}/config.sh is missing; al-haras-bootstrap.sh copies the runner there"
  [[ ! -e ${RUNNER_DIR}/.runner ]] || die "${RUNNER_DIR}/.runner exists; the runner directory was not refreshed"
  log "config.sh ${CONFIG_ARGS[*]}"
  run_config "$uid" "$gid" || die "config.sh failed"
  log "registered; GitHub de-registers this runner after its one job"
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  main "$@"
fi
