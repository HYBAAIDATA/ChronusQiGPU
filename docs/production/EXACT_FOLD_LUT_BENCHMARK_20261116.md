# Exact M15 vectorized byte-pair implementation — 16 November 2026

This elevates the maintained ExactFoldState code, not the protected PULVINI research core. Original scalar transform and inverse are exactly the M15 and inverse arithmetic in Z/256Z. A read-only full-domain uint16 lookup table vectorises the work with NumPy; no float arithmetic, approximate reconstruction, lossiness or independent compression claim. Partial unfolds continue decoding only the required aligned byte pairs. Source SHA-256 digest verification on full unfold remains mandatory.

## Same-workload local CPU measurements

Observational datasets are real recorded UCI feature vectors serialized deterministically using scikit-learn 1.8.0. Every input was verified against its separately pinned SHA-256. Two warmups then 13 measured calls per operation per dataset. This is isolated matched CPU evaluation, **not** a full current repository checkout, an iGPU device speedup or a production workload claim.

| Dataset | Old fold median | Vectorized fold median | Observed speedup | Old unfold median | Vectorized unfold median | Observed speedup |
|---|---:|---:|---:|---:|---:|---:|
| Digits | 79.754 ms | 1.323 ms | 60.27x | 79.488 ms | 1.410 ms | 56.36x |
| Wine | 2.028 ms | 0.0352 ms | 57.62x | 1.829 ms | 0.0350 ms | 52.21x |
| Breast cancer | 14.434 ms | 0.2138 ms | 67.52x | 14.163 ms | 0.2046 ms | 69.21x |

All 65,536 possible byte pairs were checked against the scalar reference, including the inverse. Input and output digests and full original bytes matched. See evidence/benchmarks/real-uci-lut-fold-20261116.json for each raw timing sample, environment, dataset SHA and exact status. These timings do not include upstream source loading, I/O or fleet execution, and cannot be extrapolated as whole-pipeline speedup. Full integrated test execution on the merged revision remains unverified.
