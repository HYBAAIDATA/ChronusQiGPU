# Changelog

All notable changes to the EUCLID-CORE / PYTHIA platform are documented in this file.

## [Unreleased] - 2026-10-14 — EUCLID PR #69 Remediation Directive Closure

### Added
- **T5 Certified-Assurance Path E2E Proof (1.1)**: Proved reachability of the stricter T5 risk ladder through a real sandboxed integration test (`tests/frontier_agent/test_t5_qualification_e2e.py`) asserting entry into the certified-assurance branch and observing verified filesystem output under governance authority.
- **Iteration Counter on Success (1.2)**: Fixed operational loop counter tracking to advance on successful iterations only (`out.counter`, `agent.iteration_counter`). Verified $N$ successful iterations with $M$ interleaved retries yields `counter == N` in `tests/frontier_agent/test_iteration_counter_and_budget.py`.
- **Shared Retry & Recovery Budget Boundary (1.3)**: Added boundary regression tests asserting primary attempts and retries never exceed shared run budget, validating $2\times$ cost reservation (action + recovery) and refusal of unsafe unbudgeted retries in `tests/frontier_agent/test_iteration_counter_and_budget.py`.
- **Lucas TIER-15 Sustained Qualification (3.1)**: Implemented deterministic qualification run harness `scripts/lucas_qualification_harness.py` executing 1,364 sustained bounded iterations with zero budget escapes, 100% permissions holding, 3 verified rollbacks, and holding kill controls. Committed run log (`evidence/lucas_tier15_run.log`) and post-run invariant audit (`evidence/lucas_tier15_invariant_audit.json`).
- **Scale Tier 20 Capacity Projection (3.2)**: Measured per-iteration execution performance (9.992 ms/iteration) and delivered measured capacity projection (151.14 s wall clock, 62,508 compute units) for TIER-20 (15,127 iterations). Honestly declared TIER-20 as `UNIMPLEMENTED` with documented blocking reasons (10,000 learning queue bound, single-process timeout). Zero fabricated evidence.
- **Emergence Log (4.1, 4.2)**: Created `EMERGENCE-LOG.md` adhering to schema `{Trigger, Observed Behavior, Reproduction Steps, Classification, Reproduction Test, Mitigation}`. Seeded with observation-time discrepancy (EMR-001) and unit suite baseline (EMR-002).
- **Capability Ledger Double-vs-Real Split (5.1, 5.2)**: Updated `CAPABILITY-LEDGER.md` with explicit `CONTRACT_DOUBLE` vs `PRODUCTION_PATH` column and logged 8 unwired items + TIER-20 as `UNIMPLEMENTED`.
- **Validation Self-Custody Signed Artifact (6.1)**: Implemented `scripts/generate_validation_custody_artifact.py` and committed HMAC-SHA256 signed reproducible validation artifact in `docs/euclid_frontier_local_validation.json` recording environment hashes, command set, and raw test logs.
- **Contract Double Traceability & TODO-Gates (6.2)**: Annotated test doubles (`FileAdapter`, `RealSandboxedAdapter`) with production traceability targets and explicit `TODO-GATE` markers. Implemented gate check in `scripts/assert_production_drift_gate.py` and tests in `tests/frontier_agent/test_production_drift_gate.py`.
- **Heavy Intelligence Package Init Smoke (6.3)**: Added smoke test `tests/frontier_agent/test_intelligence_init_smoke.py` executing full `Intelligence` package and `IntelligenceOrchestrator` initialization.
- **Mid-Iteration Kill Control & Recovery (6.4)**: Implemented `test_kill_halts_mid_iteration_and_state_is_recoverable` in `tests/frontier_agent/test_safety.py` asserting kill switch halts mid-iteration run with verified clean rollback.
- **Claim Guard Documentation Linter (6.5)**: Implemented `scripts/claim_guard_linter.py` and unit test `tests/frontier_agent/test_claim_guard_linter.py` enforcing PR #69 no-claims clause (prohibiting unverified AGI/ASI, model superiority, prize-proof, and quantum supremacy claims).
- **Rollback Receipt Verification E2E (6.6)**: Implemented `test_rollback_receipt_verification_e2e` in `tests/frontier_agent/test_operational_loop.py` comparing pre-action cryptographic digests against post-rollback observation digests bit-for-bit.
- **Remediation Status & Gate Escalation Ledger (2.1, 2.2, 2.3)**: Created `REMEDIATION-STATUS.md` enumerating all failing CI gates (verbatim failure, root cause, fix, and commit), documenting check-run 403 permissions requests (`checks: write`, `statuses: write`), and establishing strict merge order (`#68 -> #69`).

### Changed
- `chronus/agent/audit.py`: Added fallback for `os.O_NOFOLLOW` on Windows (`getattr(os, "O_NOFOLLOW", 0)`).
- `chronus/agent/control.py`: Added `counter: int = 0` field to `Outcome`.
- `chronus/agent/operational_loop.py`: Tracked `successful_iterations` and incremented counter only on verified action success.
- `chronus/agent/main.py`: Tracked `_iteration_counter` on `FrontierAgent` and exposed `counter` and `iteration_counter` properties.

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
