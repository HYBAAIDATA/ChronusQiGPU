# HYBA product style guide

**Status:** Current internal product and design standard. Apply to product interfaces, prototypes, demos, product documentation, and client-facing materials. This guide supersedes conflicting older design or packaging recommendations in this repository.

## Design ambition

Build products with the strategic clarity, analytical discipline, and executive communication associated with top-tier management consulting, combined with the enterprise technology delivery quality, service design, and implementation discipline of a leading technology consultancy. The internal shorthand is **“a McKinsey–Accenture joint-venture standard.”** It describes an aspiration for quality only: HYBA has no claimed affiliation, partnership, endorsement, or joint venture with McKinsey or Accenture. Do not use either firm’s logos or imply a relationship.

Design for the expectations of demanding enterprise clients—for example, organizations like **Stripe, Revolut, NVIDIA, and Google**. These are reference audiences, not statements that they are HYBA customers, partners, or endorsers. Do not use their names or logos in a way that implies a business relationship.

## Company and market boundaries

- The only market-facing companies are **HYBA Data** and **HYBA Security**.
- **Andre Taylor-Morris** is HYBA’s Founder and CEO.
- **Quantum is a capability**, not a separate market, company, or standalone product category. Describe it only as a capability within an offering when accurate and relevant.
- **Bitcoin mining is an in-house treasury activity**, not a customer product, service, or market offering.
- Do not invent additional company brands, market-facing business lines, product families, customer relationships, or commercial claims without direction from the owner and supporting evidence.

## Product experience principles

### 1. Lead with the client’s decision or task

State the user, problem, outcome, and next action plainly. Put the main conclusion or action first; move supporting detail into a clear hierarchy. Avoid jargon-led introductions and speculative claims.

### 2. Make evidence visible

Every important metric or status must have a defined source, unit, timestamp or measurement window, and meaning. Distinguish measured, estimated, simulated, illustrative, unavailable, and unverified information. Never make a mockup look like live telemetry.

### 3. Design complete enterprise workflows

Show the full user journey: prerequisites, permissions, inputs, progress, success, failure, recovery, audit trail, and support path. Controls must do what their labels promise. Explain consequential actions and require confirmation for destructive operations.

### 4. Make complex systems understandable

Use progressive disclosure: a concise executive view first, with inspectable technical detail for operators. Prefer explanatory diagrams and comparisons over decoration. Clearly separate capability, implementation status, and independently verified evidence.

### 5. Use a calm, precise visual system

Use consistent typography, spacing, layout, color, iconography, charts, and interaction patterns across products. Favor legibility, restraint, strong hierarchy, and purposeful whitespace. Color must have consistent meaning and never be the only signal. Support responsive layouts, keyboard operation, and accessible contrast.

### 6. Deliver enterprise-grade fit and finish

Design loading, empty, stale, error, permission-denied, offline, and degraded states—not only the happy path. Keep navigation and terminology consistent. Do not ship dead controls, fabricated data, unexplained placeholders, or visually polished screens disconnected from actual product behavior.

## Language and claims

- Name products only under HYBA Data or HYBA Security, and only when the product scope is documented and owner-approved.
- Treat quantum as a capability, not a separate market proposition.
- Treat Bitcoin mining as internal treasury activity, never as a product or customer use case.
- Do not present Stripe, Revolut, NVIDIA, Google, McKinsey, or Accenture as customers, partners, endorsers, or joint-venture parties without explicit, verifiable authorization.
- Do not imply production readiness, certification, security assurance, customer deployment, performance advantage, or market validation without current evidence. Follow the repository’s [claim audit](../claim-audit.md) and [release decision](../../RELEASE_DECISION_MCKINSEY_TECH.md).

## Review checklist

Before accepting a product or client-facing artifact, confirm:

- [ ] It clearly belongs to HYBA Data or HYBA Security; no extra market-facing company is implied.
- [ ] Quantum is framed only as a capability, where relevant.
- [ ] Bitcoin mining is not presented as a product or customer offering.
- [ ] The primary user, task, and outcome are clear.
- [ ] Metrics, statuses, and examples are sourced and labeled accurately.
- [ ] Main and failure workflows, permissions, and recovery are represented.
- [ ] Accessibility, responsive behavior, and consistent components are addressed.
- [ ] No client, partner, endorsement, or affiliation is implied without evidence and authorization.
- [ ] The result meets the intended consulting-grade clarity and enterprise technology delivery standard without overstating product maturity.
