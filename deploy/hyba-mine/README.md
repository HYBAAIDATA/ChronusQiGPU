# HYBA Mine deployment

HYBA Mine is HYBA's internal mining operation. It is never offered to customers
and nothing in this folder ships in a product distribution: lifting mining out
means removing `deploy/hyba-mine/` and `.github/workflows/hyba-mine.yml`. The code
lives in this repository; the miner runs on HYBA's Azure mining host
(`vm-qigpu-miner`, UK West), never on GitHub: GitHub's terms prohibit cryptomining
in Actions, on GitHub-hosted and self-hosted runners alike.

## What runs

- The documented miner image (`Dockerfile`, target `miner-runtime`) with the HYBA
  Mine layer (`deploy/hyba-mine/Dockerfile`): the CPU OpenCL runtime (PoCL), the
  `hyba_mine` package, `runner.py`, `bist.py` and the miner's tests.
- `hyba_mine/lanes.py`: SHA-256d search over every lane of the host. The OpenCL
  iGPU lanes run the packaged kernel (`chronus/kernels/sha256d_search.cl`) on every
  compute unit; on this host that is the CPU device, so the QiGPU runs in Mode A on
  CPU silicon. The process lanes run one process per available CPU. A lane set is
  used only after its results equal the host reference on known-answer windows
  (the genesis nonce at difficulty 1, an easy-target window on block 1, a target no
  hash can meet). Each qualified set is calibrated and the faster one takes the
  whole host.
- `hyba_mine/search.py`: replaces only the canonical engine's nonce search
  (`chronus.execution.mining_entrypoint.ChronusRealMiningEngine`); the pool
  session, job handling, gatekeeper and submission are the engine's own. Every
  lane hit is rechecked on the host, and again by the gatekeeper before submission.
- `hyba_mine/campaign.py`: the two-block campaign (below).
- Capacity (`chronus.fleet.capacity`, invariant I64) is logged once a minute as
  `[CAPACITY]`: discovered, available and allocated lanes, the calibrated rate and
  the measured rate, each from its own source.
- `bist.py`: known-answer checks of the miner's own hash path against blocks 0 and
  1, the lane qualification and the block-height reader. No BIST pass, no stratum
  connect.
- A share counts only when the pool accepts it (`[POOL SUCCESS]` lines). Hashing
  counts are local measurements.

## The campaign

1. Stage 1 mines on the first pool from the first job it sends (block height N)
   until that pool accepts a share or the network moves past N.
2. Stage 2 connects to the second pool and cools down (no hashing) until a job for
   height N + 2 or later arrives, so the two blocks are not consecutive, then mines
   that block until the second pool accepts a share or the network moves on.
3. Hashing stops, the pool session closes and the container exits; it is not
   restarted, so the host is offline for mining. `HYBA_MINE_MAX_RUN_SECONDS` bounds
   the whole campaign.
4. The workflow then examines the host for any attempt to look inside the miner:
   exec, attach, copy, export or top on the container, files changed in it, pool
   methods outside Stratum V1 mining (`[POOL PUSH] UNEXPECTED`), SSH attempts,
   logins, listening services and run-command executions, plus the Azure activity
   on the resource group in the same window.

## How to operate it

Edit `control.env` on branch `hyba-mine/control` and push:

    HYBA_MINE_ACTION=campaign        # campaign | status | stop | examine
    HYBA_MINE_POOLS=viabtc,braiins   # stage order, one block each
    HYBA_MINE_MAX_RUN_SECONDS=14400  # upper bound for the whole campaign

The push runs `.github/workflows/hyba-mine.yml`, which builds the image, runs the
self-test and the miner's tests with networking disabled, pushes the image to the
private registry, starts the campaign through Azure run-command
(`vm-hyba-mine.sh`), follows it until it ends, runs the examination and writes the
report to `hyba-mine/runs/` on the private results branch.

## Credentials

- Azure sign-in: OpenID Connect to the managed identity `id-hyba-mine-github`
  (Reader on the mining resource group, AcrPush on `crcronusqigpudemohybadata`,
  Virtual Machine Contributor on `vm-qigpu-miner`), trusted only for
  `refs/heads/hyba-mine/control` and `refs/heads/main` of this repository. No
  secret is stored in GitHub.
- Pool logins (`pool-<pool>-worker`, `pool-<pool>-password`) and the registry pull
  password stay in Key Vault `kv-cronusqigpu-demo-hyba`. The host reads them with
  its own managed identity into a 0600 file that Docker reads once; they are never
  printed.

## Pools

ViaBTC (`btc.viabtc.io:3333`) and Braiins (`stratum.braiins.com:3333`), as in the
pool catalogue. NiceHash and ckpool are added when their logins are in Key Vault
and the miner's pool settings accept them.
