# HYBA product style guide

**Status:** Current internal product and design standard. Apply to product interfaces, prototypes, demos, product documentation, and client-facing materials. This guide supersedes conflicting older design or packaging recommendations in this repository.

## Design ambition

HYBA’s working method and communication style should mirror **McKinsey-style strategic thinking**: start from the core problem, structure the analysis, test hypotheses against evidence, prioritize what matters, and communicate the conclusion and recommended action clearly. Use MECE issue structuring where it helps; do not force frameworks where they do not fit. Make the logic, assumptions, evidence, risks, and decisions easy to inspect. This is an internal quality direction, not a claim to use proprietary McKinsey material or to have a relationship with the firm.

The **finished product** should feel like the end result of a hypothetical **McKinsey–Accenture joint venture**: McKinsey-style strategic framing and analytical rigor realized through Accenture-grade product engineering, service design, integration, implementation, operational reliability, and polish. The JV comparison is an internal product-quality aspiration only. HYBA has no claimed affiliation, partnership, endorsement, or joint venture with McKinsey or Accenture. Do not use their logos or imply a relationship.

Emulate **Stripe, Revolut, NVIDIA, and Google** as benchmarks for the quality and finish of a completed product: clarity, polish, usability, consistency, reliability, and enterprise-grade execution. These are companies to emulate for product quality—not a description of HYBA’s target audience, customer base, partnerships, or endorsements. Do not use their names or logos in a way that implies a business relationship.

## Company and market boundaries

- The only market-facing companies are **HYBA Data** and **HYBA Security**.
- **Chronus is HYBA Data’s product/platform**, not a separate company.
- **AL HARAS is HYBA Security.**
- **Andre Taylor-Morris** is HYBA’s Founder and CEO.
- **Quantum is a capability**, not a separate market, company, or standalone product category. Describe it only as a capability within an offering when accurate and relevant.
- **Bitcoin mining is an in-house treasury activity**, not a customer product, service, or market offering.
- Do not invent additional company brands, market-facing business lines, product families, customer relationships, or commercial claims without direction from the owner and supporting evidence.

## Product experience principles

### 1. Lead with the problem, answer, and decision

State the user’s problem and the main answer or next action first. Organize supporting logic clearly, distinguish facts from assumptions, and make recommendations actionable. Avoid jargon-led introductions and speculative claims.

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

- Chronus is marketed as a HYBA Data product/platform, not as a third company.
- AL HARAS is HYBA Security.
- Name products only under HYBA Data or HYBA Security, and only when the product scope is documented and owner-approved.
- Treat quantum as a capability, not a separate market proposition.
- Treat Bitcoin mining as internal treasury activity, never as a product or customer use case.
- Do not present Stripe, Revolut, NVIDIA, Google, McKinsey, or Accenture as customers, partners, endorsers, or joint-venture parties without explicit, verifiable authorization.
- Do not imply production readiness, certification, security assurance, customer deployment, performance advantage, or market validation without current evidence. Follow the repository’s [claim audit](../claim-audit.md) and [release decision](../../RELEASE_DECISION_MCKINSEY_TECH.md).

## Review checklist

Before accepting a product or client-facing artifact, confirm:

- [ ] It clearly belongs to HYBA Data or HYBA Security; Chronus is identified as HYBA Data’s product/platform and AL HARAS as HYBA Security.
- [ ] The reasoning is problem-led, structured, evidence-based, prioritized, and clear about its recommendation.
- [ ] The finished experience integrates strategic clarity with robust engineering, service design, and delivery quality.
- [ ] Quantum is framed only as a capability, where relevant.
- [ ] Bitcoin mining is not presented as a product or customer offering.
- [ ] Metrics, statuses, and examples are sourced and labeled accurately.
- [ ] Main and failure workflows, permissions, and recovery are represented.
- [ ] Accessibility, responsive behavior, and consistent components are addressed.
- [ ] No client, partner, endorsement, or affiliation is implied without evidence and authorization.
- [ ] The result meets the intended quality bar without overstating product maturity.
