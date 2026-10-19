# Frozen ARC-AGI-1 training baseline

## Executed outcome

- Training tasks: 400
- Exact task solves: 2 / 400 (0.5%)
- Solved IDs: `007bbfb7`, `c59eb873`
- Execution errors: 0
- Incorrect transformations on non-fallback branches: 290
- Incorrect predictions on unsupported identity-fallback branch: 108
- Sum of runner execution times (second run): 0.077891 seconds
- Two complete runs produced identical per-task outcomes and classifications.
- Four frozen-baseline regression tests passed.
- Public evaluation score: NOT MEASURED.

## Scope and protocol

Unchanged standalone runner from `PhiEnterprise1/EuclidPhiEnterprise` commit `af4e34a3c9463750dc32bcd1eae41f7310944833`, original path `benchmarks/external/arc_agi_runner.py`. The original path was not edited. This baseline copy is byte-identical and its SHA-256 is enforced by the harness. Only DATA_DIR is overridden in memory to point to the training split. This is not an integrated EUCLID-runtime measurement.

One prediction per test input; no candidate search, no model calls, no retries, no explicit per-task timeout. Exact grid equality, including shape, is required on every test input to solve a task. Every error counts as unsolved. Dependency: NumPy 2.5.3; Python 3.13.14. Full platform and per-task timing are recorded in `training_baseline.json`. Timings are environment-specific and not a hardware-normalised comparison.

The harness performs an additional fit after scoring to diagnose consistency with demonstration pairs. That diagnostic cannot change the scored output. Failure categories identify executed code branches, not inferred semantic puzzle families. Ambiguity is not measured because this runner has no ambiguity detector. Regression tests pin existing failures for this frozen copy; future solver acceptance tests should require successful repairs, not preserve these failures.

## Reproduce from repository root

```sh
python euclid/benchmarks/arc_agi_1/verify_dataset.py
python -m pip install -r euclid/benchmarks/arc_agi_1/baseline/requirements.txt
python euclid/benchmarks/arc_agi_1/baseline/run_training_baseline.py
python -m unittest discover -s euclid/benchmarks/arc_agi_1/baseline -p 'test_baseline_regressions.py' -v
```

Re-running overwrites the local training result file. Do not use evaluation data for solver changes. No solver repair or public evaluation run was performed in this import.
