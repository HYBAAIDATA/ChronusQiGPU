#!/bin/bash
# HYBA Mine on the mining host (vm-qigpu-miner, UK West). Runs as root through Azure
# run-command, started by .github/workflows/hyba-mine.yml (no inbound access needed):
#
#   vm-hyba-mine.sh <start|stop|status> <viabtc|braiins> <key vault> <registry login server> <registry name> [image]
#
#   start   pull the image built from GitHub, run the BIST (known-answer checks of the
#           miner's own hash path; no BIST pass, no stratum connect), then run the
#           Stratum V1 miner for one pool. Docker restarts it if it stops.
#   stop    stop and remove the miner container
#   status  container state and what the miner has done (pool acknowledgements are
#           the only witness of a share)
#
# Pool logins and the registry password are read from Key Vault with this host's managed
# identity, written to a 0600 file that docker reads once, and deleted; they are never
# printed. One miner runs on this host at a time: a running CronusQiGPU shadow container
# (qigpu-miner) is stopped, not removed; its evidence on the custody disk is untouched.
if [ -z "${BASH_VERSION:-}" ]; then exec /bin/bash "$0" "$@"; fi
set -euo pipefail

action="${1:-status}"
pool="${2:-viabtc}"
vault="${3:-}"
login_server="${4:-}"
registry="${5:-}"
image="${6:-}"
name=hyba-mine

fail() { echo "MINER_ERROR $*"; exit 1; }

json_field() {
  if command -v jq >/dev/null; then jq -r ".$1"; else python3 -c "import json,sys; print(json.load(sys.stdin).get('$1') or '')"; fi
}

kv_secret() {
  local token value
  token="$(curl -fsS -H Metadata:true \
    'http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https%3A%2F%2Fvault.azure.net' \
    | json_field access_token)" || return 1
  value="$(curl -fsS -H "Authorization: Bearer $token" \
    "https://$vault.vault.azure.net/secrets/$1?api-version=7.4" | json_field value)" || return 1
  [[ -n "$value" && "$value" != null ]] || return 1
  printf '%s' "$value"
}

status() {
  local state logs
  state="$(docker inspect -f '{{.State.Status}} since {{.State.StartedAt}}; restarts {{.RestartCount}}' "$name" 2>/dev/null || true)"
  echo "MINER_STATE ${state:-not running}"
  [[ -n "$state" ]] || return 0
  echo "Image: $(docker inspect -f '{{.Config.Image}}' "$name" | cut -c1-140)"
  logs="$(docker logs --tail 200000 "$name" 2>&1 || true)"
  count() { printf '%s\n' "$logs" | grep -c -E "$1" || true; }
  echo "Handshakes: $(count 'Handshake complete') | submitted: $(count '\[LIVE WIRE\] Submitting') | accepted by pool: $(count '\[POOL SUCCESS\]') | rejected by pool: $(count '\[POOL REJECT\]') | dropped locally: $(count '\[LOCAL GATEKEEPER\]') | pool sessions ended: $(count 'Pool session ended|Pool closed connection') | errors: $(count 'Traceback|Error in ')"
  echo "Latest statistics: $(printf '%s\n' "$logs" | grep -E '\[STATS\]' | tail -n 1 | sed 's/.*\[STATS\] //' | cut -c1-200)"
  echo "Latest pool difficulty: $(printf '%s\n' "$logs" | grep -i -E 'difficulty' | tail -n 1 | cut -c1-160)"
  echo "Recent lines (worker names omitted):"
  printf '%s\n' "$logs" | grep -v -i -E "worker|identity" | grep -v -E '\[STATS\]' | tail -n 8 | cut -c1-200 || true
  return 0
}

case "$action" in
  start)
    [[ -n "$vault" && -n "$login_server" && -n "$registry" && -n "$image" ]] \
      || fail "usage: start <pool> <key vault> <registry login server> <registry name> <image>"
    case "$pool" in
      viabtc) pool_upper=VIABTC; host=btc.viabtc.io; port=3333 ;;
      braiins) pool_upper=BRAIINS; host=stratum.braiins.com; port=3333 ;;
      *) fail "unknown pool '$pool' (viabtc or braiins)" ;;
    esac
    command -v docker >/dev/null || fail "docker is not installed"
    command -v curl >/dev/null || fail "curl is not installed"

    password="$(kv_secret registry-pull-password)" || fail "cannot read registry-pull-password from Key Vault"
    printf '%s' "$password" | docker login "$login_server" --username "$registry" --password-stdin >/dev/null
    unset password
    docker pull --quiet "$image" >/dev/null || fail "cannot pull $image"
    docker logout "$login_server" >/dev/null

    echo "== BIST (no BIST pass, no stratum connect)"
    if ! bist="$(docker run --rm --network none "$image" python /opt/hyba-mine/bist.py 2>&1)"; then
      printf '%s\n' "$bist" | tail -n 30
      fail "BIST failed; the miner was not started"
    fi
    printf '%s\n' "$bist" | grep -E '"bist"' || true

    umask 077
    secrets_dir="$(mktemp -d /run/hyba-mine.XXXXXX)"
    trap 'rm -rf "$secrets_dir"' EXIT
    worker="$(kv_secret "pool-$pool-worker")" || fail "cannot read pool-$pool-worker from Key Vault"
    pool_password="$(kv_secret "pool-$pool-password")" || fail "cannot read pool-$pool-password from Key Vault"
    {
      printf 'MINING_ACTIVE_POOL=%s\n' "$pool_upper"
      printf 'MINING_%s_HOST=%s\nMINING_%s_PORT=%s\n' "$pool_upper" "$host" "$pool_upper" "$port"
      printf 'MINING_%s_USER=%s\nMINING_%s_PASSWORD=%s\n' "$pool_upper" "$worker" "$pool_upper" "$pool_password"
    } > "$secrets_dir/env"
    unset worker pool_password

    if [[ "$(docker inspect -f '{{.State.Running}}' qigpu-miner 2>/dev/null || true)" == true ]]; then
      docker stop --time 60 qigpu-miner >/dev/null 2>&1 || true
      echo "Stopped the CronusQiGPU shadow container (qigpu-miner); it was not removed and its custody-disk evidence is untouched."
    fi
    docker rm -f "$name" >/dev/null 2>&1 || true
    docker run -d --name "$name" --restart unless-stopped \
      --log-driver json-file --log-opt max-size=50m --log-opt max-file=5 \
      --env-file "$secrets_dir/env" -e PYTHONUNBUFFERED=1 \
      "$image" >/dev/null
    rm -rf "$secrets_dir"
    echo "Miner started from $image on $pool ($host:$port); waiting for the pool handshake..."
    for _ in $(seq 1 18); do
      if docker logs "$name" 2>&1 | grep -E 'Handshake complete|Traceback' >/dev/null; then break; fi
      sleep 10
    done
    status
    docker logs "$name" 2>&1 | grep -E 'Handshake complete' >/dev/null \
      || fail "no pool handshake within 3 minutes; see the lines above"
    echo "MINER_OK started: BIST passed and the $pool handshake is complete; a share counts only when the pool accepts it"
    ;;
  stop)
    docker stop --time 60 "$name" >/dev/null 2>&1 || true
    docker rm "$name" >/dev/null 2>&1 || true
    echo "MINER_OK stopped"
    ;;
  status)
    status
    ;;
  *)
    fail "unknown action '$action' (start, stop or status)"
    ;;
esac
