# Production architecture and authority contract

> Follow-up: tenant work from main PR #131 is reconciled in this branch. See
> [package/runtime qualification plan](PACKAGE_QUALIFICATION_PLAN.md) and
> `evidence/package-qualification/` for fresh results and unresolved gates.
> The 94-test figures below are the historical first-patch run at `22aa518`,
> not certification of later changes. Overall readiness remains blocked.

**Disposition: NOT YET PRODUCTION-READY.** This contract defines the required
enterprise boundary; it does not certify the complete repository or deployed services.
It covers the inspected `toe.unified` consumer and its actual exact-tensor dependency.
Other product entry points require independent qualification against this contract.

## Revision and execution scope

Review began at `a9914fc9fbd06655cbbb5fb96d9e6b0101eaa278`. During execution,
PR #130 merged as `da432bbe4e59855f7c8a6ec3028217e57ca59f25`.
The patch preserves the merged facade's analysis/receipt APIs, service-actor support,
atomic-import API, promotion evidence fields and installed-test harness.
It does not replace that work with the older implementation.

## Canonical responsibility boundaries

| Layer | Inspected execution path / declared integration | Required production authority | Present disposition |
| --- | --- | --- | --- |
| Mathematical substrate | `kellogg.exact_tensor` -> `kellogg.tensor_ml.fit/predict` | Typed arithmetic and bounded computation; no identity or release authority | Real exact-linear implementation executes in focused tests; broad mathematical/performance claims not qualified |
| TOE reasoning | `toe` package; merged `UnifiedAnalyticsPlatform.analyze` -> `TOEBridge.state_tomography` | Advisory/descriptive outputs, not permission or operational acceptance | Merged analysis path preserved; bridge and whole-package initializer not executed in this partial snapshot |
| Platform orchestration | `toe.unified.platform.UnifiedAnalyticsPlatform` -> data, models, connectors, operations | Validate inputs, authorize actions, bind computation and provenance | In-process regressions measured; not an internet-facing production security boundary |
| Governance/security | `TenantGateway` tenant-local facade instances, allowlist and live membership; `SecurityModel.authorize`; AL HARAS is a separate declared integration | Trusted principal, tenant, least privilege, fail closed, service identities, independent model promotion | Tenant-local state and completed revocation measured in process; trusted IdP/endpoint/AL HARAS end-to-end qualification unproven |
| Persistence/recovery | `UnifiedDataLayer` + new `checkpoint.save_checkpoint/load_checkpoint` | Atomic durable acknowledgements, authenticated backups, deterministic recovery and approved rollback | In-memory transactions and offline POSIX data checkpoints tested; no live WAL or complete platform recovery |
| Deployment/runtime | Existing TOE build/installed-artifact gate and enterprise clean-install workflow | Exact artifact/commit binding, supported interpreter/OS tests, secrets handling, rollout/rollback, measured dependency readiness | Gate extended, not executed here; deployment qualification remains blocked |

## Production-critical, advisory and experimental scope

Production-critical **requirements**, not currently approved deployment capabilities:
identity/tenant enforcement; data transaction and provenance integrity; model promotion;
durable recovery; runtime status; installed-package and deployment verification.
Every critical requirement must have a measured evidence row before release approval.

Advisory only: descriptive tomography, query planning diagnostics, cost/ROI scenarios,
reference productivity figures, catalog inventory, heuristic suggestions, patent counts
and scholarship bookkeeping. None proves a service SLA, legal filing, business outcome,
causal identification or production readiness.

Experimental/unqualified: physical quantum claims, universal algorithmic speedups,
hardware throughput/latency, automatic autonomous production changes, and any component
outside the tested closure. Names such as "production", "exact" or "enterprise" do
not upgrade their evidence class. This patch does not rewrite mathematical doctrine.

## Safety and data invariants

1. Host authentication precedes actor selection. `authenticate`/`as_actor` select a
   **trusted in-process** identity; they do not validate credentials or tenant claims.
   Public component attributes are not a sandbox against malicious in-process code.
2. Monitor and user actions traverse the same facade authorization methods. Contexts
   do not borrow an interactive administrator's identity; configured service actors
   still require capabilities. Existing service-actor functionality is preserved.
3. Initial `train` is a development bootstrap, not approved production promotion.
   An existing name must use validated `retrain`; it cannot be overwritten via `train`.
   All retraining requires held-out evidence, including legacy calls passing
   `require_evaluation=False`. The compatibility flag cannot bypass validation.
4. Validation checks include finite inputs, every feature, both binary classes,
   disjoint candidate/live historical training feature fingerprints, non-regression,
   a registry accuracy floor that a per-call threshold cannot weaken, and stale-live
   comparison before publication. Returns are detached from live registry records.
   These checks do not establish independent validation/promotion authority or
   representative production data.
5. Single ingest and grouped import publish payloads, blob/index/accounting state,
   batch ledger, quarantine and imported lineage together under a lock. Staging
   failure publishes nothing. This is in-memory atomicity, not crash durability.
6. Stored payloads are detached JSON objects. Non-string keys, non-finite numbers,
   tuples and arbitrary objects are rejected rather than silently stringified.
   Read/export paths detach nested structures and policies. Import verifies claimed
   content digests; imported lineage is retained as provenance, not trusted attestation.
7. Checkpoints include data, policies, audit, batch ledger, blobs and accounting.
   POSIX file publication uses private temporary files, file fsync, atomic replace
   and directory fsync. Load verifies schema, checksum and internal consistency;
   missing or inconsistent artifacts fail rather than inventing empty recovery.
   Recovery constructs a new data layer, never overwrites an active one.
   Checkpoints do not persist models, principals, connector secrets or the facade.
8. Checkpoint paths and files require a trusted host and a single writer. SHA-256
   detects corruption; it does not authenticate a backup against an attacker who
   can rewrite content and checksums. POSIX tests do not qualify Windows/network FS.
9. Full-state staging/deep copies increase memory and runtime cost. Large-store
   throughput, memory exhaustion, quotas, multi-process coordination and resource
   limits are open qualification requirements, not production performance claims.

## Status and readiness contract

- `healthy`: fresh local measured probe evidence, started runtime, authorization
  enabled, no observed failure. This is not fleet uptime or production certification.
- `degraded`: observed probe failures or monitor errors.
- `blocked`: a required control/qualification is absent, or authorization denies action.
- `rejected`: a candidate fails quality/floor/regression/staleness validation.
- `unavailable`: no fresh operational evidence, dependency/runtime unavailable, or
  a measured gate is queried before its evidence exists.

Availability is `None` until a measured sample exists. Connector configuration
preflights are not availability samples. Probe freshness defaults to 60 seconds;
this is an operational freshness policy, not an SLA measurement window.
A historical probe ratio may remain reported after expiry while operational status
becomes unavailable. Uptime denominators and time-weighted SLIs are not implemented.

`readiness()` returns `ready=False` and explicit qualification blockers.
`start(production=True)` fails closed. Default `start()` remains a development
lifecycle call. Removing this block requires measured closure of the backlog;
setting a flag or changing this document is not sufficient authorization.
