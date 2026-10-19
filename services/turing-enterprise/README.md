# TURING enterprise service control — pilot foundation

**Status: implemented control-plane library; NOT an enterprise production release.**
This is the distinct **Enterprise Service Delivery and Commercialisation**
workstream. It does not alter TURING mathematics or close package-release PR #96.
Shared lifecycle/commercial policy sits outside the VQC package, in accordance
with `docs/CIAAS_THREE_PLANE_SESSION_AUDIT.md`.

## What this implements

- Operator-attested approved contract, billing-account reference, validity window,
  contracted logical slots and per-contract verified-completion allowance.
- Transactional logical reservation, resize, activation, suspension and retirement.
- Separate operator and customer signed-capability boundaries using the existing
  AL HARAS `SubscriptionAuthority.verify` interface, checked on every request.
- Tenant-scoped job identity, atomic allowance/concurrency reservation, request
  allowlist, cancellation before dispatch, result/history and capacity reads.
- Durable job state, command retry receipts and audit in SQLite WAL/FULL mode.
- Lazy adapter to **the existing** `VQCRequest` / `run_pipeline` path. No new VQC,
  hardware scheduler, tensor implementation, identity issuer or payment ledger.
- Usage and billing outbox written in the same transaction as completion.
  Only a PASS report with execution/verification PASS, certificate, witness and
  program identity creates a candidate usage event. Runtime adapter is trusted
  and owns real certificate verification; envelope checks are not a new proof.
- At-least-once delivery with stable event identity and identity-bound receiver
  acknowledgement; reconciliation of unresolved execution, completion/usage
  consistency and local audit-chain integrity.

## Explicit semantics: do not promise VMs or QPUs

An **instance/slot** here means one reserved **logical concurrent job admission**
within a customer account. It is not a VM, isolated runtime, physical QPU, physical
GPU, memory allocation, performance guarantee or globally available infrastructure.
`provision` allocates this logical entitlement only; it does not attest runtime
readiness. Contracted, allocated, available (allocated minus unresolved/admitted
work), in-flight and consumed completions are distinct. Available is a reservation
count, not an assertion that a suspended/expired service can execute.

`verified_execution.v1` is a **proposed metering unit**, quantity one per completed
verified job, not a validated price, cost measure, FLOP, GPU second or invoice.
The allowance spans the immutable contract window, not a monthly reset. There is
no renewal/replacement contract operation in this version. Prices, recurring
commitments, reservation fees, overage, refunds and tax remain Hermitten-owned.
Different computational job sizes are not economically equivalent; this meter is
not sufficient by itself for a production consumption tariff.

## Use and test from the repository root

```bash
python -m pip install -e 'services/turing-enterprise[test]'
python -m pytest services/turing-enterprise/tests -q
python -m build services/turing-enterprise
```

Configure separate, trusted AL HARAS authority instances for customer and internal
operator verification. Operator tokens are issued for tenant `__service_ops__`
with narrowly scoped capabilities; do not let customer issuers use operator keys.
Tokens and actor identity must arrive through an authenticated transport. The
library never issues tokens. Single-use (`jti`) tokens are refused rather than
bypassing AL HARAS consume/replay semantics; this pilot uses scoped renewable
service tokens. Durable Guardian replay integration remains a production gate. No secrets or credentials belong in requests or SQL.
No HTTP listener, unauthenticated CLI or development bypass is included.

| Surface | Signed capability | Additional enforcement |
|---|---|---|
| Approve / provision / lifecycle / resolve / reconcile | `turing.ops.manage` | Separate operator authority and service-ops tenant |
| Worker execution | `turing.ops.execute` | Same operator boundary, active tenant contract, undispatched job |
| Billing outbox delivery | `turing.ops.billing` | Same operator boundary; trusted configured receiver |
| Submission / cancellation | `turing.jobs.submit` | Tenant binding, quota, submitting actor for cancellation |
| Overview / job / usage / audit reads | `turing.customer.read` | Tenant binding; org-wide read capability, no project ACL implied |

`ControlPlane` takes a DB path, both authority instances and optionally a trusted
server clock. One instance/connection per worker; close each explicitly. Never
expose authority, clock, runtime, sink or database-path injection as user inputs.
The runtime adapter requires the real installed TURING/Kellogg dependencies; this
service wheel deliberately does not bundle or publish their IP.

## Recovery / operations

1. Run `reconcile` using a narrowly scoped operator identity. Alert on unresolved
   `running`/`unknown` jobs, audit inconsistency and a growing pending outbox.
2. An execution exception may mean external work happened. It is quarantined as
   `unknown`; a process crash after dispatch remains `running`. Both retain slot
   and allowance reservations. Neither is auto-reexecuted or auto-billed.
3. Fence/stop the relevant worker, recover and retain evidence, and investigate
   before `resolve_unknown`. This records a reason, marks failed and releases the
   reservation **without billing**. It is not a successful-result recovery path.
   Late success after resolution is rejected rather than silently billed.
4. Outbox receiver must atomically deduplicate `event_id`. If receiver committed
   but its acknowledgement was lost, delivery retries the identical event key.
   Invalid/wrong-event receipts remain pending. A receipt is not payment.
5. Suspension prevents new admission/dispatch. It does not claim to kill running
   computation. Drain/cancel admitted work and fence running work before retiring;
   retirement cannot occur while any unresolved reservation remains.
6. SQLite transactions protect local atomicity, not remote exactly-once execution.
   Back up using SQLite's online backup API, retain WAL consistently, restore-test
   the DB, and reconcile remote receipt IDs before resuming. Encrypt and restrict
   DB/backups at deployment level; this library does not configure encryption.
7. Local triggers/hash chains resist accidental changes, **not a privileged DB
   attacker**, global-tail deletion, or host compromise. Production audit needs
   independent anchoring, protected retention and the existing security authority.

## Hermitten boundary — deliberately not faked

The inspected repository search found Hermitten references in research notes; it
did not establish a runnable Hermitten billing client/schema. The supported port
is `sink.accept_usage(event, idempotency_key=event_id)` returning
`{"event_id": "...", "receipt_id": "..."}`. Missing sink fails closed. The tests
use a labelled billing receiver double; they are not Hermitten integration tests.
See `usage-event.schema.json`. Agree API version, authentication, rate mapping,
receiver deduplication, correction/credit events and reconciliation against real
Hermitten before accepting revenue. Execution state remains here; invoice/payment
state remains in Hermitten. No invoice number or currency is fabricated.

## Remaining delivery scope / release gates

See `../../docs/TURING_ENTERPRISE_SERVICE_DELIVERY.md`. In particular: SSO and
membership/revocation, project policy, live runtime resource isolation and tenant
custody, network/API and three user interfaces, physical capacity orchestration,
Hermitten integration, billing corrections, contractual offer and independent
security/load/recovery acceptance remain open. Do not publish this private pilot
package to PyPI or claim enterprise readiness from its unit test result.
