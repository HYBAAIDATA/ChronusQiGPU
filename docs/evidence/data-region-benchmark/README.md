# Current data benchmark correction — local qualification

## Decision and scope

Correct the evidence entry point; do not alter the mathematical engines or infer
a valuation from the withdrawn benchmark. Base inspected live:
`PhiEnterprise1/EuclidPhiEnterprise@cd80d0371e50979cb5d1e704bafd41f70f0044d8`.
This is a review-branch correction, not production-release approval.

The old `benchmarks/production_workload_benchmarks.py` imported a mining-specific
implementation, silently substituted truncated copies when unavailable, compared
matrix multiplication with folding/copying, and labelled a >1.1 timing ratio as
statistical significance. The directory's DEPRECATED notice concerns legacy
documentation; it did not prevent this executable from producing reports.
The runner now raises `LegacyBenchmarkUnavailable` at construction. Historical
result classes remain readable; new execution is intentionally withdrawn.
No current engine is replaced or duplicated.

## Current paths and boundaries

- Numeric addressed data reads: `aethel.phi_fold.unfold_region`.
- Exact rational PULVINI: `python_backend.core_modules.geodesic_tensor_engine`,
  via `tensor.pulvini_bridge`; a distinct plane, not interchangeable with numeric partitioning.
- Folded linear execution: `tensor.folded_inference.FoldedLinearPilot` ->
  `tensor.api.TensorRuntime.execute`; existing tests retained, not benchmarked here.
- Current durable object authority: `aethel.ovid_authority.OvidAuthority`;
  `aethel.theseus_projection.TheseusProjection` is rebuildable from that authority.

## Reproduce the replacement measurement

From the repository root with NumPy installed:

```bash
python -m scripts.benchmark_data_region --output region-report.json
```

The runner requires identical shape, dtype and bytes for **every** warmup and
measured output. It compares direct dense-region copying, full decode followed
by region copying, and the actual selective decode. Order is rotated; raw timing
samples, source hashes, region and input identity are retained. Fold setup is
separate. Validation is outside each measured call. The direct-region baseline
must not be omitted to imply that full decoding is the only alternative.
Dependency or correctness failures propagate; there is no truncating fallback.

`local-region-report.json` is one synthetic 256x256 float64 local run. It checks
an 8x8 region: all three paths returned identical 512-byte outputs. Selective
instrumentation counted 64 source values out of 65,536. This is an implementation
read count, **not** physical bus traffic or a capacity measurement. Array payload
bytes include every complement; object overhead, peak RSS, energy, physical
compression, statistical significance, enterprise savings and fleet scaling
remain unmeasured. Timings are local samples, not significance or universal speed claims.
Neither this run nor the defective old run establishes a ceiling on the wider
HYBA Data capability or a company valuation.

## Executed qualification

```bash
python -m pytest -q tests/test_data_region_benchmark.py tests/test_region_decode.py tests/test_folded_inference.py tests/test_phi_fold_dtype_custody.py tests/test_ovid_exactness_verification.py tests/test_theseus_recovery_replay.py
python -m compileall -q scripts/benchmark_data_region.py tests/test_data_region_benchmark.py benchmarks/production_workload_benchmarks.py
```

Final result: **91 passed in 0.81s**, no failures/skips in this selected run;
compileall exited 0. This comprises 23 new tests and 68 existing selected tests.
The new real-owner integration test writes an OVID object to disk, builds and
deletes its THESEUS projection, reopens the OVID owner and rebuilds an identical
projection generation. Fault-injection unit tests intentionally monkeypatch the
benchmark wrapper only; they are not integration acceptance substitutes.
Environment: Python 3.13.14, NumPy 2.5.4, pytest 9.1.1, Linux x86_64.

## Source and execution limitations

Tests ran in a local archive copy aligned to live source, **not** a full Git
checkout. The initial archive-based 90-test run was superseded. Aligning only
the current package initializer first caused six collection errors against its
older triad module; these were snapshot mismatches, not waived successes.
The seven differing/missing top-level Aethel modules were then retrieved at the
pinned commit. All 36 top-level Aethel Python files, and seven listed runtime/test
files, match live Git blob hashes (`source-parity.json`). The final 91-test run
used that aligned source. Files outside this recorded parity scope have not
been claimed to be a complete checkout of the pinned commit.

No remote CI, full-repository test suite, installed-distribution qualification,
customer-workload benchmark, deployment or merge was executed. Those checks are
not recorded as passing. No CI workflow, pricing, engine, licence or product
boundary was changed. Review and clean-checkout execution remain required before
merging this correction; this is not a substitute for HYBA Data's wider evidence.
