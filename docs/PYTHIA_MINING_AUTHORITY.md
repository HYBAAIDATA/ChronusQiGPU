# PYTHIA Canonical Mining Authority

## Status

**Canonical architecture / merge invariant.**

PYTHIA owns mining intelligence and final mining-plan composition. A pull request MUST NOT reduce, sideline, reassign, replace, artificially constrain, or make unreachable PYTHIA's mining intelligence, learning, memory, planning, search strategy, optimisation, quantum/tensor reasoning, historical corpus access, or real execution-fabric choice unless the repository owner expressly approves that architectural change.

This rule applies equally to observability, security, refactor, cleanup, consolidation, performance and mining-feature changes.

## Search-theory invariant

The search has structure and PYTHIA is required to use that structure in mining.
**Hendrix is the default production search algorithm.** PYTHIA composes the
search around Hendrix and may use supposition plus the Turing quantum arsenal,
including tunnelling, annealing, swarming and entanglement, to support the
search. The 32-face, 11D, H4/600 and Hilbert structures are supporting search
structure; they do not silently replace Hendrix as the final plan-bound
algorithm.

Any change that demotes Hendrix from the canonical default, bypasses PYTHIA
supposition, or makes the named support arsenal unreachable is an architecture
change and requires express repository-owner approval.

## End-to-end production authority map

```text
Bitcoin Core / Stratum
        |
        | authoritative job, target, epoch, session, historical chain data
        v
production AgenticMiningController
  +-- generation-scoped nonce leases
  +-- provisional SearchPlan / measured operating policy
        |
        | never final until PYTHIA composes it
        v
PYTHIA integrated mining cycle
  OBSERVE -> RECALL -> INTELLIGENCE -> SUPPOSE -> COMPOSE -> PLAN
    |           |           |            |          |
    |           |           |            |          +-- Turing / Quantum GPU / Kellogg tensor / Chronus census
    |           |           |            +------------- explicit hypothesis, not proof
    |           |           +-------------------------- predictive / causal / counterfactual / topological / geometric
    |           +-------------------------------------- PYTHIA memory + Bitcoin corpus
    +-------------------------------------------------- authoritative Stratum work identity
        |
        v
PYTHIA structured-search composition
  +-- supposition
  +-- 32-face -> 11D -> H4/600 -> Turing Hilbert support
  +-- Turing support arsenal: tunnelling / annealing / swarming / entanglement
        |
        v
Hendrix default complete traversal
        |
        v
Chronus-1 execution / physical fleet
        |
        v
real SHA256d -> host recheck -> target/stale gate -> mining.submit -> literal pool outcome
        |
        +----> PYTHIA LEARN -> memory/store
        +----> Salamander observe -> diagnose -> authorise -> act -> measure -> retain/rollback -> durable evidence
```

The final production SearchPlan therefore contains both upstream production-agentic provenance and the PYTHIA intelligence/composition receipt. The upstream planner cannot bypass PYTHIA; PYTHIA cannot redefine Stratum identity or proof validity.

## Intelligence is operational, not decorative

`chronus/mla1517/mining/pythia_agentic_cycle.py` makes the mining-intelligence cycle an explicit evidence object. For each final plan it records authoritative work observation, memory retrieval, a bounded result from the five-modal intelligence engine, an explicit supposition, available Turing/Quantum-GPU/Kellogg/Chronus capabilities, the upstream `AgenticMiningController` plan, the final PYTHIA directive, and later execution/verification/outcome/learning evidence.

`Intelligence/agentic_mining.py::AgenticMiningWorkflow` is retained as recovered six-phase research/advisory lineage. It is **not** promoted into a second pool writer. Canonical pool writing stays in the production Stratum coordinator.

## Supposition lineage

Supposition is a first-class PYTHIA planning concept. The exact historical `SuppositionEngine.form_supposition` implementation has not been recovered from the available source archives, so the repository MUST NOT fabricate that class and call it the original.

Surviving lineage is explicit:

- `legacy/python_backend/pythia_mining/precompute_cache.py` persists `supposition-prior` state;
- `Intelligence/agentic_mining.py` retains the older inference/agentic lifecycle;
- the production PYTHIA cycle emits an explicit `supposition_until_sha256d_evaluated` hypothesis receipt.

