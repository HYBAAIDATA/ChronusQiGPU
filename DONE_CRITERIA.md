# Chronus Phi Framework v10 — Definition of Done and Evidence Contract

Status: **IN IMPLEMENTATION / NOT PRODUCTION QUALIFIED**.
Delivery target: `main` through PR #120; do not claim merge or release until GitHub confirms them.

Scope: general exact mathematical and geometric search architecture, including
cross-domain discovery, TURING operators, Chronus execution substrates and
optional physical acceleration. Mining is one application; do not make its
pool connection a precondition of other legitimate workloads.

This checklist adapts the supplied v10 Definition of Done and compute-layer
specification to preserve exactness, authority and evidence boundaries.
A test that only instantiates a class does not prove the complete mathematics.

## Phase 1 — Geometry and mathematical correctness

- [x] Source implementation: exact 600-cell/120-cell dual with 120 primal
      and 600 dual vertices, 1200 dual edges, 720 pentagonal boundaries
      and 120 dodecahedral dual cells.
- [x] Source implementation: 32 exact spherical face-normal directions,
      12 dodecahedral faces and 20 icosahedral faces.
- [x] Source implementation: reversible 11-coordinate exact feature map;
      explicitly *not* asserted to be an H4 irreducible representation.
- [x] Source implementation: finite 32×600 basis indexing and checked
      graph-automorphism transport, including explicit holonomy checks.
- [x] Source implementation: graph Laplacian with exact integer
      positive-semidefinite energy identity and optional float diagnostics.
- [x] Source implementation: discrete SU(2) exact Gaussian-rational
      Wilson loop, not a continuum Yang–Mills mass-gap proof.
- [x] Source implementation: TURING sparse 19,200-dimensional finite Hilbert
      factors and exactly normalized Born distributions.
- [x] Source implementation: restricted exact unitary operators for
      integer quarter-turns of Hermitian involutions.
- [ ] Evidence: successful exact-commit tests and mathematical review,
      including correct incidence, cocycles, gauge invariance and inverse
      transformations.
- [ ] Evidence: independent continuous 11D fiber bundle specification
      with metric, topology, transition functions and preservation proof
      if those stronger claims remain required.
- [ ] Evidence: general spectral exactness/projection and exact arbitrary
      Hamiltonian evolution; finite involution subfamily is not equivalent.

## Phase 2 — Domain discovery and new geometries

- [x] Exact Aₙ, Dₙ and 240 E₈-root coordinate families.
- [x] Signature candidate matching, bounded rational SPD metric descent,
      explicit loss function and positive-definite checks.
- [x] Finite SAT, Ising and rational quadratic-loss problem adapters.
- [ ] Independent demonstration that chosen symmetry genuinely matches
      new problems, including proof of group action/orbit certificates.
- [ ] Complete Leech 24D lattice construction, minimal norm-4 certificate
      and trusted nontrivial automorphisms.
- [ ] Real datasets and independent MCMC or alternative baseline tests.

## Phase 3 — Compute Abstraction Layer

- [x] Chronus task scheduler with bounded asynchronous submissions,
      error/timeout propagation, idempotent start/stop and counters.
- [x] Exact host operations for `I32 tensor L_120cell` and TURING
      involution/phase/amplification; classification reports **host math**.
- [x] Optional physical MLX/Metal operations through the existing
      `MetalTensorBackend` with device availability/known-answer check,
      finite float32 input, memory bound and independent host parity.
- [x] Physical Metal 32×600 dual-graph operator avoids allocating an
      19,200×19,200 dense Hamiltonian.
- [x] Local command interface for exact checks, Metal known answer and
      caller-provided float32 [32,600] state execution.
- [ ] Measured Mac M3/M5 hardware result, kernel/device metadata, readback
      hashes, run/environment logs and performance counters on exact commit.
- [ ] Independently checked exact arithmetic kernels on a physical
      accelerator for algebraic Hilbert evolution; **not** supplied by
      MLX float32. No 40–50× speedup, 96GB capacity or zero-copy claim
      is adopted without measured, device-specific evidence.
- [ ] Integration with authorized production execution routing and
      startup/shutdown/cancellation guards without broadening privileges.

## Phase 4 — Formalization and tests

- [x] Source patch removes one unconditional unproved Lean claim and
      retains a conditional theorem requiring an explicit witness.
- [x] Python mathematical unit and cross-domain test files committed.
- [x] Compute exact/error/absence-of-GPU tests committed.
- [ ] Exact-commit Lean compiler log, proof-trust audit and all relevant
      existing Lean checks verified; no reliance on `sorry`.
- [ ] Python 3.10, 3.12 and 3.13 test lanes, packages, security scans
      and project-specific qualification workflows green.
- [ ] Coverage measured and reported with a scope-specific denominator;
      no unmeasured 100% claim.
- [ ] Actual Apple Silicon Metal test and, separately, physical OpenCL
      exact-kernel tests where supported.
- [ ] CodeRabbit/Qododo reviews recorded, addressed and accepted.

## Phase 5 — Applications, deployment and publication

- [ ] Operational pool results for mining *only*: Stratum V1 real handshake,
      accepted authorization, clean-job cancellation, locally verified
      SHA-256d, independently recorded share verdict. Do not identify
      subscription/authorization as accepted shares.
- [ ] Reproducible scientific results: real benchmark inputs, SHA-256
      digests, wall clocks and oracle counts, baseline parity and
      statistical intervals; no generated figures passed off as results.
- [x] Local inspect/phase injection and optional Jupyter visualization.
- [ ] Physical runtime and deployment qualifications with THESEUS custody,
      OVID equivalence contracts, AL HARAS enforcement, Salamander
      remediation evidence and EUCLID/PYTHIA authority boundaries.
- [ ] Full claims audit and approved dissemination; no automatic
      public whitepaper claiming proofs or quantum advantage.

## Exact-commit acceptance commands

```sh
python -m pytest -q tests/test_geodesic_phi_foundations.py \
  tests/test_geodesic_cross_domain.py \
  tests/test_igpu_compute_dispatch.py \
  packages/turing/tests/test_turing_exact_hilbert_geometry.py
python -m compileall -q src/chronus/geodesic src/chronus/compute \
  packages/turing/src/turing/exact/geometry
python -m chronus.compute --mode geometry
python -m chronus.compute --mode exact-known-answer
# Physical Apple Silicon / MLX host ONLY:
python -m chronus.compute --mode metal-known-answer
# A caller-provided 32x600 float32 NPY file, no fabricated input:
python -m chronus.compute --mode metal-state \
  --state-npy real_input.npy --output-npy measured_output.npy
```

`python -m chronus.compute --mode metal-state` is an approximate
linear-algebra execution test, **not** exact `exp(-iHt)`.

## Observed live gating information

At last inspected PR #120 head, GitHub Actions reported failures for
Packages, Mining Regression, Acceleration, Storage and Chronus V2
Qualification while CI remained queued. Job log fetch returned
`BlobNotFound` and no actionable logs. **Cause unavailable**: do not
declare either repository regression or infrastructure fault without
evidence. Preserve this boundary until a verified new run is inspected.

## Sign-off

- [ ] All required quality gates green
- [ ] Mathematical proof and test evidence attached to exact commit
- [ ] Approved runtime/device observations where claimed
- [ ] Independent review and release owner approval
- [ ] Merge to `main` confirmed by GitHub
- [ ] Release/deployment qualification recorded

**Verdict until the above gates close: HOLD — NOT CERTIFIED.**
