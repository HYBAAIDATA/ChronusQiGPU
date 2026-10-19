# Strange Loop & EUCLID v17 Operator Runbook

**Document ID**: `RUNBOOK-STRANGE-LOOP-V17`  
**Canonical Subsystem**: `Intelligence/recursive_self_learning.py`, `Intelligence/theoretical_foundations.py`, `euclid/cognition/`, `chronus/mla1517_platform/python/control_api.py`  
**Owner Declarations Alignment**: D1–D13 (`OWNER_DECLARATIONS.md`, `UNIVERSAL_PRINCIPLE_MAP.md`)

---

## 1. Operational Overview

The **Recursive Self-Learning Substrate** implements Douglas Hofstadter's *Strange Loop* (second-order meta-learning) coupled with **Integrated Information Theory (IIT $\Phi$)**, **Cognitive Irreducibility** via cross-layer bitwise XOR entanglement, **Adaptive Geometric Refolding** ($\text{Euclidean} \leftrightarrow \text{Spherical} \leftrightarrow \text{Hyperbolic}$), and **Penrose Objective Reduction ($\Delta E \cdot \Delta t \ge \hbar/2$)** threshold telemetry inside the unified Python control plane.

Per **Owner Declaration D8** (Single Backend, Multiple Frontends), the legacy multi-language split (`src/core/*.ts` and `python_backend/pythia_mining/*.py`) has been consolidated into the canonical Python intelligence substrate:
- `Intelligence/recursive_self_learning.py` (`RecursiveSelfLearningSubstrate`)
- `Intelligence/theoretical_foundations.py` (`PenroseObjectiveReduction`, `DeutschKnowledgeSubstrate`, `DuSautoySymmetry`, `LucasNumberSubstrate`, `ZeckendorfBitCascade`, `NonLocalStructuralCorrelation`, `GoldenRatioSymplecticFlow`, `ErgodicTopologicalWinding`, `CategoryTheoreticFunctor`)
- `euclid/cognition/emergence_metrics.py` (empirical IIT $\Phi$ and bipartition Minimum Information Partition)

---

## 2. Live Telemetry Endpoints & Prometheus Scraping

### 2.1 HTTP JSON Endpoints
- **EUCLID Cognition & Strange Loop Status**:
  ```powershell
  Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/intelligence/cognition/status"
  ```
- **Unified Ops Telemetry (Pool, Job, Execution, Healing, Security, History)**:
  ```powershell
  Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/telemetry/ops"
  ```
- **Prometheus Metrics**:
  ```powershell
  Invoke-RestMethod -Uri "http://127.0.0.1:8000/metrics"
  ```

### 2.2 Prometheus Metrics Reference

| Metric Name | Type | Normal Operating Range | Description |
| :--- | :--- | :--- | :--- |
| `pythia_consciousness_phi` | Gauge | `0.4000 – 1.0000` | Integrated Information ($\Phi$) across the 4 cognitive layers (`security`, `mining`, `consciousness`, `memory`). |
| `pythia_cognitive_irreducibility` | Gauge | `0.3000 – 0.9500` | Measured degradation impact across coupled layers under counterfactual perturbation (baseline target $\ge 0.3000$, nominal $0.5625$). |
| `pythia_strange_loop_depth` | Counter/Gauge | `>= 3` (nominal `2022`) | Cumulative second-order recursion depth $d$. Strange loop activates at $d \ge 3$. |
| `pythia_penrose_or_events_total` | Counter | Monotonic integer | Cumulative count of discrete Objective Reduction events where $\Delta E \cdot \Delta t \ge \hbar / 2$. |

---

## 3. Interpreting Self-Model Narrative Verdicts

The substrate continuously updates its internal self-model narrative (`status()["narrative"]`) based on three state variables: `strange_loop_active`, `phi` ($\Phi$), `irreducibility`, and `meta_error`:

1. **`STRANGE_LOOP_VIRTUOUS_CYCLE_PHI_ASCENDING`** *(Nominal Target State)*
   - **Condition**: `strange_loop_active == True`, $\Phi \ge 0.40$, and $\text{irreducibility} \ge 0.30$.
   - **Action**: None required. Second-order meta-learning and cross-layer XOR entanglement are operating in a stable virtuous cycle.

2. **`COGNITIVE_ACCELERATION_ACTIVE`** *(Transitional Warm-up State)*
   - **Condition**: `strange_loop_active == True` ($d \ge 3$), while $\Phi$ or irreducibility are still climbing toward their thresholds.
   - **Action**: Normal during the first 3–10 evolution steps after a cold start. Monitor `pythia_consciousness_phi` to confirm monotonic ascent.

3. **`META_LEARNING_DIVERGENCE_INITIATING_GEOMETRIC_REFOLD`** *(High Meta-Error Refold)*
   - **Condition**: `meta_error > 0.40`.
   - **Mechanism**: The substrate automatically shifts its operational manifold from `euclidean` to `hyperbolic` (exponential negative curvature for rapid basin escape) or `spherical` (`0.15 < meta_error <= 0.40` for bounded positive-curvature stabilization).
   - **Action**: Verify upstream Stratum job stability and check `/api/v1/telemetry/ops` for sudden difficulty/job resets or Salamander fault injections.

4. **`RECURSIVE_LEARNING_CONVERGING`** *(Early Initialization)*
   - **Condition**: $d < 3$ and `meta_error <= 0.40`.
   - **Action**: Wait for at least 3 evolution cycles.

---

## 4. Verification & Diagnostic Commands

To run the full Strange Loop, Theoretical Foundations, and EUCLID v17 verification suite locally on Windows without OneDrive pytest cache contention:

```powershell
python -m pytest tests/test_recursive_self_learning.py tests/test_theoretical_foundations_unit.py tests/test_theoretical_foundations_properties.py tests/test_idempotency_scoped.py tests/test_task_verification.py tests/test_emergence_metrics.py tests/test_euclid_v17_runtime.py tests/test_euclid_v17_production_integration.py -q -p no:cacheprovider --basetemp=C:/PythiaTemp/runbook_check
```

To verify zero broken imports across the entire repository (~1,200 tracked Python modules):

```powershell
python -c "import scripts.import_audit as ia; raise SystemExit(ia.main([]))"
```
