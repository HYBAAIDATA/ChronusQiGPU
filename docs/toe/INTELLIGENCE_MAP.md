# Canonical TOE intelligence map — section 2

Base `d298eaa` → elevation tip `7bc6d84`. Statuses: IMPLEMENTED / PARTIAL / DISCONNECTED / UNMEASURED /
UNAVAILABLE. Each entry names the module that provides the capability and the
evidence for the status (test file, benchmark section, or honest gap).

```text
                         TOE
             ┌────────── STATE ──────────┐
             │ representation            │ IMPLEMENTED
             │ tensor state              │ IMPLEMENTED
             │ geometry                  │ IMPLEMENTED
             │ topology                  │ IMPLEMENTED
             └────────────────────────────┘
                          ↓
             ┌────── UNDERSTANDING ──────┐
             │ relationships             │ IMPLEMENTED
             │ causal effects            │ IMPLEMENTED
             │ structural models         │ IMPLEMENTED
             │ explanation               │ IMPLEMENTED
             │ uncertainty               │ IMPLEMENTED
             └────────────────────────────┘
                          ↓
             ┌──────── FUTURES ──────────┐
             │ trajectories              │ IMPLEMENTED
             │ interventions             │ IMPLEMENTED
             │ counterfactuals           │ IMPLEMENTED
             │ multi-future simulation   │ IMPLEMENTED
             └────────────────────────────┘
                          ↓
             ┌───────── ACTION ──────────┐
             │ candidate generation      │ IMPLEMENTED
             │ constraints               │ IMPLEMENTED
             │ objectives                │ IMPLEMENTED
             │ policy                    │ IMPLEMENTED
             │ plan selection            │ IMPLEMENTED
             └────────────────────────────┘
                          ↓
             ┌──────── LEARNING ─────────┐
             │ outcome attribution       │ IMPLEMENTED
             │ calibration               │ IMPLEMENTED
             │ memory                    │ IMPLEMENTED
             │ model/world update        │ IMPLEMENTED
             │ strategy adaptation       │ IMPLEMENTED
             └────────────────────────────┘
```

## Per-box evidence

### STATE

| Box | Status | Provider | Evidence / gap |
|---|---|---|---|
| representation | IMPLEMENTED | `toe/operator_compilers.py` → `kellogg.quantum_tensor` / `kellogg.exact_tensor` | deterministic typed-operator compile → 32-dim Hilbert state + exact `Q(ζ8)` path; `toe_elevation_benchmark.json` state roundtrip 20/20 max_err 0.0 |
| tensor state | IMPLEMENTED | `kellogg/{quantum_tensor,exact_tensor,exact_field}` | Born rule, QFI, Clifford+T exact fractions; tests `test_a_*` |
| geometry | IMPLEMENTED | `toe/geometry.py` (`PoincareBall` on the φ-weighted 11D metric, exp/log maps, geodesics, Fréchet mean, Sarkar tree embedding, greedy routing, `SpectralGeometry`) + `toe/poincare_golden_11d.py` | metric axioms/geodesics/isometry tests (`tests/test_toe_geometry.py`); walled-grid delivery 1.00 vs 0.61 Euclidean, open-grid negative case recorded; wired into the machine's navigation stage. Boundary: declared operations in float64 within `MAX_EMBED_RADIUS`; embeddings are constructed, not learned from data |
| topology | IMPLEMENTED | `toe/topology.py` `StateTopology` + `reachability_task`; `ToplogicalAnalytics` VR-Betti lens | components/reachability/boundary/articulation measured vs Euclidean baseline which fails the dead-end trap (§32) |

### UNDERSTANDING

