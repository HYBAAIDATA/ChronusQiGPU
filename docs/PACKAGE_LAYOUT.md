# Python package layout

The repository ships iGPU and L-HRAS as first-class packages in the main
`pythia-mla1517` distribution.

```text
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

1. Both roots and their Python subpackages are listed explicitly in
   `pyproject.toml`.
2. Both packages publish `py.typed` under PEP 561.
3. OpenCL kernels, deployment templates and the L-HRAS example configuration
   are package data rather than undeclared repository files.
4. Importing `igpu` must not probe hardware or require optional drivers.
5. L-HRAS repository coupling remains isolated in `l_hras.substrates`.
6. New Python subpackages must include `__init__.py`, tests and a package-data
   declaration when they contain runtime resources.
