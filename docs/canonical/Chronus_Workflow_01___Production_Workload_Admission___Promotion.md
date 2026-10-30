# Chronus Workflow 01 — Production Workload Admission & Promotion

<aside>

Required before any new Chronus workload is called production-ready.

</aside>

## Entry criteria

Named workload owner; exact input/output contract; reference oracle; declared precision/exactness/quality boundary; supported backend set; reproducible manifest.

## Promotion ladder

1. REFERENCE_DEFINED
2. SOFTWARE_VERIFIED
3. BACKEND_CONFORMANT
4. HARDWARE_MEASURED
5. QUALITY_ACCEPTED
6. RESILIENCE_ACCEPTED
7. SECURITY_ACCEPTED
8. RELEASE_REPRODUCIBLE
9. OWNER_APPROVED
10. PRODUCTION_ADMITTED

## Mandatory checks

Reference differential; property tests; failure/corruption tests; latency p50/p95/p99; throughput; work quantity; memory; bytes moved; setup/preprocessing; quality/error; power/energy when instrumented; sustained behavior; recovery; backend identity; matched conventional baseline.

## Fail closed

Missing hardware = UNAVAILABLE. Missing benchmark = MISSING. Changed precision/work/quality = different experiment. Benchmark path that differs materially from production cannot promote production.

## Exit artifact

Workload dossier containing contract, provenance, tests, benchmark evidence, red-team verdict, supported profiles/backends, known limitations, rollback path and owner approval reference.