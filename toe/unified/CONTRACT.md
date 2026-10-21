# Contract

`toe.unified` is an in-process library. `UnifiedAnalyticsPlatform` holds connectors, records, models, questions, operations, a cost formula, and a scholarship ledger.

What a call does:

- A catalog row binds only when credentials satisfy its protocol. Otherwise `ConnectorUnavailable` is raised and no row is written.
- Ingest stores one digest per source, entity, and payload. A repeated payload is a duplicate. A non-object row raises `TypeError` before any row in that call is stored.
- Every ingest stores the digest returned by `toe.operator_compilers.compile_operator`.
- Payload bytes are zlib-compressed under that digest. `restore_payload` returns the original object.
- Reads by entity use an index. `benchmark_processing` records index visits against a full scan. The processing gate opens when the reduction is at least 0.90.
- Models are `kellogg` `exact_linear`. `retrain` keeps the live model when held-out accuracy falls. Transfer zero-fills missing features and reports the overlap. `predict` during `retrain` still returns a class.
- `watch` plus `HealthMonitor` retrains when accuracy on the watched rows is below 0.5. `monitor.start()` ticks without a further `heal()` call; platform `start()` alone does not start the monitor.
- `ConsciousnessState.observe` weights widgets. `correct` sets the threshold to the midpoint of the corrected class scores.
- Questions accept the grammar in `toe/unified/bi.py`. Anything else raises `QueryError`. `optimize` orders filters by measured selectivity.
- Dashboards reorder the widgets the caller supplied.
- `heal()` re-probes bound connectors and quarantines a batch whose null rate is above the entity policy. `release()` clears that flag.
- Worker count is `clamp(1, ceil(queue_depth / batch_size), max_workers)`, or 1 when the queue is empty.
- `assess`, `document_fortune500_scenario`, and `financial_services_case` compute from declared inputs. The 23-system case saves 45,000,000.
- Reference workloads live in `productivity.REFERENCE`. Live timings are whatever `record` is given.
- `recognize_value` appends one ledger entry. Outcomes divide the allocated amount by the unit cost of 50,000.
- With enforcement on, the role table guards the facade data, prediction, dashboard, governance and operational methods. `security_enforced=True` selects that mode at construction. Actor selection is trusted host integration, not credential authentication. Enforced monitor threads require an explicitly provisioned `monitor_actor`; they use the same authorized heal/retrain methods.
- Phase gates include connector count 50, enterprise systems 500, satisfaction 0.95, processing reduction 0.90, three-year ROI 4.0, and 10 filed patents.
- Sensor batches return an operator digest and a maintenance slope. Fraud lift on the separable fixture is 3.0 against flag-all precision.
- Risk labels start at the register defaults and follow the observed failure rate after `observe`.

The claim register is `toe/unified/claims.py`. The evidence list is `reports/toe_unified_disposition.md`.
Evidence status is the first axis.
Implementation status is the second: `IMPLEMENTED_REAL`, `IMPLEMENTED_FIXTURE`,
`IMPLEMENTED_UNTESTED`, `SCAFFOLD`, or `ABSENT`.
The rendered coverage map is `reports/toe_unified_coverage_map.md`.
`make verify-unified` runs the seven layers in order.


## Enterprise execution and evidence boundary

See `SYSTEM_CONTRACT.md` at repository root for the layer ownership map,
governance stack, evidence matrix and open deployment qualification work.
`analyze(entity)` runs the existing TOE bridge's state tomography on a snapshot
of non-quarantined records and issues an existing-format TOE receipt binding the
analysis to compiled input and ingestion lineage. Empty input or unavailable
analysis raises `AnalysisUnavailable`, without a success receipt. Outputs are
descriptive, not causal findings or action approvals. `analysis_receipts()`
requires export permission. Receipts remain in-process.

Availability is `None` until a probe exists; its phase gate remains closed and
`require_gate("availability")` raises `GateUnavailable`. Afterwards it is a probe
success ratio, not a time-window SLA. ROI gates carry `evidence_kind="modeled"`;
connector count gates carry `bound_inventory`; processing reduction carries
`fixture_row_visits`. No phase gate certifies an enterprise deployment.
Retirement requires admin reload authority and removes the active binding;
reconnection clears the retired marker. Null-rate policy limits must be finite
numbers between zero and one.

`python scripts/verify_unified_enterprise.py` retains executed test evidence,
including failures. The CI workflow runs the unified suites on Python 3.12/3.13;
a fresh passing result must be inspected, not inferred from this contract.
