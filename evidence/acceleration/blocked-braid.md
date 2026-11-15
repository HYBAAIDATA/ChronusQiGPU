# F/R and pentagon qualification: blocked, not waived

The present `CyclotomicBraidCompiler` exposes two exact matrices and an Artin-relation check. It does not expose specified Fibonacci F and R data or a pentagon verifier. The [failing executable test](blocked_braid_test.py) and [actual output](blocked_braid_output.txt) record this missing interface, not a failed proof of an existing pentagon implementation. Run:

```sh
PYTHONPATH=src python evidence/acceleration/blocked_braid_test.py
sha256sum -c evidence/acceleration/blocked-braid-SHA256SUMS
```

The command exits 1. To complete this step, specify the precise fusion category, fusion bases, gauges, normalizations and exact algebraic coefficient domain, provide appropriate F and R matrices, and verify all required pentagon and braid relations with exact arithmetic and the seven-class suite. Do not substitute identity matrices and call them Fibonacci data. A successful Artin relation in the existing representation alone does not establish the requested F/R and pentagon identities.

The committed multiplier counterexample and timing blocker are [here](../cyclotomic/rtl-overflow-finding.md). The target must identify an exact implementation target, constraints and toolchain before timing can be measured. The existing failing simulation is not a timing run.
