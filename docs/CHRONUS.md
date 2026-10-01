# Chronus architecture

Chronus is HYBA's iGPU offering. Turing is the compute engine/substrate.

- **Turing:** mathematical computation and algorithmic execution.
- **Chronus:** hardware-facing iGPU product/runtime, device routing, resident
  execution, memory, kernels, telemetry, fleet composition and attestation.
- **Backends:** OpenCL/CUDA/Metal/CPU are execution substrates selected and
  reported by Chronus; they are not product identities.
- **MLA1517:** the compute/mining substrate beneath Chronus. It is not
  renamed; Chronus sits above it.

Chronus consolidates the former active iGPU package and the Super-GPU product
surface. It is a real namespace migration, not an alias. Historical material
under `legacy/` is retained as provenance only and is not importable through a
compatibility surface.
