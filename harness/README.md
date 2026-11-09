# Reference measurement harness

This harness measures the reference codec; it does not establish product capacity. It requires Python and a checkout with Git. No external packages are required.

Create a labels JSON object mapping every relative input filename to a nonempty class label. Create a hardware JSON object with `cpu`, `ram`, `disk` and `gpu`; use `not used` for an unused accelerator. Run from the repository root:

```sh
python harness/capacity.py --data-dir artifacts/samples --labels /path/to/labels.json --hardware /path/to/hardware.json --output-dir artifacts/capacity
```

The codec and harness must match the committed checkout. Artifacts are SHA-256-addressed over exact JSON bytes and never overwritten. Record input labels and hardware accurately. Avoid committing private customer samples or machine identifiers without authorization. The manifest hash covers paths, labels, sizes, and content digests in deterministic order; it is not a hash of a tar archive. Ratio includes the header. Decode latency uses nearest-rank per-call timings. Bytes produced are not physical write amplification. Recovery is explicitly unmeasured because the reference codec has no recovery implementation. Neither is represented as a successful result.

For a source export rather than a Git checkout, `--export-commit` and `--export-codec-blob` must both be supplied. The codec blob is verified locally, but its association with the commit and the harness source must be independently verified. Record this limitation when reporting the run.
