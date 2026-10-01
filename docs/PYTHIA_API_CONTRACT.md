# PYTHIA Python API contract

PYTHIA has one active mining control path: the Python backend under
`chronus/mla1517_platform/python`. The React/Vite frontend is an operator surface
only; it does not calculate hashes, construct Stratum jobs, decide share
validity, or submit shares.

## Read-only endpoints

| Endpoint | Meaning |
| --- | --- |
| `GET /api/health` | Python control API is serving. |
| `GET /api/v1/readyz` | Control API readiness. This is not a hardware or pool-acceptance claim. |
| `GET /api/v1/mla1517/status` | Discovered devices and the configured execution boundary. |
| `GET /api/v1/telemetry/summary` | Observed telemetry only; unavailable values remain unavailable. |

The frontend must use `src/lib/api.ts` for these requests. Any endpoint that
would claim pool acceptance, accelerator execution, or hashrate must be backed
by an observed runtime record and must expose its truth class. The absence of an
OpenCL device is displayed as unavailable/degraded; it is never relabelled as
GPU, iGPU, FPGA, or measured hardware execution.

## Mining authority

The Python adapter in
`chronus/mla1517/mining/stratum_adapter.py` is the proof
boundary. It consumes a live subscription and `mining.notify` job, constructs
the coinbase, Merkle root, 80-byte header, and SHA256d digest, and returns
`mining.submit` parameters only after the negotiated target check succeeds.

The frontend is not a mining client. It must not contain Stratum methods,
Bitcoin hashing, target comparisons, synthetic pool acknowledgements, or
fabricated hashrate values.
