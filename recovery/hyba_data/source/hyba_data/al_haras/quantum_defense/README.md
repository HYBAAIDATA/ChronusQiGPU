# HYBA Consolidated Intelligence — AL HARAS Quantum Defence

This is the canonical quantum-defence package inside the HYBA codebase, not an
independent product or a separate national-security stack. Consolidation means
enhancing these existing components and wiring them into HYBA's shared
intelligence and governance path rather than duplicating them.

The national-security capability uses the existing five-form intelligence model:
**predictive, causal, counterfactual, topological and geometric**. The forms are
complementary reasoning lenses; their outputs require evidence, uncertainty and
validation. They are not five independent sources of truth.

See [the HYBA National-Security Consolidation plan](../../../../../../docs/al-haras/NATIONAL_SECURITY_CONSOLIDATION.md)
for the canonical component map, data flow, security principles and delivery
gates.

## Current package map

- `five_form_swarm.py` — existing multi-form duty/swarm assessment.
- `honeypot_swarm.py` — decoy/honeypot-related defensive capability.
- `multi_layer.py` — layered threat/defence composition.
- `threat_model.py` — threat capability and classical-defence modelling.
- `__init__.py` — public package exports.

Related controls remain part of the same HYBA architecture:
`al_haras.paradigm_shift.SecurityGovernor` owns state-governance decisions,
`al_haras.security_core` provides audit/trust primitives, the AL HARAS runtime
owns tenant, entitlement, policy and fail-closed boundaries, and `l_hras/guardian.py`
contains the broader Guardian conjunction. Existing `Intelligence/` and
`toe/intelligences/` capabilities should be integrated through explicit
contracts; mining-specific implementations must not be assumed to be
national-security-ready merely because they exist.

## Target architecture

1. **Five intelligence forms** — each produces bounded, evidence-linked
   assessments using its canonical HYBA implementation.
2. **Shared orchestrator** — correlates outputs, preserves disagreement and
   records uncertainty/provenance.
3. **Optimization router** — optionally ranks defensive action plans using
   classical optimization first, with quantum-inspired or hardware-backed
   adapters only when explicitly configured and benchmarked.
4. **HYBA policy governor** — checks every proposed action; intelligence and
   optimization cannot grant authority.
5. **Evidence and audit** — record decision metadata and evidence digests
   without putting secrets or raw sensitive payloads into logs.
6. **Response adapter** — recommendations/dry-run by default; consequential
   actions require explicit authorization, scoped credentials, idempotency and
   rollback.

## Quantum terminology and claim boundaries

The package name does not imply that quantum hardware is used. Swarm agents,
heuristic search, simulated annealing, quantum-inspired optimization and actual
quantum computation are different implementations and must be identified
accurately in runtime metadata.

- **Swarming** means coordinated agents unless a concrete implementation says
  otherwise.
- **Supposition** is a hypothesis or candidate plan, not proof of a threat.
- **Tunnelling-inspired search** is a heuristic unless a documented backend
  implements a specific physical or algorithmic method.
- **Annealing** must state whether it is classical simulated annealing,
  quantum-inspired annealing, or a named quantum-annealing provider.
- The existing swarm's channel explicitly identifies its implementation as
  `classical_coordinated_shared_state`; do not call that physical entanglement.
- **PQC** is a cryptographic property of selected standardized algorithms and
  validated implementations, not a property conferred by this directory.

## Security invariants

- Fail closed when required identity, policy, provenance or evidence is missing.
- Treat agent output as untrusted evidence, never as authorization.
- Bound agent count, input size, runtime, retries and external calls.
- Keep tenant boundaries and least-privilege credentials enforced outside the
  model/agent layer.
- Require human approval or an explicitly approved policy for high-impact
  actions such as disabling accounts, changing firewall rules or isolating
  production systems.
- Preserve auditability, reproducible evaluations and rollback.
- Never use the defensive optimizer to attack third-party systems or search for
  cryptographic secrets.

## Development sequence

1. Inventory existing behavior and add contract tests before refactoring.
2. Define a versioned, typed finding/action-plan schema.
3. Add a deterministic baseline and reproducible replay fixtures.
4. Benchmark alternative optimizers against that baseline.
5. Add provider adapters behind feature flags only after evidence of benefit.
6. Integrate proposed actions through the HYBA governor; do not bypass it.
