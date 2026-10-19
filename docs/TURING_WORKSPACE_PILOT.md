# TURING computational workspace — first reviewable increment

Status: draft technical-evaluation implementation; disabled by default. No
production-readiness, enterprise-acceptance, remote-CI or live-billing claim.

## Repository reconnaissance and decisions

Inspected main `af4e34a3c9463750dc32bcd1eae41f7310944833` and PR #96 head
`356ab419dae197f407989da82feaa2f149da08e7`. PR #96 is open and blocked, not merged.
This increment is stacked on that work, not a replacement for it. Its public
facade, contracts, native adapter and exceptions are dependencies; the engine,
package identity and mathematical model are unchanged.

The root package delegates development/build/type-checking to `frontend/`.
The existing application is Vite/React 19/TypeScript with Tailwind, not Next.js.
`main.py` serves static assets through the Python `control_api` process.
Replacing it or adding a Node server is unnecessary for this increment.
The existing guardian owns subscription verification and durable decision audit.
The native adapter explicitly describes jobs as `in_memory_process_local`.

Only inspected paths and searches support this inventory; this was not a full
repository audit. A scoped GitHub search for Hermitten returned historical
research notes, not an executable billing interface. No live Hermitten API,
financial source of truth or commercial provisioning owner was verified.
Those notes are not a basis for implementing an invented billing integration.
Existing CI includes dependency audit, secret scanning and TURING workflows;
none is represented as having passed for this increment before a run exists.

## Implementation inventory

| Area | State in this increment | Authority / remaining gap |
| --- | --- | --- |
| Native computation | Facade reused, not reimplemented | PR #96 `TuringPipeline.submit` and `NativeBackend` |
| Workspace UI | `/turing`, isolated from mining UI | Same React/Vite stack; no mining polling on this route |
| Access | Existing AL HARAS preflight on every workspace request | Security subscription only; NOT a commercial TURING allocation |
| Identity scope | Jobs restricted to verified tenant + actor | No organisation collaboration/roles/SSO implemented |
| Jobs | Submit, manual status refresh, queued cancellation | Process-local, bounded; running work cannot be forcibly cancelled |
| Result inspection | Native report and provenance, JSON export | Not independent certification or shared enterprise custody |
| Retry | Same-key replay/conflict refusal within one process | No restart-safe or cross-replica idempotency |
| Usage | Not implemented | No monetary values, billable quantities or ledger generated |
| Provisioning / billing | Not implemented | Need approved contracts, resource semantics and Hermitten interface |
| Public website / customer admin / operations | Deferred | No decorative routes or unsupported controls created |

## Scope and resource semantics

There is no commercial "instance" in this increment. A native backend is a
process-local execution adapter, not an instance sold to a customer. The pilot
sets a width ceiling of 12 logical qubits, 4,096 materialised amplitudes and
256 operations per request; these are defensive admission limits, not measured
performance, throughput, universal mathematical limits or contractual capacity.
The registry retains at most 256 jobs globally and 32 per tenant/actor. Completed
entries count toward these limits; there is intentionally no eviction that
would silently erase deduplication. Registry exhaustion returns 429. A controlled
restart clears jobs and keys; operators must account for this before retrying.

The default native facade does NOT constitute shared CompositionRoot enterprise
acceptance. Custody/replay remain the facade defaults (false). Before an enterprise
pilot, inject/qualify the proper shared backend and custody contracts rather than
claiming that an HTTP wrapper has solved enterprise persistence.

## Contract v1

All actions use `POST /api/v1/quantum/workspace` to keep the complete pilot under
one explicit guardian operation, `quantum.workspace`. Read-like status requests
also use POST because they carry sensitive scoped access through the guardian;
they do not create computations. No arbitrary resource URLs are accepted.

Headers: `Authorization: Bearer …`, `X-HYBA-Tenant`, `X-HYBA-Actor`, and
`Content-Type: application/json`. The canonical guardian verifies the token's
binding to tenant/actor before dispatch. The adapter rechecks the allowed receipt's
tenant and operation. The source of identity is the existing verified preflight,
not a free-form tenant argument or browser role. A valid security subscription is
necessary but insufficient for a production computational commercial entitlement.

