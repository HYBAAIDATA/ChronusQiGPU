#!/bin/bash
# HYBA Mine on the mining host (vm-qigpu-miner, UK West). Runs as root through Azure
# run-command, started by .github/workflows/hyba-mine.yml (no inbound access needed):
#
#   vm-hyba-mine.sh <campaign|status|stop|examine> <pools> <key vault> <registry login server> <registry name> [image] [campaign id] [max run seconds]
#
#   campaign  pull the image built from GitHub, run the BIST (known-answer checks of the
#             miner's own hash path and lanes; no BIST pass, no stratum connect), then run
#             the two-block campaign: one block on the first pool, a cool-down, a
#             non-consecutive block on the second pool, then offline. The container exits
#             when the campaign completes and is not restarted.
#   status    container state and what the campaign has done (pool acknowledgements are
#             the only witness of a share)
#   stop      stop the miner now
#   examine   after the campaign: look for any attempt to look inside the miner (exec,
#             attach, copy, export or top on the container; files changed in it; pool
#             methods outside Stratum V1 mining; SSH attempts; logins; listening services;
#             run-command executions)
#
# Pool logins and the registry password are read from Key Vault with this host's managed
# identity, written to a 0600 file that docker reads once, and deleted; they are never
# printed. One miner runs on this host at a time: a running CronusQiGPU shadow container
# (qigpu-miner) is stopped, not removed; its evidence on the custody disk is untouched.
if [ -z "${BASH_VERSION:-}" ]; then exec /bin/bash "$0" "$@"; fi
set -euo pipefail

action="${1:-status}"
pools="${2:-viabtc,braiins}"
vault="${3:-}"
login_server="${4:-}"
registry="${5:-}"
image="${6:-}"
campaign_id="${7:-}"
max_run_seconds="${8:-14400}"
name=hyba-mine
host_state=/var/lib/hyba-mine-host

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

endpoint() {
  case "$1" in
    viabtc) echo "btc.viabtc.io 3333" ;;
    braiins) echo "stratum.braiins.com 3333" ;;
    *) return 1 ;;
  esac
}

status() {
  local state logs
  state="$(docker inspect -f '{{.State.Status}} (exit {{.State.ExitCode}}) since {{.State.StartedAt}}; restarts {{.RestartCount}}' "$name" 2>/dev/null || true)"
  echo "MINER_STATE ${state:-not running}"
  [[ -n "$state" ]] || return 0
  echo "Image: $(docker inspect -f '{{.Config.Image}}' "$name" | cut -c1-140)"
  logs="$(docker logs --tail 200000 "$name" 2>&1 || true)"
  count() { printf '%s\n' "$logs" | grep -c -E "$1" || true; }
  echo "Handshakes: $(count 'Handshake complete') | submitted: $(count '\[LIVE WIRE\] Submitting') | accepted by pool: $(count '\[POOL SUCCESS\]') | rejected by pool: $(count '\[POOL REJECT\]') | dropped locally: $(count '\[LOCAL GATEKEEPER\]') | unexpected pool methods: $(count '\[POOL PUSH\] UNEXPECTED') | errors: $(count 'Traceback|Error in ')"
  echo "Lanes:"
  printf '%s\n' "$logs" | grep -E '\[LANES\] qualification' | sed 's/.*qualification //' | python3 -c '
import json, sys
for line in sys.stdin:
    try:
        r = json.loads(line)
    except ValueError:
        continue
    cal = (r.get("calibration") or {}).get("per_s")
    print("  %s lanes=%s passed=%s selected=%s calibrated_per_s=%s %s" % (r.get("backend"), r.get("lanes"), r.get("passed"), r.get("selected"), cal, (r.get("reason") or "")[:120]))
' || true
  echo "Capacity: $(printf '%s\n' "$logs" | grep -E '\[CAPACITY\] \{' | tail -n 1 | sed 's/.*\[CAPACITY\] //' | cut -c1-600)"
  echo "Statistics: $(printf '%s\n' "$logs" | grep -E '\[STATS\]' | tail -n 1 | sed 's/.*\[STATS\] //' | cut -c1-240)"
  echo "Campaign:"
  printf '%s\n' "$logs" | grep -E '\[CAMPAIGN\]' | grep -v -E 'sent a job' | sed 's/^[0-9-]* [0-9:,]* \[INFO\] //' | cut -c1-900 | tail -n 14 || true
  echo "Recent lines (worker names omitted):"
  printf '%s\n' "$logs" | grep -v -i -E "worker|identity" | grep -v -E '\[STATS\]|\[CAPACITY\]|\[CAMPAIGN\]|\[LANES\]' | tail -n 8 | cut -c1-200 || true
  return 0
}

