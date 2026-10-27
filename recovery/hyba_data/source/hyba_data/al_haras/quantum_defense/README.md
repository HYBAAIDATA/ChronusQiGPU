# AL HARAS Quantum Defense

This directory is the canonical quantum-defense package for AL HARAS. Existing
callers already import `al_haras.quantum_defense`; keep new work here rather
than creating a parallel security package. The `hermes/quantum_defense`
compatibility shims should remain shims until a separately governed deprecation.

## Current package map

- `five_form_swarm.py` — existing multi-form duty/swarm assessment.
- `honeypot_swarm.py` — decoy/honeypot-related defensive capability.
- `multi_layer.py` — layered threat/defence composition.
- `threat_model.py` — threat capability and classical-defence modelling.
- `__init__.py` — public package exports.

Related controls remain outside this subpackage:
`al_haras.paradigm_shift.SecurityGovernor` owns state-governance decisions,
`al_haras.security_core` provides audit/trust primitives, and the AL HARAS
runtime owns tenant, entitlement, policy and fail-closed boundaries.

## Intended target architecture

1. **Duty agents** — identity, endpoint, network, cloud, application and
   cryptographic-posture specialists produce bounded evidence records.
2. **Swarm coordinator** — correlates findings, tracks disagreement and assigns
   confidence/provenance; agents do not grant each other authority.
3. **Optimization router** — optionally ranks defensive action plans using
   classical optimization first, with quantum-inspired or hardware-backed
   adapters only when explicitly configured and benchmarked.
4. **Policy governor** — checks every proposed action against AL HARAS policy.
5. **Evidence ledger** — records decision metadata and evidence digests without
   placing secrets or raw sensitive payloads in logs.
6. **Response adapter** — defaults to recommendations/dry-run; production
   containment requires explicit policy, scoped credentials, idempotency and
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
- **Entanglement** must not be claimed from ordinary agent communication.
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
6. Integrate proposed actions through the AL HARAS governor; do not bypass it.

See `docs/al-haras/QUANTUM_SECURITY_SWARM.md` and
`docs/al-haras/QUANTUM_OPTIMIZATION_BENCHMARKS.md` for the system design and
evaluation gates.
