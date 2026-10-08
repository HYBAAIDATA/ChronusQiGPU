# TOE — recovered architecture

TOE is a domain-general mathematical intelligence engine. It was discovered inside PYTHIA,
expressed through an HR application (`toe.engine.PredictiveEngine`: employees, churn,
promotion, compensation). That surface is preserved as lineage; it is not the domain.

## The cycle (one backend, every problem form)

```
domain input ──► adapter (toe.adapters / PYTHIA / EUCLID) ──► toe.problem.Problem
                                                                   │
TOEIntelligenceRuntime.solve (tenant, receipts, evidence chain, consensus boundary)
                                                                   │
TOEMachine.run ─────────────────────────────────────────────────────┘
  represent      representation.choose → IntelligenceState.observe (7 lenses, one digest)
  understand     relationships.relationship_ladder · causal_stack.identifiability ·
                 causal_ladder.intervene / counterfactual_state · uncertainty_report
  forecast       exact recurrence via KELLOGG companion powers (else labelled trend)
  navigate       topology.StateTopology · geometry (hyperbolic tree, greedy routing)
  futures        causal_stack.evaluate_futures / futures_env (distributions, "predicted")
  decide         policy.decide (rung-3 counterfactual futures when a unit is observed)
  precision      precision.select_precision / exact Q(φ) counterfactual comparison
  plan           planning.compare_plan_vs_greedy over futures_env (chance constraints)
  arbitrate      arbitration.arbitrate (causal vs associational vs planning; never averaged)
  meta           meta_reasoning.value_of_information + meta_decide → ACT / ACQUIRE_EVIDENCE
  explain        decision_explanation (computational, contrastive, falsification)
  govern         self_governance.self_check · receipts chain
TOEMachine.learn
  bind           world_model.bind_outcome (to the exact decision SHA)
  assess         world_model.assess_structural (SUPPORTED / DRIFT / CONTRADICTED / INSUFFICIENT)
  revise         world_model.fit_structural_weights (OLS on post-intervention rows)
  contradiction  widen uncertainty · request evidence · replan (when a refit is impossible)
  memory         memory.MemoryStore (regime invalidation on revision)
  persist        custody.SnapshotStore → THESEUS (hash-chained producer="toe" records)
```

The machine never reads `problem.domain` for reasoning — it names the learning namespace
(negative-transfer guard) and the provenance. `trace` lists every backend callable a run
executed; `toe.voyage.cross_domain_voyage` measures reuse across eight problem classes.

## Authority

| System | Owns | TOE's relation |
|---|---|---|
| EUCLID | orchestration — when to ask | calls `TOECapabilityAdapter.invoke`; answers land on EUCLID's evidence chain |
| TOE | world/inference machinery above | this package |
| PYTHIA | mining authority; SHA256d + target | `chronus/mla1517/mining/toe_problem.py` translates; PYTHIA authorises |
| KELLOGG | tensor + exact fields (`QPhi`, `quantum_tensor`, `scales`, `substrate`) | hard dependency, consumed |
| TURING | VQC execution | optional request |
| THESEUS | durable custody | optional integration; absent → persistence UNAVAILABLE |
| OVID | representation transformation | not bundled |
| AL HARAS | security/governance | not bundled |
| SALAMANDER | healing/optimisation | not bundled |

## Standalone boundary

The wheel (`packaging/toe/build_and_verify.py`) ships `toe`, `toe.adapters`, `toe.unified`
plus `CAPABILITY_MANIFEST.json` and `CLAIM_REGISTER.json`. It excludes the monorepo-only
mining-facing coordinator (`toe/system.py`, `toe/intelligences/`, `toe/manifold_bridge.py`,
`toe/hardened_unified_substrate.py`, which aliases aethel).

Dependency audit (what changed to make `import toe` standalone):

| Former coupling | Resolution |
|---|---|
| `lucas.algebra.ZPhi` (exact Q(φ) in the causal ladder) | KELLOGG's `kellogg.substrate.QPhi` |
| `millennium.yang_mills_data.SpectralGeometry` / `TopologicalAnalytics` | promoted into `toe.geometry` / `toe.topology`; millennium re-exports |
| `turing_core.detect_family_signature` | `toe.engine.ExtendedAlgebraicFamily` (delegates to turing_core when present) |
| `lucas.ladder.SCALE_RUNGS`, `chronus.mla1517.scale` (expansion envelope) | optional; without them the scale program fails closed |
| `toe.system` (eager import in `toe/__init__`) | lazy; absent names are dropped from `__all__` in the wheel |
| pandas (legacy HR engine) | extra `legacy-hr`; `OptionalDependencyUnavailable` otherwise |

Hard dependencies: `numpy`, `kellogg-tensor`. Verified from clean installs on CPython 3.11,
3.12 and 3.13 with identical exact fixtures.

## Recovered from archaeology

| Candidate (`docs/toe/ARCHAEOLOGY.md`) | Decision |
|---|---|
| `millennium/yang_mills_data` spectral/topological classes | promoted into TOE (sole consumer); GF(2) rank rewritten exactly on bitsets |
| `millennium/poincare_cassini_search.py` | left historical: couples traversal to aethel storage healing (THESEUS's authority); its 32-direction frame is measured in the evidence pack |
| `Intelligence/asi/world_model.py`, `discovery_engine.py`, `metacognition.py` | not promoted: TOE's world-model revision, VOI and meta-control are now live in the cycle with stronger tests |
| `millennium/mathematical_discovery.py` | outside TOE authority (research frontier); remains experimental behind `millennium/discovery_runtime.py`, which rejects proof escalation |
| `agi/simulations.py` (MCMC, Nash, MCDA) | not promoted: no TOE stage consumes them yet; recorded as candidates |