examine() {
  local since now looks
  since="$(cat "$host_state/campaign-start" 2>/dev/null || date -u -d '-6 hours' +%Y-%m-%dT%H:%M:%SZ)"
  now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "EXAMINE window $since to $now"
  echo "== Events on the miner container (exec, attach, copy, export, top, commit or pause would be a look inside)"
  docker events --since "$since" --until "$now" --filter "container=$name" --format '{{.Action}}' 2>/dev/null \
    | sed 's/:.*//' | sort | uniq -c || true
  looks="$(docker events --since "$since" --until "$now" --filter "container=$name" --format '{{.Action}}' 2>/dev/null \
    | grep -c -E '^(exec_|attach|copy|export|top|commit|pause)' || true)"
  echo "LOOKS_INSIDE_CONTAINER ${looks:-0}"
  echo "== Containers started on the host in the window"
  docker events --since "$since" --until "$now" --filter type=container --filter event=start \
    --format '{{.Actor.Attributes.name}} {{.Actor.Attributes.image}}' 2>/dev/null | sort | uniq -c | cut -c1-200 || true
  echo "== Files changed inside the miner container (its state and kernel cache excluded)"
  docker diff "$name" 2>/dev/null | grep -v -E '/var/lib/hyba-mine|/var/lib/chronus/\.cache|__pycache__|^C /var/lib/chronus$|^C /tmp|^A /tmp' | head -n 40 || true
  echo "== Pool methods outside Stratum V1 mining"
  docker logs "$name" 2>&1 | grep -E '\[POOL PUSH\] UNEXPECTED' | sed 's/.*method=//' | sort | uniq -c || true
  echo "== SSH in the window (failed, invalid user, accepted)"
  journalctl -u ssh -u sshd --since "$since" --no-pager 2>/dev/null \
    | grep -o -E 'Failed password|Invalid user|Accepted (password|publickey)|Connection closed by authenticating user|maximum authentication attempts' \
    | sort | uniq -c || true
  echo "Top SSH sources:"
  journalctl -u ssh -u sshd --since "$since" --no-pager 2>/dev/null \
    | grep -o -E 'from [0-9a-f.:]+' | sort | uniq -c | sort -rn | head -n 5 || true
  echo "== Logins"
  last -n 8 2>/dev/null | head -n 8 || true
  echo "Failed logins: $(lastb 2>/dev/null | grep -c -v -E '^$|btmp begins' || true)"
  echo "== Listening services"
  ss -tlnp 2>/dev/null | cut -c1-160 || true
  echo "== Established TCP connections"
  ss -tn state established 2>/dev/null | cut -c1-120 | head -n 20 || true
  echo "== Run-command executions on this host in the window"
  find /var/lib/waagent/run-command/download -mindepth 1 -maxdepth 1 -type d -newermt "$since" 2>/dev/null | wc -l || true
  echo "== Top processes"
  ps -eo user,pid,pcpu,pmem,etime,comm --sort=-pcpu | head -n 12 || true
  echo "EXAMINE_DONE"
}

