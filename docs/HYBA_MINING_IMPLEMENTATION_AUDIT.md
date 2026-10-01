# HYBA implementation convergence for mining

## Scope

Reviewed artifacts:

1. `HYBA_1000_QUBIT_VQC_20260724 (2).zip`
2. `chronos-gpu-v3.3-memory.zip`
3. `PULVINI_V3_HERMES_COMPLETION_20260724 (2).zip`
4. `GEODESIC_TENSOR_ENGINE_EXTENDED_20260724.zip`
5. The attached HYB export container, which duplicates the VQC and PULVINI archives.

Target repository: `QuantumPhiEnterprise/PYTHIPhiMiner`.

## Baseline findings

| Artifact | Baseline | Repository disposition |
|---|---|---|
| 1,000-qubit VQC | Compiles, but the archive is not standalone: tests and modules require a missing `euclid...pulvini_enterprise.formal` package. | Keep the repository's consolidated `PhiQuantumMachine`/`PhiGroverVQC`. It uses the exact Turing stabilizer backend, fails closed for unsupported gates, preserves candidate membership, and gives the ranker no proof authority. |
| Chronos GPU v3.3 memory | 35 tests pass. `ruff check --select E9,F .` reports 84 findings. Most of the package is a mathematical graphics/research runtime, not a SHA-256d mining backend. | Do not replace Chronus device execution. Reuse `chronus.runtime.profile` as the measured timing boundary. Mining remains on the existing OpenCL/CPU SHA-256d runtime. |
| PULVINI V3 | Compiles, but the archive is partial: tests reference many absent `pulvini_enterprise` modules and cannot collect. It also contains claims that exceed the supplied evidence. | Use the repository's exact `Fraction`-based PULVINI authority through `python_backend.core_modules.geodesic_tensor_engine`. Treat folding as reversible representation custody, never physical compression or proof. |
| Geodesic Tensor Engine | Compiles, but the archive is not installable under its declared package path and tests cannot collect. The July file mixes exact arithmetic, simulated hardware, and declared energy models. | Use the repository's hardened exact engine and `GeodesicNoncePlanner`. It may only permute an existing nonce window and has no consensus authority. |

## Product seam added

`chronus.mla1517.mining.hyba_intelligence.HYBAIntelligencePipeline`
provides one bounded call for the miner:

```python
result = HYBAIntelligencePipeline().prepare(header80, nonce_window)
ordered_nonces = result.candidates
```

The call:

1. validates a unique bounded uint32 window;
2. performs an exact PULVINI custody round-trip;
3. applies Geodesic ordering;
4. applies φ-VQC ranking;
5. measures each real call through Chronus;
6. verifies candidate membership after every advisory stage;
7. reports degraded fallbacks and measured wall time;
8. never validates proof, changes a target/header, submits a share, or interprets a pool response.

Consensus remains the repository's independently rechecked Bitcoin SHA-256d
target comparison.

## Reproduction

Supplied archive baselines:

```bash
python -m compileall -q <artifact>
ruff check --select E9,F <artifact>
PYTHONPATH=src python -m pytest -q chronos-gpu-v3.3-memory
python -m pytest -q HYBA_1000_QUBIT_VQC
python -m pytest -q PULVINI_V3_HERMES_COMPLETION
python -m pytest -q GEODESIC_TENSOR_ENGINE_EXTENDED
```

New seam:

```bash
ruff check --select E9,F chronus/mla1517/mining/hyba_intelligence.py \
  tests/test_hyba_intelligence.py
pytest -q tests/test_hyba_intelligence.py
```

## Remaining hardware evidence

Software tests cannot establish:

- target-host OpenCL availability;
- kernel compilation/execution on the intended iGPU;
- measured throughput improvement from either ordering heuristic;
- pool acceptance or credited shares.

Those claims require the existing production mining runbook on the target host.