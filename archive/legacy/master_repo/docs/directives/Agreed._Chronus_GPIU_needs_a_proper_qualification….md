Agreed. Chronus GPIU needs a proper qualification suite, not simply 28 invariant checks or a collection of synthetic demonstrations.

The test programme must establish five distinct things:

1. Unit correctness — individual mathematical operations and software components produce correct results.
2. Property correctness — mathematical laws hold across broad input domains, not just selected examples.
3. Invariant preservation — the 28 architectural and mathematical invariants hold throughout execution, including under concurrency, persistence, recovery and failure.
4. Adversarial robustness — malformed, hostile, degenerate and resource-exhausting inputs cannot produce incorrect results, corrupt state or bypass controls.
5. Real-world workload performance — representative data and computational workloads establish throughput, latency, memory consumption, scaling and reproducibility.

These must be separate test classes with separate results. Passing a unit test must not be presented as proof of a mathematical property; passing an invariant test must not be presented as production qualification.

## Chronus GPIU — qualification and benchmarking directive

Add the following as a mandatory qualification layer to the v8 mathematical execution correction. It applies across all 15 tiers and all 28 invariants. It must not alter the existing class structure, class order, method signatures or architectural responsibilities.

### 1. Unit tests — component-level correctness

Every implemented class and public method must have unit tests covering:

- Normal inputs and expected outputs.
- Boundary conditions and degenerate inputs.
- Invalid types, dimensions and parameter combinations.
- Numerical precision, rounding and overflow behaviour.
- Exception handling and fail-closed behaviour.
- State mutation, immutability and side effects.
- Deterministic behaviour and reproducibility.

Quantum mathematical operations must include tests for:

| Operation                 | Required correctness checks                                            |
| ------------------------- | ---------------------------------------------------------------------- |
| State construction        | Dimension, normalisation and valid representation                      |
| Tensor products           | Correct dimensions, ordering and amplitudes                            |
| Linear operators          | Linearity and correct operator application                             |
| Unitary operators         | \\(U^\dagger U=I\\)                                                    |
| Hermitian operators       | \\(A^\dagger=A\\)                                                      |
| Measurement probabilities | Born-rule probabilities and total probability                          |
| Density matrices          | Hermiticity, trace one and positive semidefiniteness                   |
| Partial trace             | Correct reduced density matrix                                         |
| Entanglement              | Schmidt decomposition and independently verified entanglement measures |
| Quantum channels          | Complete positivity and trace preservation where required              |
| Geometric operations      | Metric symmetry, curvature properties and coordinate consistency       |
| Topological operations    | Braid relations, Yang–Baxter and applicable coherence identities       |

Tests must distinguish exact algebraic results from floating-point approximations.

### 2. Property-based tests — mathematical laws over broad domains

Use generated inputs and property-based testing, not just hand-selected examples.

Test properties including:

- Linearity of operators.
- Associativity of tensor products, accounting for representation conventions.
- Unitary norm preservation.
- Measurement probability normalisation.
- Density matrix positivity and trace preservation.
- Partial-trace consistency.
- Equivalence of mathematically equivalent representations.
- Inverse and composition identities.
- Conservation laws where mathematically applicable.
- Numerical convergence against higher-precision or exact reference calculations.
- Serialization and deserialization round-trip equality.
- Content-addressing stability.
- Deterministic replay of identical inputs.

Use Hypothesis or an equivalent property-testing framework. Record seeds, generated input characteristics and minimized counterexamples.

Important: A property test establishes that a property held over its tested domain. It does not establish a universal mathematical proof.

### 3. Invariant tests — all 28 invariants

Retain I1–I28, but strengthen their tests.

Each invariant must have:

- A precise mathematical or architectural definition.
- A machine-executable assertion.
- Positive and negative test cases.
- A failure-injection test where applicable.
- An independently derived expected result.
- A traceable test ID and execution record.

The invariant suite must execute at several levels:

1. Individual component.
2. Cross-tier integration.
3. Full Chronus pipeline.
4. Concurrent execution.
5. Persistence and recovery.
6. Repeated execution under changing workloads.

Correct the semantics of any existing invariant that overstates what its test proves. For example, structural signature formatting is not cryptographic signature verification; a local endpoint test is not proof of a deployed public verification service; numerical Navier–Stokes experiments do not prove global regularity.

I28 must not claim that Millennium Prize Problems have been solved. It can establish that specified mathematical formulations, computations or proof-related workflows have been implemented and tested.

### 4. Adversarial testing — deliberately hostile conditions

Test the system against:

| Attack or failure class | Required tests                                                                                              |
| ----------------------- | ----------------------------------------------------------------------------------------------------------- |
| Numerical attacks       | NaN, infinity, overflow, underflow, catastrophic cancellation                                               |
| Mathematical invalidity | Non-unitary operators where unitary operators are required; invalid density matrices; impossible dimensions |
| Resource exhaustion     | Exponential state growth, oversized tensors, memory pressure and pathological workloads                     |
| Input manipulation      | Malformed objects, unexpected encodings, invalid schemas and corrupted payloads                             |
| State corruption        | Interrupted writes, partial updates, inconsistent versions and invalid recovery records                     |
| Concurrency             | Race conditions, duplicate jobs, out-of-order completion and conflicting writes                             |
| Security                | Tenant isolation, privilege escalation, forged receipts, signature tampering and replay attacks             |
| Algorithmic attacks     | Degenerate matrices, ill-conditioned systems, pathological graph structures and worst-case inputs           |
| Pipeline failures       | Worker termination, unavailable dependencies, timeouts and interrupted execution                            |

