# TURING — Enterprise Service Delivery and Commercialisation

Date: 19 October 2026. Source baseline inspected: `af4e34a3c9463750dc32bcd1eae41f7310944833`.
Status: **pilot control foundation implemented; production service / public launch NOT approved**.
This workstream is distinct from TURING package organization and software release
qualification (PR #96). Neither automatically certifies the other.

## Product boundary and commercial decisions

The offer is governed computational intelligence, with reproducible results and
explicit state-class admission, not per-seat software licensing. The pilot unit
of provisioned capacity is a **logical concurrent admission slot**. This does not
promise 100 isolated runtimes, reserve a physical GPU, establish global capacity,
or imply arbitrary universal circuits at any width. Real supported operations,
representations and refusal semantics continue to belong to the existing VQC.

Proposed packaging, not signed terms or established prices:

- Enterprise: negotiated term commitment, validated reserved capacity, usage
  allowance, governance, reporting and explicitly agreed support/service levels.
- Research/specialist: bounded project or capacity commitment, usage ceiling and
  standard reporting; not assumed to be self-service in the initial pilot.
- Strategic engagement: scoped deliverables and acceptance criteria, optional
  capacity and specialist support. Outcome-linked fees need agreed measurement.

Commercial approvals still needed: capacity meaning beyond the logical pilot,
workload classes and limits, isolation/residency, term/renewal, pricing/rate cards,
service commitments, billable versus failed/cancelled work, refunds/corrections,
retention/deletion, support obligations, background IP and publication rights.
No named institution in a planning example is assumed to be an actual customer.

## Implemented contract chain

`approved commercial record reference -> operator approval -> logical reservation
-> customer signed capability -> atomic job admission -> worker dispatch ->
existing VQC pipeline -> verified result -> candidate usage event + outbox ->
receiver acknowledgement`

Implementation: `services/turing-enterprise/src/hyba_turing_service/control.py`.
Runtime port: `adapters.TuringPipelineRuntime`, lazy consumption of the actual
VQC pipeline; not a replacement engine. Authorization consumes the actual
AL HARAS subscription verifier; external SSO/membership and Guardian policy
assembly are not recreated here. Durable application records use SQLite, not a
new interpretation of OVID/THESEUS mathematical custody. Tenant-scoped result
custody remains an integration gate, not claimed by the local DB's existence.

The outbox speaks `turing.usage.v1`; it has **no currency or rate** and cannot
create an invoice. Stable event ID is the hash of schema/tenant/job identity.
Execution, usage import and invoice/payment state remain separate. Hermitten
must confirm receiver deduplication, contract/rate mappings, recurring fees,
capacity reservations, credit adjustments and auditable reconciliation.

## Minimum UI / API contract

No new public HTTP boundary is exposed before the production gates below.
The implemented library contracts support a later authenticated API composition.
Do not expose DB path, clock, authority, runtime or billing-sink arguments as
network request fields.

| Screen | Current supporting library | Remaining work |
|---|---|---|
| Customer overview | `overview`: state, contracted/allocated/available/in-flight/consumed | Internal customer listing, pagination, health/readiness, contract details, UI |
| Instance/capacity management | Operator `approve_customer`, `provision`, `lifecycle` | Approval-system validation, global physical capacity and orchestration, UI |
| Users and permissions | Signed per-operation tenant/actor capabilities verified server-side | SSO, membership, groups/projects, revocation, delegated admin, UI |
| Usage and costs | Tenant usage events, metering schema, durable outbox | Hermitten rates/imports/invoices, spend limits, cost provenance, UI |
| Provisioning/audit history | Atomic command receipts, filtered tenant audit, reconciliation | Pagination, independent audit anchoring, operator UI, alerting |

Internal operations, customer administration and analyst workspace must have
separate entry points and authorization. Do not turn an analyst token into an
operator token based on a UI role flag. The first GUI should consume these
contracts; it must not become the authority for entitlements or invoice state.

## Workstream checklist / acceptance ownership

- [x] Add separate service-control package, leaving VQC release/package work intact.
- [x] Define logical-slot and verified-completion semantics for this implementation.
- [x] Record customer, approved contract reference, billing account and validity.
- [x] Separate operator/customer signed capability checks and tenant-scoped reads.
- [x] Add atomic logical provisioning, resizing, suspension, retirement and retries.
- [x] Enforce quota/concurrency before dispatch, including concurrent DB clients.
- [x] Add durable execution quarantine, no automatic ambiguous re-execution.
- [x] Add immutable candidate usage and retryable acknowledgement-bound outbox.
- [x] Document interface split, pilot commercial model and operating recovery path.
- [ ] Validate commercial approval record against the real approval/contract owner.
- [ ] Define global physical capacity, isolation and an enforceable runtime envelope.
- [ ] Integrate SSO, tenant membership, project policy and immediate revocation.
- [ ] Bind service to real VQC execution and tenant-scoped durable result custody.
- [ ] Implement authenticated network API, operator/customer/analyst interfaces.
- [ ] Integrate real Hermitten with reconciled statements, corrections and invoices.
- [ ] Validate pricing hypotheses and unit economics against measured workloads.
- [ ] Complete onboarding, incident/support, renewal, offboarding and deletion flows.
- [ ] Run a controlled design-partner pilot with explicit acceptance and stop rules.
- [ ] Complete independent release, security and publication approval gates.

## Mandatory production / publication gates

| Gate | Required fresh retained evidence | Current status |
|---|---|---|
| Service controls | Real authority signatures, tenant negatives, concurrency, atomicity, restart, wheel tests | Locally executed focused tests; remote CI not assumed |
| Mathematical qualification | Actual installed TURING/Kellogg suite, exact backend/admission/witness/custody regressions, no synthetic pass for unavailable checks | Only the focused stabilizer measurement regressions were additionally executed here |
| Integrated runtime | Approved contract -> real VQC -> verified retained result -> usage across service restart | NOT EXECUTED; transport tests use labelled runtime doubles |
| Runtime containment | Worker-process deadlines, resource caps, cancellation/fencing, hostile QASM and independent tenant isolation | OPEN; in-process adapter is not an untrusted-workload sandbox |
| Identity / security | SSO, key rotation/revocation, Guardian policy, privilege separation, independent review and deployment secret scan | Signed-capability conformance tested; broader integration OPEN |
| Hermitten | Authenticated real receiver, contract rates, duplicate/replayed events, lost ACK, invoice/credit reconciliation | OPEN; billing-double tests are not Hermitten evidence |
| Operational readiness | Measured load/latency/cost and saturation, global capacity, backups/restores, outage and incident drills, on-call ownership | OPEN |
| Commercial pilot | Approved offer/instance definition, lawful data use, signed pilot acceptance, validated tariffs and support | OPEN |
| Public artifacts | Clean scoped package install, approved license/IP/background rights, SBOM/dependency and secret review, audited claims, publication signoff | OPEN; no publication or IP reassignment authorized by this code |

Do not merge or publish on local unit tests alone. Keep this service alpha/private
until its gates pass. Review/qualify PR #96 separately; run the combined repository
CI and deployment validation before production promotion. No live deployment,
public package upload, release tag or customer invoice is part of this change.

## Verification scope and historical measurement finding

The 2026-10-04 Notion record reported tableau measurement defects. Current main's
`stabilizer.py` includes the paired-destabilizer exclusion and corrected phase
algebra, with an independent dense-reference regression suite and no mathematical
xfail. The **verbatim engine and measurement test source** were copied from the
inspected repository into an isolated namespace and executed here: **11 passed**.
That includes randomized collapse, both branches and post-measurement continuation.
This is fresh scoped evidence, not a full checkout/install or all-backend result.

The service suite uses the **verbatim AL HARAS entitlement verifier**, real SQLite
transactions and labelled runtime/billing doubles. Its source and clean-wheel
runs each passed **48 tests**, with no skipped or xfailed cases. No real Hermitten,
physical provisioning, full VQC pipeline integration or enterprise load test ran.
See `services/turing-enterprise/evidence/local-validation.json` for retained scope
and source hashes. CI is configured on Python 3.11/3.13; configuration alone is not
proof it executed or passed. Full repository gauntlet remains outstanding.

Targeted GitHub secret scanning was unavailable because this repository does not
have GitHub Advanced Security enabled. A local detect-secrets scan of the proposed
files reported 12 entropy findings, manually inspected as Git/content/wheel hashes,
not credentials. This does not replace repository-wide deployment security review.
