# Python package layout

The repository ships GPU, iGPU and L-HRAS as first-class packages in the main
`pythia-mla1517` distribution.

```text
gpu/
├── __init__.py          canonical GPU project API
├── backends/             lazy iGPU and ASIC compatibility facades
├── fleet.py              lazy heterogeneous fleet facade
├── tensor.py             measured tensor accounting and VQC tensor loaders
├── quantum.py            fail-closed Turing VQC facade
├── manifold.py           production Aethel manifold facade
├── readiness.py          software and physical-evidence release gates
├── reference.py         deterministic matrix/QFI/Grover/SHA-256d oracles
├── provenance.py        evidence validation
└── BLUEPRINT_AUDIT.md   implementation and hardware status

igpu/
├── __init__.py          lazy public API; safe on hosts without accelerators
├── detect.py            explicit hardware discovery
├── device.py            iGPU facade
├── engine.py            OpenCL execution
├── opencl_host.py       OpenCL host binding
├── runtime.py           runtime integration
├── telemetry.py         measured evidence
├── seam/                scheduling, contracts, invariants and receipts
├── kernels/             packaged OpenCL source
└── deploy/              reference container configurations

l_hras/
├── __init__.py          public Guardian API
├── guardian.py          orchestration
├── types.py             public contracts
├── config.py            configuration validation
├── substrates.py        sole repository-specific substrate boundary
├── attestation.py       attestations and composition
├── governance.py        enterprise governance
├── observability.py     health, metrics and alerts
├── selfdefense.py       integrity and witness mode
└── foundations/         reviewed mathematical boundaries
```

## Packaging rules

1. All roots and their Python subpackages are listed explicitly in
   `pyproject.toml`.
2. Both packages publish `py.typed` under PEP 561.
3. OpenCL kernels, deployment templates and the L-HRAS example configuration
   are package data rather than undeclared repository files.
4. Importing `igpu` must not probe hardware or require optional drivers.
5. L-HRAS repository coupling remains isolated in `l_hras.substrates`.
6. New Python subpackages must include `__init__.py`, tests and a package-data
   declaration when they contain runtime resources.
