# Chronus architecture

Chronus is HYBA's iGPU offering. Turing is the compute engine/substrate.

- **Turing:** mathematical computation and algorithmic execution.
- **Chronus:** hardware-facing iGPU product/runtime, device routing, resident
  execution, memory, kernels, telemetry, fleet composition and attestation.
- **Backends:** OpenCL/CUDA/Metal/CPU are execution substrates selected and
  reported by Chronus; they are not product identities.
- **MLA1517:** the compute/mining substrate beneath Chronus. It is not
  renamed; Chronus sits above it.

## Native execution substrates

OpenCL is one Chronus execution substrate, not the definition of Chronus.
The tensor contract now exposes three independent physical-device paths:

- `chronus-opencl` — the existing OpenCL tensor runtime and kernels.
- `chronus-cuda` — CUDA execution through CuPy using Chronus-owned CUDA
  kernels for `matmul`, `add`, `scale`, `kron`, and `hadamard`.
- `chronus-metal` — Apple GPU execution through MLX/Metal for the same tensor
  operation set.

The native paths are lazy and fail closed. Neither CUDA nor Metal silently
falls back to OpenCL or CPU. Existing OpenCL routing priority is preserved;
clients may explicitly require a native backend and policy-authorised routing
may use one when the preferred backend is unavailable.

This native expansion currently applies to the tensor execution surface. The
consensus SHA-256d mining path retains its existing OpenCL/explicit-CPU
implementation until a separate native mining kernel is implemented and
verified against the existing host acceptance authority. That boundary is
recorded rather than hidden.

## Delivery modes

Chronus has two first-class delivery methods. Neither is a fallback for the
other and provisioning must select one explicitly.

1. **Embedded Chronus** — Chronus executes inside the customer's/container
   environment and binds to the execution surfaces made available there.
   Provisioning mode: `embedded`; transport: in-process. The embedded probe is
   substrate-neutral and can report OpenCL, CUDA, and Metal physical tensor
   execution surfaces independently.
2. **Chronus Cloud Instance** — HYBA deploys a Chronus instance into the
   customer's chosen cloud and the customer reaches it through the verified
   remote Chronus protocol. Provisioning mode: `cloud_instance`; current
   transport: `remote_opencl_v1`.

`chronus.delivery` exposes the common provisioning contract for both modes.
It reports only capabilities observed from the selected delivery path. It does
not invent performance figures and does not silently move work between modes.
Measured performance belongs to the Chronus measurement/evidence stack.

The existing remote agent advertises the executable endpoints it actually
serves and imports measured devices; capability growth on that protocol should
be additive and evidence-backed rather than assumed from product identity.

Chronus consolidates the former active iGPU package and the Super-GPU product
surface. It is a real namespace migration, not an alias. Historical material
under `legacy/` is retained as provenance only and is not importable through a
compatibility surface.