The system must never convert an invalid result into a successful result merely to complete a workload.

### 5. Real-world workload benchmarks

This is essential. Do not qualify Chronus using only random arrays, toy circuits, fabricated telemetry or self-generated demonstration data.

Build a versioned workload corpus from identifiable, externally sourced material.

Quantum mathematics and computational workloads

- Quantum chemistry: molecular Hamiltonians, energy calculations and ground-state workloads.
- Quantum optimisation: representative QUBO and Ising problem instances.
- Quantum circuits: published circuit benchmarks with known gate structures and reference outputs.
- Quantum information: entanglement, channel, state tomography and information-theoretic workloads.
- Quantum error correction: published syndrome and decoding instances.
- Quantum geometry and topology: reference manifolds, operator sets, braid representations and coherence workloads.

General mathematical and computational workloads

- Large sparse and dense linear algebra.
- Eigenvalue and eigenvector calculations.
- Tensor contractions.
- Graph and expander computations.
- Exact and modular arithmetic.
- Symbolic algebra and numerical optimisation.
- Distributed reductions and large-scale data transformations.

Enterprise and persistence workloads

- Real datasets with documented schemas and provenance.
- Large-scale OVID object ingestion and retrieval.
- THESEUS journal, replay and recovery workloads.
- Concurrent multi-tenant access.
- Versioned transformations and materialisation.
- Large lineage graphs and content-addressed verification.

For each dataset, record its source, licence, version, checksum, size, schema and preprocessing. Do not silently alter the source data.

Synthetic workloads may be used for fuzzing, controlled edge cases and stress testing, but they must be labelled synthetic and must not be presented as real-world benchmark evidence.

### 6. Performance and scalability benchmarks

Measure actual execution, not estimates.

| Metric              | What must be measured                              |
| ------------------- | -------------------------------------------------- |
| Throughput          | Completed operations per second                    |
| Latency             | p50, p95, p99 and maximum                          |
| Memory              | Peak and steady-state memory consumption           |
| CPU                 | Utilisation and execution time                     |
| Parallelism         | Scaling with worker count                          |
| Data movement       | Bytes transferred and transfer overhead            |
| Storage             | Read/write throughput and retrieval latency        |
| Recovery            | Recovery time and replay correctness               |
| Numerical quality   | Error against exact or higher-precision references |
| Resource efficiency | Completed valid work per unit of resource          |

Benchmark at increasing workload sizes. Include warm and cold runs, repeated trials, and confidence intervals.

For exponential representations such as dense \\(2^n\\) state vectors, explicitly measure the memory and computational scaling. Compare appropriate symbolic, sparse, tensor-network, stabiliser and dense representations where applicable. Do not claim a general complexity improvement without evidence.

### 7. Independent reference validation

Chronus must not validate itself exclusively.

For every major mathematical workload, compare results against an independent reference:

- Published analytical results.
- Exact symbolic calculations.
- Independently implemented numerical methods.
- Established mathematical reference datasets.
- Independent implementations of relevant algorithms.

External quantum software may be used as a validation oracle where appropriate. It must not become a Chronus runtime dependency or redefine Chronus as a quantum hardware simulator.

Discrepancies must be recorded, investigated and resolved or explicitly classified as unresolved.

### 8. Qualification gates

## Mandatory release gates

1. Gate 1 — Unit correctness

   All required component tests pass. No unimplemented methods disguised as successful operations.
2. Gate 2 — Mathematical properties

   Property suites pass within declared domains and numerical tolerances.
3. Gate 3 — Invariant preservation

   All 28 invariants pass with corrected, defensible test semantics.
4. Gate 4 — Adversarial robustness

   No unresolved critical correctness, security or data-integrity failures.
5. Gate 5 — Real-world workload

   Representative external datasets execute successfully with reproducible results.
6. Gate 6 — Performance and scaling

   Measured performance meets declared acceptance thresholds, with resource consumption documented.
7. Gate 7 — Independent verification

   Key results are checked independently and evidence is retained.

No automatic qualification from partial passes

A failure at a mandatory gate blocks the corresponding release qualification. Report the exact failed gate rather than averaging failures into an overall score.

### 9. Required benchmark artefacts

The implementation must produce a durable qualification record containing:

- `unit_test_results`
- `property_test_results`
- `invariant_test_results`
- `adversarial_test_results`
- `real_world_workload_results`
- `performance_benchmark_results`
- `independent_reference_results`
- `dataset_provenance_manifest`
- `failure_and_regression_register`
- `qualification_summary`

Every result must identify the source commit, software version, execution environment, dataset version, configuration, timestamp, test ID and outcome.

Use OVID for durable, versioned benchmark artefacts and THESEUS for execution lineage, provenance, recovery and evidence custody.

## The critical acceptance principle

Chronus must demonstrate that it performs correct mathematical computation on real workloads, not merely that its classes instantiate and its demonstrations produce plausible outputs.

The distinction between software execution and physical hardware execution must remain explicit. A benchmark running on a CPU is valid evidence of software mathematical execution; it is not evidence of GPU, QPU or quantum hardware execution.

Likewise, an algorithm completing a workload is not proof that it is mathematically optimal, universally scalable or physically quantum.

My recommendation: make this a mandatory qualification framework, not an optional benchmark module. No Chronus release should receive a production-qualified designation until all applicable gates have passed and the evidence is independently inspectable.