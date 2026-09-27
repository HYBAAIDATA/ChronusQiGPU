# PYTHIA canonical MLA1517 boundary

## Product role

PYTHIA has one operational purpose: mine against a real Stratum workload to
sustain HYBA while the Enterprise product is brought to market. It is not the
Enterprise database, treasury, or customer storage system.

## Active architecture

```text
React/Vite UI
    ⇅
TypeScript Express control and Stratum API
    ⇅
mla1517_platform_v3.4
    ├── Python exact reference/control plane
    ├── C/C++ host, ring, telemetry, and persistence path
    ├── exact OpenCL kernel path
    └── negotiated Stratum adapter
```

The active implementation does not use the former M3 scaler, projected
Lucas-to-hashrate formulas, generic backend binder, fake GPU registry, or
quantum-walk demo as mining infrastructure. Those paths have been removed from
production imports.

## Measurement contract

A hashrate result is valid only when it comes from an executed device run or
from pool-accepted shares under a negotiated proof adapter. Cassini and MLA1517
invariants are internal correctness checks; they do not become Bitcoin
proof-of-work by naming convention.

The canonical ladder is exactly `10, 12, 15, 18, 20, 31, 50, 76`. The OpenCL
gate compares device output against exact reference values and fails closed on
missing hardware, mismatch, overflow, or unsupported scale.

## Claimed vs measured per capability

The composed substrate (`hyba/inventory.py` + `hyba/virtual_gpu.py`) reports a
capability only when a probe measured it on the device. The table below is the
contract: the *claimed* column is what the inventory may report, the
*measured* column is the only thing `SuperGPU.route` will route on.

| capability | claimed when | measured when |
| --- | --- | --- |
| `m32_lane_kernel` | the canonical `bitcoin_sha256d_m32` source is present | kernel source byte-checked AND OpenCL device enumerated |
| `fp64` | device extension string contains `cl_khr_fp64` | `device.get_info` returned it |
| `opencl2_svm` | — | `SVM_CAPABILITIES & 0x3` nonzero |
| `host_unified_memory` | — | `HOST_UNIFIED_MEMORY` query true |
| `local_mem_kb` / `max_workgroup` | — | device queries returned values |
| `tensor_cores` / `tf32` / `fp8` | — | `nvidia-smi` compute_cap ≥ 7.0 / 8.0 / 8.9 |
| `nvlink` / `mig_partitions` | — | live `nvidia-smi nvlink --status` / MIG mode Enabled |
| `metal` / `unified_memory` | — | `AppleSiliconRuntime.metal.available` on Darwin |
| `mmio` (ASIC) | — | `MLA1517_MMIO_LIBRARY` loaded and `mla1517_open` resolved |
| `hashlib_sha256d` / `exact_math` | always on CPU | always on CPU |
| `truth_class="design"` (RTL) | `.sv` files present under `mla1517_platform_v3.4/rtl/` or `legacy/hardware/rtl/` | design artifacts only — never hardware |

A capability not in the device's map was not measured and is treated as absent
— routing never guesses. A dispatch that ran without a derived Lucas config
attests `truth_class="unconfigured"` (see `docs/SUPER_GPU_SUBSTRATE.md`).
