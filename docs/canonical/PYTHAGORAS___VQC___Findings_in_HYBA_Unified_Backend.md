# PYTHAGORAS / VQC — Findings in HYBA_Unified_Backend

**Scope note:** this page covers only what was found in the HYBA_Unified_Backend zip. PYTHAGORAS also has quantum implementation inside HYBA_DATA that is separate from, and not present in, this repo — that side still needs its own survey pass and its own findings note.

## What's here

Quantum-shaped material found in the HYBA_Unified_Backend zip, routed here since PYTHAGORAS owns Quantum:

- `backend/quantum_core/*` — Grover search, quantum error correction, quantum RNG, dodecahedron partitioning, `pure_maths.py`, `quantum_maths.py`, algorithms/circuits/states subfolders, plus a staged build log (`phase_6_physics_applications.py` through `phase_10_documentation_validation.py`)
- Five overlapping "quantum_solver" variants at the backend root (`quantum_solver.py`, `_enhanced`, `_hybrid`, `_optimized`, `_types`) — duplication to resolve before treating any one as canonical
- `quantum_analytics/*` — a fully packaged module (own `setup.py`, `pyproject.toml`, `CHANGELOG.md`, `LICENSE`) covering Yang–Mills mass gap, electroweak/QCD/Higgs, string theory (compactification, holographic), noncommutative and spectral geometry, quantum thermodynamics
- `theory_of_everything/*` — its own engine, with three variants (`engine.py`, `engine_enhanced.py`, `engine_post_quantum.py`) needing the same canonical-version decision
- `cathedral_enhancements/*` (PULVINI / `pulvini_core`: `advanced_orchestrator.py`, `causal_intelligence.py`, `iit_rigorous.py`) — built on the same quantum-math substrate; final ownership TBD between PYTHAGORAS and HYBA Data/PULVINI
- `AMPLIFIED_RESONANT_GROVER_DEPLOYMENT.md`, `YANG_MILLS_MASS_GAP_ANALYSIS.md` at the repo root

## Items to close — completeness

- [ ]  Decide the canonical quantum solver among the five `quantum_solver*.py` variants; archive the rest
- [ ]  Decide the canonical Theory of Everything engine among `engine.py` / `engine_enhanced.py` / `engine_post_quantum.py`
- [ ]  Cross-check `backend/quantum_core/quantum_error_correction.py` against the stabilizer syndrome-extraction gap already flagged in the Product Suite review
- [ ]  Confirm whether `cathedral_enhancements/pulvini_core` belongs under PYTHAGORAS or under HYBA Data/PULVINI ownership
- [ ]  Independent verification of the Yang–Mills mass-gap claim before any external framing

## Items to close — production-ready / market / handover

- [ ]  This material sits behind the VQC's own gating strategy (see parent page) — nothing here should surface externally ahead of that gate
- [ ]  If any of it is treated as a scientific "gift" rather than product, decide the release vehicle separately from the commercial VQC gating timeline