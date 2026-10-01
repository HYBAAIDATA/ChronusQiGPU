# Tensor Architecture

This document defines the layer boundaries, dependency direction, and
policies for the `tensor/` package, and is the canonical reference called
out from `tensor/README.md`.

## 1. Layer boundaries and dependency direction

```
┌─────────────────────────────────────────────────────────────────────┐
│  CONSUMERS                                                           │
│  mining/*, hyba/hybrid/* (advisory only)                             │
└───────────────────────────────┬─────────────────────────────────────┘
                                 │ imports (one direction only)
┌───────────────────────────────▼─────────────────────────────────────┐
│  tensor/                — LOGICAL LAYER (this package)               │
│  contracts.py  errors.py  runtime.py  router.py  engine.py           │
│  backends/ (protocol + registry)   advisor.py (re-export)            │
│  kellogg_bridge.py (lazy loaders)  capability.py (manifest)          │
└───────┬──────────────────────────────────┬───────────────┬──────────┘
        │ lazy, optional                   │ lazy          │ eager (stdlib-light)
┌───────▼───────────────┐       ┌──────────▼─────────┐ ┌───▼────────────────┐
│  gpu/ , chronus/        │       │  kellogg/,          │ │ hyba/hybrid/        │
│  EXECUTION BACKENDS     │       │  turing_universal_   │ │ tensor_advisor.py   │
│  gpu.tensor = deprecated│       │  quantum_computer/   │ │ (mining advisory    │
│  thin re-export only    │       │  EXACT MATH SUBSTRATE│ │ boundary)           │
└─────────────────────────┘       └─────────────────────┘ └─────────────────────┘
```

Rules enforced by this layout (and by `tests/test_import_audit.py`,
`tests/test_tensor_package.py`):

- `tensor/` never imports `gpu.*` or `chronus.*`. Hardware/accelerator
  backends are *consumers* of `tensor`'s protocol, not dependencies of it.
- `tensor/backends/chronus_backend.py` only uses `importlib.import_module`
  at call time (never at module import time) to reach the existing public
  `chronus` surface (`chronus.detect`). This repository's Chronus/iGPU
  namespace migration is being handled in a separate change; this adapter
  has no import-time coupling to that migration's internal layout.
- `tensor/kellogg_bridge.py` lazily loads `kellogg.*` and
  `turing_universal_quantum_computer.*` on demand; it does not re-implement
  any of their mathematics.
- `gpu/tensor.py` is a temporary, zero-duplication compatibility shim. It
  re-exports `tensor.contracts.TensorMeasurement`,
  `tensor.kellogg_bridge.load_*`, and `tensor.advisor.*`, and raises a
  `DeprecationWarning` on import.

## 2. Operation registry

Declared operation names and the backends that currently support them (see
`tensor/backends/numpy_backend.py:SUPPORTED_OPERATIONS` and
`tensor/backends/chronus_backend.py:SUPPORTED_OPERATIONS`):

| Operation | numpy-cpu | chronus-opencl |
|---|---|---|
| `matmul` | yes | no (hardware-evidence-required; see capability manifest) |
| `add` | yes | no |
| `hadamard` (elementwise product) | yes | no |
| `scale` | yes | no |
| `kron` (tensor/Kronecker product) | yes | no |

Exact-algebra operations (Clifford+T gates, Born-rule measurement, QFI,
exact linear models) are **not** routed through the numeric backend
registry; they stay in their canonical substrates and are reached through
`tensor.kellogg_bridge`:

- `tensor.kellogg_bridge.load_kellogg_exact_tensor()` → `kellogg.exact_tensor`
  (`Qsqrt2`, `F4`, `ExactStateVector`, `ExactTOETensor`).
- `tensor.kellogg_bridge.load_kellogg_quantum_tensor()` → `kellogg.quantum_tensor`
  (pure-Python `Complex`/Hilbert-space first-principles tensor).
- `tensor.kellogg_bridge.load_kellogg_tensor_ml()` → `kellogg.tensor_ml`
  (TOE Tensor Elevation / exact linear model surface).
- `tensor.kellogg_bridge.load_exact_tensor_module()` /
  `load_quantum_tensor_module()` → the in-tree VQC package
  `turing_universal_quantum_computer` (requires
  `pip install ./turing_universal_quantum_computer`; see that package's
  `pyproject.toml`).

Grover/Hendrix and the ASI/TOE manifold bridges exist in the repository
(`turing_universal_quantum_computer/.../hendrix.py`,
`Intelligence/asi/manifold_bridge.py`, `toe/manifold_bridge.py`) but are not
currently wired to any tensor-contract production consumer; see the
capability manifest (`tensor/CAPABILITY_MANIFEST.md`) for the honest
`not_implemented` status and what would be required to wire them in.

## 3. Exactness / precision policy

- `ExactnessMode.EXACT` operations must reproduce their declared output
  shape exactly; the NumPy backend raises `TensorValidationError` if the
  computed shape disagrees with the declared one (no silent padding or
  truncation).
- `ExactnessMode.LOSSY_APPROX` requires explicit opt-in
  (`ResidualBounds.opt_in=True`) **and** measured residual evidence
  (`ResidualBounds.measured_residual`) that is within the declared
  `max_residual`. A lossy request without both fails closed with
  `TensorValidationError` before any backend is touched
  (`TensorRequest.__post_init__` → `ResidualBounds.require_for`).
- Exact-rational tensors (`Precision.EXACT_RATIONAL`, the
  `kellogg.exact_tensor` Q(sqrt2)+iQ(sqrt2) substrate) are never
  memory-estimated by byte size — `Fraction` values are arbitrary
  precision — so `tensor.contracts.estimate_bytes` fails closed for that
  dtype instead of under-reporting; callers use `kellogg.exact_tensor`'s own
  resource bounds (its documented fail-closed limits) directly.
