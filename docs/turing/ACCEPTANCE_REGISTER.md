# TURING requirements-to-evidence acceptance register

**Overall disposition: PARTIAL / production HOLD. This is not completion of the enterprise brief.**

Pinned baseline: `PhiEnterprise1/EuclidPhiEnterprise@4b75ace56712501f7d091e33d386df64ade9ba1b`.
This record supersedes earlier register statements that PR #98 is still draft and
that no administration/provisioning code exists. PR #97's enterprise service is
already present on main; source presence does not establish its live acceptance.
The working environment contains verified source subsets, **not a complete Git
checkout**. Review branch first implementation commit: `d015099c2c6dfa34d8e5185baf4774139374dab8`.
Subsequent integration-only tests and refreshed evidence supersede its initial
missing-runtime qualification failure without erasing that historical run.
Local candidate changes and test source hashes are retained in the
qualification handover. No whole-repository, remote-CI or production PASS is implied.

## Commercial authority

The user amendment supersedes the original brief's financial requirements.
Hermitten belongs to a separate avoided-cost data commercial model. It is not a
TURING/VQC dependency, acceptance gate or blocker. TURING/VQC's intended future
model is **contractually agreed usage-based billing**, currently **DEFERRED**.
No rate, chargeable unit, schedule, financial terms or provider is invented.
Current approved contract terms, membership, permissions and quotas remain gates.
Operational completion facts are not bills; legacy `verified_execution.v1` is not
an approved chargeable unit. Experimental receiver ports are withdrawn from
activation, not owner-approved APIs. Historical immutable records are not rewritten.

## PR reconciliation

| PR | Actual disposition observed | Dependency / current treatment |
|---|---|---|
| #96 | MERGED; historical head 754e46449c89f5f6741032469f364bb59d5c40b6 | Foundational package/SharedTuring work; preserve, do not reapply saved patches |
| #97 | MERGED; historical head a61a9dd1e34e23d3bcd2533089a001d50bc07c0a | Enterprise service reused; correct its production billing assumptions rather than rebuild |
| #98 | CLOSED UNMERGED | Originally based on #96 feature branch; do not reopen/rebuild its historical stack. Main contains pilot docs/UI; distinguish content reuse from a #98 merge |
| #99 | MERGED; historical head 89120167934284c90bbee7c2f93dc9069b5843d3 | Subsequent package work retained; no remaining merge ordering among these closed PRs |

All open PRs query returned none at reconciliation. Main includes later work
through PR #138; earlier PR descriptions and closeout ledgers are historical
claims, not fresh qualification. Remote check-run reads returned 403. No CI
success, conflict-free full checkout, installed-consumer parity or deployment is claimed.

## Evidence categories (overlapping tests, not additive totals)

| Category | Actually executed / disposition |
|---|---|
| Unit tests | Service baseline 77 passed; candidate 93 passed, zero failures/skips, one Starlette/httpx deprecation warning |
| Integration | **3 passed**, zero failures/skips: installed worker, real local API/queue/result/revocation, canonical SharedTuring shared custody and durable restart replay. Cryptographic test identity only |
| Real-runtime end-to-end | Local in-process HTTP API through real isolated native subprocess and retained result: passed. Live enterprise SSO, network ingress and complete production organism acceptance NOT EXECUTED |
| Security / tenant isolation | Local real SQLite/signatures/JWT fixtures; role/project/revocation negatives and denial-audit failure tests pass. Not deployed isolation/penetration acceptance |
| Frontend fixtures | 10 desktop/mobile views; 12 new interaction groups for history filters/pages, confirmation, unchanged export and tenant-switch safety; no real IdP/execution |
| Accessibility | 2 automated axe WCAG-tagged fixture scans, zero violations. Not manual screen-reader/zoom or complete WCAG certification |
| Failure / recovery | Existing local cancellation/quarantine/idempotency/backup/restore and new audit-failure tests pass; no target-host recovery or rollback drill |
| VQC / research | Unchanged exact-source isolated stabilizer measurement tests: 11 passed, including independent NumPy dense comparisons. Research gating: 11 passed, 4 subtests; no research claim thereby proven/refuted. Full recovered VQC test directory: **556 passed + 111 subtests**, zero failures/errors/skips; includes actual local custody/replay. Hardware qualification and full repository/installed-consumer parity NOT EXECUTED |
| Deployment / operations | Service wheel+sdist build and separate wheel test environment completed. Docker absent; host build/alerts/restore/rollbacks, named on-call and independent release approval outstanding |

The stabilizer harness directly loads the real owner module to avoid unrelated
package initialization; it is explicitly **not** installed-package integration.
AL HARAS signature tests likewise load its actual entitlements owner module;
full Guardian composition is not certified by those tests. Generated test keys,
IdP peers, runtime responses and browser API traffic are labelled fixtures.
Skipped/untested results are never passes or refuted claims.

## Exact access / authority gates

1. **Full qualification source and CI:** Git remote authentication is unavailable
   (`could not read Username`, terminal prompts disabled); GitHub connector can
   read scoped contents, but cannot read check runs (403). Maintainer must provide
   an authorized complete checkout/approved archive and check-run read access or
   retained authoritative CI results. Do not weaken tests or branch protections.
2. **Enterprise identity and lifecycle:** identity owner must supply an approved
   test tenant, registered client/callback/audiences, safe credentials, invitation
   interface and revocation/offboarding policy. Existing-subject role management
   does not establish invitation or IdP deprovisioning.
3. **Production execution/custody and installed consumers:** local VQC/Kellogg,
   native service execution and canonical SharedTuring/THESEUS/OVID restart replay
   now pass; missing owner source was recovered, not replaced with a mock. The
   remaining gate is the approved full deployed composition, installed-consumer
   parity and tenant/creator mapping through real authority. The bounded service's
   local report file is not itself the shared fabric; acceptance must identify
   which approved composition serves the release, then run its complete voyage.
4. **Salamander actuation:** current `aethel/enterprise/production_organism.py`
   already injects the shared TURING specialist and forwards an optional
   `subscription_token_provider` and tenant into EUCLID. Do not rebuild that
   integration or claim it is absent. Approved Guardian/secret-provider binding,
   least-privilege tenant/actor scopes and an authorized non-actuating validation
   target are still needed; no live action or production credential was minted.
5. **Deployment / operational authority:** deployment owner must supply a permitted
   target, secret manager, independently signed source-bound evidence, approved
   service objectives/retention/residency and named operational/escalation owners;
   run container isolation, load, alert, custody+DB restore and rollback drills.
6. **Product / legal acceptance:** accountable owners must approve actual contract
   semantics/resource meaning, brand/legal/support/enquiry channels and manual
   accessibility acceptance. No future billing or Hermitten access is requested.

These are qualification/authority gates, not assertions that every remaining
implementation task is externally blocked. The 47 requirements below remain
PARTIAL unless explicitly financially DEFERRED; unverified implementation and
full-host inspection gaps must not be relabelled complete or purely external.

## Matrix index

Machine-readable equivalent: `requirements-evidence.json`. Every record retains
authoritative wording, source, implementation, real dependency, acceptance,
observed evidence, owner, status and release impact. Wording in original financial
sections is historical and superseded by the explicit amendment above. Section-wide
PARTIAL is deliberately conservative and never a blanket PASS for all its bullets.

| ID | Requirement | Disposition | Release impact |
|---|---|---|---|
| S01 | Product vision and positioning | PARTIAL | Mandatory applicable acceptance open |
| S02 | Begin with repository reconnaissance | PARTIAL | Mandatory applicable acceptance open |
| S03 | Define the product architecture | PARTIAL | Mandatory applicable acceptance open |
| S04 | Frontend technology and engineering standards | PARTIAL | Mandatory applicable acceptance open |
| S05 | Brand identity and visual system | PARTIAL | Mandatory applicable acceptance open |
| S06 | Product information architecture | PARTIAL | Mandatory applicable acceptance open |
| S07 | Public website experience | PARTIAL | Mandatory applicable acceptance open |
| S08 | Computational intelligence workspace | PARTIAL | Mandatory applicable acceptance open |
| S09 | Enterprise organisation and user administration | PARTIAL | Mandatory applicable acceptance open |
| S10 | Provisioning and capacity management | PARTIAL | Mandatory applicable acceptance open |
| S11 | Commercial model and pricing administration | PARTIAL | Mandatory applicable acceptance open |
| S12 | Metering and Hermitten billing integration | DEFERRED | Financial scope deferred, not a current blocker |
| S13 | Backend contracts and integration boundaries | PARTIAL | Mandatory applicable acceptance open |
| S14 | Security, privacy, and governance | PARTIAL | Mandatory applicable acceptance open |
| S15 | UX completeness and interaction quality | PARTIAL | Mandatory applicable acceptance open |
| S16 | Analytics and product instrumentation | PARTIAL | Mandatory applicable acceptance open |
| S17 | Operational administration and support | PARTIAL | Mandatory applicable acceptance open |
| S18 | Go-to-market readiness | PARTIAL | Mandatory applicable acceptance open |
| S19 | Testing and release acceptance | PARTIAL | Mandatory applicable acceptance open |
| S20 | Design and implementation deliverables | PARTIAL | Mandatory applicable acceptance open |
| S21 | Execution plan | PARTIAL | Mandatory applicable acceptance open |
| S22 | Rules of engagement for the coding agent | PARTIAL | Mandatory applicable acceptance open |
| S23 | Definition of done | PARTIAL | Mandatory applicable acceptance open |
| D01 | Repository and architecture assessment. | PARTIAL | Mandatory applicable acceptance open |
| D02 | Product requirements and route map. | PARTIAL | Mandatory applicable acceptance open |
| D03 | Brand direction and design-token specification. | PARTIAL | Mandatory applicable acceptance open |
| D04 | Reusable component system. | PARTIAL | Mandatory applicable acceptance open |
| D05 | Public product website. | PARTIAL | Mandatory applicable acceptance open |
| D06 | Authenticated computational workspace. | PARTIAL | Mandatory applicable acceptance open |
| D07 | Customer administration portal. | PARTIAL | Mandatory applicable acceptance open |
| D08 | Internal service operations console. | PARTIAL | Mandatory applicable acceptance open |
| D09 | Provisioning and entitlement workflows. | PARTIAL | Mandatory applicable acceptance open |
| D10 | Typed frontend service adapters and documented API contracts. | PARTIAL | Mandatory applicable acceptance open |
| D11 | Hermitten integration assessment and implementation where feasible. | DEFERRED | Financial scope deferred, not a current blocker |
| D12 | Security and privacy assessment. | PARTIAL | Mandatory applicable acceptance open |
| D13 | Testing strategy and automated tests. | PARTIAL | Mandatory applicable acceptance open |
| D14 | Commercial model and pricing hypotheses. | PARTIAL | Mandatory applicable acceptance open |
| D15 | Enterprise onboarding and go-to-market plan. | PARTIAL | Mandatory applicable acceptance open |
| D16 | Deployment, monitoring, and recovery documentation. | PARTIAL | Mandatory applicable acceptance open |
| D17 | Implementation status and outstanding dependency register. | PARTIAL | Mandatory applicable acceptance open |
| SC-A | Enterprise onboarding | PARTIAL | Mandatory applicable acceptance open |
| SC-B | Customer administration | PARTIAL | Mandatory applicable acceptance open |
| SC-C | Computational workflow | PARTIAL | Mandatory applicable acceptance open |
| SC-D | Entitlement enforcement | PARTIAL | Mandatory applicable acceptance open |
| SC-E | Commercial reconciliation | DEFERRED | Financial scope deferred, not a current blocker |
| SC-F | Lifecycle termination | PARTIAL | Mandatory applicable acceptance open |
| SC-G | Failure recovery | PARTIAL | Mandatory applicable acceptance open |

