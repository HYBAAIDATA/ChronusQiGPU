# Bounded state operations report

Status: **engineering prototype, not release-qualified**. The partial layer has Fourier and state operations. Other modules in the work order are not implemented by this change.

## Scope and limits

`normalize(values)` produces a normalized complex vector; `apply_unitary(values, matrix)` validates a normalized input and a unitary matrix, then returns their product. Inputs are explicit, one-dimensional, finite, and at most 256 entries; the matrix is explicit and square. Validation uses absolute tolerance 1e-10, no relative tolerance. The norm calculation scales first in `normalize`; exceptionally large magnitudes that overflow even during magnitude evaluation are refused. Array conversion occurs before size checks, so this interface alone is not a resource-isolation control for untrusted input. Approximation and roundoff remain. It does not supply customer authentication, security guarantees, or an optimized unitary-checking algorithm.

## Evidence

- [State test output](state-tests.txt) records 18 passing cases across the seven classes and 100 deterministic generated examples in the property test. [State coverage](state-coverage.json) records 96% branch-inclusive module coverage. Tests run in an isolated workspace, not a full repository checkout.
- [Combined output](state-combined-tests.txt) records 34 passing Fourier and state tests, including a cross-module Fourier/state integration check. The end-to-end test exercises the mathematical API only, not a customer journey.
- [Raw benchmark](../../benchmarks/acceleration/state_raw.json) and [script](../../benchmarks/acceleration/state_benchmark.py) compare repeated state preparation, validation and application against an independent direct NumPy formulation for the same generated inputs. Inputs are generated outside the timed region; all repetitions and final output vectors are retained. The baseline assumes valid benchmark input shapes and nonzero norms, and is not equivalent for arbitrary invalid input. This is a small synthetic experiment, not evidence of generalized acceleration or of customer value.
- [SHA-256 manifest](state-SHA256SUMS) can be verified from the repository root using `sha256sum -c evidence/acceleration/state-SHA256SUMS`. It is an integrity aid, not a signature, independent validation or authorization.
- A workflow job is specified, but its execution and repository-wide CI checks have not been verified. At the time of this report GitHub returned 403 for check-run access. No full checkout, customer workload, certification or independent security assessment was established.

Reproduce with NumPy, pytest, pytest-cov and Hypothesis installed:

```sh
PYTHONPATH=src python -m pytest -v tests/acceleration/test_state.py --cov=chronus.acceleration.state --cov-branch --cov-fail-under=90 --cov-report=term-missing
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src python benchmarks/acceleration/state_benchmark.py > state_raw.json
```
