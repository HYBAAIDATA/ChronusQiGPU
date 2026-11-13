#!/usr/bin/env bash
# Run the Chronusv2 API image on an existing Linux App Service plan
# (infra/azure/app.bicep) and check it the way CI checks the container:
#   1. /health/ready answers 200;
#   2. a workload submitted without a token is refused with 401;
#   3. the same workload with the Key Vault tenant token completes (Lucas L_10 = 123).
#
# Runs in the Azure DevOps "Deploy" stage (azure-pipelines.yml, deploy=true) or by
# hand in Azure Cloud Shell (Bash), from the repository root:
#
#   bash infra/azure/deploy_app.sh --resource-group rg-cronusqigpu-demo \
#     --plan asp-cronusqigpu-demo-hybadata --web-app chronusv2-demo-hybadata \
#     --registry crcronusqigpudemohybadata --key-vault kv-cronusqigpu-demo-hyba \
#     --image-repository chronusv --image-tag <tag pushed by the pipeline>
#
# The tenant token and the JWT signing secret are generated here on first use and
# kept in Key Vault (chronusv2-tenant-token, chronusv2-jwt-secret). They are never
# printed, and existing secrets are left unchanged, so re-running never rotates them.
set -euo pipefail

resource_group=""
plan=""
web_app=""
registry=""
key_vault=""
image_repository="chronusv"
image_tag=""
allowed_ip=""
tenant_id="demo"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --resource-group)   resource_group="$2"; shift 2 ;;
    --plan)             plan="$2"; shift 2 ;;
    --web-app)          web_app="$2"; shift 2 ;;
    --registry)         registry="$2"; shift 2 ;;
    --key-vault)        key_vault="$2"; shift 2 ;;
    --image-repository) image_repository="$2"; shift 2 ;;
    --image-tag)        image_tag="$2"; shift 2 ;;
    --allowed-ip)       allowed_ip="$2"; shift 2 ;;
    --tenant-id)        tenant_id="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
for required in resource_group plan web_app registry key_vault image_tag; do
  if [[ -z "${!required}" ]]; then
    echo "Missing --${required//_/-}" >&2
    exit 2
  fi
done

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Subscription: $(az account show --query name --output tsv)"

umask 077
work="$(mktemp -d)"
rule_added=""
cleanup() {
  if [[ -n "$rule_added" ]]; then
    az webapp config access-restriction remove --resource-group "$resource_group" --name "$web_app" \
      --rule-name pipeline-smoke-test --output none || true
  fi
  rm -rf "$work"
}
trap cleanup EXIT

# Creates a Key Vault secret only if it does not exist (32 random bytes, URL-safe).
ensure_secret() {
  local name="$1"
  if az keyvault secret show --vault-name "$key_vault" --name "$name" --query id --output none 2>"$work/error"; then
    echo "Secret $name already exists; left unchanged."
  elif grep -q "SecretNotFound" "$work/error"; then
    python3 -c 'import secrets, sys; sys.stdout.write(secrets.token_urlsafe(32))' > "$work/value"
    az keyvault secret set --vault-name "$key_vault" --name "$name" \
      --file "$work/value" --encoding utf-8 --output none
    : > "$work/value"
    echo "Secret $name created."
  else
    cat "$work/error" >&2
    exit 1
  fi
}
ensure_secret chronusv2-tenant-token
ensure_secret chronusv2-jwt-secret

