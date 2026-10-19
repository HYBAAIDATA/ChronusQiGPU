# MLA1517 Platform v3.4 — PYTHIA mining product

This product-scoped drop integrates the MLA1517 exact arithmetic engine with the PYTHIA mining orchestration surface. It owns nonce/work scheduling, Stratum coordination, host-to-device control, telemetry, and mining deployment.

## Product boundary

- **Included:** exact MLA1517 state/scale primitives, OpenCL payloads, host bridge, PRIME-DB/Aethel transport, progressive mining, SIMT conformance, Salamander supervision, Stratum coordinator, and Docker deployment assets.
- **Excluded:** enterprise customer APIs, treasury/accounting workflows, and broader HYBA product surfaces. Those belong to `PHIDATA2/Enterprise`.
- **Consensus boundary:** the coordinator remains fail-closed; MLA1517/Cassini state is not represented as a valid external pool share without a negotiated algorithm adapter and normal target verification.

## v3.4 acceptance

- Python regression: 78/78 passed.
- Requirements audit: 48/48 passed.
- Rule 7 exact-core gate: passed.
- Ordinary release gate: passed.
- Strict OpenCL gate: intentionally fails closed unless a real OpenCL runtime/device is present.

## Live GPU scaling harness

`docker-compose.gpu.yml` is the explicit passthrough deployment for `scripts/measure_lucas_scaling.py`. It maps `/dev/dri`, requests `capabilities: [gpu]`, and requires a host OpenCL ICD vendor directory. The harness requires a negotiated `module:factory` adapter because an exact Lucas/Pisot result is not intrinsically a Bitcoin block-header nonce. It submits only adapter-produced candidates and counts only `result: true` responses from the pool. Missing hardware, missing target/difficulty, missing approval, adapter failure, or zero accepted shares at any rung stops the run.

Run only with an approved live adapter and credentials:

```sh
export MLA1517_ENABLE_LIVE_SUBMIT=1
export MLA1517_LIVE_APPROVAL_ID='approved-run-id'
export MLA1517_STRATUM_USER='account.worker'
export MLA1517_STRATUM_PASSWORD='pool-password'
export MLA1517_STRATUM_ADAPTER='adapter_module:factory'
export MLA1517_ADAPTER_DIR=/opt/mla1517/adapters
export MLA1517_OPENCL_VENDOR_DIR=/etc/OpenCL/vendors
docker compose -f docker-compose.gpu.yml up --build --abort-on-container-exit
```
