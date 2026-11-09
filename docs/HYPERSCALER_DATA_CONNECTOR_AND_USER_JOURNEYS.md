# Customer journeys: government, enterprise, hyperscaler

**Status: evidence-gated evaluation guidance. Not a product availability, deployment, security, compliance, capacity, or performance claim.**

This document supersedes the earlier version at this path. The earlier version described capabilities and measurements that are not established by the current repository review and must not be reused as customer evidence.

## Current evidence boundary

The repository claim audit records a **not release-qualified** posture. It identifies selected CPU reference workloads in source, but does not establish physical-GPU performance, a customer-ready compression path, GPU supply or rental service, memory tiering, customer deployments, regulatory authorizations, or service-level commitments. The four offerings below are evaluation concepts until their required artifacts exist. See [`docs/claim-audit.md`](claim-audit.md) for the dated source review.

The machine-readable journey and product data used by the console live in [`frontend/data/customer-journeys.json`](../frontend/data/customer-journeys.json). The interface is [`frontend/app/journeys/page.tsx`](../frontend/app/journeys/page.tsx).

## Claim charter

A customer-facing statement must be bounded by the build and evidence it refers to. Before release, require:

- **Performance:** workload and dataset description, baseline, hardware, software and driver versions, source commit, command, repetitions, raw output, and negative results.
- **Capacity:** a numeric ceiling, identified supply source, measured time-to-provision, test method, failure behavior, availability definition, price basis, and remedies.
- **Compression:** tested data class, measured ratio, decompression verification for lossless mode, or a named error metric and test for bounded-loss mode.
- **Memory tiering:** a reproducible baseline out-of-memory failure, successful run, correctness check, latency delta, and throughput delta.
- **Security and compliance:** exact deployment boundary, control implementation evidence, assessor and assessment scope where applicable, and precise authorization status.
- **Every journey:** distinct procurement, security, and technical evaluation gates; no gate is passed by a presentation or an unsupported assertion.

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
| Market research / RFI | Program officer: does the scoped capability plausibly address a mission need? | Mission problem, limitations, current claim audit, and reproducible artifacts where they exist. References are either verifiable or explicitly not established. |
| Sources sought / RFP | Contracting officer: can the vendor respond to the solicitation as written? | Accurate registrations and certifications, requirement-level compliance matrix, supported pricing, and verifiable past performance or explicit absence. Every item has a disposition. |
| Technical evaluation | Technical evaluator: does the reviewed build work on approved data and in the agency environment? | Evaluator-controlled plan, versioned build, environment, command, raw results, limitations, failure behavior, and engineer-led technical Q&A. The evaluator can reproduce the scoped result. |
| Security assessment / authorization | Security assessor: can this specific system boundary be authorized? | System boundary, data flows, required control mappings and evidence, scoped assessment, findings, owners, remediation, and exact authorization status. |
| Award / onboarding | Contracting and program owners: can the contracted and authorized configuration be deployed and supported? | Signed scope, measurable commitments and remedies, deployment and rollback runbooks, staffed support, and a deployment matching the reviewed boundary. |
| Production / renewal | Program owner: does measured mission value support renewal? | Customer-source value reports, incidents and post-incident actions, current authorization, and renewal terms. |

## Enterprise journey

**Buying motion:** a champion runs a bounded proof of concept; architecture, security, procurement, and the economic buyer each make an explicit decision.

| Phase | Decision owner and question | Evidence and exit gate |
|---|---|---|
| Discovery | Champion: is there a specific workload worth testing? | Short implementation overview, scope boundaries, known gaps, and benchmark artifact only where available. Agree on a testable workload. |
| Trial / POC | Champion and evaluator: does the scoped build work on approved customer data? | Written workload, time and data scope; customer infrastructure or approved sandbox; reproducible report; export, uninstall, and deletion steps. Customer can reproduce the result and recover or delete its data. |
| Business case | Economic buyer: is the value defensible from customer inputs? | Trial measurements, explicit assumptions, operational costs, pricing basis, and sensitivity to neutral or negative results. The buyer can reproduce the calculation. |
| Technical evaluation | Architect: does the evaluated build integrate and meet the workload requirement? | Architecture and data flows, API and SDK errors and limitations, harness and raw results for performance statements. Architect accepts the scoped design and results. |
| Security review | Security owner: does the proposed deployment meet requirements? | Evidence-backed questionnaire, data flow and retention, subprocessors, available scoped assessments, vulnerability handling, and explicit gaps. Accept or mitigate the documented risk. |
| Procurement / legal | Procurement: can both parties sign terms that match the tested service? | Contract, bounded pricing, measurable commitments and remedies only if staffable, data terms, subprocessors, and applicable insurance evidence. |
| Deployment / renewal | Champion and buyer: does customer evidence justify expansion? | Runbook and rollback, ongoing customer measurements, incidents, and pricing consistent with the original model. Expansion follows a scoped review. |

