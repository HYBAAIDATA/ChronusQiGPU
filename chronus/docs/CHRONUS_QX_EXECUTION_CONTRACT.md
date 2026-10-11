# Chronus QX execution contract

## Status

Computational tranche 1. This document defines the implemented, substrate-independent QX command
boundary. It does not claim a physical cryogenic device, measured cavity array, photonic fabric,
SNSPD readout system, or hardware timing result.

## Proposition

A QX command buffer is an append-only sequence of typed operations. Before execution it is sealed
into a canonical SHA-256 digest. Every backend must execute the same mathematical commands, preserve
the declared invariants, and return provenance tied to that digest.

Implemented commands:

1. `AllocateCavityRegion`
2. `SetHamiltonian`
3. `Evolve`
4. `WeakMeasure`
5. `ApplyCorrection`
6. `ReadExpectation`
7. `Synchronize`
8. `MemoryBarrier`
9. `DescriptorSetBind`

Implemented synchronization and memory semantics:

- named synchronization events;
- monotonic barrier epochs;
- `all`, `cavity`, and `classical` memory domains;
- immutable command buffers after sealing;
- canonical command-buffer custody through SHA-256.

## Invariants

The reference executor fails closed unless all applicable conditions hold:

- a cavity region exists before stateful commands execute;
- matrix dimensions match the allocated state dimension;
- Hamiltonians and observables are Hermitian within the declared tolerance;
- correction matrices are unitary;
- evolution steps are finite and positive;
- weak-readout strength satisfies `0 < epsilon <= 0.01`;
- state norm is preserved within the executor tolerance;
- execution uses a sealed command buffer.

The reference backend uses NumPy `complex128`/`float64`. This is a QX conformance surface, not the
11-D substrate: the declared Float64 boundary for that substrate remains unchanged and is not routed
through Chronus's certified Float32 tensor path.

## Provenance

`QXExecutionReport` records:

- sealed command digest;
- backend identity;
- precision policy;
- state dimension;
- executed command count;
- barrier epoch and synchronization events;
- expectation and weak-measurement results;
- descriptor sets;
- final-state SHA-256;
- measured norm error.

Hardware backends must add device, driver, kernel, firmware, calibration, and clock provenance. They
must not relabel projected timings or injected constants as measurements.

## Verification

```bash
ruff check --select E9,F chronus/v33/qx.py tests/test_chronus_v33/test_qx.py
pytest -q tests/test_chronus_v33/test_qx.py
```

The branch introducing this tranche is not verified until these commands run in CI or a captured
local environment. A passing reference test establishes computational behavior only. Physical
cryogenic behavior requires independently captured hardware evidence.

## Next tranches

1. Compile `QScene` output into QX command buffers.
2. Add a backend protocol and adapt Chronus CPU/OpenCL execution surfaces without changing the
   mathematical contract.
3. Add density-matrix weak-measurement backaction and retrodictive compensation to QX execution.
4. Add deterministic MLE tomography with log-likelihood convergence and reconstruction bounds.
5. Add physical-control schemas for pulse schedules, DAC waveforms, cavity maps, calibration, and
   fail-closed interlocks.
6. Produce cross-repository conformance vectors portable between PYTHIPhiMiner and
   UnifiedEnterprise.
