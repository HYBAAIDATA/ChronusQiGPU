# Intelligence Elevation — architecture and capability map

Base: `main` @ `bf6972f` (post-#116 v16 consolidation).

## What existed before

* Governed runtime stack (`EuclidRuntime`, `RightsLedger`, `Delegator`,
  `KairosRuntime`, `LearningService`, `MemoryDatabase`, training pipeline).
* v16 engine merged into `euclid/`: phi metric, Lucas structural metrics,
  AST primitives, process sandbox, evolutionary search, root-level MCTS,
  AST-delta discovery, HMAC-signed primitive repository, surrogate model,
  CGP topology, 11D manifold, ROI telemetry.
* The two were **not connected**: nothing in `EuclidRuntime` reached the v16
  engine, and no cognition request could flow startup -> dispatch -> effect
  -> feedback -> learning -> persistence -> restart -> replay.

## What this change adds

| Piece | Status | Evidence |
| --- | --- | --- |
| `EuclidRuntime.enable_intelligence()` | new, wired | `test_startup_to_transfer_full_chain` |
| `euclid/cognition/` loop, state, interfaces, baselines | new | 16 core tests |
| Program-domain specialists (signature, world model, abducer, deducer, discriminator, composer) | new | wired into loop; world model persists sealed |
| `euclid/search/deep_mcts.py` | new | 6 tests; multi-depth, transposition, budgets, terminal tests |
| `CognitiveEpisode` sealed evidence | new | tamper-rejection + replay determinism tests |
| `euclid/capability_matrix.py` | new | executable stage ladder |
| `euclid/benchmarks/intelligence_elevation.py` | new | conditions A/B/C/D + E1/E2/E3 ablations |
| `runtime.py` restore re-attaches `MemoryDatabase` | strengthened | restart proof in e2e test |
| `pyproject.toml` registers all `euclid.*` subpackages | repaired | #116 merged subpackages without wheel registration |
| `euclid/capability_audit.yaml` | new | CANONICAL/ADAPT/SUPERSEDE/RESEARCH_ONLY classification |

## What was superseded (preserved, not deleted)

* `MCTSSearchEngine` (v16): root-only traversal confirmed by review
  (children never expanded; tree discarded per generation).  Retained for
  compatibility and as benchmark condition C.  Canonical tree search is now
  `DeepMCTSEngine`.
* `MultiAgentEntangledOrchestrator`'s PYTHIA "recommendation": hard-coded
  annotation-density rule; classified RESEARCH_ONLY so it cannot be mistaken
  for learned strategy selection.

## Measured benchmark (internal only; no superiority asserted)

Configuration: 4 tasks (2 train / 2 held-out), 3 seeds, 8-evaluation budget
per run, sandbox-gated multi-objective fitness (tests dominate; phi is a
diagnostic).  Full artifact: `artifacts/intelligence-elevation-evidence.json`
plus `euclid.benchmarks.intelligence_elevation.run_benchmark()`.

Headline v1 measurements (exact numbers in the PR body):

* D (elevated) matched B (v16 evolutionary) on both splits at equal budget.
* C (v16 root-MCTS) underperformed A (random) on held-out tasks.
* Transfer gain D vs E2 (cold repository) on held-out tasks: **0.0**.
* World-model ablation E1 and depth ablation E3 matched D.

### Known negative results / limitations (truthfully recorded)

1. The v1 task family **saturates**: every competent condition finds the same
   beneficial operators within budget, so memory/transfer/depth advantages
   cannot express.  Harder held-out families (program repair with real test
   suites, causal-structure tasks, planning under constraints) are required
   before any transfer or world-model advantage can be claimed.
2. Primitive promotion during benchmark training did not trigger
   (repository_primitives = 0); transfer claims therefore rest on episodic
   analogy + strategy statistics, both evidenced, but with zero measured
   effect so far.
3. TOE/PYTHIA organ adapters are reserved but not yet evidence-backed; the
   benchmark's "TOE-only route" condition is deferred rather than fabricated.
4. Deep MCTS wall-cost per evaluation is dominated by sandbox subprocess
   isolation; budgets are deliberately hard.

## Governance invariants maintained

No arbitrary model-generated code execution (sandbox + AST validator only),
no runtime source self-modification, no federation, no public-network control
plane, no change to mining/Stratum/SHA256d authority, creator-scoped rights
on every new organ.
