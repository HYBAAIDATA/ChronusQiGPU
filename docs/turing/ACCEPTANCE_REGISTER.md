# TURING implementation and acceptance register

Status: expanded technical-evaluation implementation, draft PR #98 stacked on
PR #96. **The complete enterprise definition of done is not met.** Nothing in
this register authorises deployment, merging, customer commitments or charges.
The input is preserved in `MASTER_BRIEF.md`; every acceptance item remains subject
to source-owner verification. Unavailable does not mean an empty customer account.

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

## Requirements by master-brief section

| Section | Delivered / assessed | Outstanding acceptance |
| --- | --- | --- |
| 1 Vision | Capability-as-service positioning; inspectable results; no seat default | Product-owner approval and customer validation |
| 2 Reconnaissance | Existing Vite/React/Python, PR96 facade, guardian, process-local jobs, CI and scoped Hermitten search assessed | Full repo audit; authoritative control-plane inventory; no Hermitten dependency |
| 3 Architecture | Existing computation reused; identity/control/commercial boundaries separated | Operational enterprise control plane; billing platform deferred |
| 4 Engineering | Existing compatible stack retained; strict typed client, response validation, tests; no new production dependency | Locked full frontend lint/build/audit; compatibility and host regressions |
| 5 Brand | Shared tokens, wordmark, typography, spacing, forms, evidence and responsive layouts | Brand-owner approval; full assistive-technology audit |
| 6 Information architecture | Product, capabilities, workflow, enterprise, docs, research, security, enquiry, technical legal notices; computation route; unknown route fallback | Authenticated customer-admin/operator routes require real services; not fake dashboards |
| 7 Public site | Functional navigation, supported example, evidence boundaries and local evaluation brief export | Approved enquiry delivery/support channel, legal policies, publications and approved customer references |
| 8 Workspace | Native JSON validation/review/confirmation, job/status, cancellation confirmation, same-key recovery, input/envelope, unchanged report export, returned validation/payload/provenance, identity-scoped history/search/filter/pagination | Shared projects/teams; live computation and custody acceptance; typed numerical units/tolerances depend on actual returned data; no invented chart |
| 9 Organisation | Explicit identity/project boundaries, owner/entity mapping, least-privilege proposal | IdP/session/invite/offboarding, server roles and membership APIs; role-isolation qualification |
| 10 Provisioning | Resource-definition decision gate; intended request/recovery contract | Capacity inventory, approved instance meaning and contract, lifecycle/allocations/activation service, operator UI and live recovery tests |
| 11 Commercial | Usage-based direction confirmed; charging/rates and financial administration deferred | No billing gate for current non-billing delivery; no invented price or usage unit |
| 12 Billing | Superseded by user: billing on hold; no Hermitten integration | Deferred, NOT a current blocker; usage accounting remains distinct from financial charging |
| 13 Contracts | Implemented OpenAPI workspace contract; typed guarded integration boundaries | Owner-approved missing contracts and real adapters; no guessed endpoints or second ledger |
| 14 Security | Tenant/actor scope, admission recheck, strict fields, safe error, credential memory-only, escaped text, server and client regressions; threat model | Live guardian/audit, enterprise isolation, rate limits, TLS/CSP, backup/residency/retention/legal and dependency release review |
| 15 UX | Loading/empty/validation/denial/expiry/retry/confirmation/success, focus and responsive states; automated axe checks | Manual screen-reader/zoom/keyboard end-to-end and supported-browser qualification; no complete WCAG claim |
| 16 Analytics | Data-minimising event proposal; no third-party tracker shipped | Approved collector, retention/access/consent decisions and real operational measurements |
| 17 Operations | Support/incident authority boundary and runbook | Permissioned operations API, escalation channel, audited support grants and incident console |
| 18 GTM | Positioning, ICP/personas, qualification/evaluation, onboarding, security questionnaire, commercial handoff and launch gates | Approved channels/terms, real pilot evidence, training on operational admin services, production acceptance |
| 19 Tests | Local adapter/client/route/boundary/browser regressions and CI definition | Real in-scope service scenarios (E/financial checks deferred), locked host build, CI evidence, security/performance qualification |
| 20 Deliverables | See numbered mapping below | Customer admin, operator console and provisioning incomplete; billing deferred |
| 21 Execution | Discovery, product foundation, bounded functional slice and public experience implemented | Commercial control plane, actual-service qualification and release readiness |
| 22 Rules | Engine unchanged, no fabricated commercial data, no production changes; reviewable same-PR increment | Continue preserving these rules during integration |
| 23 Done | Coherent evaluated slice with automated engineering evidence and explicit dependencies | Current non-billing completion requires the in-scope blocked flows below, not merely a UI build |