| Box | Status | Provider | Evidence / gap |
|---|---|---|---|
| relationships | IMPLEMENTED | `toe/relationships.py` `relationship_ladder` | ASSOCIATION / STRUCTURE_DISCOVERED (equivalence class) / STRUCTURE_SUPPLIED (assumption) / STRUCTURE_CONTRADICTED (local-Markov implication test) / EFFECT_IDENTIFIED / EFFECT_NOT_IDENTIFIED (refusal). Boundary: Markov-equivalent wrong graphs pass every implication test |
| causal effects | IMPLEMENTED | `causal_ladder`: `identify_backdoor`, `identify_frontdoor`, `is_backdoor_admissible`, `estimate_causal_effect` | benchmark: adjusted effect within 4 SE of truth on synthetic SCMs; latent confounder correctly refused |
| structural models | IMPLEMENTED | `StructuralCausalModel` + `causal_stack.discover_structures` | bounded discovery returns admissible equivalence class with sepsets/v-structures/Meek rules (§8) |
| explanation | IMPLEMENTED | `toe/explanation.py` + `toe/decision_explanation.py` | exact interventional Shapley + contrastive (why-A-not-B with decisive factor) + falsification faithfulness metric (§13-15) |
| uncertainty | IMPLEMENTED | `toe/uncertainty.py` | five axes (aleatoric/model/structural/identifiability/missing-evidence) + measured calibration coverage vs nominal (§11-12) |

### FUTURES

| Box | Status | Provider | Evidence / gap |
|---|---|---|---|
| trajectories | IMPLEMENTED | `predict_trajectory` + `causal_stack.evaluate_futures` | per-action Gaussian distributions via exact moment propagation; horizon degradation reported (§10) |
| interventions | IMPLEMENTED | `causal_ladder.do_operator`, `intervene` | benchmark: edge-cut verified, `E[Y|do(X=2)]` exact `ZPhi` |
| counterfactuals | IMPLEMENTED | `causal_ladder.counterfactual_state` + `causal_stack.compare_worlds` | FACTUAL vs WORLD A/B/C with deltas, causal paths, invariants, receipts (§9) |
| multi-future simulation | IMPLEMENTED | `causal_stack.evaluate_futures` | A1/A2/A3 → mean/variance/p05/p95 distributions + per-depth degradation (§10) |

### ACTION

| Box | Status | Provider | Evidence / gap |
|---|---|---|---|
| candidate generation | IMPLEMENTED | `toe/planning.generate_actions` | actions emitted only from declared `OperatorSpec` vocabulary — no arbitrary code path (§17) |
| constraints | IMPLEMENTED | `policy.Constraint` (hard exclusion verified in benchmark) | |
| objectives | IMPLEMENTED | `policy.Objective` | benchmark: perturbed model flips selection |
| policy | IMPLEMENTED | `policy.decide` | |
| plan selection | IMPLEMENTED | `toe/planning.py` `plan`/`greedy`/`compare_plan_vs_greedy` + `generate_actions` (declared operators only) | budget-trap test: plan 4.0 vs greedy 3.0; joint-intervention case 5 vs 3 (§17-18) |

### LEARNING

| Box | Status | Provider | Evidence / gap |
|---|---|---|---|
| outcome attribution | IMPLEMENTED | `toe/world_model.bind_outcome` | observed outcome bound to the exact decision SHA + per-dimension error attribution (§25) |
| calibration | IMPLEMENTED | `toe/uncertainty.calibrate_effects`/`calibrate_futures` | effect coverage@90/95/99 + futures band coverage measured (95%→96.7%, band 87.7% vs 90% nominal) (§12) |
| memory | IMPLEMENTED | `toe/memory.py` `MemoryStore` | one store, five namespaces; content-addressed recall survives 1000 distractors where recency window fails; consolidation emits invariants with source receipts; regime invalidation stales derived knowledge (§19-22) |
| model/world update | IMPLEMENTED | `toe/world_model.py` `WorldModel` | predict_transition + MODEL_SUPPORTED/DRIFT/CONTRADICTED/INSUFFICIENT_EVIDENCE assess + logged revise (§23-24) |
| strategy adaptation | IMPLEMENTED | `toe/world_model.OnlineAdapter` | CUSUM detection + online refit; pre/post performance + detection latency + forgetting probe measured on mid-run regime flip (§26) |

### META (beyond the §2 diagram, required by §27-31)

| Box | Status | Provider | Evidence / gap |
|---|---|---|---|
| operator selection | IMPLEMENTED | `toe/representation.py` + `toe/meta_reasoning.meta_decide` | lens selection + meta-controller routing by measured signals (margin/evidence/identifiability) (§27) |
| value of information | IMPLEMENTED | `toe/meta_reasoning.value_of_information` | decision-invariance over the plausible range — evidence requested only when it can flip the decision (§28) |
| adaptive precision | IMPLEMENTED | `toe/precision.py` `select_precision`/`float_error_bound`/`measure_exactness` | margin-vs-bound regime pick; demonstrated ordering flip on 1e16+1 cancellation (§30-31) |
| self-test | IMPLEMENTED | `toe/self_governance.self_check` + `adversarial_battery` | per-kind release invariants (causal/action/explanation/receipt); 9-attack battery, zero vulnerable (§39-40) |
| disagreement arbitration | IMPLEMENTED | `toe/arbitration.arbitrate` | DISAGREEMENT surfaced + resolved by declared authority/calibration — never averaged (§34) |

