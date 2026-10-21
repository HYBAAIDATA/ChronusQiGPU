# Enterprise intelligence system contract

Scope: the mathematical substrate, TOE intelligence and `toe.unified` enterprise
facade. This contract describes responsibility and evidence boundaries; it does
not certify an enterprise deployment or replace owner-declared product direction.

## Architecture and responsibility

| Layer | Implementation authority | Responsibility and dependencies | Executable evidence / limits |
|---|---|---|---|
| Mathematical substrate | `kellogg/`, canonical exact-arithmetic modules | State representation, tensor operators and numerical/exact execution. TOE consumes these implementations; the platform must not introduce a second tensor engine. | Existing substrate suites. Exact-field proofs do not certify Float64 calls, performance advantage or enterprise readiness. |
| TOE intelligence | `toe/bridge.py`, `toe/machine.py`, `toe/runtime.py` | Domain-neutral reasoning and state analysis. Explicit domain adapters supply semantic structure. | Existing TOE suites; the new facade path calls `TOEBridge.state_tomography`. Tomography is descriptive representation, not causal identification. |
| Enterprise platform | `toe/unified/platform.py` | Connect, ingest, compile operators, query, train and coordinate operations. | `tests/test_toe_unified*.py`; `analyze` joins stored records to the existing bridge and TOE receipt format. This facade is an in-process library, not a network service. |
| Governance and security | `toe/unified/security.py`, entity policies; embedding host's identity/policy authority | Role checks before facade work. Host authenticates identities, provisions roles and selects request/service contexts. No transfer of domain authority. | Denial and thread-isolation tests in `test_toe_unified_authority.py`. Public low-level objects are trusted internals, not an adversarial process boundary. |
| Deployment and operations | `toe/unified/operations.py`, `monitor.py`, deployment/control-service owners | Probe connectors, quarantine dirty batches, and invoke authorized drift retraining. | Explicit service identity on enforced background ticks. Probe ratio is not elapsed-time uptime; no probes means unavailable evidence. Separate deployment qualification is required. |

## Named execution path

`connect -> integrate` (or `ingest_rows`) -> `compile_operator` ->
`UnifiedDataLayer.ingest` -> entity policy / `heal` quarantine -> `analyze` ->
`TOEBridge.state_tomography` -> existing `ReceiptLedger.issue` -> authorized output.

`analyze` snapshots non-quarantined entity records, compiles the analyzed payload,
and records both that digest and per-record ingestion lineage. It uses the
existing Kellogg bridge; no alternate reasoning implementation is added. Empty
or fully quarantined inputs and unavailable tomography do not issue success
receipts. The receipt records the acting identity, output digest, execution path
and arithmetic scope. Receipts are hash-chained **in memory**, not signed or
independently durable. Snapshot eligibility is checked when the snapshot is taken;
this is not a serializable transaction with subsequent policy changes.

## Governance contract

- `security_enforced=True` is required for a role-enforced facade. The existing
  default `False` remains for compatible local/fixture use, not a safe network default.
- The first `grant` is trusted bootstrap. `authenticate` and `as_actor` select an
  identity already verified by the host; neither validates credentials. Never
  expose them directly to untrusted clients or accept arbitrary client actor names.
- Role grants after bootstrap require `grant`; entity policy and ledger/patent
  mutation require `govern` (admin). Connector retirement/reload require `reload`
  (admin). Operators may ingest, heal and operate; analysts may train/predict;
  readers may query/export/inspect health. See the executable `ROLES` table.
- Actor context is thread/async-context-local and scoped overrides restore on
  exceptions. The host must still establish/reset identity for every request.
- Enforced monitor threads do not inherit an interactive administrator. Configure
  `monitor_actor` in the trusted composition root and grant its role explicitly.
  Every tick checks the current grant; denied ticks are errors, not successful heals.
- No result here approves a live external action, model promotion, deployment,
  financial disbursement, or a change to mathematical/consensus authority.

## Evidence matrix and claim separation

Keep the existing claim register in `toe/unified/claims.py` and its rendered
coverage/disposition reports. Do not infer implementation maturity from the
claim's evidence label. A named test is a test specification, not proof of a fresh run.

