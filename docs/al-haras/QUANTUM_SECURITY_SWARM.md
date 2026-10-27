# HYBA National-Security Intelligence: Swarm Enhancement

Status: design proposal within HYBA consolidation; not a claim that all
components are implemented or operationally validated.

## Objective

Enhance the existing HYBA intelligence and AL HARAS security components for
authorized national-security and critical-infrastructure decision support.
AL HARAS is a shared HYBA security/governance capability, not an independent
product. This work must reuse the canonical five-form model and existing
Guardian/policy path rather than create a parallel stack.

The five intelligence forms are **predictive, causal, counterfactual,
topological and geometric**. The core proposition is better coordinated,
evidence-backed decisions, not an unsupported claim that quantum computation
automatically detects attacks or makes a system unbreakable.

For the component map, data flow, predictive-validation criteria and delivery
gates, see [NATIONAL_SECURITY_CONSOLIDATION.md](NATIONAL_SECURITY_CONSOLIDATION.md).

## Architecture

```text
Approved feeds / operator reports / authorized telemetry
          |
          v
HYBA identity + tenant + purpose + policy checks
          |
          v
Validation, provenance, freshness and normalization
          |
          v
Canonical five-form intelligence implementations
  | predictive | causal | counterfactual |
  | topological | geometric |
          |
          v
Cross-form correlation + uncertainty + disagreement
          |
          v
Scenario / defensive action-plan recommendations
          |
          v
Existing HYBA AL HARAS / L-HRAS governance
          |
          v
Analyst review → explicitly authorized response
          |
          v
Outcome verification + audit receipt + feedback
```

This is the target flow, not a claim that all connections are already wired.
The optimizer may rank candidate actions, but it must not change a policy
decision or grant privileges. Existing HYBA governance remains the authority.

## Proposed agent duties

| Intelligence form | Primary question | Guardrail |
|---|---|---|
| Predictive | What plausible future state or warning indicator is emerging? | Include time horizon, calibration, uncertainty and baseline |
| Causal | Which mechanism could explain the observed pattern? | Distinguish correlation from causation and expose assumptions |
| Counterfactual | How might outcomes differ under a stated alternative? | Make assumptions and scenario boundaries explicit |
| Topological | What structural relationship, path or boundary changed? | Record graph/model provenance and limitations |
| Geometric | How is the state/trajectory deviating in its defined representation? | Validate representation and metric; do not imply meaning from geometry alone |

These are the five canonical reasoning forms, not five independent authorities.
Each output should contain a versioned schema, evidence references, confidence
or uncertainty, timestamp, model/agent version and limitations. The system
must preserve conflicts between forms rather than averaging away critical
warnings.

## Defensive optimization

Candidate defensive actions can be represented as a constrained optimization
problem. The objective may minimize expected residual risk, service disruption,
cost and time-to-containment. Constraints encode dependencies, service-level
requirements, change windows, blast-radius limits and mandatory controls.

Compare:
- a deterministic policy/rule baseline;
- conventional optimization (for example, integer programming or greedy
  selection with documented bounds);
- classical simulated annealing or other quantum-inspired heuristics;
- an optional quantum-annealing or gate-model provider where a real backend is
  configured and the problem mapping is valid.

A simulator run is not evidence of quantum-hardware advantage. The existing
swarm channel describes its communication implementation as
`classical_coordinated_shared_state`; do not label this physical entanglement.
Every candidate must be revalidated by HYBA policy before execution.

## Trust, safety and resilience

- Agent messages are untrusted inputs and must be schema-validated.
- Use authenticated, tenant-scoped identities and least privilege.
- Enforce bounded concurrency, deadlines, quotas and circuit breakers.
- Keep a deterministic safe fallback if an optimizer times out or is unavailable.
- Record solver name, version, configuration, objective, constraints, runtime,
  feasibility and fallback reason.
- Require approval for disruptive actions unless a customer has explicitly
  configured a narrowly scoped, tested response policy.
- Actions must be idempotent where possible and include a recovery/rollback
  strategy.
- Never permit a model or agent to modify its own permissions or disable audit.
- Preserve purpose limitation, data minimization, retention rules and human
  accountability for consequential decisions.

## Delivery gates

1. **Inventory:** document the real runtime path across the existing five-form
   swarm, predictor, Guardian, policy and audit components.
2. **Contract:** add typed schemas and tests for malformed/stale/cross-tenant
   events, conflicting findings, timeouts and absent evidence.
3. **Replay:** build a fixed, sanitized defensive event corpus.
4. **Shadow mode:** produce recommendations without taking actions.
5. **Evaluation:** measure calibration, detection quality, false-positive rate,
   decision latency, resource use, policy violations and rollback success.
6. **Controlled response:** enable only after explicit authorization, threat
   modelling and incident-recovery testing.
7. **Quantum experiments:** benchmark separately; do not gate incident response
   on unproven quantum advantage.

## Non-goals

This is authorized defensive monitoring, early warning, resilience and decision
support. It is not an autonomous offensive agent, a cryptographic key-breaking
service, a system for coercive decisions based solely on inferred risk, or a
replacement for incident responders and independent security review.
