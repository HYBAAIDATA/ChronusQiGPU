# EUCLID training readiness — bounded batch

Status vocabulary used below: **PASS** (verified by an executable check in
this change), **FAIL** (executed and did not meet the contract),
**NOT_RUN** (no executable evidence yet), **INSUFFICIENT_EVIDENCE** (ran but
the result cannot support the claim).

## What this batch proves

| Gate | Status | Evidence |
|---|---|---|
| Whole-lineage train/validation/final-test partitioning | PASS | `tests/test_euclid_training_readiness.py::PartitionContractTests` — duplicate case ids, shared lineage/session/seed and identical declared records across partitions are rejected before any training step; `final_test` is evaluated once and never enters `passed` |
| Named controls replace `null` semantics | PASS | `current_policy_baseline`, `fixed_action`, `uninformed` recorded separately with the control seed (`TrainingEvidence.controls`); `null_mean` kept as an alias of `fixed_action_mean` for compatibility |
| Action/reward contract enforcement | PASS | `ContractValidationTests` — fewer than two unique actions, unregistered action selection, non-finite or out-of-`reward_range` rewards all raise before/at train time; the pipeline refuses to run when `LearningService.experience_learner is not pipeline.learner` |
| Durable replay rejection across restart | PASS | `DurableReplayTests` — a sealed `replay_journal.json` plus `MemoryDatabase.has_replay_id` reject a repeated `replay_id` after a fresh service/learner are constructed, before any learner mutation; conflicting content under a claimed id fails closed; a tampered journal fails closed |
| Real `ExperienceSuperlearner` train → checkpoint → restore | PASS | `test_experience_superlearner_train_checkpoint_restore` — the actual `hyba_substrate.euclid_experience_superlearner.ExperienceSuperlearner` is trained on a mining-shaped HOLD/REDUCE/RESTORE task (oracle reward over banded transport state, `reward_range (-1,1)`), reaches `trained_mean=1.000` vs baseline `-0.167`, fixed `-0.167`, uninformed `-0.333`; a fresh object loaded only from the checkpoint retains task registry, q-values and world-model and reproduces identical deterministic decisions |
| Sealed checkpoint manifest | PASS | `euclid/checkpoint_manifest.py` — schema `euclid.checkpoint-manifest/1` binds source revision (injectable), task/action/state schema, learner checkpoint path+sha256, dataset partition fingerprints, dedup/watermark state and the evidence report hash; `load_manifest`/`verify_manifest` fail closed on seal drift, schema drift or artefact hash drift; secret-looking fields are rejected |
| Mining-adapter checkpoint handoff | PASS | `load_policy_checkpoint` + `EuclidMiningSupport(manifest_path=...)` — the adapter consumes only the manifest-verified checkpoint, exposes `policy_identity` in advice evidence and `snapshot()` (`single_actuator`: bounded `dispatch_breadth` only); a corrupted manifest leaves the adapter `UNAVAILABLE` and neutral |
| Executable train/evaluate/verify command | PASS | `python scripts/production_preflight.py --profile training --epochs N --cases N --seed N` — runs the full chain (imports → pipeline → controls → manifest → restore → handoff → replay) and exits non-zero on any FAIL |
| Deterministic tests retained | PASS | `tests/test_euclid_training_genetic_healing.py` (TinyLearner) untouched and green; new deterministic suite `tests/test_euclid_training_readiness.py` (15 tests) green |

## Evidence boundaries — what this does NOT prove

| Capability | Status | Note |
|---|---|---|
| Live-pool training/readiness | NOT_RUN | No pool connection, submission or acknowledgement exists in this path |
| Hardware/device readiness | NOT_RUN | `dispatch_breadth` advisory only; no hardware measurement |
| Profitability / performance gains | NOT_RUN | Bounded oracle reward, not production reward |
| Production readiness | NOT_RUN | Preflight `application`/`device`/`live` gates unchanged and separately owned |
| External/general validation | INSUFFICIENT_EVIDENCE | `boundaries.external_validation=False` in the report — one bounded task only |
| General intelligence | INSUFFICIENT_EVIDENCE | `boundaries.general_intelligence_proven=False` |

## Notes

- `EuclidRuntime` now wires `replay_journal_path = state_dir / "replay_journal.json"`, so replay protection survives restarts for every service the runtime builds. Services built without a journal path keep the prior process-only `_seen` behaviour plus `MemoryDatabase.has_replay_id` when a database is attached.
- `hyba_substrate/memory_preservation.py::_fsync_directory` was made Windows-safe (directory descriptors cannot be opened/fsynced there; the file-level fsync + atomic rename is the durability guarantee). Without this, `verified_atomic_json_write` — and therefore every learner checkpoint, journal and manifest write — raises `PermissionError` on Windows.
- `euclid/evidence.py::atomic_write` has a separate pre-existing Windows failure (`os.fchmod`) fixed by open PR #83, not by this change; no new code path depends on it.
- Partition rule of thumb: share the *state space*, never the *lineage*. `euclid/mining_training_task.py` demonstrates it — canonical banded states recur across partitions while every case owns a distinct `lineage_id`/`session_id`/`seed`.

## Reproduce

```bash
python -m unittest -v tests.test_euclid_training_genetic_healing
python -m unittest -v tests.test_euclid_training_readiness
python -X utf8 scripts/production_preflight.py --profile training --epochs 3 --cases 12 --seed 7
```
