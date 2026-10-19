# Apple public-framework integration

Reviewed sources:
- https://developer.apple.com/videos/play/wwdc2025/315/ — MLX unified memory, CPU/GPU streams, lazy evaluation and graph optimization.
- https://developer.apple.com/documentation/coreml/mlcomputeunits — ALL, CPU_ONLY, CPU_AND_GPU and CPU_AND_NE model execution policies.

This extension uses public framework APIs and documented techniques. It does not contain private Apple neural designs, nor claim Apple involvement.

## MLX tensor executor

`MLXOverlay` composes beneath the existing OneIGPU owner. It accepts real floating tensor operations, explicitly selects the GPU stream and materialises with `mx.eval` before timing/result receipts. Exact Lucas and SHA256d continue on their compatible executors: float32 tensor capability does not intercept integer work.

The NumPy conversion at the Python facade is explicit; no end-to-end zero-copy promise is made. The host checks finite shape and numeric agreement with declared tolerances. An unavailable Metal/MLX/macOS runtime raises BackendAbsent.

```python
from chronos import OneIGPU
from chronos.igpu import MLXOverlay
with OneIGPU(host_adapter=MLXOverlay()) as gpu:
    result = gpu.tensor('matmul', [[1., 0.], [0., 1.]], [[2.], [3.]])
```

## Neural ranker and Core ML

`LinearNeuralRanker` executes bounded dense/ReLU inference with supplied weights. It is executable on the native host and preserves a stable permutation of candidate IDs. No trained Bitcoin model is bundled or claimed. `CoreMLRanker` loads a bounded, optionally digest-pinned `.mlmodel` and executes the specified input/output tensor contract on macOS.

Allowing ALL compute units permits OS selection including the Neural Engine; that policy does not prove every layer ran on the Neural Engine. Receipts preserve the policy and set actual per-layer Neural Engine dispatch to unknown.

`gpu.neural_rank(...)` checks that no candidate is invented, lost or duplicated. You can supply its result via the existing solver callback; exact target/lease verification remains in the existing core.

```python
from chronos import OneIGPU
from chronos.igpu import LinearNeuralRanker
ranker = LinearNeuralRanker([[1.]], [0.])
with OneIGPU() as gpu:
    order = gpu.neural_rank([10, 20, 30], [[1.], [3.], [2.]], ranker)
    assert order == (20, 30, 10)
```

The release host executed native ranker, ownership and operation-routing tests. Apple hardware execution requires the macOS target; it was not performed on the Linux release host.