| Concern | Code / declared behaviour | Executed evidence required | What it does not establish |
|---|---|---|---|
| Facade authorization | Guards on data, model, governance and operations methods | Denial tests and permitted-role flows | External credential verification, tenant/row isolation by the bare facade or a security audit |
| Tenant routing | `TenantGateway` owns separate enforced runtime instances and rechecks membership/roles on every call | Cross-tenant data/model/policy/receipt/connector separation and revoke/downgrade tests in `test_toe_unified_tenancy.py` | External identity, adversarial Python/process isolation, distributed custody or independent tenant security qualification |
| Context isolation | Context-local identity and scoped service selection | Cross-thread denial; service role downgrade | Host login correctness or universal concurrency safety |
| Quality policy | Finite null-rate limit in [0, 1] | Invalid-policy rejection; real quarantine path | Retention deletion or regulatory compliance |
| Connectors | Bind/extract, retirement removes active binding | Fixture lifecycle and failure tests | Vendor certification, live connectivity or displaced customer systems |
| Ingest -> TOE -> output | Existing operator compiler, bridge and receipt ledger | Real tomography, norm assertion, input/output binding, quarantine exclusion | Identified causality, business benefit, durable custody or physical QPU execution |
| Availability | Successful / total probe ratio; no probes is unknown | Empty/failing/successful probe tests | Time-window SLA or independent uptime observation |
| Import publication | All groups and quarantine flags stage before one locked publish | Atomic rollback, concurrent-reader and payload-alias tests in `test_toe_unified_atomic.py` | Durable transactions or isolation across later policy changes |
| Automatic retraining | Disjoint held-out evaluation, non-regression, accuracy floor and live-version compare-and-swap | Real exact-linear tests in `test_toe_unified_promotion.py` | Generalization guarantees, independent corpus quality or deployment approval |
| Economics | Scenario arithmetic | Formula and input checks, labeled `modeled` | Realized savings or return on a deployed investment |
| Phase counters | Inventory, supplied feedback, counters and fixture benchmarks | Tests of each threshold; explicit `evidence_kind` where specialized | A deployment-readiness score or production release approval |

A claim requires a named execution path and evidence scoped to that claim.
Declared architecture, implemented code, fixture-tested behaviour, live integration
and enterprise release readiness are separate assertions. Do not promote one
into another. In particular, the default zero downtime counter is a counter, not
an independently observed zero-downtime interval.

## Verification and release boundary

Run `python scripts/verify_unified_enterprise.py`. It executes all unified suites
and writes `evidence.json`, JUnit XML, a log and a SHA-256 source manifest under
`artifacts/unified-enterprise/`. The CI workflow retains these on success **and
failure**, separately for Python 3.12 and 3.13. Failures, no tests and skipped tests
are not a complete passing verdict. A report records commit, worktree state,
interpreter, timestamps, command and artifact hashes; it never grants production
certification. Existing `make verify-unified` remains the seven-layer entry point.

Source/facade tests and installed-package tests are separate evidence scopes.
`python packaging/toe/build_and_verify.py` also copies the authority, atomic-import,
promotion and tenancy suites into each clean installed-artifact check, for both the wheel
and a wheel rebuilt from the sdist. It verifies that TOE, Kellogg and the facade
resolve inside that interpreter's installed-package directories, then runs those
four suites with `python -I`, importlib-mode pytest, no repository conftest and
no inherited Python/pytest path or plugin overrides. This is an explicit runtime
regression subset, not a replacement for the source or full repository suites.

Logs, JUnit, test hashes and a fail-closed verdict are retained under
`packaging/toe/dist/installed-unified/`, including on import-probe/test failure.
Missing suites, zero executed tests, skips and failures cannot produce a passing
verdict; reruns discard older evidence. The unified CI workflow includes separate
Python 3.12/3.13 artifact jobs and retains the build outputs even on failure.
Adding a gate or passing its orchestration-fixture tests does **not** establish
that the real installed artifacts passed: inspect a fresh, commit-bound run.
Nothing in this build path publishes a package or certifies deployment readiness.

Before any release claim, the accountable release reviewer must check that the
executed evidence matches the candidate commit/artifacts, is fresh for the
change, covers the claimed deployment and has no unresolved blocking failures.
CI reporting does not configure branch protection or replace independent review.

### Explicitly open qualification work

