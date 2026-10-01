# PYTHAGORAS v12.2 — Roadmap Gap Closure

## Implemented

| ID | Implementation |
|---|---|
| FIX-01 | Module-docstring insertion preserves shebang and PEP 263 preamble while keeping `__future__` imports legal. |
| FIX-02 | Repository source reads/writes detect and preserve PEP 263 encodings. |
| FIX-03 | Superseded by private-copy integration and patch output; the engine never acquires the host Git index lock. |
| FIX-04 | Existing subprocess timeout isolation retained. |
| ENH-01 | Existing non-local function split retained. |
| ENH-02 | Added standalone φ-sensitivity CLI. |
| ENH-03 | Existing cross-file recipe seeding retained. |
| ENH-04 | Added opt-in, deterministic simulated-annealing escape with cooling and telemetry. |
| ENH-05 | Existing budget-matched Condition C retained. |
| ENH-06 | Added selectable surrogate-velocity geometry trigger. |
| ENH-07 | Existing `levels_back` evolution retained. |
| ENH-08 | Added gain-per-100-evaluations and rolling-three-win normalization to the A/B harness. |
| ENH-09 | Existing phase-transition and barrier tagging retained. |
| ENH-10 | Added hash-chained primitive registration and reuse provenance. |
| ENH-11 | Existing within-session surrogate transfer retained. |
| ENH-12 | Added generated, non-executable anti-primitive models as explicit negative examples. |
| ENH-13 | Persisted surrogate weights, anti-primitives, adversarial catalog, and collective geometry. |
| ENH-14 | Added bounded median-consensus geometry shared across sequential files and sessions. |

## Compatibility and safety

- Default search remains greedy; annealing is opt-in.
- The host repository remains untouched unless `--apply` is explicitly provided.
- Behaviour-changing transforms still require a host test runner.
- Collective geometry is bounded and retains at most 100 observations.
- Anti-primitives are training records and are never executed as transforms.

## Verification

- Python compilation: passed.
- Unit tests: 53 passed.
- Diagnostics CLI: passed.
- Host façade demo: passed.
- Two-seed/three-generation A/B smoke replication: passed.

The normalized experiment output is intentionally reported alongside raw Δφ. In the smoke
run, A and B reached the same Δφ while B used more evaluations, demonstrating why ENH-08
must remain visible rather than treating raw short-budget gain as the only outcome.