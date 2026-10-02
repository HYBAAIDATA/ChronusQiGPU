# Chronus on an Intel integrated GPU

Chronus uses the host's installed OpenCL ICD and a physical GPU/accelerator.
It does not emulate a GPU and never silently labels CPU execution as Chronus.

## Bind the Intel iGPU

UHD 620:

```bash
export HYBA_REQUIRE_HYBA=0
export HYBA_DEVICE_VENDOR=Intel
export HYBA_DEVICE_ALIAS=intel,uhd
export CHRONUS_OPENCL_DEVICE="UHD Graphics 620"
python3 -m chronus.report
```

UHD 630 uses the same setup with
`CHRONUS_OPENCL_DEVICE="UHD Graphics 630"`. `CHRONUS_OPENCL_PLATFORM` can
additionally constrain the OpenCL platform. If an explicit identity is absent,
Chronus fails closed rather than choosing another device.

## Execution behaviour

- Only OpenCL GPU/accelerator devices are eligible.
- Shared-memory Intel UHD/Iris devices are preferred when no identity is set.
- Elementwise and Kronecker launches are padded to a bounded power-of-two local
  size.
- Matrix multiplication uses a bounds-safe local-memory tile selected from the
  device's reported work-group and local-memory limits.
- The command queue has profiling enabled. Each completed operation retains
  kernel/device timing when the driver provides it, wall timing, launch sizes,
  kernel identity, output shape, and device identity in
  `ChronusTensorRuntime.last_evidence`.
- Float32 is the only certified tensor type. Consensus SHA256d verification and
  pool acknowledgement remain unchanged.

## Verify on the target host

```bash
python3 -m chronus.report
pytest -q tests/test_chronus_tensor_compute.py tests/test_chronus_igpu_runtime.py
```

Run a real tensor operation through `tensor.backends.chronus_backend`, then
inspect `get_runtime().last_evidence`. Timing is evidence from that execution,
not a projected performance claim. If the host has no Intel OpenCL ICD or no
exposed iGPU, the report records the unavailable reason.