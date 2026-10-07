# HYBA distribution plan — Chronos / Chronus / Tensor / Turing / Kellogg (7 Oct 2026)

Owner intent: publish the planes as **separate installable packages** so each
capability (Kellogg, Tensor, iGPU, Turing, Chronos maths) is a product with its own release cadence,
dependency set, and consumption surface. This file is the packaging contract
and the evidence-based status of each split. The monorepo distribution
`pythia-mla1517` stays canonical until a split's wheel is built and installed
in CI; a scaffold here never silently replaces it.

## Package boundaries

| Distribution | Plane | Modules (monorepo paths) | Dependencies | Status |
|---|---|---|---|---|
| `chronos-core` | Chronos maths (render engine, QSDL, Hamiltonian, evolution, reconstruction, theory, academic) | `chronus/__init__.py`, `chronus/v33/**` | `numpy` | **Scaffolded** (`packaging/chronos-core/pyproject.toml`); structural validation passes (schema parsed, every declared package/module exists); wheel build gated on CI (setuptools not present on the elevation sandbox) |
| `turing-universal-quantum-computer` | Turing VQC compute substrate | `turing_universal_quantum_computer/**` | `numpy` | **Already separate** — own `pyproject.toml` in-tree; declared as a dependency of `pythia-mla1517` (`pip install ./turing_universal_quantum_computer .`) |
| `chronus-igpu` | Chronus hardware/runtime plane (device detect, backends, virtual iGPU, delivery, telemetry) | `chronus/device.py`, `detect.py`, `gpu_capabilities.py`, `native_tensor.py`, `tensor_compute.py`, `opencl_host.py`, `virtual_igpu/**`, `delivery.py`, `telemetry.py`, `runtime.py` | `chronos-core` (soft), optional `pyopencl`/`cupy` | **Planned** — module list frozen from the repo tree; scaffold after #35 (delivery.py imports `native_hash`, fixed there) merges |
| `kellogg-tensor` | Kellogg: exact tensor networks (Q(zeta_8) MPS/MPO/TT in custody), certificates, exact channels/Fisher, surface code, golden substrate, TT-SVD, DMRG, specification registry, benchmark suite | `kellogg/**` | `numpy` (Aethel fold store optional, bound by protocol) | **Scaffolded and wheel-verified** (`packaging/kellogg-tensor/`): `build_and_verify.py` builds the wheel, installs it into a clean venv, imports every module with no sibling product present, and runs the correctness and meta benchmarks against the installed wheel |
| `chronus-tensor` | Tensor plane (folded-state runtime, contracts, receipts) | `tensor/**`, `aethel/fold_store.py` | `chronos-core`, `aethel`, `kellogg-tensor` | **Planned** — Kellogg is no longer bundled here; it is its own distribution and a dependency |

## Provisioning and consumption model (Chronos/Chronus)

`chronus/delivery.py` is the provisioning contract, already implemented on
`main`:

- **`embedded`** — Chronus executes inside the customer's container and binds
  directly to local GPU/accelerator surfaces. Probed per backend
  (OpenCL/CUDA/Metal); no backend is silently substituted and no CPU
  fallback is introduced by the delivery probe.
- **`cloud_instance`** — the customer consumes a HYBA Chronus instance in
  their own cloud via the existing verified remote protocol
  (`remote_opencl_v2`).

For published packages this means:

1. `pip install chronos-core` renders on any host with numpy — **import never
   requires OpenCL/CUDA/Metal** (the existing v33 import contract).
2. Hardware acceleration is opt-in via extras (`chronos-core[gpu]` → cupy)
   and via the separate `chronus-igpu` runtime package; an explicit backend
   request that cannot bind **raises** (`RenderBackendUnavailable`,
   `RenderBackendRequestedUnavailable`) — it never silently renders on CPU.
3. The commercial tiers (STANDARD / PREMIUM SOVEREIGN in the Customer
   Lifecycle plan) are provisioned through the existing evidence-gated
   deployment profiles (`hyba_profiles`: developer → enterprise → sovereign
   → hyperscaler, gate statuses ACCEPTED / CONDITIONALLY_ACCEPTED /
   EXTERNAL_ASSESSMENT_REQUIRED) — the package boundary never invents
   capability the substrate has not evidenced.

## Verification protocol for each split

A distribution is only "published" when, in CI:

1. `python -m build` produces a wheel from its scaffold;
2. the wheel installs into a clean venv and its declared modules import
   (import-without-hardware for chronos-core);
3. the plane's own test suite runs against the installed wheel (not the
   source tree);
4. the capability manifest of the plane matches the wheel contents.

## What this scaffolding does NOT claim

- No PyPI publication has happened; no version beyond the monorepo exists.
- `chronos-core` here packages the v33 Chronos maths only — the deprecated
  `chronos` facade, `chronos.academic` compatibility set, and the seam/
  mla1517 mining platforms stay in the monorepo distribution.
- No tier entitlement or license enforcement is implemented by packaging;
   entitlement gating remains the `hyba_profiles`/AL HARAS plane's job.