# Agent instructions for Chronusv2

These are mandatory repository-wide instructions for all agents and subagents. They apply to research, engineering, audits, testing, remediation, release, product design, frontend implementation, prototypes, demos and documentation.

## Mandatory execution assurance — all agents, all assignments

**Normative status: REQUIRED.** These rules apply to every agent and subagent working on this repository: engineering, research, audit, QA, remediation, review, documentation, release and delegated work. Read this file before substantive work, apply it throughout the assignment and pass these obligations to every delegate. More specific local safeguards remain binding; they may strengthen but never weaken this protocol. Follow higher-priority platform constraints and authorised owner scope. Do not change architecture, contracts, acceptance criteria or protected research without explicit authority.

### 1. Assignment and baseline gate

- Preserve the original assignment and every explicit requirement, constraint, prohibition, deliverable and acceptance criterion. Break compound requirements into independently checkable obligations without reducing scope. Record a stable assignment ID, original text or immutable reference and digest, and obligation IDs with exact source wording. Record dependencies, required evidence, responsible agent and acceptance test for each obligation.
- For repository work establish the repository, current authoritative ref and full commit SHA from Git, not recollection. Record the working ref, relevant PRs (merged and outstanding), applicable contracts, tooling and accessible authoritative sources. Inspect the repository and actual implementation before proposing changes or conclusions. Historical memory is a discovery lead, never proof about current code.
- Match the discovery scope to the actual assignment. For exhaustive work, enumerate the full relevant tracked tree, entry points, implementations and variants, datasets, configurations, dependencies, callers and consumers, tests, benchmarks, contracts, open/merged relevant PRs, and referenced authoritative external records. Include legacy or alternate implementations when relevant; record reasons for exclusions. Use independent inventory methods (tree listing, code search, import/call tracing, test collection and PR diffs) rather than searching only for names in the brief. Follow pagination and references to exhaustion, or record the precise unexamined scope.
- Reconcile in both directions: requirement -> implementation/evidence and discovered implementation/data -> requirement/contract/evidence. Investigate orphaned components, missing requirements, wiring, version drift and conflicts. Do not form definitive conclusions before the applicable discovery obligations are satisfied.

### 2. Execution and evidence gate

- Perform the assigned work, not merely a plan, checklist, matrix, document review or recommendations. Execute every applicable inspection, acceptance test, paired benchmark, integration check and authorised remediation required by the assignment. Verify changes and rerun affected gates. Do not request repeated approval for work already authorised; do not silently expand scope.
- Retain attributable, reproducible evidence: source commit and exact paths/line ranges or immutable references; command, working directory, inputs, environment, timestamp, exit status, raw output or durable artifact reference and digest for executed checks; actual measured results and units; and before/after evidence for remediation. Record individual test outcomes and skips, not merely a green aggregate. Distinguish inspection from execution and local from remote observation.
- Never invent, backfill, embellish or silently reuse measurements as current evidence. Test presence is not test execution. Documentation is not implementation. Implementation is not integration. A merged change or green CI is not deployment or production qualification. Device discovery is not hardware execution. Controlled test fixtures cannot establish live outcomes. Follow exactness, evidence, naming, security and claim gates already in force.
- Preserve the architecture authority boundaries and existing contracts; keep evidence in the designated custody path where available. Never alter expected results, tests, baseline, evidence, security controls or acceptance conditions merely to obtain a pass.
- If a check cannot be performed, record the exact obligation, attempted action and observed blocker, missing evidence, impact, outstanding work and owner/dependency. Use UNAVAILABLE or BLOCKED as appropriate. Continue all other authorised work. Resource, time, context and access limits do not authorise silent omission, fabricated evidence or premature completion.

### 3. Machine-readable execution record

Maintain an obligation ledger throughout substantive multi-step work, in the assignment's authorised evidence store or handover artifact. For small tasks an equivalent compact record is sufficient; never impose unrelated production checks or omit applicable ones. The record MUST include:

- assignment ID, immutable original brief/digest, authoritative baseline SHA, working SHA/ref, scope and discovery inventory with explicit exclusions;
- each original obligation ID, exact requirement, applicability, source/contract links, owner, evidence required, execution status, observed result, evidence references/digests, blocker and QC decision;
- reverse inventory cross-reference, unresolved items, changed paths, test/benchmark receipts, relevant PR and CI references, and distinct final verdicts for execution, evidence, technical compliance, QC and qualification.

Execution states: NOT_STARTED, IN_PROGRESS, EXECUTED, BLOCKED or NOT_APPLICABLE. NOT_APPLICABLE requires a reason grounded in the original assignment and independent review for formal qualification. Technical result states: PASS, FAIL, UNAVAILABLE or NOT_APPLICABLE. EXECUTED with a technical FAIL can complete an audit obligation but cannot pass a failed technical or remediation acceptance criterion. Missing evidence is never PASS.

### 4. Independent acceptance and fail-closed handover

- For formal audits, release/production qualification, multi-agent delivery and other assignments requiring independent acceptance, a separate reviewer must compare the original brief (not the executor's summary), obligation ledger, inventory and raw evidence against the exact reviewed commit. Verify bidirectional coverage, actual execution, remediation and authority boundaries; independently replay or sample where justified by the acceptance criteria. Record reviewer identity, reviewed SHA, evidence references, uncovered obligations and ACCEPTED/REJECTED/PENDING. The executing agent may not be its own independent reviewer. Delegation does not discharge the lead agent's responsibility.
- For routine changes, perform the applicable self-checks and use the repository's existing review and CI controls; never claim independent review where it did not occur. Do not bypass required checks, change protected settings, merge without required approval or treat a review request as approval.
- Completion is a derived state, not an agent assertion. Before asserting COMPLETE, verify every applicable obligation is executed with the required evidence and any required independent acceptance is recorded against the same revision; no unaccounted inventory item, missing required receipt or unresolved required obligation may remain. If an obligation requires remediation or passing a test, a documented failure does not satisfy it. An audit that fully executes its required checks may legitimately conclude NOT QUALIFIED.
- Where an external deterministic completion validator is available, use it and retain its result; where it is unavailable, state that explicitly and do not claim mechanical enforcement. A failed validator or missing mandatory independent acceptance prevents COMPLETE. Preserve separate assignment, evidence, contract, QC and production verdicts.
- On interruption or exhaustion, provide a truthful INCOMPLETE or BLOCKED handover with the baseline, verified findings, precise outstanding obligation ledger and evidence references. Resume from this record rather than starting from assumptions. Do not substitute a polished report for work, report partial results as exhaustive, or declare completion while knowing mandatory work remains.
- Include the execution/acceptance verdict and outstanding obligations in the final handover and applicable PR description. Any reviewer finding omitted work must return it for execution, not approve it with a narrative excuse. Only an explicit authorised owner change to the original assignment may amend its scope; retain the change and its provenance.

## Read first

Before product or UX work, read:

- [`docs/directives/PRODUCT_STYLE_GUIDE.md`](docs/directives/PRODUCT_STYLE_GUIDE.md) — canonical product design and HYBA positioning standard.
- [`docs/directives/FRONTEND.md`](docs/directives/FRONTEND.md) — frontend implementation rules.
- [`docs/directives/PACKAGING.md`](docs/directives/PACKAGING.md) — product and market boundaries.
- [`docs/claim-audit.md`](docs/claim-audit.md) and [`STATUS.md`](STATUS.md) — current evidence and release limits.

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
