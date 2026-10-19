# Proposed Hermitten adapter contract — receiver acceptance required

**No live receiver conformance was established.** These are implemented port
requirements, not a claim that the existing Hermitten service exposes these
endpoints. Confirm or adapt paths/schema with its owner before activation. Do not
implement a second rate engine, tax ledger, payment ledger or invoice database.

Transport: trusted configured HTTPS origin; certificate validation, no redirects,
10-second timeout, 1 MiB response maximum, bearer credential from a private file.
API customers cannot choose the URL. Imports use `Idempotency-Key` = stable event
ID. Receiver must durably deduplicate atomically with its import transaction,
return the same logical receipt for a retry, and refuse identity/content mismatch.

| Method/path | Required semantics |
|---|---|
| `GET /v1/capabilities` | `atomic_event_deduplication: true`, `schemas` includes accepted version strings; production also `spend_authorisation: true` |
| `POST /v1/usage/import` (configurable path) | Accept the supported event; acknowledge `{event_id, receipt_id}` only after durable import |
| `GET /v1/accounts/{account}/statement` | Account-bound authoritative entitlement/commitment/usage/currency/invoice references; never locally inferred prices |
| `PUT /v1/accounts/{account}/spend-limit` | Idempotent command; decimal-string `amount`, uppercase three-letter `currency`; account-bound acknowledgement |
| `POST /v1/accounts/{account}/work-authorisations` | Atomically reserve commercial spending authority against account limits for stable `job_key` and immutable `request_digest` |

A work authorisation response binds **all** of `account_id`, `job_key`,
`request_digest`, `authorization_id`, integer future `expires_at`, `approved:true`.
The local intent is persisted before the network call. A lost response is retried
with the same remote identity; no guessed local balance is used. Admission and
its local authorisation state transition are atomic. A known failure before
execution emits a release request. Running/unknown outcomes remain held for
reconciliation, never automatically credited. Completed usage carries the
`spend_authorization` reference. Hermitten, not TURING, owns settlement and rates.
An operator must inspect unresolved `intent` and `release_pending` records; resume
the exact request or reconcile/cancel it with billing, preserving evidence.

## Event families

- `turing.usage.v1`: see `../usage-event.schema.json`; one candidate verified
  execution; contract/account, program/report digests and optional spend reference.
- `turing.reservation.v1`: approved contract lifecycle and logical allocation
  snapshot, `action`, `state`, `slots`, timestamp, tenant/account/contract and audit
  head. These are observations, **not instructions to multiply invoices** for
  every snapshot. Receiver rates commitment periods without duplicate charges.
- `turing.adjustment.v1`: immutable correction referencing the original
  event and approved reason; original usage is never overwritten.
- `turing.spend_release.v1`: stable event/job/tenant/authorization identity and
  reason. Receiver must release at most once and prevent release after settlement.

Inspect the serializer for exact correction fields; schema changes require
versioning and a receiver compatibility check. The receiver capability handshake
must advertise every enabled event family, not merely verified executions.
An acknowledgement is **not** an invoice, payment or recognition of revenue.

## Required real-system acceptance

1. Account hierarchy and contract-specific rates/allowances; recurring enterprise
   commitments, reserved-capacity periods and premium/strategic service items.
2. Same import twice; lost ACK after commit; retry after restart; wrong event ACK;
   same key/different content; receiver outage. Exactly one economic posting.
3. Concurrent spending approvals at the ceiling; denied/expired approval; lost
   response; admission failure; cancelled work; unknown execution; late completion.
4. Completed event to statement/invoice line reconciliation; explicit currency and
   tax; credit/correction authorisation; no silent edits or backdated overwrites.
5. Renewal/retirement stops future commitments at the agreed boundary; usage still
   pending remains reconcilable. Never delete the financial record with live data.

Retain actual receiver logs, statement/invoice references and owner acceptance as
`billing_reconciliation` evidence. HTTP doubles and capability assertions alone
cannot satisfy this gate.
