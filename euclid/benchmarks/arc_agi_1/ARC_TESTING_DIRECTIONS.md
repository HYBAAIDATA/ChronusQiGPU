# ARC-AGI-1 Testing Architecture & Evaluation Directions

> **MANDATORY DIRECTIVE FOR ALL AUTONOMOUS AGENTS AND HUMAN COLLABORATORS:**  
> This document establishes the canonical testing discipline, mathematical invariants, and governance protocol for evaluating EUCLID on the **ARC-AGI-1 (Abstraction and Reasoning Corpus)** benchmark.
> Prior to making code or test modifications, confirm alignment with [`AGENTS.md`](../../../AGENTS.md), [`OWNER_DECLARATIONS.md`](../../../OWNER_DECLARATIONS.md), and [`adapter_contract.md`](./adapter_contract.md).

---

## 1. Foundational Axioms & Substrate Agnosticism

1. **Substrate Independence**: ARC-AGI-1 evaluates mathematical abstraction, spatial geometry, and rule induction. As established in `AGENTS.md` (Section 1), computation is an abstract trajectory over algebraic structures. Silicon hardware, memory constraints, and process scheduling are incidental representation channels.
2. **Emergence via Pure Native Representation**:
   - Zero hardcoded task lookup tables.
   - Zero ARC-specific cheat rules or heuristic shortcuts.
   - Zero separate ad-hoc search engines or fallbacks.
   - Solvers must operate exclusively through EUCLID's native cognitive architecture: `TaskSpec`, `ArcDemonstrationWorld`, `PhiResonanceCalculator`, `ProgramSearchEngine`, and `IntegratedAgent`.

---

## 2. The Seven Pillars of ARC Evaluation Discipline

```
                         THE SEVEN PILLARS OF ARC EVALUATION
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ 1. Zero Answer Leakage    │ Test outputs strictly scorer-only               │
 │ 2. Dihedral Symmetry (D4) │ Invariant color histograms & algebraic groups    │
 │ 3. Metric Truth (N=400)   │ Denominator is ALWAYS all tasks in split        │
 │ 4. Two-Attempt Protocol   │ Strict solve requires all test inputs matched   │
 │ 5. Worker Memory Recycled │ Fresh runtime / gc.collect() prevents OOM       │
 │ 6. Hard Wall-Clock Bounds │ Subprocess timeout prevents runaway tasks       │
 │ 7. Canonical EUCLID Logic │ Hypotheses logged to ledger, no solver cheats   │
 └─────────────────────────────────────────────────────────────────────────────┘
```

### Pillar I: Strict Zero-Answer Leakage & Immutability
- **Withheld Test Outputs**: The test output grids are reserved strictly for the independent local scorer (`score_arc.py`) or official evaluators.
- **Envelope Hygiene**: `load_public_task()` and `public_task()` filter out any `"output"` field inside `"test"` objects. If any unstripped test output is passed into `run_task()`, it fails closed immediately with `ValueError`.
- **Deepcopy Isolation**: All structures passed into `ArcDemonstrationWorld` or returned by `public_task()` are deep-copied. Mutating an input structure post-creation cannot taint world execution or test targets.

### Pillar II: Dihedral Symmetry ($D_4$) & Klein-4 Invariant Groups
- ARC grids inhabit the discrete Dihedral group $D_4$ of square transformations (order 8):
  $$\mathcal{D}_4 = \langle r, s \mid r^4 = 1, s^2 = 1, s r s = r^{-1} \rangle$$
- **Rotations ($C_4$)**:
  $$R_{90}^4 = I, \quad R_{180} = R_{90}^2, \quad R_{270} = R_{90}^3, \quad R_{90} \circ R_{270} = I$$
- **Klein-4 Involutions ($V_4$)**:
  $$H^2 = I, \quad V^2 = I, \quad \text{Transpose}^2 = I, \quad H \circ V = V \circ H = R_{180}$$
- **Dihedral Commutation**:
  $$H \circ R_{90} \circ H = R_{270}, \quad V \circ R_{90} \circ V = R_{270}$$
- **Conservation Law**: The multi-set color frequency histogram $\mathcal{C}(g) = \{c \mapsto \sum_{ij} \mathbb{I}[g_{ij}=c]\}$ is an exact invariant under all 8 transformations of $\mathcal{D}_4$.
- **Dimension Transformation**:
  $$\dim(R_{90}(g)) = \dim(R_{270}(g)) = \dim(\text{Transpose}(g)) = (W, H)$$
  $$\dim(R_{180}(g)) = \dim(H(g)) = \dim(V(g)) = (H, W)$$

### Pillar III: Metric Truth & ARC Prize Official Denominator ($N=400$)
- **Fixed Denominator**: ARC-AGI-1 contains 400 training tasks and 400 evaluation tasks.
- **The Denominator Invariant**:
  $$\text{ARC Prize Score} = \frac{1}{N} \sum_{i=1}^{N} \text{Fraction}(T_i), \quad N = 400$$
  $$\text{Strict Task Accuracy} = \frac{1}{N} \sum_{i=1}^{N} \mathbb{I}[\text{All Test Inputs Solved}(T_i)], \quad N = 400$$
- **Anti-Subset Fallacy**: Under no circumstances may an attempted subset (e.g. 15 tasks out of 20) be normalized as the full score. Tasks unattempted, timed out, or returning no candidate count as $0.0$ against the full denominator $N=400$.

### Pillar IV: Two Attempts & Strict Multi-Test-Input Protocol
- **Two Attempts Policy**: For each test input, the agent provides `attempt_1` and `attempt_2`. If either matches exactly, that test input is counted as solved.
- **Multi-Test-Input Tasks**: Certain ARC tasks have 2 or 3 test inputs.
  - Partial solve (e.g. 1 of 2 inputs matched) contributes $0.5$ point to `arc_prize_score`.
  - But `strict_tasks_solved` remains $0$! Strict task accuracy requires element-for-element exact match across **all** test inputs of that task.

