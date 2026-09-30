# `gpu`

Canonical project package for GPU/iGPU/ASIC contracts, hardware-independent
reference operations and provenance validation.

Physical backends remain capability-gated. A CPU reference result proves
functional correctness only; it is never labelled GPU execution. TFLOPs remain
compute telemetry and never multiply SHA-256d hashrate.

## Package boundaries

- `gpu.reference`: deterministic reference implementations for matrix, QFI,
  Grover and SHA-256d operations.
- `gpu.provenance`: validation for source/software/hardware/pool evidence.
- `gpu.tensor`: measured TFLOP accounting and exact-tensor loaders.
- `gpu.quantum`: fail-closed access to the separately packaged Turing VQC.
- `gpu.manifold`: lazy access to the production Aethel manifold.
- `gpu.readiness`: software and external-evidence production gates.
- `gpu.backends`: lazy compatibility entry points for iGPU and ASIC backends.
- `gpu.fleet`: lazy compatibility entry points for inventory and `SuperGPU`.
- `igpu`: existing physical integrated-GPU/OpenCL backend. This remains a
  compatibility package during staged migration into `gpu.backends.igpu`.
- `hyba.hybrid`: current GPU/ASIC nonce coordination and host verification.

`igpu.seam` now executes the available matrix, QFI, Grover, SHA-256d and host
attestation references instead of returning synthetic digest placeholders.
Advertised kernels without executable semantics fail closed with
`kernel_unavailable`.

The installed distribution now includes `hyba` and its `hybrid`, `math_ir`
and `operating_model` subpackages. The hybrid coordinator includes measured
performance reporting and permits tensor advice only as an exact permutation
of already-certified nonce windows.

See `BLUEPRINT_AUDIT.md` for implementation and hardware-verification status.

Run `pythia-gpu-readiness` in the release image. It exits non-zero until every
software surface and every physical-evidence gate is satisfied.
