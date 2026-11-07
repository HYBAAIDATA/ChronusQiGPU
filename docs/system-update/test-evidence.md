# Chronus Test Evidence

**Scope:** current working-tree implementation of the v36 package

## Recorded verification

The following checks were run after the service, SDK, execution, persistence, and documentation updates:

| Check | Command | Result |
|---|---|---|
| Repository test suite | `/tmp/chronus-system-update-venv/bin/python -m pytest -q` | **118 passed** with a CPU OpenCL runtime available; one third-party deprecation warning |
| RTL testbench | `iverilog -g2012 -o tb_phi hw/tb_qigpu_phi_alu.sv hw/zeckendorf_norm_alu.sv && ./tb_phi` | **TB PASS** (norm and fold known-answer vectors) |
| RTL synthesis | `yosys -Q -T -p 'read_verilog -sv hw/zeckendorf_norm_alu.sv; hierarchy -check -top qigpu_phi_alu; synth -top qigpu_phi_alu; stat'` | **Passed**; 4,622 generic cells, zero inferred memories |
| Active implementation lint | `ruff check --select F src/chronus/execution src/chronus/backends src/chronus/service src/chronus/sdk src/chronus/security tests` | **Passed** |
| Active package syntax compilation | `/tmp/chronus-system-update-venv/bin/python -m compileall -q /root/Chronusv2/src/chronus/config.py /root/Chronusv2/src/chronus/execution /root/Chronusv2/src/chronus/backends /root/Chronusv2/src/chronus/sdk /root/Chronusv2/src/chronus/security /root/Chronusv2/src/chronus/service` | **Passed** |
| Wheel build | `/tmp/chronus-system-update-venv/bin/python -m pip wheel --no-deps --no-build-isolation /root/Chronusv2 --wheel-dir /tmp/chronus-wheelhouse --quiet` | **Passed** (`chronus_quantum_igpu-36.0.0-py3-none-any.whl`) |
| Azure infrastructure compilation | `bicep build infra/azure/main.bicep --stdout` | **Passed**; compilation does not validate deployment permissions or regional availability. |
| Container smoke | Build image; submit and retrieve a workload across a container restart | **Passed** with local Docker; this does not demonstrate container replacement or production persistence. |
| Dependency audit | `python -m pip_audit` | **No known vulnerabilities** in audited installed dependencies; local project package itself is not audited by PyPI lookup. |

The test suite includes exact \(Q(\sqrt5)\) arithmetic, Lucas/PV identity checks, binary payload handling, authentication, tenant isolation, SQLite re-open, SDK-to-service submission, no automatic replay of failed submissions, backend registration, a real Bitcoin genesis SHA-256d vector, 32-lane partition coverage, all byte-pair M15 round-trips, exact lattice parity and overflow rejection. Symbolic scale/fold/store tests cover chained index 4781, seed recovery, canonical-state validation, and agreement with exact expanded arithmetic. Storage tests cover golden-ratio lane distribution, golden-turn coordinates, Theseus tenant isolation, deduplication, tamper fail-closed reconstruction, and QiGPU surface inventory and preference resolution. OpenCL tests exercise each checked execution tier, signed boundaries, cancellation and randomized comparisons on a CPU OpenCL runtime when available; these are not physical GPU evidence. Actual GPU execution has not been tested.

## What this evidence establishes

- The tested source paths execute the two supported native mathematical workload families with exact integer/rational operations.
- The HTTP API and SDK can complete the supported local workload path, and the result can be retrieved by the authorized tenant.
- The current SQLite workload store preserves a workload record across a store re-open.
- The API does not claim release gates passed as a side effect of a successful test; the package-level qualification facade returns `NOT_QUALIFIED` with zero evaluated gates.

## What it does not establish

This is a small software test suite, not system-wide qualification. It does not establish physical GPU/NPU execution, accelerator scaling, global or multi-region durability, production throughput/latency/energy, high availability, a complete threat-model assessment, secure credential lifecycle, Ed25519 key persistence, ML-DSA compliance, zk-STARK/FRI proof soundness, formal proof, regulatory authorization, or customer value.

The compile check intentionally covered active package directories. A separate legacy versioned monolith, `src/chronus/chronus_gpiu-v35.py`, remains syntactically truncated and is not included in that targeted check. Historical source files and reports must not be treated as current executable behavior without separate validation.

## Reproduction

Install the declared development extra and run from the repository root:

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
```

Run the targeted syntax check:

```bash
python -m compileall -q \
  src/chronus/config.py \
  src/chronus/execution \
  src/chronus/backends \
  src/chronus/sdk \
  src/chronus/security \
  src/chronus/service
```

Build a wheel with the declared setuptools backend:

```bash
python -m pip wheel --no-deps . --wheel-dir dist
```

The result table records a local working-tree run; it is not a CI attestation for a commit or release artifact.
