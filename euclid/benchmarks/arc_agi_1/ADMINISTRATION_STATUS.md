# ARC-AGI-1 administration correction

## Disposition

Outcome B: exact execution-access blocker established. No canonical-runtime ARC experiment has run. No EUCLID intelligence score, capability limit or emergence verdict is established by the withdrawn helper experiment.

## Invalid experiment removal

Inspected commit `f4b48c884a4afaf8885a524e930e600d3d477d8c`: it added exactly eight files under `euclid/benchmarks/arc_agi_1/baseline/`. All eight were removed from active main. Removal started before the expanded directive requested a single commit. The available deletion tool operates one file per commit; cleanup therefore consists of eight dedicated commits, not a rewritten/squashed history:

1. `89107f6e43d46dc941cacf53f96e4ebb62c9d7b9` — training results.
2. `b8d5ea65e65179345fa84c080c23084f12cb6b83` — baseline report.
3. `df5e828514c65415568048f8b0be8de16b47ec82` — copied runner.
4. `13884fc02a53a804157170826ab15008ef6ad96a` — execution harness.
5. `a71b5778db0e5d3dbcb4dccaaaa7fb8c06a742dc` — regression tests.
6. `fb02642c22ba7e4be10ff0073053beb9332496aa` — test log.
7. `ed442a5d7970ba2da612337cb1dcb89d70729082` — reproducibility artifact.
8. `82aba774bf32ca2581a2ee9e0f5f956073d706bc` — dependency file; removal complete.

Review the net removal: https://github.com/PhiEnterprise1/EuclidPhiEnterprise/compare/f4b48c884a4afaf8885a524e930e600d3d477d8c...82aba774bf32ca2581a2ee9e0f5f956073d706bc

The original shared `benchmarks/external/arc_agi_runner.py` was preserved (Git blob `d46d5bf2a5938a797624b9b37bee5e0f89f95d2d`). No production source or unrelated tests were edited. Repository code searches for `arc_agi_1/baseline` and `run_training_baseline` returned no references; search indexing is not an exhaustive filesystem audit. The pinned dataset-root listing directly confirms baseline directory absence. No CI entries were added by the withdrawn eight-file commit. Dataset README now withdraws the helper experiment rather than advertise a result. Git history remains intact.

## Dataset preservation evidence

Upstream commit: `399030444e0ab0cc8b4e199870fb20b863846f34`.
At cleanup head `82aba774bf32ca2581a2ee9e0f5f956073d706bc`, remote EUCLID and pinned upstream Git trees match exactly:

| Split | Tasks | Git tree SHA |
| --- | ---: | --- |
| training | 400 | c00693818df744970c1cd3e201a559e30b070bbe |
| evaluation | 400 | 4a19f8327d45dda5e1809ee47be08bf1484b493b |

These recursive Git-tree identities establish identical filenames and blob content, not merely matching counts. The SHA-256 manifest was also rechecked against all 800 locally staged task files. Upstream licence, upstream README, checksum manifest and verifier remain intact. Evaluation files were checked for integrity only; no evaluation puzzle was run through a solver.

## Runtime source trace (not execution evidence)

Runtime source blob: `31e561c29dfe044951c20866a12d252373df5cf8`, inspected from commit `f4b48c884a4afaf8885a524e930e600d3d477d8c`. Subsequent cleanup changes only the eight invalid artifacts.

