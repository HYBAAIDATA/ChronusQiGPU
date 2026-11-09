# Acceleration layer work order

Status: **in progress; not release-qualified**. Input: [acceleration review](../reviews/acceleration_review.md), REVIEW FIRST and the mathematical exposition supplied with the request. The page establishes evidence expectations rather than a complete implementation specification. Do not treat planned APIs as implemented capabilities.

## Operating rules

Implement under `src/chronus/acceleration/` without changing existing interfaces until reviewed. Deliver modules incrementally; a module enters a commit only after invariant, property, adversarial, edge, unit, integration and end-to-end tests pass locally and measured module coverage is at least 90%. Each module has an explicit bounded public API, documented assumptions, invalid-input refusal and an equivalent-task baseline. CI must independently run the same gates at a named commit. No speedup is promised, and a timing ratio never generalizes beyond its measured task.

## Capability map and planned public APIs

| Module | Public API and bounded scope | Acceptance and limitations |
| --- | --- | --- |
| `fourier` | `qft(values, inverse=False)` returns the normalized discrete transform of an explicit power-of-two vector. | Check direct DFT agreement, round trip and norm; time against direct DFT and an optimized FFT comparator. No promise of advantage for explicit data. |
| `state` | Validate bounded complex vectors, normalization and unitary application. | Compare against independently computed small examples; account for all amplitudes and floating-point error. |
| `tensor` | Bounded matrix low-rank approximation and reconstruction with discarded-singular-value error. | Compare to direct SVD; refuse invalid rank or excessive input; no universal compression claim. |
| `composition` | Compose and validate finite linear maps. | Check associativity within tolerance and composition against direct multiplication; no automatic synthesis advantage claim. |
| `geometry` | Pure-state metric and regularized natural-gradient step with reported conditioning. | Gauge-invariance checks, singular-metric refusal or explicit regularization and comparator. |
| `topology` | Finite boundary-matrix validation and Betti numbers for bounded complexes. | Check boundary composition and ranks against independently worked examples; no security or fault-tolerance claim. |
| `search` | Bounded amplitude-rotation model and explicit reference search. | Verify probabilities and charge all oracle evaluations; no runtime advantage claim without equivalent measured workloads. |
| `walks` | Bounded finite graph walk evolution and observables. | Validate normalization and graph-dependent behavior; no universal mixing claim. |
| `variational` | Bounded energy evaluation for a supplied state and Hermitian matrix. | Test variational bound; no optimizer convergence claim. QAOA/VQE require separately specified ansatz and optimizer. |
| `kernels` | Bounded normalized-state overlap kernel. | Test symmetry, diagonal and positive semidefiniteness within tolerance; no predictive advantage claim. |
| `phase` | Bounded eigenphase reference calculation with explicit precision and error. | Compare against direct eigenvalue computation; no uncounted controlled-operation claims. |

These are proposed interfaces, not a commitment that all mathematical claims can be realized as accelerated products. Exact signatures, supported inputs and resource limits are finalized per module before implementation. The capabilities not yet implemented are refused, not silently substituted. Reuse existing modules only after checking their documented semantics; in particular, the existing finite-field state and search code is not a complex-amplitude sampling model.

## Tests and benchmark for each module

- **Invariant:** bounded exhaustive checks or established numerical invariants; document the domain and tolerance.
- **Property:** generated inputs with Hypothesis and regression cases for discovered failures.
- **Adversarial:** malformed, nonfinite or resource-exhausting inputs must fail deterministically; this does not claim security certification.
- **Edge:** empty, singleton, limits, invalid types and numerical boundaries, as applicable.
- **Unit:** each public callable and documented result.
- **Integration:** interaction with a second independently implemented mathematical operation or repository interface.
- **End-to-end:** a clean invocation through the public API, verification of the output and complete workload flow. This is not a sign-in-to-settlement customer journey.

Commit actual generated test output, coverage report, per-module benchmark raw records and a whole-layer benchmark at named paths. Benchmark equivalent outputs, input preparation and extraction costs, repeated timings, correctness tolerances and environment; retain all raw measurements. Report setup costs separately when excluded. Record SHA-256 hashes in the capability report, without claiming a signature until a conformant implementation and key custody are independently verified. A CI link and exact commit SHA must be verified, not inferred from a workflow file.

## Release blockers and external decisions

Unspecified: customer workload and reference, target deployments, pricing, authorized production service, control owners, independent penetration assessment, compliance/authorization, support SLA, and conformant evidence signing. The existing claim audit withdraws release and cryptographic claims. Until these are resolved, outputs are engineering evidence only; no production, enterprise, government, analyst endorsement or customer-reference claim is permitted. Customer-facing and executive packs must explicitly distinguish missing evidence from achieved results.
