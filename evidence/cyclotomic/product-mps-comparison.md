# Product-state MPS: exact versus repository floating-point path

Experimental 1D bond-dimension-one MPS, inspired by the MPS representation in Pérez-García et al., Reviews of Modern Physics 93, 045003 (2021), https://doi.org/10.1103/RevModPhys.93.045003. It is a synthetic product state, not a solved many-body Hamiltonian or a customer workload. Site values are `(100000001, 99999989)`; depths 1–13 are run with identical tensors. Raw outputs for depth 8, all per-depth measurements, input, implementation hashes and environment are in the JSON artifact.

The ring path expands the unnormalised tensor and uses integer ring arithmetic only. For all measured depths, it matched every coefficient of an independent direct integer-product oracle (zero mismatches). The existing `TensorNetwork.to_statevector()` path returns a **normalised** complex128 vector. Its components were compared against a 100-digit Decimal normalisation of the same exact integer oracle; Decimal is only in the benchmark oracle, not the ring path. The measurements therefore do not establish an exact normalised ring state and are not a like-for-like timing comparison: the baseline normalises and the ring path does not.

For an explicitly chosen absolute per-component tolerance `1e-18`, the floating-point baseline first exceeded tolerance at depth 1; the unnormalised ring outputs remained exact through the last tested depth 13. These are different error definitions, so this is **not** a demonstrated equal-task deeper-fold advantage; no depth beyond 13 was tested. At depth 13 the FP maximum normalised absolute difference was `1.1309204182293693621784015378668757805150402824257167922165017897189272910704277121190E-16`, and single-run ring and FP timings were 107160073 ns and 397268 ns respectively; timings include different operations, are not repeated statistics, and are environment-specific.

Source commit `71f3ffafa349234860b70b639ac07b270aec5d97`; local run executed GitHub-MCP source text for the existing tensor modules in memory after verifying their Git blobs. The run did not use a full checkout. Local command: `python tools/local_injected_mps_benchmark.py` (temporary injection bootstrap, not committed). Checkout reproduction, not yet verified in a full checkout:

```sh
PYTHONPATH=src python tools/compare_product_mps.py --source-commit 71f3ffafa349234860b70b639ac07b270aec5d97 --output /tmp/product-mps-comparison.json
```

The benchmark was committed after that source commit, so use a checkout containing both and verify the source versions. The tool output records exact input and source. No physical measurement, security or customer benefit is asserted.

SHA-256:

- `tools/compare_product_mps.py`: `d3924dbce9b0d3e027352575d1cd41bbce755fae1ea40cc4d3ba4eef21f23a00`
- `evidence/cyclotomic/product-mps-comparison.json`: `24878c156f6428f61dd6d699cb43dd5babcd8cf74abe74435cfdd9dc03ad33ed`
- `evidence/cyclotomic/product-mps-output.txt`: `d81d80221bb59a6fb7d4c406cedef0b90728c15283ea9044e072038e0b1f484e`

For the artifact-introduction commit use `git log --diff-filter=A -- evidence/cyclotomic/product-mps-comparison.json`.
