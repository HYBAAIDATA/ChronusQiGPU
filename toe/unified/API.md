# API

```python
from toe.unified import UnifiedAnalyticsPlatform

platform = UnifiedAnalyticsPlatform(
    allocation_rate=0.0, max_workers=8, security_enforced=False, monitor_actor=None
)
platform.start() -> dict
platform.catalog(**filters) -> tuple[ConnectorSpec, ...]
platform.connect(connector_id, credentials) -> BoundConnector
platform.reload(connector_id, credentials) -> BoundConnector
platform.integrate(connector_id, entity, mode="batch") -> dict
platform.ingest_rows(source, entity, rows) -> dict
platform.export_records() -> list[dict]
platform.import_records(rows) -> list[dict]
platform.benchmark_processing(entities=100, per_entity=20) -> dict
platform.optimize(rows, filters) -> dict
platform.govern(entity, classification, retention_days, owner, max_null_rate=0.2) -> Policy
platform.train(name, rows, features, target) -> TrainResult
platform.retrain(name, rows, eval_rows=None, require_evaluation=False, min_accuracy=0.8) -> TrainResult
platform.predict(name, rows) -> list[int]
platform.transfer(name, rows, features) -> dict
platform.watch(name, rows, eval_rows=None, min_accuracy=0.8) -> None
platform.monitor.start() / stop() / tick_once()
platform.ask(question) -> dict
platform.analyze(entity) -> dict
platform.analysis_receipts() -> list[dict]
platform.feedback(user, widget, depth=1, rating=None) -> CognitiveProfile
platform.dashboard_for(user, name, widgets) -> dict
platform.consciousness.observe / correct / rank / accuracy
platform.health() -> dict
platform.heal() -> list[HealAction]
platform.release(batch_id) -> int
platform.scale() -> ScaleDecision
platform.file_patent(title) -> int
platform.case_financial_services() -> ROIResult
platform.productivity.reference(name) / record(name, seconds)
platform.risks.probability(name) / observe(name, failed)
platform.security.enforced / grant / authenticate
platform.displacement() -> dict
platform.retire(connector_id) -> None
platform.economics(baseline, platform_cost) -> ROIResult
platform.scenario() -> dict
platform.recognize_value(amount, source) -> Recognition
platform.ledger.outcomes() -> dict
platform.industry(name) -> dict
platform.run_application(application, **payload)
platform.phases() -> list[Gate]
```

Accepted questions:

- `show <metric> by <dimension> from <entity> [where <field> <op> <value>]`
- `count <entity> [where ...]`
- `what drives <model>`
- `quality [of <entity>]`
- `health`
- `roi`

Protocols: `jdbc` (SQLite DSN), `rest`, `odata`, `kafka`, `sdk`, `opcua`.

Roles, once `security.enforced` is set: `reader`, `analyst`, `operator`, `admin`.

`import_records` stages all entity/source groups and quarantine flags atomically
in the in-process store. Supplied content digests must match; quarantine flags
must be booleans. Bad later groups cannot leave earlier groups published.

A `watch` without `eval_rows` reports `blocked_missing_evaluation`. Automatic
promotion uses disjoint held-out model inputs, compares incumbent/candidate
accuracy, requires `min_accuracy`, and refuses a stale-version swap. Its outcome
and evaluation digest are exposed under `health()["drift"]`. The holdout must
contain both binary labels and complete finite model features. Direct manual
training/retraining remains trusted; see `SYSTEM_CONTRACT.md` for boundaries.

`analyze` is descriptive state tomography via the existing TOE bridge, not a
causal finding or action approval. Acting identity selection is performed by the
trusted embedding host; it is not a login/credential-verification API.


## Host-composed tenant entry point

```python
from toe.unified import TenantGateway

gateway = TenantGateway()  # trusted host composition root; not a tenant RPC object
gateway.provision("customer-a")
gateway.grant("customer-a", "principal-42", "operator")

# verified_subject must come from the host's successful authentication, never a
# client-supplied actor name. The client may select only a tenant they belong to.
verified_subject = "principal-42"  # stand-in for the host IdP's verified subject
request = gateway.session(tenant_id="customer-a", verified_actor=verified_subject)
result = request.call("ingest_rows", "approved-source", "events", [{"x": 1}])
assert result.tenant_id == "customer-a"

gateway.revoke("customer-a", verified_subject)
# request.call("export_records") now raises AccessDenied.
```

The host controls `provision`, `grant`, `revoke` and `configure_connector`.
`TenantSession.call` exposes only `TENANT_OPERATIONS`; connector credentials,
`connections`, direct security objects and live registry/runtime handles are not
returned. All results have `tenant_id`, `operation` and a detached `value`.
Existing facade role policy still applies within that tenant. Sessions are host
identity selections, not bearer/login credentials. Calls serialize per tenant;
in-flight work may complete before revocation returns. A bare
`UnifiedAnalyticsPlatform(tenant_id=...)` labels analysis receipts but does not
supply membership enforcement. External authentication, durable isolation and
production qualification remain the embedding deployment's responsibility.