If the original class is recovered later it must attach behind this same PYTHIA authority rather than create another mining control plane.

## Memory and historical Bitcoin corpus

Current PYTHIA code has a four-tier dynamic memory implementation: working, episodic, semantic and archival. Mining execution outcomes are additionally journalled with causal/counterfactual/failure/meta evidence through the intelligence and production ledgers. Historical EUCLID seven-form memory is lineage and must not be silently represented as already identical to PYTHIA's four-tier implementation.

`Intelligence/bitcoin_corpus.py` has two source-preservation layers:

1. **Header/index corpus (always available when ingested):** canonical 80-byte header, block hash, exact Zeckendorf decomposition, Fibonacci addresses, Cassini certificates, Lucas residues, exact Binet/Fibonacci certificates and canonical header fields.
2. **Optional full serialized-block custody:** `raw_blocks` retains the exact bytes returned by Bitcoin Core `getblock(hash, 0)`, including transactions. Each body is content-addressed by `sha256(raw_block)` and must begin with the independently validated stored header. The active-chain mapping is rechecked during source observation.

The full-block layer is optional because storing the entire blockchain is large and must not be a live-mining dependency. `scripts/feed_pythia_bitcoin_corpus.py --include-raw-blocks` backfills from the earliest missing raw block even when headers were previously ingested. Existing header rows are idempotent.

The repository does **not** claim an independent transaction-body/merkle verifier merely because it preserves Bitcoin Core's canonical serialization. Consensus anchoring is the independently verified header; raw-body custody is exact-data preservation.

## Historical Bitcoin corpus -> Turing VQC training

`Intelligence/bitcoin_vqc_training.py` and `scripts/train_pythia_vqc_from_corpus.py` connect the validated corpus to Turing's recovered `VQCTrainingDataGenerator` and 32-face variational circuit. Training is explicit and bounded; it never runs synchronously inside the live Stratum hot path.

The trainer reads locally validated corpus rows, translates canonical header fields plus the historically valid nonce into the existing Turing training format, runs the existing VQC implementation, and writes an atomic parameter checkpoint plus corpus-range metadata and SHA-256 receipt.

Historical winning nonces are supervised examples only. Training success is **not** evidence that future winning nonces are predictable.

When `PYTHIA_VQC_CHECKPOINT` points to a compatible checkpoint, PYTHIA may use the trained VQC's ranked candidates as ordering advice inside the already-owned nonce lease. The list is mapped into that lease, merged with the existing PYTHIA schedule, and full lease coverage remains preserved by the executor. The VQC cannot prune coverage, change the target, validate a share, or fabricate a pool outcome. An absent checkpoint is reported as `NO_CHECKPOINT`; an untrained model is never silently promoted into production guidance.

## Full Turing / quantum arsenal

PYTHIA is not limited to a hand-selected list of quantum functions. The production authority exposes complete public module surfaces from current Turing and quantum-compute packages, including search, quantum-walk, swarm, annealing, variational, stabilizer, exact-state-vector, Hendrix, phi-machine, MIDAS/VQC, Trotter and modern algorithm modules.

Named reachability includes at minimum Grover/exact Grover-style search, Hendrix, coined/hypercube/Szegedy quantum walks, tunnelling, annealing, swarming, entanglement, measurement/collapse, VQE, QAOA, QFT, period-finding primitives, quantum simulation, quantum ML, hybrid algorithms and VQC surfaces.

Hendrix is the default production nonce-order/search algorithm. PYTHIA owns
composition around that default. Supporting algorithms need not all execute on
every block, but tunnelling, annealing, swarming, entanglement and the wider
arsenal must remain reachable to PYTHIA and must be reported truthfully when
used or unavailable. Supporting capability is not permission to replace
Hendrix silently.

## Kellogg = tensor

Kellogg's authority is **tensor**. PYTHIA may consume its tensor-network, exact-tensor, compressed-tensor and related tensor mathematics, and Turing/Chronus may compose with those tensor capabilities when appropriate. That composition does not make Kellogg the owner of quantum algorithms, mining intelligence, mining routing, or execution authority.

## Chronus is not a vendor runtime

