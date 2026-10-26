# HYBA Scientific Constitution — Execution Record

**Purpose:** preserve and enforce the scientific boundary while the HYBA Intelligence substrate is rebuilt and wired.

## Architectural invariant

HYBA is treated as **one shared mathematical/intelligence substrate**, not a collection of domain-specific intelligence implementations. Domain adapters may translate inputs and outputs, but predictive, causal, counterfactual and quantum primitives remain shared infrastructure.

The foundational state-transition pattern is:

`STATE_t -> TRANSITION MODEL T -> predicted STATE_(t+1) -> OBSERVATION -> ERROR -> ADAPTATION`

The repository already contains a live shared substrate in `python_backend/hyba_substrate/manifold_orchestrator.py`, including predictive, causal, counterfactual and quantum intelligence lobes. `EuclidCore` instantiates these lobes and is therefore the correct integration point; a parallel standalone predictive engine would violate the one-backend invariant.

## Four orders of truth

| Order         | Meaning                                  | Evidence required                         |
| ------------- | ---------------------------------------- | ----------------------------------------- |
| Mathematical  | Follows from explicit axioms/definitions | proof or derivation                       |
| Computational | Reproduces in code                       | source + deterministic test + environment |
| Empirical     | Observed in a real system                | raw measurement + provenance              |
| Hypothesis    | Candidate explanation/prediction         | falsification experiment                  |

No lower order is allowed to silently promote itself into a higher order.

## Current evidence

- `UniversalPredictor` exists in the live backend and has an older archived ancestor. The live implementation is explicitly described as a practical domain-agnostic ML framework rather than magic code.
- `EuclidCore` already owns the six intelligence lobes and the discovery engine.
- `hyba_substrate.manifold_orchestrator` already provides shared predictive, causal, counterfactual and quantum components.
- Discovery verification was previously committed as `a52c53d` and Cathedral integration followed as `1d6c7add`.
- The current repository therefore has substantial wiring already; the remaining work is to make the state-transition semantics explicit, test them adversarially, and remove any duplicate/heuristic pathways that bypass the shared substrate.

## Phase gates

### Phase 0 — Baseline freeze

**This branch:** tooling added in `scripts/archaeological_freeze.py`.

The freeze records git state, runtime, dependency state and SHA-256 file manifest. It deliberately does **not** fabricate historical stdout or test results; historical artifacts must be attached as captured evidence.

### Phase 1 — Clean-room reproducibility

Gate: a fresh environment reproduces the same mathematical and computational results without access to developer-local state.

### Phase 2 — Causal architecture trace

Gate: every production intelligence path can be traced from input -> shared substrate -> decision -> evidence. Domain adapters must not contain alternate predictive engines.

### Phase 3 — Scientific stress matrix

Required attacks:

1. empty/zero state;
2. constant/zero-variance state;
3. randomized destruction;
4. permutation null;
5. anonymous domain labels;
6. independent numerical implementation;
7. adversarial cyclic/trapping structures.

A test that fails is evidence of a gap, not evidence of a theorem.

### Phase 4 — Predictive-causal wiring

The implementation target is the **existing shared predictive and causal lobes**, not a new standalone engine. Required semantics:

1. accept a typed state;
2. construct/accept a transition representation;
3. predict a next state or trajectory;
4. compare prediction with observation;
5. expose residual/error explicitly;
6. update the transition representation from observed error;
7. record provenance through the existing memory/evidence paths.

The first intelligence criterion is **predictive-causal capability**: prediction alone is insufficient; the system must distinguish correlation from an interventionally testable causal relation where the available data permits it.

### Phase 5 — Domain invariance

The same substrate must execute structurally equivalent experiments over HR, finance, security, mining and quantum simulation adapters. Domain names are metadata, not mathematical operators.

Success means equivalent state-transition machinery, not identical numeric answers across unrelated domains.

### Phase 6 — Quantum first principles

Quantum components must be verified as exact classical simulations of their mathematical formulations unless actual quantum hardware evidence is separately attached.

Required contracts include density-matrix positivity, unit trace, unitary preservation, partial trace identities and normalized measurement probabilities.

### Phase 7 — Autonomic repair gate

Salamander may certify wiring/reachability/contract adherence. It must not certify mathematical truth.

### Phase 8 — Historical genealogy

Compare the archived `UniversalPredictor` / `UnifiedPlatformEngine` lineage with the live backend and preserve useful ancestors as provenance. Do not resurrect historical claims merely because they existed in older code.

### Phase 9 — External reproducibility

Package source, lockfile, tests, evidence manifests and explicit claim boundaries so an independent reviewer can reproduce results without trusting HYBA's internal agents.

## Non-negotiable scientific rules

- No component certifies its own scientific claim.
- No `P != NP` claim can be promoted from heuristic boundary crossings to a theorem without a formal proof.
- No "quantum advantage" claim can be promoted from a classical simulation or search heuristic to hardware evidence.
- No emergence score is meaningful until null controls demonstrate that the score is not generated by the detector itself.
- Warning-free execution is an engineering quality gate, not scientific proof.
- Historical artifacts are preserved exactly; corrections are additive and provenance-linked.
- A domain adapter may translate data, but it may not fork the intelligence primitive.
