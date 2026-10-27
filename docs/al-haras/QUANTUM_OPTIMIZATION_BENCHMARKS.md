# AL HARAS Quantum and Quantum-Inspired Optimization Benchmarks

Status: evaluation protocol proposal. No quantum speedup or production advantage
is claimed by this document.

## Research question

Can a quantum-inspired or quantum-hardware optimizer select safer defensive
action plans than strong classical baselines for representative AL HARAS
problems, within operational latency and cost limits?

## Suitable defensive problem classes

- Prioritizing remediation across dependent assets under a fixed budget.
- Selecting a low-disruption containment set subject to service dependencies.
- Scheduling certificate/PQC migrations across maintenance windows.
- Allocating limited analyst and compute capacity to high-risk investigations.
- Selecting a minimum-cost set of controls that satisfies explicit policy
  constraints.

Do not use security optimization as a pretext for attacking third-party systems
or attempting to recover cryptographic secrets.

## Candidate methods

| Method | Execution reality | Required comparison |
|---|---|---|
| Deterministic rules / greedy baseline | Classical | Reproducible baseline and clear feasibility checks |
| Integer/constraint programming | Classical | Best suitable solver with documented limits |
| Simulated annealing | Classical stochastic heuristic | Multiple seeds, solution quality and runtime distribution |
| Quantum-inspired optimizer | Classical hardware unless specified otherwise | Same objective, constraints and compute budget |
| Quantum annealing | Actual provider/hardware only when explicitly configured | Include embedding, queue, transfer, sampling and post-processing costs |
| Gate-model quantum algorithm | Actual quantum backend or explicitly labelled simulator | Include circuit depth, shots, noise, data-loading and classical overhead |

A simulator run is not evidence of quantum-hardware advantage. A heuristic called
"tunnelling" is not proof that physical quantum tunnelling occurred. Supposition
is a candidate hypothesis, not a validated result. Swarming refers to agent
coordination unless a specific quantum algorithm is demonstrated.

## Benchmark protocol

1. Use sanitized, reproducible problem instances representative of customer
   workflows; publish instance sizes and generation seeds.
2. Define objective and hard constraints before running the algorithms.
3. Compare all methods on identical instances and quality requirements.
4. Record best, median and worst objective value; feasibility rate; wall-clock
   latency; total compute/provider cost; memory use; timeout rate; and run count.
5. Include all end-to-end overhead: model construction, embedding, queueing,
   data transfer, repeated sampling and classical post-processing.
6. Use multiple seeds and report uncertainty, not only the best run.
7. Test out-of-distribution cases, adversarially malformed inputs and solver
   unavailability.
8. Keep a deterministic fallback and prove that infeasible solutions are
   rejected.
9. Evaluate security outcomes: expected residual risk, blast radius, service
   disruption, policy violations and rollback success.
10. Have results independently reviewed before making a performance claim.

## Minimum acceptance gates

- Every returned plan passes the same hard-constraint validator.
- No solver can authorize or directly execute an action.
- Timeouts and provider failures select the documented safe fallback.
- Results are reproducible within stated stochastic tolerances.
- Any claimed improvement exceeds measurement noise and includes full costs.
- Any production use has a documented benefit over the strongest practical
  baseline for that workload.
- Cryptographic algorithms and key material are not treated as optimization
  targets.

## Output record

Each experiment should record:
`benchmark_id`, `instance_digest`, `objective_version`, `constraints_version`,
`solver_name`, `solver_version`, `hardware_or_simulator`, `seed`,
`runtime_ms`, `provider_cost`, `feasible`, `objective_value`,
`constraint_violations`, `fallback_used`, and `artifact_refs`.

## Claim policy

Until the evidence exists, use language such as "experimental", "candidate",
"quantum-inspired", or "provider-backed". Do not claim "quantum advantage",
"quantum-resistant", "unbreakable", or a numerical speedup without a narrowly
defined, independently reproducible test supporting that exact claim.
