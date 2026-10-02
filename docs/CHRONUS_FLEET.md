# PYTHIA GPU Fleet — vendor-agnostic dispatch (Apple / NVIDIA / HPE)

One OpenCL execution core, every vendor enumerated, exact identity per
device, fail-explicit strict mode. The SHA-256d consensus kernels execute
on `opencl` (or explicit `cpu`); Metal/CUDA/ROCm/Vulkan presence drives
container selection and is reported honestly — never claimed as execution
it does not perform.

## Enumerate (host or container)

```bash
python3 -m chronus.report        # opencl + vendors + hasher + punch
python3 -m hyba.diagnose         # legacy five-section observed facts
```

`chronus.report` prints one JSON doc, e.g. on the UHD 620 dev laptop:

```json
{
  "opencl": {"devices": [{"name": "Intel(R) UHD Graphics 620",
    "family": "intel-uhd-620", "dispatch": "opencl", "known": true}]},
  "vendors": {"planning_backends": ["vulkan", "opencl", "cpu"],
    "container_hint": "docker-compose.chronus-linux.yml or chronus-wsl2.yml"},
  "hasher": {"backend": "opencl:gpu", "device": "Intel(R) UHD Graphics 620"},
  "punch": {"use_opencl": true, "backend": "opencl:gpu"}
}
```

## Vendor catalog (`hyba/catalog.py`)

| Family | Vendor | PCI | Container dispatch |
|---|---|---|---|
| apple-m1..m4 | Apple | — (Metal/MLX) | native Darwin, `docker-compose.metal.yml` marker |
| intel-uhd-620 (0x5917) | Intel | `0x5917` | `chronus-linux` / `chronus-wsl2` |
| intel-iris-xe (0x9a49) | Intel | `0x9a49` | `chronus-linux` / `chronus-wsl2` |
| intel-arc (0x56a0) | Intel | `0x56a0` | `chronus-linux` |
| nvidia-t4/l4/a10/l40s/h100/rtx4090 | NVIDIA | per-SKU | `docker-compose.cuda.yml` |
| amd-mi210/mi300x/780m | AMD/HPE | per-SKU | `docker-compose.rocm.yml` |
| hyba-mla1517 | HYBA | name-alias | strict `HYBA_REQUIRE_HYBA=1` fabric |

Unknown silicon → `known:false`, `dispatch:cpu` — reported, never invented.

## Strict vs dev gates

```bash
# Production fabric: refuse non-HYBA silicon
HYBA_REQUIRE_HYBA=1 HYBA_DEVICE_ALIAS=hyba-mla1517,hyba_mla1517,mla1517,hyba
# Dev laptop (UHD 620): bind the enumerated iGPU explicitly
HYBA_REQUIRE_HYBA=0 HYBA_DEVICE_ALIAS=intel \
  HYBA_DEVICE_VENDOR=Intel HYBA_DEVICE_PCI_IDS=0x5917
```

## Container matrix

| Target | Overlay | Device | ICD |
|---|---|---|---|
| Linux iGPU | `chronus-linux.yml` | `/dev/dri` + video/render | Intel NEO (baked) |
| WSL2 iGPU | `chronus-wsl2.yml` | `/dev/dxg` + `/usr/lib/wsl:ro` | WSL lib (mounted) |
| NVIDIA/HPE | `cuda.yml` | toolkit reservation | host driver |
| AMD/HPE | `rocm.yml` | `/dev/kfd` + `/dev/dri` | ROCm ICD (baked) |
| Apple | `metal.yml` | native Darwin | system Metal |
| CPU fallback | base image | none | PoCL (baked) |

Probe any overlay: `--profile probe run --rm chronus-probe` (`clinfo`).

## Remote GPU agents (`chronus.mla1517.remote_gpu_agent`)

A GPU that lives on another host joins the fleet over HTTP
(`remote_opencl_v1`); the client re-verifies every result against exact
arithmetic, so the network hop cannot weaken the proof.

```bash
# on the GPU host (any vendor — the agent binds what the driver gives it)
python -m chronus.mla1517.remote_gpu_agent --host 0.0.0.0 --port 8632
# on the miner
export MLA1517_REMOTE_GPU_ENDPOINT=http://<host>:8632     # one agent
export HYBA_REMOTE_OPENCL_ENDPOINTS=http://a:8632,http://b:8632  # a fleet
export MLA1517_REMOTE_GPU_TOKEN=<shared bearer>           # optional gate
export MLA1517_REMOTE_GPU_TIMEOUT=120                      # per-dispatch cap (s)
```

Routes: `GET /v1/health` · `GET /v1/devices` · `GET /v1/telemetry` ·
`POST /v1/ladder` · `POST /v1/sha256d` (orders `contiguous`, `m32`,
`batch`; wire caps 2^24 nonces per window, 2^20 per batch list).

With several endpoints configured, `mining.remote_hasher.hasher_for_env`
binds `RemoteFleetHasher`: each dispatched window slices into disjoint
sub-ranges executed in parallel — per-slice order preserved (m32 slices
stay whole 32-lane sweeps), merged winner = earliest slice's verified
winner, and any slice failure fails the call rather than claim partial
coverage. `/v1/telemetry` reports temperature/power/utilization only
where a vendor probe on the agent host actually measured them — every
field null otherwise, with a `sources` audit trail per probe.

## Consensus boundary

In-kernel `(reversed digest < target)` + host `hashlib` re-verify on every
hit + init self-check (`0,1,0x12345678,0xFFFFFFFF`). Lucas
`effective = physical * L_n` is `projection_is_measured:false`; only a
route's measured window rate is measured (the world model's `hash_rate_hs`
per route, published as `mining.world` at `/api/v1/knowledge`).
