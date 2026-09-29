# Capability matrix — every named capability with an execution trace

Pin: `e09afab`. Seeded from `system_fabric.SUBSYSTEMS` (runtime fabric map) at
baseline. `fabric`/`orchestrator`/`idle` are the repo's *static labels* — MAP-01
requires every claimed wire to have runtime evidence or an honest "not wired"
verdict; the Evidence column is filled only from executed checks.

States: PASS / FAIL / BLOCKED / NOT_RUN / NOT_APPLICABLE. Owner A rows concern
mathematical/computational capability; Owner B rows concern mining/workflows.

| key | capability (module) | fabric label | gate | verified status @ baseline | evidence / remaining |
|---|---|---|---|---|---|
| igpu | Bespoke iGPU substrate (`mining.bitcoin_hasher`) | production | opencl | NOT_RUN | no OpenCL device here; host CPU mirror exercised via tests |
| unified_punch | Phi-filter nonce scoring (`Intelligence.unified_punch`) | production | — | PASS | covered by `tests/` suite + `Intelligence.self_test` PASS |
| manifold_iid | IID manifold device 32-face (`Intelligence.search_crystal`) | fabric | — | PENDING-A | fold path claimed exercised by verification — needs runtime evidence |
| poincare_11d | 11D Poincare golden fold/unfold (`toe.poincare_golden_11d`) | orchestrator | — | PENDING-A | exact math + 11d nonce order in bridge |
| yang_mills | Yang-Mills mass gap (`toe.system`) | fabric | — | PENDING-A | T10 verified per candidate in chain run |
| ricci | Ricci-Einstein exact relation (`Intelligence.chain_verification`) | fabric | — | PENDING-A | stage 9 of 11-stage chain |
| toe | TOE 12-theorem arbiter (`toe.system`) | fabric | — | PENDING-A | provenance + full-chain run evidence needed |
| structured_search | Poincare-Cassini search (`Intelligence.search_crystal`) | orchestrator | — | PENDING-A | — |
| unstructured_search | Grover-exact (`tqc.grover_exact_scale`) | idle | — | PENDING-A | honestly idle — wired or documented |
| tensor | Exact qubit tensor (`kellogg.exact_tensor`) | production | — | PENDING-A | tests cover; runtime path trace needed |
| vqc | 11-qubit VQC (`tqc.scaled_execution`) | production | pool_credentials | **FAIL** | `test_vqc_execution_certifies_window`: hashes=1 vs 256 (early-exit) — Owner A |
| folding_storage | Zeckendorf archival-exact fold (`Intelligence.folded_state`) | orchestrator | — | PASS | self_test `folded_state — bit_exact=True` |
| salamander | Self-healing engine (`Intelligence.salamander`) | orchestrator | mmio | PENDING-B | fault→repair→verify loop needs behavioral evidence |
| agentic_workflow | 6-phase autonomous mining (`Intelligence.agentic_mining`) | fabric | — | PENDING-B | lifecycle/cancellation/recovery evidence |
| chain_verification | 11-stage chain (`Intelligence.chain_verification`) | fabric | — | PENDING-A | — |
| hash_pipeline | sha256d sole accept authority (`mining.hash_pipeline`) | production | — | PASS | `re_paper_gate` PASS; proof-boundary unittests |
| m32_solver | M32 lane solver (`mla1517.mining.solver`) | production | — | PASS | unittest discover 203 OK |
| stratum_bridge | Stratum arms (`mining.stratum_bridge`) | production | opencl+creds | PARTIAL | dry-run/CPU path exercised; live pool NOT_RUN (authorization) |
| strict_quantum | Work-window certificates (`toe.strict_quantum`) | production | — | PENDING-A | — |
| agentic_controller | Solver dispatch (`Intelligence.agentic_controller`) | orchestrator | — | PASS | self_test `agentic_controller PASS (jobs=5, winners=1)` |
| toe_bridge | Tomography/trajectory/causality (`toe.bridge`) | orchestrator | — | PENDING-A | — |
| meta_evolution | Meta-evolution (`Intelligence.meta_evolution`) | orchestrator | — | PASS | self_test verdict (dphi=+0.0038, transitions=5) |
| pythia_learning | Learning substrate (`Intelligence.pythia_learning`) | orchestrator | — | PASS | self_test ACTIVE (learned=14, consolidated=5) |
| pythia_memory | Memory system (`Intelligence.pythia_memory`) | orchestrator | — | PASS | self_test ACTIVE (semantic=91) |
| predictive_solver | Predictive solver (`Intelligence.predictive_solver`) | orchestrator | — | PENDING-A | needs nltk vader_lexicon at runtime |
| counterfactual | Counterfactual intelligence | orchestrator | — | PENDING-A | Pearl rungs measured per commit 7f89d84 |
| safety | Hashrate-cap FSM (`Intelligence.safety_constraints`) | orchestrator | — | PENDING-B | — |
| registry | 45-module registry (`Intelligence.registry`) | orchestrator | — | PENDING-B | — |
| manifold_bridge | substrate-12 storage (`toe.manifold_bridge`) | fabric | — | PENDING-A | — |
| pythia_agent | Deterministic orchestration (`pythia_agent`) | idle | — | NOT_RUN | honest idle label |
| ontology_chain | Ontology mining chain | idle | — | NOT_RUN | honest idle label |
| search_tree | Parallel search tree | idle | — | NOT_RUN | honest idle label |
| toe_tensor_ml | Kellogg tensor ML family | idle | — | NOT_RUN | honest idle label |
| salamander_transaction | Salamander transaction layer | idle | — | NOT_RUN | honest idle label |
| first_principles_quantum | First-principles quantum | idle | — | NOT_RUN | honest idle label |
| pulvini_runtime | Pulvini runtime | idle | — | NOT_RUN | honest idle label |
| discovery | Mathematical discovery engine | idle | — | NOT_RUN | honest idle label |
| pool_aware_miner | Pool-aware miner | idle | — | NOT_RUN | honest idle label |

Seed backlog statuses: RUN-01/RUN-02, DATA-01/DATA-02, MAP-01 → PENDING (Owner B
platform files; verified/fix in flight).
