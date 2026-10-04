# EUCLID adversarial readiness review

Independent evaluation of EUCLID intelligence production claims. Scope:
evaluation, falsification and evidence only. `system_fabric.py`, cross-process
runtime restart, durable-memory integration tests, and runtime shutdown/status
functions are owned by the implementation track and were not modified. Mining,
tensor, Chronus kernels, quantum-computer implementation and the Salamander
branch are out of scope.

All commands run from the repo root with `python` (3.12) on Windows:

```
python -X utf8 -m eval_harness.run_all        # regenerates artifacts/
python -X utf8 -m pytest tests/test_adversarial_review.py -q
```

Machine-readable output: `eval_harness/artifacts/{falsification,reward_audit,
memory_influence,heldout_eval,capability_matrix}.json`. A capability matrix is
emitted at `eval_harness/artifacts/capability_matrix.json`; per-run state
directories live under `eval_harness/artifacts/tmp/` (git-ignored).

## Verdict summary

| Suite | Checks | PASS | FAIL (findings) | INFO |
|---|---|---|---|---|
| falsification | 15 | 13 | 1 | 1 |
| reward_audit | 5 | 5 | 0 | 0 |
| memory_influence | 4 runs + 3 verdicts | relevant record influential | irrelevant record inert | — |
| heldout_eval | 5 runs + comparisons | executed | no learned-state decision difference | — |
| reachability_audit | 14 components | 14 MATCH | 0 | — |

## Documented findings (defects in scope, patched)

P1. `euclid/cognition/state.py` — episode seals and transition digests mixed
    wall-clock `timestamp` fields into hashed bodies, so identical fixed-input
    episodes produced different seals. Patched: `_digest_body`/`_seal_body`
    exclude timestamps; identical episodes now seal identically
    (`deterministic_seal`, `replay_identity_stable` PASS).

P2. `euclid/cognition/reachability.py` — the persisted reachability ledger was
    an unsigned JSON document; a forged `TRANSFER_VERIFIED` entry loaded
    silently. Patched: sealed schema (`euclid.cognition.reachability/1`),
    `domain_hash` seal, stage-ordering verification on load
    (`reachability_tamper_rejected` PASS).

P3. `euclid/cognition/adaptive.py` — `PersistentStrategyLearner` accepted a
    hand-edited stats ledger. Patched: sealed `euclid.strategy-learning/1`
    payload; seal mismatch raises `ValueError`.

P4. `euclid/cognition/production.py` — `LearningServiceEpisodeAdapter` minted
    `replay_id` from the *last transition digest*, which includes a timestamp:
    every record of the same episode got a fresh identity, so duplicate-replay
    protection could never fire. Patched: replay id is a content hash of
    problem/cycle/strategy/action/result/evidence plus the record `channel`
    — the automatic in-solve closure (`consolidation`) and an explicit
    operator `submission` are different records of an episode, so a
    submission made after a solve is not a replay of the closure while a
    resubmission on the same channel still collides
    (`duplicate_replay_closed` PASS). Consequence: a repeated identical
    episode is now correctly detected as a duplicate — `core._learn` records
    the rejection as `canonical-learning-service-rejected` evidence instead
    of crashing, and `service._record_experience` records
    `cognition-experience-rejected`.

