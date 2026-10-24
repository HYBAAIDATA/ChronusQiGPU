# ARC-AGI-1 Adapter Contract for EUCLID

**Purpose**: Minimum representation adapter converting between ARC grid format and EUCLID's native TaskSpec interface, using only EUCLID's native capabilities (no hand-written ARC solution rules, separate search engine, or fallback solver).

## 1. Data Encoding/Decoding

### 1.1 Grid to EUCLID Representation
- ARC grids (list of lists of integers) are encoded as deterministic feature vectors
- Encoding uses EUCLID's `PhiResonanceCalculator` and `LucasSequenceCalculator` from `euclid.core`
- No semantic content from output grids is revealed; only structural features from input grids are extracted
- Encoding is many-to-one by design — multiple grid configurations may produce identical feature vectors

### 1.2 EUCLID Representation to Grid
- Candidate programmes output feature vectors or symbolic descriptions
- Decoder converts feature vectors back to grid format using deterministic rules
- Decoder does not contain ARC-specific pattern matching; it is a generic grid renderer

## 2. Native EUCLID Interfaces Used

### 2.1 ProgramSearchEngine (EuclidEngineAdapter)
- Executes MCTS/evolutionary search over primitive programmes
- Target phi parameter: `0.618033988749895` (golden ratio conjugate)
- Search modes: `mcts` (default) or `evolutionary`
- External test runner: adapter-provided validity gate (see Section 3)

### 2.2 IntegratedAgent (via compose_adaptive_intelligence)
- Constructed explicitly when ARC task processing is requested
- Uses AgentKnowledge, ablations, and runtime evidence chain
- Adaptive data port binding optional; without custody knowledge remains process-local

### 2.3 Experience Contract
- Each ARC task generates `Experience` objects recording:
  - Task ID and input identity
  - Generated candidate programmes
  - Outcome (valid/invalid, timeout, refusal)
  - Resource usage (time, compute)

## 3. Answer Isolation Protocol

### 3.1 Withheld Output Grids
- Test input grids are legitimate runtime inputs
- **Withheld test outputs are scorer-only** — never passed to adapter or EUCLID runtime
- Training example pairs (input/output) are legitimate runtime inputs
- Adapter receives: training input/output pairs + test **inputs only**
- Test **outputs** are stored separately and read only by independent scorer

### 3.2 Adapter Restrictions
- **Prohibited**: Hand-written ARC solution rules, task-specific answer lookup, separate search/induction engine, fallback solver
- **Permitted**: 
  - Grid encoding/decoding using EUCLID mathematical features
  - MCTS/evolutionary search over programme space
  - Deterministic programme execution and result conversion
  - Budget enforcement (probe/submission budgets)
  - Timeout and error recording

### 3.3 Leakage Prevention
- Adapter entry point receives: `{task_id, train_pairs, test_inputs}`
- Adapter never receives: test outputs
- All grid data containing correct output values is excluded from adapter accessible input
- SHA-256 verification of task file integrity enforced

## 4. Budget Enforcement

| Budget Type | Default Value | Description |
|---|---|---|
| Probe budget | 12 | Number of probe (partial information) queries |
| Submission budget | 3 | Number of final solution submissions |
| Max programme length | 16 | Maximum programme depth in search |
| Max probe length | 3 | Maximum steps in a probe programme |

Budgets are declared in the protocol and enforced by the WorldExecutor.

## 5. Timeout, Refusal, and Crash Treatment

- **Timeout**: If search exceeds budget or wall-clock limit (300s per task), record as `timeout` and terminate
- **Refusal**: If adapter cannot encode/decode grid, record as `refusal` and terminate
- **Crash**: If EUCLID search engine raises exception, record as `error` with traceback
- All outcomes are recorded in the adaptation ledger

## 6. Learning and Feedback Rules

- **Learning between tasks**: EUCLID adaptive knowledge may retain state across tasks (adaptive_custody must be explicitly attached)
- **Task order**: Preserved and documented; lineage tracked via Experience provenance
- **Reset**: Between training and evaluation splits, knowledge state is sealed/frozen
- **Adaptation log**: Every task generates an adaptation record; empty list is valid if no adaptations occurred

## 7. Scoring Rules

- **Exact-match**: Candidate grid must match the withheld test output grid element-for-element
- **Partial accuracy**: Not presented as "solved"; exact-match is the only reported outcome
- **Scoring denominator**: Number of tasks where a valid candidate was generated and submitted within budgets
- **Adaptation accounting**: Each run version is distinct; outcomes from different versions are not merged

## 8. Checkpoint/Resume Behaviour

- Checkpoint: Saved after each task including current search state, adaptive knowledge snapshot, and evidence chain
- Resume: From last checkpoint; duplicate-attempt prevention via experience_id deduplication
- Development vs frozen evaluation: Training split may adapt; evaluation split uses sealed starting state

## 9. External Tool and Model Permissions

- **Network access**: None required — all computation is local
- **Model providers**: EUCLID's internal engines (MCTS, evolutionary) only
- **External services**: None — fail closed on unavailable dependency

---

**Adapter Contract Version**: 1.0
**Generated**: 2026-10-23
**Protocol**: ARC-AGI-1 administration v1