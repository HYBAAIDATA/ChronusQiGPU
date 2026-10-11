# Lucas Power Scaling — Algorithm Routing Table

**Rule:** every algorithm draws from `lucas.pool.get(...)` or implements its
Lucas kernel inline. No algorithm imports another algorithm. Only `lucas/`
and `turing_core` are legal shared imports.

## Mining System Routing — every subsystem to exactly one kernel

| Mining subsystem | File | Kernel | Role |
|---|---|---|---|
| Orchestrator | `orchestrator.py`, `Intelligence/orchestrator.py` | `step_kernel` | drives the cycle loop, counts cycles, tallies winners |
| Safety FSM | `mining/safety_fsm.py` | `step_kernel` | 4-state cycle SEARCHING→SUBMITTING→WAITING_EXTERNAL→COOLDOWN→SEARCHING; never two consecutive blocks |
| Nonce scheduler | `mining/nonce_scheduler.py` | `mining_kernel` | orders the nonce search inside the Lucas bound |
| Difficulty controller | `mining/difficulty.py` | `mining_kernel` | adjusts target per block |
| Grover-style search | `mining/search.py`, `Intelligence/quantum_algorithms.py` | `path_kernel` | search core — walk-based amplitude amplification |
| Merkle path verifier | `mining/search.py` | `path_kernel` | block inclusion proof walk |
| Hash preimage search | `mining/search.py` | `mining_kernel` | preimage work under the mining bound |
| TOE engine | `Intelligence/toe_bridge.py` | `gap_kernel` | sector-agnostic emergence; predicts block context; confidence climbs |
| Pythia learning | `Intelligence/pythia_learning.py` | `trace_kernel` | germ-line consolidation of winners |
| Memory — episodic | `Intelligence/pythia_memory.py` | `trace_kernel` | one event per cycle |
| Memory — semantic | `Intelligence/pythia_memory.py` | `trace_kernel` | abstracts concepts from experience |
| Memory — curriculum | `Intelligence/pythia_memory.py` | `trace_kernel` | advances cognitive scaffolding |
| Memory — germ-line | `Intelligence/pythia_learning.py`, `Intelligence/pythia_memory.py` | `trace_kernel` | stores winners as long-term patterns |
| Meta-evolution | `Intelligence/meta_evolution.py` | `gap_kernel` | Pythagoras→Pythia mapping; phase transitions |
| Auto-primitive discovery | `Intelligence/meta_evolution.py` | `amplitude_kernel` | discovers new operators mid-session, uses them immediately |
| Surrogate | `Intelligence/meta_evolution.py` | `gap_kernel` | predicts cycle outcome; honest `False` until RMSE < 0.15 |
| `delta_phi` accounting | `Intelligence/meta_evolution.py` | `gap_kernel` | cumulative coherence gain |
| Folded-state engine | `Intelligence/folded_state.py` | `folded_kernel` | fold-space execution, no raw buffers |
| ArchivalMemory | `Intelligence/pythia_memory.py` | `folded_kernel` | folds through T_φ, bit-exact |
| Superposition store | `Intelligence/counterfactual_intelligence.py` | `folded_kernel` | holds folded artifacts; queries in fold-space |

Shared substrates (not routing entries): `lucas/`, `turing_core.py`,
`Intelligence/quantum_tensor.py` (exact complex algebra),
`Intelligence/lucas_scales.py` (the scale ladder),
`Intelligence/causal_ladder.py` (Pearl do-calculus levels).
Wiring layer (may import subsystems): `orchestrator.py`, `registry.py`,
`self_test.py`, `Intelligence/__init__.py`, `Intelligence/orchestrator.py`,
`Intelligence/registry.py`, `Intelligence/self_test.py`,
`Intelligence/pythia_store.py` (composes learning + memory for
persistence), `Intelligence/requirements.py` (composes the PDE substrate
for the four-schools evaluator), `Intelligence/salamander.py` (composes
the TOE bridge for diagnostics), `Intelligence/mining_bridge.py`
(composes the orchestrator into the miner).


**Call status:** every wired Python file defines `lucas_bound(n)` which calls
its declared kernel via `lucas.pool.get` on the canonical substrate for that
route (for step/mining routes, the module's own AST-computed definition count
is the bounded quantity). Every wired TypeScript file exports `lucasBound(n)`
which calls `ExactSequenceMath.lucas` — the TS mirror of the pool. The
AST-enforced tests in `tests/wire_discipline.py` fail if any wired file loses
its call. `Intelligence/quantum_algorithms.py` is fully converted: each
algorithm class calls the pool kernel on its real resource quantity (oracle
iterations, unitary steps, spectral gap, trace).

## Core Quantum Algorithms