Every body includes `action` and an `observation` object for the guardian.
Additional action-specific fields:

| Action | Fields | Response |
| --- | --- | --- |
| `capabilities` | None | 200 pilot admission envelope, integration limitations |
| `submit` | `program`, `idempotency_key` | 202 new job; 200 replay |
| `status` | `job_id` | 200 last native state; report only for succeeded |
| `cancel` | `job_id` | 200 state + `cancellation_accepted` |

Native program: `{ "n_qubits": 2, "operations": [{ "gate": "h", "qubits": [0] },
{ "gate": "cx", "qubits": [0, 1] }] }`. This is an example INPUT, not a result.
Only fixed native gates are accepted. Bool/string widths, repeated/out-of-range
targets, angle fields, extra configuration and unsupported gates are refused.
The engine still performs its own authoritative compilation/admission.

Successful responses identify `schema_version: turing.workspace.v1`,
`service_mode: technical_evaluation_only`, and
`persistence: in_memory_process_local`. Job states are exactly `queued`,
`running`, `succeeded`, `failed`, `cancelled`, matching the native facade.
Timestamps are UTC ISO-8601 submission acknowledgement times, not invented
execution start/completion times. Failed jobs expose a safe error code, not raw
engine exception messages/host paths. Successful reports are returned without
rewriting the canonical evidence.

Errors: 400 malformed schema/key; 403 missing admission; 404 job not visible in
current identity/process; 409 same key with different program; 422 native
admission refusal; 429 registry budget; 503 disabled/missing dependency/service
unavailable. Guardian errors pass through the existing boundary, including
subscription/evidence denial. A timeout or 5xx does NOT prove failed execution.

Idempotency is scoped to tenant + actor + key. Keys are hashed before reaching
the native backend. Input canonicalisation determines conflict semantics.
The UI preserves the program/key after an ambiguous acknowledgement and retries
that request only. It never automatically resubmits. Idempotency is not a
billing deduplication guarantee. Status is manually refreshed to avoid repeated
expensive guardian/evidence evaluation. No list/pagination/filter API is claimed.

## Visual system and route map

Paper `#f7f8f6`, ink `#172c39`, muted `#52626c`, blue `#185d82`, line `#c8d0d3`.
System sans typography avoids new font licensing/deployment requirements. A
restrained wordmark, explicit step labels, visible focus, labelled forms, live
status, responsive cards, evidence tables and horizontally scrollable raw JSON
form the initial component language. There are no external imagery dependencies,
fake quantum graphics, decorative charts, dark-mode controls or market claims.

`/turing` is the only new application route. Existing operator routes are kept.
It is not a public marketing/legal site or a complete organisation-admin portal.
Potential later routes in the master brief remain proposals until their owners
and service contracts exist.

## Threat model / release gates

- **Cross-tenant or actor access:** preflight identity binding plus registry scope;
  return the same 404 for unknown and foreign jobs. Regression tests cover status
  and cancellation. Live AL HARAS HTTP/tenant-isolation tests still required.
- **Credentials / compromised browser:** bearer stays in React memory, never
  local/session storage; same-origin fetch, redirect rejection, no credential
  logging. This is not SSO, MFA or an HttpOnly enterprise session. XSS remains a
  material threat; review the host CSP and any third-party scripts before exposure.
- **CSRF:** explicit bearer and custom headers, no cookie credentials, JSON POST;
  no CORS changes. An enterprise cookie-session transition needs separate CSRF review.
- **Abuse:** bounded program/registry and existing guardian body limits; these do
  not replace edge rate limits, per-tenant CPU quotas, timeout/resource accounting
  or a denial-of-service audit. Long-running jobs are not forcibly terminated.
- **Unsupported provisioning/charges:** no price, invoice, allocation, commercial
  entitlement or usage ledger is created. Obtain owner-defined resource units,
  contract approval, immutable metering/outbox and tested Hermitten ingestion first.
- **Restart/replay:** no distributed job/deduplication state. Do not run a public
  multi-replica deployment or blindly retry after a restart.
