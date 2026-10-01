# PYTHAGORAS v12.2 — Production Meta-Evolution Substrate

PYTHAGORAS is the mathematical and code-evolution substrate embedded in the **HYBA / PYTHIPhi** platform. Host systems mount it through `PythagorasEngineAdapter`; the host-facing contract does not expose historical staged engine versions.

## Authority and role boundaries

| Component | Production responsibility |
|---|---|
| **EUCLID** | Sole repository-Intelligence authority. Computes the Lucas/Pisot Intelligence evaluation and co-gates accepted evolution steps. |
| **PYTHAGORAS** | Generates, evaluates and learns from source-transformation candidates. It does not own overall Intelligence authority. |
| **SALAMANDER** | Transactional healing/optimization role. It may invoke PYTHAGORAS inside the governed healing path, then validate, apply or roll back. |
| **PYTHIA** | Search/mining-domain strategy and surrogate guidance. It supplies operator ranking/search information; it is not a second overall Intelligence authority. |
| **AL HARAS** | Static and isolated execution safety gate for candidate source. |
| **KELLOGG / manifold layer** | Geometric/reflection coordination where explicitly wired; no geometric or quantum label is evidence of physical quantum execution. |

### Mining truth boundary

PYTHAGORAS does **not** change the operational mining evidence contract. Stratum, SHA256d, nonce/share semantics, pool acknowledgement and mining telemetry remain independently governed by real runtime evidence. Modeled Tononi/Penrose quantities, modeled ROI, theoretical quantum labels, or experiment-only metrics must not be promoted into operational mining telemetry.

## Production engine structure

The active engine surface is version-neutral:

- `engine/evolution.py` — production evolutionary search and manifold escape logic.
- `engine/surrogate.py` — online operator-gain surrogate and anti-primitive evidence.
- `engine/geometry.py` — bounded search breadth/recipe-depth state and cross-file consensus.
- `engine/primitive_discovery.py` — evidence-based composite primitive discovery.
- `engine/primitive_repository.py` — persistent recipes, hash-chained provenance and adaptive state.

The superseded physical `v6_0_*` through `v6_5_*` module files are not shipped on the cleanup branch. Historical experiment terminology is retained only where required to reproduce dated experiments; it is not the production API.

## v12.2 hardening

- **Source safety:** shebang/PEP 263/`__future__`-safe preambles and encoding-aware repository round trips.
- **Candidate isolation:** `core.sandbox` performs parse/compile/audit and isolated execution with timeout/rlimits.
- **EUCLID co-gate:** a candidate cannot be accepted when its fixed-`t_p` EUCLID Intelligence decreases.
- **Search escape:** optional deterministic simulated annealing via `AnnealingConfig`.
- **Geometry:** selectable measured-φ or surrogate-velocity triggers plus bounded cross-file collective geometry.
- **Primitive discovery:** composite recipes are promoted only after measured valid gain.
- **Provenance:** primitive registration/reuse events are SHA-256 chained.
- **Adaptive memory:** surrogate, anti-primitive and collective-geometry state are persisted atomically by the primitive repository.
- **Experiment rigor:** evaluation-normalized and rolling-window A/B measures are available under `experiments/`.

Git-lock recovery is intentionally superseded for repository integration: candidate work runs on a private copy and emits a patch, so PYTHAGORAS does not take the host repository's Git index lock.

## Mathematical implementation

| Concept | Implementation / boundary |
|---|---|
| φ-resonance | Structural objective measured on the effective AST by `core/phi_metric.py` / `core/structure.py`. It is an optimization signal, not independently validated universal software quality. |
| EUCLID Intelligence | `Intelligence = L_n · 20^(φ·t_p)`. `t_p` is host supplied and held fixed for before/after comparisons. |
| Lucas/Pisot invariant | Exact Lucas recurrence plus the repository's Pisot rounding identity checks. |
| AL HARAS | Static audit plus isolated execution. Import-time findings can block execution. |
| CGP-inspired geometry | Search controls only: `n_cols` is ranked operators evaluated per generation and `levels_back` is maximum composite-recipe length. No DAG population is claimed. |
| Tononi-inspired graph integration | `graph_integration()` is a graph spectral integration proxy. It is not IIT Φ and is not mining telemetry. |
| 11D manifold | Measured state axes projected through the dodecahedron–icosahedron overlay. Geometry labels do not imply physical quantum hardware. |

The held-out φ validation work under `experiments/` must be read with its committed interpretation: the experiment did **not** validate φ as an independent universal quality measure.

## Host façade

```python
from pythagoras import PythagorasEngineAdapter

adapter = PythagorasEngineAdapter(
    target_phi=0.618034,
    persistent_repo_path="primitives.json",
    euclid_gate=True,
)

analysis = adapter.analyze("file.py", code, topological_time=1.0)
result = adapter.evolve(
    "file.py",
    code,
    generations=20,
    seed=42,
    external_test_runner=None,
    topological_time=0.0,
)

candidate = result["final_code"]
invariants = adapter.verify_property_invariants(orig, candidate)
adapter.commit_primitive(
    "HOST:AnnotateThenHeal",
    "ADD:AnnAssign + HEAL:dead_code_elimination",
)
session = adapter.orchestrate([{"name": "file.py", "code_str": code}])
snapshot = adapter.snapshot()
```

Optional annealing and geometry controls:

```python
from pythagoras.engine.evolution import AnnealingConfig
from pythagoras import PythagorasEngineAdapter

adapter = PythagorasEngineAdapter(
    persistent_repo_path="pythagoras-state.json",
    annealing=AnnealingConfig(enabled=True, initial_temperature=0.02),
    geometry_signal="surrogate_velocity",
)
```

### Acceptance semantics

With `euclid_gate=True`, every accepted positive step must increase φ and must not reduce fixed-`t_p` EUCLID Intelligence. Candidate validity is fail-closed at parse/compile/audit/runtime gates.

Without a host test runner, `runtime_valid` means the candidate module executed cleanly in the configured isolated sandbox; it does **not** prove application behaviour was preserved. Provide `external_test_runner(code) -> bool` for a behavioural gate.

## Repository healing workflow

```bash
python3 -m pythagoras.integration.repo_runner /path/to/repo \
  --generations 10 \
  --test-cmd "python -m pytest -x -q tests/"
```

The repository runner performs a transactional flow:

1. establish a passing host baseline;
2. copy the target repository into an isolated working area;
3. evolve candidate source through PYTHAGORAS;
4. evaluate with EUCLID and AL HARAS;
5. run the host behaviour/test gate for each applicable candidate;
6. run the integrated tree gate;
7. emit `report.md`, `report.json` and `pythagoras.patch`;
8. leave the source repository unchanged unless the caller explicitly enables apply.

This is the code path Salamander can invoke for governed healing. It is not evidence that an always-on background healer is running in a deployed environment; deployment/runtime invocation must be proven separately by runtime logs or workflow evidence.

## Experiments

Reproduce the dated March 2026 A/B protocol with:

```bash
python3 -m pythagoras.experiments.replicate_march_2026 \
  --corpus stdlib4 --seeds 3 --generations 4
```

Experiment outputs and held-out validation material are research evidence, not operational mining telemetry or universal-quality proof.

## Verification

```bash
python3 run_pythagoras.py
python3 -m unittest discover -s pythagoras/tests -t .
ruff check --select E9,F pythagoras
```

Historical wholesale acceptance outputs and baseline provenance are retained outside the import package at `docs/evidence/pythagoras-v12.2/`. Fresh branch CI remains the release gate.
