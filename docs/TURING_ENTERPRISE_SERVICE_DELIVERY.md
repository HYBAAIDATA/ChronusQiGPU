# TURING — Enterprise Service Delivery and Commercialisation

Status: **0.2.0 service implementation / local contract validation. Not deployed,
production-approved or published.** This is distinct from mathematical correctness
and package/release qualification (PR #96). One cannot certify the other.

## Product and commercial boundary

Sell governed computational intelligence, reproducible results and provenance,
not per-user software licences. A provisioned instance in this implementation
means **one logical concurrent job admission slot** within an approved customer
contract. It is neither a VM nor a physical QPU/GPU nor an isolated dedicated
runtime. Contracted, allocated, available, in-flight and consumed are distinct.
Host/global and project budgets are enforced transactionally; the reference queue
worker is serial. Capacity/latency promises must come from target-host measurement.

Candidate consumption unit is `verified_execution.v1`, one verified completion.
It is not a calibrated economic unit; varied workloads may have different costs.
Prices, reservation periods, overage, credits, tax and invoices remain Hermitten's
commercial authority, never inferred from a UI counter or technical job state.

Commercial packaging hypotheses (not approved prices or actual customers):

| Offer | Proposed commitment | Required validation |
|---|---|---|
| Enterprise | Negotiated term + reserved capacity + bounded usage, governance/support | Workload envelope, measured delivery cost, isolation/residency, agreed service levels |
| Research/specialist | Project/capacity allowance and explicit ceiling | Time-to-result, onboarding/support effort, upgrade criteria |
| Strategic engagement | Scoped analytical outcomes/acceptance, optional reserved capacity | Deliverable measurement, integration cost, IP and specialist support |

Unit-economics model to validate with actual workload records: revenue = term
commitment + reservation-period fees + agreed consumption + premium/engagement
items − credits. Delivery cost = measured compute/memory/storage/egress + support
and operations + external costs. Contribution margin = (revenue − delivery cost)
/ revenue. Avoid double charging commitments and allowances. No invented demand,
prices, margins, 100-instance economics or named-customer endorsement.

## Requirements closure and acceptance ownership

**Implemented** means executable source exists, not that an external gate passed.
See service README and deployment runbooks for commands and exact limits.

| Requirement from brief | Implementation | Executed evidence / remaining acceptance |
|---|---|---|
| Distinct commercial/service workstream | Separate `services/turing-enterprise` private package | Kept outside mathematical package; no changes to VQC algorithms |
| Define offer, instance/capacity/usage boundaries | This spec + README and schemas | Logical slots/verified completions implemented; contracts/pricing/SLA require commercial owner |
| Customer organisation, contract and billing identity | `EnterprisePlane.approve_customer`, immutable exact-term approvals | Signed authority/exact-envelope negatives tested; actual legal approval not generated |
| Provision, resize, activate, suspend, terminate | Transactional `ControlPlane` lifecycle and command receipts | Contract/global/project quota and concurrency tests; not physical orchestration |
| Recovery/idempotency | SQLite WAL/FULL, durable commands/claims/outboxes, schema migration | Restart/atomicity/idempotency and ambiguous execution tests; target environment recovery drill outstanding |
| Operator console | `/ops`, distinct signed operator authority, disjoint approver identity configuration | API role negatives + browser rendering; live SSO/operator runbook acceptance outstanding |
| Customer administrator portal | `/admin`, users/roles/projects/usage/spend ceilings/audit | Current membership, last-admin and tenant/project negatives tested |
| Analyst workspace and API | `/workspace`, bounded QASM submission/result/cancel; authenticated OpenAPI | API/form rendering tested; canonical installed-runtime CI added, not observed passing locally |
| Shared identity and governance | RS256 OIDC/JWKS, code+PKCE/state/nonce, private server sessions, CSRF/origin, AL HARAS signed actions | Real crypto positive/negative tests; current service membership revocation tested; enterprise IdP/MFA/device policies need deployment acceptance |
| Separate privileged control | Server-side operator and commercial-approver allowlists, customer role checks | No browser role flag can issue operator authority; full Guardian policy assembly not claimed |
| Capacity admission enforcement | Per-contract, project and configured global budgets at API/service boundary | Real SQLite contention/quota tests; serial worker and host sizing are explicit limits |
| Governed execution and durable results | Canonical pipeline adapter, bounded process group, tenant-keyed custody | Process limits/cancel/output/custody tested; real VQC/Kellogg and container integration are non-skipping CI gates, not local successes |
| Metering/provenance/reconciliation | Completion+immutable usage in one transaction, SHA identities, ACK-bound retry, audit chain | Malformed/non-PASS/duplicate/quarantine negatives tested; independent WORM audit anchoring requires deployment |
| Reuse Hermitten | HTTPS adapter, capability handshake, statement/import/correction/reservation ports | Explicit receiver double tests; actual receiver/rates/invoices not established |
| Monetary limits | Durable spend intent, remote authority, atomic admission state, compensation event | Approval/denial/replay/failure/cancellation/completion tests; real concurrent financial settlement acceptance required |
| Renewal and offboarding | Approved next contract, drain gates, archive, suspended reactivation, retention-gated live data purge | Renewal/allowance/retention tests; backup expiry/legal holds/privacy policy remain deployment responsibilities |
| Onboarding/support/incidents | Executable operator APIs + `deploy/OPERATIONS.md` | Runbook and escalation template delivered; actual on-call/contact/SLA must be assigned |
| Deployment and release discipline | Non-root read-only image, offline worker reference Compose, CI, signed artifact-bound promotion gate | Local build/package/crypto tests; Docker unavailable locally, remote gate results not assumed |
| Publication | Separate `publication_rights` signed evidence gate and public-claim boundary | No upload/tag/public visibility change; rights/license/IP and package signoff outstanding |

## Controlled enterprise pilot

1. Define and approve the offer, workload limits, residency/isolation, meter/rate
   mapping, support/retention and contractual boundaries. No per-seat default.
2. Configure the real IdP and Hermitten receiver, target environment, signing keys,
   approvals and monitoring. Confirm no capability is made available by merely
   hiding/showing a UI control.
3. Onboard one or two **approved** design partners, not hypothetical customers.
   Require positive and negative tenant/project tests, correct refusals, complete
   provenance, idempotent provisioning, bounded concurrency and spend authority.
4. Reconcile technical usage → import ACK → commercial statement/invoice/credit.
   Validate actual delivery costs and willingness to pay, not just job counts.
5. Exercise outage, lost billing response, revocation, ambiguous execution,
   backup+custody restore, renewal and offboarding. Stop pilot on tenant leakage,
   unverifiable results, duplicate economic posting or unexplained spend drift.
6. Record named owner acceptance and retained evidence; only then standardise
   contracts/tiers, automate more self-service, expand sales and promote release.

## Promotion evidence

Mandatory signed gates: `runtime_integration`, `identity_security`,
`billing_reconciliation`, `recovery_load`, `package_qualification`,
`commercial_approval`; publication also `publication_rights`. Manifest binds the
running image source commit, named reviewer, recent execution time, retained
artifact SHA-256, signature and expiry. This verifies evidence binding/freshness;
it cannot independently prove a reviewer assertion true. Unit fixture signatures
are never production approvals. Missing gates keep production closed.

Evidence in `services/turing-enterprise/evidence/local-validation.json` records
historical 0.1.0 validation. `completion-validation.json` records the new scope.
Neither is signed external acceptance. Current implementation is not a physical
quantum computer, general arbitrary-scale circuit promise, validated tariff,
licensed publication decision or proof of customer demand.
