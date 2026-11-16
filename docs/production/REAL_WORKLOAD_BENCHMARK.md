# Real-workload benchmark — bounded, evidence-first

## Scope and authority

`benchmarks/real_workload_benchmark.py` accepts *only* explicitly declared, full-SHA-256-pinned on-disk assets. It does not generate input arrays, invent source files or infer that arbitrary discovered files are genuine production data. No production asset was available to the implementer, so **production measurements are unavailable**.

The supplied draft referenced APIs that do not exist in the maintained tree (`chronus.compute.pulvini.PULVINIV3`, `chronus.manifold.h4.H4Manifold`, `chronus.unfold.partial.TruePartialUnfold`, and a `PhyllotaxisStorage.write/read` service). This implementation uses the maintained APIs without modifying their authority:

- Chronus: `PhiTensorCore`, `GeodesicScheduler`, `MetricTensor`, `ExactFoldState`; software NumPy reference execution.
- PULVINI V3: existing protected `fold_verified` / `unfold_verified`; float64/complex128 numerical reconstruction, with the **full retained kernel state** counted. Not net compression.
- OVID: representation transforms/materialisation through `ProductionTriad`.
- THESEUS: durable tenant-scoped SQLite/WAL custody, restart readback and journal continuity through `ProductionTriad`.
- Phyllotaxis: implemented within existing durable-store addressing; no nonexistent standalone PhyllotaxisStorage I/O API is asserted.
- No PYTHIA, TURING, EUCLID, Salamander or AL HARAS authority is transferred to this benchmark.

## Input contract

Provide an operator-controlled YAML file using `chronus.real-workload-manifest/1`. Each `data_sources` entry requires `path`, `kind` (`tensor` or `snapshot`), full 64-hex SHA-256, `source_class` and optional `provenance`. `OPERATOR_DECLARED_PRODUCTION` is **a declaration, not third-party proof**. Unit tests use `TEST_FIXTURE_NON_PRODUCTION` explicitly and are **not production benchmarks**.

- Tensor format: `.npy` only, loaded with NumPy `allow_pickle=False`. Unspecified raw `.bin` headers, PyTorch pickle/checkpoints, ONNX graphs and custom tensor formats are rejected until an independently validated safe decoder contract exists.
- Snapshot formats: `.snapshot`, `.state`, `.fold` or `.checkpoint` interpreted as opaque bytes. The test is byte-equivalent reversible representation, *not* semantic recovery of an unknown application state.
- Assets must be nonempty, regular, non-symlinked files, each at most 16 MiB **and** at most the effective THESEUS payload bound (1 MiB by default through `runtime_bounds()`), allowing for an extra OVID padding byte on odd-length input. The smaller bound applies; larger production data requires independently reviewed bounded chunking rather than bypassing custody limits. NPY headers are validated before decoding (4 KiB header cap; numeric data; at most 1,000,000 elements). Duplicate file paths and checksum mismatch fail closed.
- No recursive directory scanning and no implicit fallback to simulated or generated data. Explicit allowlisting prevents accidentally selecting fixtures, sensitive unrelated files or inconsistent snapshots.

Copy `benchmarks/data_manifest.example.yaml` to a private operator manifest, fill in *actual* input paths and verified SHA-256 hashes, and keep customer/private data outside Git. The example intentionally contains no populated source data.

## Execution

Install the current Chronus distribution/dependencies in the target environment, then run:

```bash
python benchmarks/real_workload_benchmark.py \
  --manifest /secure/operator/manifest.yaml \
  --custody-db /secure/benchmark/chronus-custody.sqlite3 \
  --output /secure/benchmark/chronus-real-workload-evidence.json \
  --depth 4
```

The custody DB contains **copies of the actual input payloads** and must reside in an access-controlled directory with retention/encryption appropriate to that data. This benchmark does not alter its input sources. Do not commit generated receipts, DBs or manifests containing sensitive paths.

Run contract tests separately:

```bash
python -m pytest -q tests/test_real_workload_benchmark.py
```

These tests deliberately use marked non-production fixtures to validate safety and correctness; **they do not measure production performance**.

## What is and is not measured

The report contains input SHA-256, explicit provenance status, git commit when locally available, wall-clock `perf_counter_ns` application-call timings, independent NumPy addition output comparison, deterministic Euclidean-4D reference path endpoints when applicable, full PULVINI kernel accounting, exact partial snapshot reconstruction and durable custody readback from a fresh service instance.

The NumPy baseline and Chronus `PhiTensorCore` both use software NumPy; their timings do not establish quantum or physical acceleration. Euclidean-4D endpoints do **not** establish H4 execution. PULVINI working-set ratio is **not** net storage compression. Partial-access latency samples do not prove constant-time complexity. SQLite/WAL application-call timings do not prove NVMe throughput or power-loss recovery. No scaled tableau baseline, fabricated 13x ratio, random H4 target, hardware claim or unconditional success receipt is generated.

`integrity_sha256` is a deterministic digest of the JSON record **not a signature**. Actual authenticated evidence requires THESEUS/AL HARAS-backed attestation and independent source/runtime qualification, outside this script's scope.

`result=PASS` only means the executed software operations and integrity checks completed for the selected inputs. The report always records `production_qualification=UNVERIFIED`, `device_execution=UNVERIFIED`, `external_source_attestation=UNVERIFIED` and `signed_evidence=false`. Missing, modified, incompatible or absent assets fail closed, without writing a success evidence file. Existing evidence outputs are never overwritten; the operator manifest and source files must never be destinations.

## Next qualification gate

Obtain the actual authorized production asset manifest, run on the target machine, retain the exact commit-bound output and independent custody/signing evidence, then reconcile against production qualification gates. The absence of a local asset is **UNAVAILABLE**, never a license to report a simulated or example result.
