# Customer journeys: government, enterprise, hyperscaler

**Status: evidence-gated evaluation guidance. Not a product availability, deployment, security, compliance, capacity, or performance claim.**

This document supersedes the earlier version at this path. The earlier version described capabilities and measurements that are not established by the current repository review and must not be reused as customer evidence.

## Current evidence boundary

The repository claim audit records a **not release-qualified** posture. It identifies selected CPU reference workloads in source, but does not establish physical-GPU performance, a customer-ready compression path, GPU supply or rental service, memory tiering, customer deployments, regulatory authorizations, or service-level commitments. The four offerings below are evaluation concepts until their required artifacts exist. See [`docs/claim-audit.md`](claim-audit.md) for the dated source review.

The machine-readable journey and product data used by the console live in [`frontend/data/customer-journeys.json`](../frontend/data/customer-journeys.json). The interface is [`frontend/app/journeys/page.tsx`](../frontend/app/journeys/page.tsx). The content-governance suite is [`tests/test_customer_journey_governance.py`](../tests/test_customer_journey_governance.py).

## Claim charter

A customer-facing statement must be bounded by the build and evidence it refers to. Before release, require:

- **Performance:** workload and dataset description, baseline, hardware, software and driver versions, source commit, command, repetitions, raw output, and negative results. Show relevant median and tail percentiles and variance.
- **Capacity:** a numeric ceiling, identified supply source, measured time-to-provision, test method, failure behavior at the ceiling and next requested increment, availability definition, price basis, and remedies.
- **Compression:** tested data class, measured ratio, decompression verification for lossless mode, or a named error metric and test for bounded-loss mode.
- **Memory tiering:** a reproducible baseline out-of-memory failure, successful run, correctness check, latency delta, and throughput delta.
- **Security and compliance:** exact deployment boundary, control implementation and test evidence, assessor and assessment scope where applicable, open findings and remediation dates, and precise authorization status.
- **Every journey:** distinct procurement, security, and technical evaluation gates; visible limitations and refusals; no gate is passed by a presentation or an unsupported assertion.

If an artifact is missing, the response says so and does not substitute an estimate or roadmap for a measured result.

## Four evaluation concepts

| Concept | Current repository boundary | Evidence needed before a customer claim |
|---|---|---|
| Accelerator / iGPU | Selected CPU reference execution code is present; a physical-device result or workload speedup was not verified. | Customer workload, named device and driver, source commit, reproducible baseline and harness, raw results, repetitions, and wins and regressions. |
| Compression | A customer-ready compression path, ratio, verification, and error-bound test were not established. | Customer-approved data class, ratio, round-trip verification or bounded-loss error test, and reproducible artifact. |
| GPU rental and scaling | A vendor-backed supply source, live provisioning path, capacity, price, and service level were not verified. | Supply commitment, ceiling, provision time, availability, price per GPU-hour, limit behavior, and remedies. |
| Memory tiering | A validated tiering path and workload-specific memory and performance results were not established. | Baseline failure, successful run, correctness, latency and throughput deltas, and test environment. |

## Government journey

**Buying motion:** procurement and authorization precede production; mission fit and technical evidence are assessed separately.

| Phase | Decision owner and question | Evidence and exit gate |
|---|---|---|
| Market research / RFI | Program officer: does the scoped capability plausibly address a mission need? | Mission-first capability statement, data class, limitations and visible refusal list, downloadable benchmark artifact when one exists, and verifiable references or explicit absence. |
| Sources sought / RFP | Contracting officer: can the vendor respond to the solicitation as written? | Applicable SAM.gov or state/local registration; only held certifications with scope; pricing in the requested form; requirement-level comply / exception / does-not-comply matrix backed by evidence; verifiable past performance or explicit absence. |
| Technical evaluation | Technical evaluator: does the reviewed build work on approved data and agency hardware? | Live evaluator-driven sandbox or runnable harness, reproducible benchmark, build and environment details, limitations shared in advance, negative results, failure behavior, and engineer-led Q&A. |
| Security assessment / authorization | Security assessor: can this system boundary be authorized for the intended use? | System Security Plan in the requested format; applicable NIST SP 800-53 Rev. 5 or state-equivalent control matrix mapping controls to implementation, test, and owner; dated and scoped evidence; explicit system boundary and verified inherited controls; POA&M with owner and remediation date for each open item. State authorization status exactly. |
| Award / onboarding | Contracting and program owners: can the contracted and authorized configuration be deployed and supported? | Signed scope, staffable support commitments and remedies, deployment runbook, rollback plan for the first 30 days, support owner, response window, and escalation path. |
| Production / renewal | Program owner: does measured mission value support renewal? | Quarterly or contract-period customer-source value report, measurement window, complete incident record and post-incident actions, current authorization, renewal terms, and roadmap distinguishing commitments from possibilities. |

## Enterprise journey

**Buying motion:** a champion runs a bounded proof of concept; architecture, security, procurement, and the economic buyer each make an explicit decision.