## Seventeen deliverables

1. Repository/architecture assessment: `../TURING_WORKSPACE_PILOT.md` (scoped, not full audit).
2. Requirements/route map: this register and `PRODUCT_AND_GTM.md`.
3. Brand/tokens: `PRODUCT_AND_GTM.md`, `frontend/src/turing/workspace.css`.
4. Components: PublicSite, Workspace, History, Evidence, shared CSS/client/download helpers.
5. Public site: implemented technical-evaluation pages; no approved public launch.
6. Computational workspace: implemented adapter/UI; real-service acceptance outstanding.
7. Customer administration portal: **not operational**; owner contracts required.
8. Internal operations console: **not operational**; owner contracts required.
9. Provisioning/entitlements: **not operational**; intended contract and decision gates only.
10. Typed adapters/API: workspace client + OpenAPI operational code; seven unavailable boundaries typed explicitly.
11. Billing integration: **deferred by user; Hermitten excluded**. Not required for current acceptance.
12. Security/privacy: threat model/runbook and technical notices, **not approved legal policies**.
13. Testing: unit/client/browser suite and workflow; remote/live outcomes unverified.
14. Commercial direction: usage-based; pricing and financial administration on hold. No rates or capacity commitments.
15. Onboarding/GTM: `PRODUCT_AND_GTM.md`; actual customer lifecycle blocked.
16. Deployment/monitoring/recovery: `OPERATIONS_AND_QUALIFICATION.md`; no deployment performed.
17. Status/dependencies: this register and `CONTRACTS_AND_BILLING.md`.

## Mandatory end-to-end acceptance scenarios

| Scenario | Present evidence | Required completion evidence |
| --- | --- | --- |
| A Onboarding | None against actual customer/capacity services | Authorised operator + approved contract creates one allocation and verifies activation/audit; replay creates no duplicate |
| B Administration | No enterprise invite/role API connected | Real invite/accept/revoke, least-privilege roles, direct URL/API and cross-org denials |
| C Computation | Fake-adapter unit and explicitly mocked browser workflow; opt-in real smoke defined but skipped locally | Live issued subscription through real guardian, real native job, unchanged result/provenance/export and audit evidence |
| D Entitlement | Security admission/owner-scope regression only, NOT commercial entitlement | Expired/suspended/exhausted/out-of-contract request denied by authority before execution and audited |
| E Commercial reconciliation | **Deferred by user with billing** | Not a current acceptance gate; do not substitute job counts for billable usage |
| F Termination | Disconnect only clears local view, never customer service | Real suspension/termination revokes access, executes approved retention policy with audit; financial settlement deferred with billing |
| G Recovery | Same-key process-local submission recovery tested with fixtures | Actual partial provisioning/usage-ingestion failure, restart and replay resolve without duplicate resources/facts; financial checks deferred |

## Dependency register (role owners; no invented named assignees)

| Dependency | Accountable role | Evidence needed to unblock |
| --- | --- | --- |
| PR96 dependency and native environment | TURING maintainer | Reviewed base, locked real-engine smoke and shared-backend qualification |
| Identity and memberships | Enterprise identity / AL HARAS owner | IdP metadata, session semantics, permission matrix, test tenant and issued evaluation identity |
| Workspaces/projects | Customer workspace service owner | Entity contracts, persistence/retention and project/organisation access tests |
| Resource and provisioning | Capacity control-plane + commercial owners | Approved instance definition, inventory/quota semantics, versioned operation API and sandbox |
| Usage | Metering authority | Measurement definition/version, durable fact/outbox ownership, duplicates/corrections tests |
| Billing | Deferred by user | Usage-based future scope; no Hermitten access or financial integration required now |
| Durability | Theseus/deployment owner | Approved job/dedupe persistence, backup/restore and restart evidence |
| Operations | Service operations owner | Incident/support API, time-limited grants, real support/escalation channel |
| Legal/security/public launch | Authorised legal/security/product owners | Approved terms/privacy/data arrangements, controls review and explicit release authorisation |

Acceptance requires evidence attached to the relevant gate. A document, test
fixture, unavailable boundary, browser screenshot or passing build does not
convert a blocked service into an implemented feature.
