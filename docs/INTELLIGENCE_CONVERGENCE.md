# EUCLID intelligence convergence

## Runtime authority

`EuclidRuntime.production()` is the composition root. It creates one evidence
chain, rights/delegation boundary, durable `MemoryDatabase`, replay journal,
PYTHIA memory/learning/store, `ExperienceSuperlearner`, TOE world model,
TOE planner/meta-controller, v16 search/primitive stack, repository engineer,
and cognition episode lifecycle.

The deterministic cognition specialists remain reference baselines. Production
uses `euclid.cognition.production` adapters. Specialist internals remain owned
by their packages.

## Reconciled capability inventory

| Repository capability | Classification | Production route |
|---|---|---|
| `euclid/cognition` loop/state/interfaces | CANONICAL | `GeneralIntelligenceCore` |
| `euclid/runtime.py` | CANONICAL | sole composition root |
| `toe/world_model.py` + online adaptation | ADAPT_INTO_COGNITION | `TOEWorldModelAdapter` |
| `toe/planning.py` | ADAPT_INTO_COGNITION | `TOECognitivePlanner` |
| `toe/meta_reasoning.py` | ADAPT_INTO_COGNITION | `TOEMetaController` |
| `euclid/search` MCTS/evolution | ADAPT_INTO_COGNITION | `V16SkillSearchAdapter` |
| v16 surrogate/topology/discovery/transfer repository | ADAPT_INTO_COGNITION | constructed by v16 engines |
| `euclid/core/primitives.py` | CANONICAL | candidate vocabulary |
| `euclid/learning_service.py` | CANONICAL | sole episode feedback facade |
| `euclid/memory_database.py` | CANONICAL | durable cognitive/episode state |
| PYTHIA memory/learning/store | SPECIALIST_ORGAN | shared instances in `LearningService` |
| `ExperienceSuperlearner` | SPECIALIST_ORGAN | reward-authority-gated feedback |
| `Intelligence/repo_engineer.py` | SPECIALIST_ORGAN | governed read-only execution/evidence |
| repository skills | SPECIALIST_ORGAN | discovered through repo engineer and v16 vocabulary |
| Turing | SPECIALIST_ORGAN | registered typed read-only organ; retains compute authority |
| Chronus | SPECIALIST_ORGAN | registered typed organ; retains backend capability authority |
| Salamander | SPECIALIST_ORGAN | registered typed organ; retains repair authority |
| Aethel / THESEUS custody | SPECIALIST_ORGAN | registered typed organ; retains durable custody authority |
| Aethel / OVID transforms | SPECIALIST_ORGAN | registered typed organ; retains transformation/lineage authority |
| AL HARAS | SPECIALIST_ORGAN | registered typed organ; retains security/evidence authority |
| `TableWorldModel` | REFERENCE_BASELINE_ONLY | tests/ablation only |
| `InMemoryMemorySystem` | REFERENCE_BASELINE_ONLY | tests/ablation only |
| `HierarchicalPlanner` | REFERENCE_BASELINE_ONLY | tests/ablation only |
| legacy/experimental intelligence copies | RESEARCH_ONLY or SUPERSEDED | never auto-registered |

Unique implementations are retained. Runtime authority is removed from
baselines by composition, not deletion.

## Evidence and non-claims

`ReachabilityMatrix` records:

`PRESENT → IMPORTABLE → ADAPTED → REGISTERED → REACHABLE →
USED_IN_EPISODE → CHANGES_DECISION → EXECUTED → OUTCOME_OBSERVED →
FEEDBACK_CLOSED → PERSISTED → RESTART_VERIFIED → TRANSFER_VERIFIED`

A component is not integrated below `FEEDBACK_CLOSED`. Restart and transfer
are recorded only after an actual later runtime/task observes them.

Imagined TOE/v16 output never becomes observed evidence. `LearningService`
applies reward only when an execution result explicitly carries an accepted
`RewardAuthority`; otherwise it stores an observed, reward-free episode.
Duplicate replay fails closed.

Mining consensus ownership is unchanged. Cognition has no API for block-header
truth, target, SHA256d, nonce validity, credentials, share validation,
submission, or pool acknowledgement.