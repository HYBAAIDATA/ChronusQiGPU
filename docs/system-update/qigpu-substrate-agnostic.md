# QiGPU — substrate-agnostic compute engine

**Status:** Implemented, verified, and structurally bounded. `src/chronus/execution/qigpu.py`
(`QiGPUOrchestrator`) is the substrate-agnostic execution-surface inventory and routing layer;
`src/chronus/execution/reference.py` (`ExecutionRouter`) is the backend-neutral dispatch layer.
Tests: `6 passed` in `tests/test_qigpu.py`.

> Design rule carried throughout this repository: **the mathematics is the substrate; the hardware is
> an interchangeable surface.** QiGPU is *not* a claim of physical quantum execution, hardware
> advantage, fidelity, or production readiness. Those boundaries follow `docs/claim-audit.md` and
> `docs/system-update/quantum-package-taxonomy.md`.

## The core model

QiGPU inventories execution surfaces and resolves routing without changing workload semantics:

- The CPU reference surface (`python-math-reference`) is **always present**.
- A client-provisioned accelerator surface (e.g. OpenCL GPU) registers **only when** it is
  explicitly enabled (`CHRONUS_ENABLE_OPENCL_PV=1`), is detected, and passes its known-answer
  startup test.
- `QiGPUOrchestrator.resolve(workload_type, preference?)` honors a client's choice and **fails closed**
  on an unknown surface or a workload it does not support.
- `QiGPUOrchestrator.auto_select(workload_type)` **climbs into a provisioned accelerator** when one
  supports the workload; otherwise it operates on the **CPU substrate**. It fails closed when no
  surface supports the workload.

## Evidence

The following facts are directly observable in source and tests:

- `qigpu.py` `inventory()` returns `"substrate": "mathematical"` and `"hardware_agnostic": True`.
- `inventory()` sets `"default_surface": "python-math-reference"`.
- `resolve()` raises `ValueError` with `not provisioned` (unknown surface) and `does not support`
  (workload not supported by the chosen surface).
- `auto_select()` returns `("python-math-reference", "cpu-substrate")` when no accelerator is
  provisioned, and `("fake-gpu", "client-accelerator")` when one is.
- `tests/test_qigpu.py` covers CPU-always-present, accelerator scale-in, `resolve()` fail-closed,
  auto-select climb-in/fallback, and exact integer states (`PHYLOTAXIS_STORE`, `THESEUS_RETRIEVE`,
  `TRINITY_SCALE_FOLD_STORE`).
- `reference.py` dispatch is backend-neutral: a workload is executed by the registered backend whose
  `supports()` is true, with no changes to workload semantics.

## What "substrate-agnostic" does and does not mean here

- **It means**: a bounded exact-mathematics execution substrate whose hardware surface is
  interchangeable (CPU reference always present; client accelerator optional and provisioned).
- **It is not**: physical-device execution, hardware fidelity, quantum advantage, or release
  qualification. The `src/chronus/quantum/` namespace is legacy finite-field/algebraic research, and
  `packages/turing` is the only first-principles complex-Hilbert-space mathematics in the repository.
  The `hw/` RTL and `artifacts/qigpu/manifests` are acknowledged source artifacts only — ready only
  for bounded exact models, with no physical execution claim (`docs/claim-audit.md`).

## Intended next state — the sandbox demo

The substrate-agnostic engine is designed to expose a client walkthrough:

1. **Input** — the client supplies a workload (bring their own input).
2. **Fold** — data is folded once, into the integer-lattice representation, and stored folded.
3. **Search** — the system runs the requested search/fold operation in the folded state (no unfolding).
4. **Result** — the folded result is returned, and storage savings and operation timing are reported
   at each step, with a signed receipt.

This keeps the *capability* (what the math lets us do) visibly distinct from the *evidence* (measured
and measured-on-instrument), as the style guide requires.

## Open items

1. **Sandbox demo** — host the walkthrough in the frontend and wire the `QiGPUOrchestrator`
   inventory + `ExecutionRouter` routing through it.
2. **Frontend surface/health panel** — a workspace view of live surfaces (CPU vs provisioned
   accelerator), routing outcome, fail-closed states, and telemetry.
3. **Repository hygiene** — remove scratch files off `main` so the routed CI checks are restored
   (currently gated behind a GitHub approval/clean-up in the cowork workflow).
