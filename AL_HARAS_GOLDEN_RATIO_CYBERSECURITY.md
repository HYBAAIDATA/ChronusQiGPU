# HYBA + AL HARAS: Golden-Ratio Defensive Cyber Triage

Status: implemented deterministic heuristic; requires workload-specific evaluation.
This is the top-level entry point for the AL HARAS consolidation and its
phi-based defensive triage experiment.

## Consolidated platform direction

HYBA is the platform boundary. AL HARAS and L-HRAS remain the security,
authorization and governance capabilities, not a parallel product stack. The
canonical five intelligence forms are predictive, causal, counterfactual,
topological and geometric. TOE is the shared reasoning/evidence substrate;
Salamander is the canonical adaptive-resilience control plane. Millennium Maths
is an isolated, bounded mathematical probe service and never receives mission
observations.

Implementation sources:

- National-security consolidation: docs/al-haras/NATIONAL_SECURITY_CONSOLIDATION.md
- Platform topology v2: docs/al-haras/HYBA_PLATFORM_TOPOLOGY_V2.md
- TOE integration: docs/al-haras/TOE_PLATFORM_INTEGRATION.md
- Salamander integration: docs/al-haras/SALAMANDER_ADAPTIVE_RESILIENCE_INTEGRATION.md
- Defensive optimization benchmark protocol: docs/al-haras/QUANTUM_OPTIMIZATION_BENCHMARKS.md
- Shared golden-ratio math substrate: hyba_substrate/golden_ratio_library.py
- Executable phi defensive triage: recovery/hyba_data/source/hyba_data/hermes/offerings/phi_security_optimizer.py

## What phi contributes

The implementation uses the golden ratio phi = (1 + sqrt(5)) / 2 for a
transparent freshness-decay factor and deterministic review-slot apportionment:

- freshness_weight = phi^(-age_units)
- priority = severity * exposure * confidence * freshness_weight
- review allocation uses descending phi^(-rank) weights and largest-remainder
  apportionment so integer slots sum exactly to the available budget.

Age units are explicit and results are reproducible. This makes no claim that
the golden ratio is inherently cryptographic, detects attacks unaided, improves
predictive accuracy, or creates quantum advantage. Inputs must come from
validated adapters; scores are triage priorities, not attack probabilities.
Conventional baselines and held-out operational data must establish whether this
approach improves outcomes.

## Runtime and authority boundaries

The module returns recommendation-only outputs. It does not authenticate
sources, infer missing telemetry as healthy, change thresholds, authorize
actions, dispatch remediation, or bypass AL HARAS/L-HRAS. Consequential actions
must pass the existing tenant/capability admission, signed policy and action
authorization path. Preserve evidence references and uncertainty when combining
the result with the five intelligence forms.

Never send mission observations to Millennium Maths. Mathematical probes remain
separate from mission assessments. Finite numerical results are not proofs of
open mathematical problems.

## Minimum evaluation plan

1. Compare against severity-only, severity-times-exposure, and existing policy
   baselines on the same sanitized defensive cases.
2. Fix scoring definitions, age units and thresholds before evaluation.
3. Use temporally held-out cases; report precision/recall, false-alarm rate,
   miss rate, lead time, time-to-triage, analyst workload and confidence intervals.
4. Include missing/stale evidence, duplicate IDs, contradictory signals,
   cross-tenant attempts and dependency failures.
5. Run in shadow mode first. Never use the score as the sole basis for a
   consequential decision.
6. Independently review performance claims before publication.

## Delivery status

The code and contract tests are added in the consolidation branch. They have
not been executed in this editing session. This is not a production-readiness claim.
