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
