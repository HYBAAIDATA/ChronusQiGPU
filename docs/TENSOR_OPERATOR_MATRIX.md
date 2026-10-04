# Tensor Operator Matrix

Built from live code on `main` @ `f311eac` (2026-10-04, post-PR-#27) for the
tensor-stack elevation. Every row was verified against the implementation
named; "evidence" cites the test file that exercises it. This matrix is the
Phase-0 audit artifact of `PHIMINER_TENSOR_ELEVATION_20261004`.

Legend for the **Gap** column: `--` = no known gap, otherwise the live
limitation is stated.

## 1. Logical plane — `tensor/` (canonical contract layer)

| Operation | Definition | Implementation | dtype / layout / shape support | Production caller | Backend | Residency | Reference | Evidence | Gap |
|---|---|---|---|---|---|---|---|---|---|
| `matmul` | `np.matmul` contract `A(m,k)·B(k,n)→C(m,n)` | `tensor/backends/numpy_backend.py` | float32/64, complex64/128; any rank accepted by numpy but must match declared output shape | `tensor/folded_inference.py::FoldedLinearPilot` (pilot only); **no embedded production caller** | numpy-cpu | host-materialized | numpy-cpu is the reference | `tests/test_tensor_backends.py`, `tests/test_chronus_native_tensor.py` | matmul fully unfolds operands in both folded planes; global dependency unmodelled |
| `add` | elementwise `a+b` | numpy_backend | same dtypes; two equal-shape inputs | none outside tests | numpy-cpu | host | numpy-cpu | `tests/test_tensor_backends.py` | no lifted folded form |
| `hadamard` | elementwise `a*b` | numpy_backend | same dtypes; equal shapes | none outside tests | numpy-cpu | host | numpy-cpu | `tests/test_tensor_backends.py` | no lifted folded form |
| `scale` | `a*scalar` (second input size 1) | numpy_backend | same dtypes | none outside tests | numpy-cpu | host | numpy-cpu | `tests/test_tensor_backends.py` | no lifted folded form |
| `kron` | `np.kron` rank-1/rank-2 | numpy_backend | same dtypes; declared output dims enforced | none outside tests | numpy-cpu | host | numpy-cpu | `tests/test_tensor_backends.py` | no lifted folded form |
| `matmul/add/hadamard/scale/kron` on OpenCL | `chronus.tensor_compute` → `kernels/tensor_ops.cl` | `tensor/backends/chronus_backend.py` | **float32 only**; rank/shape checked in `_shape_supported` | none | chronus-opencl (fail-closed) | device | numpy-cpu | `tests/test_chronus_tensor_compute.py` (test double) | hardware-evidence-required; no physical GPU on dev box |
| same on CUDA/Metal | `chronus.native_tensor` `get_{cuda,metal}_runtime` | `tensor/backends/chronus_native_backend.py` | float32 only | none | chronus-cuda / chronus-metal (fail-closed) | device | numpy-cpu | `tests/test_chronus_native_tensor.py` | hardware-evidence-required |
| fold custody (numeric) | `phi_fold`: Fibonacci split `1/φ²` complement per level, `retained + reversed(complements)` | `aethel/phi_fold.py` | **coerces all input to float64** (`phi_fold` L130); any shape | `chronus.phi_gpu.PhiGPU`, `aethel.phi_memory.PhiMemoryHierarchy`, `kellogg.phi_tensor_core` | host | `NumericFoldState` resident | exact plane twin | `tests/test_aethel_package.py` et al. | dtype/complex custody lost; `fold_result` is a full unfold→write→re-fold |
| partial unfold (numeric) | segment-intersection addressed read | `aethel/phi_fold.py::unfold_partial_with_stats` | contiguous flat `[offset, offset+length)` only | `chronus.phi_gpu.PhiGPU.launch_kernel`, kellogg boundary reads | host | reads resident segments | exact plane twin | tests incl. stats (`source_values_read`) | contiguous boundaries only; no region → dependency-cone mapping |
| memory tiers | REGISTER/SRAM/L2/HBM = fold depths 0/1/2/3+ | `aethel/phi_memory.py::PhiMemoryHierarchy` | float64 via `phi_fold` | `chronus.phi_gpu` (scheduler depth policy, PhiGPU) | host | named residents dict | — | `tests/test_aethel_package.py` | no eviction, device-loss invalidation, content identity, or restart recovery; name→state dict only |
| integrity gate | expected-vs-actual error + norm-ratio band + chronology | `aethel/phi_memory.py::TopologicalIntegrityGate` | float64 | `chronus.phi_gpu.PhiGPU` | host | verdict ledger | — | `tests/test_aethel_package.py` | callers must supply an independent reference themselves |

## 2. Exact-rational plane — `python_backend/core_modules/geodesic_tensor_engine.py`

| Operation | Definition | Implementation | dtype / layout / shape | Production caller | Backend | Residency | Evidence | Gap |
|---|---|---|---|---|---|---|---|---|
| `fold_exact` | PULVINI pair fold `(a+b, a)`, recursive `depth` levels | `fold_exact` | int/Fraction only; floats rejected | `FoldedWeightState.from_array` (uint-view), `GeodesicNoncePlanner` | host CPU (Fraction) | `ExactFoldState` | `tests/test_geodesic_tensor_engine.py` | every fold re-verifies a full unfold roundtrip (O(n·depth) Fraction ops per fold) |
| `unfold` | recursive pair-inverse | `ExactFoldState.unfold` | — | same | host | — | same | reference impl |
| `unfold_partial` | memoized recursive index recovery, `x[2p]=f[2p+1]`, `x[2p+1]=f[2p]-f[2p+1]` | `unfold_partial_with_stats` | contiguous flat `[start, stop)` | `FoldedWeightState.rows` | host | — | `tests/test_geodesic_tensor_extensions.py` | contiguous boundaries only |
| `fma` / `elementwise` / `reduce_sum` | lifted per-boundary ops | `PhiTensorCore` | Fraction; boundary-limited input decode | internal (`PhiGPU.launch_fma`) | host | result re-folded | `tests/test_geodesic_tensor_extensions.py` | result shape collapses to flat; boundary op then re-folds whole slice |
| `matmul` | rank-2 exact contraction | `PhiTensorCore.matmul` | Fraction; **full unfold of both operands** | none | host | — | `tests/test_geodesic_tensor_engine.py` | global dependency executed but not modelled as such |
| `launch_fma` | block-partitioned exact FMA across logical cores | `PhiGPU.launch_fma` | Fraction; blocks `ceil(total/num_blocks)` | none outside tests | host | — | extensions tests | ordered concat assembly; scheduler not consulted |
| `order_window` | permutation-only nonce ordering | `GeodesicNoncePlanner` | uint32 ints | `chronus/mla1517/mining/geodesic_support.py` (env-gated `PYTHIA_GEODESIC_ORDERING`) | host | — | `tests/test_geodesic_tensor_engine.py` | — |
| `EnergyModel` | declared coefficient model | `EnergyModel` | — | `PhiGPU.launch_fma` report | host | — | extensions tests | `measured: False` declared correctly |

## 3. Numeric control plane — `chronus/phi_gpu.py`

| Operation | Definition | Implementation | Caller | Evidence | Gap |
|---|---|---|---|---|---|
| `GeodesicScheduler` | heapq nearest-first by `phi_log_distance` + tier depth policy | `GeodesicScheduler.submit/schedule*` | `PhiGPU` holds one but **never consults it** | `tests/test_chronus_phi_gpu.py` | **scheduler→executor disconnect**: `launch_kernel` picks its own boundary; `mark_completed` is manual bookkeeping |
| `PhiGPU.launch_kernel` | partial-unfold boundary → `np.array_split` over 32 logical cores → kernel → concat → verify vs full-work reference | `PhiGPU.launch_kernel` | `HybridGPU.execute` | tests | serial loop; `_reduce_results` is whole-state concat (no coordinate-committed output); scheduler ignored |
| `HybridGPU` | classify payload → phi_native / traditional | `HybridGPU.route_workload/execute` | none outside tests | tests | routing only |
| `EnergyModel` | declared coefficients | `EnergyModel` | reports | tests | declared model |
| `GeodesicScheduler` (router) | Dijkstra shortest path over cost graph | `chronus/virtual_igpu/planner.py` | `ChronusPlanner` | `tests/test_virtual_igpu.py` | **name collision** — different semantics (route planner, not task scheduler); rename target: `GeodesicRouter` |
| `ChronusPlanner` | Lucas-bounded candidate plans with CostVector | `ChronusPlanner.candidates/select` | virtual_igpu runtime | `tests/test_virtual_igpu.py` | `lucas(n)` recomputed per call — memoize for large n |

## 4. Custody / inference pilot — `tensor/folded_inference.py`

| Operation | Definition | Implementation | Caller | Evidence | Gap |
|---|---|---|---|---|---|
| `FoldedWeightState` | uint-view of IEEE floats → exact PULVINI fold (bit-exact custody) | `from_array`/`restore`/`rows` | `FoldedLinearPilot` | `tests/test_folded_inference.py` | float32/64 only; dtype preserved via uint view (the pattern Phase 2 generalizes) |
| `FoldedLinearPilot.run` | chunked row partial-unfold → `tensor.execute` matmul per chunk | `run` | tests only | `tests/test_folded_inference.py` | only path reaching `tensor.execute` outside tests; still calls `weights.restore()` for the reference baseline (expected — it's the verifier) |

## 5. Duplicate surfaces (Phase 9 consolidation ledger)

| Symbol | Copies | Disposition |
|---|---|---|
| `PhiTensorCore` | `kellogg/phi_tensor_core.py` (numeric folded ALU — canonical), `python_backend/core_modules/geodesic_tensor_engine.py` (exact authority), `quantum_compute_substrate/phi_tensor_core.py` (quantum-amplitude unit used by `chronus/mining_bridge.py`) | keep numeric + exact in canonical homes; quantum-amplitude unit keeps distinct semantics — rename to remove the collision |
| `GeodesicScheduler` | `chronus/phi_gpu.py` (task ordering), `chronus/virtual_igpu/planner.py` (Dijkstra route planning), `geodesic_tensor_engine.py` (exact ordering facade) | rename planner's to `GeodesicRouter`; keep the other two (different planes) |
| `PhiMemoryHierarchy` / `TopologicalIntegrityGate` / `EnergyModel` / `PhiGPU` / `HybridGPU` / `MetricTensor` / `KernelBoundary` / `PartialUnfoldStats` | aethel+chronus numeric family vs `geodesic_tensor_engine.py` exact family | keep both semantic families; all new capability lands in canonical files only; `KernelBoundary` field names differ (`offset/length` vs `start/stop`) — keep, document |
| `fold_result` vs exact plane | numeric has `fold_result` (full re-fold); exact plane has no write-back op at all | Phase 3 adds regional write-back on both |

## 6. Reachability ledger (the primary gap)

| Surface | Reachable today? | Path |
|---|---|---|
| `tensor.execute` | tests + pilot only | no CLI, no control-API endpoint, no embedded caller |
| `gpu.tensor` shim | importable | deprecated re-export (may remain the documented deprecation path) |
| `chronus.phi_gpu.PhiGPU` | tests + `HybridGPU` | no production caller |
| `geodesic_tensor_engine` | `geodesic_support.py` (mining, env-gated) + tests | only the nonce planner is reachable in production |
| `PhiMemoryHierarchy` | via `chronus.phi_gpu` | no direct production residency lifecycle |
| `FoldedLinearPilot` | tests only | not wired into any serving path |
| `ChronusPlanner` | virtual_igpu runtime | internal |
| control API | live | `chronus/mla1517_platform/python/control_api.py` — no `/api/v1/tensor/*` endpoints |

## 7. Defect ledger carried forward (verified live @ f311eac)

| Finding | Status |
|---|---|
| `aethel.phi_fold.phi_fold` coerces to float64 (line ~130) — dtype/complex custody lost | **LIVE** |
| `fold_result` full-tensor unfold→write→re-fold per regional write | **LIVE** (documented limitation) |
| `PhiGPU.launch_kernel` ignores `self.scheduler`; serial `np.array_split`; `_reduce_results` whole-state concat | **LIVE** (partially improved: uses `config.boundary` + verifies vs reference) |
| matmul fully unfolds operands in both planes | **LIVE** (global dependency unmodelled) |
| exact plane has no write-back op | **LIVE** |
| no persistent/versioned folded-state graph, no checkpoint/restore, no eviction/device-loss handling | **LIVE** |
| no semantic IR (axis/contraction algebra, dependency-graph program) | **LIVE** |
| no registered lifted-operator catalogue | **LIVE** |
| `PhiRecursiveOperator`/`formal.py` absent | **confirmed absent** — lifting rules derive from `PulviniFold` |
| `tensor` has zero production callers | **LIVE** — primary reachability gap |