## Requirement records — authoritative wording and evidence

### S01 — Product vision and positioning

**Authority:** MASTER_BRIEF.md section 1; user billing amendment supersedes original financial requirements

**Authoritative wording (verbatim):**

```text
# 1\. Product vision and positioning

TURING is a computational intelligence capability delivered as a service.

It is not a software-licensing business, a generic SaaS subscription, a chatbot, a thin API wrapper, or a conventional AI dashboard.

The product exposes mathematically grounded computational capabilities through a governed, typed, reproducible, auditable, and commercially sustainable service.

The underlying mathematical substrate is hardware-agnostic. Do not introduce physical-hardware requirements, hardware-specific onboarding, simulated hardware workflows, or hardware-oriented marketing into the product.

Preserve the existing TURING engine, mathematical model, package identity, and established implementation boundaries. The frontend and commercial platform must expose genuine capabilities rather than redefine the computational engine.

The customer purchases access to capability and outcomes under an agreed commercial arrangement. The supporting platform provides identity, authorisation, workspaces, service entitlements, provisioning, execution tracking, provenance, usage accounting, support, and commercial administration.

## Strategic design benchmarks

Draw inspiration from the following disciplines without copying proprietary designs, logos, visual assets, or distinctive trade dress:

- **Apple:** clarity, restraint, typographic hierarchy, polished details, and an intuitive first-use experience.
- **IBM:** technical credibility, disciplined information architecture, enterprise reliability, accessibility, and engineering rigour.
- **Google:** interaction consistency, discoverability, coherent component behaviour, and low-friction workflows.
- **McKinsey:** executive communication, structured problem-solving, decision support, and concise presentation of consequential information.
- **Gartner:** analytical frameworks, evidence provenance, transparent assumptions, decision criteria, and clear differentiation between facts and estimates.
- **Pentagram:** a distinctive, ownable identity, editorial sophistication, conceptual clarity, and consistent visual language.

The result must be a coherent TURING identity, not six unrelated visual styles combined into one interface.

Never claim affiliation with or endorsement by these organisations.
```

**Implementation:** `docs/turing/PRODUCT_AND_GTM.md; frontend/src/turing/PublicSite.tsx`

**Runtime dependencies:** Approved positioning and customer validation; no live integration implied

**Acceptance test:** Product/brand signoff and customer review; no fresh customer evidence

**Current evidence:** Source/document inventory only for this scope; no current owner/live acceptance.

**Owner / external dependency:** Product/commercial and brand owners

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### S02 — Begin with repository reconnaissance

**Authority:** MASTER_BRIEF.md section 2; user billing amendment supersedes original financial requirements

**Authoritative wording (verbatim):**

```text
# 2\. Begin with repository reconnaissance

Before changing code, inspect the repository and report internally on:

1. The current application architecture, package manager, framework versions, scripts, and build configuration.
2. The existing TURING package, `TuringPipeline` entry point, typed contracts, validation, jobs, and provenance interfaces.
3. The current API boundaries, computational execution model, result structures, errors, and available metadata.
4. Existing identity, persistence, billing, user administration, and service provisioning implementations, if any.
5. The Hermitten billing system: its actual interfaces, data model, integration constraints, and existing reusable capabilities. Do not assume access to it or invent its API.
6. Existing tests, CI workflows, release procedures, dependency constraints, and architectural decisions.
7. Existing UI components, design assets, typography, routing, documentation, and accessibility support.

Inspect PR #96 and its current state if repository access permits. Respect ongoing agent work and existing changes. Do not overwrite uncommitted work, duplicate completed functionality, or reopen settled architectural decisions without evidence of a problem.

Distinguish confirmed capabilities from proposed functionality. Maintain an implementation inventory showing what exists, what is incomplete, what requires a new backend contract, and what cannot safely be implemented yet.

**Do not start by replacing the existing stack or rebuilding the engine.** Preserve compatible technology and introduce new dependencies only when they solve a defined problem.
```

**Implementation:** `docs/turing/MASTER_BRIEF.md; current GitHub main/PR metadata; source inventories`

**Runtime dependencies:** Full authenticated checkout and accessible checks

**Acceptance test:** Fetch main and all PR dependencies; compare exact source trees; full audit not achieved

**Current evidence:** Source/document inventory only for this scope; no current owner/live acceptance.

**Owner / external dependency:** Repository maintainer; CI owner

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### S03 — Define the product architecture

**Authority:** MASTER_BRIEF.md section 3; user billing amendment supersedes original financial requirements

**Authoritative wording (verbatim):**

```text
# 3\. Define the product architecture

Design a coherent platform around the following conceptual layers.

## A. Computational capability layer

The existing TURING computational engine remains the authority for its mathematical and computational behaviour.

Expose it through documented, typed service boundaries. Preserve mathematical invariants, validation rules, result semantics, and execution provenance.

Do not implement a second computational engine in the browser. The frontend must not silently substitute fabricated calculations, random results, or illustrative values for actual computation.

## B. Service control plane

Responsible for:

- Customer and organisation lifecycle.
- Customer workspaces and projects.
- Instance or capacity provisioning.
- Service entitlements and policy enforcement.
- User and role administration.
- Execution scheduling and job lifecycle, where supported.
- Usage metering and provenance.
- Operational status, audit events, and support workflows.

The control plane should coordinate existing services rather than duplicate their responsibilities.

## C. Commercial platform

Responsible for:

- Contracts and commercial commitments.
- Service tiers and negotiated pricing.
- Reserved capacity and usage allowances.
- Billable usage records.
- Billing integration, invoicing, adjustments, and reconciliation.
- Customer usage reports and expenditure controls.

Assess and reuse the existing Hermitten billing system wherever its real capabilities fit. Do not create a parallel billing ledger unnecessarily.

Keep technical execution state, entitlement state, and financial records logically separate, with traceable integration between them.

## D. User experience layer

Build three connected experiences:

1. Internal TURING operations console.
2. Enterprise customer administration portal.
3. Computational intelligence workspace for analysts, researchers, and business users.

Use shared design primitives and consistent identity and authorisation semantics, while separating privileged administrative functions from ordinary customer access.
```

**Implementation:** `euclid/runtime.py; al_haras/entitlements.py; services/turing-enterprise/src/hyba_turing_service/{main,api,enterprise,runtime}.py`

**Runtime dependencies:** Installed canonical package closure and approved service composition

**Acceptance test:** Trace authority through default startup, service adapter, custody and installed consumers

**Current evidence:** Local service suite: 93 passed, 0 failed/skipped (one deprecation warning). Real SQLite/cryptography; IdP and unit-test runtime peers are doubles; actual local integrations are listed separately. Not live acceptance. Recovered pinned owner sources; installed hyba-turing-vqc 1.0.0 and hyba-kellogg-tensor 1.0.0. Full recovered VQC test directory: 556 passed plus 111 subtests, 0 failed/errors/skipped (134.85s). No VQC implementation patch reapplied. Three actual local integrations passed (3.01s): installed subprocess runtime; signed TEST-identity API -> SQLite queue -> default worker -> certificate/witness/report, same-key recovery and revocation; canonical SharedTuring -> shared THESEUS/OVID -> verified lineage -> durable lifecycle restart replay. Real local owner code, not enterprise SSO/approved production composition. Current aethel/enterprise/production_organism.py already binds the shared TURING specialist and forwards subscription_token_provider with tenant_id; preserve that implementation. Source trace is not approved credential deployment.

**Owner / external dependency:** Platform, identity and custody owners

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### S04 — Frontend technology and engineering standards

**Authority:** MASTER_BRIEF.md section 4; user billing amendment supersedes original financial requirements

**Authoritative wording (verbatim):**

```text
# 4\. Frontend technology and engineering standards

Use **Next.js with TypeScript** as the primary frontend stack, subject to the repository reconnaissance confirming compatibility with the existing project.

Preferred implementation principles:

- Next.js App Router where appropriate.
- Strict TypeScript with no unjustified `any` usage.
- Server Components by default; Client Components only where interactivity requires them.
- Typed server-side service adapters and API contracts.
- Zod or an equivalent established schema-validation library where runtime validation is needed.
- React Hook Form or an equivalent mature form solution for complex forms, if justified.
- A consistent component system built on accessible primitives.
- Tailwind CSS or the existing compatible styling system, avoiding unnecessary competing styling frameworks.
- OpenAPI-generated clients where a suitable API specification exists.
- Structured error handling, explicit loading states, and predictable data fetching.
- Unit, integration, accessibility, and end-to-end testing appropriate to the application.
- ESLint, formatting, type checking, dependency auditing, and production-build verification.

Do not introduce a library simply because it is fashionable. Verify compatibility with the actual repository, current versions, licensing, maintenance status, and project conventions.

Avoid:

- Untyped API responses.
- Business logic embedded in presentation components.
- Excessive global state.
- Large monolithic client components.
- Client-side secrets or privileged operations.
- Duplicated validation rules across unrelated layers.
- Dead routes, decorative controls, placeholder links, and nonfunctional forms.
- Arbitrary abstractions that make a small codebase harder to maintain.
```

**Implementation:** `frontend/src/turing/{client.ts,integrations.ts}; services/turing-enterprise/pyproject.toml`

**Runtime dependencies:** Locked host toolchain and complete checkout

**Acceptance test:** Locked lint/typecheck/build/dependency scans plus installed consumer regression

**Current evidence:** Source/document inventory only for this scope; no current owner/live acceptance.

**Owner / external dependency:** Frontend/release maintainers

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### S05 — Brand identity and visual system

**Authority:** MASTER_BRIEF.md section 5; user billing amendment supersedes original financial requirements

**Authoritative wording (verbatim):**

