# HYBA Mine deployment

HYBA Mine is HYBA's internal mining operation. It is never offered to customers.
The code lives in this repository; the miner runs on HYBA's Azure mining host
(`vm-qigpu-miner`, UK West), never on GitHub: GitHub's terms prohibit
cryptomining in Actions, on GitHub-hosted and self-hosted runners alike.

## What runs

- The documented miner image (`Dockerfile`, target `miner-runtime`, the same image
  as `docker compose --profile miner`), with `runner.py` and `bist.py` added
  (`deploy/hyba-mine/Dockerfile`).
<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:f1342fac041fa268a85d9839779e6bc87dd24a24b246c0854bd6426a0964ea9e -->

- `runner.py` runs the canonical Stratum V1 miner
  (`chronus.execution.mining_entrypoint.ChronusRealMiningEngine`) with startup
  self-test and session supervision, plus one `[STATS]` line a minute with the
  miner's counters. See [search integration and readiness](READINESS.md) for
  TURING, Hendrix, geometric/Galois wiring and remaining release gates.

<!-- /coderabbit-ai-generated:v1 -->
- `bist.py` is the built-in self-test: known-answer checks of the miner's own hash
  path against blocks 0 and 1 (coinbase and merkle root, prevhash word order,
  80-byte header, SHA-256d, share and network targets, version rolling, and the
  pre-submission gatekeeper). No BIST pass, no stratum connect.
- A share counts only when the pool accepts it (`[POOL SUCCESS]` lines). Hashing
  counts in `[STATS]` are local measurements.

## How to operate it

Edit `control.env` on branch `hyba-mine/control` and push:

    HYBA_MINE_ACTION=start   # start | stop | status
    HYBA_MINE_POOL=viabtc    # viabtc | braiins

The push runs `.github/workflows/hyba-mine.yml`, which builds the image, runs the
self-test with networking disabled, pushes the image to the private registry and
acts on the mining host through Azure run-command (`vm-hyba-mine.sh`). The
workflow log shows the host's report: container state, handshakes, shares
submitted, accepted and rejected by the pool, and the latest statistics.

## Credentials

- Azure sign-in: OpenID Connect to the managed identity `id-hyba-mine-github`
  (AcrPush on `crcronusqigpudemohybadata`, Virtual Machine Contributor on
  `vm-qigpu-miner`), trusted only for `refs/heads/hyba-mine/control` and
  `refs/heads/main` of this repository. No secret is stored in GitHub.
- Pool logins (`pool-<pool>-worker`, `pool-<pool>-password`) and the registry pull
  password stay in Key Vault `kv-cronusqigpu-demo-hyba`. The host reads them with
  its own managed identity into a 0600 file that Docker reads once; they are never
  printed.

## Pools

ViaBTC (`btc.viabtc.io:3333`) and Braiins (`stratum.braiins.com:3333`), as in the
pool catalogue. NiceHash and ckpool are added when their logins are in Key Vault
and the miner's pool settings accept them.
