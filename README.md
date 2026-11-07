# Chronus Quantum iGPU

Chronus is a mathematics-first, representation-aware computational substrate. Its premise is to express suitable workloads in their mathematical structure—rather than defaulting to dense expansion—and to route those workloads across available execution backends. The Lucas/Pisot–Vijayaraghavan (PV) and exact \(Q(\sqrt5)\) representations are central examples, not a claim that every workload can be reduced to constant memory or that every GPU path is already implemented.

The intended QiGPU model has two operating modes: Chronus can execute independently on its own substrate, or extend execution into client- or fleet-side accelerators. The default is a Python mathematical reference backend; an experimental OpenCL GPU adapter is available by explicit opt-in, but has not been validated on a physical device. A compatible remote execution service can also be configured.

## Architecture and operating model

- **Mathematical workload layer:** exact rational arithmetic over \(Q(\sqrt5)\) and Lucas/Fibonacci values using fast doubling.
- **Execution layer:** backend registration and workload selection; currently the built-in backend is a CPU reference implementation.
- **Service layer:** authenticated workload API, tenant-filtered access, SQLite-backed single-node workload records, health/readiness endpoints, and a synchronous SDK.
- **Extension path:** `CHRONUS_EXECUTION_BASE_URL` forwards workloads to a compatible service endpoint. This is an adapter seam, not proof of client-GPU discovery, dispatch, or scaling.

Input descriptions can remain compact, but materialized integers and exact outputs grow with the requested problem. The Lucas reference backend currently caps the index at 100,000. Performance, memory, or energy claims require workload-specific measurements on identified hardware.

## Mission posture

Chronus is a sovereign utility, not a corporate product. Its native search capability is a private, self-sustaining treasury engine that funds and protects the underlying mathematical discoveries; it is never sold or offered to clients. The mathematical substrate — Lucas/PV scaling, phyllotaxis storage, Zeckendorf folding, Galois receipts — is hardware-agnostic so that sovereign entities and enterprises can compute without dependency on any single hyperscaler.

## Market and operating footprint

Chronus is being positioned with Dubai/DIFC as headquarters and London as the go-to-market office, serving a global customer base that includes sovereign clients in the GCC. The product ambition is hardware-agnostic mathematical execution across independent Chronus capacity and customer/fleet accelerators. These are strategic positioning statements; they do not imply that a specific office, customer deployment, regulatory authorization, or accelerator integration has been independently verified in this source checkout.

## Current capability boundaries

| Capability | Current implementation |
|---|---|
| Native mathematical execution | `EXACT_Q5_ALGEBRAIC` arithmetic, `LUCAS_PV_SCALING`, exact `PV_LATTICE_FOLD`, symbolic `TRINITY_SCALE_FOLD_STORE`, and `METALLIC_SCALE` over the full metallic-means family (golden, silver, bronze, m ≤ 64). |
| Phyllotaxis storage (Ovid/Theseus) | `PHYLOTAXIS_STORE` and `THESEUS_RETRIEVE`: content-addressed storage with golden-ratio lane distribution, per-tenant query, and digest-verified reconstruction. Process-local. |
| QiGPU orchestration | Hardware-agnostic surface inventory, `auto` climb-in preference; CPU substrate always available, client-provisioned OpenCL GPU surface when opted in. |
| Zero-knowledge receipts | `OVID_NORM_PROOF`: Schnorr Sigma protocol proving knowledge of a Galois-norm preimage over F_257[φ], soundness 1/257, without revealing the witness. |
| Exact quantum evolution | `chronus.quantum.StateVector`: statevectors over F_257 with the full gate set as exact field constants (1/√2 = 30, i = 16, ω₈ = 4); circuit equivalence by integer equality. No floats, no simulated noise. |
| Configurable bounds | All operational limits (lanes, orders, payload sizes) are `CHRONUS_*` environment settings via `chronus.config.runtime_bounds()`; only protocol-defining constants are fixed. |
| Phi-ALU RTL | `hw/zeckendorf_norm_alu.sv` + `hw/zeckendorf_alu_32lane.sv`: synthesizable norm unit and full 32-lane carry-free Zeckendorf ALU array; Icarus testbenches + Yosys synthesis in CI (8,095 pure-logic cells, no multipliers or carry chains). |
| Sovereign console | Authenticated `/console` dashboard: live surfaces, phyllotaxis lane density, spiral map, workload counters. |
| Hardware-agnostic backend seam | Python protocol, registry, named selection, optional remote forwarding, and experimental opt-in OpenCL GPU adapter; no GPU adapter is registered by default or verified on physical hardware here. |
| Workload API and SDK | Bearer-token authentication, base64-safe payloads, synchronous workload execution, tenant-checked retrieval/listing, health/readiness, and metrics. |
| Workload persistence | SQLite records survive process restart on a single node; this is not multi-region or distributed storage. |
| Receipts | Process-local Ed25519 receipts; signing keys and receipt records are not durable across restart. |
| ML-DSA and STARK/FRI | Not implemented as conformant signing or proof verification. No production or compliance claim is made for these paths. |
| Release qualification | No executable package-level release-gate suite is present. Test results are reported as tests, not as production qualification. |

