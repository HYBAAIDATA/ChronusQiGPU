# Bounded exact MPS contraction

`contract_mps` contracts explicit binary-physical-index tensors with up to 10 sites and bond dimension up to 4 over `Cyclotomic5`. The output is an explicit unnormalized vector. This implementation uses no floating-point operations; coefficient growth and output size remain resource costs. Inputs are explicit nested lists/tuples and validated before contraction. There is no claim of a general speedup.

[Seven-class test output](ring-mps-tests.txt): 8 tests passed, including bounded exhaustive product states, generated cases, a nontrivial bond example and interaction with coordinate scaling. [Coverage](ring-mps-coverage.json): 100% branch-inclusive for this module in a partial source export. The end-to-end test exercises this mathematical API, not a customer journey. The literal-purity test covers this file only. No universal correctness or release qualification is asserted.

## Same-input experiment

The chosen system is a matrix-product representation of a noninteracting many-body product state |0> at every site, bond dimension 1. MPS are a standard representation for many-body calculations; see Schollwöck, *The density-matrix renormalization group in the age of matrix product states*, https://arxiv.org/abs/1008.3477. This sample is deliberately simple and is not evidence of an interacting-system result. The existing `build_network` / `TensorNetwork.to_statevector` functions are the FP baseline documented in [findings_tensor_baseline.md](findings_tensor_baseline.md). Its normalization is a no-op for this input; the ring result is unnormalized and already unit norm.

[Raw comparison artifact](../../artifacts/acceleration/tensor_system_54c1d6ffe148ea655e251515fbbc07304ba9b250a6a47735ddf7310172267ec7.json) includes both outputs, timing samples, sizes, tolerance, and measured differences for depths 1, 2, 4, 6, 8 and 10. Both outputs agree with the independently specified product state at each depth; measured maximum difference is zero at every tested depth. Neither exceeded 1e-12 within the tested range, so this experiment **does not demonstrate deeper contraction or eliminated drift**. The raw ring coefficients are exact for these inputs; this does not establish zero error for inputs not represented exactly. Execution times are workload-specific. The baseline includes normalization and the ring path includes input validation; network construction is excluded from timing. Full checkout and customer workload were not used.

Reproduce with the referenced source blobs and dependencies:

```sh
PYTHONPATH=src python -m coverage run --branch --include='*/ring_mps.py' -m pytest -v tests/test_ring_mps_seven_classes.py
python -m coverage report -m --fail-under=90
python -m coverage json -o evidence/acceleration/ring-mps-coverage.json
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src python benchmarks/acceleration/ring_mps_benchmark.py > /tmp/ring_mps_raw.json
sha256sum -c evidence/acceleration/ring-mps-SHA256SUMS
```

The checked [manifest](ring-mps-SHA256SUMS) records the SHA-256 digest of each committed file. Timing changes make a rerun's JSON digest different. The sampled depth limit is not a maximum depth for other representations or workloads.