### Pillar V: Worker Memory Isolation & Garbage Collection Discipline
- Sequential task processing inside a single process can cause cognitive graphs, MCTS search trees, and experience buffers to accumulate in RAM, triggering `MemoryError` in low-memory environments.
- **Remediation**:
  - `fresh_runtime` mode (default): Instantiates a distinct `EuclidRuntime` per task with an ephemeral state directory, invoking `runtime.close()`, explicit reference deletion, and `gc.collect()`.
  - `subprocess` mode: Runs each task in an independent OS worker process.

### Pillar VI: Hard Wall-Clock Subprocess Boundaries
- Post-hoc checks (evaluating `elapsed > budget.wall_clock_seconds` after `solve_task()` finishes) fail to prevent deep loops from hanging execution (e.g. 2,784 seconds on task `11852cab`).
- **Remediation**:
  - Subprocess worker execution enforced with `subprocess.run(..., timeout=budget.wall_clock_seconds)`.
  - If a worker exceeds the budget, the operating system terminates the process immediately. The runner marks status as `"timeout"`, records elapsed time, and advances cleanly to the next task.

### Pillar VII: Canonical EUCLID Hypothesis Logging
- Every action taken by the agent must be recorded in `ArcDemonstrationWorld.ledger`.
- Programmes are ordered and ranked by `goal_met`, `kind == 'submission'`, and `score`.
- Predictions are generated by applying the top ranked programmes to the withheld test inputs:
  $$\text{Program} \times \text{Test Input} \longrightarrow \text{Candidate Output Grid}$$

---

## 3. Test Suite Organization

The test suite in [`tests/test_arc_euclid_adapter.py`](../../../tests/test_arc_euclid_adapter.py) covers 15 critical invariants:

| Test Name | Focus Area | Verification Criteria |
| :--- | :--- | :--- |
| `test_encode_grid_to_features` | Core Representation | Feature extraction, dimensions, phi resonance |
| `test_features_to_grid` | Feature Synthesis | Deterministic grid regeneration from features |
| `test_grid_primitives` | Primitive Transforms | Basic rotation and reflection operations |
| `test_fitted_primitives` | Parameter Fitting | Color mapping and constant fitting from demonstrations |
| `test_answer_isolation_public_task` | Answer Isolation | Public envelope strips test output grids |
| `test_arc_demonstration_world_budgets` | Resource Governance | Probe and submission budget enforcement |
| `test_scorer_with_perfect_and_wrong_submissions` | Scorer Truth | Verification of local scorer against reference grids |
| `test_dihedral_group_d4_algebraic_laws` | Geometric Symmetries | $D_4$ group relations, Klein-4, color conservation |
| `test_primitive_invariants_and_boundaries` | Invertibility & Physics | Downscale/scale2 roundtrip, bbox, gravity, fill |
| `test_strict_zero_answer_leakage_and_immutability` | Air-Gapped Boundary | Deepcopy independence, goal isolation, fail-closed |
| `test_multi_test_input_scoring_and_official_denominator` | Official Scoring | Multi-input strict vs fractional, $N=400$ denominator |
| `test_submission_schema_and_grid_error_validation` | Format Conformance | 1..30 bounds, 0..9 ints, rectangular syntax |
| `test_hard_wall_clock_timeout_enforcement` | Deadline Discipline | Clean timeout handling under tight deadlines |
| `test_worker_isolation_and_memory_discipline` | Memory Recycled | Fresh runtime instantiation & GC validation |
| `test_e2e_real_arc_task_pipeline` | Real Task Pipeline | Real ARC task execution and submission scoring |

---

## 4. Benchmark Execution Commands

### 1. Unit & Property Verification
```bash
python -m pytest tests/test_arc_euclid_adapter.py -v
```

### 2. Output Validator & Dataset Integrity Checks
```bash
python euclid/benchmarks/arc_agi_1/test_output_validation.py
python euclid/benchmarks/arc_agi_1/verify_dataset.py
```

### 3. Running Calibration on Training Split
```bash
# Run 10 training tasks with fresh runtime isolation and 60s per-task budget
python euclid/benchmarks/arc_agi_1/euclid_arc_runner.py --split training --limit 10 --worker-isolation fresh_runtime --wall-clock-seconds 60.0
```

### 4. Running with Subprocess Isolation (Hard OS Deadline)
```bash
python euclid/benchmarks/arc_agi_1/euclid_arc_runner.py --split training --limit 5 --worker-isolation subprocess --wall-clock-seconds 30.0
```

### 5. Scoring a Run Directory
```bash
python euclid/benchmarks/arc_agi_1/score_arc.py --split training --submission runs/<run_name>/submission.json
```

---

## 5. Official Submission & Air-Gapped Boundary

1. **Air-Gapped Disclosure Boundary**:
   - The ARC adapter, world, primitives, and runner are self-contained in `euclid/benchmarks/arc_agi_1/`.
   - **Zero Proprietary Treasury/Mining Leakage**: Under no circumstances should ASIC designs, Lucas mining attractors, Cassini oval hash pipelines, or confidential trading logic be imported into or packaged with ARC evaluation submissions.
2. **External Routes**:
   - **Local Private Benchmarking**: Evaluate on the training and evaluation splits locally. Record exact git commits, seeds, and execution logs.
   - **ARC Prize Official Evaluation / Kaggle**: When entering the leaderboard, build a dedicated, stripped submission package that includes only the benchmark adapter and the required EUCLID reasoning core, strictly compliant with competition rules.