- This package does not claim PULVINI invariant preservation; no PULVINI
  surface is wired into `tensor/` in this change.

## 4. Backend policy

- `tensor.backends.BackendRegistry` holds **factories**, not instances, so
  constructing an optional backend (and any import it triggers) happens
  only when actually requested or health-checked.
- `tensor.router.route()`:
  - If `TensorRequest.backend_required` names a backend, that backend is
    used or the call raises `TensorBackendUnavailableError`. There is never
    a silent substitution when a backend was explicitly required — this is
    the "no silent GPU fallback" rule from the project's hardware honesty
    policy.
  - In automatic mode (`backend_required=None`), the router tries the
    preferred backend first; it may only fall back to the next backend in
    priority order when `TensorRequest.allow_fallback=True`, and every
    fallback is recorded (`fallback_used`, `fallback_reason`) in the
    returned `TensorMeasurement` — never silent.
  - `BackendRegistry.health_report()` captures backend-construction
    failures as `available: False` with the exception recorded, rather
    than silently treating a broken optional backend as healthy.
- `numpy-cpu` (`tensor/backends/numpy_backend.py`) is always available; it
  is the deterministic ground truth other backends are measured against.
- `chronus-opencl` (`tensor/backends/chronus_backend.py`) is optional. It
  honestly reports `is_available() == False` when `chronus`, OpenCL, or a
  device is absent, and currently declares zero supported operations
  (`SUPPORTED_OPERATIONS = ()`) because Chronus has no generic tensor
  kernel yet — see the capability manifest for what evidence would close
  that gap.

## 5. Mining advisory boundary

Tensor advice may only **reorder** an already certified set of nonce
windows (`hyba.hybrid.tensor_advisor`, re-exported unchanged as
`tensor.advisor`). It must not create, delete, prune, resize, overlap,
retarget, reassign, or mutate windows, and it never decides acceptance:
host protocol-valid SHA-256d verification remains the sole acceptance
boundary. `apply_tensor_advice()` enforces this by comparing the multiset
of windows before and after ranking (`Counter` equality on
`(device_id, base_nonce, span, face)`); any mismatch raises
`TensorAdviceViolation` before the reordered result is used.

**Documentation correction**: `docs/TENSOR_MINING_INTEGRATION.md` and
`docs/M32_TENSOR_BRIDGE.md` describe an `EUCLID_TENSOR_PRUNE` mode that
would let a TypeScript bridge *prune* candidates. No such pruning path
exists in this Python repository's mining stack, and the in-repo exact
rule (`hyba.hybrid.tensor_advisor.apply_tensor_advice`) is an
**exact-permutation-only** boundary — it rejects any window-count change,
including pruning. Those two docs describe a separate (TypeScript)
codebase surface that does not exist in this repository
(`src/lib/*.ts` is not present here); until an independently executed,
separately verified coverage path exists in *this* repository, the
Python `tensor_advisor` exact-permutation rule is canonical here. Treat
those two documents as describing a different system, not this one.

## 6. Telemetry / evidence schema

`tensor.runtime.telemetry_record(measurement, **extra)` returns
`measurement.as_dict()` (operations, elapsed_ns, backend, model_id,
fallback_used/reason, `measured_tensor_tflops`, `truth_class="measured"`,
`hashrate_hps=None`) merged with any extra fields the caller supplies
(e.g. `operation`, `request_id`). `TensorResult.as_dict()` additionally
carries the `ProvenanceRecord` (operation, backend identity, model
identity, input/output digests, timestamp) and the top-level `truth_class`.

**Unit correctness invariant**: `TensorMeasurement.tflops` is computed only
from `operations` (a declared op count) and `elapsed_ns` (measured elapsed
time, `time.perf_counter_ns()`); it is structurally incapable of being
combined with a hash rate because `TensorMeasurement` carries no hash
count field and `as_dict()["hashrate_hps"]` is hard-coded to `None`.

## 7. Security / provenance

- `ProvenanceRecord` binds every result to the backend identity (name,
  class, device id), the model identity (id, version), and SHA-256 digests
  of the input and output payloads (`tensor.engine._digest`), plus a
  `time.time_ns()` timestamp.
- `BackendIdentity.backend_class` is restricted to `reference`, `hardware`,
  or `simulator` so a result can never claim an unrecognized backend class.

## 8. Capability matrix

See `tensor/CAPABILITY_MANIFEST.md` (generated from
`tensor/capability.py::CAPABILITY_MANIFEST`) for the full, versioned
feature-to-implementation-to-test table and the remaining external
hardware gates (a physical OpenCL device plus new Chronus tensor kernels).

## 9. Test commands run for this change

```
PYTHONPATH=.:mla1517_platform_v3.4/python python3 -m pytest \
  tests/test_tensor_package.py \
  tests/test_tensor_contracts.py \
  tests/test_tensor_backends.py \
  tests/test_tensor_runtime.py \
  tests/test_tensor_advisor_safety.py \
  tests/test_tensor_gpu_compat.py \
  tests/test_gpu_reference.py \
  tests/test_kellogg_tensor.py \
  tests/test_toe_tensor_ml.py \
  tests/test_three_layer_runtime.py \
  tests/test_package_layout.py \
  -q
```

`tests/test_import_audit.py::test_the_repository_has_no_broken_imports`
was also run; it has pre-existing, unrelated failures on the base branch
(`gpu/backends/asic.py`, `hyba_substrate/memory_preservation.py`,
`igpu/seam/workflow.py`, `aethel.device.IGpuSku`) that are not touched by
this change (verified by running the same test against the base commit).
A full repository-wide test run was not attempted; this list is the
focused set relevant to the tensor consolidation.
