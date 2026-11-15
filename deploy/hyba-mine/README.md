# HYBA Mine: local validation before deployment

Hosting is undecided. Docker is the initial validation environment, with Braiins
as the pool under test. Azure scripts in this folder are historical optional
adapters, not an active deployment path or evidence of a running host.

## Repeatable local checks

From the repository root:

```bash
docker build --target mining-check -t chronus-mining-check .
docker run --rm --network none chronus-mining-check
```

This runs the packaged mining self-test, endpoint configuration regressions,
core Stratum lifecycle tests and HYBA Mine synthetic-pool session/runtime tests.
Loopback sockets work with `--network none`; no real pool is contacted. Synthetic
share acceptance is not evidence of Braiins acceptance or mining performance.

If the build environment uses a private certificate authority, supply its trusted
CA bundle as a BuildKit secret (certificate verification remains enabled):

```bash
docker build --secret id=build_ca,src=/path/to/trusted-ca-bundle.pem \
  --target mining-check -t chronus-mining-check .
```

## Bounded live Braiins test

Build the canonical runner, copy the example outside the checkout, and replace
`YOUR_BRAIINS_USERNAME.docker-test` with your real Braiins account and worker.
`PYTHIA_POOL_SPECS`, when set, overrides `MINING_ACTIVE_POOL` and its settings.
Braiins uses plain Stratum V1 TCP on port 3333 (backup 443); do not require TLS
for this profile.

```bash
docker build --target miner-runtime -t chronus-braiins .
cp deploy/hyba-mine/braiins.env.example /tmp/chronus-braiins.env
chmod 600 /tmp/chronus-braiins.env
# Edit /tmp/chronus-braiins.env before running the following command.
timeout --signal=TERM --kill-after=30s 120s docker run --rm --init \
  --name chronus-braiins-test --env-file /tmp/chronus-braiins.env chronus-braiins
```

Use a host with outbound access to the pool. A timeout is a test bound, not a
success signal. Inspect logs separately for TCP connection, authorization,
`mining.notify`, submitted shares and matching accepted-share replies. A short
run may receive jobs without finding any share. Stop the test container with
`docker stop chronus-braiins-test` if the client is interrupted.

No deployment, registry, cloud identity or restart policy is selected by these
commands. Live credentials belong in the operator's local file or credential
store, never in the repository or image.

## What runs

- The documented miner image (`Dockerfile`, target `miner-runtime`) with the HYBA
  Mine layer (`deploy/hyba-mine/Dockerfile`): the CPU OpenCL runtime (PoCL), the
  `hyba_mine` package, `runner.py`, `bist.py` and the miner's tests.
- `hyba_mine/lanes.py`: SHA-256d search over every lane of the host. The OpenCL
  iGPU lanes run the packaged kernel (`chronus/kernels/sha256d_search.cl`) on every
  compute unit; PoCL executes on CPU silicon; actual device availability and execution
  must be established on each test host. The process lanes run one process per available CPU. A lane set is
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
- The canonical engine runs its self-test before connecting. See
  [search integration and readiness](READINESS.md) for the documented integration
  and remaining release gates.
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

## Historical deployment adapters

The empty `.github/workflows/hyba-mine.yml` has been deleted. `control.env` and
`vm-hyba-mine.sh` are retained as historical adapters; they are not used by the
local validation commands. The owner hold in `control.env` remains in place.

## Pools

The canonical runner defaults to Braiins. The optional campaign runner defaults
to `viabtc,braiins`; a Braiins-only campaign requires `HYBA_MINE_POOLS=braiins`
and all four `MINING_BRAIINS_*` values, including `PASSWORD=x`. The local commands
above use the canonical runner, not the optional campaign.
