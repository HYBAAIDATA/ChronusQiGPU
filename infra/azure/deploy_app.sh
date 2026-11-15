#!/usr/bin/env bash
# Run both docker-compose.yml services of Chronus_Redux on an existing Linux App
# Service plan (infra/azure/app.bicep) and check them the way CI checks the container:
#   1. api /health/ready answers 200;
#   2. a workload submitted without a token is refused with 401;
#   3. the same workload with the Key Vault tenant token completes (Lucas L_10 = 123);
#   4. the web console answers 200 and reaches the api through its proxy route.
#
# Runs in the Azure DevOps "Deploy" stage (azure-pipelines.yml, deploy=true) or by hand
# in Azure Cloud Shell (Bash), from the repository root:
#
#   bash infra/azure/deploy_app.sh --resource-group rg-cronusqigpu-demo \
#     --plan asp-cronusqigpu-demo-hybadata --api-app chronus-redux-demo-hybadata \
#     --web-app chronus-redux-demo-hybadata-web --registry crcronusqigpudemohybadata \
#     --key-vault kv-cronusqigpu-demo-hyba --image-tag "$(git rev-parse HEAD)" --build-images
#
# --build-images builds Dockerfile and frontend/Dockerfile and pushes them to the
# registry first; without it the images for --image-tag must already be there.
# The tenant token and the JWT signing secret are generated here on first use and kept
# in Key Vault (chronus-redux-tenant-token, chronus-redux-jwt-secret). They are never
# printed, and existing secrets are left unchanged, so re-running never rotates them.
set -euo pipefail

resource_group=""
plan=""
api_app=""
web_app=""
registry=""
key_vault=""
image_tag=""
allowed_ip=""
tenant_id="demo"
integration_subnet="auto"
build_images="no"
api_repository="chronus-redux-api"
web_repository="chronus-redux-web"
secret_prefix="chronus-redux"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --resource-group)     resource_group="$2"; shift 2 ;;
    --plan)               plan="$2"; shift 2 ;;
    --api-app)            api_app="$2"; shift 2 ;;
    --web-app)            web_app="$2"; shift 2 ;;
    --registry)           registry="$2"; shift 2 ;;
    --key-vault)          key_vault="$2"; shift 2 ;;
    --image-tag)          image_tag="$2"; shift 2 ;;
    --allowed-ip)         allowed_ip="$2"; shift 2 ;;
    --tenant-id)          tenant_id="$2"; shift 2 ;;
    --integration-subnet) integration_subnet="$2"; shift 2 ;;
    --build-images)       build_images="yes"; shift ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
for required in resource_group plan api_app web_app registry key_vault image_tag; do
  if [[ -z "${!required}" ]]; then
    echo "Missing --${required//_/-}" >&2
    exit 2
  fi
done

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$here/../.." && pwd)"
echo "Subscription: $(az account show --query name --output tsv)"

umask 077
work="$(mktemp -d)"
rules_added=()
cleanup() {
  for app in "${rules_added[@]}"; do
    az webapp config access-restriction remove --resource-group "$resource_group" --name "$app" \
      --rule-name pipeline-smoke-test --output none || true
  done
  rm -rf "$work"
}
trap cleanup EXIT

login_server="$(az acr show --name "$registry" --query loginServer --output tsv)"
if [[ "$build_images" == yes ]]; then
  # Push with the signed-in Azure identity (needs AcrPush), not the registry admin password.
  az acr login --name "$registry" --output none
  docker build --file "$repo_root/Dockerfile" --tag "$login_server/$api_repository:$image_tag" "$repo_root"
  docker build --file "$repo_root/frontend/Dockerfile" --tag "$login_server/$web_repository:$image_tag" "$repo_root/frontend"
  docker push "$login_server/$api_repository:$image_tag"
  docker push "$login_server/$web_repository:$image_tag"
  docker logout "$login_server" >/dev/null || true
fi

# The web console joins the demo network's console subnet when it exists (infra of
# CronusQiGPU, infra/main.bicep), so it can reach the api while the api stays closed.
if [[ "$integration_subnet" == auto ]]; then
  integration_subnet="$(az network vnet subnet list --resource-group "$resource_group" \
    --vnet-name vnet-cronusqigpu-demo-hybadata --query "[?name=='web-console'].id | [0]" --output tsv 2>/dev/null || true)"
