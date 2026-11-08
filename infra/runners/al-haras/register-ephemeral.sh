#!/usr/bin/env bash
# Registers this host as an ephemeral, single-job runner for the repository.
# Requires RUNNER_CFG_PAT (or a JIT config) and REPO_URL in the environment,
# e.g. via an EnvironmentFile referenced from an override unit.
set -euo pipefail

: "${REPO_URL:=https://github.com/hybadatadevops1/Chronusv2}"
RUNNER_NAME="${RUNNER_NAME:-sovereign-$(hostname)-$(date +%s)}"
LABELS="${RUNNER_LABELS:-self-hosted,sovereign,al-haras-enforced}"

./config.sh \
  --url "${REPO_URL}" \
  --token "${RUNNER_CFG_TOKEN:?RUNNER_CFG_TOKEN must be set (short-lived registration token)}" \
  --name "${RUNNER_NAME}" \
  --labels "${LABELS}" \
  --runnergroup "${RUNNER_GROUP:-sovereign-compute}" \
  --work _work \
  --ephemeral \
  --unattended \
  --replace
