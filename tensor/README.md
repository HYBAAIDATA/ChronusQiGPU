# `tensor` — the canonical logical Tensor layer

`tensor` is the backend-neutral production surface for tensor operations in
this repository. It is architecturally separate from `gpu/`, `chronus/`,
MLA1517, and mining:

| Layer | Role |
|---|---|
| `tensor` (this package) | Logical layer: typed contracts, backend protocol/registry, deterministic router, production runtime (timing, cancellation, memory preflight, telemetry). |
| `gpu` / `chronus` | Execution backends only. `gpu.tensor` is a deprecated thin re-export of this package (see below). |
| `kellogg`, `turing_universal_quantum_computer` | The exact mathematical substrate (Q(sqrt2)+iQ(sqrt2), exact state vectors, first-principles quantum tensor). `tensor.kellogg_bridge` loads these lazily; it does not re-implement them. |
| Mining (`mining/`, `hyba/hybrid/*`) | A consumer/advisory use case. `tensor.advisor` re-exports the existing permutation-only nonce-window advisory contract. |

See [`../docs/TENSOR_ARCHITECTURE.md`](../docs/TENSOR_ARCHITECTURE.md) for
the full architecture: dependency direction, operation registry,
exactness/precision policy, backend policy, the mining advisory boundary,
telemetry/evidence schema, security/provenance, the capability matrix, and
remaining external hardware gates.

See [`CAPABILITY_MANIFEST.md`](CAPABILITY_MANIFEST.md) for the
machine-readable (`tensor/capability.py`) feature-to-test status table.

## Quick start

```python
import numpy as np
from tensor import (
    ExactnessMode, MemoryBudget, Precision, TensorOperationSpec,
    TensorRequest, TensorShape, execute,
)

a = np.eye(2)
b = np.eye(2)
op = TensorOperationSpec(
    name="matmul",
    input_shapes=(TensorShape((2, 2)), TensorShape((2, 2))),
    output_shape=TensorShape((2, 2)),
    dtype=Precision.FLOAT64,
    exactness_mode=ExactnessMode.EXACT,
    op_count=2 * 2 * 2 * 2,  # declared FLOP count, used only for TFLOPs
)
request = TensorRequest(operation=op, memory_budget=MemoryBudget(1 << 20))
result = execute(request, (a, b))
print(result.data)                      # the computed tensor
print(result.measurement.tflops)        # measured TFLOPs: op_count / elapsed time
print(result.measurement.as_dict()["hashrate_hps"])  # always None — never H/s
```

## Fail-closed guarantees

- Invalid shapes/dtypes/memory budgets/residual evidence raise immediately
  (`tensor.errors.TensorValidationError` / `TensorMemoryError`) — nothing is
  silently coerced, padded, or truncated.
- An explicitly required backend that is unavailable raises
  `TensorBackendUnavailableError`; there is **no silent GPU fallback**.
  Automatic routing may fall back only when `TensorRequest.allow_fallback`
  is `True`, and the fallback is always recorded in the returned
  `TensorMeasurement`.
- `TensorMeasurement.tflops` is derived only from a declared `op_count` and
  measured `elapsed_ns`. It is never combined with, or converted into, a
  hash rate; `as_dict()["hashrate_hps"]` is always `None`.
- The mining tensor advisor (`tensor.advisor`) may only permute an already
  certified set of nonce windows; any mutation (resize, retarget, add,
  remove, duplicate) raises `TensorAdviceViolation`. SHA-256d verification
  remains the sole acceptance boundary.

## Migrating off `gpu.tensor`

`gpu.tensor` is now a deprecated, zero-duplication re-export of this
package (it emits a `DeprecationWarning` on import). Replace:

```python
from gpu.tensor import TensorMeasurement, load_exact_tensor_module
```

with:

```python
from tensor import TensorMeasurement
from tensor.kellogg_bridge import load_exact_tensor_module
```

`chronus`/`igpu` namespace migration is out of scope for this change (it is
being handled separately); `tensor.backends.chronus_backend` only uses
lazy, dynamic imports of the existing public `chronus` surface so it has no
import-time coupling to that migration.
