# Production mining runbook

The canonical path is one supervisor per host: `main.py` starts the control
API (`mla1517_platform_v3.4/python/control_api.py`), which supervises three
workers: `agentic-mining` (`mining_runtime.py`), `salamander` and
`discovery`. The retired `mining/production_miner.py` flow lives in
`legacy/` and is not used.

## Before the first run

```bash
python -m flake8 --count
python -m pytest tests/ -q
(cd mla1517_platform_v3.4/python && python -m pytest -q)
python -m scripts.deploy_sentry
python scripts/import_audit.py
```

## Configuration

Credentials live in an ignored env file or a secret manager, never in Git.
Start from `.env.example`; two variables are required:

```bash
MLA1517_STRATUM_USER='account.worker'           # the pool worker identity
EUCLID_ADMIN_API_KEY="$(openssl rand -hex 32)"  # the operator key
```

Pools come from the pool catalog: `PYTHIA_POOL_PROFILE` picks the primary
and `PYTHIA_POOLS` the failover order (see `pool_catalog.py`). The device is
`MLA1517_MMIO_DEVICE`; `PYTHIA_EXECUTION_BACKEND=auto|cpu|opencl` picks the
SHA256d executor, and `HYBA_REQUIRE_HYBA=1` with `HYBA_DEVICE_ALIAS` refuses
any OpenCL device that is not the declared one. The operating policy sizes
windows itself, within `PYTHIA_MAX_WINDOW_SECONDS` (default 2 s).

## Start: shadow first

```bash
python main.py
```

`/api/v1/mining/*` is an AL HARAS-mediated privileged route — it does not take
the operator key. Start it from the operator console (`frontend/`, Runtime
control), which supplies the subscription Bearer token plus `X-HYBA-Tenant` /
`X-HYBA-Actor` headers and the `observation` block mutating privileged calls
require. Direct calls must carry the same headers and a minted subscription
token (`al_haras.entitlements.SubscriptionAuthority`); anything else is denied
with an evaluated 400/402/403 — never silently accepted.

A started worker mines in **shadow** until live submission is approved. It
connects, authorizes, receives jobs, and hashes with full SHA256d and target
checks. It finds, records and learns from proof-checked shares, but writes
nothing to the pool.

- `GET /api/v1/mining/evidence` reports `"submission": "shadow"`.
- `GET /api/v1/knowledge` shows what the miner has measured (`mining.world`:
  each route's hash rate and overhead) and how its learning stands
  (`learning.*`).

Shadow evidence to capture before going live:

- `/api/v1/mla1517/status`: the three workers `running`;
- `/api/v1/mining/evidence`: `execution_backend.route` is the expected
  device, `last_execution.executed` is true, shares appear in the session
  share log;
- `/api/v1/knowledge`: `learning.shares.follow.work` reports `holds`, meaning
  shares arrive at the rate the work predicts; an `anomaly` stops the run.

## Live submission

Approve it in the operator UI (Runtime control, live submit), or:

```bash
curl -X PUT -H "Authorization: Bearer $EUCLID_ADMIN_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"live_submit": {"enabled": true}}' \
     http://127.0.0.1:3000/api/v1/config
```

`PUT /api/v1/config` is a non-privileged mutating route and does take the
operator key (`mining/*` does not — see above). Out-of-bounds values
(`solvers.arms` outside [1,600], `hashrate.target_hs` outside [0,1e18],
unknown sections, malformed pool endpoints) are rejected with 400 and
nothing is persisted.

- **Binding:** the approval is bound to the enabled pool's endpoint and
  worker.
- **When it applies:** the worker re-reads it within 5 s and submits only
  while it is connected to exactly that identity. Switching pools revokes it.
- **What changes:** the evidence then reports `"submission": "live"`.
- **Acceptance:** the pool's `mining.submit` result, never device visibility
  or a benchmark.

## Stop

Stop via the operator console (Runtime control) — `/api/v1/mining/stop` is
privileged and needs the same subscription credential flow as start.

Workers finish their window and stop. On WSL2, always stop mining this way
before stopping the container: a stop that lands during an OpenCL call can
wedge the device. Stopping the whole API (`SIGTERM`, `CTRL_BREAK`, or
`SIGINT`) runs graceful cleanup and a `shutdown_signal` audit entry.

## Campaigns

`POST /api/v1/campaign/start` (operator key) runs the configured campaign
phases; `POST /api/v1/campaign/stop` retires all worker arms on every exit
path — operator stop, phase failure or completion — and the terminal record
(`GET /api/v1/campaign/status`) carries the phase results plus `retired`.
A stop lands as terminal `"stopped"`, never `"error"`. With no mining
device the config still applies and arms stay honestly `armed_no_device`
with `measured_hs_avg: null` (unmeasured, not zero).

## Stop conditions

Stop immediately if any of these happen:

- the device identity is not exact, or falls back to CPU under
  `HYBA_REQUIRE_HYBA=1`;
- the kernel self-check fails;
- a candidate fails the independent SHA256d recheck;
- `learning.shares.follow.work` reports an anomaly;
- the hashrate governor reports the network cap binding unexpectedly.
