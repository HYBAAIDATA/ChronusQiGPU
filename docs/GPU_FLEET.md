# PYTHIA GPU Fleet — vendor-agnostic dispatch (Apple / NVIDIA / HPE)

One OpenCL execution core, every vendor enumerated, exact identity per
device, fail-explicit strict mode. The SHA-256d consensus kernels execute
on `opencl` (or explicit `cpu`); Metal/CUDA/ROCm/Vulkan presence drives
container selection and is reported honestly — never claimed as execution
it does not perform.

## Enumerate (host or container)

```bash
python3 -m hyba.gpureport        # opencl + vendors + hasher + punch
python3 -m hyba.diagnose         # legacy five-section observed facts
```

`hyba.gpureport` prints one JSON doc, e.g. on the UHD 620 dev laptop:

```json
{
  "opencl": {"devices": [{"name": "Intel(R) UHD Graphics 620",
    "family": "intel-uhd-620", "dispatch": "opencl", "known": true}]},
  "vendors": {"planning_backends": ["vulkan", "opencl", "cpu"],
    "container_hint": "docker-compose.igpu-linux.yml or igpu-wsl2.yml"},
  "hasher": {"backend": "opencl:gpu", "device": "Intel(R) UHD Graphics 620"},
  "punch": {"use_opencl": true, "backend": "opencl:gpu"}
}
```

## Vendor catalog (`hyba/catalog.py`)

| Family | Vendor | PCI | Container dispatch |
|---|---|---|---|
| apple-m1..m4 | Apple | — (Metal/MLX) | native Darwin, `docker-compose.metal.yml` marker |
| intel-uhd-620 (0x5917) | Intel | `0x5917` | `igpu-linux` / `igpu-wsl2` |
| intel-iris-xe (0x9a49) | Intel | `0x9a49` | `igpu-linux` / `igpu-wsl2` |
| intel-arc (0x56a0) | Intel | `0x56a0` | `igpu-linux` |
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
| Linux iGPU | `igpu-linux.yml` | `/dev/dri` + video/render | Intel NEO (baked) |
| WSL2 iGPU | `igpu-wsl2.yml` | `/dev/dxg` + `/usr/lib/wsl:ro` | WSL lib (mounted) |
| NVIDIA/HPE | `cuda.yml` | toolkit reservation | host driver |
| AMD/HPE | `rocm.yml` | `/dev/kfd` + `/dev/dri` | ROCm ICD (baked) |
| Apple | `metal.yml` | native Darwin | system Metal |
| CPU fallback | base image | none | PoCL (baked) |

Probe any overlay: `--profile probe run --rm igpu-probe` (`clinfo`).

## Consensus boundary

In-kernel `(reversed digest < target)` + host `hashlib` re-verify on every
hit + init self-check (`0,1,0x12345678,0xFFFFFFFF`). Lucas
`effective = physical * L_n` is `projection_is_measured:false`; only
`live_mine` wall-clock `hashes_total/seconds_wall` is measured.