```text
# 5\. Brand identity and visual system

Create a distinctive visual identity for TURING before styling individual screens.

## Brand characteristics

The visual language should communicate:

- Intellectual depth.
- Mathematical precision.
- Institutional trust.
- Scientific credibility.
- Calm authority.
- Commercial sophistication.
- Transparency and reproducibility.
- Long-term reliability.

Avoid generic purple AI gradients, glowing neural networks, robot imagery, gratuitous particle effects, faux scientific visualisations, and stereotypical quantum imagery.

Do not use decorative complexity to compensate for weak information architecture.

## Typography

Develop a clear typographic hierarchy covering:

- Product wordmark and primary headlines.
- Executive page titles.
- Section headings.
- Body text.
- Data tables and numerical values.
- Code, identifiers, and provenance metadata.
- Helper text, timestamps, and system status.

Choose fonts with suitable licensing, readability, numerals, and broad character coverage. Use a restrained combination of type families and a consistent scale.

## Colour

Define design tokens for:

- Brand identity.
- Primary and secondary surfaces.
- Text and muted text.
- Borders and dividers.
- Primary and secondary actions.
- Success, warning, error, and informational states.
- Focus indicators and disabled states.
- Data visualisation.

Meet WCAG 2.2 AA contrast requirements wherever applicable. Status must never be conveyed by colour alone.

## Layout and interaction

Use generous but efficient spacing, deliberate alignment, readable content widths, consistent navigation, responsive layouts, and a disciplined grid.

Motion should explain state transitions and preserve spatial understanding. Respect reduced-motion preferences.

Define light and dark themes only if both can be implemented and tested consistently. Do not add theme controls as decoration.

Build a reusable design system with documented tokens, components, variants, interaction states, and usage guidelines.
```

**Implementation:** `frontend/src/turing/{workspace.css,PublicSite.tsx}; docs/turing/PRODUCT_AND_GTM.md`

**Runtime dependencies:** Brand approval; supported browsers and assistive technologies

**Acceptance test:** Design review; manual keyboard/screen-reader/zoom and automated accessibility

**Current evidence:** Source/document inventory only for this scope; no current owner/live acceptance.

**Owner / external dependency:** Brand and product owners

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### S06 — Product information architecture

**Authority:** MASTER_BRIEF.md section 6; user billing amendment supersedes original financial requirements

**Authoritative wording (verbatim):**

```text
# 6\. Product information architecture

Design and implement the following route groups, adapting names and scope to the existing application.

## Public product website

- `/` — positioning, product value, capability overview, trust, and primary calls to action.
- `/capabilities` — genuine computational capabilities and supported use cases.
- `/how-it-works` — mathematical and computational model, service workflow, and reproducibility.
- `/enterprise` — enterprise governance, deployment model, access control, and commercial engagement.
- `/documentation` — developer and user documentation.
- `/security` — accurate security architecture and controls, without unsupported certifications.
- `/research` — methodology, publications, citations, and validated research material.
- `/contact` — sales, partnership, and technical enquiries.
- `/legal/privacy`, `/legal/terms`, and any other applicable legal pages.

Do not publish claims about performance, customer adoption, certifications, research priority, or market leadership without evidence.

## Authenticated application

- `/app` — personal or organisation workspace overview.
- `/app/workspaces` — workspace management.
- `/app/projects` — computational projects.
- `/app/jobs` — execution history and status.
- `/app/jobs/[id]` — job details, results, and provenance.
- `/app/results` — results and analytical reports.
- `/app/usage` — usage, allowances, and capacity visibility.
- `/app/settings` — user preferences and account settings.
- `/app/developers` — API credentials and integration documentation, if supported.

## Customer administration

- `/org/[orgId]/overview`
- `/org/[orgId]/users`
- `/org/[orgId]/teams`
- `/org/[orgId]/roles`
- `/org/[orgId]/projects`
- `/org/[orgId]/capacity`
- `/org/[orgId]/instances`
- `/org/[orgId]/usage`
- `/org/[orgId]/billing`
- `/org/[orgId]/audit`
- `/org/[orgId]/settings`

## Internal operations

- `/ops/overview`
- `/ops/customers`
- `/ops/customers/[customerId]`
- `/ops/provisioning`
- `/ops/instances`
- `/ops/entitlements`
- `/ops/contracts`
- `/ops/metering`
- `/ops/billing-reconciliation`
- `/ops/audit`
- `/ops/incidents`
- `/ops/system-health`

These are proposed route contracts, not evidence that backend functionality already exists. Implement only routes whose capabilities can be supported safely, and clearly distinguish unavailable capabilities from empty data.
```

**Implementation:** `frontend/src/turing/{routes.ts,TuringApp.tsx}; services/turing-enterprise/src/hyba_turing_service/static/portal.js`

**Runtime dependencies:** Approved IdP/customer/contract and real runtime

**Acceptance test:** Route all real surfaces with permitted backend state; no simulated customer success

**Current evidence:** Local service suite: 93 passed, 0 failed/skipped (one deprecation warning). Real SQLite/cryptography; IdP and unit-test runtime peers are doubles; actual local integrations are listed separately. Not live acceptance.

**Owner / external dependency:** Product/platform owners

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### S07 — Public website experience

**Authority:** MASTER_BRIEF.md section 7; user billing amendment supersedes original financial requirements

**Authoritative wording (verbatim):**

```text
# 7\. Public website experience

The public website must communicate what TURING does, who benefits, what makes its computational approach distinctive, and how an enterprise can engage.

## Homepage

Create a polished, editorially strong homepage with:

1. A distinctive brand-led hero and concise positioning statement.
2. A clear explanation of computational intelligence as a service.
3. Genuine examples of the types of problems the platform can address.
4. An explanation of the mathematical foundation and computational workflow.
5. A transparent account of provenance, validation, and reproducibility.
6. Enterprise governance and service-delivery information.
7. A credible path for technical evaluation and commercial engagement.
8. Research, documentation, and relevant evidence.
9. A restrained, professional footer containing appropriate company and legal links.

Use strong copy and purposeful visual storytelling. Prefer meaningful diagrams, carefully typeset mathematics, and genuine product screenshots over generic stock imagery.

Do not present the product as a chatbot or imply capabilities not implemented.

## Product storytelling

Explain the relationship between mathematical inputs, computational execution, validation, and results.

Show how results can be inspected, traced, reproduced where guaranteed, and evaluated against relevant criteria.

Separate established functionality, current limitations, planned functionality, and research hypotheses.

Every call to action must lead somewhere meaningful.
```

**Implementation:** `frontend/src/turing/{PublicSite.tsx,productContent.ts}; docs/turing/PRODUCT_AND_GTM.md`

**Runtime dependencies:** Approved policies, enquiry destination, references and publication rights

**Acceptance test:** Public journey, approved contact delivery, legal/privacy and claim review

**Current evidence:** Source/document inventory only for this scope; no current owner/live acceptance.

**Owner / external dependency:** Product, legal, privacy and support owners

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### S08 — Computational intelligence workspace

**Authority:** MASTER_BRIEF.md section 8; user billing amendment supersedes original financial requirements

**Authoritative wording (verbatim):**

```text
# 8\. Computational intelligence workspace

Build the primary working environment for analysts, researchers, and business users.

## Workspace overview

Show:

- Recent projects and computational jobs.
- Current job states.
- Available entitlements and capacity.
- Recent results.
- Relevant service notifications.
- Quick access to start a new computation.
- Useful activity and provenance summaries.

Every metric must come from an authoritative data source or be explicitly labelled as illustrative during development.

## Project management

Support, where backed by the service contract:

- Project creation, editing, and archiving.
- Project descriptions and metadata.
- Team access and project-level permissions.
- Associated jobs, results, and reports.
- Search, filtering, sorting, and pagination.
- Project activity history.

## Job submission

Create an accessible, guided workflow that:

1. Explains the computational task.
2. Collects validated inputs.
3. Presents relevant domain restrictions and constraints.
4. Shows the effective configuration before submission.
5. Displays estimated resource or usage implications only when supported by actual estimation logic.
6. Requires confirmation for consequential or potentially billable actions.
7. Submits work through the documented API.
8. Displays the resulting job identifier and status.

Never allow the UI to imply that an invalid input is valid merely because a form accepted it.

## Job lifecycle

Represent only the states defined by the backend contract. Where appropriate, these might include:

- Draft.
- Submitted.
- Queued.
- Running.
- Completed.
- Failed.
- Cancelled.

Do not invent transitions or treat a timeout as proof that a job failed to execute.

Show timestamps, execution identifiers, meaningful error messages, retry eligibility, and provenance where available.

## Results experience

Present results with:

- Clear executive summaries.
- Mathematical and numerical outputs.
- Units, precision, and tolerances where applicable.
- Input and configuration summaries.
- Validation status and limitations.
- Execution provenance.
- Download or export options where supported.
- Reproducibility information.
- Appropriate charts and tables.

Charts must represent actual data and identify axes, units, assumptions, and missing values.

Never manufacture a favourable result to make a demonstration appear successful.
```

**Implementation:** `frontend/src/turing/{Workspace.tsx,History.tsx,Evidence.tsx}; services/turing-enterprise/src/hyba_turing_service/{api.py,static/portal.js,runtime.py}`

**Runtime dependencies:** Actual canonical installed runtime and authenticated target

**Acceptance test:** Real execution through result/provenance; search/filter/pages, cancellation and same-key recovery; fixtures are insufficient

**Current evidence:** Local service suite: 93 passed, 0 failed/skipped (one deprecation warning). Real SQLite/cryptography; IdP and unit-test runtime peers are doubles; actual local integrations are listed separately. Not live acceptance. Fixture history/filter/cursor/cancel/export/stale-tenant workflows passed. Three actual local integrations passed (3.01s): installed subprocess runtime; signed TEST-identity API -> SQLite queue -> default worker -> certificate/witness/report, same-key recovery and revocation; canonical SharedTuring -> shared THESEUS/OVID -> verified lineage -> durable lifecycle restart replay. Real local owner code, not enterprise SSO/approved production composition. Recovered pinned owner sources; installed hyba-turing-vqc 1.0.0 and hyba-kellogg-tensor 1.0.0. Full recovered VQC test directory: 556 passed plus 111 subtests, 0 failed/errors/skipped (134.85s). No VQC implementation patch reapplied. Three actual local integrations passed (3.01s): installed subprocess runtime; signed TEST-identity API -> SQLite queue -> default worker -> certificate/witness/report, same-key recovery and revocation; canonical SharedTuring -> shared THESEUS/OVID -> verified lineage -> durable lifecycle restart replay. Real local owner code, not enterprise SSO/approved production composition.

**Owner / external dependency:** Execution/custody and frontend owners

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### S09 — Enterprise organisation and user administration

**Authority:** MASTER_BRIEF.md section 9; user billing amendment supersedes original financial requirements

**Authoritative wording (verbatim):**

