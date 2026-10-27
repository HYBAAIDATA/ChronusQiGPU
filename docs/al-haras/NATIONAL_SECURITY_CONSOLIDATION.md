# HYBA National-Security Intelligence Consolidation

Status: consolidation and enhancement plan. This document describes target
integration; it does not certify operational readiness or claim unmeasured
predictive performance.

## Direction

AL HARAS is a HYBA security/governance capability, not an independent product.
National-security enhancement must consolidate around existing HYBA intelligence,
predictive, Guardian, evidence, and policy components. Do not fork a second
orchestrator, duplicate the five intelligence implementations, or create a
parallel authorization boundary.

The target is a unified, evidence-led decision-support capability for authorized
national-security and critical-infrastructure use: early warning, scenario
analysis, defensive cyber risk, resilience planning, incident triage and
auditable recommendations. Human authorities retain responsibility for
consequential decisions. Avoid autonomous targeting, population surveillance,
or decisions that materially affect people based solely on inferred risk.

## The canonical five intelligence types

Use the existing HYBA five-form model from
`al_haras.quantum_defense.five_form_swarm.IntelligenceForm`:

1. **Predictive** — estimate plausible future states and warning indicators,
   with time horizon, calibrated uncertainty and baseline comparisons.
2. **Causal** — distinguish association from plausible causal mechanisms and
   identify which assumptions support an explanation.
3. **Counterfactual** — compare explicit alternative scenarios: what may change
   if a stated condition or defensive measure changes.
4. **Topological** — analyse relationships, connectivity, paths, boundaries and
   structural changes in an evidence graph or system model.
5. **Geometric** — analyse state-space structure, distances, trajectories and
   deviations using documented representations and validated metrics.

These are complementary reasoning lenses, not five independent sources of
truth. Each lens must return evidence references, assumptions, confidence or
uncertainty, model/version information and limitations. A missing or failed
lens must be visible; it must not silently become a reassuring result.

## Consolidated component map

| Responsibility | Existing HYBA location | Integration rule |
|---|---|---|
| Five-form duty swarm | `recovery/hyba_data/source/hyba_data/al_haras/quantum_defense/five_form_swarm.py` | Enhance in place; do not reimplement the five forms elsewhere |
| State/transition security governance | `recovery/hyba_data/source/hyba_data/al_haras/paradigm_shift.py` | Keep policy decisions distinct from intelligence recommendations |
| Hash-chain/Merkle audit primitive | `recovery/hyba_data/source/hyba_data/al_haras/security_core.py` | Treat as tamper-evidence, not automatically as external immutable custody |
| Tenant, subscription and capability boundary | `al_haras/runtime.py` and related AL HARAS runtime | Preserve the existing admission boundary; no bypass paths |
| Full Guardian conjunction | `l_hras/guardian.py` | Reuse the governed detection, policy, attestation and response flow |
| Guardian integration gaps | `docs/al-haras/GAP_ANALYSIS.md` | Use this as the evidence register for integrations not yet proven |
| National-security offering | `recovery/hyba_data/source/hyba_data/hermes/offerings/national_security.py` | Refactor claims and route through canonical HYBA components; no duplicate stack |
| Broader intelligence registry/orchestration | `Intelligence/registry.py`, `Intelligence/orchestrator.py`, `toe/intelligences/` | Establish one explicit integration contract; do not assume mining-specific code is production national-security capability |

The module names and code presence are not by themselves proof of deployment,
independent validation, external service connectivity, or mission effectiveness.
Confirm each claim against tests and operational evidence.

## Target data flow

```text
Authorized feeds / operator reports / approved telemetry
                       |
                       v
Tenant + identity + purpose + data-handling policy
                       |
                       v
Validation, provenance, freshness, deduplication
                       |
                       v
Canonical observation / event schema
                       |
             +---------+---------+
             |         |         |
             v         v         v
        Predictive   Causal   Counterfactual
             |         |         |
             +---------+---------+
                       |
               Topological + Geometric
                       |
                       v
Cross-lens reconciliation and uncertainty
                       |
                       v
Risk/scenario assessment + evidence packet
                       |
                       v
AL HARAS / L-HRAS policy and governance
                       |
                       v
Analyst review → authorized recommendation/action
                       |
                       v
Outcome verification + audit receipt + feedback
```