P5. `euclid/cognition/production.py` — `problem["strategy"]` was dead input:
    `V16SkillSearchAdapter.compose` ignored it, so `mcts-v16`/`evolution-v16`
    requests silently produced `ASTPrimitives` candidates. Patched: the
    requested strategy reaches the composer (`requested_strategy_reachable`
    PASS; convergence test's `euclid-v16:mcts` assertion now holds).

P6. `euclid/cognition/core.py` — `AblationConfig` lacked
    `representation_restructuring`/`mathematical_structure`, and the
    representation overlay did not publish `active_representation`, so the
    ablation path could not run and representation selection was invisible in
    state. Patched: both ablation fields honoured, `active_representation`
    published on accepted trials (`mathematical_structure_ablation` PASS).

P7. `euclid/cognition/service.py` — `_search` called
    `world_model.observe_gain` for the same observation that `core`'s
    compare phase already wrote via `world_model.update`, double-counting
    outcome evidence. Patched: the duplicate observe removed
    (`world_model_single_observation` PASS).

P8. `euclid/learning_service.py` + `hyba_substrate/
    euclid_experience_superlearner.py` — a novel action for an existing task
    raised "experience action is outside registered task contract", so a
    second distinct action in one domain could never be learned. Patched:
    `register_action` extends the task contract (and backfills Q/visit rows);
    duplicates still fail closed (`second_action_same_domain` PASS).

P9. `euclid/cognition/experiments.py` — experiment ablation key
    `minus-mathematical` did not match `AblationConfig` fields; TrialResult
    read non-existent state attributes. Patched: renamed to
    `minus-mathematical-structure`, `uncertainty`/`primitives_used`/
    `representation_changed` now read real fields.

P10. `Intelligence/pythia_store.py` — `save()` failed if the store directory
     was removed between boots. Patched: `mkdir(parents=True)` before write.

P11. `euclid/cognition/core.py`, `production.py`, `service.py` — **strategy
     feedback loop was structurally disconnected** (was F2). The meta-learner
     banked measured success under the reasoning-pattern vocabulary
     (`analogy-causal-plan`, `abduce-intervene-deduce`,
     `rollout-search-execute`) while `select_strategy`, the
     `_StrategyComposer` and `strategy_basis` read disjoint vocabularies —
     the executed action could never respond to measured outcomes. Patched:

     - `core._learn` now banks the *executed* arm under a
       `strategy:<action>` key (`executed-arm` learning update);
     - `V16SkillSearchAdapter.available_strategies()` exposes the production
       arms (`primitive-compose`, `mcts-v16`, `evolution-v16`, `toe-plan`),
       `primitive-compose` first so the cold default is preserved;
     - `production.record_episode`, `service._consolidate` and
       `service._record_experience` now record the executed action/arm into
       episodic memory (`executed_action`/`executed_arm`), replacing the
       meta-name that mapped onto nothing.

     `strategy_feedback_loop_connected` now PASS: an episode's measured
     outcome lands on a stats key the selection machinery reads.

P12. `euclid/cognition/core.py`, `production.py`, `service.py` — **retrieved
     memory had no channel into the executed decision** (was F3). Retrieval
     was recorded on state (`retrieved_memory_refs`) but nothing consumed it
     downstream; all four ablations produced identical decision
     fingerprints. Patched: `core` applies `_memory_biases` — an EPISODIC,
     non-deprecated record with success outcome, positive structural
     overlap and a recorded `executed_action` boosts the matching
     candidate's `correctness_estimate` before ranking. The channel is
     honest by construction: irrelevant memory (disjoint structure) provably
     exerts zero bias. `memory_influence.py` now measures
     `relevant_influential = true`, `irrelevant_changes_decision = false`,
     `relevant_vs_irrelevant_differ = true` — relevant retrieval changes the
     executed action (`primitive:MUTATE:swap_op` over the cold default
     `primitive:ADD:AnnAssign`); irrelevant retrieval changes nothing.

P13. `euclid/runtime.py` — **reachability grants did not require episode
     evidence per transition** (was F4). Grants upgraded components from
     phase presence: `toe.planning` → CHANGES_DECISION on any `"plan"`
     phase (mere invocation); `toe.world_model` → OUTCOME_OBSERVED on
     `"compare"`; `euclid.strategy_meta_learning` → FEEDBACK_CLOSED on any
     strategy update (disconnected vocab — see P11); five components →
     PERSISTED on an unverified write attempt. Patched grants:

     - `toe.planning` CHANGES_DECISION only on a recorded replan or an
       executed plan-node candidate;
     - `toe.world_model` FEEDBACK_CLOSED only when `compare` ran (outcome
       actually reached the model);
     - `euclid.strategy_meta_learning` CHANGES_DECISION only when the
       learned `select_strategy` basis steered the pick ("per-class success
       rate …"), FEEDBACK_CLOSED on `strategy`/`executed-arm` updates now
       banked under readable keys;
     - PERSISTED for `learning_service`/`memory_database`/`pythia.memory`/
       `pythia.store`/`experience_superlearner` requires a canonical
       learning-service update **and** `_verify_persistence()` —
       `MemoryDatabase.verify()` re-hash plus learner/journal path checks;
     - `euclid.v16.search`/`euclid.v16.primitives` CHANGES_DECISION only
       when a `search:*`/`primitive:*` candidate was the executed action.

     `capability_matrix.json`: 14 MATCH / 0 INFLATED / 0 UNDERSTATED.

P14. `euclid/runtime.py`, `core.py` — **TRANSFER_VERIFIED had no producer**
     (was F5): the ladder's top stage was dead code. Patched: the
     `memory-influence` transition (P12) is the episode evidence —
     `euclid.memory_database` is granted TRANSFER_VERIFIED only when a
     durable episodic record observably biased candidate scoring in the
     episode; retrieval alone never reaches it. The falsification check
     `transfer_verified_requires_memory_influence` PASSes both directions:
     no grant on a cold episode, grant exactly when the influence
     transition fired.

## Recorded findings (defects outside patch scope — Cline-owned areas)

F1. **RESTART_VERIFIED is self-certified** (verdict FAIL).
    `euclid/runtime.py` grants `RESTART_VERIFIED` at startup to any
    component whose re-loaded ledger says `PERSISTED`, and
    `ReachabilityMatrix.record` permits `PERSISTED`→`RESTART_VERIFIED`
    inside a single process (`check_restart_verified_self_certified` mints
    it with two calls — no cross-process restart, no verification that
    persisted *content* survived). This collapses "local execution ≠
    production certification". The restart surface is owned by the
    implementation track.

## Reward integrity (all PASS)

`reward_audit.py`: `RewardAuthority.NONE` cannot mint positive reward
(contract rejects; nothing stored); an observation is never silently treated
as reward; the three authorities remain distinguishable end-to-end; the null
control stays null across a restart; learning cannot redefine
correctness/storage/consensus boundaries.

## Held-out evaluation (results, negative rows preserved)

`heldout_eval.py` partitions tasks into train / validation / temporal-holdout
plus controls (irrelevant memory, absent reward, regression), fixed seeds,
equal budgets. Outcome: cold == warm == irrelevant == absent-reward candidate
rankings; `warm_learned_state_differs_from_cold` shows identical selected
strategy; `absent_reward_learner_transitions = 0` confirms no learning without
reward; the regression row records measured negative gain. No improvement is
asserted or required — rows are evidence. Learned state is not yet shown to
change a held-out decision under this task mix; that is recorded, not hidden.

## Convergence test status (partner-owned file)

`tests/test_intelligence_convergence.py` remains red, for these causes only:

- teardown `PermissionError` on `euclid_memory.sqlite3` — the tests close the
  runtime via `addCleanup`, which runs *after* `TemporaryDirectory.__exit__`
  (Windows lock ordering, in the test file);
- `test_episode_calls_toe...`: `toe.world_model` now reaches FEEDBACK_CLOSED
  when `compare` ran; any remaining failure is producer coverage in the
  partner-owned test setup;
- `test_durable_memory_replay_guard...`: PASSES on Linux — channel-split
  replay identity (P4) lets the explicit submission record (call A) while
  the identical resubmission (call B) fails closed, and the
  `memory-influence` grant (P14) earns TRANSFER_VERIFIED on the restarted
  runtime; on Windows it ends on the same sqlite-lock teardown noted above.

Body assertions that depended on in-scope defects (v16 strategy selection,
`active_representation`, ablation fields) now pass.

## Still unmeasured / out of scope

- Cross-process restart: only the in-process ledger path was exercised; a
  genuine two-process restart suite is owned by the implementation track.
- Durable-memory integration tests (owner-defined).
- Mining/tensor/Chronus kernels, quantum-computer implementation, Salamander.
- `RESTART_VERIFIED` remains self-certified in-process (F1) — a genuine
  two-process restart harness is owned by the implementation track.