```text
# 9\. Enterprise organisation and user administration

Implement a coherent organisation model supporting enterprise customers with different sizes, departments, projects, and access requirements.

## Core entities

Establish or map existing equivalents for:

- Organisation.
- Customer account.
- User.
- Organisation membership.
- Team.
- Role.
- Workspace.
- Project.
- Service contract.
- Entitlement.
- Capacity allocation.
- Instance or execution resource.
- Job.
- Result.
- Usage event.
- Invoice reference.
- Audit event.

Avoid creating duplicate entities when existing models already cover these concepts.

Define ownership, lifecycle, relationships, identifiers, retention, and authorisation boundaries.

## Roles and permissions

Support a least-privilege model with clearly separated responsibilities. Potential roles include:

- Internal platform operator.
- Internal service administrator.
- Customer organisation administrator.
- Billing administrator.
- Project administrator.
- Analyst or researcher.
- Read-only reviewer.
- Support operator with explicitly constrained access.

Final roles and permissions must reflect actual business requirements.

Implement permission checks on the server. Hiding a menu item is not authorisation.

Test organisation isolation, cross-organisation resource access, direct URL access, and API-level permission enforcement.

## Enterprise identity

Design integration boundaries for enterprise identity providers and SSO, including OIDC or SAML where required and supported.

Account for MFA, session expiry, account recovery, invitation workflows, domain verification where appropriate, and offboarding.

Do not implement a home-grown authentication protocol.

Never log credentials, expose secret values after creation, or store privileged tokens in browser-accessible storage.
```

**Implementation:** `services/turing-enterprise/src/hyba_turing_service/{identity,sessions,enterprise,api}.py`

**Runtime dependencies:** Approved IdP tenant/client, invitation/offboarding interface and revocation policy

**Acceptance test:** Actual SSO, invite, assign/revoke, expiry, current role and direct cross-tenant API negatives

**Current evidence:** Local service suite: 93 passed, 0 failed/skipped (one deprecation warning). Real SQLite/cryptography; IdP and unit-test runtime peers are doubles; actual local integrations are listed separately. Not live acceptance.

**Owner / external dependency:** Identity and customer administrators

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### S10 — Provisioning and capacity management

**Authority:** MASTER_BRIEF.md section 10; user billing amendment supersedes original financial requirements

**Authoritative wording (verbatim):**

```text
# 10\. Provisioning and capacity management

Build the control-plane interface for creating and maintaining customer service entitlements.

## Define what an instance means

Before implementing commercial commitments, determine whether an instance represents a persistent runtime, a logical service allocation, a concurrency slot, a workspace, or another precisely defined resource.

Document its lifecycle, limits, isolation requirements, cost implications, and relationship to computational throughput.

Do not conflate the number of instances with guaranteed throughput or completed computations.

## Provisioning workflow

Provide a guided internal workflow to:

1. Select or create a customer.
2. Select an approved commercial contract.
3. Choose an authorised service configuration.
4. Allocate the agreed capacity.
5. Configure access policies and limits.
6. Validate available capacity and policy compliance.
7. Review the proposed change.
8. Submit the provisioning request.
9. Track progress and failures.
10. Verify the resulting state.
11. Record the audit event and notify the appropriate parties.

The backend must be authoritative for allocation and activation.

Provisioning must be idempotent and recoverable. Handle partial failures without creating duplicate allocations or unintended charges.

## Illustrative customer scenarios

Design the system to support different negotiated enterprise allocations, such as:

- A large financial institution with 100 provisioned instances.
- A professional-services firm with 10 provisioned instances.
- A smaller research customer with a different contractual arrangement.

These are illustrative planning scenarios, not existing customers, confirmed capacity, or pricing commitments.

The interface must support different entitlements and negotiated terms without hardcoding specific customer names or quantities.

## Capacity visibility

Where the underlying service supports it, distinguish:

- Contracted capacity.
- Provisioned capacity.
- Available capacity.
- Active capacity.
- Consumed usage.
- Reserved but unused capacity.
- Capacity awaiting provisioning.
- Capacity unavailable because of a service restriction.

Do not equate instance counts with computational usage unless that relationship is explicitly defined.

## Lifecycle operations

Support authorised workflows for:

- Provisioning.
- Activation.
- Resizing or reallocation.
- Suspension.
- Reactivation.
- Renewal.
- Decommissioning.
- Customer termination.

Use confirmation screens for destructive or commercially consequential operations. Provide previews, reason fields where appropriate, and audit records.
```

**Implementation:** `services/turing-enterprise/src/hyba_turing_service/{control,enterprise,supervisor,api}.py`

**Runtime dependencies:** Approved logical-slot meaning and contract limits; target resource sizing

**Acceptance test:** Transactional provisioning/resize/activation/revocation, contention, duplicate/restart/partial failure on authoritative target

**Current evidence:** Local service suite: 93 passed, 0 failed/skipped (one deprecation warning). Real SQLite/cryptography; IdP and unit-test runtime peers are doubles; actual local integrations are listed separately. Not live acceptance.

**Owner / external dependency:** Capacity and contract authority

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### S11 — Commercial model and pricing administration

**Authority:** MASTER_BRIEF.md section 11; user billing amendment supersedes original financial requirements

**Authoritative wording (verbatim):**

```text
# 11\. Commercial model and pricing administration

Design the system around selling computational capability rather than defaulting to software seats.

Support a flexible commercial model combining relevant elements of:

- Recurring enterprise service commitments.
- Reserved capacity.
- Included usage allowances.
- Metered consumption.
- Negotiated pricing.
- Premium support or service commitments.
- Bespoke computational engagements.

Do not assume every customer uses every pricing component.

## Commercial administration

Provide internal interfaces for managing, subject to actual billing-system capabilities:

- Customer contracts and effective dates.
- Service entitlements and contractual limits.
- Pricing schedules and version history.
- Capacity commitments.
- Included usage and overage policies.
- Discounts and authorised adjustments.
- Renewal dates.
- Billing account references.
- Commercial exceptions and approval history.

Keep pricing configuration separate from execution logic.

Changes to pricing must not retroactively alter previously rated usage without an explicit, audited correction process.

## Pricing strategy

Develop a commercial hypothesis rather than inventing arbitrary prices.

Assess:

- Customer willingness to pay.
- Cost to serve.
- Capacity reservation costs.
- Actual computational resource consumption.
- Variability in job complexity.
- Value delivered to customers.
- Support and governance costs.
- Contract duration and revenue predictability.
- Gross margin and sensitivity to utilisation.

Distinguish value-based pricing from cost-based price floors. Identify assumptions that require pilot data.

Do not introduce per-seat licensing as the default commercial model merely because the UI contains users.
```

**Implementation:** `services/turing-enterprise/src/hyba_turing_service/{commercial,enterprise,release}.py; docs/turing/CONTRACTS_AND_BILLING.md`

**Runtime dependencies:** Current approved non-financial terms and effective entitlements; future financial scope deferred

**Acceptance test:** Exact-term approval and quotas remain mandatory; no rates/provider/invoices accepted

**Current evidence:** Local service suite: 93 passed, 0 failed/skipped (one deprecation warning). Real SQLite/cryptography; IdP and unit-test runtime peers are doubles; actual local integrations are listed separately. Not live acceptance.

**Owner / external dependency:** Commercial approver and authorization owner

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### S12 — Metering and Hermitten billing integration

**Authority:** MASTER_BRIEF.md section 12; user billing amendment supersedes original financial requirements

**Authoritative wording (verbatim):**

```text
# 12\. Metering and Hermitten billing integration

Investigate the actual Hermitten implementation before designing the integration.

Identify existing billing capabilities and extend them where appropriate. Reuse customer records, invoice mechanisms, pricing logic, or payment workflows only when their semantics are compatible.

## Usage event contract

Design an immutable or otherwise auditable usage-event model containing, as appropriate:

- Unique event identifier.
- Organisation and billing-account identifiers.
- Project and job references.
- Event type and timestamp.
- Measurement unit and quantity.
- Relevant service or capability identifier.
- Applicable entitlement or contract reference.
- Idempotency key.
- Provenance references.
- Rating status and reconciliation metadata.

Avoid placing confidential inputs or sensitive computational outputs into billing events unless strictly necessary.

## Billing workflow

Separate these steps:

1. Technical execution generates authoritative usage facts.
2. Metering validates and records usage.
3. Commercial rating applies the applicable contractual rules.
4. Billing receives rated, reconcilable records.
5. Invoices or statements are produced by the appropriate system.
6. Reconciliation detects omissions, duplicates, and discrepancies.
7. Corrections create traceable adjustment records.

Use durable delivery, idempotent ingestion, explicit failure handling, and reconciliation.

Do not claim billing integration is complete until the actual interface has been tested end to end.

## Customer billing interface

Where supported, show:

- Contracted commitments.
- Provisioned capacity.
- Period-to-date usage.
- Included allowance and remaining balance.
- Rated charges and pending charges, clearly distinguished.
- Historical statements and invoices.
- Billing period and applicable rate schedule.
- Exportable usage details.

Never label estimated or pending charges as final invoices.
```

**Implementation:** `services/turing-enterprise/src/hyba_turing_service/commercial.py; services/turing-enterprise/deploy/HERMITTEN_CONTRACT.md`

**Runtime dependencies:** None for current billing: DEFERRED by user amendment

**Acceptance test:** Reject active financial configuration and provider injection; no Hermitten acceptance gate

**Current evidence:** Production scope/composition negative tests pass locally; no live financial call made; deferred financial gate removed without removing identity/runtime/recovery/package/commercial approval gates.

**Owner / external dependency:** Commercial owner (future scope only)

**Final disposition:** DEFERRED

**Release impact:** Not a current financial release gate

### S13 — Backend contracts and integration boundaries

**Authority:** MASTER_BRIEF.md section 13; user billing amendment supersedes original financial requirements

**Authoritative wording (verbatim):**

```text
# 13\. Backend contracts and integration boundaries

Before implementing complex UI flows, map each screen to its source of truth.

Define the necessary API contracts for:

- Authentication and session management.
- Organisation membership and roles.
- Projects and workspaces.
- Computational job submission and status.
- Results and provenance.
- Service entitlements.
- Provisioning operations.
- Capacity and instance inventory.
- Usage events.
- Billing and reconciliation.
- Audit history.
- Support and operational incidents.

For each contract, document request and response schemas, authentication requirements, error semantics, pagination, filtering, versioning, and idempotency.

If a required backend endpoint does not exist:

1. Document the gap.
2. Define the intended contract.
3. Implement the frontend integration boundary.
4. Use clearly labelled development fixtures only where appropriate.
5. Do not report the capability as operational until the real integration works.

Avoid silently introducing a new database or second backend when an established system already owns the data.
```

**Implementation:** `services/turing-enterprise/src/hyba_turing_service/{api,adapters}.py; docs/turing/workspace.openapi.json`

**Runtime dependencies:** Approved external contracts and installed consumers

**Acceptance test:** Authenticated OpenAPI and actual typed request/response contracts; do not invent missing ports

**Current evidence:** Local service suite: 93 passed, 0 failed/skipped (one deprecation warning). Real SQLite/cryptography; IdP and unit-test runtime peers are doubles; actual local integrations are listed separately. Not live acceptance.

**Owner / external dependency:** Authoritative service/interface owners

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### S14 — Security, privacy, and governance

**Authority:** MASTER_BRIEF.md section 14; user billing amendment supersedes original financial requirements

