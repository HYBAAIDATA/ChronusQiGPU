# Chronus Workflow 02 — Hardware & Accelerator Certification

<aside>

No physical backend may be represented as production-certified without device-bound evidence.

</aside>

## Sequence

1. Device census and fingerprint.
2. Driver/runtime/compiler/toolchain capture.
3. Capability and precision probe.
4. Known-answer self-test.
5. Reference-vs-device differential.
6. Boundary sizes/alignment/resource limits.
7. Precision/exactness checks.
8. Memory pressure and allocation failure.
9. Cancellation, timeout and device loss.
10. Sustained/thermal run.
11. Latency/throughput/memory/bytes-moved measurement.
12. Power/energy only when instrumented and attributable.
13. Replay on exact release artifact.
14. Evidence hash and backend certificate.

## Certificate

Record backend class, physical device, supported operations, tested dtypes/limits, conformance, performance envelope, known failures, runtime/kernel/package versions and evidence hashes.

## Rule

Certification is workload-specific where necessary. Passing one kernel cannot be generalized into unsupported Chronus-wide GPU performance.