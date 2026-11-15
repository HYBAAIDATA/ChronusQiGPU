# TRIAD Capability Matrix

This matrix maps the required product capabilities to the maintained source and the evidence needed to admit each capability into a production release.

| Capability | Authority | Current implementation | Current branch status | Admission evidence |
| --- | --- | --- | --- | --- |
| Workload execution | CHRONUS | `src/chronus/execution/` | Maintained | Current regression + workload-specific evidence |
| Fleet execution/recovery | CHRONUS | `src/chronus/fleet/` | Maintained | Multi-worker recovery, receipt and backend evidence |
| Tensor runtime | CHRONUS | `src/chronus/tensor/` | Elevated | Current tensor regressions + equivalent-output checks |
| Selective resident-state materialisation | CHRONUS | `tensor/folded_state.py` | Elevated | Partial-read regression + full round-trip digest |
| Physical OpenCL tensor execution | CHRONUS | `tensor/opencl_backend.py`, `kernels/tensor_ops.cl` | Implemented; device evidence open | Identified GPU, driver/kernel binding, parity, repeated timing |
| Physical CUDA tensor execution | CHRONUS | `tensor/cuda_backend.py` | Implemented; device evidence open | Identified NVIDIA GPU, runtime/driver, parity, repeated timing |
| Physical Metal tensor execution | CHRONUS | `tensor/metal_backend.py` | Implemented; device evidence open | Identified Apple GPU, MLX/Metal binding, parity, repeated timing |
| Profiled hybrid routing | CHRONUS | `tensor/geodesic.py` | Elevated | Verified timing profiles; no unverified route selection |
| Measured energy comparison | CHRONUS | `tensor/geodesic.py::EnergyModel` | Elevated | Same-workload measured joules from named environment |
| Versioned representation transform | OVID | `ovid/transform.py` | Elevated | Round-trip/digest/version tests |
| Verified materialisation | OVID | `ovid/transform.py` | Elevated | Independent source digest on reconstructed bytes |
| Durable object custody | THESEUS | `storage/durable.py` | Elevated | Restart, corruption, concurrency and persistence tests |
| Journal continuity | THESEUS | `storage/durable.py` | Elevated | Hash-chain replay and fresh-open verification |
| Triad composition | TRIAD | `triad.py` | Elevated | Transform → durable commit → restart → materialise |
| Enterprise connectors | CHRONUS | `storage/connectors.py` | Maintained | Real provider integration evidence per connector |
| Production admission | CHRONUS | `core/qualification.py`, `scripts/ci/evaluate_attested.py` | Hardened | Exact-commit test + product-gate attestations |
| External key custody | security profile | `security/kms.py` interfaces | Not yet remotely implemented | Real customer-held provider operation + FN-CUSTODY PASS |
| Multi-region durability | THESEUS deployment | Local durable path only | Not established by branch | Replication/failover/RTO/RPO evidence |
| Current hardware performance | CHRONUS | backend-specific | Device-specific | Current device-bound benchmark artifacts |

## Historical capability reconciliation

The historical Geodesic/Tensor system contained MetricTensor, EnergyModel, PhiGPU, HybridGPU, selective folded-state operation and OpenCL operations. The maintained branch restores or supersedes those surfaces without copying old architectural duplication.

The former fixed energy percentage model has been strengthened: current `EnergyModel` accepts measured values only. The former heuristic hybrid path has been strengthened: current `ProfiledHybridRouter` uses verified route observations only. The selective materialisation test explicitly prevents the implementation from satisfying a partial-read request by calling the full reconstruction path.

## Claim boundary

Source implementation and current software tests establish software behavior. Physical acceleration, provider connectivity, external key custody, availability, multi-region continuity and comparative performance each require their own environment-bound evidence.