**Authoritative wording (verbatim):**

```text
# 14\. Security, privacy, and governance

Security must be part of the architecture and user experience, not a later visual or compliance exercise.

Implement or specify, according to the actual system:

- Server-side authorisation.
- Tenant and organisation isolation.
- Secure session management.
- CSRF protections where applicable.
- Input validation and output encoding.
- Protection against injection and broken access control.
- Secure secret management.
- Rate limits and abuse protection.
- Audit logging.
- Data minimisation.
- Appropriate retention and deletion policies.
- Dependency and supply-chain scanning.
- Secure error handling.
- Backup and recovery requirements.
- Controlled administrative access.
- Export and download permissions.

Consider enterprise requirements such as SSO, customer-specific retention policies, data residency, legal holds, contractual confidentiality, and security reviews where relevant.

Do not claim certifications, regulatory compliance, encryption configurations, or isolation guarantees without verified evidence.

Build a threat model covering customer isolation, compromised accounts, privileged operators, exposed credentials, manipulated usage events, duplicate billing, and unauthorised provisioning.
```

**Implementation:** `services/turing-enterprise/src/hyba_turing_service/{identity,sessions,api,control,runtime,release}.py`

**Runtime dependencies:** Actual IdP/Guardian, secret manager, deployment controls and approved retention

**Acceptance test:** Role/tenant/project negatives, stale credentials, rate/body limits, audit integrity, threat review and deployed isolation

**Current evidence:** Local service suite: 93 passed, 0 failed/skipped (one deprecation warning). Real SQLite/cryptography; IdP and unit-test runtime peers are doubles; actual local integrations are listed separately. Not live acceptance. Denial audit is durable/correlation-bound/pseudonymous; audit write failure stays closed. No deployed penetration/isolation/retention qualification.

**Owner / external dependency:** Security, identity, privacy and platform owners

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### S15 — UX completeness and interaction quality

**Authority:** MASTER_BRIEF.md section 15; user billing amendment supersedes original financial requirements

**Authoritative wording (verbatim):**

```text
# 15\. UX completeness and interaction quality

Every implemented screen must be designed for real use.

Include, as appropriate:

- Loading states.
- Empty states with useful next actions.
- Validation errors.
- API errors.
- Permission-denied states.
- Expired-session handling.
- Retry and recovery options.
- Pagination and filtering.
- Search and sorting.
- Confirmation for consequential actions.
- Success feedback.
- Keyboard navigation.
- Responsive layouts.
- Accessible focus states.
- Tooltips and contextual explanations.
- Clear timestamps and status semantics.

Never leave primary buttons inert.

Forms must submit to real handlers or clearly identified development fixtures. Destructive actions must have appropriate safeguards.

Avoid unnecessarily dense dashboards. Prioritise the most important decisions and actions for each user role.

## Accessibility

Target WCAG 2.2 AA.

Test semantic structure, keyboard operation, focus management, screen-reader announcements, contrast, zoom, reduced motion, and accessible validation feedback.

Use accessible primitives rather than building complex interactions from scratch without a compelling reason.

## Responsive behaviour

Design for large desktop workspaces first where analytical density requires it, while preserving useful tablet and mobile experiences.

Tables, charts, sidebars, navigation, dialogs, and complex forms must adapt without losing essential information or requiring horizontal scrolling unnecessarily.
```

**Implementation:** `services/turing-enterprise/src/hyba_turing_service/static/; frontend/src/turing/`

**Runtime dependencies:** Manual assistive technology and supported-browser testing

**Acceptance test:** Loading/error/recovery/focus and mobile/desktop journeys; automated scans not WCAG certification

**Current evidence:** 10 responsive fixture views without page errors/overflow; 12 new interaction groups; 2 automated WCAG-tagged axe scans with 0 violations. Manual testing not done.

**Owner / external dependency:** Accessibility and frontend owners

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### S16 — Analytics and product instrumentation

**Authority:** MASTER_BRIEF.md section 16; user billing amendment supersedes original financial requirements

**Authoritative wording (verbatim):**

```text
# 16\. Analytics and product instrumentation

Instrument the product to understand adoption and service quality while respecting privacy.

Potential events include:

- Account onboarding completed.
- Workspace created.
- User invited.
- Provisioning request submitted and completed.
- Job submitted, completed, failed, or cancelled.
- Results viewed or exported.
- Usage threshold approached.
- Billing discrepancy detected.
- Support request opened.

Define event schemas, ownership, retention, access restrictions, and permissible uses.

Do not send confidential computation inputs, secrets, or sensitive results to general product analytics.

Measure genuine customer value and workflow completion rather than optimising vanity metrics alone.
```

**Implementation:** `docs/turing/OPERATIONS_AND_QUALIFICATION.md; services/turing-enterprise/src/hyba_turing_service/{api,control}.py`

**Runtime dependencies:** Approved collector, event/retention/access/consent policy

**Acceptance test:** Verify actual privacy-minimizing metrics, trace correlation, alert delivery and access

**Current evidence:** Source/document inventory only for this scope; no current owner/live acceptance.

**Owner / external dependency:** Operations/privacy owners

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### S17 — Operational administration and support

**Authority:** MASTER_BRIEF.md section 17; user billing amendment supersedes original financial requirements

**Authoritative wording (verbatim):**

```text
# 17\. Operational administration and support

Provide internal tools for authorised service operators to understand customer state and resolve operational problems.

Include, where supported:

- Customer service status.
- Provisioning history.
- Entitlement discrepancies.
- Job failures and error categories.
- Usage ingestion failures.
- Billing reconciliation exceptions.
- Audit history.
- Support notes with appropriate access controls.
- Incident status and remediation records.

Support actions must be permissioned and audited.

Avoid unrestricted impersonation. If support access to a customer workspace is necessary, require explicit authorisation, limited duration, and traceable records.
```

**Implementation:** `services/turing-enterprise/deploy/OPERATIONS.md; services/turing-enterprise/src/hyba_turing_service/{main,supervisor,api}.py`

**Runtime dependencies:** Target infrastructure, approved objectives, independent audit sink and named operators

**Acceptance test:** Readiness, monitoring/alerts, incident, backup+custody restore, rollback and failure drill

**Current evidence:** Local service suite: 93 passed, 0 failed/skipped (one deprecation warning). Real SQLite/cryptography; IdP and unit-test runtime peers are doubles; actual local integrations are listed separately. Not live acceptance.

**Owner / external dependency:** Deployment owner; named on-call/security escalation

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### S18 — Go-to-market readiness

**Authority:** MASTER_BRIEF.md section 18; user billing amendment supersedes original financial requirements

**Authoritative wording (verbatim):**

```text
# 18\. Go-to-market readiness

Treat the product website, commercial offer, onboarding, service delivery, and billing as one coherent customer journey.

Develop the following deliverables:

## Product strategy

- Positioning statement.
- Ideal customer profiles.
- Buyer and user personas.
- Use-case prioritisation.
- Competitive differentiation supported by evidence.
- Product packaging.
- Commercial hypotheses.
- Pilot acceptance criteria.
- Customer success measures.

## Sales and onboarding

- Enterprise enquiry workflow.
- Technical evaluation process.
- Customer qualification.
- Security and architecture questionnaire materials.
- Contract-to-provisioning handoff.
- Customer onboarding checklist.
- Administrator training.
- Support escalation model.
- Renewal and expansion workflow.

## Public launch

- Product messaging and approved claims.
- Documentation and API onboarding.
- Case studies only where real and authorised.
- Research citations.
- Public release notes.
- Contact and support channels.
- Website analytics and conversion measurement.
- Incident communication and status information where appropriate.

Do not fabricate customers, testimonials, market-size estimates, competitive benchmarks, or performance claims.

The initial objective is a credible enterprise pilot and a repeatable delivery model—not a superficial appearance of being a global platform.
```

**Implementation:** `docs/turing/PRODUCT_AND_GTM.md; services/turing-enterprise/deploy/OPERATIONS.md`

**Runtime dependencies:** Approved offer/support/contact/legal; actual pilot authorization

**Acceptance test:** Approved onboarding and pilot success evidence, not hypothetical customer references

**Current evidence:** Source/document inventory only for this scope; no current owner/live acceptance.

**Owner / external dependency:** Commercial/product, legal and customer owners

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### S19 — Testing and release acceptance

**Authority:** MASTER_BRIEF.md section 19; user billing amendment supersedes original financial requirements

**Authoritative wording (verbatim):**

```text
# 19\. Testing and release acceptance

Create a test plan covering the complete customer lifecycle.

## Frontend and API tests

- Component and interaction tests.
- Schema and validation tests.
- API contract tests.
- Authentication and authorisation tests.
- Organisation isolation tests.
- Provisioning lifecycle tests.
- Job submission and status transitions.
- Error, timeout, retry, and cancellation handling.
- Billing event ingestion and idempotency.
- Pricing and rating rules.
- Usage reconciliation.
- Accessibility.
- Responsive layouts.
- Browser compatibility where relevant.

## End-to-end scenarios

At minimum, validate:

**Scenario A — Enterprise onboarding**

An authorised operator creates a customer, associates an approved contract, provisions the agreed capacity, and activates the service.

**Scenario B — Customer administration**

The customer administrator invites a user, assigns an appropriate role, and verifies that the user can access only permitted resources.

**Scenario C — Computational workflow**

An authorised user submits valid inputs, tracks a real computational job, inspects the returned result, and accesses the available provenance.

**Scenario D — Entitlement enforcement**

An organisation attempts an operation outside its permissions or contractual entitlement. The service rejects it correctly and records the appropriate event.

**Scenario E — Commercial reconciliation**

A completed billable operation produces one authoritative usage record, which can be rated and reconciled without duplicate charges.

**Scenario F — Lifecycle termination**

An authorised operator suspends or terminates a customer according to policy, access is revoked, and retention and billing consequences are handled correctly.

**Scenario G — Failure recovery**

A provisioning or usage-ingestion operation fails partway through, is retried safely, and reaches a consistent state without duplicated resources or charges.

Use the existing project's testing infrastructure where possible. Run tests against the actual service interfaces when available; label mocks and fixtures accurately.
```

**Implementation:** `services/turing-enterprise/tests/; services/turing-enterprise/integration/test_installed_runtime.py; turing_universal_quantum_computer/tests/`

**Runtime dependencies:** Full installed checkout, CI check-read access and authorized target services

**Acceptance test:** All nine evidence categories separately; integration failure retained, no skipped tests called passes