| Phase | Decision owner and question | Evidence and exit gate |
|---|---|---|
| Discovery | Champion: is there a specific workload worth testing? | Problem-first overview, concise technical explanation, artifact only when available, and specific supported and unsupported cases. |
| Trial / POC | Champion and evaluator: does the scoped build work on approved customer data? | If offered, self-serve start with fixed workload, time, and data-volume scope; this is a launch requirement, not a claim that a trial is currently available. Use customer infrastructure or an approved sandbox; provide a customer-workload artifact and export, uninstall, and deletion steps. |
| Business case | Economic buyer: is value defensible from customer inputs? | Customer-populated template, assumptions, TCO including operations, integration and vendor fees, and neutral or negative cases. Candidate units may include GPU-hour, compressed terabyte, or measured workload outcome; state floor and ceiling and do not imply current prices are established. |
| Technical evaluation | Architect: does the build integrate and meet requirements? | Architecture, integration points, API schemas and error cases, SDK limits, reference deployment, supported and unsupported workloads, and benchmark harness and raw results for any performance statement. |
| Security review | Security owner: does the deployment meet requirements? | Evidence-backed questionnaire, data-flow and retention diagrams, named and scoped penetration-test report when available, DPA, subprocessor list, vulnerability-disclosure policy, software bill of materials, and explicit gaps. |
| Procurement / legal | Procurement: can both parties sign terms matching the tested service? | Standard contract with negotiated terms marked, measurable staffable SLA with remedies and exclusions, DPA, BAA if applicable, complete subprocessors, pricing, and applicable insurance certificate. |
| Deployment / renewal | Champion and buyer: does customer evidence justify expansion? | Deployment and rollback runbooks, support contact, customer-measured value and incidents, and expansion pricing using the original documented model. |

## Hyperscaler journey

**Buying motion:** a reproducible technical bake-off precedes capacity negotiations and production integration.

| Phase | Decision owner and question | Evidence and exit gate |
|---|---|---|
| Initial technical review | Technical evaluator: is the implementation scoped enough for a benchmark slot? | Technical brief no longer than two pages, named workload and hardware where evidence exists, support boundaries, refusal list, and a real engineer contact only if established. |
| Benchmark bake-off | Technical evaluator: how does the same workload compare under agreed conditions? | Evaluator-runnable harness, source commit, hardware and software versions, data and commands, raw output and repetitions, median and p50/p95/p99 where relevant, variance, failure modes at scale, near capacity, and under contention. |
| Capacity commitment | Capacity planner: can supply meet the requested quantity and schedule? | Numeric ceiling, named supply source, measured time-to-provision by tier, availability, price, failure behavior at the ceiling and next requested increment (N+1), and contractual remedies. |
| Integration / security | Engineering and security: can the evaluated build integrate within the accepted boundary? | API, SDK, reference architecture, data flow, scoped security evidence and gaps, engineer support owner, rollback, and joint escalation path. |
| Procurement | Commercial owner: do terms match verified performance and supply? | Contracted quantities, price, measurable service levels, exclusions, remedies, named support owners, assumptions, source-of-supply confirmation, and change control. |
| Production / expansion | Engineering leadership: do production measurements justify expanding? | Quarterly customer-workload value report, source window, complete incidents and post-mortems, service-level results, capacity use, supply confirmation, and roadmap separating commitments from possibilities. |

## Shared trust artifacts and present status

| Artifact | Current status in this repository review | Evidence required for a customer-facing commitment |
|---|---|---|
| Claim audit page | `docs/claim-audit.md` exists as a dated static review, not a live claim service. | Current claim, source commit, method, artifact, limitations, and reviewer. |
| Benchmark artifact library | A complete commit-linked physical-hardware library was not established. | Runnable harness, workload and hardware identifiers, software versions, commands, raw results, repetitions, and independent reproduction. |
| Limitations and refusal page | The new console page states product-specific evidence gaps and non-claims; it is not a complete feature or risk register. | Specific unsupported workloads, failure modes, dependencies, customer-visible refusals, and scope boundaries. |
| Incident log | A complete customer-facing incident log was not established. | Dated incidents, impact, remediation, and post-incident review with confidentiality controls. |
| Release charter | Current posture is not release-qualified. | Current release gates, commit-linked test results, scope, reviewers, and applicable authorizations. |
| Service status | A readiness endpoint exists in source; production monitoring, uptime, and an SLA are not established by that endpoint. | Operational monitoring, measurement windows, incident handling, and contractual definitions. |
| Named technical contact | A named customer-facing engineering contact was not established in the reviewed repository content. | A real owner, role, response path, and staffed escalation commitment. |

## Acceptance tests

Run the standard-library-compatible content checks with `python -m unittest tests.test_customer_journey_governance -v`. They verify:

1. Exactly one government, enterprise, and hyperscaler journey, all with procurement, security, and technical-evaluation gates.
2. Every phase has a decision question, required evidence, an exit criterion, and at least one gate.
3. Product status, required artifacts, and visible customer refusals for all four concepts.
4. Government RFI/RFP, technical evaluation, SSP/control matrix/POA&M, onboarding, production, and renewal requirements.
5. Enterprise trial, business-case, technical, security, procurement, and renewal requirements.
6. Hyperscaler brief, p50/p95/p99 and variance, capacity ceiling, supply, N+1 behavior, procurement, and production requirements.
7. Seven shared trust artifacts with current status and required evidence.
8. Customer-facing copy avoids the disallowed superlatives and unverified numeric speedup claims.
9. The console and documentation use the same machine-readable journey source.

These are content and policy checks. They do not qualify software behavior, validate security controls, prove service operation, or establish performance.
