# Evidence-scoped Tomorrow Readiness Index

## Purpose and boundary

This implements the operator-supplied, Telehouse-inspired five-area framework as
an executable, read-only assessment of the integrated system. It does not claim
Telehouse endorsement, reproduce an official Telehouse methodology, or validate
the supplied campaign statistics. Those statistics are not system measurements
and are deliberately excluded from scoring.

The engine turns scoped observations into a gap inventory and remediation order.
It does **not** start mining, mutate configuration, bypass custody/Guardian,
change hashrate, publish packages, or grant production approval. It complements
existing runtime readiness, portfolio release audits and independent verifiers;
it does not replace them. No external dependency is needed.

Each assessment is bound to one offering, one environment and one actual source
revision. Run separate assessments for different offerings/targets; do not reuse
one product's score as proof for the entire portfolio. The current gate set is for
the integrated mining/intelligence/storage/GPU system, not a configurable shortcut
for declaring a standalone library production-qualified.

## System impact and product distinction

The index adds a common assessment model beside the existing operational stack:
31 criteria, evidence coverage, dependency-constrained maturity, nine distinct
integrated-system gates, accepted-risk disclosure and a deterministic roadmap.
It connects AI ambitions to security, continuity, residency and capacity conditions
without transferring execution, proof, security, custody or recovery authority.

The product distinction is the combination of intelligence-led execution and
inspectable, deployment-scoped readiness—not an unsupported claim of market
exclusivity or faster computation. A dedicated TOE gate makes analytical execution
and learning evidence explicit; a separate Salamander gate makes exercised
recovery evidence explicit. Neither is established by the assessor itself.

See [system impact, architecture and supported product language](../v2/07_EVIDENCE_SCOPED_READINESS.md)
for the full account. Receipt collection/adaptation is an upstream integration
step, not an already automatic end-to-end feature of this CLI. This addition
changes assessment/reporting capability; it does not itself increase hashrate,
create external acceptance evidence, certify compliance or publish a package.

## Running

From the repository root:

```bash
python tools/tomorrow_readiness.py --template > assessment.json
# Fill profile, actual revision/environment, answers, metric targets,
# verifier policy and receipt references. Empty values remain unknown.
python tools/tomorrow_readiness.py \
  --input assessment.json \
  --evidence-root ./release-evidence \
  --output readiness-report.json
```

Optionally include an existing saved runtime probe as an **unscored observation**:

```bash
python tools/tomorrow_readiness.py \
  --input assessment.json --evidence-root ./release-evidence \
  --runtime-probe ./captured-ready.json --output readiness-report.json
```

The probe adapter supports `chronus.mla1517.ready/1`. It extracts only declared
component states, control/submission scope and the reported `ready` boolean,
plus the exact file digest. Paths, reasons, credentials and arbitrary component
payloads are not copied. A saved HTTP-200/`ready:true` probe establishes neither
current liveness nor gate success. The screenshot with ready control-plane but
unconfigured custody/Guardian/remote OpenCL is not proof of full-system readiness.
A probe snapshot has no score or qualification credit.

Exit codes:

- `0`: template generated, or an assessment has no outstanding gaps.
- `1`: valid assessment completed with gaps or unestablished gates/context.
- `2`: malformed input, invalid values/thresholds, unsupported schema, or I/O error.

Even an assessment with no gaps does not grant production approval. A software
maturity label such as `OPTIMISED` describes this model only; it is not an external
certification. JSON reports explicitly retain that distinction.

## Scoring contract

- 31 criteria across AI (25%), cyber (20%), resilience (20%), sovereignty (20%)
  and energy/scaling (15%). Criterion weights are equal within an area because
  the supplied pseudocode does not specify individual criterion weights.
- BOOL accepts JSON booleans, not truthy numbers or strings.
- SCALE_1_5 accepts integers 1–5, normalized as `value / 5`, matching the supplied
  model. This intentionally gives a score of 20 to the lowest answered level.
- METRIC requires measured value plus `threshold.unit`, `threshold.worst` and
  `threshold.target`. Normalization is `(value - worst) / (target - worst)`,
  bounded to [0,1], supporting higher- and lower-is-better metrics. The engine
  does not invent power budgets, runway targets or device capacity.
- Missing answers score zero. Unsupported or non-finite numbers are errors.
- Unproven claims receive half their normalized score; valid local receipts can
  restore full score. A high self-reported score never substitutes for evidence.
- A criterion below 60%, or any criterion without locally validated evidence,
  becomes a gap. Missing dependency context and incomplete gates also become gaps.
- Maturity bands: below 20 ABSENT; below 40 EXPERIMENTING; below 60 DEVELOPING;
  below 80 DEPLOYING; otherwise OPTIMISED. Classification uses unrounded scores.

### Dependencies corrected from the pseudocode

The original accumulation loop could repeatedly boost scores and depend on area
iteration order. It also used undeclared `Connectivity` and `WorkloadLocation`
areas and equated AI maturity with demand.

This implementation instead uses synchronous, base-anchored multiplicative
constraints, at most three passes, with no upward evidence credit:

- Cyber -> resilience (0.6) and sovereignty (0.4).
- Verified connectivity readiness -> resilience (0.6).
- Verified residency control -> sovereignty (0.7).
- Verified capacity planning -> energy/scaling (0.6).
- Verified AI demand pressure -> energy/scaling pressure (0.7).

Support factor: `1 - strength * (1 - source_score/100)`.
Pressure factor: `1 - strength * source_score/100`.
Each pass starts from the original criterion-derived area scores, not the last
pass's modified targets. Missing/unproven support is zero; missing/unproven demand
pressure is 100, conservatively. Context values are normalized 0–100 and require
measurement-bound receipts. Device execution is not inferred from a GPU namespace,
a 600-coordinate solver, a configured ceiling, or a successful CPU/software route.