**Current evidence:** Local service suite: 93 passed, 0 failed/skipped (one deprecation warning). Real SQLite/cryptography; IdP and unit-test runtime peers are doubles; actual local integrations are listed separately. Not live acceptance. Isolated current stabilizer: 11 passed. Research gating: 11 passed plus 4 unittest subtests. The initial isolated harness was supplemented by the full recovered VQC suite; no QPU or theorem proof inferred. Recovered pinned owner sources; installed hyba-turing-vqc 1.0.0 and hyba-kellogg-tensor 1.0.0. Full recovered VQC test directory: 556 passed plus 111 subtests, 0 failed/errors/skipped (134.85s). No VQC implementation patch reapplied. Three actual local integrations passed (3.01s): installed subprocess runtime; signed TEST-identity API -> SQLite queue -> default worker -> certificate/witness/report, same-key recovery and revocation; canonical SharedTuring -> shared THESEUS/OVID -> verified lineage -> durable lifecycle restart replay. Real local owner code, not enterprise SSO/approved production composition.

**Owner / external dependency:** CI, security, accessibility and release owners

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### S20 — Design and implementation deliverables

**Authority:** MASTER_BRIEF.md section 20; user billing amendment supersedes original financial requirements

**Authoritative wording (verbatim):**

```text
# 20\. Design and implementation deliverables

Produce:

1. Repository and architecture assessment.
2. Product requirements and route map.
3. Brand direction and design-token specification.
4. Reusable component system.
5. Public product website.
6. Authenticated computational workspace.
7. Customer administration portal.
8. Internal service operations console.
9. Provisioning and entitlement workflows.
10. Typed frontend service adapters and documented API contracts.
11. Hermitten integration assessment and implementation where feasible.
12. Security and privacy assessment.
13. Testing strategy and automated tests.
14. Commercial model and pricing hypotheses.
15. Enterprise onboarding and go-to-market plan.
16. Deployment, monitoring, and recovery documentation.
17. Implementation status and outstanding dependency register.

Not every deliverable must be completed in a single iteration. Prioritise the coherent, working end-to-end journey over superficially implementing every route.
```

**Implementation:** `This register D01–D17; source locations in each deliverable`

**Runtime dependencies:** All mandatory applicable acceptance gates

**Acceptance test:** Verify each of the 17 deliverables independently; document existence alone is not acceptance

**Current evidence:** Source/document inventory only for this scope; no current owner/live acceptance.

**Owner / external dependency:** Each deliverable owner below

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### S21 — Execution plan

**Authority:** MASTER_BRIEF.md section 21; user billing amendment supersedes original financial requirements

**Authoritative wording (verbatim):**

```text
# 21\. Execution plan

Work in controlled increments.

### Stage 1 — Discovery and definition

Inspect the repository, identify actual capabilities, map existing contracts, review PR #96, and document the architecture and implementation gaps.

### Stage 2 — Product foundations

Establish the information architecture, visual identity, design tokens, accessible components, application shell, and typed service boundaries.

### Stage 3 — Functional core

Implement identity integration, organisation structure, customer administration, workspace navigation, and the real computational workflow wherever the necessary backend interfaces exist.

### Stage 4 — Commercial control plane

Implement entitlement management, provisioning, capacity accounting, metering contracts, and the Hermitten integration where technically and organisationally authorised.

### Stage 5 — Public experience and enterprise polish

Complete product messaging, documentation, executive-facing presentation, responsive layouts, error states, onboarding, and customer support workflows.

### Stage 6 — Qualification

Run type checking, linting, security scans, automated tests, production builds, accessibility checks, and end-to-end scenarios.

### Stage 7 — Release readiness

Document verified functionality, unresolved dependencies, security considerations, known limitations, rollback procedures, and the evidence required for release approval.
```

**Implementation:** `This register; services/turing-enterprise/src/; docs/turing/`

**Runtime dependencies:** Full qualification environment and independent release approvals

**Acceptance test:** Stages A–F cannot be closed by a plan; code and local evidence delivered, full acceptance still open

**Current evidence:** Local service suite: 93 passed, 0 failed/skipped (one deprecation warning). Real SQLite/cryptography; IdP and unit-test runtime peers are doubles; actual local integrations are listed separately. Not live acceptance.

**Owner / external dependency:** Repository and release owners

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### S22 — Rules of engagement for the coding agent

**Authority:** MASTER_BRIEF.md section 22; user billing amendment supersedes original financial requirements

**Authoritative wording (verbatim):**

```text
# 22\. Rules of engagement for the coding agent

1. Preserve the existing TURING engine and package identity.
2. Respect existing agent work and avoid duplicate implementations.
3. Inspect before modifying.
4. Prefer working functionality over mockups.
5. Never fabricate capabilities, customers, data, results, or integrations.
6. Do not hardcode customer-specific allocations or pricing.
7. Keep business rules outside presentational components.
8. Make security and authorisation enforceable on the server.
9. Keep billing, metering, entitlements, and execution responsibilities distinct.
10. Use typed contracts and explicit error semantics.
11. Avoid unnecessary dependencies and architectural rewrites.
12. Maintain accessible and responsive interactions.
13. Preserve existing tests and add regression coverage for changes.
14. Do not publish, deploy, or modify production infrastructure without explicit authorisation.
15. Never represent unverified CI checks as successful.
16. Do not declare the product production-ready merely because the UI builds.
17. Document genuine blockers and decisions requiring human approval.
18. Make progress in reviewable increments, with clear summaries of changed files, test results, and remaining risks.
```

**Implementation:** `Pinned source inventories; targeted implementation and test diffs`

**Runtime dependencies:** Repository protections and approved external access

**Acceptance test:** No engine rewrite, fabricated integration, merge, force-push, release publication or deployment; preserve tests

**Current evidence:** Local service suite: 93 passed, 0 failed/skipped (one deprecation warning). Real SQLite/cryptography; IdP and unit-test runtime peers are doubles; actual local integrations are listed separately. Not live acceptance.

**Owner / external dependency:** Engineering/release owners

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### S23 — Definition of done

**Authority:** MASTER_BRIEF.md section 23; user billing amendment supersedes original financial requirements

**Authoritative wording (verbatim):**

```text
# 23\. Definition of done

The work is successful when:

- TURING has a distinctive, coherent, enterprise-grade identity.
- The public website explains the real product accurately.
- The application provides a polished, usable computational workspace.
- Internal operators can manage customer provisioning through authorised workflows.
- Customer administrators can manage permitted users, roles, and capacity.
- The frontend uses real, documented contracts for supported operations.
- Mathematical results and provenance are represented faithfully.
- Commercial entitlements are enforced by the authoritative service.
- Usage and billing integration are traceable and reconcilable.
- Security boundaries and audit trails have meaningful tests.
- The application handles errors, empty states, loading, cancellation, and recovery properly.
- The design system and codebase are maintainable.
- The implementation has automated evidence supporting its claims.
- Outstanding dependencies and release risks are explicit.
- The product has a credible enterprise-pilot and go-to-market path.

**Final instruction:** Build TURING as a serious computational intelligence institution expressed through exceptional software and product design. The interface should make complex computation accessible without trivialising its mathematical foundations. The commercial platform should make the service governable and economically sustainable without turning the product into a generic SaaS subscription dashboard.

Start by examining the actual repository and existing work. Then implement the highest-value complete vertical slice, verify it, and continue systematically. Do not substitute another strategic essay for execution.

## My recommendation on how to use this prompt

Give the agent this brief as the overarching product mandate, but tell it to retain its existing implementation plan and completed work. It should use the prompt to identify genuine gaps, not restart from zero.

Three priorities matter most:

1. A real end-to-end journey: customer provisioned → user authorised → computation submitted → results inspected → usage recorded → billing reconciled.
2. A distinctive product identity: coherent design, outstanding typography, thoughtful data presentation, and an experience that feels purpose-built for computational intelligence.
3. Commercial truth: define exactly what an instance represents, how capability is measured, and how Hermitten fits before committing to pricing or promising customer capacity.

That combination will do more for TURING's credibility than an enormous interface with dozens of incomplete screens.
```

**Implementation:** `This register and evidence manifest; all implementation locations above`

**Runtime dependencies:** All mandatory in-scope acceptance and actual deployment qualification

**Acceptance test:** Every applicable condition in authoritative text must be evidenced; current overall completion NOT established

**Current evidence:** Local service suite: 93 passed, 0 failed/skipped (one deprecation warning). Real SQLite/cryptography; IdP and unit-test runtime peers are doubles; actual local integrations are listed separately. Not live acceptance.

**Owner / external dependency:** Accountable product/security/release owners

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### D01 — Repository and architecture assessment.

**Authority:** MASTER_BRIEF.md section 20, deliverable 1; user billing amendment applies

**Authoritative wording (verbatim):**

```text
Repository and architecture assessment.
```

**Implementation:** `docs/turing/MASTER_BRIEF.md; current GitHub main/PR metadata; source inventories`

**Runtime dependencies:** Full authenticated checkout and accessible checks

**Acceptance test:** Fetch main and all PR dependencies; compare exact source trees; full audit not achieved

**Current evidence:** Source/document inventory only for this scope; no current owner/live acceptance.

**Owner / external dependency:** Repository maintainer; CI owner

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### D02 — Product requirements and route map.

**Authority:** MASTER_BRIEF.md section 20, deliverable 2; user billing amendment applies

**Authoritative wording (verbatim):**

```text
Product requirements and route map.
```

**Implementation:** `frontend/src/turing/{routes.ts,TuringApp.tsx}; services/turing-enterprise/src/hyba_turing_service/static/portal.js`

**Runtime dependencies:** Approved IdP/customer/contract and real runtime

**Acceptance test:** Route all real surfaces with permitted backend state; no simulated customer success

**Current evidence:** Local service suite: 93 passed, 0 failed/skipped (one deprecation warning). Real SQLite/cryptography; IdP and unit-test runtime peers are doubles; actual local integrations are listed separately. Not live acceptance.

**Owner / external dependency:** Product/platform owners

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### D03 — Brand direction and design-token specification.

**Authority:** MASTER_BRIEF.md section 20, deliverable 3; user billing amendment applies

**Authoritative wording (verbatim):**

```text
Brand direction and design-token specification.
```

**Implementation:** `frontend/src/turing/{workspace.css,PublicSite.tsx}; docs/turing/PRODUCT_AND_GTM.md`

**Runtime dependencies:** Brand approval; supported browsers and assistive technologies

**Acceptance test:** Design review; manual keyboard/screen-reader/zoom and automated accessibility

**Current evidence:** Source/document inventory only for this scope; no current owner/live acceptance.

**Owner / external dependency:** Brand and product owners

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### D04 — Reusable component system.

**Authority:** MASTER_BRIEF.md section 20, deliverable 4; user billing amendment applies

**Authoritative wording (verbatim):**

```text
Reusable component system.
```

**Implementation:** `frontend/src/turing/{client.ts,integrations.ts}; services/turing-enterprise/pyproject.toml`

**Runtime dependencies:** Locked host toolchain and complete checkout

**Acceptance test:** Locked lint/typecheck/build/dependency scans plus installed consumer regression

**Current evidence:** Source/document inventory only for this scope; no current owner/live acceptance.

**Owner / external dependency:** Frontend/release maintainers

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### D05 — Public product website.

**Authority:** MASTER_BRIEF.md section 20, deliverable 5; user billing amendment applies

