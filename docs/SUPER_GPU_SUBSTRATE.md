# SUPER_GPU substrate (Chronus fabric)

The super-GPU composite substrate is Chronus: post-consolidation, "the GPU"
is the `chronus/` tree and `SuperGPU` is `chronus.fabric.ChronusFabric`.
The canonical substrate document is `docs/CHRONUS_SUBSTRATE.md`; this page
maps the five-phase elevation contract onto the code that carries it.

| Spec surface | Implementation |
|---|---|
| `SuperGPU.compose/route` | `hyba/virtual_gpu.py` → `chronus.fabric.ChronusFabric` |
| `super_gpu` diagnose section | `hyba/diagnose.py` (aliases `chronus_fabric`) |
| inventory | `hyba/inventory.py::ClusterInventory.collect` |
| IR specs / emitters | `hyba/math_ir/{specs,emit_opencl,emit_msl,emit_cpu}.py` |
| IR executor | `hyba/math_ir/executor.py::IRExecutor` |
| attestation | `hyba/attestation.py` (wired into `ChronusFabric.execute`) |
| multi-device partition | `hyba/multi_hasher.py::MultiDeviceHasher` |
| per-device hasher | `mining/bitcoin_hasher.py` (`device=` pin, Lucas launch sizes) |
| ladder executor pin | `chronus/mla1517/scaling.py::OpenCLLadderExecutor(device=)` |
| driver dispatch | `chronus/mla1517/mining/opencl_driver.py` (`device_index=`) |
| benchmark | `scripts/benchmark_chronus.py` (`benchmark_super_gpu.py` alias) |
| tests | `tests/test_chronus_fabric.py`, `tests/test_super_gpu.py` |

Honesty invariants are unchanged from the canonical doc: sha256d(header) ≤
target is the sole accept authority (every device-declared winner is
hashlib-rechecked), projections never report `measured: true`, and missing
hardware fails explicit — never silently to CPU.
