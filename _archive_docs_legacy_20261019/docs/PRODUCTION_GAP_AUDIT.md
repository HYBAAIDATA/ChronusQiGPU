# Production gap audit — PYTHIA PR #16

## Closed in code

| Boundary | Enforcement |
|---|---|
| Virtual qubit width | Production adapter rejects anything except 11 qubits / 2,048 states. |
| Memory/data fit | Full-rank state bytes plus job data reserve checked before execution; insufficient budget raises `MemoryError`. |
| Exact tensor | Canonical `mtheory.hilbert.QuantumRegister`; numerical export is explicit. |
| Intelligence/TOE | TOE records job-window preparation, execution/consensus result, failures, and pool results; hash-chain verification is required. |
| Tensor/AETHEL | Existing AETHEL store and Tensor fold/unfold run before iGPU execution; round-trip must be lossless. |
| Hendrix/Pisot | L76 deterministic coprime nonce permutation; worker partitions are disjoint and cover the complete window. |
| GPU/iGPU | Existing `HashPipeline` selects OpenCL/GPU when available and reports the backend that actually executed SHA-256d. |
| Consensus | Candidate is independently SHA-256d/target rechecked before submission. |
| Stratum | Subscribe, authorize, notify, target, generation/stale-job, correlated submit response, and accepted/rejected accounting are implemented. |
| Live side effect | Submission requires all three explicit approval environment controls; otherwise dry-run only. |
| CI | Focused Lucas, federation, PULVINI, quantum, Hilbert, scaling, integration, and production-wiring tests are wired into CI. |

## Evidence still requires the target host

These are not software implementation gaps and cannot be truthfully closed by
source inspection:

1. Windows Docker can see the intended iGPU/OpenCL device.
2. The target OpenCL kernel compiles and executes on that device.
3. A real authenticated pool returns `mining.notify`.
4. A real candidate is submitted and the pool returns `result: true`.
5. The pool credits the accepted share.
6. GitHub Actions publishes a green check-run; current PR status is still
   `pending` with zero reported checks.

The system therefore fails closed at each boundary rather than reporting
production success from a unit test or a job receipt.
