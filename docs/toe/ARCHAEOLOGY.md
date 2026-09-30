# TOE archaeology — intelligence elevation pass, section 1

Base: `d298eaa` (post-production `main` HEAD; contains verified production
baseline `73a716d` — see `docs/production/validation.md`).

Method: static import-graph reachability over every `.py` file in the repo
(a module counts as reachable when at least one non-self file imports it),
plus module-by-module inspection. Dynamic dispatch (registry `probe_import`,
console scripts, subprocess boundaries) is a caveat noted per file where it
applies. Machine-readable form: `reports/toe_archaeology.json`.

Baseline re-verified on this base before any change:
`pytest tests/ -q` → 1728 passed, 1 failed, 16 skipped;
`unittest discover -s mla1517_platform_v3.4/python` → 317 ran, OK.

The one failure — `test_import_audit` IA02 on
`mla1517_platform_v3.4/python/autonomous_supervisor.py` — was a genuine defect
in `d298eaa` itself (`AutonomousCapabilitySupervisor` is not a name in
`Intelligence.autonomous_capabilities`; the real class is `AutonomySupervisor`;
the `try/except` swallowed it, silently disabling the supervisor's three
autonomies). Intelligence integration exposed it; it is fixed on this branch.

## What TOE is today

Two orchestration centres exist and are already correctly separated:

- **`toe/`** — the domain-general reasoning core. Canonical entry point is
  `TOEBridge` (`toe/bridge.py`): tomography → trajectory forecast → causal
  ladder → interventional-Shapley explanation → policy decision, with
  hash-chained receipts. Its supporting modules are `causal_ladder`
  (supplied-graph identification + do + counterfactual + effect estimation),
  `explanation`, `policy`, `agreement`, `receipts`, `operator_compilers`,
  `poincare_golden_11d`, `expansion`, `system`, `manifold_bridge`,
  `strict_quantum`, `solovay_kitaev`, `poincare_yangmills`, `phi_klein`,
  `geometric_contract`, and the monolithic `engine` (PredictiveEngine +
  Pisot-family substrate).
- **`Intelligence/`** — the mining-facing aggregation layer.
  `IntelligenceOrchestrator` wires every module into the mining adapter
  boundary (`MINING → observed state → TOE → result → adapter`). The
  domain-general law is already enforced: `toe/` contains zero mining
  vocabulary (asserted by the elevation benchmark).

The substrate under both is **`kellogg/`** (32-dim Hilbert tensor +
Clifford+T exact `Q(ζ8)` path + exact-tensor ML family), with **`lucas/`**
as the canonical Lucas kernel family (`lucas.pool` is the only legal shared
import) and **`aethel/`** as the storage/cost substrate.

## Classification summary

| Class | Files | Where |
|---|---:|---|
| ACTIVE_CANONICAL | 15 | toe core (engine, bridge, causal_ladder, explanation, policy, agreement, receipts, operator_compilers, poincare_golden_11d), kellogg core, lucas, Intelligence/{__init__, orchestrator, registry, self_test} |
| ACTIVE_SUPPORTING | ~120 | toe/{system, expansion, manifold_bridge, strict_quantum, poincare_yangmills, phi_klein, geometric_contract, solovay_kitaev}, toe/intelligences/* (mining five), toe/unified/*, aethel/, mtheory/, phi_rotation/, Intelligence/* mining-bound modules, al_haras/, pythagoras/, millennium probe suite, platform/conformance surfaces |
| SUPERSEDED | 2 | toe/hardened_unified_substrate.py (alias → aethel), toe/poincare_golden_11d parallel in millennium/ |
| DUPLICATE | 2 | Intelligence/nobel_fields_intelligence.py vs millennium/nobel_fields_intelligence.py; millennium/poincare_golden_11d.py vs toe/poincare_golden_11d.py |
| EXPERIMENTAL | ~70 | Intelligence/asi/* capability ports, Intelligence/consciousness/, meta_evolution, prime_memory, pvsnp_memory, omega/, l_hras/, agi/ (test-only reachability), experiments/ |
| DISCONNECTED | ~230 | pci/ (0 importers), integrations/ (0 importers), Intelligence/{endpoint_wrapper, intelligent_wrappers, mining_api_intelligence, agentic_mining_evals}.py, millennium/{poincare_cassini_search, mathematical_discovery, clay_checklist, millennium_reasoning_service, yang_mills_data, sl5_millennium_bridge}.py, asi/{api, macro_simulation}, 184 legacy files |
| HISTORICAL | legacy/ remainder | prior generations; salvage candidates listed below |
| UNREACHABLE | 1 | enhanced_intelligence/ (empty stub) |

## Trapped mathematics — stronger capability in disconnected code

| File | What is trapped | Where it belongs |
|---|---|---|
| `millennium/poincare_cassini_search.py` (467L) | 11D search topology as a traversal machine: `DodecaIcosahedron32`, anchors, weighted Poincaré distance, search results | topological/geometric reasoning; representation navigation (map boxes: topology, multi-future) |
| `millennium/mathematical_discovery.py` (3108L) | `MathematicalDiscoveryEngine` — hypothesis/frontier exploration machinery | meta-reasoning / action generation review |
| `asi/macro_simulation.py` (783L) | Second causal engine: `GlobalDataset`, `CausalVariable`, `GlobalIntervention`, `ForecastResult` | candidate comparison against `toe/causal_ladder` before any reuse |
| `agi/simulations.py` (1532L) | `NashEquilibriumSolver`, `MonteCarloSimulation`, `BayesianMCMC`, `MultiCriteriaDecisionAnalysis` | action evaluation / uncertainty machinery |
| `agi/reasoning.py` (564L) | `AutonomousReasoningEngine` + `MetaCognition` (hypothesis/goal/knowledge records) | meta-reasoning review |
| `Intelligence/asi/world_model.py` (130L) | Working ablation-based world-model learner (rung-2 attribution over own experiment history) — reachable only via `discovery_runtime` domain path | world-model / model-revision capability (§23-24) — elevate or port, don't duplicate |
| `Intelligence/asi/discovery_engine.py` (534L) | Bayesian experimental design = an existing expected-information-gain mechanism | value-of-information capability (§28) — generalise |
| `Intelligence/asi/metacognition.py` | Calibration monitor + strategy switching | meta-reasoning (§27) — generalise |
| `pci/`, `integrations/` | whole packages unreachable | no intelligence salvage identified at this depth; left disconnected |

Duplicates found (no merge needed for this pass; recorded): the two
`nobel_fields_intelligence.py` copies and the `millennium/poincare_golden_11d.py`
copy of the canonical toe module.

`legacy/` is HISTORICAL by class, but per the brief it is not dismissed:
`legacy/Intelligence/{discovery, exact_tensor_bridge, first_principles_quantum,
mathematical_discovery, phi_resonance, self_test_search}.py` are flagged for
targeted comparison when the corresponding elevation sections run (a capability
that is strictly stronger than the canonical module must be promoted, not
re-written).

## Prior evidence this pass builds on

`reports/toe_elevation_benchmark.json` (commit `f57d1a9`, 64/64 checks) already
establishes: 11D fold roundtrip, binary-Iris prediction, supplied-DAG
backdoor/frontdoor identification, do-intervention, counterfactual surgery,
interventional-Shapley explanation, action policy over counterfactual futures,
receipt replay/tamper detection, exact-vs-float agreement, domain cleanliness.

Its recorded boundaries are the starting gap list: causal discovery NOT
ESTABLISHED; estimation only for supplied DAGs; counterfactuals need the full
SCM; explanation explains the supplied model only; action selection needs
supplied candidates; prediction evidence is one binary task.
