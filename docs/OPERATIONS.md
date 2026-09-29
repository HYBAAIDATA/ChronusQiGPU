# Operations

Operator-facing runbook. For the mining runbook see
`docs/PRODUCTION_MINING_RUNBOOK.md`; for the audit this document was produced under,
`docs/PRODUCTION_READINESS_AUDIT.md`.

## Running the control API

```bash
python3 main.py --host 0.0.0.0 --port 3000 --web-root dist/public
```

`main.py` auto-loads `.env` (process env wins). The API exposes `/api/v1/mla1517/status`
with `canonicalEngine` (product, path, backend, ladder, execution state, hashrate policy,
`fallback: false`).

## Running the miner (hardware required)

```bash
PYTHONPATH=mla1517_platform_v3.4/python \
  python3 mla1517_platform_v3.4/python/headless_miner.py \
  --device /dev/uio0 --user <stratum-user.worker> --password x --submit
```

Or the runtime/coordinator CLIs, which now accept TLS:

```bash
python3 mla1517_platform_v3.4/python/manifold_pool_coordinator.py \
  --endpoint stratum+ssl://stratum.braiins.com:3333 --user $MLA1517_STRATUM_USER
# or bare endpoint + TLS:
python3 mla1517_platform_v3.4/python/mining_runtime.py --endpoint host:3333 --tls
```

`--tls` can also be enabled with `MLA1517_STRATUM_TLS=1`. `stratum+ssl://` and
`stratum+tls://` endpoints always use TLS; `stratum+tcp://` never does; unknown
schemes fail closed.

## Required env surface

See `.env.example` (every variable there is read by live code):

- `MLA1517_STRATUM_USER` / `MLA1517_STRATUM_PASSWORD` — canonical stratum creds
- `MLA1517_BRAIINS_ENDPOINT` / `MLA1517_VIABTC_ENDPOINT` — pool endpoints
- `MLA1517_MMIO_DEVICE` — MMIO device path
- `MLA1517_STRATUM_TLS` — `1/true/yes/on` to require TLS on bare endpoints
- `PYTHIA_HOST`, `PYTHIA_PORT`, `PYTHIA_WEB_ROOT` — control API
- `PYTHIA_BITCOIN_RPC_URL` + `PYTHIA_BITCOIN_RPC_AUTH` or `PYTHIA_BITCOIN_RPC_COOKIE` —
  optional Bitcoin node RPC for chain observation
- `PYTHIA_BITCOIN_NETWORK` — `main|test|testnet4|signet|regtest`; when set,
  `mining_runtime` fails startup unless the configured node reports the same
  chain via `getblockchaininfo` (see `BitcoinChainObserver.assert_chain`)

## Pool connectivity smoke (non-destructive)

`scripts/pool_smoke.py` verifies a stratum endpoint end-to-end — TCP/TLS
connect → `mining.subscribe` → `mining.authorize` — and optionally waits for a
`mining.notify` job. It never calls `mining.submit`.

```bash
# Sentinel worker (no credentials): expect authorize-reject on strict pools
PYTHONPATH=mla1517_platform_v3.4/python \
  python3 scripts/pool_smoke.py --endpoint stratum.braiins.com:3333 --wait-for-job 20

# Operator worker: real credentials via env
MLA1517_STRATUM_USER=<worker> MLA1517_STRATUM_PASSWORD=<pw> \
  PYTHONPATH=mla1517_platform_v3.4/python \
  python3 scripts/pool_smoke.py --endpoint stratum.braiins.com:3333
```

Output is a JSON report per endpoint; exit code is 0 only when every endpoint's
verdict is honest (`ok: true`). Pools that accept arbitrary worker names
(ViaBTC: authorization binds to the account embedded in the worker string, not
the worker itself) are reported as such — not as a honeypot failure.

## Environments

- **offline/test**: loopback stratum + `--dry-run`; no live gate needed.
- **testnet/regtest**: point endpoints at a test pool; keep submit gate off until verified.
- **staging**: real pool + real credentials + TLS + submit gate ON; verify first accepted share.
- **mainnet**: same as staging; audit `HYBA_*` env before deploy.

## Health & telemetry

- `/api/v1/mla1517/status` is the source of truth for the operator UI.
- Logs never include credentials (`StratumIdentity` holds only the password hash;
  conflict errors mask values).
- Accepted-share telemetry counts only pool-acknowledged submissions.

## Live submit approval

Live share submission requires the three `HYBA_*` gates (see `docs/SECURITY.md`).
Before enabling in staging/mainnet, confirm the approval-id is recorded and audited.
