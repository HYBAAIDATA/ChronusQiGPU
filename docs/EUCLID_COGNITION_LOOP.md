# EUCLID COGNITION LOOP

Composition root: `euclid.cognition.CognitionRuntime`, constructed by
`euclid.runtime.EuclidRuntime`, which is itself the production composition
root reachable via `EuclidRuntime.production()`.

This document records what was found **in code**, what was wired, and what
remains genuinely open. Claims here require execution evidence, not the
existence of a class.

---

## 1. What the audit found (from code, not documentation)

The architecture was reconstructed by imports, composition roots, object
construction and runtime call paths.

| Area | Finding |
| --- | --- |
| `euclid/` package | `EuclidRuntime` was a **governance and persistence shell**: evidence chain, rights ledger, organ registry, delegator, scoped SQLite memory, replay journal. It had **no world model, no planner, no causal reasoning, no strategy selection, no execution loop**. |
| `EuclidRuntime` reachability | Constructed **only inside its own package and its own tests**. No production entry point built it. |
| `euclid/adapter.py` | `EuclidEngineAdapter` — MCTS + evolutionary AST search with a phi-resonance objective. A genuine, well-tested **program-search** capability, but a **name collision** with the cognition authority, not a cognition loop. |
| `toe/` package | A **complete, well-tested** cognitive substrate: `world_model` (fitted dynamics, revision log, CUSUM drift), `causal_ladder` (SCM, do-operator, backdoor/frontdoor), `causal_stack` (identifiability oracle, structure discovery, counterfactual worlds, moment propagation), `planning` (bounded hierarchical forward search), `policy` (constraints + Pareto), `memory` (causal-tag retrieval, consolidation, regime invalidation), `meta_reasoning` (VOI, cheapest-adequate-path), `generalization` (`DomainAdapter`, capability matrix, transfer probe), `representation` (structural signature). |
| `toe/` reachability | **`toe.planning`, `toe.world_model`, `toe.memory`, `toe.meta_reasoning`, `toe.generalization` were imported only by `scripts/probe_*.py` and `tests/`.** No production code path reached them. |
| `Intelligence/intelligence_integration.py` | `IntegratedIntelligence.run_cycle` is the closest thing to an integrated loop (TOE → meta-evolution → memory → curriculum → Brier self-model). Reachable **only from scripts and tests** — never from production. |
| `Intelligence/orchestrator.py` | `IntelligenceOrchestrator` wires ~20 subsystems and produces mining nonce schedules. Real, but mining-specific; PYTHIA's orchestrator, not EUCLID's cognition authority. |
| `chronus/mla1517/mining/` | The genuinely live production intelligence: `intelligence_controller` (deterministic telemetry thresholds), `euclid_support` (`ExperienceSuperlearner` over HOLD/REDUCE/RESTORE on dispatch breadth, with measured pool-outcome reward — **a real, live learning loop**), `closed_loop` (`ClosedLoopOptimizer` trial/accept/rollback with measured persistence), `intelligence_memory` (Aethel-chained checkpoints). |
| `chronus/.../euclid_core.py` | Named `EuclidCoreBandit` but is a **deterministic measured policy** with no exploration. Honestly documented as such; a bandit in name only. |

**Net finding: the repository contained a sophisticated, fully-tested cognitive
substrate (`toe/`) that no production path could reach, and a production mining
intelligence that could not reason, plan or transfer.** The gap was
architectural wiring, not missing mathematics.

---

## 2. What was implemented

`euclid/cognition.py` composes the existing TOE substrate under **one
world-model contract** and makes every stage of the governing loop executable.

```
PERCEIVE      structural_signature(state)         -> outcome.perception
REMEMBER      MemoryStore.recall(causal_tags=)   -> outcome.recalled_count
              StructuralMemory.retrieve(tokens)   -> outcome.analogy
MODEL         DomainModel (WorldModel + OnlineAdapter)
              SCM derived from the SAME fitted weights
ABDUCT        _abduce()      -> competing hypotheses, each with a claim,
                               a predicted state, an identifiability verdict
DISCRIMINATE  _discriminate()-> score = weight*(expected - 0.25*sd) - cost
                               retained AND rejected are both reported
META-GATE     meta_reasoning.meta_decide()       -> may withhold planning
STRATEGY      StrategyPolicy.select(structure_key) -> outcome.strategy
PLAN          toe.planning.plan(env_evaluate = fitted world model)
EXECUTE       caller-supplied executor; its report is the ONLY source of truth
BIND          bind_outcome(decision_sha, predicted, observed)
LEARN         _absorb(): CUSUM step + ridge least-squares refit (exact)
              reward from measured prediction/outcome only
              policy.update() ONLY when a real outcome was observed
REPLAN        revised plan against the now-revised model, excluding what failed
MEMORY        one episode per cycle carrying tokens, strategy, error, reward
TRANSFER      structural (domain-stripped) keys drive retrieval AND strategy
```

