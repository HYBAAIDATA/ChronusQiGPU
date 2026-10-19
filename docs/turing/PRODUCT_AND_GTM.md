# Product, design and enterprise-pilot plan

## Scope correction — billing deferred

The user's clarification supersedes the original billing requirements: the
intended model is **usage-based**, billing is **on hold**, and **Hermitten is not
an integration dependency**. Do not implement Hermitten, pricing/rating, invoicing,
payments or financial reconciliation in the current scope. Do not request
Hermitten access or hold non-billing implementation/acceptance on it. Keep
execution/usage evidence distinct from charges; any future billing work needs a
separate authorised scope. Operational usage accounting must not invent a
measurement unit or financial event. Identity, authorisation, provisioning,
execution, evidence and recovery work remain in scope.

## Positioning and evidence policy

TURING is being developed as computational capability delivered as a service:
precise mathematical inputs, governed execution, inspectable returned evidence.
The current public experience offers a bounded technical evaluation, not a
production SLA, physical QPU, universal solver, measured advantage or independent
certification. Only the native program workflow exposed by this interface is
advertised. The two-qubit Bell circuit is editable input, never a supplied result.
No customer story, publication or comparative benchmark is invented.

## Audience and use-case prioritisation

| Audience | Decision / value to validate | First workflow |
| --- | --- | --- |
| Analyst or researcher | Can an admitted mathematical task be specified and its answer inspected? | Compose/review native program -> real execution -> inspect payload/validation/provenance |
| Technical/security reviewer | Are the execution boundary, missing evidence and limitations understandable? | Examine report scope, refusals, architecture and controls with the service owner |
| Enterprise buyer / administrator | Can an agreed use case become a governable, economically viable service? | Bounded evaluation brief and data policy; later contract/provisioning/roles once real services exist |
| Service operator / billing owner | Can delivery be recovered and usage reconciled without duplication? | Owner-contract review and actual-service acceptance A–G, not a decorative operations console |

Initial ICP hypothesis: organisations with explicit mathematical workloads,
reviewable evidence requirements and willingness to jointly qualify a bounded
service. This is a hypothesis, not market-size evidence. Prioritise admission,
faithful outputs and recovery before industry-specific claims. Differentiate by
the inspectable workflow actually demonstrated; establish any competitive or
performance advantage through approved reproducible evaluations first.

## Implemented route map and boundaries

- `/turing/product`: positioning, service journey, audience paths and evaluation CTA.
- `/turing/capabilities`: exact workspace domain/limits and excluded features.
- `/turing/how-it-works`: review, admit/execute, inspect, recover.
- `/turing/enterprise`: commercial/activation conditions and unavailable integration register.
- `/turing/documentation`: actual evaluation API, access, errors, history/export.
- `/turing/security`: implemented request controls, data lifecycle and obligations.
- `/turing/research`: report interpretation and evidence/claim distinction, no invented papers.
- `/turing/contact`: accessible local evaluation-brief JSON export; explicitly NOT sent or a CRM enquiry.
- `/turing/legal/privacy`: technical evaluation data notice, NOT an approved privacy policy.
- `/turing/legal/terms`: missing-approval/release gate, NOT fabricated contractual terms.
- `/turing/app`, legacy `/turing`: computational workspace and retained-execution history.
- Unknown TURING routes: clear not-implemented page; original non-TURING application unchanged.

The first site has no invented contact address, analytics collector, status
service or support submission endpoint. Supply approved channels before launch.
Customer administration and internal operations are withheld until actual
membership/capacity/commercial/support contracts can support functional flows.

## Design system

Paper `#f7f8f6`, ink `#172c39`, muted `#52626c`, blue `#185d82`, line `#c8d0d3`;
white cards and soft blue evaluation/confirmation regions. Status/error always
includes text, not colour alone. Fixed light evaluation theme is intentional.
System sans avoids external font requests; code uses local monospace. Body16px,
small14px, readable line-height, restrained responsive display typography.
Spacing scale4/8/12/16/24/32/48/64; content max1120px with desktop gutters and
narrow-screen single-column flow. Borders before shadows; no decorative imagery
or misleading quantum visualisation. Visible focus, semantic landmarks/heading,
labelled controls, live feedback, reduced motion and bounded internal JSON scroll.

Reusable families: product header/footer/CTA/article navigation; cards and
notices; labelled fields and buttons; review/cancellation confirmation; native
status/input envelope; evidence stages/provenance/payload; filtered history and
pagination; safe JSON download. Business rules stay in client validation,
response parsers, server adapter and integration boundaries, not page copy.
Automated axe/overflow and visual checks are engineering evidence, not complete
WCAG 2.2 AA certification. Qualify assistive technology, zoom and all browsers.

