# Reproduction Guide

From the repository root:

```bash
PYTHONPATH=. python3 -m unittest -v tests.test_euclid_experience_superlearner
PYTHONPATH=. python3 scripts/run_euclid_experience_benchmark.py
```

The benchmark uses 20 matched seeds and three conditions: EUCLID world-model learning, model-free Q-learning, and random action selection. Inspect `artifacts/euclid_experience_benchmark.json` for the full protocol, dispersion, and claim boundaries.

Every authoritative JSON artifact is preserved byte-exactly and canonically in mirrored memory-vault generations. Tensor and phi folds are diagnostics or reversible scaling aids; they do not replace the canonical evidence.
