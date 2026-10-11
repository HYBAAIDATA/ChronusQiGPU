# Chronus v3.3 full capability convergence

## Decision

The July `chronos-gpu-v3.3-memory.zip` capability stack is integrated in full
under `chronus.v33`. No July module was cherry-picked or discarded.

The existing top-level `chronus` package remains the physical execution,
OpenCL, telemetry, and production-mining authority. The v3.3 namespace adds the
complete mathematical compute surface without overwriting those hardware
contracts.

## Manifest comparison

Current `chronus` did not contain the July package's `academic`, `compression`,
`control`, `environment`, `fields`, `graphics`, `memory`, or `theory`
subpackages. The July top-level engine also had a separate QSDL/render,
Hamiltonian, weak-measurement, reconstruction, EMP, and φ-scaling stack.

Integrated surface:

- 61 Python modules
- 101 public classes
- 111 public functions
- 35 tests

The machine-readable inventory is committed as
`chronus/v33/CAPABILITY_MANIFEST.json`.

## Capability groups

1. QSDL parser/compiler, M32 manifold, Hamiltonian construction, evolution,
   reconstruction, and rendering.
2. Weak measurement and error-mitigation processing.
3. Exact φ-scaling benchmark machinery.
4. Tensor networks, MPS state/storage, TEBD, φ-fold representations, and
   large-space utilities.
5. Table, QRAM, PREPARE/SELECT block encoding, QSVT, neural-combine indexing,
   and the four-level memory facade.
6. Closed-loop control, decoherence channels, thermal environment, coherent
   laser, microwave fields, and graphics pipeline.
7. Anyons, superconductivity, cryogenics, photonics, metrology, QCD,
   stabilizer error correction, oscillator normal modes, chemistry, and
   Riccati/Kalman-Bucy control.
8. Cavity QED, surface code, PINN/GQN/RL utilities, NIST checks, Jaynes-Cummings
   dynamics, and tensor-compression integrations.

## Cleaning

The original July package produced 84 `ruff --select E9,F` findings. All were
resolved in the integrated namespace, including unused imports, unused local
state, public export definitions, and test cleanup.

## Mining wiring

`HYBAIntelligencePipeline` now calls the July Chronus memory implementation as
an exact 32-bit candidate-custody table before PULVINI, Geodesic, and φ-VQC
ordering. It verifies a byte-for-byte integer round-trip before continuing.

Other v3.3 capabilities are available through `chronus.v33` for mining
diagnostics, memory, spectral, control, and tensor consumers. They do not
replace SHA-256d or obtain consensus authority.

## Reproduction

```bash
ruff check --select E9,F chronus/v33 tests/test_chronus_v33
pytest -q tests/test_chronus_v33
```

Expected:

```text
All checks passed!
................................................                         [100%]
48 passed
```