- **Audit failure:** existing guardian durable-audit initialization remains
  mandatory. The host `_json` continues attaching/auditing its receipt. Full
  audit persistence/failure injection is a release gate, not proven by route tests.
- **Sensitive evidence:** reports may include inputs and configuration. Export is
  only for the same verified owner; retention, legal hold, backups, deletion and
  residency need explicit enterprise policy. No result data enters analytics.

No conformance/certification or complete WCAG audit is claimed. A visual/keyboard
foundation is present; assistive-technology, zoom, contrast-state coverage and
browser compatibility qualification remain required.

## Local qualification record

Run in an isolated workspace copy using Python 3.13 and available browser tools:

- Python: 23 adapter/routing unit tests passed; one opt-in real-engine smoke
  intentionally skipped. Fake jobs are explicitly labelled fixtures; route tests
  execute the extracted real method but do not boot the heavy CompositionRoot.
- TypeScript: 18 client contract tests passed in an isolated Vitest 4 environment.
- Strict type check for the two new implementation TS/TSX modules passed using
  isolated TypeScript 5.9.3 + React 19 declarations. This is not a full repository
  TypeScript 7 check.
- React component and CSS bundle built with sandbox esbuild. This is not the full
  locked Vite production build, dependency audit or release artifact.
- Local Chromium UI fixture checks passed: connection, review, lost acknowledgement,
  retained same-key retry, report inspection/export, disconnect clearing data,
  no browser credential storage, and no mining API calls. No runtime page errors.
- Desktop (1440px) and mobile (390px) review/error/results/disconnected captures
  were inspected; no page-level horizontal overflow in checked mobile states.
  Fixture screenshots do NOT demonstrate real engine execution or auth acceptance.

Not executed locally: real native computation, live guardian/subscription/TOE
integration, full host regression suite, production Vite build, locked dependency
scan, commercial A/B/D/E/F/G lifecycle acceptance, distributed persistence, soak
or enterprise security review. Remote CI success is not asserted.

## Reproduce and review

Adapter unit tests (stdlib only):

```bash
python -m unittest discover -s tests -p test_turing_workspace_pilot.py -v
```

In the repository's qualified/locked TURING environment, run the real smoke
without fake engines:

```bash
TURING_RUN_ENGINE_SMOKE=1 turing_universal_quantum_computer/.venv/bin/python \
  -m unittest discover -s tests -p test_turing_workspace_pilot.py -v
npm --prefix frontend ci
npm --prefix frontend run lint
(cd frontend && npx --no-install tsc --noEmit -p tsconfig.turing.json)
npm --prefix frontend run test:ts -- src/turing/client.test.ts
npm --prefix frontend run build
```

A narrow draft-PR workflow requests the locked real-engine smoke and contract
checks; inspect its actual results before approval. The host/guardian integration
must also be exercised with a legitimate issued subscription and real evidence
provider; do not add a bypass to make the pilot appear connected.

Only an authorised operator in a non-production evaluation environment may set
`TURING_WORKSPACE_PILOT_ENABLED=1`, run the existing `main.py` service and open
`/turing`. No environment, infrastructure or production flags were changed by
this implementation. TLS, credential issuance and evidence availability must be
configured using established systems; no fabricated credentials are shipped.

Rollback: unset the pilot flag (all pilot actions return 503), withdraw `/turing`
from use, let acknowledged native work finish, and revert this increment if
required. Do not restart blindly to free capacity: first account for live jobs
and tell users that process-local history/keys will be lost.

## Next acceptance increment

1. Execute the real-engine smoke and live AL HARAS request/denial/audit tests;
   qualify the existing shared-enterprise backend and durable custody adapter.
2. Identify authoritative organisation/contract/provisioning/usage owners. Define
   "instance" and approved quota semantics; do not equate counts with throughput.
3. Obtain the live Hermitten schema and run duplicate/retry/reconciliation tests
   against it. Reuse its ledger; do not create a second one.
4. Build one contract-to-provisioning-to-computation-to-metering journey with
   server-owned entitlements and accountable release owners, then expand routes.

Commercial hypothesis only: negotiated capability/capacity commitments plus
measured consumption where contracts support it, not default per-seat pricing.
No prices, savings, customer references or performance advantage are asserted.
