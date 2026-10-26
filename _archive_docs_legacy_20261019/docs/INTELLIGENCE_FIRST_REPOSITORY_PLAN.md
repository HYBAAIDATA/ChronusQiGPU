# Intelligence-First Repository Elevation Plan

This is the recovered implementation plan from the Perplexity intelligence
review, reconciled against the current QuantumPhiRedux/PhiMiner repository.

## Governing position

EUCLID is the canonical intelligence/cognition orchestrator. PYTHIA retains
final mining authority. SALAMANDER owns bounded self-healing and
self-optimisation. AL HARAS owns security/governance. TURING is computational
capability. CHRONUS is heterogeneous execution. THESEUS owns durable custody.

## Completion matrix

| Item | Status | Implementation |
| --- | --- | --- |
| Promote intelligence to primary architectural concept | IMPLEMENTED | README intelligence-first composition + EuclidRuntime.production |
| README intelligence rewrite | IMPLEMENTED | README.md |
| Remove EUCLID program-search name collision | IMPLEMENTED | ProgramSearchEngine; EuclidEngineAdapter compatibility alias |
| Promote cognition status to first-class API | IMPLEMENTED | GET /api/v1/intelligence/cognition/status + nested status |
| Remove competing cognition authority | IMPLEMENTED | Intelligence/intelligence_integration.py marked compatibility-only |
| Mining as cognition problem | IMPLEMENTED | euclid/cognition/problem.py + mining.py + live euclid_support integration |
| UI intelligence truth alignment | IMPLEMENTED | IntelligenceView reads runtime cognition capabilities/open gates |
| Non-linear intelligence extension | IMPLEMENTED | zero-start quadratic/interaction features in TOEWorldModelAdapter |
| Long-horizon credit assignment | IMPLEMENTED | euclid/cognition/credit.py + PersistentStrategyLearner.update_credit |
| Counterfactual plan evaluation | IMPLEMENTED | GeneralIntelligenceCore scores plans/replans vs no-intervention |
| Held-out generalisation test/gate | IMPLEMENTED AS GATE | multi-family sealed evidence contract; claim remains unavailable until earned |
| L-HRAS default-on review | REVIEWED — KEEP CONFIG-GATED | current runtime requires AL_HARAS_LHRAS_CONFIG and fails closed when absent; forcing default-on would make unprovisioned production unavailable |
| Evidence-bundle seam | PRESENT | euclid/evidence_bundle.py; bare executor output is not relabelled independent proof |

## Restored Perplexity workstream

The authority-boundary and discovery/self-optimisation artifacts described by
the trial workstream have been restored:

- toe/intelligences/authority_boundary.py
- tests/test_euclid_pythia_authority_boundary.py
- salamander/discovery_optimisation.py
- tests/test_discovery_self_optimisation_bridge.py

Discovery follows:

TheoreticalSpaceExplorer -> DiscoveryOptimisationCandidate -> held-out
OptimizationTrial -> independent verification -> Salamander policy lifecycle.

Failed discoveries, training/incident partitions, mismatched metrics,
non-finite measurements and PYTHIA-final mining domains are refused before
promotion.

## Claim boundary

This completion does not create evidence for physical hardware, live-pool
acceptance, performance uplift, external validation or production
certification. Those remain unavailable until directly observed and retained.
