# Governed learning lifecycle integration

Main repository: **PhiEnterprise1/EuclidPhiEnterprise**.
Inspected base: `6688e83c22d36dc16dfd5516e9e7d81959c84438` (`main`).
Delivery is a review branch; no merge, release, or deployment is implied.

## One system, existing engines

`EuclidRuntime` → `LearningService` → the existing `ExperienceSuperlearner`,
`EuclidLearningSystem`, PYTHIA learning/memory/store, and scoped SQLite memory.
No third policy learner is created. The runtime's training factory uses the
same object that the service mutates, evaluates, and checkpoints.

| Surface | Integration in this patch |
| --- | --- |
| Governed seeds / seven memory forms / event chain / claims | Existing ledger is attached to the runtime and the experience learner. Seeds remain seeds. Procedural learner events are not duplicated. Other memory forms remain explicitly selected through the ledger API. |
| Experience policy / transition model / Dyna / novelty / transfer | Existing implementation retained. Task actions restore as tuples; RNG state persists; rewards obey task ranges. |
| PYTHIA feature learning | Only an explicit finite `observation.learning_pattern` vector matching `pythia.n` is ingested. No content hash is misrepresented as a semantic feature vector. |
| Mining fate evidence | Only explicit boolean `outcome.mining_success` on measured-environment mining experiences enters success/failure statistics. Synthetic or enterprise observations are **neither** successes **nor** failures. |
| Episodic persistence | Exact outcome, observation, provenance, replay identity, and reward authority enter PYTHIA episodic memory and SQLite. The legacy numeric episodic API uses 0 for an unknown reward but retains null reward and NONE authority in exact content. |
| Claims / curriculum | Both experience and claim curricula are reachable. External comparison/review requires approval and an evidence reference; prerequisite stages cannot be skipped; contradictions keep claims refuted. This low-level API records operator approval, it does not authenticate a remote reviewer. |
| Consolidation | `runtime.consolidate_learning()` reaches governed consolidation, PYTHIA consolidation, and store persistence. An operator can inject an existing governed ledger with a `MemoryVault` for mirrored preservation; distributed custody is not automatically configured. |
| Training / validation / final test | Existing partition checks and named controls retained. Evaluation is non-exploratory and read-only. Single-step training cases are terminal. Each run has a distinct replay namespace; injectable `run_id` allows explicit retries to be rejected. |
| Persistence / restart | Sealed, verified atomic PYTHIA snapshots retain fate statistics. Corruption fails closed, including custom stores. Older unsealed snapshots are labelled legacy; old missing fate statistics do not carry unsupported germ-line truth forward. |
| Crash handling | A durable pending intent precedes mutation. A partial operation remains pending and blocks retry until operator reconciliation. This is **not** a distributed transaction or a proof of exactly-once completion. One writer per state directory is required. |

## Runtime API

```python
runtime = EuclidRuntime.production(creator_id=owner, state_dir=state_dir)
pipeline = runtime.training_pipeline(mission_id=mission, provenance=source_ref)
# pipeline.run(...): use explicit train/validation/final-test partitions,
# measured task rewards, revision, report path, and manifest path.
curriculum = runtime.learning.curriculum(limit=10)
consolidation = runtime.consolidate_learning(replay_limit=64)
runtime.close()
```

The default production factory still composes the existing cognition and organism
planes; this patch does not replace them or change mining consensus authority.

## Executed verification

- Same new suite on the inspected baseline: 23 tests; **3 passed, 11 failed,
  9 errored**. Failures/errors identify missing lifecycle methods/wiring and
  evidence/continuity defects; not all are numerical policy failures.
- Patched lifecycle suite: **23/23 passed**, including a fresh subprocess restart.
- Existing `test_euclid_training_readiness` subset: **14/14 passed** (partition,
  contract, replay, real learner/checkpoint and manifest tests).
- Changed/retrieved Python source compilation: passed.
- GitHub MCP secret scan was attempted but unavailable: Advanced Security is not enabled.
- Full output and hashes: `docs/euclid_learning_lifecycle_validation.json` and
  `docs/euclid_learning_lifecycle_test_output.txt`.

Reproduce on a full supported checkout:

```bash
python scripts/verify_euclid_learning_lifecycle.py
python -m unittest discover -s tests -p test_euclid_training_readiness.py -v
```

### Verification scope / remaining gates

The local run used a scoped MCP-retrieved checkout of actual main-branch module
contents, Python 3.13 and NumPy. `euclid/__init__.py` was exercised. The unrelated
`Intelligence`, `kellogg`, `hyba_substrate`, and cognition package initializers
were not included. The production-composition test isolates `_compose_cognition`
and uses `organism=False`; learning objects and persistence are real. The
normal runtime-constructor and fresh-process persistence tests are not mocked.
The optional `turing_core` backend was absent, so PYTHIA's existing fallback
fold/Zeckendorf paths ran; this is not quantum-library backend qualification.

Before claiming whole-system completion:

- Run full-repository CI, conftests, formatting/import/security gates with normal
  package initializers and supported dependencies.
- Run default unmodified `production()` startup with cognition and all required
  organs; close the feedback path for each actual domain adapter.
- Run the excluded mining-adapter handoff test and live/device assurance gates
  where applicable; no pool/hashrate/profitability claim follows from these tests.
- Measure long-horizon retention, held-out transfer and independent external
  baselines. Matching bounded state families across partitions is not evidence
  of generalization to unseen domains.
- Qualify signed evidence/reviewer custody and distributed transactional recovery;
  hashes are integrity checks, not signature/authentication proofs.
- Reconcile/review concurrent stacked PRs before merging. Main is not modified
  merely by publishing this branch.

Historical archive success counts remain historical evidence, not inherited
certification of this enterprise repository.