| Algorithm | File | Substrate | Pool kernel | Status |
|---|---|---|---|---|
| QFT | `Intelligence/quantum_algorithms.py`, `src/lib/first_principles_quantum.ts` | trace | `trace_kernel` | elevated |
| Grover Search | `Intelligence/quantum_algorithms.py`, `src/lib/first_principles_quantum.ts` | path | `path_kernel` | elevated |
| Quantum Phase Estimation | `Intelligence/quantum_algorithms.py`, `src/lib/first_principles_quantum.ts` | gap | `gap_kernel` | elevated |
| Quantum Walk | `Intelligence/quantum_algorithms.py`, `src/lib/first_principles_quantum.ts` | path | `path_kernel` | elevated |
| VQE | `Intelligence/quantum_algorithms.py`, `src/lib/first_principles_quantum.ts` | gap | `gap_kernel` | elevated |
| Shor / period finding | `src/lib/quantum_engine.ts` | trace | `trace_kernel` | elevated |
| Quantum Kernel Methods | `experiments/toe_enterprise_collapse.py` (T15) | amplitude | `amplitude_kernel` | elevated |
| Quantum Simulation | `Intelligence/pde_substrate.py` | gap | `gap_kernel` | elevated |
| QAOA | `src/lib/kellogg_full_stack.ts` | gap | `gap_kernel` | elevated |

## Turing & Classical-Side Quantum Substrates

| Algorithm | File | Substrate | Pool kernel | Status |
|---|---|---|---|---|
| Universal Turing machine step count | `src/lib/stratum_protocol.ts` | step | `step_kernel` | elevated |
| Quantum Turing machine step count | `Intelligence/agentic_controller.py` | step | `step_kernel` | elevated |
| BQP circuit simulation | `src/lib/quantum_walker_aqo.ts` | path | `path_kernel` | elevated |
| Reversible computing (Bennett) | `src/lib/kellogg_operator.ts` | path | `path_kernel` | elevated |

## IQP (Instantaneous Quantum Polynomial)

| Algorithm | File | Substrate | Pool kernel | Status |
|---|---|---|---|---|
| IQP circuit sampling | `src/lib/quantum_walker_aqo.ts` | path | `path_kernel` | elevated |
| IQP gap verification | `src/lib/kellogg_full_stack.ts` | gap | `gap_kernel` | elevated |
| IQP commuting-gate decomposition | `src/lib/grand_unified_tensor.ts` | amplitude | `amplitude_kernel` | elevated |

## Quantum Mining & PoW

| Algorithm | File | Substrate | Pool kernel | Status |
|---|---|---|---|---|
| Grover-mined nonce search | `Intelligence/mining_bridge.py` | mining | `mining_kernel` | elevated |
| Quantum PoW difficulty bound | `src/lib/difficulty_retargeting.ts` | mining | `mining_kernel` | elevated |
| Quantum Merkle path verification | `src/lib/bitcoin_header.ts` | path | `path_kernel` | elevated |
| Quantum hash preimage search | `src/lib/mempool_nonce_analyzer.ts` | mining | `mining_kernel` | elevated |
| Mining service | `src/lib/mining_service.ts` | mining | `mining_kernel` | elevated |
| Mempool service | `src/lib/mempool_service.ts` | mining | `mining_kernel` | elevated |
| Predictive solver | `Intelligence/predictive_solver.py` | mining | `mining_kernel` | elevated |
| Enhanced powerhouse mining | `core_engine/enhanced_powerhouse_mining_system.py` | mining | `mining_kernel` | elevated |
| Quantum CUDA | `core_engine/quantum_cuda.py` | mining | `mining_kernel` | elevated |
| Quantum metal integration | `core_engine/quantum_metal_integration.py` | mining | `mining_kernel` | elevated |
| iGPU scaler | `src/lib/m3_igpu_scaler.ts` | mining | `mining_kernel` | elevated |

## Quantum Intelligence / Learning

