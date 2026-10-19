# Governed φ and VQC intelligence organs

Date: 2026-10-04

## Purpose

Expose verified golden-ratio mathematics and the repository's existing bounded 384-parameter VQC as governed EUCLID intelligence organs without transferring execution or mining authority.

## φ/PULVINI organ

The mathematical core is recovered byte-exactly from `EUCLID_PROD_GOLDEN_RATIO_ELEVATION_20260719.zip` (SHA-256 `7dae964b8065f0c6fb2e63f720e8321b06c304669eb0c2e6d74f01a9b7e5e8a5`). It provides deterministic identities, working-set laws, Beatty scheduling, Lucas/great-scaler ladders, RL discount, Fibonacci allocation, federated weights, FEC positions, filter centres, and related primitives.

The organ is read-only. PULVINI depth 2 is labelled bounded; depth 4 remains internal. HERMES reports `claims_authorized=false` because no physical accelerator measurement is supplied.

## VQC organ

The adapter reuses the existing source at `turing_universal_quantum_computer/turing_universal_quantum_computer/variational.py` (Git blob `f1c15c8459916913c74387800cfc12fff9c594c8`). It does not copy or replace the circuit.

The existing implementation already declares 32 faces × 4 layers × 3 parameters = 384 parameters and performs candidate ranking on a classical NumPy substrate. The organ has proposal authority only. Returned candidates are explicitly unverified and require the canonical SHA-256d/target path.

## Validation

```bash
python -m py_compile hyba_substrate/golden_ratio_library.py hyba_substrate/phi_multi_use.py euclid/organ_adapters/*.py tests/test_phi_vqc_intelligence_organs.py
python -m unittest -v tests.test_phi_vqc_intelligence_organs
```

Focused adapter result: 6/6 passed. The underlying golden-ratio archive suite independently passed 7/7 and reproduced identity seal `0ad0de2a94bd4dd37e4c5a982d011d05bfcde153c9279660131d66eb3292bae3`.

## Claim boundary

No physical QPU, GPU, speedup, profitability, accepted share, block discovery, or production certification is claimed. Neither organ can alter headers, targets, SHA-256d, credentials, submission, pool acknowledgement, or share truth.
