# Canonical TOE intelligence map — section 2

Base `d298eaa`. Statuses: IMPLEMENTED / PARTIAL / DISCONNECTED / UNMEASURED /
UNAVAILABLE. Each entry names the module that provides the capability and the
evidence for the status (test file, benchmark section, or honest gap).

```text
                         TOE
             ┌────────── STATE ──────────┐
             │ representation            │ IMPLEMENTED
             │ tensor state              │ IMPLEMENTED
             │ geometry                  │ PARTIAL
             │ topology                  │ PARTIAL
             └────────────────────────────┘
                          ↓
             ┌────── UNDERSTANDING ──────┐
             │ relationships             │ PARTIAL
             │ causal effects            │ IMPLEMENTED
             │ structural models         │ PARTIAL
             │ explanation               │ IMPLEMENTED
             │ uncertainty               │ PARTIAL
             └────────────────────────────┘
                          ↓
             ┌──────── FUTURES ──────────┐
             │ trajectories              │ PARTIAL
             │ interventions             │ IMPLEMENTED
             │ counterfactuals           │ IMPLEMENTED
             │ multi-future simulation   │ PARTIAL
             └────────────────────────────┘
                          ↓
             ┌───────── ACTION ──────────┐
             │ candidate generation      │ UNAVAILABLE
             │ constraints               │ IMPLEMENTED
             │ objectives                │ IMPLEMENTED
             │ policy                    │ IMPLEMENTED
             │ plan selection            │ PARTIAL
             └────────────────────────────┘
                          ↓
             ┌──────── LEARNING ─────────┐
             │ outcome attribution       │ PARTIAL
             │ calibration               │ PARTIAL
             │ memory                    │ PARTIAL
             │ model/world update        │ PARTIAL
             │ strategy adaptation       │ PARTIAL
             └────────────────────────────┘
```

## Per-box evidence

### STATE

| Box | Status | Provider | Evidence / gap |
|---|---|---|---|
| representation | IMPLEMENTED | `toe/operator_compilers.py` → `kellogg.quantum_tensor` / `kellogg.exact_tensor` | deterministic typed-operator compile → 32-dim Hilbert state + exact `Q(ζ8)` path; `toe_elevation_benchmark.json` state roundtrip 20/20 max_err 0.0 |
| tensor state | IMPLEMENTED | `kellogg/{quantum_tensor,exact_tensor,exact_field}` | Born rule, QFI, Clifford+T exact fractions; tests `test_a_*` |
| geometry | PARTIAL | `toe/poincare_golden_11d.py`, `toe/phi_klein.py`, `toe/geometric_contract.py`; `millennium/yang_mills_data.SpectralGeometry` now wired as the `geometric` lens | metrics + 12-check contract + lens exist; no operational geometric-reasoning tasks vs baselines (§32) |
| topology | PARTIAL | `counterfactual_intelligence.topological_intelligence` (mining-bound); `millennium/yang_mills_data.TopologicalAnalytics` (Vietoris-Rips Betti) now wired as the `topological` lens | real TDA reachable from TOE core; no ground-truth topological tasks (§33) |

### UNDERSTANDING

| Box | Status | Provider | Evidence / gap |
|---|---|---|---|
| relationships | PARTIAL | `causal_ladder.infer_causal_graph` (heuristic, labelled), `association_query` | supplied-graph relations only; no structural model abstraction |
| causal effects | IMPLEMENTED | `causal_ladder`: `identify_backdoor`, `identify_frontdoor`, `is_backdoor_admissible`, `estimate_causal_effect` | benchmark: adjusted effect within 4 SE of truth on synthetic SCMs; latent confounder correctly refused |
| structural models | PARTIAL | `StructuralCausalModel` (supplied only) | SCM exists as an object but must be supplied; no discovery (boundary recorded) |
| explanation | IMPLEMENTED | `toe/explanation.py` (interventional Shapley, exact ≤12 inputs) | benchmark: 10 faithfulness checks; contrastive (why-A-not-B) and a falsification metric are missing (§14-15) |
| uncertainty | PARTIAL | `CausalEffectEstimate` SEs + evidence classes | no aleatoric/model/structural/identifiability/missing-evidence taxonomy on outputs (§11); no calibration suite beyond causal coverage (§12) |

### FUTURES

| Box | Status | Provider | Evidence / gap |
|---|---|---|---|
| trajectories | PARTIAL | `TOEBridge.predict_trajectory` (unitary forecast on tomography) | point forecast; no uncertainty retention, no horizon-degradation measurement (§10) |
| interventions | IMPLEMENTED | `causal_ladder.do_operator`, `intervene` | benchmark: edge-cut verified, `E[Y|do(X=2)]` exact `ZPhi` |
| counterfactuals | IMPLEMENTED | `causal_ladder.counterfactual_state` | benchmark: factual reproduction + negative controls + fail-closed missing evidence; single intervention only — multi-world comparison is PARTIAL via `policy.counterfactual_futures` (§9) |
| multi-future simulation | PARTIAL | `policy.counterfactual_futures` | evaluates candidate actions → futures; scalar per action, no distributions |