Chronus is its own execution architecture. CUDA is an NVIDIA programming/runtime platform; NVIDIA is a hardware vendor; OpenCL and Metal are programming/runtime interfaces. Those are different categories and MUST NOT define the architectural model for Chronus.

The normative Chronus execution authority is `isa/chronus1.md` + `abi/chronus1-abi.md` + the Chronus conformance/compiler/emulator stack. Vendor/runtime APIs may exist only as explicit compatibility or reference adapters where implemented and evidenced.

## Supporting 600-way search fabric

The repository contains the H4/600-cell implementation under `chronus/h4_600.py` and `chronus/cell600_bind.py`: 120 geometric vertices, 600 tetrahedral cells, one normal frame per cell, every frame lifted/folded into the 11-dimensional search space, and 600 logical work shards over the leased nonce window.

The 32-face dodecahedron/icosahedron construction and the H4/600-cell fabric
are active search structure available to PYTHIA. They are not parallel
pool-writing miners and neither is the final search-algorithm identity:
Hendrix remains the default traversal over the complete composed itinerary.

Each logical search vertex may be backed by multiple physical Chronus workers. Fleet growth happens below the fixed mathematical topology. The aggregate engineering target is the **governed 1e19 H/s hashrate ceiling**, but it remains a target until measured. Mathematical topology, tensor compression, search-order intelligence or configured fleet size never substitutes for measured hashrate.

## Salamander production closed loop

Salamander is not a log label and not another mining planner. `salamander/runtime.py` provides the production autonomy bridge. `chronus/mla1517_platform/python/mining_runtime.py` feeds canonical mining evidence into `MiningAutonomyBridge` and publishes `salamander_autonomy` beside mining evidence.

Its production loop is:

```text
measured mining evidence
  -> classify degradation/failure/optimisation opportunity
  -> bounded authorisation
  -> RecoveryGovernor and/or ClosedLoopOptimizer
  -> real actuator
  -> measured post-action result
  -> retain improvement OR reject/rollback
  -> append hash-chained evidence
  -> restore prior chain/state on restart
  -> continue monitoring
```

Device-error recovery re-enters the same Chronus H4/600 promotion seam, so a successful restart cannot silently demote the process to an older execution topology. Salamander owns healing/optimisation; it does not own search strategy, Stratum identity or share validity.

## Truth boundaries

Immutable boundaries remain exact Bitcoin SHA256d, negotiated target comparison, Stratum job/session/generation identity, stale-work and epoch cancellation, independent local candidate recheck, Stratum authentication/submission semantics, literal pool acknowledgement/outcome, AL HARAS/network controls, and truthful evidence provenance.

They answer whether work is valid and authorised. They do not answer how PYTHIA should search.

## Production SearchPlan contract

Every precomputed production-agentic plan and every fallback lease passes through PYTHIA before execution. A queue miss is not permission to bypass intelligence.

The final SearchPlan retains upstream agentic provenance, PYTHIA intelligence
evidence, memory recall, supposition, Turing/Quantum-GPU/Kellogg/Chronus
capability context, the supporting structural itinerary and H4/600 evidence.
Its plan-bound default nonce order is Hendrix. The full leased nonce interval
remains covered without gaps or overlap.

## Learning loop

Completed execution records are recorded by the canonical mining coordinator first. Only then is the measured result fed back to PYTHIA's memory/store. Accepted/rejected states come only from literal pool outcomes; missing pool response is not converted into acceptance or rejection. The same measured snapshot then enters Salamander's closed loop.

## Merge gate

`.github/workflows/pythia-authority-gate.yml` runs:

1. static architecture non-regression for intelligence/agentic/Supposition lineage, Turing/Quantum-GPU/Kellogg reachability, Salamander, Chronus-1, raw-block custody and H4/600;
2. `test_pythia_authority.py`;
3. `test_bitcoin_full_corpus.py`;
4. `test_bitcoin_vqc_training.py`;
5. Salamander closed-loop and production-supervisor tests;
6. existing Stratum/SHA256d proof-boundary regression.

A PR that removes or bypasses these boundaries is not merge-ready. A passing software gate is not evidence of live-pool acceptance, physical GPU/fleet execution or the governed 1e19 H/s hashrate ceiling target; those require fresh runtime evidence.