### The world-model contract

`DomainModel` holds one `WorldModel` and derives its `StructuralCausalModel`
from *those same fitted weights*. A planner reasoning over a different structure
than the executor transitions in produces plans correct only in theory; here
they are literally the same numbers.

### Why ridge least squares, not `WorldModel.revise`

`WorldModel.revise` is a batch gradient step intended for occasional refits.
Calling it every cycle diverges — measured: weights reached `5.4e14` after eight
cycles with error exploding to `6.6e11`. Cognition therefore refits with
ridge-regularised ordinary least squares (`_ridge_solve`), which is stable,
deterministic and converges exactly. Measured after the fix: prediction error
falls from `8.0` to `0.0` within three cycles.

### The learning contract

`solve()` with no executor plans, records a `planned-not-executed` episode
(retrievable as context, never used as a strategy seed) and **refuses to update
the policy**. A reward is derived only from a real observed outcome. A reported
failure maps the reward into `[-1, 0]`, so no amount of objective improvement
can make a failed execution look successful.

### Reachability

`EuclidRuntime.__init__` always constructs `CognitionRuntime` and calls
`_restore_cognition()`. `startup_report()["cognition"]` exposes the loop's
honest state. `close()` persists it. `EuclidRuntime.restore()` rebinds cognition
onto the restored evidence chain.

Corrupt or foreign cognition state is **quarantined**
(`euclid_cognition_state.rejected.json`) and reported via
`cognition_status()["state_error"]` — never silently repaired, never trusted.

---

## 3. Behavioural evidence

`tests/test_euclid_cognition_loop.py` — 22 behavioural tests, each asserting a
decision / execution / feedback / state change rather than a helper's return
value.

| Test | Asserts |
| --- | --- |
| reasoning effect | winning hypothesis == plan's merged intervention, and it is the raising action |
| causal effect | a skeleton with no path to the objective yields objective value `0.0` |
| memory effect | the second cycle retrieves the first episode with non-zero structural similarity |
| persistence | tampered seal and foreign creator both raise |
| prediction error | `> 0.5` when unfitted, `< 1e-6` after learning, attributed per dimension |
| replanning | a failed execution produces a non-null revised plan |
| meta-learning | 6 measured updates change strategy selection and the score table |
| transfer | a lesson recorded against domain `alpha` changes behaviour in domain `beta` |
| capability composition | perception + hypotheses + plan + decision digest + model status all present |
| authority | no consensus term appears in any cognition artefact |
| replay | receipt chain verifies; persisted seal valid |
| restart | models, memory, policy and cycle counter survive a new runtime, which then keeps learning |
| composition root | `EuclidRuntime.production()` carries the loop; a fresh runtime over the same state dir resumes at cycle 1 and continues learning |
| quarantine | corrupt cognition state is rejected, `cycle == 0`, rejected file present |
| no-executor | no reward manufactured, policy observations unchanged |
| regime change | derived knowledge stales; history preserved verbatim |

---

## 4. Authority map

| Authority | Owns | Boundary |
| --- | --- | --- |
| **EUCLID** | the cognition loop, world models, memory, strategy policy, organ delegation | may not touch consensus: `bitcoin-header`, `nonce-semantics`, `sha256d`, `target`, `credentials`, `share-validation`, `submission`, `pool-acknowledgement` |
| **PYTHIA** | predictive/causal mining intelligence, schedules, orchestration | mining truth and evidence boundaries |
| **SALAMANDER** | self-healing, recovery, optimisation | operational repair; must not become EUCLID |
| **AL HARAS** | policy, entitlement, mediation, audit | governs dangerous action without crippling intelligence |
| **TURING** | quantum / virtual-quantum computational substrate | capability, never the intelligence authority |

---

## 5. Remaining genuine gaps

Honest, not aspirational.

1. **Linearity limit.** `DomainModel` fits linear dynamics only. Non-linear
   structure needs feature augmentation or a different model class.
2. **Single-step rewards.** Reward is derived per cycle. Long-horizon credit
   assignment across a plan is not implemented.
3. **Executor trust.** Cognition verifies *its own* prediction against the
   reported outcome; it cannot independently verify the outcome. A future seam
   should accept an evidence bundle rather than a bare state mapping.
4. **Analogy is a seed, not a proof.** A structurally similar episode seeds the
   search; the plan is still recomputed from the fitted world model. This is
   deliberate — transfer must not bypass the current model.
5. **No counterfactual plan evaluation.** Hypotheses are discriminated, but the
   revised plan is not itself scored against a counterfactual baseline.