# Deployment parameters, secrets included, go through a private file, never the command line.
CHRONUS_TENANT_TOKEN="$(az keyvault secret show --vault-name "$key_vault" --name chronusv2-tenant-token --query value --output tsv)" \
CHRONUS_JWT_SECRET="$(az keyvault secret show --vault-name "$key_vault" --name chronusv2-jwt-secret --query value --output tsv)" \
python3 - "$work/parameters.json" "$web_app" "$plan" "$registry" "$image_repository" "$image_tag" "$allowed_ip" "$tenant_id" <<'PY'
import json, os, sys
path, web_app, plan, registry, repository, tag, allowed, tenant = sys.argv[1:9]
parameters = {
    "webAppName": web_app,
    "planName": plan,
    "registryName": registry,
    "imageRepository": repository,
    "imageTag": tag,
    "allowedIpCidr": allowed,
    "tenantTokensJson": json.dumps({tenant: os.environ["CHRONUS_TENANT_TOKEN"]}),
    "jwtSecret": os.environ["CHRONUS_JWT_SECRET"],
}
with open(path, "w", encoding="utf-8") as handle:
    json.dump({
        "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
        "contentVersion": "1.0.0.0",
        "parameters": {name: {"value": value} for name, value in parameters.items()},
    }, handle)
PY

az deployment group create \
  --resource-group "$resource_group" \
  --name "chronusv2-app-$(date -u +%Y%m%d%H%M%S)" \
  --template-file "$here/app.bicep" \
  --parameters @"$work/parameters.json" \
  --query "properties.outputs" --output json
: > "$work/parameters.json"

# A new image needs a restart to be pulled when the tag already ran before.
az webapp restart --resource-group "$resource_group" --name "$web_app" --output none
host="$(az webapp show --resource-group "$resource_group" --name "$web_app" --query defaultHostName --output tsv)"
echo "Chronusv2 API: https://$host (closed to the internet except: ${allowed_ip:-nobody})"

# The app is closed to the internet: open it to this agent only, and close it again on exit.
agent_ip="$(curl -fsS https://api.ipify.org)"
az webapp config access-restriction add --resource-group "$resource_group" --name "$web_app" \
  --rule-name pipeline-smoke-test --action Allow --ip-address "$agent_ip/32" --priority 50 --output none
rule_added="yes"

code=""
for attempt in $(seq 1 45); do
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "https://$host/health/ready" || true)"
  echo "health/ready attempt $attempt: HTTP $code"
  [[ "$code" == 200 ]] && break
  sleep 20
done
[[ "$code" == 200 ]] || { echo "##vso[task.logissue type=error]Chronusv2 did not report ready on /health/ready"; exit 1; }

workload='{"tenant_id":"'"$tenant_id"'","workload_type":"LUCAS_PV_SCALING","representation_mode":"PV_LUCAS_COLLAPSE","payload_bytes":"base64:eyJpbmRleCI6MTB9"}'
anon="$(curl -s -o /dev/null -w '%{http_code}' --max-time 60 -X POST -H 'Content-Type: application/json' \
  -d "$workload" "https://$host/workloads/submit" || true)"
echo "Workload without a token: HTTP $anon (must be 401)"
[[ "$anon" == 401 ]] || { echo "##vso[task.logissue type=error]Workload without a token was not refused"; exit 1; }

az keyvault secret show --vault-name "$key_vault" --name chronusv2-tenant-token --query value --output tsv \
  | python3 -c 'import sys; sys.stdout.write("Authorization: Bearer " + sys.stdin.read().strip() + "\n")' > "$work/auth-header"
authed="$(curl -s -o "$work/result.json" -w '%{http_code}' --max-time 120 -X POST -H 'Content-Type: application/json' \
  -H @"$work/auth-header" -d "$workload" "https://$host/workloads/submit" || true)"
: > "$work/auth-header"
echo "Workload with the Key Vault token: HTTP $authed"
python3 - "$work/result.json" <<'PY'
import json, sys
try:
    result = json.load(open(sys.argv[1], encoding="utf-8"))
except (OSError, ValueError) as error:
    print("##vso[task.logissue type=error]Workload response was not JSON:", error)
    sys.exit(1)
status = result.get("status")
lucas = ((result.get("result") or {}).get("result") or {}).get("lucas")
print("status:", status, "| lucas L_10:", lucas)
if status != "COMPLETED" or lucas != "123":
    print("##vso[task.logissue type=error]Workload with the token did not complete with L_10 = 123")
    sys.exit(1)
PY
echo "Chronusv2 deployed and checked: https://$host"