### ACTION

| Box | Status | Provider | Evidence / gap |
|---|---|---|---|
| candidate generation | UNAVAILABLE | — | no operator-vocabulary action generation; `asi/discovery_engine` generates hypotheses (domain-bound) — §17 candidate |
| constraints | IMPLEMENTED | `policy.Constraint` (hard exclusion verified in benchmark) | |
| objectives | IMPLEMENTED | `policy.Objective` | benchmark: perturbed model flips selection |
| policy | IMPLEMENTED | `policy.decide` | |
| plan selection | PARTIAL | `asi/hierarchical_planning` (domain-bound, unreachable from TOE core) | no multi-step plan vs greedy comparison (§18) |

### LEARNING

| Box | Status | Provider | Evidence / gap |
|---|---|---|---|
| outcome attribution | PARTIAL | `receipts` provenance + `ValidityLearner` drift | no closed loop binding observed outcome to the exact generating decision (§25) |
| calibration | PARTIAL | causal coverage measurement (95% → 0.9 validation) | no prediction/trajectory/action calibration |
| memory | PARTIAL | `pythia_memory` 4-tier, `pythia_store` journal, `prime_memory`, `ManifoldBridge` | no episodic/causal/strategy/world-model separation; no long-horizon retention test (§19-20); consolidation→invariant unproven (§21); regime invalidation unmeasured (§22) |
| model/world update | PARTIAL | `asi/world_model` (domain-bound), monitor drift retrain | no `MODEL_SUPPORTED/DRIFT/CONTRADICTED` states in general core (§24) |
| strategy adaptation | PARTIAL | `SelfOptimisingLoop`, `asi/metacognition` | bound to CUOP/evolution domains |

### META (beyond the §2 diagram, required by §27-31)

| Box | Status | Provider | Evidence / gap |
|---|---|---|---|
| operator selection | PARTIAL | `TOEBridge.reason` task-field dispatch + `toe/representation.py` (`structural_signature` → `select_views`/`choose`) | lens-level selection implemented with explicit rejections + per-lens admissible-operator lists; sensitivity/VOI-driven operator-level choice still open (§27-28) |
| value of information | PARTIAL | `asi/discovery_engine` EIG (domain-bound) | no VOI on general reasoning tasks (§28) |
| adaptive precision | UNAVAILABLE | exact `Q(φ)`/`F4` + float paths exist | no sensitivity-driven regime selection; no error-bound bookkeeping per decision (§30-31) |
| self-test | PARTIAL | `Intelligence/self_test.py` (gate) | not an output-release gate inside the reasoning loop (§40) |
| disagreement arbitration | PARTIAL | `toe/agreement.py` | agreement measured; DISAGREEMENT surfacing + authority-based arbitration absent (§34) |

## Cross-cutting

| Concern | Status | Note |
|---|---|---|
| multi-representation `IntelligenceState` | IMPLEMENTED | `toe/intelligence_state.py` + `toe/representation.py`: 7 lenses (statistical/tensor/temporal/algebraic/geometric/topological/causal_graph) bound to one sha256 observation digest; `DivergenceError` on foreign digest; receipt ledger verifies; probe `toe_representation_elevation.json` 15/15 (§4-5) |
| cross-domain generality | UNMEASURED | toe core is domain-clean (asserted); no multi-domain capability matrix (§35-36) |
| invariance under transformation | UNMEASURED | §37 suite absent |
| adversarial intelligence | UNMEASURED | §39 suite absent (some causal negatives exist) |
| ablation / composition study | UNMEASURED | §44-45 absent |
| PYTHIA adapter boundary | IMPLEMENTED | `MINING→TOE→adapter→SearchPlan` clean; zero mining vocabulary in toe/ (asserted) |

## Reading the gaps

The honest position: TOE has a strong **supplied-model** reasoning core
(identify → intervene → counterfactual → explain → decide, all
receipt-chained) and a strong **substrate** (exact arithmetic, 11D fold).
The paradigm-relevant gaps are ~~(1) no bound multi-representation state~~
(resolved §4-5: `IntelligenceState` binds all lens views to one observation
identity; signature-driven selection with explicit rejections),
(2) no identifiability oracle beyond backdoor adjustment, (3) no action
*generation*, (4) no long-horizon memory evidence, (5) no model-revision
states, (6) no meta-controller over its own operators, (7) no
cross-domain/composition/ablation evidence. Elevation sections attack these
in dependency order.
