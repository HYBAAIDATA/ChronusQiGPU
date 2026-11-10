# HYBA product style guide

**Status:** Current internal product and design standard. Apply to product interfaces, prototypes, demos, product documentation, and client-facing materials. This guide supersedes conflicting older design or packaging recommendations in this repository.

## What the standard means for HYBA

HYBA adopts McKinsey-style strategic thinking and communication as the working method: begin with the core problem and decision, structure the analysis, test hypotheses against evidence, prioritize what matters, and communicate a clear conclusion and recommendation. Use issue trees or MECE structuring where useful, not as decoration. Surface assumptions, trade-offs, risks, evidence, and unknowns.

The finished product should feel like the integrated result of that strategic rigor and Accenture-grade product engineering, service design, integration, implementation, reliability, and polish—a hypothetical McKinsey–Accenture joint-venture quality bar. This is an internal aspiration only. HYBA does not claim affiliation, partnership, endorsement, or an actual joint venture with McKinsey or Accenture, and does not copy proprietary materials or marks.

Emulate **Stripe, Revolut, NVIDIA, and Google** as companies whose finished products set a bar for clarity, polish, usability, consistency, reliability, and execution. These are quality emulation benchmarks, not a description of HYBA’s target audience, customers, partnerships, or endorsements.

## HYBA identity and market boundaries

- The only market-facing companies are **HYBA Data** and **HYBA Security**.
- **Chronus is HYBA Data’s product/platform**, not a separate company.
- **AL HARAS is HYBA Security.**
- **Andre Taylor-Morris** is HYBA’s Founder and CEO.
- **Quantum is a capability**, not a separate market, company, or standalone product category. Describe it only as a capability within an offering when accurate and relevant.
- **Bitcoin mining is an in-house treasury activity**, not a customer product, service, or market offering.
- Do not invent additional company brands, market-facing business lines, product families, customer relationships, or commercial claims without direction from the owner and supporting evidence.

## What the products should look and feel like

### Shared experience

A HYBA product should not look like a generic cloud dashboard, crypto-mining console, or futuristic science-fiction interface. It should feel like a coherent, client-ready enterprise product: calm, precise, purposeful, visually disciplined, easy to navigate, and complete in its workflows.

A typical screen should make this sequence easy to understand:

1. **The question or task** the user is addressing.
2. **The answer or current state** in plain language.
3. **The evidence** behind it, including source and freshness.
4. **The next action or decision** available to the user.
5. **Technical detail** when needed, progressively disclosed.

### HYBA Data — Chronus

Chronus should look and behave as a polished data/computational product under HYBA Data. Lead with the user’s data or workload task and the outcome—not the mathematical novelty alone. Where the behavior is implemented, make the path from input or configuration through execution to result and supporting evidence understandable. Separate actual execution records from examples, simulations, and unverified capabilities. Do not present Chronus as a quantum or Bitcoin-mining product.

### HYBA Security — AL HARAS

AL HARAS should look and behave as a calm, trustworthy security product under HYBA Security. Make the security question, status meaning, evidence, responsible action, and audit trail clear. Use precise state labels and explain what is and is not covered. Only show controls, protections, certifications, or positive security outcomes when implemented and supported by evidence; never use a green shield or “secure” badge as decoration.

These product descriptions are design directions, not claims that the described workflows or capabilities are already shipped.

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
- [ ] The screen makes the task, answer/status, evidence, next action, and supporting detail clear.
- [ ] Quantum is framed only as a capability, where relevant.
- [ ] Bitcoin mining is not presented as a product or customer offering.
- [ ] Metrics, statuses, and examples are sourced and labeled accurately.
- [ ] Main and failure workflows, permissions, and recovery are represented.
- [ ] Accessibility, responsive behavior, and consistent components are addressed.
- [ ] No client, partner, endorsement, or affiliation is implied without evidence and authorization.
- [ ] The result meets the intended quality bar without overstating product maturity.
