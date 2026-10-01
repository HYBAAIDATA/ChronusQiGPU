# PYTHAGORAS: Meta-Evolutionary Code Intelligence Platform (v12.2)
## Embedded Computational Payload & Host Integration Façade

Drop-in engine for the **HYBA / PYTHIPhi** platform. Mounted via `PythagorasEngineAdapter`;
no host framework, database or deployment dependencies (stdlib + numpy).

v12.2 keeps the v12.0 façade API and the v12.1 computational model. It closes the
remaining roadmap gaps without changing the default greedy search semantics.

### v12.2 roadmap gap closures

- **Source safety:** shebang/PEP 263/`__future__`-safe module preambles and
  encoding-aware repository round trips.
- **Diagnostics:** `python -m pythagoras.core.diagnostics FILE --metric v12_1 --json`.
- **Search escape:** optional deterministic simulated annealing via `AnnealingConfig`.
- **Geometry:** selectable measured-φ or surrogate-velocity triggers plus bounded
  cross-file collective geometry.
- **Experiment rigour:** evaluation-normalized and rolling-window A/B measures.
- **Provenance:** hash-chained primitive registration/reuse events.
- **Adversarial learning:** generated non-executable anti-primitive models.
- **Multi-session memory:** persisted surrogate, anti-primitive, and collective-geometry state.

Git-lock recovery is intentionally superseded: repository integration operates on a private
copy and emits a patch, so it does not acquire the host repository's Git index lock.

---

### Ontology → implementation

| Component | Definition | v12.1 implementation |
|---|---|---|
| φ-resonance | Golden-ratio structural coherence of the AST | Computed on the *effective* AST (`core/structure.py`). Golden growth term = level-to-level AST growth vs `1/target_phi`. Integrity factor `(1 − redundancy)^φ` penalises dead, shadowed, repeated and unreferenced code. Weights in `PHI_WEIGHTS`. |
| EUCLID | `Intelligence = L_n · 20^(φ·t_p)` | Lucas index from the effective AST. `t_p` is host-supplied and identical for before/after comparisons. Adds `lucas_lock` (Pisot proximity). |
| Pisot property | φ is Pisot, so `L_n = round(φ^n)` | Checked in the Lucas invariant and unit tests. |
| AL HARAS | Security guard | Static audit (9 rules, AH001–AH009) + isolated `python -I` execution with timeout and rlimits. Import-time findings block execution. |
| SALAMANDER | Self-healer | Runs the V6.5 engine; `HEAL:dead_code_elimination` removes dead / shadowed / repeated code. |
| PYTHIA | Search oracle | Surrogate ranking of applicable operators, with RMSE. |
| CGP-inspired geometry | Search controls, not a DAG population | `n_cols` = ranked operators evaluated per generation; `levels_back` = maximum composite-recipe length. |
| Primitive discovery | Emergent operators | Composites (recipes) of consecutive winning operators; promoted on real φ gain; persisted as recipes and restored exactly. |
| Tononi substrate | Integration | `graph_integration()`: λ₂/n of the module's reference graph (IIT-inspired proxy, not Φ). Penrose term left unwired. |
| 11D manifold | Dodecahedron–icosahedron dual overlay | 11 measured axes (`STATE_AXES`); dual coherence measured against the real 12 icosahedral / 20 dodecahedral φ-vertices. |

### Operators (all real source transforms; comments and formatting preserved)

Behaviour-preserving: `ADD:AnnAssign` (inferred types only), `NON_LOCAL:function_split_refactor`
(golden-section extract-method, one division per function), `NON_LOCAL:conditional_flattening`,
`MUTATE:list_comprehension`, `HEAL:dead_code_elimination`, `MUTATE:inject_docstring` (φ-neutral).
Behaviour-changing (enabled only with a host test runner): `MUTATE:swap_binary_operator`,
`MUTATE:rename_variable`. Inert: `NON_LOCAL:class_decomposition`.

---

### Façade API (v12.0 signatures preserved; new keys/params are additive)

```python
from pythagoras import PythagorasEngineAdapter

adapter = PythagorasEngineAdapter(target_phi=0.618034, persistent_repo_path="primitives.json",
                                  euclid_gate=True)            # sandbox_config=SandboxConfig(...)

analysis = adapter.analyze("file.py", code, topological_time=1.0)
result   = adapter.evolve("file.py", code, generations=20, seed=42,
                          external_test_runner=None,         # host callable(code)->bool
                          topological_time=0.0)
result["final_code"]                                          # also "final_code_sample" (v12.0 key)
inv      = adapter.verify_property_invariants(orig, mutated, external_test_runner=None)
adapter.commit_primitive("HOST:AnnotateThenHeal", "ADD:AnnAssign + HEAL:dead_code_elimination")
session  = adapter.orchestrate([{"name": "file.py", "code_str": code}])
snapshot = adapter.snapshot()
```

Optional search escape and geometry controls:

```python
from pythagoras.engine.v6_5_manifold_escape import AnnealingConfig

adapter = PythagorasEngineAdapter(
    persistent_repo_path="pythagoras-state.json",
    annealing=AnnealingConfig(enabled=True, initial_temperature=0.02),
    geometry_signal="surrogate_velocity",
)
```

**EUCLID co-gate (`euclid_gate=True`).** A step is accepted only if φ rises and EUCLID
intelligence does not fall, so the monotonicity invariant holds for every accepted step.
Note: EUCLID's Lucas parameter grows with depth and node count, while φ's depth term peaks
at 8, so some φ-raising simplifications (e.g. conditional flattening) are rejected by the gate.

**Runtime validity.** Without a host test runner, `runtime_valid` means the module executes
cleanly in isolation; it does not prove behaviour is unchanged. Supply `external_test_runner`
for behavioural guarantees. For hard network isolation, run the host in a container without egress.

**ROI.** Monetary fields are `None` unless the host passes `hours_saved_per_phi_point` and `hourly_rate`.

---

### Running inside a host repository

```bash
python3 -m pythagoras.integration.repo_runner /path/to/repo --generations 10 \
        --test-cmd "python -m pytest -x -q tests/"      # default: pytest if installed, else unittest
```
The host's own test suite is the behaviour gate: baseline must pass; every candidate is tested in a
private copy (with a timeout); the integrated tree is tested once more. Output in
`pythagoras_integration/`: `report.md`, `report.json` (A meta-off vs B meta-on per file) and
`pythagoras.patch` for review (`git apply`). The repository is untouched unless `--apply` is given.
Behaviour-changing operators stay off unless `--allow-behaviour-changing`.

---

### Replicating the 21 March 2026 A/B experiment

```bash
python3 -m pythagoras.experiments.replicate_march_2026 --corpus stdlib4 --seeds 3 --generations 4
```
`meta_evolution=False` on the engine gives Condition A; the harness adds a budget-matched Condition C,
ENH-09 phase-transition / barrier-crossing tags and the ENH-02 sensitivity diagnostic
(`core/diagnostics.py`). Findings: `experiments/RESULTS_2026-10-01.md`.

---

### Verification
```bash
python3 run_pythagoras.py
python3 -m unittest discover -s pythagoras/tests -t .   # from the directory containing pythagoras/
```