6. **The mining loop is not yet a cognition problem.** `EuclidMiningSupport`
   remains a three-armed bandit. Porting it onto `CognitionProblem` (bounded
   dispatch breadth as an `Objective`, share outcomes as reward) is the next
   integration, deliberately not done here because it would change production
   mining behaviour and must be validated separately.
7. **`Intelligence/IntegratedIntelligence` remains off the production path.**
   It duplicates part of what cognition now does (cross-subsystem coupling and
   calibration). It should be reviewed for deprecation against this loop rather
   than left as a competing parallel system.
8. **`EuclidEngineAdapter` name collision.** It is program search, not
   cognition. Renaming it (e.g. `ProgramSearchEngine`) would remove the
   impression of two EUCLID authorities.

---

## 6. Production entry points and verified evidence

The loop is reachable through the control plane, not only from tests.

| Entry point | Role |
| --- | --- |
| `system_fabric.euclid_cognition_solve(...)` | runs one real episode and returns its trace |
| `system_fabric.euclid_cognition_status()` | honest availability, integrity and open gates |
| `system_fabric.euclid_cognition_close()` | idempotent, fail-soft shutdown |
| `POST /api/v1/intelligence/cognition/solve` | control-authenticated route to the above |

All three compose the canonical root (`EuclidRuntime.production()`) and honour
`PYTHIA_EUCLID_STATE_DIR`. No second learner, memory system or cognition
runtime exists.

### What is now proven, and by what

| Claim | Evidence |
| --- | --- |
| Reachability | A production call executes the real loop: `represent → retrieve → analogy → abduce → deduce → discriminate → strategy → plan → compose → imagine → rank → execute → compare → metacontrol → learn → terminate` |
| Strategy really executes | `mcts-v16` and `evolution-v16` are selected and produce `euclid-v16:mcts` / `euclid-v16:evolution` candidates. Previously the portfolio was a hardcoded tuple, so these routes were unreachable from the loop |
| Fail-closed | An unknown strategy returns `failure: strategy_unavailable` **before** execution; an empty request returns `invalid_request` |
| Persistence | Two separate interpreters: A (pid 54232) wrote 4 memories + 2 replay entries; B (pid 27084) read them back with `memory_valid=true`, identical `event_chain_head`, scope `restart-probe/euclid-cognition/repository` and `learning-service:<digest>` provenance |
| Tamper rejection | Altered replay journal → `replay journal seal mismatch`; altered memory payload → `memory content hash mismatch` |
| Decision effect | Cold run retrieves 0 records; warm run retrieves 8 and adopts 8 of them as structural mappings |
| Determinism | Two independent cold runtimes produce 126 byte-identical transitions and the same sealed digest |
| Absent reward | Every persisted record stays `RewardAuthority.NONE` with `reward=None`; a guard executor fails the test if cognition ever reports an unmeasured reward |

### Corrections made to make the above true

These were real defects, not documentation drift:

1. **Strategy selection was dead.** `core.solve()` used a hardcoded strategy
   tuple, so `V16SkillSearchAdapter` always fell through to `primitive-compose`.
   The composer is now the authority on its own portfolio.
2. **`TRANSFER_VERIFIED` was promoted from retrieval alone.** It now requires a
   retrieved record to have been *adopted* as a structural mapping — a decision
   effect. Retrieval that changes nothing records
   `transfer-not-established` instead.
3. **Episodes were not reproducible.** `Experience.digest()` hashed
   `created_at` (a wall clock), so the same episode hashed differently every
   replay and duplicate detection could not work. `created_at` is now excluded
   from the digest and stays on the record; `experience_id` is content-derived
   rather than a uuid.
4. **Shutdown could strand a handle.** `EuclidRuntime.close()` raised from
   `store.save()` *before* closing SQLite, and `restore()` replaced the database
   without closing the one `production()` opened. Both now release deterministically.
5. **One episode cost ~350 s.** The repository organ re-ran a full 1 810-file
   import audit (~44 s) once per cycle with no cache or bound. The audit is now
   reused inside a 60 s window and reports `cached`, so a repeated episode
   dropped from 32 s to 1.9 s.

### What is still open

These remain genuinely unproven and are reported as open gates in
`euclid_cognition_status()`:

- `held_out_generalisation_not_established` — the cold/warm comparison exists
  and reports `improved` / `no_change` / `regressed` honestly, but one task
  family is not a generalisation result.
- `restart_not_verified` on a long-lived deployment (per-test restarts pass).
- `external_validation_absent`, `production_certification_absent`.
- `DomainModel` fits linear dynamics only; long-horizon credit assignment
  across a plan is still unimplemented.