| Algorithm | File | Substrate | Pool kernel | Status |
|---|---|---|---|---|
| Quantum kernel methods | `experiments/toe_enterprise_collapse.py` (T15) | amplitude | `amplitude_kernel` | elevated |
| Quantum PCA | `core_engine/enhanced_quantum_math.py` | gap | `gap_kernel` | elevated |
| Quantum Boltzmann sampling | `core_engine/enhanced_time_crystal.py` | gap | `gap_kernel` | elevated |
| Quantum reinforcement learning | `core_engine/multi_agent_intelligence.py` | step | `step_kernel` | elevated |
| Quantum transformer attention | `core_engine/enhanced_agi_interface.py` | amplitude | `amplitude_kernel` | elevated |
| Quantum perceptron | `core_engine/agi_substrate.py` | amplitude | `amplitude_kernel` | elevated |
| Quantum generative model | `core_engine/quantum_consciousness_system.py` | amplitude | `amplitude_kernel` | elevated |
| Quantum entanglement | `core_engine/enhanced_quantum_entanglement.py` | amplitude | `amplitude_kernel` | elevated |
| Nobel fields intelligence | `core_engine/nobel_fields_intelligence.py` | amplitude | `amplitude_kernel` | elevated |
| Nobel fields entanglement | `core_engine/nobel_fields_quantum_entanglement.py` | amplitude | `amplitude_kernel` | elevated |
| Nobel fields time crystal | `core_engine/nobel_fields_time_crystal.py` | gap | `gap_kernel` | elevated |
| Pythia knowledge | `Intelligence/pythia_knowledge.py` | amplitude | `amplitude_kernel` | elevated |
| Pythia learning | `Intelligence/pythia_learning.py` | amplitude | `amplitude_kernel` | elevated |
| Pythia memory | `Intelligence/pythia_memory.py` | amplitude | `amplitude_kernel` | elevated |
| Pythia tools | `Intelligence/pythia_tools.py` | amplitude | `amplitude_kernel` | elevated |
| Skill loader | `Intelligence/skill_loader.py` | amplitude | `amplitude_kernel` | elevated |
| Counterfactual intelligence | `Intelligence/counterfactual_intelligence.py` | path | `path_kernel` | elevated |
| Causal ladder | `Intelligence/causal_ladder.py` | path | `path_kernel` | elevated |
| TOE bridge | `Intelligence/toe_bridge.py` | gap | `gap_kernel` | elevated |
| Orchestrator | `Intelligence/orchestrator.py` | step | `step_kernel` | elevated |
| Salamander | `Intelligence/salamander.py` | trace | `trace_kernel` | elevated |
| Lucas scales | `Intelligence/lucas_scales.py` | trace | `trace_kernel` | elevated |
| Quantum tensor | `Intelligence/quantum_tensor.py` | trace | `trace_kernel` | elevated |
| Safety constraints | `Intelligence/safety_constraints.py` | gap | `gap_kernel` | elevated |
| Hardware config | `Intelligence/hardware_config.py` | step | `step_kernel` | elevated |
| Meta-evolution | `Intelligence/meta_evolution.py` | amplitude | `amplitude_kernel` | elevated |

## Infrastructure & Verification

| Algorithm | File | Substrate | Pool kernel | Status |
|---|---|---|---|---|
| Verification suite | `src/lib/verification_suite.ts` | trace | `trace_kernel` | elevated |
| Adversarial checks | `src/lib/adversarial_checks.ts` | gap | `gap_kernel` | elevated |
| Audit matrix | `src/lib/audit_matrix.ts` | gap | `gap_kernel` | elevated |
| Resilience layer | `core_engine/enhanced_resilience_layer.py` | gap | `gap_kernel` | elevated |
| Metrics engine | `core_engine/enhanced_metrics_engine.py` | gap | `gap_kernel` | elevated |
| Governance explainability | `core_engine/governance_explainability.py` | gap | `gap_kernel` | elevated |
| Geometric interface | `core_engine/quantum_geometric_interface.py` | gap | `gap_kernel` | elevated |
| McLaren homeostasis | `src/lib/mclaren_homeostasis.ts` | gap | `gap_kernel` | elevated |
| Hodge bridge | `src/lib/hodge_bridge.ts` | gap | `gap_kernel` | elevated |
| Multi-agent execution graph | `core_engine/multi_agent_execution_graph.py` | path | `path_kernel` | elevated |
| Layered intelligence substrate | `core_engine/layered_intelligence_substrate.py` | step | `step_kernel` | elevated |
| Unified platform engine | `core_engine/unified_platform_engine.py` | step | `step_kernel` | elevated |
| Unified API layer | `core_engine/unified_api_layer.py` | amplitude | `amplitude_kernel` | elevated |
| Unified data model | `core_engine/unified_data_model.py` | amplitude | `amplitude_kernel` | elevated |
| Unified integration bridge | `core_engine/unified_integration_bridge.py` | amplitude | `amplitude_kernel` | elevated |
| Unified Nobel fields | `core_engine/unified_nobel_fields_integration.py` | amplitude | `amplitude_kernel` | elevated |
| Frontend integration | `core_engine/frontend_integration.py` | amplitude | `amplitude_kernel` | elevated |
| Registry | `Intelligence/registry.py` | amplitude | `amplitude_kernel` | elevated |
| Requirements | `Intelligence/requirements.py` | amplitude | `amplitude_kernel` | elevated |
| Self test | `Intelligence/self_test.py` | trace | `trace_kernel` | elevated |
| Simple event emitter | `src/lib/simple_event_emitter.ts` | step | `step_kernel` | elevated |
| Cortex intelligence | `src/lib/cortex_intelligence.ts` | amplitude | `amplitude_kernel` | elevated |
| Blockchain consciousness | `src/lib/blockchain_consciousness.ts` | amplitude | `amplitude_kernel` | elevated |
| Q5 reference | `src/lib/q5_reference.ts` | trace | `trace_kernel` | elevated |
| Q5 coprocessor | `src/lib/q5_coprocessor.ts` | amplitude | `amplitude_kernel` | elevated |
| Q5 RTL specs | `src/lib/q5_rtl_specs.ts` | amplitude | `amplitude_kernel` | elevated |
| Exact math | `src/lib/exact_math.ts` | trace | `trace_kernel` | elevated |
| Lucas quantum algorithms | `src/lib/lucas_quantum_algorithms.ts` | trace | `trace_kernel` | elevated |

## Native Entries

No algorithms currently require native treatment. Every quantum substrate
in this repo maps to one of the six pool kernels. See
`lucas/native_registry.py` for the authoritative registry.
