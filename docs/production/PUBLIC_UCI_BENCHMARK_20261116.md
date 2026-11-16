# Real observed public data — first measured Chronus capability results

**Date:** 16 November 2026, local isolated Linux CPU worker; private engineering evidence.
**Classification:** `ISOLATED_SOURCE_BYTE_VERIFIED`, **not** full Chronus, deployed Triad, hardware or production qualification.

## Inputs: externally published observations, not generated benchmark data

No test samples, nonces, statevector experiments, simulated hardware or fabricated
baselines were generated. We used the copies of UCI observational datasets
distributed with **scikit-learn 1.8.0**, independently corroborated against
the documented UCI origins. The script
`scripts/benchmarks/prepare_public_uci_data.py` deterministically serialises
the original numeric features to uncompressed `.npy`; `wine_data.csv` bytes
are copied unchanged for the **opaque-byte** test (not a true production state).

| Input | Original observations | Dataset provenance | Source SHA-256 (resulting input file) |
| --- | ---: | --- | --- |
| Handwritten digits | 1,797 × 64 | [UCI Optical Recognition of Handwritten Digits](https://archive.ics.uci.edu/dataset/80/optical+recognition+of+handwritten+digits), `load_digits()` | `0f1c225bbabf3d4eaccd81f73c9594ceec77d84c9b425ef0e4cc815743050529` |
| Wine recognition | 178 × 13 | [UCI Wine](https://archive.ics.uci.edu/dataset/109/wine), `load_wine()` | `09af9db3ce2a52b3f168d5d9eb1d4d4ceba584fad9e0e9aba63ff536c192c6a6` |
| Wisconsin breast cancer feature observations | 569 × 30 | [UCI WDBC](https://archive.ics.uci.edu/dataset/17/breast+cancer+wisconsin+diagnostic), `load_breast_cancer()` | `602e781b91843b0ea3dc8bf3ff3e63055985230cad47c45a5099780e3c33459f` |
| Unmodified packaged wine source bytes | 11,157 bytes | `sklearn.datasets.data/wine_data.csv`; opaque-copy test only | `10e8a802908b34f86e5da8ce962f3c806694bc98450a18f61851af59f324bede` |

The original UCI source and the scikit-learn redistribution are distinct from
the new `.npy` serialisation. SHA-256 anchors bind **the benchmark inputs**,
not necessarily the original UCI download files. No private customer data was used.

## Source fidelity — actual maintained Chronus modules

We copied the following maintained source **byte-for-byte** from the private
GitHub repository and validated each as its exact Git blob SHA-1 before running
it. This is a module-local execution, not a checkout of the entire repository.

| Source | Verified Git blob SHA-1 |
| --- | --- |
| `src/chronus/pulvini/formal.py` | `863c0397e9c9e8ee9935183f4b736153b8160f8b` |
| `src/chronus/pulvini/interop.py` | `6b6a9d848799235de1427c2d31e04cf33a6139c7` |
| `src/chronus/pulvini/__init__.py` | `7710d94658f7bae88f202866214fc23f4343c062` |
| `src/chronus/execution/structural.py` | `d9d9fc82a64d98f2d78cc79bb172dff9ecb6c090` |
| `src/chronus/tensor/folded_state.py` | `2eaca5ff169d1c5b8256a76347acef4f630164d0` |
| `src/chronus/tensor/geodesic.py` | `b561ce6541da08ec386bc5dc564b03b35b535d5e` |

**Environment:** Python 3.13.5; NumPy 2.3.5; scikit-learn 1.8.0;
Linux `6.18.57-x86_64-with-glibc2.41`; five reported logical CPUs.
Actual CPU model, governor, process isolation, load, GPU/device and energy
were **not measured**. Do not extrapolate latency to customer or fleet targets.

## Measured result 1 — PULVINI V3

Depth 4, orthonormal normalisation, 31 samples after three warm-ups. The
`fold_verified` call **already includes internal reconstruction and verification**;
the additional `unfold_verified` call was timed separately.

| Input | Median fold+verify | Median additional unfold+verify | Relative reconstruction error | Original / active / kernels / complete retained |
| --- | ---: | ---: | ---: | --- |
| Digits | 33.703 ms | 11.168 ms | 3.48e-16 | 920,064 / 134,240 / 1,271,504 / 1,405,744 B |
| Wine | 0.319 ms | 0.170 ms | 4.46e-16 | 18,512 / 2,696 / 25,576 / 28,272 B |
| Breast cancer | 2.796 ms | 0.407 ms | 3.34e-16 | 136,560 / 19,928 / 188,728 / 208,656 B |

**Result:** numerical reconstruction passed at 1e-12 tolerance.
These reconstructions are **not byte-identical**. The working-set ratio is
about **6.85×** but the full retained representation is about **1.53×
the original bytes** (i.e. it *increases* retained storage). Nothing here
supports net compression, storage savings, physical quantum semantics or
a 13× performance advantage. See original per-call distribution JSON
`real_public_pulvini_31runs.json` retained in the private measurement bundle.

## Measured result 2 — exact resident-state byte representation

`ExactFoldState.from_bytes` and `unfold` executed five times each, with 31
timed 64-byte partial accesses per folded state. Byte-by-byte recovery:
**PASS for all four inputs**.

| Input | Fold median | Full-unfold median | 64-byte partial-read median | Encoded / original bytes |
| --- | ---: | ---: | ---: | ---: |
| Digits .npy | 334.915 ms | 353.615 ms | 17.44 µs | 920,192 / 920,192 |
| Wine .npy | 10.451 ms | 12.485 ms | 18.51 µs | 18,640 / 18,640 |
| Breast cancer .npy | 92.352 ms | 93.533 ms | 18.77 µs | 136,688 / 136,688 |
| Original packaged wine source | 6.482 ms | 6.914 ms | 18.81 µs | 11,158 / 11,157 |

The odd-length source is padded by one byte. **This is no compression**.
Partial timing is an observed application call, not an asymptotic O(1) proof
or a physical IOPS measurement.

## Measured result 3 — PhiTensorCore vs the same NumPy add reference

201 alternating-order sequential samples per operator after ten warm-ups.
Same exact `float64` arrays; outputs independently compared for equality.

| Input | Standalone NumPy median | Chronus PhiTensorCore median | Chronus / NumPy latency |
| --- | ---: | ---: | ---: |
| Digits | 81.679 µs | 83.086 µs | **1.017×** |
| Wine | 1.656 µs | 2.504 µs | **1.512×** |
| Breast cancer | 9.839 µs | 10.506 µs | **1.068×** |

**These values are latency ratios, not speedups.** Greater than 1 means the
Chronus wrapper was slower in this reference run. The selected backend was
`numpy-reference`, no physical accelerator. Tiny timings have material host
jitter; do not use these single-host observations to set pricing or SLAs.
The `numpy-reference` path calls NumPy internally, so this is mainly
wrapper and measurement overhead, not an independent execution algorithm.

## Evidence, reproducibility and next gate

The complete local evidence package contains:
`real_public_pulvini_31runs.json`,
`real_public_exactfold_5runs.json`,
`real_public_tensor_core_201runs.json`,
`reference-only.json`, input `manifest.yaml`, source-file checksums,
and the exact source-verified local execution harnesses. These raw files
are local artifacts, **not** signed production receipts.

- Local source-extracted contract tests: **10 passed**, explicitly not full repo tests.
- GitHub Actions: incomplete/unavailable; do not promote as current-head CI.
- Real `ProductionTriad` end-to-end: **NOT RUN** on this host (full private
  repository and its runtime dependencies were not present).
- Device-bound performance, cloud deployment, tenant isolation, customer
  data rights, whole-system energy and net savings: **UNAVAILABLE**.
- Exact H4 mathematical traversal and non-Clifford physical execution:
  **NOT TESTED** by these datasets.

Run the public-data script in an authorized, up-to-date repo checkout,
then the maintained benchmark:

```bash
python -m pip install 'scikit-learn==1.8.0'
python scripts/benchmarks/prepare_public_uci_data.py --output /secure/uci-observed
python benchmarks/real_workload_benchmark.py \
  --manifest /secure/uci-observed/manifest.yaml \
  --custody-db /secure/uci-observed/custody.sqlite3 \
  --output /secure/uci-observed/chronus-full-evidence.json \
  --depth 4
python scripts/demo/real_data_proof_report.py \
  --evidence /secure/uci-observed/chronus-full-evidence.json \
  --output /secure/uci-observed/public-observed-data-proof.md
```

Run any published benchmarks on a pinned release commit and identified host;
collect original timing distributions, detailed environment and independent
attestation. **Do not conflate a verified module-local benchmark with a
production-ready integrated service.**


### Unified component remeasurement (direct maintained source)

After installing the repository, run the exact same CPU-reference component
workloads against the SHA-256-pinned public files. This command measures
`PhiTensorCore`, `PULVINI V3` and `ExactFoldState` directly from the
maintained `chronus` package and writes unsigned, commit-linked per-call
distributions; it does **not** require a production tenant or represent full
Triad deployment evidence:

```bash
python scripts/benchmarks/run_public_uci_components.py \
  --manifest /secure/uci-observed/manifest.yaml \
  --output /secure/uci-observed/component-measurements.json \
  --depth 4
```

This component runner is deliberately separate from
`benchmarks/real_workload_benchmark.py` (which additionally exercises the
full OVID–THESEUS persistent custody path). Do not add their timings
or compare unrelated operations to produce an artificial speedup.