See the [current architecture and market model](docs/system-update/architecture-and-market.md), [implementation assessment](docs/system-update/current-state-assessment.md), and [test evidence](docs/system-update/test-evidence.md).

## Development setup

Requires Python 3.10 or later.

```bash
git clone https://github.com/hybadatadevops1/Chronusv2.git
cd Chronusv2
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Run the implemented test suite:

```bash
python -m pytest -q
```

## Run the API locally

Configure a development tenant token before starting the process:

```bash
export CHRONUS_TENANT_TOKENS='{"demo":"replace-with-a-local-development-token"}'
uvicorn chronus.service.app:app --host 127.0.0.1 --port 8000
```

Submit an exact Lucas/PV reference workload:

```bash
curl -sS http://127.0.0.1:8000/workloads/submit \
  -H 'Authorization: Bearer replace-with-a-local-development-token' \
  -H 'Content-Type: application/json' \
  -d '{
    "tenant_id": "demo",
    "workload_type": "LUCAS_PV_SCALING",
    "representation_mode": "PV_LUCAS_COLLAPSE",
    "payload_bytes": "base64:eyJpbmRleCI6MTB9"
  }'
```

The base64 payload decodes to `{"index":10}`. The response includes the selected backend, execution state, exact decimal strings for Fibonacci/Lucas values, and the Lucas identity. API documentation is available at `/docs`; liveness/readiness are at `/health/live` and `/health/ready`.

Set `CHRONUS_WORKLOAD_DB_PATH` to choose a SQLite file. Set `CHRONUS_EXECUTION_BASE_URL` to forward supported workloads to a compatible remote service exposing `/health/ready` and `/workloads/submit`. Treat both environment settings as deployment configuration, not as evidence of high availability or physical accelerator operation.

## Security and release posture

Tenant tokens are configured as a JSON environment variable for this implementation; production provisioning, rotation, and federated identity are not included. Do not use the development setup for sensitive workloads. Ed25519 keys and receipts are process-local. ML-DSA requests return `501`, STARK verification returns false, and the polynomial identity helper is not a proof verifier. The service does not assert regulatory authorization, production qualification, or certified hardware execution.

## Documentation

- [Executive architecture and project summary](docs/executive/executive-architecture-and-project-summary.md)
- [Architecture and market model](docs/system-update/architecture-and-market.md)
- [Current implementation assessment](docs/system-update/current-state-assessment.md)
- [Test evidence and limitations](docs/system-update/test-evidence.md)
- [Governance and acceptance controls](docs/system-update/governance-and-acceptance.md)
- [Azure deployment foundation](docs/system-update/azure-deployment.md)
- [Native nonce search and accelerator integrity](docs/system-update/mining-and-accelerators.md)
- [QiGPU, Chronus, Theseus and Ovid unified system](docs/system-update/qigpu-storage.md)
- [Market-ready elevations: RTL, norm proofs, climb-in, console](docs/system-update/elevations.md)
- [The metallic means family](docs/system-update/metallic-means.md)
- [Beyond quadratic: the metallic search experiment](docs/system-update/after-quantum.md)
- [Four-phase integration status](docs/system-update/integration-plan.md)
- [Historical reports](docs/reports/README.md)
