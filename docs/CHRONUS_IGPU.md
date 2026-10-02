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

## Capture a complete evidence artifact

The evidence command runs the production Chronus OpenCL runtime, checks every
result against NumPy, records OpenCL device and wall time, observes a sustained
load, samples only sensors exposed by the host, inventories all OpenCL
GPU/accelerator devices, and content-binds the runtime, kernel, inputs, and
output.

```bash
python3 -m bench.chronus_igpu_evidence \
  --size 512 \
  --iterations 20 \
  --stress-seconds 300 \
  --sha256d-count 1048576
```

The command writes
`bench/results/igpu_<device>_<UTC timestamp>.json`. It fails if the requested
iGPU is absent, any tensor result disagrees with the CPU reference, or the
evidence artifact cannot validate its physical-execution and content-hash
invariants. When requested, SHA256d is measured through the production
`BitcoinHasher` OpenCL path. Pool acknowledgement stays `Unavailable`; local
work is not presented as an accepted mining share.

Generic OpenCL does not expose peak bandwidth, and a product-name estimate is
not evidence. Supply independently measured peak inputs only when available:

```bash
python3 -m bench.chronus_igpu_evidence \
  --peak-gflops <measured-value> \
  --peak-bandwidth-gbps <measured-value>
```

Without both values, roofline classification is `Unavailable`. Intel RAPL is
reported as a package-level energy proxy, never as iGPU-only power. GPU hwmon
power and temperature are reported only when corresponding sysfs sensors exist.

The attestation is a reproducible software content binding, not hardware-rooted
firmware attestation. Generic OpenCL does not expose a trustworthy firmware or
ROM hash, so those claims remain unavailable.

The existing remote agent supports verified SHA256d, ladder execution,
telemetry, and multi-agent mining fleets. The evidence artifact probes and
reports that path. Remote Chronus tensor dispatch is separately labelled
`unimplemented`; it is not inferred from the mining path.