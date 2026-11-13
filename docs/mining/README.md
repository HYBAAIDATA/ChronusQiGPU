<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:5e491681af2c264812fa7c1c60fc6b7327e44862e393b853f3bfe342d72397c4 -->

# Mining implementation and evidence

The live runner uses authored geometric/Galois traversal, Hendrix and TURING
exact operations. Lucas/PV supplies structural extension-field factors at
10^12, 10^15, 10^18 and 10^20. Lane coverage remains disjoint and every submitted
candidate is independently checked with SHA-256d against its job's exact target.

## Run the checks

From the repository root, after installing the root development/mining extras
and the local `packages/turing` distribution:

```bash
python -m pytest -q tests/test_mining_readiness.py tests/test_extension_search.py tests/test_scaling_paths.py tests/test_pv_scale_fleet.py
python tools/verify_galois_invariant.py --output /tmp/mining-galois-invariant.json
python deploy/hyba-mine/bist.py
```

The verifier checks all six fixed vectors, independent matrix parity, exact
period 516, anti-period 258, Lucas norm parity and readonly unsigned storage of
at least 16 bits. It emits function/module SHA256, raw timing samples and integer
`median_ns`. Inputs and schema are deterministic; elapsed timings vary by host.
The checked-in [sample artifact](galois-invariant.json) records one local run.

[Mathematical assessment](mathematical-assessment.md) explains the verified
identities and the proof obligations for broader computational claims.
[Arithmetic comparison](pv-acceleration.json) measures the previous linear
arithmetic against period lookup. Neither artifact measures mining hashes per
second, a competitor comparison, or network market share. The reported 5x
mining baseline was not located in the inspected PR descriptions/reviews.

## Fleet integration and deployment

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:364a6c6480dc2402c9eac3cfde8e36a977262f89906d47b658784b1cda8d8032 -->

[Structural fleet scaling](../fleet/PV_SCALING.md) documents the reusable exact
scaling kernel and the distinction between field and integer lattice domains.
[Folded state execution](../fleet/FOLDED_STATE.md) documents the optional exact
OpenCL state pipeline, one-launch jumps and host-owned high quotient limbs.

<!-- /coderabbit-ai-generated:v1 -->
[Deployment readiness](../../deploy/hyba-mine/READINESS.md) lists the operational
gates. Local synthetic-pool tests and isolated image self-tests do not replace
host pool acceptance, physical GPU measurements or a sustained operational run.
No live fleet deployment was performed from this sandbox.


<!-- /coderabbit-ai-generated:v1 -->