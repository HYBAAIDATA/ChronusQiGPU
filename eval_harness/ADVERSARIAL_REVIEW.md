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
| falsification | 15 | 12 | 2 | 1 |
| reward_audit | 5 | 5 | 0 | 0 |
| memory_influence | 4 runs + 3 verdicts | executed | all influence verdicts negative | — |
| heldout_eval | 5 runs + comparisons | executed | no learned-state decision difference | — |
| reachability_audit | 14 components | 8 MATCH | 4 INFLATED, 1 UNDERSTATED, 1 absent-claim | — |

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
    problem/cycle/strategy/action/result/evidence (`duplicate_replay_closed`
    PASS). Consequence: a repeated identical episode is now correctly
    detected as a duplicate — `core._learn` records the rejection as
    `canonical-learning-service-rejected` evidence instead of crashing, and
    `service._record_experience` records `cognition-experience-rejected`.

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

## Recorded findings (defects outside patch scope — Cline-owned areas)

F1. **RESTART_VERIFIED is self-certified** (verdict FAIL).
    `euclid/runtime.py:184-190` grants `RESTART_VERIFIED` at startup to any
    component whose re-loaded ledger says `PERSISTED`, and
    `ReachabilityMatrix.record` permits `PERSISTED`→`RESTART_VERIFIED` inside
    a single process (`eval_harness/falsification.py:
    check_restart_verified_self_certified` mints it with two calls — no
    cross-process restart, no verification that persisted *content* survived).
    This collapses "local execution ≠ production certification".

F2. **Strategy feedback loop is structurally disconnected** (verdict FAIL).
    `euclid/cognition/core.py:322-326` sets `state.selected_strategy` from the
    meta vocabulary `{"analogy-causal-plan","abduce-intervene-deduce",
    "rollout-search-execute"}`; `core.py:604` banks measured success under
    those names. `_StrategyComposer` (`euclid/cognition/service.py:76-86`) and
    `strategy_basis` (`service.py:410`) score executed candidates using
    `STRATEGIES = {"deep-mcts","evolutionary-search","greedy-surrogate"}`
    (`service.py:51`). The write key-space and read key-space are disjoint —
    measured outcome can never change which candidate executes
    (`check_strategy_feedback_loop_connected` FAIL). Separately,
    `service._record_experience` (`service.py:470`) records
    `action=selected_strategy` (a meta name) so experience records never map
    onto candidate actions either.

F3. **Retrieved memory has no channel into the executed decision**
    (negative result). `memory_influence.py` ablations A–D produce identical
    decision fingerprints: `executed_actions`, `candidate_ranking`,
    `selected_strategy`, `plan_nodes` and `outcome` are unchanged whether the
    relevant record is present, removed, replaced by irrelevant content, or
    memory is disabled entirely. `state.retrieved_memory_refs` is populated
    (retrieval runs and is recorded) but no consumer reads it before
    planning/ranking/execution — "retrieval ≠ transfer" collapses in the
    ledger: records are claimed at `RESTART_VERIFIED`/`PERSISTED` while no
    downstream decision can be influenced.

F4. **Reachability grants do not require episode evidence per transition.**
    `euclid/runtime.py:213-291` upgrades components from phase presence:
    `toe.planning` → CHANGES_DECISION whenever a `"plan"` phase exists (mere
    invocation); `toe.world_model` → OUTCOME_OBSERVED on `"compare"`;
    `euclid.strategy_meta_learning` → FEEDBACK_CLOSED on any `"strategy"`
    learning-update; five components → PERSISTED on any canonical-service
    update. Result (`capability_matrix.json`): INFLATED for
    `euclid.strategy_meta_learning` (FEEDBACK_CLOSED recorded vs
    USED_IN_EPISODE evidenced), `euclid.v16.search`, `toe.planning`,
    `pythia.memory`; UNDERSTATED for `euclid.v16.primitives` (EXECUTED
    evidenced vs CHANGES_DECISION recorded — the ladder conflates "touched"
    with "executed"); MATCH for the remaining eight rows.
    The grant loop belongs to the runtime/status surface owned by the
    implementation track.

F5. **TRANSFER_VERIFIED has no producer** (verified negative). No code path
    records it; the convergence test's `require(... TRANSFER_VERIFIED)` cannot
    pass. `transfer_verified_never_recorded` PASS documents the gap.

## Reward integrity (all PASS)

`reward_audit.py`: `RewardAuthority.NONE` cannot mint positive reward
(contract rejects; nothing stored); an observation is never silently treated
as reward; the three authorities remain distinguishable end-to-end; the null
control stays null across a restart; learning cannot redefine
correctness/storage/consensus boundaries.

## Held-out evaluation (negative results preserved)

`heldout_eval.py` partitions tasks into train / validation / temporal-holdout
plus controls (irrelevant memory, absent reward, regression), fixed seeds,
equal budgets. Outcome: cold == warm == irrelevant == absent-reward candidate
rankings; `warm_learned_state_differs_from_cold` shows identical selected
strategy; `absent_reward_learner_transitions = 0` confirms no learning without
reward; the regression row records measured negative gain. No improvement is
asserted or required — rows are evidence.

## Convergence test status (partner-owned file)

`tests/test_intelligence_convergence.py` remains red, for these causes only:

- teardown `PermissionError` on `euclid_memory.sqlite3` — the tests close the
  runtime via `addCleanup`, which runs *after* `TemporaryDirectory.__exit__`
  (Windows lock ordering, in the test file);
- `test_episode_calls_toe...`: `toe.world_model` reaches only
  OUTCOME_OBSERVED — the FEEDBACK_CLOSED grant has no producer (F4/F5 class);
- `test_durable_memory_replay_guard...`: its scenario asserts the *first*
  manual re-record succeeds — under content-derived replay identity (P4) that
  re-record is already a duplicate and correctly fails closed; the test
  encodes the old non-deterministic identity behaviour.

Body assertions that depended on in-scope defects (v16 strategy selection,
`active_representation`, ablation fields) now pass.

## Still unmeasured / out of scope

- Cross-process restart: only the in-process ledger path was exercised; a
  genuine two-process restart suite is owned by the implementation track.
- Durable-memory integration tests (owner-defined).
- Mining/tensor/Chronus kernels, quantum-computer implementation, Salamander.
- Reachability stages above PERSISTED lack episode-evidence producers —
  RESTART_VERIFIED and TRANSFER_VERIFIED currently cannot be earned honestly.