case "$action" in
  campaign)
    [[ -n "$vault" && -n "$login_server" && -n "$registry" && -n "$image" && -n "$campaign_id" ]] \
      || fail "usage: campaign <pools> <key vault> <registry login server> <registry name> <image> <campaign id> [max run seconds]"
    [[ "$max_run_seconds" =~ ^[0-9]+$ ]] || fail "max run seconds must be a whole number"
    IFS=',' read -r -a pool_list <<< "$pools"
    [[ ${#pool_list[@]} -ge 1 ]] || fail "no pools"
    for pool in "${pool_list[@]}"; do endpoint "$pool" >/dev/null || fail "unknown pool '$pool' (viabtc or braiins)"; done
    command -v docker >/dev/null || fail "docker is not installed"
    command -v curl >/dev/null || fail "curl is not installed"

    password="$(kv_secret registry-pull-password)" || fail "cannot read registry-pull-password from Key Vault"
    printf '%s' "$password" | docker login "$login_server" --username "$registry" --password-stdin >/dev/null
    unset password
    docker pull --quiet "$image" >/dev/null || fail "cannot pull $image"
    docker logout "$login_server" >/dev/null

    echo "== BIST (no BIST pass, no stratum connect)"
    if ! bist="$(docker run --rm --network none "$image" python /opt/hyba-mine/bist.py 2>&1)"; then
      printf '%s\n' "$bist" | tail -n 40
      fail "BIST failed; the miner was not started"
    fi
    printf '%s\n' "$bist" | python3 -c '
import json, sys
r = json.loads(sys.stdin.read())
print("bist", r["bist"], "checks", sum(1 for c in r["checks"] if c["passed"]), "/", len(r["checks"]))
for lane in r.get("lanes", []):
    print("  lane", lane.get("backend"), "passed=%s" % lane.get("passed"), (lane.get("reason") or "")[:120], (lane.get("device") or {}).get("device_name", ""))
' || printf '%s\n' "$bist" | grep -E '"bist"' || true

    umask 077
    secrets_dir="$(mktemp -d /run/hyba-mine.XXXXXX)"
    trap 'rm -rf "$secrets_dir"' EXIT
    {
      printf 'HYBA_MINE_POOLS=%s\nHYBA_MINE_CAMPAIGN_ID=%s\nHYBA_MINE_MAX_RUN_SECONDS=%s\n' "$pools" "$campaign_id" "$max_run_seconds"
      for pool in "${pool_list[@]}"; do
        read -r host port <<< "$(endpoint "$pool")"
        upper="${pool^^}"
        worker="$(kv_secret "pool-$pool-worker")" || fail "cannot read pool-$pool-worker from Key Vault"
        pool_password="$(kv_secret "pool-$pool-password")" || fail "cannot read pool-$pool-password from Key Vault"
        printf 'MINING_%s_HOST=%s\nMINING_%s_PORT=%s\n' "$upper" "$host" "$upper" "$port"
        printf 'MINING_%s_USER=%s\nMINING_%s_PASSWORD=%s\n' "$upper" "$worker" "$upper" "$pool_password"
        unset worker pool_password
      done
    } > "$secrets_dir/env"

    if [[ "$(docker inspect -f '{{.State.Running}}' qigpu-miner 2>/dev/null || true)" == true ]]; then
      docker stop --time 60 qigpu-miner >/dev/null 2>&1 || true
      echo "Stopped the CronusQiGPU shadow container (qigpu-miner); it was not removed and its custody-disk evidence is untouched."
    fi
    docker rm -f "$name" >/dev/null 2>&1 || true
    docker volume create hyba-mine-state >/dev/null
    mkdir -p "$host_state"
    date -u +%Y-%m-%dT%H:%M:%SZ > "$host_state/campaign-start"
    echo "$campaign_id" > "$host_state/campaign-id"
    docker run -d --name "$name" --init --restart on-failure:3 \
      --log-driver json-file --log-opt max-size=50m --log-opt max-file=5 \
      -v hyba-mine-state:/var/lib/hyba-mine \
      --label "hyba-mine.campaign=$campaign_id" \
      --env-file "$secrets_dir/env" \
      "$image" >/dev/null
    rm -rf "$secrets_dir"
    echo "Campaign $campaign_id started from $image: pools $pools, at most $max_run_seconds s; waiting for the first pool handshake..."
    for _ in $(seq 1 24); do
      if docker logs "$name" 2>&1 | grep -E 'Handshake complete|Traceback|\[CAMPAIGN\] complete' >/dev/null; then break; fi
      sleep 10
    done
    status
    docker logs "$name" 2>&1 | grep -E 'Handshake complete' >/dev/null \
      || fail "no pool handshake within 4 minutes; see the lines above"
    echo "MINER_OK campaign running: BIST passed, lanes qualified and the first pool handshake is complete; a share counts only when the pool accepts it"
    ;;
  stop)
    docker stop --time 60 "$name" >/dev/null 2>&1 || true
    echo "MINER_OK stopped"
    ;;
  status)
    status
    ;;
  examine)
    examine
    ;;
  *)
    fail "unknown action '$action' (campaign, status, stop or examine)"
    ;;
esac