## Commercial direction — usage-based, billing on hold

The intended model is usage-based, not seat licensing. Billing implementation,
pricing/rating, invoices, payments and financial reconciliation are deferred.
Hermitten will not be integrated. Do not promise rates, allowances or billable
units, and do not equate instance counts or completed jobs with measured usage.
Future measurement and charging decisions require their own approved scope;
they must not obstruct current identity/provisioning/execution delivery.

## Qualification, onboarding and handoff

1. Qualify buyer, user, task, supported domain, required evidence and procurement/security owner.
2. Agree success criteria, synthetic/public input policy and operator contact channel.
3. Review architecture/security questionnaire below and approved handling arrangement.
4. Operator issues legitimate evaluation identity through the existing authority; no bypass.
5. Run a real admitted task and inspect report scope, refusals, reproducibility limits and export.
6. Record observed completion/recovery and value; distinguish evidence from hypotheses.
7. For enterprise progression, approve resource definition, contract/version and quotas.
8. Handoff canonical customer/contract/entitlement IDs to capacity owner; authorised operation provisions and verifies state with audit.
9. Customer admin configures real IdP/membership/roles; test invited and revoked users and project isolation.
10. Qualify operational usage evidence, support and restore; obtain in-scope service signoffs. Billing scenario E and financial parts of lifecycle/recovery are deferred.

Admin training must cover invitations/revocation, role scope, contract vs usage,
capacity vs throughput, destructive confirmations, export confidentiality and
incident escalation, using the actual services when integrated. Customer-success
measures: agreed task/evidence acceptance, successful permitted-user onboarding,
recovery time against agreed policy, reconciled usage completeness and support
resolution. Do not substitute vanity page views for these outcomes.

Renewal/expansion: review evidence, utilisation, cost-to-serve, exceptions and
support load; approve an effective service scope and capacity change,
not an unreviewed retroactive edit. Termination requires access revocation,
approved retention/legal-hold handling; financial settlement remains deferred, not a browser disconnect.

## Security/architecture questionnaire pack

| Question | Current answer / required evidence |
| --- | --- |
| Identity / SSO / MFA? | Existing AL HARAS evaluation credentials only; enterprise IdP/session contract and test evidence required |
| Tenant isolation? | Server tenant+actor job ownership; regression tested with fixtures, live authority qualification outstanding |
| Data sent/stored? | Native inputs/reports to same origin; process-local registry; guardian audit/evidence separate; operator data map required |
| Secrets? | UI memory only; same-origin bearer request, no browser persistence; deployment vault/TLS and credential lifecycle require approval |
| Retention/residency/deletion? | No enterprise promise; obtain Theseus/store policy, backups, legal hold and deletion verification |
| Encryption/compliance? | No unverified claims; obtain deployment configuration/control evidence and independent reviews if needed |
| Usage/financial integrity? | Operational usage contract still to qualify; financial charging on hold, no Hermitten dependency |
| Availability / recovery? | Single-process pilot; no SLA or restart-safe history; qualify approved durable service before enterprise activation |
| Operator access / incidents? | No unrestricted impersonation; approved scoped/time-bound grants, audit, escalation contacts and incident process required |
| Software supply chain? | Existing CI plus scoped regression workflow; locked dependency audit/full build/remote CI outcomes must be reviewed |

## Privacy-respecting instrumentation proposal

No analytics SDK or collector is shipped. Before instrumentation, approve schema,
purpose/access/retention and customer policy. Allowlisted event envelope proposal:
version, event_id, occurred_at, service/version, event_type, coarse outcome,
correlation_ref and pseudonymous scoped subject only if approved. Allowed events
include admitted/submitted/finished/failed/cancelled job, viewed/exported result,
onboarding/provisioning stage, ingestion/reconciliation exception and support
request. Do not include bearer, email, raw program, result, hashes that expose
confidential workloads or arbitrary free text. Keep analytics separate from
billing facts and guardian audit. Deduplicate events; report measured funnel and
service completion against an agreed cohort, never implied customer counts.

## Launch gate

Approve claims, public terms/privacy/controller identity and data arrangements;
real contact/support/incident channels; source-verified research/case studies
only if authorised; API onboarding and release notes; approved analytics policy;
In-scope real service evidence and operational/security signoff (financial scenario E deferred); explicit deployment
authorisation. The current local-only brief export is not a completed sales
handoff. Draft release note: bounded evaluation workspace and evidence-based
product pages added; enterprise provisioning and durable custody are
not integrated; billing is explicitly deferred, not a missing Hermitten integration. No public or production launch has been performed.