## Cross-cutting

| Concern | Status | Note |
|---|---|---|
| multi-representation `IntelligenceState` | IMPLEMENTED | `toe/intelligence_state.py` + `toe/representation.py`: 7 lenses (statistical/tensor/temporal/algebraic/geometric/topological/causal_graph) bound to one sha256 observation digest; `DivergenceError` on foreign digest; receipt ledger verifies; probe `toe_representation_elevation.json` 15/15 (§4-5) |
| cross-domain generality | IMPLEMENTED | `toe/generalization.py` `DomainAdapter` + `capability_matrix` | 5 capabilities × 5 domains, same machinery, domain code lines measured (§35-36) |
| invariance under transformation | IMPLEMENTED | `invariance_report` | rename/shuffle/scale measured — which hold reported, which fail reported (§37) |
| adversarial intelligence | IMPLEMENTED | `toe/self_governance.adversarial_battery` | 9 named attacks; refused/detected/degraded outcomes recorded; zero vulnerable (§39) |
| ablation / composition study | IMPLEMENTED | `reports/toe_intelligence_elevation.json` `ablations` + `composition_study` | per-capability removal effects + stacked composition measured (§44-45) |
| PYTHIA adapter boundary | IMPLEMENTED | `MINING→TOE→adapter→SearchPlan` clean; zero mining vocabulary in toe/ (asserted) |

## Reading the gaps

Post-elevation position (see `reports/toe_intelligence_elevation.json`):
the paradigm-relevant gaps from the pre-pass map are closed at the
measured level — bound multi-representation state (§4-5), strict
identifiability oracle with refusal (§7), bounded equivalence-class
discovery (§8), multi-world counterfactuals (§9), multi-future
distributions with horizon degradation (§10), five-axis uncertainty +
calibration (§11-12), computational/contrastive/falsifiable explanation
(§13-15), declared-operator action generation + bounded planning (§16-18),
namespaced memory with consolidation/invalidation (§19-22), world model
with revision states (§23-24), consequence binding + online adaptation
(§25-26), meta-controller/VOI/compute-aware routing (§27-29), adaptive
precision with real error bounds (§30-31), operational topology +
disagreement arbitration (§32-34), cross-domain capability matrix +
invariance + transfer (§35-38), adversarial battery + self-check +
measured promotion (§39-41).

Recorded negative results (kept, not laundered): memory views are
digests — larger than pickle, not compression; a supplied WRONG causal
graph is not mechanically detectable (estimates stay assumption-bound);
planning over linear SCMs adds nothing without interaction or budgets.

## Composition (2026-10-07)

| Concern | Status | Note |
|---|---|---|
| reasoning core | IMPLEMENTED | `toe/machine.py` `TOEMachine` runs one problem through every box above; composed by `toe/runtime.py` (`solve`/`learn`) |
| domain-neutral problem | IMPLEMENTED | `toe/problem.py`; adapters in `toe/adapters/`; 8 classes measured through one machine |
| durable learning | IMPLEMENTED | `toe/custody.py` via THESEUS; fresh-process restart + tamper tests |
| mining as first workload | IMPLEMENTED | `chronus/mla1517/mining/toe_problem.py` + `scripts/toe_mining_voyage.py`; validity stays `check_pow` |
| EUCLID access | IMPLEMENTED | `euclid/cognition/toe_capabilities.py`; `EuclidRuntime.toe` |
| ablations | MEASURED | `reports/toe_ablation_heldout.json` (held-out seeds, negative controls) |


## Dated assessment addendum — 2026-10-20

See [research/capability assessment](RESEARCH_CAPABILITY_ASSESSMENT_20261020.md) for TOE origin, 124 fresh research tests and 16 additional configuration/integration tests, historical artifact discrepancies, conditional custody coverage and tracked gaps. Earlier measurements above retain their original scope; this addendum does not silently reconcile them. Production/publication HOLD remains.