1. `euclid/runtime.py::EuclidRuntime.production` constructs the shared MemoryDatabase, PYTHIA memory/learner/store, ExperienceSuperlearner and LearningService; calls `_compose_cognition`; by default composes specialist organs and the governed recovery plane.
2. `_compose_cognition` wires the repository-oriented GeneralIntelligenceCore to TOE adapters, durable memory, strategy learning, v16 search/primitives and a repository executor. This is distinct from presenting an ARC task.
3. `compose_adaptive_intelligence` constructs `euclid.cognition.integrated.agent.IntegratedAgent` with AgentKnowledge, config, ablations and the runtime evidence chain. This composition must be invoked explicitly; production construction alone does not establish adaptive task participation.
4. `solve_task(spec, world_executor, seed=...)` registers a per-episode PROPOSE task-world organ; grants a creator-scoped dispatch right; calls `IntegratedAgent.solve` through a DelegatorExecutor; revokes the right in finally; verifies transition evidence; then attempts canonical knowledge custody and records observed reachability phases.
5. `IntegratedAgent.build_core` composes MechanismWorldModel, StructuralMemory, GraphAnalogyEngine, MechanismAbducer/Deducer, InformationGainDiscriminator, EvidenceMetaController, contextual strategy learning, CausalHierarchicalPlanner, ModelBasedComposer, EpisodeConsolidator and shared EpisodeContext around GeneralIntelligenceCore. AccountingExecutor wraps the governed executor.
6. `AgentKnowledge` retains episodic/structural memory, skills, strategy outcomes, priors, calibration and policy parameters across episodes. Snapshot/freeze and sealed serialization exist in source. Runtime persistence/restoration uses its adaptive data port/canonical custody; without custody, knowledge remains process-local. No restart-retention claim was tested here.

This is a source-level call path only. None of these components is asserted to have instantiated or participated in an ARC episode in this session. The old `euclid/run_euclid.py` is explicitly a local demonstration runner; it was not used as a substitute.

## Exact blockers

### B1 — no authenticated executable checkout or installed runtime

The GitHub MCP connection can read and mutate repository files. It does not supply shell Git credentials or execute repository Python. The shell probe actually attempted was:

```sh
GIT_TERMINAL_PROMPT=0 git ls-remote https://github.com/PhiEnterprise1/EuclidPhiEnterprise.git HEAD
```

It exited 128 with `fatal: could not read Username for 'https://github.com': terminal prompts disabled`. A separate Python availability probe returned `euclid_installed=False`; the two proposed local EUCLID checkout paths do not exist. This is an access/availability preflight failure, not a failed EUCLID startup and not an intelligence result. No attempt was made to copy a handful of modules, mock missing imports or label a partial source reconstruction as the complete instantiated system.

### B2 — native ARC task contract not yet established

The traced native adaptive input is `worlds/world.py::TaskSpec`: named finite-domain variables/operators, an initial state, known assignment goal or response maximisation objective, and interaction budgets. The traced output consists of operator programmes and trajectories. It does not directly specify ARC demonstration pairs plus test inputs with hidden target grids. No native ARC adapter was established by the inspected source or code searches; this is not an exhaustive proof of absence elsewhere in the repository.

Copying expected ARC test cells into `TaskSpec.goal` would leak answers and is prohibited. Hand-solving transformations in the evaluator or supplying a parallel ARC solver would repeat the invalid administration. A legitimate grid-task integration needs to preserve the canonical intelligence path, expose demonstrations/test inputs without target answers, and collect the runtime's own candidate grids/programmes. It must be verified in the authenticated runnable checkout before any task score is interpreted.

## Execution status

- Canonical EUCLID startup: NOT EXECUTED.
- Canonical-runtime ARC training tasks attempted: 0.
- Exact solves, invalid outputs, runtime errors and timeouts: NOT MEASURED (not zero-score results).
- Fresh/experienced instance: not instantiated.
- Adaptation, retention, transfer, ablation: not executed.
- New runtime/adapter/evaluator tests: none; no untested implementation is claimed as working.
- Public evaluation: unrun; no evaluation answers were embedded in runtime artifacts.

## Minimal next executable action

Provide an authenticated complete checkout/source archive (with required submodules/assets), or execution access to an isolated approved EUCLID research instance. Do not change security policy or expose credentials in chat. At that boundary, verify the source revision and startup procedure, instantiate the production composition plus integrated adaptive path with isolated recoverable state, then establish the grid-task contract and an independently tested no-answer-leak adapter. Freeze budgets, order, attempts, feedback and persistence conditions before presenting training tasks. Require live transition/dispatch provenance for the first task before proceeding to a full training run.
