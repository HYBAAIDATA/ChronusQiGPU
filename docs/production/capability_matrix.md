# Capability matrix — every named capability with an execution trace

Pin: `e09afab` (baseline) — refreshed at `73a716d` (post-A/C merge) and `10c6a63`
(post-fold, production-readiness re-baseline) where marked. Seeded from `system_fabric.SUBSYSTEMS` (runtime fabric map) at
baseline. `fabric`/`orchestrator`/`idle` are the repo's *static labels* — MAP-01
requires every claimed wire to have runtime evidence or an honest "not wired"
verdict; the Evidence column is filled only from executed checks.

States: PASS / FAIL / BLOCKED / NOT_RUN / NOT_APPLICABLE. Owner A rows concern
mathematical/computational capability; Owner B rows concern mining/workflows.

| key | capability (module) | fabric label | gate | verified status @ baseline | evidence / remaining |
|---|---|---|---|---|---|
| chronus | Bespoke Chronus substrate (`mining.bitcoin_hasher`) | production | opencl | NOT_RUN | no OpenCL device here; host CPU mirror exercised via tests |
| unified_punch | Phi-filter nonce scoring (`Intelligence.unified_punch`) | production | — | PASS | covered by `tests/` suite + `Intelligence.self_test` PASS |
| manifold_iid | IID manifold device 32-face (`Intelligence.search_crystal`) | fabric | — | **PASS** (#23) | D: `enumerate_nonces` ≡ `_candidate_stream` ordering, coverage/`faces_exhausted` accounting, winner re-verified vs sha256d, cassini_permutation bijective, partition gapless; `tests/test_c_search_crystal.py` |
| poincare_11d | 11D Poincare golden fold/unfold (`toe.poincare_golden_11d`) | orchestrator | — | **PASS** (#23) | D: fold/unfold bit-exact preimage roundtrip + documented closed-form fallback, Zeckendorf encode/slot/mask exact, Beatty disjointness+coverage, cassini det (−1)^k, certificate honesty; `tests/test_c_poincare_golden_11d.py` |
| yang_mills | Yang-Mills mass gap (`toe.system`) | fabric | — | **PASS** (#23) | D: provenance hash-chain tamper detection (mutate/reorder/hash-overwrite), 12-theorem recompute all-pass on stored candidate; `tests/test_c_toe_system.py` |
| ricci | Ricci-Einstein exact relation (`Intelligence.chain_verification`) | fabric | — | **PASS** (#23) | D: 11-stage envelope, fail-closed `ready`, `_recheck_winner` accept/reject incl. nonce mask, overlay self-consistency (32=12+20 faces, multiplier honestly `projection_only_never_measured`); `tests/test_c_chain_verification.py` |
| toe | TOE 12-theorem arbiter (`toe.system`) | fabric | — | **PASS** (#23) | D: provenance + 12-theorem recompute (see yang_mills row), coordination-learning bounds; `tests/test_c_toe_system.py` |
| structured_search | Poincare-Cassini search (`Intelligence.search_crystal`) | orchestrator | — | **PASS** (#23) | same evidence class as manifold_iid; `tests/test_c_search_crystal.py` |
| unstructured_search | Grover-exact (`tqc.grover_exact_scale`) | idle | — | **PASS** @73a716d | A: FoldedGrover iterate/closed-form bit-exact, Cassini drift <1e-12; `binet_residual` float64 cancellation fixed (`|ψ|ⁿ` direct) both copies; `tests/test_a_grover_exact.py` |
| tensor | Exact qubit tensor (`kellogg.exact_tensor`) | production | — | **PASS** @73a716d | A: Z[φ] exact layer — `phi_power`, `pisot_drift`, norm `(-1)ⁿ`, Zeckendorf — `tests/test_a_exact_algorithms.py` |
| vqc | 11-qubit VQC (`tqc.scaled_execution`) | production | pool_credentials | **PASS** @73a716d | A fix merged (#18): `tests/test_vqc.py` 8/8 verified on integrated main |
| folding_storage | Zeckendorf archival-exact fold (`Intelligence.folded_state`) | orchestrator | — | PASS | self_test `folded_state — bit_exact=True` |
| salamander | Self-healing engine (`Intelligence.salamander`) | orchestrator | mmio | **PASS** (#22) | B: fault→ack-gated retire→verify-recovery→probationary readmit, failover once/cooldown/cancel, `MIN_LANES` degraded floor — `tests/test_b_*` |
| agentic_workflow | 6-phase autonomous mining (`Intelligence.agentic_mining`) | fabric | — | **PASS** (#22, +10c6a63) | B: campaign start→running→stop→`stopped` terminal, `retire_all` on every exit incl. failure, operator-stop `stop_detail`; @10c6a63 truthful `stopping` mid-state (`finished_at` = worker exit, not request time; terminal `stopped` restart-eligible) + per-phase share deltas w/ reset re-arm; `tests/test_b_*` |
| chain_verification | 11-stage chain (`Intelligence.chain_verification`) | fabric | — | **PASS** (#23) | D: 11-stage envelope + `_recheck_winner` boundaries (see ricci row); `tests/test_c_chain_verification.py` |
| hash_pipeline | sha256d sole accept authority (`mining.hash_pipeline`) | production | — | PASS | `re_paper_gate` PASS; proof-boundary unittests |
| m32_solver | M32 lane solver (`chronus.mla1517.mining.solver`) | production | — | PASS | unittest discover 203 OK |
| stratum_bridge | Stratum arms (`mining.stratum_bridge`) | production | opencl+creds | PARTIAL | dry-run/CPU path exercised; live pool NOT_RUN (authorization) |
| strict_quantum | Work-window certificates (`toe.strict_quantum`) | production | — | **PASS** @73a716d | A: exact Q(i) work-window certification, `consensus_authority=False` honored; `tests/test_a_exact_algorithms.py` |
| agentic_controller | Solver dispatch (`Intelligence.agentic_controller`) | orchestrator | — | PASS | self_test `agentic_controller PASS (jobs=5, winners=1)` |
| toe_bridge | Tomography/trajectory/causality (`toe.bridge`) | orchestrator | — | **PASS** (#23) | D: hamiltonian hermiticity, propagator unitarity+cache, codec roundtrips, causal intervene/counterfactual/estimate_effect + receipt issuance, receipt-chain tamper detection, replay, config-id dedup; `tests/test_c_toe_bridge.py` |
| meta_evolution | Meta-evolution (`Intelligence.meta_evolution`) | orchestrator | — | PASS | self_test verdict (dphi=+0.0038, transitions=5) |
| pythia_learning | Learning substrate (`Intelligence.pythia_learning`) | orchestrator | — | PASS | self_test ACTIVE (learned=14, consolidated=5) |
| pythia_memory | Memory system (`Intelligence.pythia_memory`) | orchestrator | — | PASS | self_test ACTIVE (semantic=91) |
| predictive_solver | Predictive solver (`Intelligence.predictive_solver`) | orchestrator | — | PENDING-A | needs nltk vader_lexicon at runtime |
| counterfactual | Counterfactual intelligence | orchestrator | — | **PASS** | Pearl intervention/counterfactual rungs measured @7f89d84; receipt-chain seams in `tests/test_c_toe_bridge.py` (#23) |
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

Seed backlog statuses: RUN-02, DATA-02, MAP-01 → PASS on #22 (B: campaign arms
retire on every exit; sidecar metrics 30 s TTL + hashrate None-vs-0.0;
importlib-verified wiring tiers). RUN-01 residual (stop marked `stopped` at
request time, `finished_at` fabricated) → fixed @10c6a63: truthful `stopping`
state until worker exit. DATA-01 residual (campaign `shares_accepted` = cumulative
counter) → fixed @10c6a63: per-phase deltas with counter-reset re-arm.
DOC-01 → closed @10c6a63: AGENTS.md §4 rewritten against the real product
(control API + static UI + Python worker plane), README records the per-operation
device policy (`cpu_reference` fallback carries `fallback_reason`).
`autonomous_supervisor` IA02 (dead import, supervisor never built) → fixed here;
`trigger_cycle` now runs real heal cycles. @10c6a63 also fixed Windows-only
persistence defects surfaced by the re-baseline: `euclid.evidence.atomic_write`
(POSIX-only `os.fchmod` + leaked fd on failure) and `MemoryDatabase.backup`
(`sqlite3.connect` context manager never closed the output connection).
