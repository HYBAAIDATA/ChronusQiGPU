# PYTHIA production mining runbook

This is the operational path for Stratum V1 SHA-256d mining. It is separate
from the research/frontend control plane and accepts a share only after an
independent exact SHA-256d target check.

## Pre-flight

```bash
python scripts/audit_production_contracts.py
python scripts/benchmark_hashrate.py --backend opencl --batch 1000000 --iterations 5
pytest -q tests/test_production_miner.py tests/test_device_identity_contract.py tests/test_hash_pipeline.py
```

The benchmark is offline. It must report `consensus_vector_passed: true`,
`errors: []`, and a non-zero measured rate. `--backend opencl` is required for
a hardware claim; `auto` may deliberately select the CPU reference when the
hardware gate is not strict.

## Configuration

Use a secret manager or a local ignored `.env`; never commit credentials.

```bash
export PYTHIA_STRATUM_ENDPOINT='stratum+ssl://pool.example:443'
export PYTHIA_STRATUM_WORKER='account.worker'
export PYTHIA_STRATUM_PASSWORD='pool-password'
export PYTHIA_EXECUTION_PATH='aethel'
export PYTHIA_HASH_BACKEND='opencl'
export PYTHIA_TURING_QUBITS=10000
export PYTHIA_NONCE_WINDOW=1048576
export HYBA_REQUIRE_HYBA=1
export HYBA_DEVICE_VENDOR=Intel
export HYBA_DEVICE_PCI_IDS=0x5917
export HYBA_DEVICE_NAME="Intel(R) Graphics [0x5917]"
export HYBA_ENABLE_LIVE_SHARE_SUBMIT=true
export HYBA_LIVE_SHARE_APPROVAL_ID='approved-change-id'
export HYBA_AUTONOMOUS_EXTERNAL_ACTIONS=true
```

## Live workflow

Dry-run connects, subscribes, authorizes, receives jobs, constructs headers,
and searches without submitting:

```bash
python -m mining.production_miner --dry-run --max-runtime 120
```

Live submission requires both the command flag and the explicit environment
gate:

```bash
python -m mining.production_miner --submit --max-runtime 3600
```

For ordered failover, set `PYTHIA_POOL_SPECS` to semicolon-separated
`endpoint|worker|password` entries. Credentials are read at runtime and never
written to Git:

```bash
export PYTHIA_POOL_SPECS="stratum+tcp://btc.viabtc.io:3333|ACCOUNT.WORKER|PASSWORD;stratum+tcp://stratum.braiins.com:3333|ACCOUNT.WORKER|PASSWORD"
```

With `PYTHIA_EXECUTION_PATH=aethel`, the production executor is the
AETHEL store -> Tensor fold -> symbolic TURING schedule -> iGPU/OpenCL
SHA-256d path. `PYTHIA_EXECUTION_PATH=direct` is retained only for
conformance isolation. The client implements TLS, correlated JSON-RPC requests, subscription,
authorization, difficulty/target updates, extranonce updates, job replacement,
clean-jobs handling, stale-job suppression, bounded reads/writes, reconnect
backoff, and accepted/rejected accounting.

## Acceptance evidence

Production status is not `mining successfully` until logs contain all of:

```text
Stratum authorized
Job received
Execution path=AETHEL->Tensor->TURING->iGPU
Hasher backend=opencl
Share result accepted=True
```

A measured hashrate alone proves only kernel execution. A pool's positive
`mining.submit` response is the authority for share acceptance.