## Hyperscaler journey

**Buying motion:** a reproducible technical bake-off precedes capacity negotiations and production integration.

| Phase | Decision owner and question | Evidence and exit gate |
|---|---|---|
| Initial technical review | Technical evaluator: is the implementation sufficiently scoped for a benchmark slot? | Concise brief, source boundary, supported and unsupported workload classes, and a real technical owner where one is established. Agree on a workload and baseline. |
| Benchmark bake-off | Technical evaluator: how does the same workload compare under agreed conditions? | Evaluator-runnable harness, source commit, hardware and software versions, commands, dataset description, raw results, repetitions, tail distribution where relevant, variance, and failure modes. Evaluator reproduces the result. |
| Capacity commitment | Capacity planner: can supply meet the requested quantity and schedule? | Numeric ceiling, named supply source, measured provisioning time, price, availability, behavior at the limit, and remedies. Commitment matches confirmed supply. |
| Integration / security | Engineering and security: can the evaluated build integrate within the accepted risk boundary? | API, SDK, reference architecture, data flow, scoped security evidence and gaps, rollback, support owner, and escalation path. Both owners accept the plan before production. |
| Procurement | Commercial owner: do contract terms match measured results and confirmed supply? | Quantities, price, service levels, exclusions, remedies, named support owners, assumptions, and change control. The contract stays within technical and supply evidence. |
| Production / expansion | Engineering leadership: do production measurements justify expanding? | Customer workload reports with source window, incidents and post-mortems, service-level results, and renewed supply confirmation. Expansion stays within the measured operating envelope. |

## Shared trust artifacts and their present status

| Artifact | Current status in this repository review | Evidence required for a customer-facing commitment |
|---|---|---|
| Claim register | `docs/claim-audit.md` exists as a dated static review, not a live claim service. | Current claim, source commit, method, artifact, limitations, and reviewer. |
| Benchmark library | A complete commit-linked physical-hardware library was not established. | Runnable harness and raw, scoped, reproducible artifacts. |
| Limitations register | This document and the claim audit record evidence gaps; keep both aligned to source changes. | Specific unsupported workloads, dependencies, failure modes, and boundaries. |
| Incident record | A complete customer-facing incident log was not established. | Dated incident, impact, remediation, and post-incident review with confidentiality controls. |
| Release / assurance record | Current posture is not release-qualified. | Current release gates, commit-linked tests, scope, reviewers, and applicable authorizations. |
| Service status | A readiness endpoint exists in source; production monitoring, uptime, and an SLA are not established by that endpoint. | Operational monitoring, measurement windows, incident handling, and contract definitions. |
| Technical contact | A named customer-facing engineering contact was not established in the reviewed repository content. | Real owner, role, response path, and staffed escalation commitment. |

## Acceptance tests

`tests/test_customer_journey_governance.py` enforces the content-level gates below:

1. Exactly one government, enterprise, and hyperscaler journey is present.
2. Each journey has procurement, security, and technical-evaluation gates.
3. Every phase contains a buyer question, evidence list, and exit criterion.
4. The four evaluation concepts state current evidence boundaries and required artifacts.
5. Seven shared trust artifacts carry explicit current status and required evidence.
6. The customer-facing data contains no prohibited superlative phrasing or unsupported numeric speedup claims.

These are documentation and content-governance checks. They do not qualify the software, validate security controls, prove service operation, or establish performance.