The graph is intentionally explicit and currently acyclic. Its bounded iteration
has no claim of convergence for arbitrary future cyclic graph extensions.

## Evidence adapter contract

The operator supplies an `evidence` map of IDs to relative paths and SHA-256:

```json
{
  "ai-experiment-001": {
    "path": "ai-experiment-001.json",
    "sha256": "REPLACE_WITH_ACTUAL_FILE_SHA256"
  }
}
```

A producing verifier supplies the receipt; **do not fabricate PASS receipts from
this example**. A criterion receipt has the following structure:

```json
{
  "schema": "hyba.readiness.check.v1",
  "subject": "C1.1",
  "source_revision": "ACTUAL_TESTED_REVISION",
  "offering": "ACTUAL_OFFERING",
  "environment": "ACTUAL_TARGET",
  "observed_at": "2026-10-22T12:00:00+00:00",
  "verifier_id": "APPROVED_EXECUTED_VERIFIER",
  "status": "PASS",
  "checks": {"experiment_executed_and_checked": true},
  "measurement": {"value": true}
}
```

Reference this receipt from `answers.C1.1.evidence`. Metric receipts must bind the
entire measurement including the exact `threshold` object. Context subjects are
`context.connectivity`, `context.residency_control`, `context.capacity_planning`
and `context.ai_demand_pressure`, with `measurement: {"value": 0..100}`.

Receipt validation checks file digest, schema, exact subject/offering/environment/
revision binding, approved verifier ID, timezone-aware capture time, maximum age,
non-empty strictly boolean all-true checks, and exact typed measurement equality.
Evidence files are read once per check. Absolute paths, root escape (including
resolved symlinks), duplicate JSON keys, NaN/Infinity, oversized files, future
capture times, and stale receipts are rejected or denied evidence credit.
No credentials are required by this assessment.

**Trust boundary:** these are local receipt checks, not a new cryptographic trust
root. A hash proves byte identity, not truth; an allowlisted text identifier does
not authenticate a signer. Input policy, evidence root, producing verifiers and
receipts must be controlled by the deployment authority. Existing signed custody,
artifact provenance and external acceptance verification must execute upstream.
The engine does not independently attest that asserted checks actually ran.
The input and policy must not be treated as trusted merely because a user uploaded
them. Untrusted receipts require authentication by an existing approved verifier
before entering this adapter. The JSON report states this assurance level.

## Integrated-system qualification gates

Gates use subjects `gate.<id>` and require a scoped PASS receipt containing all
named checks below. A criterion receipt cannot be reused as gate evidence. All
checks must be literal `true`. Connection-only evidence cannot pass acceptance.

| Gate | Required check names |
| --- | --- |
| regression_suite | tests_executed, zero_failures, zero_errors, required_suites_complete |
| docker_e2e | image_built, container_started, mounts_verified, services_exercised, health_checked |
| gpu_execution | device_identified, device_work_executed, result_independently_checked |
| pool_acceptance | share_submitted, pool_acceptance_observed, acceptance_bound_to_work |
| failover | failure_injected, automatic_recovery, work_resumed |
| custody | authenticated_custody, lineage_verified, reconciliation_passed |
| toe_end_to_end | plan_bound_to_work, execution_observed, learning_receipt_verified |
| salamander_recovery | fault_injected, recovery_executed, state_integrity_verified |
| release_artifacts | artifacts_built, metadata_checked, boundary_checked, installed_smoke_passed |

These are prerequisites for an evidence-complete assessment, not substitutes for
full verifier semantics. For example, a regression verifier must execute the
required suites, not an arbitrary passing subset; GPU verification must establish
actual device work, not a software name; pool proof must bind an external accepted
share to submitted work. Artifact gate completion is not TestPyPI/PyPI publication
verification: retain the existing portfolio audit state machine and receipts.

The engine records operator-accepted risks separately and never rewrites failed
checks as passed. Earlier authorization to deploy with accepted risk remains a
separate operator decision; this assessment neither revokes nor disguises it.

## Roadmap and integration with the repair work

Roadmap sorting is deterministic by phase, severity, dependency leverage and ID:

1. Critical gates, critical controls, security and continuity foundations.
2. Data platform, sovereignty, capacity and pre-planning enablement.
3. Remaining AI, operational scaling and sustainability improvements.
4. Reserved for future non-blocking optimization recommendations; no invented
   low-priority work is added just to populate a phase.

Known historical repair evidence must be imported only with its real revision,
actual observation time and scope. Do not turn the previous 48 failed regression
nodes, unestablished pool acceptance or Docker `/proc` failure into passing
receipts. No current full-system assessment score is asserted by this addition.
Existing repair and release records remain authoritative for what actually ran.

The first productive integration is to have existing test, custody, device,
TOE, Salamander, failover and package verifiers export the receipt contract after
their own authenticated checks. The index consumes these records; it does not
pretend that exporters or missing target tests are already implemented here.

## Validation scope

`python -m unittest discover -s tests -p test_tomorrow_readiness.py -v` exercises
synthetic fixtures only. They cover scoring, maturity boundaries, typed values,
metric binding, scope/time/hash checks, stale/future/forged-shape evidence,
required gate checks, conservative dependencies, order independence, path escape,
JSON ambiguity, size limits, risk separation and the read-only probe adapter.
The dedicated CI matrix targets Python 3.11–3.14; adding the workflow does not
establish that remote CI has run. These tests do not resolve the outstanding
whole-system regression, Docker, physical GPU, external-share or publication gates.
