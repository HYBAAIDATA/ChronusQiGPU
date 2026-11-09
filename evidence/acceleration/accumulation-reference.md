# Accumulation reference experiment and open qualification

Source: `src/chronus/hw/zeckendorf.py`, Git blob `1687afd68d841bb9ededc675d4fb6e5afd63e6fe`, read from PR source in a partial export. The [raw experiment](../../benchmarks/acceleration/accumulation_reference_raw.json) times seven complete calls each for the existing Zeckendorf reference, ring integer addition, and a binary64 addition loop. All start at 2^53 and add one 100 times. The two exact representations returned 9007199254741092; the baseline returned 9007199254740992, an error of -100 for this deliberately chosen numerical example. This is a workload-specific result, not an overall advantage. Timings are in the raw record; the scope includes setup. It is not a throughput measurement of the ALU, nor does it compare mathematically equivalent error guarantees for all inputs.

[Failing input test](blocked_zeckendorf_test.py) and [output](blocked_zeckendorf_output.txt): for 2^128, which exceeds the stored Fibonacci table, the reference raises an invariant error rather than producing the exact round trip. This is outside the stated 64-bit design scope; the result identifies an input-domain limitation, not a claim of a failure inside the intended range. The docstring says n >= 0 without an explicit maximum. No new implementation or complete seven-class ALU evidence is asserted.

```sh
PYTHONPATH=src python -u evidence/acceleration/blocked_zeckendorf_test.py
PYTHONPATH=src python benchmarks/acceleration/accumulation_reference.py > /tmp/accumulation_reference_raw.json
sha256sum -c evidence/acceleration/accumulation-SHA256SUMS
```

The first command exits 1. To qualify the requested ALU comparison, establish the actual allowed input range, specify the execution target and measurement procedure, run equivalent operations through the actual ALU and the baseline, and commit seven classes plus coverage and throughput evidence. The current experiment is a partial reference result and not the requested ALU measurement.
