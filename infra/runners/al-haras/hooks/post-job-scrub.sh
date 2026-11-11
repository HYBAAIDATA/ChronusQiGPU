#!/usr/bin/env bash
# AL HARAS job-completed hook (ACTIONS_RUNNER_HOOK_JOB_COMPLETED). The runner
# runs it as github-runner, inside the unit's sandbox, after the job's last
# step ("Complete runner" in the job log).
#
# Deletes, as the job user:
#  - /opt/actions-runner/_work/_al_haras (the pre-flight receipt). The
#    receipt's retention ends with the job: a workflow that needs to keep it
#    must upload or attest it in one of its own steps;
#  - the contents of $GITHUB_WORKSPACE (the job's checkout);
#  - entries owned by this user directly under /tmp, /var/tmp and /dev/shm.
#    /tmp and /var/tmp are private to the unit invocation (PrivateTmp=true)
#    and are discarded by systemd when the unit stops; RemoveIPC=true removes
#    this user's /dev/shm and SysV IPC objects at the same point.
# al-haras-teardown.sh deletes the rest of _work after the runner exits, and
# al-haras-bootstrap.sh replaces the whole runner directory before the next
# job. Deletion unlinks files; it does not overwrite disk blocks.
set -euo pipefail

readonly WORK_ROOT=/opt/actions-runner/_work
readonly RECEIPT_DIR=/opt/actions-runner/_work/_al_haras

# scrub_job_files WORK_ROOT RECEIPT_DIR WORKSPACE
scrub_job_files() {
  local work_root=$1 receipt_dir=$2 workspace=$3
  rm -rf -- "$receipt_dir"
  if [[ -z $workspace ]]; then
    echo "::warning::[AL HARAS] GITHUB_WORKSPACE is not set; workspace not scrubbed here (teardown removes _work)"
    return 0
  fi
  if [[ $workspace != "$work_root"/?* || $workspace == *'/../'* || $workspace == */.. ]]; then
    echo "::warning::[AL HARAS] GITHUB_WORKSPACE '${workspace}' is outside ${work_root}; not scrubbed here"
    return 0
  fi
  if [[ -d $workspace && ! -L $workspace ]]; then
    find "$workspace" -mindepth 1 -maxdepth 1 -exec rm -rf --one-file-system -- {} +
  fi
}

# scrub_user_temp UID DIR...
scrub_user_temp() {
  local uid=$1 dir
  shift
  for dir in "$@"; do
    if [[ -d $dir ]]; then
      find "$dir" -mindepth 1 -maxdepth 1 -uid "$uid" -exec rm -rf --one-file-system -- {} + 2> /dev/null || true
    fi
  done
}

main() {
  echo "::group::[AL HARAS] Post-job scrub"
  trap 'echo "::endgroup::"' EXIT
  scrub_job_files "$WORK_ROOT" "$RECEIPT_DIR" "${GITHUB_WORKSPACE:-}"
  scrub_user_temp "$(id -u)" /tmp /var/tmp /dev/shm
  echo "[AL HARAS] deleted ${RECEIPT_DIR}, the contents of ${GITHUB_WORKSPACE:-<GITHUB_WORKSPACE unset>}," \
    "and $(id -un)-owned entries directly under /tmp, /var/tmp and /dev/shm"
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  main "$@"
fi
