# AL HARAS Quantum Security Swarm

Status: design proposal; not a claim that all components are implemented.

## Objective

Extend the existing AL HARAS protection layer into a governed defensive
orchestration system. It combines evidence-producing specialist agents,
risk-aware planning and optional optimization backends while retaining the
existing AL HARAS authorization and audit boundaries.

The core security proposition is **better coordinated decisions**, not an
unsupported claim that quantum computation automatically detects attacks or
makes a system unbreakable.

## Architecture

```text
Telemetry and asset inventory
          |
          v
Input validation + tenant / identity / policy checks
          |
          v
Defensive agent swarm (parallel, bounded, evidence-producing)
          |
          v
Correlation + confidence + disagreement handling
          |
          v
Action-plan generator
          |
          v
Optimizer router
  | classical | quantum-inspired | optional quantum provider |
          |
          v
AL HARAS SecurityGovernor / policy decision
          |
          v
Dry-run recommendation or explicitly authorized response
          |
          v
Tamper-evident audit receipt + outcome verification
```

The optimizer may rank candidate actions, but it must not change the policy
decision or grant privileges. The SecurityGovernor remains the authority for
allow/deny/escalate/quarantine decisions.

## Proposed agent duties

| Agent | Evidence to produce | Guardrail |
|---|---|---|
| Identity | Unusual login, token and privilege-change signals | Never request or expose plaintext credentials |
| Endpoint | Process, file and host posture indicators | No arbitrary command execution |
| Network | Connection anomalies and segmentation evidence | Read-only telemetry by default |
| Cloud | IAM, configuration and workload drift | Scope access to the authorized tenant/account |
| Crypto posture | Algorithm, protocol, certificate and dependency inventory | Never collect private keys as inventory data |
| Threat correlation | Correlated indicators, provenance and confidence | Distinguish observed facts from inference |
| Response planner | Candidate containment/remediation plans and expected impact | Propose only; no authority to execute |
| Verification | Post-action checks and recovery status | Report failure honestly; do not infer success from submission |

Each agent returns a versioned record with: `event_id`, `tenant_id`,
`asset_id`, `observations`, `evidence_refs`, `confidence`,
`timestamp`, `agent_version`, `limitations`, and `recommended_next_step`.
Secrets and raw sensitive payloads should not be copied into the audit ledger.

## Defensive optimization

Candidate actions can be represented as a constrained optimization problem.
The objective may minimize expected residual risk, service disruption, cost
and time-to-containment. Constraints encode dependencies, service-level
requirements, change windows, blast-radius limits and mandatory controls.

The system should compare:
- a deterministic policy/rule baseline;
- conventional optimization (for example, integer programming or greedy
  selection with documented bounds);
- classical simulated annealing or other quantum-inspired heuristics;
- an optional quantum-annealing or gate-model provider where a real backend is
  configured and the problem mapping is valid.

The output is a **ranked candidate plan**, not an authorization token. Every
candidate must be revalidated by AL HARAS policy before execution.

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
- Treat disagreement between agents as a reason to gather evidence or escalate,
  not as a reason to average away a critical warning.

## Quantum-safe foundations

The platform's own transport, identity, signing and key-establishment layers
must have a separately managed cryptographic migration plan. Use current
standards-based PQC implementations and vendor-supported protocol profiles.
Do not label the entire product quantum-resistant merely because one component
uses a PQC algorithm.

## Delivery gates

1. **Inventory:** document existing AL HARAS swarm, governor and ledger APIs.
2. **Contract:** add typed schemas and unit tests for malformed/stale/cross-tenant
   events, conflicting findings, timeouts and absent evidence.
3. **Replay:** build a fixed, sanitized defensive event corpus.
4. **Shadow mode:** produce recommendations without taking actions.
5. **Evaluation:** measure detection quality, false-positive rate, decision
   latency, resource use, policy violations and rollback success.
6. **Controlled response:** enable only after explicit authorization, threat
   modelling and incident-recovery testing.
7. **Quantum experiments:** separately benchmark candidate optimizers; do not
   gate incident response on unproven quantum advantage.

## Non-goals

This system is for authorized defensive monitoring and remediation. It is not
an autonomous offensive agent, a cryptographic key-breaking service, or a
replacement for endpoint/network controls, secure engineering, incident
response staff or independent security review.
