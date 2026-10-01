# Chronus

**Chronus is HYBA's canonical iGPU offering. Turing is compute.**

Chronus owns the hardware-facing product/runtime boundary: device census and
selection, resident execution, mathematical-state memory, punch/kernels,
M32/H4 topology bindings, measured telemetry, fleet composition, dispatch
provenance and attestation.

Turing remains the mathematical computation substrate Chronus invokes. Chronus
does not rename, wrap, or absorb Turing.

## Runtime boundary

```text
Turing computation
      |
      v
Chronus route / state / device policy
      |
      +--> OpenCL integrated GPU
      +--> OpenCL discrete GPU
      +--> CUDA / Metal capability surfaces where implemented
      +--> explicit CPU reference/fallback where permitted
      |
      v
measured telemetry + attestation
```

OpenCL, CUDA, Metal, GPU and integrated GPU remain factual backend/hardware
terms. They are not competing HYBA product identities.

## Truth contract

Chronus reports what ran. Measured dispatches are measured, projected figures
stay labelled projections, and unavailable hardware remains unavailable. In the
mining path, SHA-256d target verification remains the sole acceptance authority.

Historical Chronos/Chronus design targets such as fixed 8K frame times,
"perfect GI", "infinite resolution", O(1) search, or fixed PULVINI compression
ratios are not promoted as measured capabilities here unless reproducible tests
produce that evidence.

## Migration rule

The former active `chronus` product namespace is being removed, not retained as a
compatibility alias. Active code must import `chronus` when it addresses the
HYBA iGPU offering. Historical files under `legacy/` remain provenance only.
