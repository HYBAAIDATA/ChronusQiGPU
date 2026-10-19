# Super-GPU composite substrate

The Super-GPU substrate composes every measured device on the host into one
virtual device: OpenCL GPUs, CUDA/ROCm cards, Apple Metal/MLX, the MLA1517
ASIC (via MMIO), RTL design artifacts, and the CPU reference. Nothing is
invented — a device reports only what a probe measured, and an op executes
only where the required capabilities were attested.

## Layers

- `hyba/inventory.py` — `ClusterInventory.collect()` probes each backend and
  emits `DeviceInfo{name, vendor, backend, type, compute_units,
  global_mem_mb, capabilities}`. Unmeasurable keys are omitted; per-tier
  probe failures land in `inventory.errors` with the concrete reason.
- `hyba/virtual_gpu.py` — `ChronusFabric.compose(inventory)` aggregates compute
  units and unions capabilities keyed to the best device.
  `route(op, workload)` returns a `RouteDecision` (device, capability,
  backend, lucas_dispatch). `execute(op, inputs, workload)` routes, binds
  the IR spec to that device, runs it, and attests the dispatch.
- `hyba/math_ir/` — `KernelSpec` registry (math, signature, required
  capabilities, precision bound, Lucas dispatch discipline),
  `emit_opencl` (canonical `.cl` bytes only — no generated kernels),
  `emit_cpu` (the oracle callables), and `IRExecutor` (capability-matched
  binding; `compile()` raises `CapabilityMismatch` when the device lacks a
  required measured capability).
- `hyba/attestation.py` — `OpAttestation` per dispatch: op, backend,
  device_name, capability_used, lucas_rung, chunk_size, workgroup_size,
  partition_share, measured_ns, clock_source, truth_class. A dispatch that
  ran without a derived Lucas config attests `unconfigured`.
- `hyba/multi_hasher.py` — `MultiDeviceHasher` partitions each nonce window
  across the bound hashers with `hyba.hybrid.lucas_partition` (share ∝
  measured hashrate, else compute units; disjoint; ≤ 2^32; m32 whole-epoch
  aligned; earliest probe-order winner = `atomic_min` semantics). Every
  device-declared winner is re-verified with hashlib — the sole accept
  authority.

## Honesty invariants

- `projection_is_measured: false` stays false for every projected figure;
  only executed dispatch results report `measured_ns`.
- sha256d ≤ target is the sole accept authority; device-reported winners
  that fail the hashlib recheck raise before being reported.
- Strict env gates (`HYBA_REQUIRE_HYBA`, `HYBA_REQUIRE_GPU`,
  `HYBA_DEVICE_NAME`/`HYBA_DEVICE_VENDOR`/`HYBA_DEVICE_PCI_IDS`,
  `EUCLID_*`) are unchanged.
- The canonical kernel sources live in `kernels/`; `chronus/kernels/` is a
  byte-identical mirror asserted in tests.

## Verify

```powershell
python -m pytest tests/test_chronus_fabric.py -x -q
python scripts/benchmark_chronus_fabric.py --n 8 --nonce-space 4096
python -m hyba.diagnose   # includes the chronus_fabric section
```

On a host with no measured GPU, every performance claim in the benchmark
report is emitted as `{"measured": false, ...}` — the harness reports what
ran, not what was hoped for.