fi
echo "Web console network integration: ${integration_subnet:-none}"

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
ensure_secret "$secret_prefix-tenant-token"
ensure_secret "$secret_prefix-jwt-secret"

# Deployment parameters, secrets included, go through a private file, never the command line.
CHRONUS_TENANT_TOKEN="$(az keyvault secret show --vault-name "$key_vault" --name "$secret_prefix-tenant-token" --query value --output tsv)" \
CHRONUS_JWT_SECRET="$(az keyvault secret show --vault-name "$key_vault" --name "$secret_prefix-jwt-secret" --query value --output tsv)" \
python3 - "$work/parameters.json" "$api_app" "$web_app" "$plan" "$registry" "$api_repository" "$web_repository" \
  "$image_tag" "$allowed_ip" "$tenant_id" "$integration_subnet" <<'PY'
import json, os, sys
(path, api_app, web_app, plan, registry, api_repo, web_repo,
 tag, allowed, tenant, subnet) = sys.argv[1:12]
parameters = {
    "apiAppName": api_app,
    "webAppName": web_app,
    "planName": plan,
    "registryName": registry,
    "apiImageRepository": api_repo,
    "webImageRepository": web_repo,
    "imageTag": tag,
    "allowedIpCidr": allowed,
    "integrationSubnetId": subnet,
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
  --name "chronus-redux-apps-$(date -u +%Y%m%d%H%M%S)" \
  --template-file "$here/app.bicep" \
  --parameters @"$work/parameters.json" \
  --query "properties.outputs" --output json
: > "$work/parameters.json"

api_host="$(az webapp show --resource-group "$resource_group" --name "$api_app" --query defaultHostName --output tsv)"
web_host="$(az webapp show --resource-group "$resource_group" --name "$web_app" --query defaultHostName --output tsv)"
echo "api: https://$api_host | web: https://$web_host (closed to the internet except: ${allowed_ip:-nobody})"

# Both apps are closed to the internet: open them to this agent only, and close them again on exit.
agent_ip="$(curl -fsS https://api.ipify.org)"
for app in "$api_app" "$web_app"; do
  az webapp config access-restriction add --resource-group "$resource_group" --name "$app" \
    --rule-name pipeline-smoke-test --action Allow --ip-address "$agent_ip/32" --priority 50 --output none
  rules_added+=("$app")
done

wait_for_200() {
  local url="$1" label="$2" code=""
  for attempt in $(seq 1 45); do
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$url" || true)"
    echo "$label attempt $attempt: HTTP $code"
    [[ "$code" == 200 ]] && return 0
    sleep 20
  done
  echo "##vso[task.logissue type=error]$label did not answer 200"
  return 1
}
wait_for_200 "https://$api_host/health/ready" "api /health/ready"

workload='{"tenant_id":"'"$tenant_id"'","workload_type":"LUCAS_PV_SCALING","representation_mode":"PV_LUCAS_COLLAPSE","payload_bytes":"base64:eyJpbmRleCI6MTB9"}'
anon="$(curl -s -o /dev/null -w '%{http_code}' --max-time 60 -X POST -H 'Content-Type: application/json' \
  -d "$workload" "https://$api_host/workloads/submit" || true)"
echo "Workload without a token: HTTP $anon (must be 401)"
[[ "$anon" == 401 ]] || { echo "##vso[task.logissue type=error]Workload without a token was not refused"; exit 1; }

az keyvault secret show --vault-name "$key_vault" --name "$secret_prefix-tenant-token" --query value --output tsv \
  | python3 -c 'import sys; sys.stdout.write("Authorization: Bearer " + sys.stdin.read().strip() + "\n")' > "$work/auth-header"
authed="$(curl -s -o "$work/result.json" -w '%{http_code}' --max-time 120 -X POST -H 'Content-Type: application/json' \
  -H @"$work/auth-header" -d "$workload" "https://$api_host/workloads/submit" || true)"
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

wait_for_200 "https://$web_host/" "web /"
proxied="$(curl -s -o /dev/null -w '%{http_code}' --max-time 60 "https://$web_host/api/chronus/health/ready" || true)"
echo "web -> api through /api/chronus/health/ready: HTTP $proxied (must be 200)"
[[ "$proxied" == 200 ]] || { echo "##vso[task.logissue type=error]The web console could not reach the api"; exit 1; }
echo "Chronus_Redux deployed and checked: api https://$api_host, web https://$web_host"
