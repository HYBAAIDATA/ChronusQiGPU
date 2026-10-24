# Evidence-scoped readiness — system impact and product distinction

**Implementation:** [`tools/tomorrow_readiness.py`](../../tools/tomorrow_readiness.py)  
**Contracts:** [`tests/test_tomorrow_readiness.py`](../../tests/test_tomorrow_readiness.py)  
**Integration record:** [merged PR #142](https://github.com/PhiEnterprise1/EuclidPhiEnterprise/pull/142)  
**Technical reference:** [scoring, evidence format and CLI](../readiness/TOMORROW_READINESS_INDEX.md)

## Executive summary

**Intelligence-led execution. Evidence-scoped readiness.**

HYBA/PYTHIA adds an executable readiness assessment alongside its intelligence,
execution, security, custody and recovery capabilities. The addition answers a
question that a feature list or healthy process alone cannot answer:

> For this offering, in this environment, at this source revision, which
> readiness requirements have supporting evidence, what remains unestablished,
> and what should be addressed first?

The engine brings 31 criteria across five operational areas into a shared model,
checks locally supplied verifier receipts, applies dependency constraints, and
produces a machine-readable report with a phased remediation roadmap. It is an
assessment layer, not a new execution controller, proof authority or certification.
Its value is making the conditions for dependable operation explicit and
inspectable—not declaring those conditions satisfied without execution evidence.

## What has been added

| Addition | Implemented behavior | Practical contribution |
| --- | --- | --- |
| Five-area assessment | AI infrastructure, cyber security, resilience, sovereignty, and energy/scaling, with 31 criteria | Places compute ambition alongside the operational conditions needed to support it |
| Evidence-scoped scoring | Answers and receipts are checked against offering, environment, revision, time and measurement | Distinguishes a capability claim from locally validated supporting evidence |
| Explicit dependency constraints | Connectivity, security, residency control, planning and AI demand can constrain related scores | Makes cross-area weaknesses visible without inventing evidence credit |
| Separate qualification gates | Nine named integrated-system verification contracts | Keeps process health distinct from end-to-end execution, recovery and acceptance |
| Deterministic roadmap | Gaps sorted by phase, severity, dependency leverage and stable identifier | Gives engineering and operations a reproducible remediation order |
| Read-only runtime adapter | Sanitized fields from an existing saved readiness probe | Adds operational context without treating a connected process as a qualified system |
| Portable report generation | Standard-library Python CLI and JSON output | Supports use beside existing tooling without replacing the runtime or its authorities |

The engine uses the operator-supplied Telehouse-inspired framework as a starting
point. It does not claim Telehouse endorsement, certification, an official scoring
methodology, or validation of the supplied research statistics.

## Where it sits in the system

```text
Existing runtime and subsystem verification
  intelligence / execution / security / custody / recovery / release
                              |
           authenticated checks and scoped observations
                              |
             verifier-produced receipt files
       [export/adaptation required where not yet available]
                              |
                    Readiness assessment
         scope + freshness + digest + measurement checks
         criterion scoring + explicit dependency constraints
                              |
                 JSON report and phased roadmap
                              |
            Operator / engineering review and action
                              |
        Existing authorized execution and verification paths
```

This is a **read-only assessment path**. The CLI consumes configured inputs and
receipt files. It does not automatically instrument every subsystem, run every
test, ingest all live telemetry, export signed receipts, change runtime policy,
or execute its roadmap. Those are separate integration and operating steps.
A report file is output, not durable custody by itself.

### Authority boundaries remain intact

| Existing authority | Relationship to the readiness layer |
| --- | --- |
| EUCLID cognition and orchestration | Assessment output can inform human planning; direct orchestration consumption is not added by this change |
| TOE analytical and learning capabilities | The TOE gate requests plan/work binding, execution observation and a checked learning receipt; a maturity score does not replace TOE or establish its execution |
| PYTHIA mining authority and proof boundary | Share validity and literal pool acknowledgement remain external to readiness scoring |
| CHRONUS heterogeneous execution | Requested or discovered devices are not execution proof; actual device work requires its own checked receipt |
| SALAMANDER bounded recovery | A recovery gate requires fault injection, recovery execution and state-integrity checks; the assessment does not invoke healing |
| AL HARAS security and policy | Authorization and entitlement remain enforced by their existing owners; scoring neither grants nor overrides them |
| THESEUS custody and integrity | Producing verifiers must authenticate custody upstream; the assessor's local file checks are not a replacement trust root |
| Existing portfolio publication audit | Artifact assessment does not establish TestPyPI/PyPI publication, registry verification or release completion |

## How this elevates the system

### 1. From module capability to deployment conditions

TOE analysis, a tensor operation, a running service or a successful unit test can
establish something useful without establishing the entire deployment. The index
provides a common place to relate those capabilities to infrastructure, security,
continuity, residency and scaling requirements. It keeps the integrated-system
qualification gates visible beside the numerical maturity score.

### 2. From a generic score to a scoped evidence assessment

A receipt for one environment or revision does not receive credit for a different
one. The report separates raw answers, evidence-adjusted scores, evidence coverage,
dependency-adjusted area scores, individual gate status and accepted risks.
This makes assessment decisions inspectable within the stated local trust model.
It does not automatically authenticate a signer or prove that a verifier ran.

### 3. From isolated strengths to dependency-aware readiness

Strong AI answers cannot erase an unproven power budget. Security and connectivity
can constrain resilience; residency controls can constrain sovereignty. Adjustments
are synchronous and anchored to the criterion-derived scores, avoiding repeated
score inflation. The result is a model of limiting conditions, not a claim that
all dependencies or business risks have been exhaustively represented.

### 4. From an undifferentiated gap list to engineering order

The roadmap places critical gates and security/continuity foundations first,
then data, sovereignty and capacity enablement, followed by remaining operational
improvements. It is a deterministic recommendation, not an autonomous repair loop
or an optimized project schedule with owners, costs and delivery dates.

### 5. From implicit exceptions to explicit risk decisions

An operator can accept a deployment risk without converting the underlying check
into a pass. The report preserves accepted risks separately from measurement and
qualification. This supports clear engineering handover and governance discussion
without rewriting the historical evidence.

## How it strengthens our positioning

The defensible distinction is the **combination** of intelligence-led computation
with explicit execution, proof, custody, recovery and readiness boundaries.
The addition makes those boundaries easier to assess together and explain to
operators, technical evaluators and prospective customers.

| Positioning theme | What we can show | Why it matters |
| --- | --- | --- |
| Intelligence with operational accountability | A dedicated TOE execution/learning evidence contract alongside infrastructure and control criteria | Connects analytical ambition to conditions that must be demonstrated in operation |
| Specificity instead of an undifferentiated green light | Revision/environment-scoped criteria, evidence coverage and nine distinct gates | Supports a more precise discussion of what has and has not been demonstrated |
| Cross-domain readiness | Dependencies between security, connectivity, residency, capacity and AI demand | Helps prioritize prerequisites rather than treating scaling as a compute-only problem |
| Recovery as an exercised requirement | Separate failover and Salamander fault/recovery/integrity contracts | Makes the requested recovery evidence explicit rather than inferring it from a service being available |
| Reviewable risk handling | Accepted risks preserved without score or gate uplift | Separates an authorized decision from a technical assertion |
| Low-coupling adoption | A standard-library CLI, local evidence adapter and JSON output | Allows assessment use alongside the existing architecture without transferring actuator authority |

These are documented product characteristics and their intended benefits, not a
competitive benchmark. No market-wide review establishes that they are exclusive
to HYBA/PYTHIA. Avoid “the only platform,” “first of its kind,” quantified cost or
risk reductions, and superiority claims until supported by comparative evidence.

### Approved short product description

> HYBA/PYTHIA combines intelligence-led execution with evidence-scoped readiness.
> Its readiness engine assesses AI infrastructure, security, resilience,
> sovereignty and scaling conditions for a declared offering, environment and
> revision. It distinguishes supported measurements from unproven claims,
> exposes dependency constraints, and produces a prioritized engineering roadmap
> while preserving existing execution, proof, security and recovery authorities.

This description is suitable for product documentation and technical briefings.
Do not append claims of production certification, measured quantum advantage,
guaranteed hashrate or external pool acceptance unless separately demonstrated.

## Operational use

1. Declare the actual offering, target environment, source revision and verifier
   policy; set metric units and targets explicitly.
2. Execute the existing subsystem checks and retain authentic, scoped receipts.
   Adapt their outputs to the receipt contract where exporters are still missing.
3. Run the index and review both evidence coverage and individual gates—not just
   the composite maturity score.
4. Use the roadmap to organize remediation through the existing authorized paths.
5. Rerun the relevant checks after changes and reassess the new revision. A new
   report generation time does not refresh an old receipt's observation time.

See the [technical reference](../readiness/TOMORROW_READINESS_INDEX.md#running)
for exact commands, receipt fields, trust assumptions and exit codes.

## Implementation and validation status

- The engine and dedicated workflow were merged in PR #142.
- The implementation delivery recorded 34 passing local synthetic unit,
  adversarial and CLI tests. These are assessment-engine tests, not a whole-system
  validation result.
- The dedicated CI workflow targets Python 3.11–3.14. Workflow existence does not
  establish a current remote CI outcome.
- No current deployment maturity score, complete receipt-exporter integration,
  whole-system production qualification or registry publication is asserted here.
- Local digest/scope/time/measurement/allowlist validation is not independent
  attestation. Verifier and policy integrity must be established upstream.

The addition improves the system's assessment and handover capability. It does
not, by itself, change compute throughput, energy consumption, accepted shares,
intelligence performance or the outcome of an unexecuted end-to-end test.
