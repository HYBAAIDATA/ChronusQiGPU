# Bounded Fourier capability report

Status: **engineering prototype; not release-qualified**. This report covers only the Fourier module, not the proposed acceleration layer as a whole. The other proposed modules and a customer journey have not been implemented or validated here. The source baseline is commit `8fddfd17eb776a95e0eec1d1514dd48290c905b4`; the review and work order precede this module in branch history.

## What is implemented

`chronus.acceleration.fourier.qft` computes a normalized positive-sign discrete Fourier transform of a finite explicit one-dimensional power-of-two vector of length 1–4096, with an inverse option. It rejects invalid dimensions, nonfinite inputs and nonfinite output. Conversion to an array precedes the length check; this is not an externally exposed resource-isolation boundary. Floating-point results are approximate. Input loading and output materialization are not free.

## Evidence

- [Local test log](fourier-tests.txt): 16 test cases passed across seven named classes; property generation is seeded by Hypothesis's deterministic mode. The end-to-end test is a mathematical API journey, not a customer sign-in or settlement journey. Tests ran against the added files in an isolated local workspace, not a complete repository checkout.
- [Local branch coverage](fourier-coverage.json): 100% for this module in that run, not a correctness proof or repository-wide measurement.
- [Benchmark raw output](../../benchmarks/acceleration/fourier_raw.json) and [benchmark script](../../benchmarks/acceleration/fourier_benchmark.py): repeated timings, full transform outputs, size, environment, checks and exact method. The only implemented operation is also the entire scope of this partial layer benchmark; it is not a whole-product or customer-workload benchmark.
- [SHA-256 manifest](SHA256SUMS) covers code, tests, logs and benchmark. Verify from the repository root with `sha256sum -c evidence/acceleration/SHA256SUMS`. Hashes demonstrate integrity relative to the manifest, not authenticity or correctness. No conformant signature or verification endpoint is established.
- A dedicated workflow has been added, but a successful named CI run has not been verified by this report. Existing repository-wide CI, package installation, service integration and customer execution are not verified by the isolated local run.

## Interpretation and refusal

The raw record compares exactly the same explicit transform with direct matrix evaluation and an optimized FFT. It includes function-call timing but excludes input construction and result verification; direct matrix construction is included. It is a small synthetic single-environment experiment, not an asymptotic proof or a customer benchmark. The implementation wraps an optimized FFT with validation; do not claim a general acceleration over that baseline. Do not interpret this as an exponential advantage, a service SLA, security assurance, certification, independent audit, analyst endorsement, or customer reference. Missing release requirements remain blockers in the [work order](../../work_orders/acceleration.md).

Reproduce locally after installing NumPy, pytest, pytest-cov and Hypothesis:

```sh
PYTHONPATH=src python -m pytest -v tests/acceleration/test_fourier.py --cov=chronus.acceleration.fourier --cov-branch --cov-fail-under=90 --cov-report=term-missing
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src python benchmarks/acceleration/fourier_benchmark.py > fourier_raw.json
```
