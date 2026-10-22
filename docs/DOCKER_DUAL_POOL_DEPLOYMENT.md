# Dual Docker Desktop pool deployment

One PYTHIA supervisor per Windows/WSL2 host. Host A mines at Braiins and
Host B at ViaBTC.

- **Container:** each host runs the single `pythia-main` container from
  `docker-compose.pools.yml`.
- **Workers:** that container supervises the mining, Salamander and discovery
  workers in-process.
- **Caps:** one supervisor per device means one hashrate governor, so the
  operator cap and the 1%-of-network cap hold for the whole host.

## Host A — Braiins

```powershell
Copy-Item .env.example .env.braiins
# Edit .env.braiins locally (do not commit it):
#   MLA1517_STRATUM_USER=<account.worker>
#   EUCLID_ADMIN_API_KEY=<openssl rand -hex 32>
#   PYTHIA_POOL_PROFILE=braiins
docker compose -f docker-compose.pools.yml config
docker compose -f docker-compose.pools.yml up -d --build
```

## Host B — ViaBTC

```powershell
Copy-Item .env.example .env.viabtc
# As above, with PYTHIA_POOL_PROFILE=viabtc
$env:PYTHIA_MAIN_ENV_FILE = ".env.viabtc"
docker compose -f docker-compose.pools.yml up -d --build
```

## Verify each host

```powershell
docker exec pythia-main clinfo
Invoke-RestMethod http://localhost:8377/api/v1/mla1517/status | ConvertTo-Json -Depth 8
```

Confirm the device name from `clinfo` before accepting the identity values
in the env file. `/readyz` is the control plane's readiness; the stricter
effectiveness gate is `/api/v1/ready-to-mine`.

## Start in shadow, then go live

```powershell
$h = @{ Authorization = "Bearer $env:EUCLID_ADMIN_API_KEY" }
Invoke-RestMethod -Method Post -Headers $h http://localhost:8377/api/v1/mining/start
Invoke-RestMethod http://localhost:8377/api/v1/mining/evidence | ConvertTo-Json -Depth 8
```

The worker starts in shadow (`"submission": "shadow"`): real jobs, real
SHA256d, shares found and recorded, nothing written to the pool.

- **Going live:** when the shadow evidence is clean, approve live submission
  in the operator UI. The approval binds to the host's enabled pool and
  worker.
- **Acceptance:** the pool's `mining.submit` result.

## Stop

```powershell
Invoke-RestMethod -Method Post -Headers $h http://localhost:8377/api/v1/mining/stop
docker stop pythia-main
```

Always stop mining through the API first: on WSL2 a container stop during an
OpenCL call can wedge the device.


## Hardware-free local qualification

Use the **complete** `docker-compose.local.yml` profile, not a merge with the
MMIO profile. It declares no `/dev/uio0`, `/dev/dri` or NVIDIA passthrough.

Provide these values privately in the shell or an ignored, access-restricted
local env file: `EUCLID_ADMIN_API_KEY`, `PYTHIA_IDENTITY_HMAC_SECRET`,
`MLA1517_BRAIINS_USER`, `MLA1517_BRAIINS_PASSWORD`, `MLA1517_VIABTC_USER` and
`MLA1517_VIABTC_PASSWORD`. Use a strong admin key and a random 32-byte hex
heartbeat key. Pool worker passwords are separate from administrative keys.
Do not commit or paste expanded `docker compose config` output: it contains
resolved secrets. Do not reuse the primary pool's worker identity for failover.

```sh
docker compose --env-file .env.local -f docker-compose.local.yml config --quiet
docker compose --env-file .env.local -f docker-compose.local.yml up -d --build
curl --fail http://127.0.0.1:3000/api/health
```

The profile selects the canonical `chronus` mining backend and independent
software-defined GPU. It enables no live authorization and starts with the
normal shadow/submission gates. Check `/api/v1/mla1517/status`, execution
receipts and `/api/v1/ready-to-mine`; a healthy HTTP process is not mining
readiness. Existing persistent config takes precedence, so verify
`execution.mode=independent` through the authenticated config API. No fixed
rate is promised: target zero uses available execution capacity under policy.

Climb/scale mode requires `execution.mode=scale_stack`, a real executable physical
adapter and host-specific passthrough/qualification. It must refuse an absent
adapter, not relabel software work as a physical execution or scaling result.
TOE's non-mining capabilities remain available under their own qualifications.
