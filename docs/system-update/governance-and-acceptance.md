# Chronus Governance and Acceptance Framework

**System update programme · release controls**

## 1. Evidence principles

1. **Traceability:** each claim, requirement, invariant, and gate maps to a source version, test or assessment, owner, and evidence artifact.
2. **Independent checks:** tests should not simply repeat the implementation's own status or expected value. Use independent reference implementations or reviewers where practical.
3. **Bounded conclusions:** report what was tested, on which configuration, and under which assumptions. A passing sample is not a universal proof.
4. **No success-shaped defaults:** skipped, mocked, unavailable, or inconclusive checks cannot become `PASS`.
5. **Capability-level status:** do not let an aggregate green label conceal a failed or missing mandatory control.
6. **Reproducibility:** retain commit identity, dependencies, environment, inputs, random seeds where applicable, command, timestamp, raw output, and result.
7. **Separation of assurance types:** distinguish executable software tests, simulations, physical-hardware measurements, formal proofs, security assessments, and customer acceptance.

## 2. Standard outcome vocabulary

| Outcome | Meaning | Release treatment |
|---|---|---|
| `PASS` | The defined acceptance criterion executed and was met; evidence is retained and traceable. | Eligible to satisfy a mandatory gate. |
| `FAIL` | The criterion executed and was not met. | Blocks any dependent mandatory gate until resolved or formally accepted as out of scope. |
| `BLOCKED` | The criterion could not be evaluated because a prerequisite, environment, or evidence source was unavailable. | Does not satisfy a mandatory gate. |
| `SKIPPED` | The check was intentionally not executed. | Does not satisfy a mandatory gate. |
| `NOT_APPLICABLE` | A documented scope analysis establishes that the criterion does not apply to this release. | Requires approval by the release authority; never use as a convenience default. |

Use `NOT_TESTED` only when quoting historical source material; new qualification records should use the vocabulary above.

## 3. Minimum evidence record

Each qualification result should include:

- Stable test/requirement ID and test-family classification.
- Requirement text, acceptance criterion, and applicability.
- Source commit, package/build identity, and configuration.
- Toolchain, dependencies, operating system, and execution backend.
- Input corpus identity and checksum; random seed if relevant.
- Exact command or procedure, start/end time, and executor.
- Expected and actual outcomes, assertion details, and failure trace.
- Raw logs/results and durable evidence reference with integrity checksum.
- Resource measurements and instrumentation source where relevant.
- Reviewer, status, limitations, linked defect, and re-test result.

Evidence must be retained in a location appropriate to its sensitivity. Public verifiability must not disclose tenant or customer data.

## 4. Mandatory release gate model

Tailor applicability to the release, but do not omit a gate silently.

| Gate | Decision question | Minimum acceptance evidence |
|---|---|---|
| G1 — Scope and baseline | Is the exact release candidate and its claims unambiguous? | Immutable source/package identity; approved scope; reconciled claim and requirement register. |
| G2 — Functional behavior | Does the pilot behavior meet its defined contract? | Direct assertions, boundary/negative tests, independent references where relevant. |
| G3 — Data integrity and recovery | Are committed outputs durable and recoverable under the stated failure model? | Real persistence/retrieval tests, interruption-point tests, integrity checks, documented recovery limits. |
| G4 — Security and isolation | Are trust boundaries enforced for the target deployment? | Threat model, authorization and tenant-isolation tests, dependency review, independent review of critical controls. |
| G5 — Performance and capacity | Are published service measures reproducible for the target workload? | Protocol, hardware/backend identity, sample counts, raw results, resource metrics, repeat runs, comparison limits. |
| G6 — Operations | Can the service be deployed, observed, supported, backed up, and rolled back? | Deployment and restore exercises; monitoring and alert evidence; runbooks; incident and rollback procedures. |
| G7 — Customer acceptance | Does the chosen workload deliver the agreed outcome for the pilot user? | Customer-observed end-to-end journey and agreed value measure with evidence source. |
| G8 — Release decision | Are remaining risks and limitations explicitly accepted by the right authority? | Signed decision record; mandatory gates satisfied; accepted exceptions, limitations, and deployment conditions. |

Passing a software test does not by itself establish physical hardware execution, formal theorem validity, cryptographic certification, regulatory authorization, or commercial value.

## 5. Claim and qualification register

Maintain one version-controlled register with at least:

| Field | Description |
|---|---|
| Claim ID | Stable identifier; never reuse an ID for a materially changed claim. |
| Claim | Exact wording and intended audience. |
| Claim class | Software behavior, mathematical property, simulation, hardware measurement, security, compliance, commercial, or roadmap. |
| Scope and assumptions | Input domain, deployment, backend, threat model, workload, and exclusions. |
| Evidence | Test, report, raw results, commit, and independent reviewer, where applicable. |
| Status | One standard outcome plus a plain-language evidence classification. |
| Owner and approver | Accountable subject-matter owner and release/claim authority. |
| Limitation and next action | What remains unproven, remedy, and review date. |

Recommended evidence classifications: **demonstrated in tested software scope**, **simulated**, **independently reviewed**, **measured on identified hardware**, **formally proven for a stated model**, **proposed**, or **unsupported**. Do not equate these labels.

## 6. Decision rights and cadence

- **Product lead:** owns pilot scope, user outcome, and acceptance criteria.
- **Technical lead:** owns architecture, implementation boundaries, and technical limitations.
- **Verification lead:** owns test integrity, reproducibility, and evidence completeness.
- **Security lead:** owns threat model, security review, and security acceptance recommendation.
- **Operations lead:** owns deployment, observability, recovery, and support readiness.
- **Release authority:** accepts release risk and records the final decision; this role should be distinct from the author of the evidence where feasible.

Run a weekly programme review against outcomes, blockers, decisions, and risk. Hold a separate release review only when the evidence dossier is complete. Record material decisions with rationale, owner, date, and reconsideration trigger.

## 7. Go / conditional go / no-go

- **GO:** all applicable mandatory gates pass; no unresolved blocking risk; operating scope and claims match the evidence.
- **CONDITIONAL GO:** only for a named, bounded deployment with explicit safeguards, time-limited exceptions, owners, and exit criteria; no exception may misrepresent a failed mandatory safety, security, or data-integrity control.
- **NO-GO:** any mandatory gate fails, is blocked, or lacks evidence; critical assumptions are unresolved; or proposed claims exceed the validated scope.

Every decision records the source version, applicable gate outcomes, accepted risks, deployment conditions, claim limitations, approvers, and review/expiry date.
