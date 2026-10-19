> Scope amendment from the user: billing is on hold. The intended model is usage-based and Hermitten will not be used. Original billing requirements below are preserved as historical input, not current acceptance gates. See ACCEPTANCE_REGISTER.md.

The brief should position TURING as an institutional-grade computational intelligence product, not a generic SaaS dashboard, quantum-themed website, or conventional AI chatbot.

The design ambition is Apple-level product clarity, IBM-level engineering credibility, Google-level interaction quality, McKinsey-level executive communication, Gartner-level analytical rigour, and Pentagram-level visual identity. Those are design benchmarks, not claims of affiliation or endorsement.

The most important instruction to the agent is to build a complete, working product experience grounded in the existing TURING implementation and actual service capabilities—not merely a beautiful landing page or a collection of dashboard mockups.

Below is the master implementation prompt, designed to be passed directly to your coding agent.

Writing

# MASTER AGENT BRIEF — TURING

## World-Class Computational Intelligence Platform: Product Strategy, Brand, Frontend, Enterprise Administration, Provisioning, and Commercialisation

**Role:** Act as a combined principal product architect, world-class product designer, design systems lead, senior Next.js/TypeScript engineer, enterprise platform architect, computational intelligence product strategist, commercial product manager, security engineer, and go-to-market lead.

**Mission:** Transform TURING into an exceptional, enterprise-ready computational intelligence product with a coherent brand, sophisticated user experience, production-quality frontend, customer administration, service provisioning, commercial entitlements, and a credible path to market.

This is a product-defining initiative. Treat the standard of execution as exceptionally high. Every architectural decision, interaction, word, screen, and operational workflow must withstand scrutiny from demanding enterprise buyers, technical reviewers, researchers, legal and compliance teams, and sophisticated investors.

Do not respond with another advisory document or a list of proposed improvements. Inspect the existing repository, understand what is implemented, develop an evidence-based plan, and execute the appropriate work.

---

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