**Authoritative wording (verbatim):**

```text
Public product website.
```

**Implementation:** `frontend/src/turing/{PublicSite.tsx,productContent.ts}; docs/turing/PRODUCT_AND_GTM.md`

**Runtime dependencies:** Approved policies, enquiry destination, references and publication rights

**Acceptance test:** Public journey, approved contact delivery, legal/privacy and claim review

**Current evidence:** Source/document inventory only for this scope; no current owner/live acceptance.

**Owner / external dependency:** Product, legal, privacy and support owners

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### D06 — Authenticated computational workspace.

**Authority:** MASTER_BRIEF.md section 20, deliverable 6; user billing amendment applies

**Authoritative wording (verbatim):**

```text
Authenticated computational workspace.
```

**Implementation:** `frontend/src/turing/{Workspace.tsx,History.tsx,Evidence.tsx}; services/turing-enterprise/src/hyba_turing_service/{api.py,static/portal.js,runtime.py}`

**Runtime dependencies:** Actual canonical installed runtime and authenticated target

**Acceptance test:** Real execution through result/provenance; search/filter/pages, cancellation and same-key recovery; fixtures are insufficient

**Current evidence:** Local service suite: 93 passed, 0 failed/skipped (one deprecation warning). Real SQLite/cryptography; IdP and unit-test runtime peers are doubles; actual local integrations are listed separately. Not live acceptance. Fixture history/filter/cursor/cancel/export/stale-tenant workflows passed. Three actual local integrations passed (3.01s): installed subprocess runtime; signed TEST-identity API -> SQLite queue -> default worker -> certificate/witness/report, same-key recovery and revocation; canonical SharedTuring -> shared THESEUS/OVID -> verified lineage -> durable lifecycle restart replay. Real local owner code, not enterprise SSO/approved production composition. Recovered pinned owner sources; installed hyba-turing-vqc 1.0.0 and hyba-kellogg-tensor 1.0.0. Full recovered VQC test directory: 556 passed plus 111 subtests, 0 failed/errors/skipped (134.85s). No VQC implementation patch reapplied. Three actual local integrations passed (3.01s): installed subprocess runtime; signed TEST-identity API -> SQLite queue -> default worker -> certificate/witness/report, same-key recovery and revocation; canonical SharedTuring -> shared THESEUS/OVID -> verified lineage -> durable lifecycle restart replay. Real local owner code, not enterprise SSO/approved production composition.

**Owner / external dependency:** Execution/custody and frontend owners

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### D07 — Customer administration portal.

**Authority:** MASTER_BRIEF.md section 20, deliverable 7; user billing amendment applies

**Authoritative wording (verbatim):**

```text
Customer administration portal.
```

**Implementation:** `services/turing-enterprise/src/hyba_turing_service/{identity,sessions,enterprise,api}.py`

**Runtime dependencies:** Approved IdP tenant/client, invitation/offboarding interface and revocation policy

**Acceptance test:** Actual SSO, invite, assign/revoke, expiry, current role and direct cross-tenant API negatives

**Current evidence:** Local service suite: 93 passed, 0 failed/skipped (one deprecation warning). Real SQLite/cryptography; IdP and unit-test runtime peers are doubles; actual local integrations are listed separately. Not live acceptance.

**Owner / external dependency:** Identity and customer administrators

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### D08 — Internal service operations console.

**Authority:** MASTER_BRIEF.md section 20, deliverable 8; user billing amendment applies

**Authoritative wording (verbatim):**

```text
Internal service operations console.
```

**Implementation:** `services/turing-enterprise/deploy/OPERATIONS.md; services/turing-enterprise/src/hyba_turing_service/{main,supervisor,api}.py`

**Runtime dependencies:** Target infrastructure, approved objectives, independent audit sink and named operators

**Acceptance test:** Readiness, monitoring/alerts, incident, backup+custody restore, rollback and failure drill

**Current evidence:** Local service suite: 93 passed, 0 failed/skipped (one deprecation warning). Real SQLite/cryptography; IdP and unit-test runtime peers are doubles; actual local integrations are listed separately. Not live acceptance.

**Owner / external dependency:** Deployment owner; named on-call/security escalation

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### D09 — Provisioning and entitlement workflows.

**Authority:** MASTER_BRIEF.md section 20, deliverable 9; user billing amendment applies

**Authoritative wording (verbatim):**

```text
Provisioning and entitlement workflows.
```

**Implementation:** `services/turing-enterprise/src/hyba_turing_service/{control,enterprise,supervisor,api}.py`

**Runtime dependencies:** Approved logical-slot meaning and contract limits; target resource sizing

**Acceptance test:** Transactional provisioning/resize/activation/revocation, contention, duplicate/restart/partial failure on authoritative target

**Current evidence:** Local service suite: 93 passed, 0 failed/skipped (one deprecation warning). Real SQLite/cryptography; IdP and unit-test runtime peers are doubles; actual local integrations are listed separately. Not live acceptance.

**Owner / external dependency:** Capacity and contract authority

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### D10 — Typed frontend service adapters and documented API contracts.

**Authority:** MASTER_BRIEF.md section 20, deliverable 10; user billing amendment applies

**Authoritative wording (verbatim):**

```text
Typed frontend service adapters and documented API contracts.
```

**Implementation:** `services/turing-enterprise/src/hyba_turing_service/{api,adapters}.py; docs/turing/workspace.openapi.json`

**Runtime dependencies:** Approved external contracts and installed consumers

**Acceptance test:** Authenticated OpenAPI and actual typed request/response contracts; do not invent missing ports

**Current evidence:** Local service suite: 93 passed, 0 failed/skipped (one deprecation warning). Real SQLite/cryptography; IdP and unit-test runtime peers are doubles; actual local integrations are listed separately. Not live acceptance. Recovered pinned owner sources; installed hyba-turing-vqc 1.0.0 and hyba-kellogg-tensor 1.0.0. Full recovered VQC test directory: 556 passed plus 111 subtests, 0 failed/errors/skipped (134.85s). No VQC implementation patch reapplied. Three actual local integrations passed (3.01s): installed subprocess runtime; signed TEST-identity API -> SQLite queue -> default worker -> certificate/witness/report, same-key recovery and revocation; canonical SharedTuring -> shared THESEUS/OVID -> verified lineage -> durable lifecycle restart replay. Real local owner code, not enterprise SSO/approved production composition.

**Owner / external dependency:** Authoritative service/interface owners

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### D11 — Hermitten integration assessment and implementation where feasible.

**Authority:** MASTER_BRIEF.md section 20, deliverable 11; user billing amendment applies

**Authoritative wording (verbatim):**

```text
Hermitten integration assessment and implementation where feasible.
```

**Implementation:** `services/turing-enterprise/src/hyba_turing_service/commercial.py; services/turing-enterprise/deploy/HERMITTEN_CONTRACT.md`

**Runtime dependencies:** None for current billing: DEFERRED by user amendment

**Acceptance test:** Reject active financial configuration and provider injection; no Hermitten acceptance gate

**Current evidence:** Production scope/composition negative tests pass locally; no live financial call made; deferred financial gate removed without removing identity/runtime/recovery/package/commercial approval gates.

**Owner / external dependency:** Commercial owner (future scope only)

**Final disposition:** DEFERRED

**Release impact:** Not a current financial release gate

### D12 — Security and privacy assessment.

**Authority:** MASTER_BRIEF.md section 20, deliverable 12; user billing amendment applies

**Authoritative wording (verbatim):**

```text
Security and privacy assessment.
```

**Implementation:** `services/turing-enterprise/src/hyba_turing_service/{identity,sessions,api,control,runtime,release}.py`

**Runtime dependencies:** Actual IdP/Guardian, secret manager, deployment controls and approved retention

**Acceptance test:** Role/tenant/project negatives, stale credentials, rate/body limits, audit integrity, threat review and deployed isolation

**Current evidence:** Local service suite: 93 passed, 0 failed/skipped (one deprecation warning). Real SQLite/cryptography; IdP and unit-test runtime peers are doubles; actual local integrations are listed separately. Not live acceptance. Denial audit is durable/correlation-bound/pseudonymous; audit write failure stays closed. No deployed penetration/isolation/retention qualification.

**Owner / external dependency:** Security, identity, privacy and platform owners

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### D13 — Testing strategy and automated tests.

**Authority:** MASTER_BRIEF.md section 20, deliverable 13; user billing amendment applies

**Authoritative wording (verbatim):**

```text
Testing strategy and automated tests.
```

**Implementation:** `services/turing-enterprise/tests/; services/turing-enterprise/integration/test_installed_runtime.py; turing_universal_quantum_computer/tests/`

**Runtime dependencies:** Full installed checkout, CI check-read access and authorized target services

**Acceptance test:** All nine evidence categories separately; integration failure retained, no skipped tests called passes

**Current evidence:** Local service suite: 93 passed, 0 failed/skipped (one deprecation warning). Real SQLite/cryptography; IdP and unit-test runtime peers are doubles; actual local integrations are listed separately. Not live acceptance. Isolated current stabilizer: 11 passed. Research gating: 11 passed plus 4 unittest subtests. The initial isolated harness was supplemented by the full recovered VQC suite; no QPU or theorem proof inferred. Recovered pinned owner sources; installed hyba-turing-vqc 1.0.0 and hyba-kellogg-tensor 1.0.0. Full recovered VQC test directory: 556 passed plus 111 subtests, 0 failed/errors/skipped (134.85s). No VQC implementation patch reapplied. Three actual local integrations passed (3.01s): installed subprocess runtime; signed TEST-identity API -> SQLite queue -> default worker -> certificate/witness/report, same-key recovery and revocation; canonical SharedTuring -> shared THESEUS/OVID -> verified lineage -> durable lifecycle restart replay. Real local owner code, not enterprise SSO/approved production composition.

**Owner / external dependency:** CI, security, accessibility and release owners

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### D14 — Commercial model and pricing hypotheses.

**Authority:** MASTER_BRIEF.md section 20, deliverable 14; user billing amendment applies

**Authoritative wording (verbatim):**

```text
Commercial model and pricing hypotheses.
```

**Implementation:** `services/turing-enterprise/src/hyba_turing_service/{commercial,enterprise,release}.py; docs/turing/CONTRACTS_AND_BILLING.md`

**Runtime dependencies:** Current approved non-financial terms and effective entitlements; future financial scope deferred

**Acceptance test:** Exact-term approval and quotas remain mandatory; no rates/provider/invoices accepted

**Current evidence:** Local service suite: 93 passed, 0 failed/skipped (one deprecation warning). Real SQLite/cryptography; IdP and unit-test runtime peers are doubles; actual local integrations are listed separately. Not live acceptance.

**Owner / external dependency:** Commercial approver and authorization owner

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### D15 — Enterprise onboarding and go-to-market plan.

**Authority:** MASTER_BRIEF.md section 20, deliverable 15; user billing amendment applies

**Authoritative wording (verbatim):**

