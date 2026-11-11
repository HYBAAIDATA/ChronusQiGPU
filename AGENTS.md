# Agent instructions for Chronusv2

These are repository-wide instructions for coding and documentation agents. Apply them to product design, frontend implementation, prototypes, demos, and product or client-facing writing.

## Read first

Before product or UX work, read:

- [`docs/directives/PRODUCT_STYLE_GUIDE.md`](docs/directives/PRODUCT_STYLE_GUIDE.md) — canonical product design and HYBA positioning standard.
- [`docs/directives/FRONTEND.md`](docs/directives/FRONTEND.md) — frontend implementation rules.
- [`docs/directives/PACKAGING.md`](docs/directives/PACKAGING.md) — product and market boundaries.
- [`docs/claim-audit.md`](docs/claim-audit.md) and [`RELEASE_DECISION_MCKINSEY_TECH.md`](RELEASE_DECISION_MCKINSEY_TECH.md) — current evidence and release limits.

If older project notes conflict with these current instructions, follow the current style guide and release/evidence documents. Do not silently revive superseded claims.

## HYBA identity and product map

- The two market-facing companies are **HYBA Data** and **HYBA Security**.
- **Chronus is a HYBA Data product/platform**, not a separate company.
- **AL HARAS is HYBA Security.**
- **Andre Taylor-Morris is HYBA’s Founder and CEO.**
- Quantum is a capability, not a separate company, market, or standalone product category.
- Bitcoin mining is an in-house treasury activity, not a customer product or service.
- Do not invent other companies, product lines, markets, partnerships, customers, or business claims without explicit owner direction.

## Quantum package boundaries and evidence

- **TURING** (`packages/turing`) is HYBA Data's first-principles, finite-dimensional quantum-mathematics library over complex Hilbert spaces. It is a mathematical foundation, not a new company, market, hardware SDK, physical-device simulator, or evidence of quantum advantage.
- Keep TURING's mathematical core distinct from Chronus's existing quantum-labelled code. Do not wrap, rename, or re-export legacy code in a way that suggests it has been validated as TURING or as conventional quantum mechanics.
- Treat existing non-TURING quantum-labelled modules as legacy computational research: classify them accurately as finite-field/algebraic models, simulations, quantum-inspired algorithms, or classical systems as source inspection supports. A quantum-themed name or test count is not evidence of physical quantum semantics.
- The currently reviewed `src/chronus/quantum` namespace uses finite-field/algebraic constructions and proxy measures; it is not the canonical complex-Hilbert-space implementation. See [`docs/system-update/quantum-package-taxonomy.md`](docs/system-update/quantum-package-taxonomy.md).
- Do not claim quantum advantage, hardware execution, physical fidelity, cryptographic/security conformance, or release qualification without independent, current, reproducible evidence tied to an exact source commit.
- Preserve explicit mathematical conventions, numerical tolerances, clear failure modes, and tests of the defining axioms when extending TURING. Keep simulator/backend concerns separate from its mathematical core.

## How to think and communicate

Use a McKinsey-style problem-solving and communication approach:

1. Start from the user’s problem and the decision that needs to be made.
2. Structure the problem and analysis; use issue trees or MECE grouping when useful, not as decoration.
3. Test hypotheses against evidence. Separate facts, assumptions, unknowns, and recommendations.
4. Prioritize the few findings that change the decision. Lead with the conclusion and a clear next step.
5. Make reasoning, sources, trade-offs, risks, and limitations easy to inspect.

Do not imitate proprietary materials or imply a relationship with McKinsey.

## What products should feel like

The finished product should feel like the integrated result of McKinsey-style strategic rigor and Accenture-grade product engineering, service design, integration, implementation, reliability, and finish—a hypothetical McKinsey–Accenture joint-venture quality bar, not an actual relationship.

Emulate **Stripe, Revolut, NVIDIA, and Google** as companies whose finished-product clarity, usability, consistency, reliability, and polish are quality benchmarks. They are not a target-audience label or a claim of customer, partner, or endorsement status. Do not use company logos or imply a relationship.

### HYBA Data: Chronus

Design Chronus as a precise, polished data/computational product. The experience should help users understand the work they are doing, move through a coherent workflow, inspect outcomes, and see supporting evidence. Prefer the sequence **problem or input → configured work → actual execution state → result → evidence and next action**. Show only steps and data supported by implemented behavior. Do not brand Chronus as a quantum product or a Bitcoin-mining product.

### HYBA Security: AL HARAS

Design AL HARAS as a calm, trustworthy security product. Make the security question, current evidence, status meaning, responsible action, and audit trail clear. Security states and controls must be backed by actual implementation and evidence. Do not invent protections, certifications, assurance badges, or successful status indicators.

These are product-design directions, not claims that these workflows or capabilities are already shipped.

## Build and content rules

- Prefer one clear user question or decision per screen; show the conclusion/status, evidence and timestamp, next action, then technical detail as needed.
- Build complete states: loading, empty, stale, unavailable, denied, degraded, failed, success, and recovery.
- Use a shared, accessible design system across HYBA products while preserving the distinct identity of Chronus and AL HARAS.
- Every control must be functional, permission-aware, and connected to the actual system state. Do not present mock data as live.
- Label metrics with units, source, time window, and whether they are measured, estimated, simulated, or illustrative.
- Avoid decorative dashboards, unsupported green “PASS” states, fake telemetry, generic crypto/mining imagery, and unexplained technical jargon.
- Do not claim production readiness, security effectiveness, compliance, customer use, or performance without current, commit-linked evidence.

## Completion check

Before finishing a product-facing change, confirm that it:

- follows the HYBA identity map above;
- applies structured, evidence-led reasoning and recommendation-first communication;
- translates that reasoning into complete, polished, enterprise-grade workflows;
- distinguishes design aspiration from implemented capability and verified evidence;
- preserves accessibility, responsive behavior, permissions, and error/recovery states; and
- makes no unsupported customer, partnership, security, performance, or release claim.
