# `igpu`

Production package for integrated-GPU discovery, capability binding, OpenCL
execution, telemetry and the SEAM execution layer.

## Boundaries

- Importing `igpu` is hardware-independent and does not probe devices.
- `igpu.detect` performs explicit capability discovery.
- `igpu.device` exposes the high-level device facade.
- `igpu.engine` and `igpu.opencl_host` own OpenCL execution.
- `igpu.telemetry` owns measured device/runtime evidence.
- `igpu.seam` owns scheduling, invariants, receipts and hybrid orchestration.
- `igpu.kernels` contains package-distributed OpenCL source.
- `igpu.deploy` contains reference container deployment files.

Hardware absence must remain explicit. CPU fallback, projections and design
artifacts must never be labelled as measured iGPU execution.
