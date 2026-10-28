# TOE-backed HYBA National-Security Offering

## Decision

The national-security offering is delivered by HYBA and supported by the existing
Theory of Everything (TOE) platform. AL HARAS is a security/governance capability
within that consolidated offering, not a separate product or reasoning stack.
TOE supplies domain-neutral reasoning, uncertainty handling, causal analysis,
policy constraints, explanations and evidence receipts; HYBA supplies mission
context, source adapters, security controls, analyst workflow and operational
ownership.

This document defines the integration contract. It does not claim that all
runtime connections or operational approvals are already deployed.

## Canonical architecture

```text
Authorized source adapters
  -> HYBA mission / tenant / purpose validation
  -> normalized evidence envelope (source IDs, timestamps, lineage, quality)
  -> TOE Problem + TOEIntelligenceRuntime (one tenant-scoped reasoning path)
  -> five-form assessment mapping
       predictive | causal | counterfactual | topological | geometric
  -> evidence reconciliation + uncertainty + dissent preservation
  -> AL HARAS / L-HRAS policy and authorization checks
  -> analyst review and approval for consequential action
  -> outcome feedback, TOE receipt, HYBA audit record
```

Use the canonical TOE runtime and problem contract where available:
- `toe/problem.py`: domain-neutral `Problem`, validation, and content identity.
- `toe/runtime.py`: `TOEIntelligenceRuntime`, `TenantContext`, runtime response,
  evidence and receipt boundary.
- `toe/machine.py` and reasoning modules: representation, causal ladder,
  uncertainty, planning, arbitration, explanation, policy, topology, geometry,
  custody and receipts.
- `toe/intelligences/`: supporting/mining-facing components only where their
  status and contract are appropriate; do not create parallel aliases or a
  second orchestration root.

The standalone TOE distribution excludes some monorepo-only intelligence
coordinators. Integration must therefore target the supported TOE runtime and
problem contract, not assume every `toe/intelligences/*` helper is part of the
standalone package.

## Five-form contract

The offering's five forms remain the canonical HYBA labels. They are an
assessment taxonomy, not a claim that five independent autonomous agents are
required. TOE may contribute evidence to multiple forms; the adapter must keep
the form label, source evidence, model/version, timestamp and limitations
attached to every result.

| Form | TOE-backed contribution | Required output discipline |
|---|---|---|
| Predictive | Temporal forecasts, uncertainty and comparison to baselines | Horizon, as-of time, calibration/uncertainty, provenance and invalidation conditions |
| Causal | Causal graph and intervention analysis where assumptions/data support it | Separate observed association from causal claim; state graph assumptions and confounder limits |
| Counterfactual | Alternative scenario evaluation under declared assumptions | Label scenarios as hypothetical; state what changes and what is held fixed |
| Topological | Connectivity, reachability, dependency and structural-change analysis | Identify graph/state representation and missing nodes/edges |
| Geometric | State-space/geometry representations where inputs justify them | Declare coordinate/model assumptions; do not treat a mathematical score as a physical fact |

Do not manufacture a TOE output for a form that the configured runtime cannot
support. Return an explicit status such as `not_available`, `insufficient_evidence`
or `validation_required`; absence must never be interpreted as low risk.

## Shared evidence envelope

Every observation passed from HYBA into TOE should be tenant- and purpose-scoped
before inference and include:
- stable event/assessment ID and schema version;
- source identifiers, acquisition time, event time, lineage and integrity status;
- permitted purpose, classification/handling label and retention policy reference;
- normalized facts separated from source assertions and model-derived features;
- data quality, freshness, missingness and known source limitations;
- bounded payload size and explicit allow-listed fields.

Do not place secrets, raw credentials, or unnecessary personal data in model
metadata, audit messages or free-text logs. Enforce source access before calling
TOE; a downstream explanation is not an authorization check.

## Result and receipt contract

The HYBA adapter should normalize each successful TOE response into an assessment
envelope containing:
- `status`, `form`, `assessment_id`, `tenant_id`, and `purpose`;
- structured findings and competing hypotheses;
- evidence references and model/runtime version;
- confidence only where its meaning is defined, plus uncertainty and missing data;
- assumptions, limitations, and a human-readable explanation;
- TOE runtime receipt and HYBA audit correlation ID;
- `recommendation_only: true` for outputs that have not passed authorization.

Preserve the TOE response's `ok`, `degraded`, error and receipt fields. If the
runtime is degraded, receipt creation fails, evidence is stale, or tenant/purpose
validation fails, do not silently fall back to an ungoverned prediction. Mark the
assessment unavailable/degraded and route it for operator review.

## Governance and feedback

1. HYBA authenticates the caller and checks mission, tenant, source permissions
   and purpose before inference.
2. TOE validates the problem, reasons and emits its result/receipt.
3. HYBA reconciles five-form evidence without suppressing material disagreement.
4. AL HARAS/L-HRAS applies policy; the TOE output itself cannot grant access or
   authorize collection, targeting, interdiction, or other consequential action.
5. An authorized human reviews high-impact recommendations and records the
   decision, rationale, authority and any override.
6. Verified outcomes may be returned to TOE's feedback path with lineage and
   permitted retention. Feedback must not cross tenant boundaries or silently
   relabel analyst decisions as ground truth.

Initial deployment mode: offline replay and shadow assessment. No autonomous
high-impact action. Any operational integration requires a threat model, data
protection review, role/attribute access controls, audit and retention checks,
incident response, rollback, and independent validation appropriate to the
mission.

## Verification gates

- Contract tests: valid/malformed inputs, size limits, missing evidence, stale
  evidence, unsupported forms, and stable schema/version behavior.
- Tenant and purpose isolation: prove that evidence, memory, receipts and feedback
  cannot cross authorization boundaries.
- Resilience: TOE unavailable/degraded, timeout, malformed response, receipt or
  audit failure; fail closed with explicit status.
- Reasoning quality: temporal holdout for forecasts; causal assumptions and
  sensitivity checks; counterfactual consistency; graph integrity; geometry
  assumptions and sensitivity.
- Reconciliation: conflicting sources, duplicate events, source corrections and
  dissent preservation.
- Human authority: no consequential action without a verified authorization
  path; no model-only adverse decision.
- Claims: document which components are implemented, tested, experimentally
  supported, or not established. Do not claim production readiness until the
  applicable TOE acceptance gates and HYBA operational gates are evidenced.
