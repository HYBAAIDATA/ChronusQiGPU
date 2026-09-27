# Dual Docker Desktop pool deployment

This deployment runs one PYTHIA mining container per Windows/WSL2 host. Host A
uses the Braiins profile and Host B uses the ViaBTC profile. The profiles are
mutually selectable; run only one profile on each physical host.

## Host A — Braiins

```powershell
Copy-Item .env.braiins.example .env.braiins
# Edit .env.braiins locally; do not commit it.
docker compose -f docker-compose.pools.yml --profile braiins config
docker compose -f docker-compose.pools.yml --profile braiins up -d --build
```

## Host B — ViaBTC

```powershell
Copy-Item .env.viabtc.example .env.viabtc
# Edit .env.viabtc locally; do not commit it.
docker compose -f docker-compose.pools.yml --profile viabtc config
docker compose -f docker-compose.pools.yml --profile viabtc up -d --build
```

Each profile starts two containers on that host: `pythia-main` and the
selected pool miner. `pythia-main` runs the canonical `main.py` control API;
its startup supervision starts the agentic mining runtime and Salamander
self-healing workers when `/dev/dxg` is present. The pool container owns the
production Stratum session and share submission. The selected env file is also
passed to `pythia-main` because its supervised agentic runtime needs the
Stratum identity to start cleanly.

Both containers use Docker Desktop WSL2 `/dev/dxg`, `/usr/lib/wsl`, AETHEL
execution, and OpenCL. The pool container also applies the deterministic
score-order limit and starts in dry-run mode. Pool credentials are runtime-only
through the ignored env files; the main control container does not require them.

## Verify each host

```powershell
docker compose -f docker-compose.pools.yml --profile braiins run --rm pythia-braiins clinfo
docker compose -f docker-compose.pools.yml --profile braiins logs -f pythia-braiins
```

Use `viabtc` in place of `braiins` on Host B. Confirm the device name from
`clinfo` before accepting the identity values in the env file.

Required startup evidence in the main logs:

```text
[pythia-control] agentic mining + salamander self-healing workers started
```

The main status endpoint also exposes worker state. `/readyz` is only the
control-plane liveness/readiness check; `/ready-to-mine` is the stricter
effectiveness gate:

```powershell
Invoke-RestMethod http://localhost:8377/api/v1/mla1517/status | ConvertTo-Json -Depth 8
```

Both `agentic-mining` and `salamander` must be `running`, `restarting`, or
explicitly `armed_no_device`; a missing/failed worker must not be reported as
healthy.

Required pool dry-run evidence:

```text
Stratum authorized
Job received
Execution path=AETHEL->Tensor->TURING->iGPU
Hasher backend=opencl
```

## Enable one live-share test

Only after the dry run is clean, set the three live-submit variables in the
host's ignored env file and run one bounded submission attempt:

```powershell
docker compose -f docker-compose.pools.yml --profile braiins run --rm --no-deps pythia-braiins python3 -m mining.production_miner --submit --max-runtime 3600 --max-shares 1
```

The pool's `mining.submit` response with `result=true` is the acceptance gate.
Do not infer pool acceptance from device visibility or benchmark H/s.
