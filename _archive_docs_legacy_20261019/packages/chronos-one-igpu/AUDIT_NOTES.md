# Chronos GPU -- Audit & Fix Notes (3 Aug 2026)

This package was independently audited against the pasted "Enhanced Chronos
Pseudocode" and against this workspace's real, executed HYBA infrastructure.
Full audit write-up: see the Notion page "Chronos GPU -- Independent Audit:
Shipped Code vs. Pasted Pseudocode".

## Scope of this fix pass

This fix pass completes the **quantum-from-maths / M32 manifold** reframe
that this codebase actually implements. It does **not** implement the pasted
"Enhanced Chronos Pseudocode" (physical cryogenic version: 1,000,000
resonators @ 15 mK, weak measurement, EMP, cryogenic control, QX API). That
is a structurally different architecture; none of this code is reusable for
it. If that is the version you want built, it needs to start from the
physics/engineering spec on its own page, not from this repository.

## What was fixed

| # | Defect (as found) | Fix |
|---|---|---|
| 1 | `qsd l_source` typo -> hard `SyntaxError`, pipeline could not import | Fixed in the single real implementation (`src/chronos/qsdl_compiler.py`) |
| 2 | `HamiltonianLibrary` used unseeded global `np.random` -> non-deterministic energy every run (-1.06 / -1.17 / -1.14 across 3 test runs) | Face geometry and material/resonance terms are now deterministic functions of scene input (`src/chronos/manifold.py`, `src/chronos/hamiltonian.py`) |
| 3 | `EvolutionEngine.evolve` returned an unrelated random unit vector ("# Synthetic final state for now") -- never touched the Hamiltonian | Now computes the **exact** ground state via dense eigendecomposition of the real Hamiltonian (`src/chronos/evolution_engine.py`) |
| 4 | `src/chronos/engine.py` hardcoded `energy = 0.123456`, matching a Notion "smoke test" result that could not otherwise be reproduced | `ChronosEngine.render()` now runs the real pipeline end-to-end and returns the computed energy |
| 5 | `ReconstructionEngine.reconstruct` broadcast one scalar to the whole 8K frame (flat color swatch) | Now ray-traces a real pinhole camera against the scene sphere and shades hit points using the nearest manifold face's real amplitude (`src/chronos/reconstruction.py`) |
| 6 | `fold_ratio: 11.5` was a hardcoded literal, contradicted by this workspace's own real `TensorTrainState.audit()` result (0.44x) at the same scale | Replaced with an honestly computed `raster_compression_ratio` (state bytes vs. dense frame bytes); not described as quantum/tensor compression |
| 7 | Two divergent, duplicate implementations existed (top-level `*.py` scripts vs. `src/chronos/*`), neither matching the other | Consolidated into one real implementation in `src/chronos/`; the top-level files are now thin compatibility shims that import from it |
| 8 | `README.md` quickstart used `result.energy` but `render()` returned a plain dict (`AttributeError` if actually run) | `render()` now returns a real object with an `.energy` attribute |
| 9 | `test_harness.py` always printed "passed" and returned `True` regardless of any actual behavior | Now runs the real pipeline twice and asserts determinism, frame shape, normalization, and non-flat output |
| 10 | First real-Hamiltonian draft computed a mixer/adjacency term but silently discarded it, so the Hamiltonian was purely diagonal and its exact ground state trivially collapsed onto a single manifold face (uniform, flat-looking render even after fix #2/#3) | `HamiltonianLibrary.build()` now actually adds the mixer into `total_hamiltonian` |
| 11 | The manifold adjacency graph used an arbitrary strict 35-degree angular threshold, producing a sparse, disconnected graph (average degree 1). The Hamiltonian's ground state localized entirely onto one small graph component, which happened to sit on the sphere hemisphere facing away from the camera -- still an effectively flat render from the camera's point of view even though the underlying state was no longer literally a single basis vector | `M32Manifold` now uses the same 0.70 cosine-similarity threshold as this workspace's real `build_spectral_adjacency`, giving a connected graph and a ground state spread across faces on both hemispheres |
| 12 | The renderer used the raw Hamiltonian ground-state energy (frequently negative) directly as pixel "intensity"; tone-mapping clips negative brightness to 0, so every rendered pixel silently clipped to black -- the last and root cause of the persistent "flat render" symptom, only found by directly inspecting per-pixel shade values | `EvolutionEngine` now reports `energy` (real eigenvalue, can be negative) and `intensity` (neutral non-negative exposure baseline) as separate fields; per-pixel brightness comes from the always-non-negative per-face probability distribution |
| 13 | `ReconstructionEngine` computed ray-sphere normals for every pixel in a row, including rays that missed the sphere (`t = +inf`), which produced `RuntimeWarning: invalid value encountered in matmul` (harmless since results were masked, but noisy/sloppy) | Normals are now only computed for rays that actually hit the sphere |

All of the above were confirmed by actually running `chronos_gpu_demo.py` and
`python3 -m chronos.test_harness` repeatedly during this fix pass, not by
inspection alone. Final verified state: energy is bit-identical across
repeated renders (deterministic), the rendered frame has 20 distinct pixel
values (not a flat fill), `rendered_pixels_hit < total_pixels` (a real
silhouette exists), and no runtime warnings are emitted.

## Revision 3 (4 Aug 2026): production pass -- closing out the list below

Following an explicit instruction to "complete all the missing pieces
validated by the audit and make production ready", each item in the original
"still NOT real" list was revisited:

- **M32 manifold geometry** -- FIXED. `src/chronos/manifold.py` now builds a
  real icosahedron + dual-dodecahedron composition via the golden ratio
  (matching the workspace's own `build_m32()` doctrine), replacing the
  Fibonacci-sphere placeholder. This changed the demo scene's deterministic
  ground-state energy from `-6.064956` to `-7.337994` (20 -> 19 distinct
  pixel values) -- a real physical consequence of the corrected geometry,
  confirmed by rerunning `chronos.test_harness` (still 7/7 PASS) and
  `chronos_gpu_demo.py` after the change.
- **`QSDLCompiler.compile()` ignoring its `qsdl_source` argument** -- FIXED.
  `src/chronos/qsdl_parser.py` is a real tokenizer + recursive-descent parser
  implementing the full published QSDL v1.0 BNF grammar (scenes, objects,
  geometry, materials incl. nested `quantum {}` blocks, lights, cameras incl.
  `readout = {}`, quality blocks, matrix-expression transforms). `
  src/chronos/qsdl_compiler.py` v3.0 now really parses and compiles genuine
  `scene NAME { ... }` source into a `QScene`; only unrecognized/legacy
  labels (not real QSDL) fall back to the fixed canonical demo scene, and
  that fallback is now clearly documented rather than being the only path.
- **`QAOAOptimizer` / `FisherNaturalGradientTrainer` / `TensorTrainState` not
  imported or used** -- left as an intentional scope decision, not a defect.
  The exact-diagonalization approach used throughout this codebase is a
  different, simpler, and exact method appropriate to these manifold sizes
  (tens to low thousands of faces, confirmed tractable up to n_faces=1364 in
  `BENCHMARKS.md`); the workspace's own `TensorTrainState` MPS machinery
  *is* used elsewhere in this codebase where it is the right tool (the real
  1000-qubit compression demo in `src/chronos/academic/tensor_compression.py`,
  see `ACADEMIC_AUDIT.md` Revision 2), but grafting it onto this exact-solve
  pipeline would not add real capability here.
- **"8K / infinite resolution" claims** -- unchanged, and this is an
  inherent, honest limit rather than a bug: rendered detail is fundamentally
  bounded by manifold face count, not pixel count. `BENCHMARKS.md` reports
  the real face counts tested (up to a projected 15,127 faces via the
  phi-power scaling benchmark).
- **No physical hardware / cryogenics / measurement backaction** --
  unchanged by design. This codebase implements the "quantum comes from
  maths, substrate-agnostic" reframe; the physical cryogenic architecture is
  a structurally different project (see "Scope of this fix pass" above).

All fixes in this revision were verified by actually re-running, not just
inspecting: `chronos.test_harness` (7/7 PASS), all 10 `theory/` module
self-tests, `qsdl_parser`/`qsdl_compiler` self-tests, `chronos.academic
.run_academic_enhancements()` end-to-end, `chronos_gpu_demo.py`, the
phi-power-scaling benchmark, and the new `benchmarks/run_benchmarks.py`
suite -- see `BENCHMARKS.md` for every measured number.

## What is still honestly out of scope (not defects, by design)

- `QAOAOptimizer` / `FisherNaturalGradientTrainer` / `TensorTrainState` are
  not wired into this exact-diagonalization pipeline (see Revision 3 above).
- "8K / infinite resolution" rendering is bounded by manifold face count,
  not pixel count -- this is inherent to the maths-only reframe.
- No physical hardware, cryogenics, or measurement backaction of any kind is
  modeled anywhere in this codebase (expected for the maths-only reframe; a
  hard blocker only if the physical pseudocode variant is what's wanted).
