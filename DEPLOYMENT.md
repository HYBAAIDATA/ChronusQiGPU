# PYTHIA Deployment

PYTHIA's canonical runtime is Python. `main.py` starts the control API and
serves the built React/Vite frontend; the frontend is not a mining backend.
The Docker image builds that frontend and starts `main.py`. The canonical
mining implementation lives under `chronus/mla1517/` and
`chronus/mla1517_platform/python/`.

## Choose a deployment

### Control service

For a host with the required MLA1517 device, prepare a private `.env` from the
template and set a new operator key:

```bash
cp .env.example .env
openssl rand -hex 32
# Put the generated value in .env as EUCLID_ADMIN_API_KEY.
docker compose up --build -d
```

The root `docker-compose.yml` builds `Dockerfile`, publishes
`${PYTHIA_PORT:-3000}`, requires `EUCLID_ADMIN_API_KEY`, and maps
`${MLA1517_UIO_DEVICE:-/dev/uio0}` from the host to `/dev/uio0`. The host
device must exist; set `MLA1517_UIO_DEVICE` if it is elsewhere. Compose maps
the device node but does not set `MLA1517_MMIO_DEVICE` inside the container;
the mount alone does not arm a mining worker. Keep `.env` private and do not
commit it. The Compose file persists `/app/data` in the `pythia_data` volume.

Check the service health and logs:

```bash
curl --fail http://localhost:${PYTHIA_PORT:-3000}/api/health
docker compose logs -f pythia
```

`/api/health` reports whether the HTTP service is responding. It does not
prove that a worker is ready, a device executed work, or a pool accepted a
share. `/readyz` reports worker readiness; use the mining and Stratum status
surfaces to inspect their independent state.

This is a control-service deployment, not by itself a live-miner deployment:
the root Compose service does not pass pool credentials or configure an
explicit submission approval. State-changing requests using the admin-key
gate require the configured key as a bearer token in the HTTP Authorization
header; absent or incorrect keys fail closed.

### Live miner

Live mining is a separate, explicitly approved operation. Use the canonical
headless entry point only after configuring a real pool identity and endpoint
from `.env.example`/the pool catalog, and binding a supported execution path:

```bash
PYTHONPATH=chronus/mla1517_platform/python \
  python3 chronus/mla1517_platform/python/headless_miner.py \
  --device /dev/uio0 \
  --user "$MLA1517_STRATUM_USER" \
  --password "$MLA1517_STRATUM_PASSWORD" \
  --submit
```

`--submit` is explicit approval for this headless invocation; do not add it
until the operator has approved live submissions. The supervised control
service instead requires live-submit approval bound to the configured pool
identity. Protect that approval and the admin key as operational secrets.

For a live deployment, keep the control and mining prerequisites distinct:

- The control API needs a protected admin key for state-changing requests. A
  direct headless invocation uses its explicit `--submit` option instead.
- Live mining needs a valid Stratum worker identity, endpoint, and any
  pool-required password/TLS settings.
- Live mining needs an actual supported execution path: the MLA1517 MMIO
  device, a self-checked OpenCL device, or another explicitly supported
  backend. The CPU reference is software execution and must not be described
  as hardware execution.
- Live mining needs a real negotiated Stratum job and the corresponding
  installed proof adapter.
- Submission needs explicit operator approval, bound to the live pool
  identity where the supervised control API is used.
- A share is accepted only after the pool acknowledges the submission.

Without these conditions the runtime remains unavailable or fails closed. A
configured endpoint, a started process, a candidate nonce, or a locally
computed digest is not a pool-accepted share.

For NVIDIA hosts, `docker-compose.cuda.yml` is an override for the root
Compose file and requires the NVIDIA Container Toolkit:

```bash
docker compose -f docker-compose.yml -f docker-compose.cuda.yml up --build -d
```

It reserves `${EUCLID_CUDA_GPU_COUNT:-all}` GPUs and selects the CUDA backend.
This does not configure pool credentials, a negotiated job, or submission
approval. Other hardware and OpenCL setup must use a backend supported by the
runtime and must pass its device checks; a declared device is not evidence of
execution.

## Runtime configuration

Use the actual Python runtime names in `.env.example`:

| Variable | Purpose |
| --- | --- |
| `EUCLID_ADMIN_API_KEY` | Required operator key for privileged control changes. |
| `MLA1517_STRATUM_USER` | Pool worker identity (`account.worker`). |
| `MLA1517_STRATUM_PASSWORD` | Pool password when required; the runtime default is `x`. |
| `MLA1517_STRATUM_ENDPOINT` | Pool endpoint when overriding the catalog default. |
| `MLA1517_STRATUM_TLS` | Require TLS for a bare host/port endpoint. |
| `MLA1517_MMIO_DEVICE` | Host MLA1517 device path for the direct miner. |
| `PYTHIA_EXECUTION_DEVICE` | Supervised bridge-free `opencl` or labelled `cpu` selection; standalone mining also supports a configured `remote` backend. |
| `PYTHIA_EXECUTION_BACKEND` | SHA256d executor selection (`auto`, `cpu`, or `opencl`). |
| `PYTHIA_HOST`, `PYTHIA_PORT`, `PYTHIA_WEB_ROOT` | Python control API bind and frontend settings. |
| `HYBA_REQUIRE_HYBA`, `HYBA_DEVICE_ALIAS` | OpenCL device-identity policy. |

The Compose file also accepts `PYTHIA_PORT` and `MLA1517_UIO_DEVICE` for host
port and device mapping. It injects `EUCLID_ADMIN_API_KEY`,
`HYBA_REQUIRE_HYBA`, and `HYBA_DEVICE_ALIAS`; it does not automatically pass
every variable in `.env.example` into the container. `main.py` loads a
repository-root `.env` for direct Python runs, but `.env` is excluded from the
Docker build context.

## Evidence and capability boundary

Hashrate is reported only for executed device work or pool-accepted shares.
Lucas, Kellogg, TOE, tensor, and geometric outputs are advisory ordering,
scheduling, tensor, or research signals. They do not multiply executed
SHA256d hashes or establish a throughput result. Search ordering does not
change the SHA256d proof check or the pool's independent acceptance decision.

Use the README evidence classes without upgrading evidence by implication:

- **SOURCE VERIFIED** — implementation and source-level contract inspected.
- **SOFTWARE EXECUTION VERIFIED** — software behavior passed its tests.
- **HARDWARE EXECUTION VERIFIED** — the actual device executed and passed
  independent checks.
- **POOL VERIFIED** — a live pool acknowledged the share.
- **UNVERIFIED** — evidence has not met the applicable class above.

This documentation change does not satisfy the hardware release gate.
Promotion still requires a real-device run, independent host SHA256d
recheck, bounded live submission, literal pool acknowledgement,
restart/recovery testing, and recorded route/device provenance.