The diagram is a target flow, not a claim that every connection is already wired.
The same event identity and provenance must survive the entire path. Intelligence
components can recommend; they cannot grant entitlements or authorize actions.

## Predictive intelligence requirements

Predictive output should include at minimum:

- forecast subject and scope, target event, time horizon and as-of timestamp;
- probability or calibrated score with a stated interpretation;
- evidence identifiers, data lineage and missing-data indicators;
- model/version, training/evaluation window and known limitations;
- comparison to a simple baseline and a measured uncertainty interval where
  statistically supportable;
- actionable early-warning indicators and the conditions that would invalidate
  the forecast.

Measure precision/recall at useful thresholds, calibration, false-alarm rate,
miss rate, lead time, drift, subgroup error where appropriate, and analyst
workload. Evaluate on temporally held-out data to avoid leakage. Do not publish
a fixed accuracy claim without a reproducible evaluation on a defined task and
dataset. Forecasts are hypotheses, not facts or sole grounds for coercive action.

## National-security operating principles

- **Purpose limitation:** define permitted mission, data classes, retention and
  sharing before ingesting data.
- **Data minimization:** collect only what the authorized task needs; segregate
  sensitive sources and enforce retention/deletion rules.
- **Evidence-first:** distinguish observed facts, source assertions, model
  inferences and analyst judgments in every report.
- **Uncertainty and dissent:** preserve conflicting indicators; do not average
  away a high-consequence warning or conceal disagreement.
- **Human accountability:** require named review and approval for consequential
  decisions; provide a contestable explanation and a route to correction.
- **Least privilege and isolation:** tenant-scoped identities, role-based access,
  compartmentalized source access and auditable exports.
- **Defensive cyber use:** focus on authorized monitoring, threat assessment,
  resilience, incident response and recovery.
- **Fail-safe operation:** bounded execution, explicit degraded modes, safe
  fallbacks, incident escalation and tested rollback.
- **Audit honesty:** local hash chains are tamper-evident structures; claims of
  independent witnessing, WORM retention, hardware roots or certification need
  separately verified controls.

## Delivery plan

### Gate 1 — Inventory and claims cleanup
Map the actual runtime path and test coverage across the five-form swarm,
predictor, Guardian, policy and audit. Remove or quarantine unsubstantiated
marketing claims (for example, fixed prediction accuracy or hardware quantum
claims) from code responses and product material.

### Gate 2 — Shared contracts
Define versioned schemas for observation, evidence, forecast, causal hypothesis,
counterfactual scenario, graph/state analysis, composite assessment and
decision receipt. Add strict validation, provenance and explicit missing-result
states.

### Gate 3 — Evidence-backed integration
Connect existing components through one orchestrator contract. Ensure tenant,
purpose and policy context are bound before inference and rechecked before any
response. Add tests for stale feeds, conflicting lenses, malformed input,
cross-tenant leakage, timeout, provider failure and audit failure.

### Gate 4 — Predictive validation
Build a sanitized historical replay set, temporal holdout, baseline comparisons,
calibration analysis and independent review. Keep the system in shadow mode
until the acceptance criteria are met.

### Gate 5 — Operational readiness
Demonstrate real feed/SIEM/SOAR round trips where applicable, incident drills,
access review, retention enforcement, outage behavior, disaster recovery,
rollback and a documented operator playbook. The existing GAP_ANALYSIS should
be updated with actual evidence, not assumptions.

### Gate 6 — Advanced optimization
Only after the classical baseline and end-to-end pipeline are measurable, test
classical optimization, quantum-inspired heuristics and any configured quantum
provider against identical constraints and workloads. Label simulations and
heuristics accurately. Optimization never changes the policy authority.

## Acceptance criteria

- One canonical five-form implementation and one governed decision path.
- Every material assessment is traceable to source evidence and model version.
- Missing/stale/conflicting evidence is surfaced and does not silently imply low
  risk.
- Predictions beat a declared baseline on held-out data with uncertainty
  reported, or are not promoted.
- No unapproved action is executed; every high-impact action has an authority,
  reason, scope and recovery path.
- Cross-tenant isolation, purpose limits, audit integrity and fail-safe behavior
  have automated tests.
- External integration, independent validation and deployment claims are
  explicitly marked as proven, partial or not established.
