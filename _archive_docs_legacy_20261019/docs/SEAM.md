# The Seam — iGPU contract

The seam is the only surface Kellogg, TOE, and Aethel talk to.
Silicon (OpenCL, CUDA, Metal, firmware) stays below it.

Implemented in `chronus/seam/` on top of the existing package:

| Layer | Module | Existing substrate |
|-------|--------|--------------------|
| L1 Device probe | `chronus/seam/probe.py` | `chronus.detect`, `chronus.telemetry` |
| L2 Buffer | `chronus/seam/buffer.py` | `chronus.runtime.allocate_device` |
| L3 Kernel | `chronus/seam/kernel.py` | `chronus.device.Chronus.grind` / punch ISA |
| L4 Queue | `chronus/seam/queue.py` | process-local linearizable queue |
| L5 Fleet | `chronus/seam/fleet.py` | `hyba.hybrid.HybridCoordinator` via `run_hybrid_stratum` |
| Hybrid partition | `chronus/seam/hybrid.py` | `hyba.hybrid.lucas_partition` compared, not replaced |

## Honesty rules already in chronus, now enforced as invariants

- `chronus.detect` never labels a discrete NVIDIA part as iGPU.
- `chronus.runtime` never names host RAM as device memory (`host_fallback`).
- `Chronus.backend` reports the surface that ran, not the one hoped for.
- `hyba.hybrid` declares `asic_absent` instead of simulating an ASIC.
- Host `verify_share` is the sole accept authority for Stratum shares.

## Known gaps in hyba.hybrid vs the full contract

See `chronus.seam.invariants.audit_hyba_hybrid()`:

- Capability HPS is a scalar, not a `Distribution` (P4).
- Public APIs raise exceptions rather than return `Result[T]` (S1).
- No threshold multi-device verification (F4).
- No zero-knowledge attestation mode (K5).
- No digested multi-tenant buffer layer inside hyba.hybrid (B1–B5).

Those gaps stay declared. The seam implements the missing contract above
the existing solvers; it does not rewrite `gpu_solver` / `asic_solver`.

## Usage

```python
from chronus.seam import probe_devices, run, KernelName

caps = probe_devices().unwrap()
result = run(
    {"job_id": "j1", "kernels": [KernelName.lucas_wind.value], "span": 1024},
    caps,
)
```

Live hybrid mining still goes through `hyba.hybrid.HybridCoordinator`.
Call `run_hybrid_stratum(job, gpu_solver, asic_solver)` to record that
run on the seam audit ledger without changing the solver path.