```text
Enterprise onboarding and go-to-market plan.
```

**Implementation:** `docs/turing/PRODUCT_AND_GTM.md; services/turing-enterprise/deploy/OPERATIONS.md`

**Runtime dependencies:** Approved offer/support/contact/legal; actual pilot authorization

**Acceptance test:** Approved onboarding and pilot success evidence, not hypothetical customer references

**Current evidence:** Source/document inventory only for this scope; no current owner/live acceptance.

**Owner / external dependency:** Commercial/product, legal and customer owners

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### D16 — Deployment, monitoring, and recovery documentation.

**Authority:** MASTER_BRIEF.md section 20, deliverable 16; user billing amendment applies

**Authoritative wording (verbatim):**

```text
Deployment, monitoring, and recovery documentation.
```

**Implementation:** `services/turing-enterprise/deploy/OPERATIONS.md; services/turing-enterprise/src/hyba_turing_service/{main,supervisor,api}.py`

**Runtime dependencies:** Target infrastructure, approved objectives, independent audit sink and named operators

**Acceptance test:** Readiness, monitoring/alerts, incident, backup+custody restore, rollback and failure drill

**Current evidence:** Local service suite: 93 passed, 0 failed/skipped (one deprecation warning). Real SQLite/cryptography; IdP and unit-test runtime peers are doubles; actual local integrations are listed separately. Not live acceptance.

**Owner / external dependency:** Deployment owner; named on-call/security escalation

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### D17 — Implementation status and outstanding dependency register.

**Authority:** MASTER_BRIEF.md section 20, deliverable 17; user billing amendment applies

**Authoritative wording (verbatim):**

```text
Implementation status and outstanding dependency register.
```

**Implementation:** `This register and evidence manifest; all implementation locations above`

**Runtime dependencies:** All mandatory in-scope acceptance and actual deployment qualification

**Acceptance test:** Every applicable condition in authoritative text must be evidenced; current overall completion NOT established

**Current evidence:** Local service suite: 93 passed, 0 failed/skipped (one deprecation warning). Real SQLite/cryptography; IdP and unit-test runtime peers are doubles; actual local integrations are listed separately. Not live acceptance.

**Owner / external dependency:** Accountable product/security/release owners

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### SC-A — Enterprise onboarding

**Authority:** MASTER_BRIEF.md section 19, scenario A; user billing amendment applies

**Authoritative wording (verbatim):**

```text
**Scenario A — Enterprise onboarding**

An authorised operator creates a customer, associates an approved contract, provisions the agreed capacity, and activates the service.
```

**Implementation:** `services/turing-enterprise/src/hyba_turing_service/{control,enterprise,supervisor,api}.py`

**Runtime dependencies:** Approved logical-slot meaning and contract limits; target resource sizing

**Acceptance test:** Transactional provisioning/resize/activation/revocation, contention, duplicate/restart/partial failure on authoritative target

**Current evidence:** Local service suite: 93 passed, 0 failed/skipped (one deprecation warning). Real SQLite/cryptography; IdP and unit-test runtime peers are doubles; actual local integrations are listed separately. Not live acceptance.

**Owner / external dependency:** Capacity and contract authority

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### SC-B — Customer administration

**Authority:** MASTER_BRIEF.md section 19, scenario B; user billing amendment applies

**Authoritative wording (verbatim):**

```text
**Scenario B — Customer administration**

The customer administrator invites a user, assigns an appropriate role, and verifies that the user can access only permitted resources.
```

**Implementation:** `services/turing-enterprise/src/hyba_turing_service/{identity,sessions,enterprise,api}.py`

**Runtime dependencies:** Approved IdP tenant/client, invitation/offboarding interface and revocation policy

**Acceptance test:** Actual SSO, invite, assign/revoke, expiry, current role and direct cross-tenant API negatives

**Current evidence:** Local service suite: 93 passed, 0 failed/skipped (one deprecation warning). Real SQLite/cryptography; IdP and unit-test runtime peers are doubles; actual local integrations are listed separately. Not live acceptance. Existing-subject membership APIs are not an IdP invitation or delivery integration.

**Owner / external dependency:** Identity and customer administrators

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### SC-C — Computational workflow

**Authority:** MASTER_BRIEF.md section 19, scenario C; user billing amendment applies

**Authoritative wording (verbatim):**

```text
**Scenario C — Computational workflow**

An authorised user submits valid inputs, tracks a real computational job, inspects the returned result, and accesses the available provenance.
```

**Implementation:** `frontend/src/turing/{Workspace.tsx,History.tsx,Evidence.tsx}; services/turing-enterprise/src/hyba_turing_service/{api.py,static/portal.js,runtime.py}`

**Runtime dependencies:** Actual canonical installed runtime and authenticated target

**Acceptance test:** Real execution through result/provenance; search/filter/pages, cancellation and same-key recovery; fixtures are insufficient

**Current evidence:** Local service suite: 93 passed, 0 failed/skipped (one deprecation warning). Real SQLite/cryptography; IdP and unit-test runtime peers are doubles; actual local integrations are listed separately. Not live acceptance. Fixture history/filter/cursor/cancel/export/stale-tenant workflows passed. Three actual local integrations passed (3.01s): installed subprocess runtime; signed TEST-identity API -> SQLite queue -> default worker -> certificate/witness/report, same-key recovery and revocation; canonical SharedTuring -> shared THESEUS/OVID -> verified lineage -> durable lifecycle restart replay. Real local owner code, not enterprise SSO/approved production composition. Recovered pinned owner sources; installed hyba-turing-vqc 1.0.0 and hyba-kellogg-tensor 1.0.0. Full recovered VQC test directory: 556 passed plus 111 subtests, 0 failed/errors/skipped (134.85s). No VQC implementation patch reapplied. Three actual local integrations passed (3.01s): installed subprocess runtime; signed TEST-identity API -> SQLite queue -> default worker -> certificate/witness/report, same-key recovery and revocation; canonical SharedTuring -> shared THESEUS/OVID -> verified lineage -> durable lifecycle restart replay. Real local owner code, not enterprise SSO/approved production composition.

**Owner / external dependency:** Execution/custody and frontend owners

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### SC-D — Entitlement enforcement

**Authority:** MASTER_BRIEF.md section 19, scenario D; user billing amendment applies

**Authoritative wording (verbatim):**

```text
**Scenario D — Entitlement enforcement**

An organisation attempts an operation outside its permissions or contractual entitlement. The service rejects it correctly and records the appropriate event.
```

**Implementation:** `services/turing-enterprise/src/hyba_turing_service/{identity,sessions,api,control,runtime,release}.py`

**Runtime dependencies:** Actual IdP/Guardian, secret manager, deployment controls and approved retention

**Acceptance test:** Role/tenant/project negatives, stale credentials, rate/body limits, audit integrity, threat review and deployed isolation

**Current evidence:** Local service suite: 93 passed, 0 failed/skipped (one deprecation warning). Real SQLite/cryptography; IdP and unit-test runtime peers are doubles; actual local integrations are listed separately. Not live acceptance. Denial audit is durable/correlation-bound/pseudonymous; audit write failure stays closed. No deployed penetration/isolation/retention qualification.

**Owner / external dependency:** Security, identity, privacy and platform owners

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### SC-E — Commercial reconciliation

**Authority:** MASTER_BRIEF.md section 19, scenario E; user billing amendment applies

**Authoritative wording (verbatim):**

```text
**Scenario E — Commercial reconciliation**

A completed billable operation produces one authoritative usage record, which can be rated and reconciled without duplicate charges.
```

**Implementation:** `services/turing-enterprise/src/hyba_turing_service/commercial.py; services/turing-enterprise/deploy/HERMITTEN_CONTRACT.md`

**Runtime dependencies:** None for current billing: DEFERRED by user amendment

**Acceptance test:** Reject active financial configuration and provider injection; no Hermitten acceptance gate

**Current evidence:** Production scope/composition negative tests pass locally; no live financial call made; deferred financial gate removed without removing identity/runtime/recovery/package/commercial approval gates.

**Owner / external dependency:** Commercial owner (future scope only)

**Final disposition:** DEFERRED

**Release impact:** Not a current financial release gate

### SC-F — Lifecycle termination

**Authority:** MASTER_BRIEF.md section 19, scenario F; user billing amendment applies

**Authoritative wording (verbatim):**

```text
**Scenario F — Lifecycle termination**

An authorised operator suspends or terminates a customer according to policy, access is revoked, and retention and billing consequences are handled correctly.
```

**Implementation:** `services/turing-enterprise/src/hyba_turing_service/{control,enterprise,supervisor,api}.py`

**Runtime dependencies:** Approved logical-slot meaning and contract limits; target resource sizing

**Acceptance test:** Transactional provisioning/resize/activation/revocation, contention, duplicate/restart/partial failure on authoritative target

**Current evidence:** Local service suite: 93 passed, 0 failed/skipped (one deprecation warning). Real SQLite/cryptography; IdP and unit-test runtime peers are doubles; actual local integrations are listed separately. Not live acceptance. Suspension blocks new work; preserved read/audit access follows existing implementation, not an approved universal offboarding policy. Financial consequences deferred.

**Owner / external dependency:** Capacity and contract authority

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence

### SC-G — Failure recovery

**Authority:** MASTER_BRIEF.md section 19, scenario G; user billing amendment applies

**Authoritative wording (verbatim):**

```text
**Scenario G — Failure recovery**

A provisioning or usage-ingestion operation fails partway through, is retried safely, and reaches a consistent state without duplicated resources or charges.
```

**Implementation:** `services/turing-enterprise/src/hyba_turing_service/{control,enterprise,supervisor,api}.py`

**Runtime dependencies:** Approved logical-slot meaning and contract limits; target resource sizing

**Acceptance test:** Transactional provisioning/resize/activation/revocation, contention, duplicate/restart/partial failure on authoritative target

**Current evidence:** Local service suite: 93 passed, 0 failed/skipped (one deprecation warning). Real SQLite/cryptography; IdP and unit-test runtime peers are doubles; actual local integrations are listed separately. Not live acceptance. Local SQLite retry/recovery tests only. Provisioning and operational-fact integrity remain in scope; no financial posting implied. Recovered pinned owner sources; installed hyba-turing-vqc 1.0.0 and hyba-kellogg-tensor 1.0.0. Full recovered VQC test directory: 556 passed plus 111 subtests, 0 failed/errors/skipped (134.85s). No VQC implementation patch reapplied. Three actual local integrations passed (3.01s): installed subprocess runtime; signed TEST-identity API -> SQLite queue -> default worker -> certificate/witness/report, same-key recovery and revocation; canonical SharedTuring -> shared THESEUS/OVID -> verified lineage -> durable lifecycle restart replay. Real local owner code, not enterprise SSO/approved production composition.

**Owner / external dependency:** Capacity and contract authority

**Final disposition:** PARTIAL

**Release impact:** Applicable mandatory acceptance remains open; no section-wide PASS inferred from unit/source evidence
