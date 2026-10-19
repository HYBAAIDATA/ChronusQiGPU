# Contract

`toe.unified` is an in-process library. `UnifiedAnalyticsPlatform` holds connectors, records, models, questions, operations, a cost formula, and a scholarship ledger.

What a call does:

- A catalog row binds only when credentials satisfy its protocol. Otherwise `ConnectorUnavailable` is raised and no row is written.
- Ingest stores one digest per source, entity, and payload. A repeated payload is a duplicate. A non-object row raises `TypeError` before any row in that call is stored.
- Every ingest stores the digest returned by `toe.operator_compilers.compile_operator`.
- Payload bytes are zlib-compressed under that digest. `restore_payload` returns the original object.
- Reads by entity use an index. `benchmark_processing` records index visits against a full scan. The processing gate opens when the reduction is at least 0.90.
- Models are `kellogg` `exact_linear`. `retrain` keeps the live model when held-out accuracy falls. Transfer zero-fills missing features and reports the overlap. `predict` during `retrain` still returns a class.
- `watch` plus `HealthMonitor` retrains when accuracy on the watched rows is below 0.5. `start` ticks without a further `heal()` call.
- `ConsciousnessState.observe` weights widgets. `correct` sets the threshold to the midpoint of the corrected class scores.
- Questions accept the grammar in `toe/unified/bi.py`. Anything else raises `QueryError`. `optimize` orders filters by measured selectivity.
- Dashboards reorder the widgets the caller supplied.
- `heal()` re-probes bound connectors and quarantines a batch whose null rate is above the entity policy. `release()` clears that flag.
- Worker count is `clamp(1, ceil(queue_depth / batch_size), max_workers)`, or 1 when the queue is empty.
- `assess`, `document_fortune500_scenario`, and `financial_services_case` compute from declared inputs. The 23-system case saves 45,000,000.
- Reference workloads live in `productivity.REFERENCE`. Live timings are whatever `record` is given.
- `recognize_value` appends one ledger entry. Outcomes divide the allocated amount by the unit cost of 50,000.
- With enforcement on, one role table allows or denies `connect`, `ingest`, `train`, `ask`, `export`, `heal`, and `reload`.
- Phase gates include connector count 50, enterprise systems 500, satisfaction 0.95, processing reduction 0.90, three-year ROI 4.0, and 10 filed patents.
- Sensor batches return an operator digest and a maintenance slope. Fraud lift on the separable fixture is 3.0 against flag-all precision.
- Risk labels start at the register defaults and follow the observed failure rate after `observe`.

The claim register is `toe/unified/claims.py`. The evidence list is `reports/toe_unified_disposition.md`.
Evidence status is the first axis.
Implementation status is the second: `IMPLEMENTED_REAL`, `IMPLEMENTED_FIXTURE`,
`IMPLEMENTED_UNTESTED`, `SCAFFOLD`, or `ABSENT`.
The rendered coverage map is `reports/toe_unified_coverage_map.md`.
`make verify-unified` runs the seven layers in order.

