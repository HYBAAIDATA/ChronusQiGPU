# Changelog

All notable changes to the EUCLID-CORE / PYTHIA platform are documented in this file.

## [3.5.0] — TOE Tensor Elevation fixes

### Breaking
- TF-IDF's exact default is now `TFIDF_MODE="exact_linear"` with rational `N/df` weights. Log-IDF is available only through the explicit `TFIDF_MODE="diagnostic_log"` path.
- Artifacts trained with the former log-IDF behavior must select `diagnostic_log` explicitly or be retrained. Predictions from stale artifacts are undefined.
- The historical `rf`, `xgb`, `lgbm`, and `gb` names are deprecated aliases for the canonical `exact_linear` model and do not implement the vendor algorithms.
- Exact training now defaults to `MODE="center_only"`; callers relying on the former scaling path must set their preprocessing mode explicitly and retrain.

### Correctness and hardening
- Range and diagnostic preprocessing remain explicit opt-in modes; exact square-root scaling is not called on the training path.
- Unitary validation is performed once at construction and cached.
- Joint state construction is restricted to cross-validation fold binding; trainers and predictors consume the ordinary `n × d` batch state.
- `theorem_proven=True` is unreachable without a checked proof artifact.
- Supervisor identity HMAC uses length-prefixed canonical encoding, constant-time verification, supervisor-epoch and worker-ID binding, and a mode-0600 file-backed secret path; raw secrets are not passed in environment values or exposed in status/audit output.
- The production container uses `restart: unless-stopped`; child workers receive only the secret path and epoch and are supervised with a bounded restart budget.

## [Unreleased] - 2026-09-17

### Added
- **ASI Manifold Elevation (S-2, S-3, S-11)**: Elevated three ASI schools from 1-D scalar scaffolds to genuine operators over the 11-D Poincaré-Golden ball `B_phi^11`, via the new shared adapter `pythagoras/asi/manifold_bridge.py` (exact golden→standard-ball isometry, Möbius/exponential-map geodesics, bipartite MIP machinery, state→covariance/DAG/prior-layer projections).
  - S-3 `information_integration.py`: genuine bipartite Minimum Information Partition `Φ = min_{A,B} D(ρ ‖ ρ_A ⊗ ρ_B)` with Gaussian relative entropy (covariance route) and quantum relative entropy (density route); Φ = 0 on product states, 2·ln2 on a Bell pair.
  - S-2 `causal_reasoning.py`: arbitrary DAGs over 11 dimensions, Pearl `do()` as explicit adjacency-column severing, multi-variable interventions with exact do-composition, counterfactuals preserved.
  - S-11 `predictive_processing.py`: hierarchical generative model with ambient errors `ε_l = u_l − K u_{l+1}`, closed-form joint optimum reached by true geodesic steps; free energy strictly non-increasing.
  - All scalar contracts preserved via dual-mode results (`.to_scalar()` / `phi_scalar`); `perceive`/`act`/`observe`/`intervene`/`counterfactual`/`measure_phi` signatures unchanged.
  - New suite `tests/test_asi_scale_validation.py` (25 tests); substrate files `poincare_golden_11d.py` / `salamander.py` untouched.
- **Autonomous Agentic Mining Lifecycle (`Intelligence/agentic_mining.py`)**:
  - Implemented the complete 6-phase autonomous mining lifecycle from Cold Start to Cool Down without manual intervention.
  - Wired all 13 substrates (Predictive, Causal, Topological, Geometric, Counterfactual, Yang-Mills, Millennium, MDMemory, Tensor, Quantum, iGPU, Storage, Physics).
  - Enforced SHA-256d as the sole accept authority for Bitcoin proof-of-work consensus.
  - Implemented O(1) candidate lookup and submission latency.
- **Five Domain Intelligences (`Intelligence/intelligences/`)**:
  - `CausalIntelligence`: Full authority over pool selection, network reasoning, and Rung 2 causal interventions.
  - `GeometricIntelligence`: Full authority over nonce space partitioning, 11D manifold navigation, and Cassini orbits.
  - `PlasticIntelligence`: Full authority over punch kernel fusion, dynamic batch sizing, and thermal/power budgets.
  - `CounterfactualIntelligence`: Full authority over share verification, submission timing, and Rung 3 what-if projections.
  - `QuantumIntelligence`: Full authority over Born rule probability verification, unitarity audits, and fee-optimal payout scheduling.
- **Theory of Everything (TOE) System (`Intelligence/toe_system.py`)**:
  - Master coordinator for routing decisions across the 5 intelligences and 13 substrates.
  - Implemented the 12-Theorem Candidate Verification Matrix for Contract 2 precompute gating.
  - Built immutable SHA-256 decision provenance ledger for auditability (Contract 8).
- **Manifold Bridge (`Intelligence/manifold_bridge.py`)**:
  - Connected `PrimeStorageManifold`, `PoincareCassiniSearch`, and `UnifiedPunchHost`.
  - Implemented multi-dimensional memory indexing, 7-sector distribution, Galois prime persistence, and continuous random sample Cassini verification with self-healing triggers.
- **Comprehensive Verification Suites**:
  - `tests/test_agentic_mining.py`: 18 tests covering Cold Start, Precompute, Hold, Submit (O(1)), Steady State, Cool Down, and Integrity Invariants.
  - `tests/test_mining_contracts.py`: 8 tests verifying all 8 formal mining contracts.
- **Documentation**:
  - `docs/AGENTIC_MINING.md`: Complete architectural guide to the agentic mining workflow, contract enforcement, and honest gap disclosures.

### Changed
- Preserved all baseline contracts in `hardened_unified_substrate.py` and `unified_punch_kernel.cl` without regression.