- Live vendor integration, credential lifecycle, external identity and independently qualified tenant/record-level authority.
- Durable custody, restart/recovery, signed or independently retained audit receipts.
- Isolation across subsequent policy changes and crash recovery of import transactions.
- Independent evaluation-corpus quality, holdout reuse controls and domain-specific promotion qualification.
- Load/fault/soak tests and externally observed availability windows in target deployments.
- Realized economics, retention enforcement, external governance and security review.

These are required qualification boundaries, not silently completed capabilities.

## Atomic import and automatic-promotion implementation

`import_records` validates and detaches every envelope, verifies any supplied
content digest, strictly checks quarantine flags and compiles all groups before
writing. `UnifiedDataLayer.ingest_atomic` stages records, blobs, indexes, batch
metadata, audit and counters, then publishes under the data-layer lock only when
all batches and quarantine updates succeed. A failed transaction emits no facade
success receipts or consumed live batch IDs. Duplicate imports cannot silently
release quarantined data. Ingest inputs and export snapshots detach nested
payloads so caller mutation cannot invalidate stored digests.

This is copy-on-write **in-process** atomicity for lock-participating data-layer
readers. Staging costs memory proportional to the current store plus imported
data and blocks those readers during staging. It does not implement durable
custody, serializable policy changes or an external database transaction.

`watch(name, rows, eval_rows=held_out, min_accuracy=0.8)` registers detached drift
and evaluation evidence. A watch without held-out rows stays
`blocked_missing_evaluation` and cannot automatically replace a model. Held-out
model inputs must differ from both the candidate training inputs and the current
model's recorded training inputs, ignoring unrelated IDs and labels. All features
must be present and finite, and the binary evaluation must contain both classes.

Automatic promotion evaluates the actual candidate and incumbent on that
holdout. It requires non-regression and the configured accuracy floor (default
0.8, an explicit local policy, not an industry readiness threshold). The live
version must still be the evaluated version at swap time. Rejected or stale
candidates do not append model history or increment `drift_retrains`; the health
report exposes the outcome, evaluated version, scores and evaluation digest.

The direct/manual `train` and legacy `retrain` APIs remain trusted operations;
`retrain(..., require_evaluation=True)` opts into the same guarded path. The host
must restrict direct training authority appropriately. No holdout's existence
proves independence of its collection process or fitness for a deployed domain.


## Tenant composition boundary

`TenantGateway` is a trusted embedding-host composition root, not an authentication
endpoint or a network service. The host authenticates the principal, provisions
its exact tenant membership and role, and obtains a `TenantSession` using that
verified identity. Never accept `verified_actor` from an unverified client field
or expose gateway provisioning/grant/revoke/connector configuration as tenant APIs.

Each provisioned tenant has an independent role-enforced platform instance,
including records, indexes, policies, models/history, connectors, operational and
drift state, governance state and receipt chain. Tenant calls use an explicit
allowlist and the canonical facade's current role checks. Membership is rechecked
on every invocation; revocation and role changes serialize with calls for that
tenant. In-flight calls may complete before revoke returns. Once it returns,
previously issued sessions cannot start another authorized call. Revocation cannot
recall data already returned or cancel an external action already started.

Connector credentials and live driver/runtime objects are host-only. Tenant
results and model records are detached copies, with explicit tenant/operation
scope. Analysis receipts also hash-bind the tenant ID in their configuration.
A bare platform's optional tenant label alone does not enforce membership.

Calls serialize per tenant, trading same-tenant throughput for a clear grant/
revocation boundary; different tenant locks are independent. The gateway is
in-process: it does not isolate arbitrary Python code, process memory, filesystem,
external credentials, vendor namespaces or shared external services. Hosts must
not share credential scopes/transports across tenants unless that sharing is
intentional and independently controlled. It does not provide durable tenant
custody or restart recovery, nor replace an independent multi-tenant security review.

### Remaining qualification order

1. Obtain a fresh full-package wheel and rebuilt-sdist verdict at the candidate
   commit, including root-package initialization and the installed runtime suites.
2. Read and retain source/package CI evidence; inaccessible checks remain a blocker.
3. Qualify the host authentication/tenant adapter and external resource isolation
   against cross-tenant adversarial cases in the actual deployment.
4. Implement and test durable checkpoint/restore and rollback using the accountable
   custody backend: interruption at each write boundary, corruption rejection,
   fresh-process restore, tenant binding and model/data/audit consistency.
5. Run live-vendor, load/fault/soak and SLA qualification in the target environment.

Implemented tenant routing and passing fixture tests do not close these release gates.
