# Onboarding Phase 0 — gap analysis

**Status: accepted.** Review basis: repository commit `9f0985775a11022f013ae6a993cc90c02cf747b2`. This is a static source review, not a build, test run, deployment check, or CI verification. The branch carrying this document was created from `8fddfd17eb776a95e0eec1d1514dd48290c905b4`; the original review was not revalidated against that later commit.

## Current common path

No separate onboarding flow for any of the four customer types was found in the reviewed frontend. The home page is a platform-readiness overview; `/ciaas` is a tenant-operations page that explicitly says it does not demonstrate end-to-end cloud provisioning or customer identity lifecycle. The evidenced common path is API-level tenant creation: a generic tenant endpoint, or an instant endpoint driven by a contract/admin or signed webhook. The instant request is contract- and capacity-allocation-oriented; tests cover generic tenant creation and instant provisioning, not four distinct customer journeys or their required artifacts.

## Data centre operators

**Currently takes:** The generic tenant/API path, then generic workload or capacity operations if provisioned. No data-centre-specific onboarding sequence was found.

**Should take:** Sign in; select data classes; upload representative samples or choose vendor samples; receive a per-class measured report; download and run the harness on their hardware; start a scoped pilot with rollback; deploy to a subset with a production report; expand based on measured value.

| Gap and affected screen, document, or flow | Rating |
| --- | --- |
| No data class selection or representative sample upload screens; no sample-per-class path. | BLOCKER |
| No measured report screen or artifact showing per-class ratio, p50/p95/p99 latency, write amplification, recovery time, and artifact ID. | BLOCKER |
| No harness download/instructions flow to reproduce results on customer hardware. | BLOCKER |
| No pilot flow with scope, rollback procedure, and exit report. | BLOCKER |
| Generic capacity allocation/scaling is not a production deployment report or measured-value expansion flow. | BLOCKER |

## Hyperscalers

**Currently takes:** The generic tenant/API path. Existing workload/API surfaces do not establish a self-service bake-off on customer hardware or a verifiable capacity commitment.

**Should take:** Sign in; select or upload workload definitions; download the reproducible harness; run a bake-off and commit results as artifacts; review capacity commitment, named supply source, provisioning time, SLA and remedies; integrate using SDK/reference architecture and a joint escalation path; enter production with a report on their workloads.

| Gap and affected screen, document, or flow | Rating |
| --- | --- |
| No workload selection/definition upload screen for this onboarding journey. | BLOCKER |
| No customer-runnable harness download flow or committed bake-off results artifact. | BLOCKER |
| No verifiable capacity commitment document naming supply source, capacity tiers, time-to-provision, SLA, and remedies. | BLOCKER |
| No onboarding integration screen/document packaging the SDK, reference architecture, and joint escalation path. | BLOCKER |
| No production report tied to the customer's own workloads. | BLOCKER |

## Enterprise

**Currently takes:** A generic tenant-creation path; the enterprise-labelled test checks tenant creation and retrieval. The instant path is contract/admin-oriented, not a self-serve trial-first journey.

**Should take:** Sign in; select a use case; start a scoped self-serve trial on customer data or a sandbox; receive a trial artifact; use a pre-filled business-case template; review integration/security materials; sign a contract with SLA remedies and DPA; deploy using a runbook.

| Gap and affected screen, document, or flow | Rating |
| --- | --- |
| No use-case selection screen or self-serve trial that can start before contracting. | BLOCKER |
| No trial artifact on customer data or business case template pre-filled from that artifact. | BLOCKER |
| No packaged integration screen with API docs, reference architecture, security questionnaire, and SBOM. | BLOCKER |
| No trial-to-contract sequence or contract screen with SLA remedies, DPA, and subprocessor list. | BLOCKER |
| No deployment runbook screen with rollback and support contact. | BLOCKER |

## Government

**Currently takes:** The generic tenant/API path. Governance-related surfaces do not establish a guided procurement dossier or a customer-assessor workflow. Repository documentation also warns that some provisioning/status data is local, simulated, or static; that is not evidence of a completed security or compliance assessment.

**Should take:** Sign in; review the RFI response and its limits; review a requirement-by-requirement compliance matrix; run the technical sandbox evaluation; review dated, scoped security evidence; assemble a pre-staged ATO package; deploy using a runbook and support SLA.

| Gap and affected screen, document, or flow | Rating |
| --- | --- |
| No onboarding RFI response screen linking artifacts, does-not-do statements, and references or stated absence. | BLOCKER |
| No compliance matrix flow mapping each requirement to comply/exception/does not comply with evidence. | BLOCKER |
| No driveable technical evaluation sandbox flow with harness, refusal list, and engineer Q&A booking. | BLOCKER |
| No dated, scoped security evidence workflow for SSP, control matrix, system boundary, evidence packages, and POA&M dates. | BLOCKER |
| No pre-staged ATO package or government production deployment runbook/support SLA flow. | BLOCKER |

## Prioritized shared gaps

### Blockers

- Four distinct onboarding journeys and their customer-specific artifacts are absent from the reviewed onboarding surface.
- The shared artifact pipeline, content-addressed customer measurement artifacts, and `/claims` links from claims to evidence are not established by the reviewed flow.
- The requested `/refusals`, named-human `/contact`, and blameless `/incidents` surfaces were not found in the reviewed frontend routes. The home-page readiness probe is not, by itself, the requested real-time `/status` service.
- API token issuance exists, but the reviewed onboarding flow does not provide SSO/MFA setup per customer policy.
- Provisioning and settlement/status claims need verified operational evidence: the repository's current-state assessment describes local/simulated provisioning and demo/static status data, not live customer provisioning or measured operations.

### Friction

- The available route is generic and API-led; the instant path is contract/admin or webhook-oriented. Customers lack a segment-specific entry point and cannot follow their intended evaluation sequence through the reviewed UI.

### Cosmetic

- None prioritized. Missing flows and evidence artifacts are functional gaps; visual polish follows them.

## Sequencing

1. Phase 1 — shared infrastructure: verified auth, provisioning, billing/settlement, artifact pipeline, claims/refusals, contact/status/incidents, and acceptance tests.
2. Phase 2 — data centre: sample-to-measurement, hardware harness, pilot, production report, measured expansion.
3. Phase 3 — hyperscaler: workload selection, reproducible bake-off artifacts, verifiable capacity commitment, integration, production reporting.
4. Phase 4 — enterprise: use-case selection, self-serve trial, artifact-backed business case, integration/security materials, contract, deployment runbook.
5. Phase 5 — government: RFI, compliance matrix, sandbox, dated security evidence, ATO package, deployment dossier.
6. Phase 6 — integration, operational handoff, performance and accessibility verification.

Phase 0 included no code changes, acceptance-test run, or verified CI URL.
