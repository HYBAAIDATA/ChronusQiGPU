# Operational Runbooks, Verification Sweeps & Execution Harness

**Source**: `scripts/execute_sprint_1_to_4_pipeline.py` | `tests/` | `src/api/main.py`  
**Commit**: `07c563e8` | **Seeds**: `[1337, 42, 2026]` | **Status**: **MEASURED**  

---

## 1. Automated Test Sweeps

### 1.1 Core 101-Test Recursive Substrate Sweep
Executes the foundational Strange Loop, Security Swarm, Metacognitive Bridge, and Theoretical Foundations suites:

```powershell
python -m pytest `
  tests/test_recursive_self_learning.py `
  tests/test_security_swarm.py `
  tests/test_bridge_server.py `
  tests/test_theoretical_foundations_unit.py `
  tests/test_theoretical_foundations_properties.py `
  tests/test_euclid_voice_router.py `
  -v --basetemp=temp/pytest_101
```
**Expected Output**:
```text
tests/test_recursive_self_learning.py ................... [ 18 passed ]
tests/test_security_swarm.py .................           [ 17 passed ]
tests/test_bridge_server.py ..............               [ 14 passed ]
tests/test_theoretical_foundations_unit.py ............. [ 23 passed ]
tests/test_theoretical_foundations_properties.py ....... [ 13 passed ]
tests/test_euclid_voice_router.py ....................   [ 20 passed ]
============================= 105 passed in 48s =============================
```

### 1.2 Full 144-Test Production Suite (Including v17 & Adversarial)
Executes all 12 test files across Recursive Substrate, EUCLID v17 Production Integration (`DEF-01` through `DEF-06`), and Sprint 4 Red-Team vectors:

```powershell
python -m pytest `
  tests/test_recursive_self_learning.py `
  tests/test_security_swarm.py `
  tests/test_bridge_server.py `
  tests/test_theoretical_foundations_unit.py `
  tests/test_theoretical_foundations_properties.py `
  tests/test_euclid_voice_router.py `
  tests/test_idempotency_scoped.py `
  tests/test_task_verification.py `
  tests/test_emergence_metrics.py `
  tests/test_euclid_v17_runtime.py `
  tests/test_euclid_v17_production_integration.py `
  tests/test_sprint4_adversarial_suite.py `
  -v --basetemp=temp/pytest_144
```
**Expected Output**:
```text
======================= 144 passed in 75s =======================
```

### 1.3 Lucas & Pisot-Vijayaraghavan (PV) 52-Test Scaling Sweep
Executes the foundational integer ring identities, fast doubling, Cassini-Hoggatt conservation, and Pisot precision boundary tests:

```powershell
$env:PYTHONPATH="chronus/packages/chronos-one-igpu/src;."
python -m pytest `
  tests/test_a_lucas_math.py `
  tests/test_benchmark_lucas_pisot.py `
  tests/test_lucas15_operator_ablation.py `
  tests/test_lucas_algebra.py `
  tests/test_lucas_exponential_scaling_honesty.py `
  tests/test_lucas_partition.py `
  tests/test_lucas_pisot_scaling_research.py `
  -v -p no:cacheprovider --basetemp=.pytest_tmp
```
**Expected Output**:
```text
============================= 52 passed in 14.34s =============================
```

### 1.4 Euclid Arena 100-Test Anti-Hype & Benchmark Suite
Executes the full 100-test comparative arena across all 5+1 intelligences, Solver/Ineffable duel, and Frontier duel:

```powershell
python -m pytest `
  tests/euclid_arena/test_10_predictive.py `
  tests/euclid_arena/test_11_causal.py `
  tests/euclid_arena/test_12_counterfactual.py `
  tests/euclid_arena/test_13_topological.py `
  tests/euclid_arena/test_14_geometric.py `
  tests/euclid_arena/test_15_quantum_ext.py `
  tests/euclid_arena/test_16_solver_duel.py `
  tests/euclid_arena/test_17_ineffable_duel.py `
  tests/euclid_arena/test_18_frontier_duel.py `
  tests/euclid_arena/test_19_efficiency.py `
  -v -p no:cacheprovider --basetemp=.pytest_tmp
```
**Expected Output**:
```text
============================= 100 passed in 5.71s =============================
```

---

## 2. Full Scientific Pipeline Execution

Generates all research outputs, entropy traces, and replication release archives:

```powershell
python scripts/execute_sprint_1_to_4_pipeline.py
```
**Expected Deliverables**:
- `artifacts/research/first_breath_session.jsonl`
- `artifacts/research/entropy_trace.csv`
- `artifacts/research/provocation_results.json`
- `artifacts/research/transfer_case_ctcf.json`
- `artifacts/research/ablation_matrix.csv`
- `artifacts/research/redteam_ledger.jsonl`
- `release.zip` (Contains all 19 verified release artifacts)

---

## 3. First Breath Gateway Curls & Endpoint Verification

### 3.1 Start the Cognitive Gateway Server
```powershell
uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

### 3.2 Inject ERN Spike (Fast Reflex & Working Memory Lockout)
```bash
curl -X POST http://127.0.0.1:8000/api/v1/euclid/voice/ern-spike   -H "Content-Type: application/json"   -d '{
    "source_agent": "operator",
    "intensity": 9.0,
    "confidence_pre": 0.8,
    "expected_outcome": "Clean boundary",
    "observed_outcome": "Session token leak",
    "violated_invariant": "SECURITY_BOUNDARY",
    "active_concept_nodes": ["session_auth"]
  }'
```
**Expected Output**:
```json
{
  "status": "SPIKE_REGISTERED",
  "reflex_marker": {
    "latency_ms": 12.4,
    "audio_cue": "Hmm, let me trace that side-effect..."
  },
  "manifold_state": {
    "trauma_node": "session_auth",
    "initial_singularity_curvature": -1.62,
    "insufficiently_map_matched": true,
    "allow_write": false
  }
}
```

### 3.3 Trigger Discrete Ricci Reconciliation Loop
```bash
curl -X POST http://127.0.0.1:8000/api/v1/euclid/reconciliation/run-reflection   -H "Content-Type: application/json"   -d '{
    "target_node": "session_auth",
    "max_steps": 8,
    "tau_tolerance": 0.05
  }'
```
**Expected Output**:
```json
{
  "status": "RECONCILIATION_COMPLETE",
  "steps_executed": 8,
  "final_curvature": -0.0345,
  "in_equilibrium": true,
  "allow_write": true
}
```

### 3.4 Query Metacognitive Readiness
```bash
curl -X GET http://127.0.0.1:8000/api/v1/euclid/validation/readiness
```
**Expected Output**:
```json
{
  "readiness_status": "HOMEOTYPIC_EQUILIBRIUM",
  "strange_loop_active": true,
  "phi": 1.0,
  "irreducibility": 0.5625,
  "curriculum_phase": "Phase 2: Scaffolded Dialogue"
}
```
