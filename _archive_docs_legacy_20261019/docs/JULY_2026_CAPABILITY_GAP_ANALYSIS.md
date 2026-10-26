# July 2026 Capability Gap Analysis

Reference date: 2026-07-24. Machine-readable source of truth:
`manifests/july_2026_capability_gap_analysis.json` (schema `pythia.july-2026-capability-gap-analysis/v1`). This document is rendered from
that manifest by `scripts/render_gap_analysis_doc.py` — do not edit it by
hand; regenerate instead.

## Verdict

All 65 inventoried July 2026 surfaces are accounted for:
- **adapter-added**: 7
- **elevated**: 31
- **present**: 2
- **retired-with-reason**: 2
- **superseded**: 23

- `present`/`elevated`/`adapter-added` rows name a live importable symbol
  and exactly three evidence tests (unit, invariant, integration) that
  exist and pass in this checkout.
- `superseded`/`retired-with-reason` rows name an executable redirect
  resolved by `HISTORICAL_REDIRECTS` in
  `turing_universal_quantum_computer/july_compat.py`, plus a retirement
  reason.
- The aggregate gate is `tests/test_july_capability_gap_analysis.py` and
  `tests/test_july_chronos_mapping.py`: any row whose evidence test is
  renamed or deleted fails CI.

Nothing in this table claims production readiness without a named,
passing test. Historical totals (61/61, 110/110, 144/144) are provenance
only — fresh evidence is the cited tests.

## Status definitions

| Status | Meaning |
|---|---|
| present | Capability exists in the rebuilt tree under its canonical name. |
| elevated | Capability exists and was strengthened relative to July (real implementation + measured audit fields). |
| adapter-added | July surface kept as a thin adapter into a canonical owner; the adapter is bounded and fails closed. |
| superseded | Replaced by a canonical owner; `redirect` resolves to it. |
| retired-with-reason | No modern equivalent; `redirect` fails closed with a named reason. |

## Inventory

### `acceleration_result_record` — adapter-added

- **Historical surface**: `algorithm acceleration result records` (euclid.pythagoras.quantum.pulvini_enterprise.quantum_engine)
- **Capability**: Return an algorithm result with declared backend and measurement truth.
- **Current owner**: `Turing` (turing_universal_quantum_computer/turing_universal_quantum_computer/july_compat.py)
- **Symbol**: `turing_universal_quantum_computer.july_compat:AlgorithmResult`
- **Evidence**: `unit: tests/test_july_capability_gap_analysis.py::test_algorithm_result_rejects_overclaim`; `invariant: tests/test_july_capability_gap_analysis.py::test_algorithm_result_keeps_claim_flags_false`; `integration: tests/test_july_capability_gap_analysis.py::test_enhanced_grover_and_qft_integrate_with_canonical_algorithms`
- **Claim boundary**: Immutable result records reject hardware, speedup, or consensus-authority assertions.

### `acceleration_facade` — adapter-added

- **Historical surface**: `QuantumAccelerationEngine` (euclid.pythagoras.quantum.pulvini_enterprise.quantum_engine)
- **Capability**: Algorithm facade and result records for bounded quantum algorithm execution.
- **Current owner**: `Turing` (turing_universal_quantum_computer/turing_universal_quantum_computer/july_compat.py)
- **Symbol**: `turing_universal_quantum_computer.july_compat:QuantumAccelerationEngine`
- **Evidence**: `unit: tests/test_july_capability_gap_analysis.py::test_algorithm_adapter_rejects_invalid_domains_and_types`; `invariant: tests/test_july_capability_gap_analysis.py::test_algorithm_result_keeps_claim_flags_false`; `integration: tests/test_july_capability_gap_analysis.py::test_enhanced_grover_and_qft_integrate_with_canonical_algorithms`
- **Claim boundary**: Dense software simulation only; bounded to configured qubit width, no measured acceleration, hardware, or mining authority.

### `audit_and_compliance` — superseded

- **Historical surface**: `AuditLedger` (euclid.pythagoras.quantum.pulvini_enterprise.audit)
- **Capability**: Append-only evidence ledger and integrity checking.
- **Current owner**: `AL HARAS` (al_haras/audit.py)
- **Evidence**: `redirect: tests/test_july_capability_gap_analysis.py::test_retired_surfaces_have_executable_redirects`
- **Claim boundary**: Use the current hash-chain audit; a ledger does not establish compliance or theorem truth by itself.
- **Redirect**: `al_haras.audit.HashChainAudit`
- **Retirement reason**: The July wrapper name is redundant with the canonical hash-chain audit.

### `compliance_verifier` — superseded

- **Historical surface**: `ComplianceVerifier` (euclid.pythagoras.quantum.pulvini_enterprise.compliance)
- **Capability**: Evaluate evidence against current release and claim governance rules.
- **Current owner**: `AL HARAS` (al_haras/claims_yaml.py; al_haras/promotion_gates.py)
- **Evidence**: `redirect: tests/test_july_capability_gap_analysis.py::test_retired_surfaces_have_executable_redirects`
- **Claim boundary**: Claim governance checks configured evidence and policy; it does not prove scientific claims.
- **Redirect**: `al_haras.claims_yaml.load_claims`
- **Retirement reason**: The historical facade is replaced by explicit AL HARAS claim and promotion gates.

### `backend_selection` — elevated

- **Historical surface**: `backend selection` (euclid.pythagoras.quantum.pulvini_enterprise.quantum_engine)
- **Capability**: Select an execution backend by supported algorithm domain.
- **Current owner**: `Turing` (turing_universal_quantum_computer/turing_universal_quantum_computer/backends)
- **Symbol**: `turing_universal_quantum_computer.backends:select_backend`
- **Evidence**: `unit: turing_universal_quantum_computer/tests/test_backend_boundary.py::test_dense_backend_refuses_beyond_its_budget`; `invariant: turing_universal_quantum_computer/tests/test_backend_boundary.py::test_no_backend_claims_a_physical_device_except_qpu`; `integration: turing_universal_quantum_computer/tests/test_console_session.py::test_backends_matrix_lists_every_backend`
- **Claim boundary**: Registry dispatch is capability admission, not physical device evidence; unsupported domains fail closed.

### `benchmark_reproducibility` — elevated

- **Historical surface**: `benchmark and reproducibility surfaces` (euclid.pythagoras.quantum.pulvini_enterprise.benchmarks)
- **Capability**: Repeatable benchmark reports with execution and measurement boundaries.
- **Current owner**: `Kellogg and Tensor` (kellogg/tensor_network.py; tensor/contracts.py)
- **Symbol**: `kellogg.tensor_network:TensorNetworkAudit`
- **Evidence**: `unit: tests/test_kellogg_tensor_network_convergence.py::test_tt_compatibility_payload_and_error_budget`; `invariant: tests/test_kellogg_tensor_network_convergence.py::test_hamiltonian_evolution_is_norm_preserving`; `integration: tests/test_hash_pipeline.py::test_benchmark_reports_measured`
- **Claim boundary**: Reports distinguish measured fields from models and representation accounting; no general speedup claim.

### `compression_artifact_codec` — superseded

- **Historical surface**: `ArtifactCodec` (euclid.pythagoras.quantum.pulvini_enterprise.quantum_engine)
- **Capability**: Persist, reload, and validate compressed tensor artifacts.
- **Current owner**: `Kellogg` (kellogg/tensor_serialization.py)
- **Evidence**: `redirect: tests/test_july_capability_gap_analysis.py::test_retired_surfaces_have_executable_redirects`
- **Claim boundary**: Use checksummed, non-pickle PV serialization; validation is structural integrity, not artifact provenance.
- **Redirect**: `kellogg.tensor_serialization.save_pv/load_pv/validate_pv`
- **Retirement reason**: The historical codec facade is replaced by the tested safe canonical serializer.

### `compression_policy` — superseded

- **Historical surface**: `CompressionPolicy` (euclid.pythagoras.quantum.pulvini_enterprise.quantum_engine)
- **Capability**: Choose a tensor representation and bounded compression policy.
- **Current owner**: `Kellogg` (kellogg/compressed_tensor.py)
- **Evidence**: `redirect: tests/test_july_capability_gap_analysis.py::test_retired_surfaces_have_executable_redirects`
- **Claim boundary**: Use EngineConfig and explicit lossy TT/MPS error; representation ratios are not physical compression.
- **Redirect**: `kellogg.compressed_tensor.EngineConfig`
- **Retirement reason**: The canonical engine already validates schemes, rank budgets, and approximation error.

### `compression_service` — superseded

- **Historical surface**: `PulviniCompressionService` (euclid.pythagoras.quantum.pulvini_enterprise.quantum_engine)
- **Capability**: Compression-aware tensor loading, execution, and reconstruction.
- **Current owner**: `Kellogg` (kellogg/compressed_tensor.py)
- **Evidence**: `redirect: tests/test_july_capability_gap_analysis.py::test_retired_surfaces_have_executable_redirects`
- **Claim boundary**: Use the canonical operator engine; no physical compression or hardware benefit is implied.
- **Redirect**: `kellogg.compressed_tensor.QuantumCompressedTensorEngine`
- **Retirement reason**: A second service layer would duplicate Kellogg ownership.

### `exact_tensor_core` — elevated

- **Historical surface**: `Exact tensor and algebraic contracts` (euclid.pythagoras.quantum.pulvini_enterprise.formal)
- **Capability**: Validated exact state/tensor operations with bounded unsupported cases.
- **Current owner**: `Kellogg` (kellogg/exact_tensor.py; kellogg/exact_field.py)
- **Symbol**: `kellogg.exact_tensor:ExactStateVector`
- **Evidence**: `unit: turing_universal_quantum_computer/tests/test_exact_state_vector.py::test_tensor_and_cnot_bell_state`; `invariant: tests/test_july_capability_consolidation.py::test_kellogg_binary_elementwise_reduce_and_metrics`; `integration: tests/test_kellogg_tensor_network_convergence.py::test_compressed_tensor_schemes_roundtrip`
- **Claim boundary**: Exactness applies only to declared algebraic domains; unsupported values or operations are rejected.

### `formal_contract_reports` — superseded

- **Historical surface**: `FormalContract, AxiomReport, TheoremReport, ComplexityReport, FullContractReport` (euclid.pythagoras.quantum.pulvini_enterprise.formal)
- **Capability**: Aggregate axioms, theorem statements, and complexity claims into contract reports.
- **Current owner**: `Turing and AL HARAS` (turing_universal_quantum_computer/turing_universal_quantum_computer/certificates.py; al_haras/)
- **Evidence**: `redirect: tests/test_july_capability_gap_analysis.py::test_retired_surfaces_have_executable_redirects`
- **Claim boundary**: RunWitness records execution evidence only; this repository does not claim theorem proofs.
- **Redirect**: `turing_universal_quantum_computer.certificates.RunWitness`
- **Retirement reason**: A generic theorem-report facade risks conflating executable evidence with mathematical proof.

### `geodesic_exact_folding` — elevated

- **Historical surface**: `Exact PULVINI fold and selective unfold` (euclid.pythagoras.quantum.pulvini_enterprise.geodesic_tensor_engine)
- **Capability**: Reversible pair folding and selective reconstruction for tensor custody.
- **Current owner**: `python_backend.core_modules` (python_backend/core_modules/math_folding.py; python_backend/core_modules/geodesic_tensor_engine.py)
- **Symbol**: `python_backend.core_modules.geodesic_tensor_engine:unfold_partial_with_stats`
- **Evidence**: `unit: tests/test_july_capability_consolidation.py::test_fold_result_round_trip_updates_only_requested_slice`; `invariant: tests/test_july_capability_consolidation.py::test_integrity_gate_roundtrip_and_metrics`; `integration: tests/test_july_capability_consolidation.py::test_selective_unfold_does_not_call_full_unfold`
- **Claim boundary**: Exact reversible representation and selective reads; no physical memory savings or acceleration claim.

### `geodesic_tensor_facade` — elevated

- **Historical surface**: `MetricTensor, PhiTensorCore, EnergyModel, HybridGPU` (euclid.pythagoras.quantum.pulvini_enterprise.geodesic_tensor_engine)
- **Capability**: Metric-aware tensor operations, virtual routing, and declared resource models.
- **Current owner**: `Kellogg, Tensor, and Chronus` (kellogg/phi_tensor_core.py; tensor/; chronus/tensor_compute.py)
- **Symbol**: `kellogg.phi_tensor_core:MetricTensor`
- **Evidence**: `unit: tests/test_july_capability_consolidation.py::test_metric_tensor_exposes_riemannian_surface`; `invariant: tests/test_july_capability_consolidation.py::test_kellogg_binary_elementwise_reduce_and_metrics`; `integration: tests/test_july_capability_consolidation.py::test_current_chronus_physical_backend_declares_tensor_ops_fail_closed`
- **Claim boundary**: Virtual routing and EnergyModel values are not device measurements; hardware execution uses Chronus provenance.

### `hamiltonian_reduction` — elevated

- **Historical surface**: `HamiltonianReducer` (euclid.pythagoras.quantum.pulvini_enterprise.hamiltonian)
- **Capability**: Reduce Hamiltonian dimension while preserving spectral and topology properties.
- **Current owner**: `quantum_compute_substrate.pulvini` (quantum_compute_substrate/pulvini/pulvini_scaling.py)
- **Symbol**: `quantum_compute_substrate.pulvini.pulvini_scaling:PulviniOperator`
- **Evidence**: `unit: quantum_compute_substrate/tests/test_pulvini.py::TestSpectralGapPreservation::test_rejects_non_square`; `invariant: quantum_compute_substrate/tests/test_pulvini.py::TestSpectralGapPreservation::test_gap_preserved_dim_16`; `integration: quantum_compute_substrate/tests/test_pulvini.py::TestSubstrateIntegration::test_orchestrator_hamiltonian_from_cathedral_pauli`
- **Claim boundary**: SVD projection into the phi^2-complement subspace with a measured spectral-gap delta and Frobenius reconstruction bound; the audit declares is_reversible=False for the Hamiltonian path.

### `hamiltonian_result_record` — elevated

- **Historical surface**: `HamiltonianResult` (euclid.pythagoras.quantum.pulvini_enterprise.hamiltonian)
- **Capability**: Report a Hamiltonian reduction outcome and its declared error or preservation evidence.
- **Current owner**: `quantum_compute_substrate.pulvini` (quantum_compute_substrate/pulvini/pulvini_scaling.py)
- **Symbol**: `quantum_compute_substrate.pulvini.pulvini_scaling:PulviniAuditEnvelope`
- **Evidence**: `unit: quantum_compute_substrate/tests/test_pulvini.py::TestSpectralGapPreservation::test_audit_envelope_fields_populated`; `invariant: quantum_compute_substrate/tests/test_pulvini.py::TestQuantumDynamics::test_norm_drift_field_populated`; `integration: quantum_compute_substrate/tests/test_pulvini.py::TestPythagorasOrchestrator::test_routing_audit_fields_present`
- **Claim boundary**: The audit envelope reports measured dimensions, reconstruction error, spectral-gap delta and norm drift; it does not claim spectral preservation.

### `historical_enhanced_grover` — adapter-added

- **Historical surface**: `EnhancedGroverAlgorithm` (euclid.pythagoras.quantum.pulvini_enterprise.enhanced_classics)
- **Capability**: Grover search facade over a bounded marked-item domain.
- **Current owner**: `Turing` (turing_universal_quantum_computer/turing_universal_quantum_computer/july_compat.py)
- **Symbol**: `turing_universal_quantum_computer.july_compat:EnhancedGroverAlgorithm`
- **Evidence**: `unit: tests/test_july_capability_gap_analysis.py::test_algorithm_adapter_rejects_invalid_domains_and_types`; `invariant: tests/test_july_capability_gap_analysis.py::test_algorithm_result_keeps_claim_flags_false`; `integration: tests/test_july_capability_gap_analysis.py::test_enhanced_grover_and_qft_integrate_with_canonical_algorithms`
- **Claim boundary**: Finite-precision software simulation of standard Grover; no measured speedup or consensus authority.

### `historical_enhanced_qft` — adapter-added

- **Historical surface**: `EnhancedQuantumFourierTransform` (euclid.pythagoras.quantum.pulvini_enterprise.enhanced_classics)
- **Capability**: Bounded QFT and inverse-QFT operator construction.
- **Current owner**: `Turing` (turing_universal_quantum_computer/turing_universal_quantum_computer/july_compat.py)
- **Symbol**: `turing_universal_quantum_computer.july_compat:EnhancedQuantumFourierTransform`
- **Evidence**: `unit: tests/test_july_capability_gap_analysis.py::test_algorithm_adapter_rejects_invalid_domains_and_types`; `invariant: tests/test_july_capability_gap_analysis.py::test_algorithm_result_keeps_claim_flags_false`; `integration: tests/test_july_capability_gap_analysis.py::test_enhanced_grover_and_qft_integrate_with_canonical_algorithms`
- **Claim boundary**: Bounded finite-precision matrix construction; dense dimension cap applies.

### `historical_enhanced_shor` — retired-with-reason

- **Historical surface**: `EnhancedShorAlgorithm` (euclid.pythagoras.quantum.pulvini_enterprise.enhanced_classics)
- **Capability**: Shor factoring facade.
- **Current owner**: `Turing` (turing_universal_quantum_computer/turing_universal_quantum_computer/july_compat.py)
- **Evidence**: `redirect: tests/test_july_capability_gap_analysis.py::test_algorithm_adapters_are_bounded_and_make_no_hardware_or_speedup_claim`
- **Claim boundary**: The adapter explicitly refuses Shor; factoring and quantum speedup are not claimed.
- **Redirect**: `turing_universal_quantum_computer.july_compat.QuantumAccelerationEngine.run_shor`
- **Retirement reason**: No validated end-to-end factoring implementation exists in the retained backend.

### `invariant_verification_facade` — adapter-added

- **Historical surface**: `operator-calculus run_all_verifications and report generation` (euclid.pythagoras.quantum.pulvini_enterprise.quantum_formalism)
- **Capability**: Run seeded operator invariants and return an aggregate verification report.
- **Current owner**: `Turing` (turing_universal_quantum_computer/turing_universal_quantum_computer/july_compat.py)
- **Symbol**: `turing_universal_quantum_computer.july_compat:run_all_verifications`
- **Evidence**: `unit: tests/test_july_capability_gap_analysis.py::test_operator_verification_report_returns_canonical_report`; `invariant: tests/test_july_capability_gap_analysis.py::test_operator_verification_report_fails_closed`; `integration: tests/test_july_capability_gap_analysis.py::test_operator_verification_report_covers_core_invariants`
- **Claim boundary**: Runs deterministic numerical checks and raises on failed checks; does not certify a theorem or physical device.

### `kellogg_compressed_tensor_engine` — elevated

- **Historical surface**: `QuantumCompressedTensorEngine` (euclid.pythagoras.quantum.pulvini_enterprise.quantum_engine)
- **Capability**: Validated compressed tensor operations, quantum operators, measurement, and interference.
- **Current owner**: `Kellogg` (kellogg/compressed_tensor.py)
- **Symbol**: `kellogg.compressed_tensor:QuantumCompressedTensorEngine`
- **Evidence**: `unit: tests/test_kellogg_tensor_network_convergence.py::test_compressed_tensor_schemes_roundtrip`; `invariant: tests/test_kellogg_tensor_network_convergence.py::test_unitary_kraus_and_measurement_paths_preserve_density`; `integration: tests/test_kellogg_tensor_network_convergence.py::test_safe_authenticated_serialization_roundtrip`
- **Claim boundary**: Explicit finite-precision software semantics, validated dimensions and CPTP completeness; no physical compression claim.

### `modern_variational_eigensolver` — present

- **Historical surface**: `ModernVariationalQuantumEigensolver and next-gen VQE facade` (euclid.pythagoras.quantum.pulvini_enterprise.next_gen_2025)
- **Capability**: Variational energy minimization for a small explicit Hamiltonian.
- **Current owner**: `Turing` (turing_universal_quantum_computer/turing_universal_quantum_computer/quantum_algorithms.py)
- **Symbol**: `turing_universal_quantum_computer.quantum_algorithms:VQE`
- **Evidence**: `unit: tests/test_july_capability_gap_analysis.py::test_vqe_hamiltonian_is_hermitian`; `invariant: tests/test_july_capability_gap_analysis.py::test_vqe_result_respects_variational_energy_bound`; `integration: tests/test_july_capability_gap_analysis.py::test_current_vqe_surface_executes_finite_bounded_problem`
- **Claim boundary**: Small dense numerical optimizer; convergence and optimality are not guaranteed beyond reported finite run results.

### `next_gen_2025_facades` — superseded

- **Historical surface**: `next_gen_2025` (euclid.pythagoras.quantum.pulvini_enterprise.next_gen_2025)
- **Capability**: Aggregate planned or experimental optimization and simulation interfaces.
- **Current owner**: `Turing` (turing_universal_quantum_computer/turing_universal_quantum_computer/capabilities.py)
- **Evidence**: `redirect: tests/test_july_capability_gap_analysis.py::test_retired_surfaces_have_executable_redirects`
- **Claim boundary**: Only backend-specific capability metadata and implemented algorithms are advertised; planned facades are not execution evidence.
- **Redirect**: `turing_universal_quantum_computer.capabilities.capability_report`
- **Retirement reason**: The broad historical namespace mixed executable algorithms and plans without a stable per-domain contract.

### `mps_tt_budgeted_compression` — elevated

- **Historical surface**: `MPS/TT decomposition, reconstruction, and budgeted compression` (src.chronos.compression and src.chronos.academic.tensor_compression)
- **Capability**: Validated tensor network decomposition with bounded rank and reconstruction-error accounting.
- **Current owner**: `Kellogg` (kellogg/tensor_network.py)
- **Symbol**: `kellogg.tensor_network:TensorTrain`
- **Evidence**: `unit: tests/test_kellogg_tensor_network_convergence.py::test_tensor_train_roundtrip_preserves_complex_dtype`; `invariant: tests/test_kellogg_tensor_network_convergence.py::test_mps_roundtrip_and_dimension_contract`; `integration: tests/test_kellogg_tensor_network_convergence.py::test_tt_compatibility_payload_and_error_budget`
- **Claim boundary**: Lossy truncation reports reconstruction error and representation storage only; no HBM or physical compression claim.

### `operator_hamiltonian_and_trotter` — elevated

- **Historical surface**: `Hermitian Hamiltonian Trotter simulation` (euclid.pythagoras.quantum.pulvini_enterprise.hamiltonian)
- **Capability**: Bounded full-Hilbert-dimension time evolution with invalid Hamiltonians refused.
- **Current owner**: `Turing` (turing_universal_quantum_computer/turing_universal_quantum_computer/trotter_simulation.py)
- **Symbol**: `turing_universal_quantum_computer.trotter_simulation:TrotterHamiltonianSimulator`
- **Evidence**: `unit: tests/test_july_capability_gap_analysis.py::test_trotter_adapter_rejects_non_hermitian_hamiltonians`; `invariant: tests/test_july_capability_consolidation.py::test_completed_qsim_trotterization_retains_full_hilbert_dimension`; `integration: tests/test_kellogg_tensor_network_convergence.py::test_hamiltonian_evolution_is_norm_preserving`
- **Claim boundary**: Approximate Trotter-Suzuki software evolution with validated Hermiticity and reported finite-time behavior.

### `pv_artifact_persistence` — elevated

- **Historical surface**: `PV serialization save/load/validate` (src.chronos.compression)
- **Capability**: Safely serialize compressed tensor payloads with integrity checks.
- **Current owner**: `Kellogg` (kellogg/tensor_serialization.py)
- **Symbol**: `kellogg.tensor_serialization:save_pv`
- **Evidence**: `unit: tests/test_july_capability_gap_analysis.py::test_malformed_pv_payload_is_rejected`; `invariant: tests/test_chronus_gpu_capability_closure.py::test_pipeline_uses_safe_kellogg_serialization`; `integration: tests/test_kellogg_tensor_network_convergence.py::test_safe_authenticated_serialization_roundtrip`
- **Claim boundary**: Checksums, optional HMAC, and allow_pickle=False validate the artifact container; no signing identity is implied.

### `pulvini_array_matrix_tensor_wrappers` — superseded

- **Historical surface**: `PulviniArray, PulviniMatrix, PulviniTensor` (euclid.pythagoras.quantum.pulvini_enterprise.formal)
- **Capability**: Convenience objects for typed folded arrays and matrix/tensor views.
- **Current owner**: `python_backend.core_modules` (python_backend/core_modules/geodesic_tensor_engine.py)
- **Evidence**: `redirect: tests/test_july_capability_gap_analysis.py::test_retired_surfaces_have_executable_redirects`
- **Claim boundary**: ExactFoldState records flat exact values, shape, depth, and inverse behavior; no parallel wrapper hierarchy.
- **Redirect**: `python_backend.core_modules.geodesic_tensor_engine.ExactFoldState`
- **Retirement reason**: Shape-tagged exact fold state covers the data custody contract without duplicate object wrappers.

### `pulvini_functor` — retired-with-reason

- **Historical surface**: `PulviniFunctor` (euclid.pythagoras.quantum.pulvini_enterprise.functor)
- **Capability**: Functorial mapping over folded tensor structures.
- **Current owner**: `python_backend.core_modules` (python_backend/core_modules/geodesic_tensor_engine.py)
- **Evidence**: `redirect: tests/test_july_capability_gap_analysis.py::test_retired_surfaces_have_executable_redirects`
- **Claim boundary**: Only concrete exact fold and tensor operations are asserted; categorical law preservation is not claimed.
- **Redirect**: `python_backend.core_modules.geodesic_tensor_engine.ExactFoldState`
- **Retirement reason**: No executable mapping-law specification or test evidence was recovered for the historical abstraction.

### `quantum_inspired_optimizer` — superseded

- **Historical surface**: `QuantumInspiredOptimizer` (euclid.pythagoras.quantum.pulvini_enterprise.quantum_optimizer)
- **Capability**: Numerical parameter optimization using declared variational methods.
- **Current owner**: `Turing` (turing_universal_quantum_computer/turing_universal_quantum_computer/quantum_algorithms.py; variational.py)
- **Evidence**: `redirect: tests/test_july_capability_gap_analysis.py::test_retired_surfaces_have_executable_redirects`
- **Claim boundary**: Use explicit VQE or VQC optimizers; no quantum runtime or advantage is inferred.
- **Redirect**: `turing_universal_quantum_computer.quantum_algorithms.VQE.optimize`
- **Retirement reason**: The generic optimizer name obscures the distinct validated VQE and VQC objective contracts.

### `quantum_inspired_vqc` — present

- **Historical surface**: `VQCPhiGroverIntegration, VQCTrainingDataGenerator` (euclid.pythagoras.quantum.pulvini_enterprise.next_gen_2025)
- **Capability**: Deterministic training data and a constrained VQC/Grover candidate-ranking integration.
- **Current owner**: `Turing` (turing_universal_quantum_computer/turing_universal_quantum_computer/variational.py; phi_vqc.py)
- **Symbol**: `turing_universal_quantum_computer.variational:VQCPhiGroverIntegration`
- **Evidence**: `unit: turing_universal_quantum_computer/tests/test_variational.py::VQCCircuitTests::test_forward_distribution_sums_to_one`; `invariant: turing_universal_quantum_computer/tests/test_phi_quantum_machine_consolidation.py::test_vqc_ranks_only_existing_candidates`; `integration: turing_universal_quantum_computer/tests/test_variational.py::VQCIntegrationTests::test_demonstrate_vqc_end_to_end`
- **Claim boundary**: VQC can only rank an existing candidate set; SHA-256d and target checking remain sole consensus authority.

### `regenerative_checkpoint` — elevated

- **Historical surface**: `exact machine checkpoint, tamper detection, restoration, invariant reporting` (euclid.pythagoras.quantum.pulvini_enterprise.regenerative)
- **Capability**: Integrity-checked checkpoint, corruption detection, and exact restoration for supported Clifford state.
- **Current owner**: `Turing` (turing_universal_quantum_computer/turing_universal_quantum_computer/phi_quantum_machine.py)
- **Symbol**: `turing_universal_quantum_computer.phi_quantum_machine:PhiQuantumMachine`
- **Evidence**: `unit: turing_universal_quantum_computer/tests/test_phi_machine_profile.py::TestPhiMachineProfile::test_checkpoint_roundtrip_and_tamper_detection`; `invariant: turing_universal_quantum_computer/tests/test_phi_quantum_machine_consolidation.py::test_depth_20_pulvini_checkpoint_restores_exact_digest`; `integration: turing_universal_quantum_computer/tests/test_phi_quantum_machine_consolidation.py::test_vqc_clifford_skeleton_checkpoint_is_exact`
- **Claim boundary**: Exact checkpoint custody and tamper detection for supported Clifford state only; no generic hardware fault recovery.

### `regenerative_contract_facade` — superseded

- **Historical surface**: `RegenerativeContract, arbitrary fault injection, regeneration experiment reports` (euclid.pythagoras.quantum.pulvini_enterprise.regenerative)
- **Capability**: Generic fault injection, automatic recovery, and aggregated invariant experiment reporting.
- **Current owner**: `Turing` (turing_universal_quantum_computer/turing_universal_quantum_computer/phi_quantum_machine.py)
- **Evidence**: `redirect: tests/test_july_capability_gap_analysis.py::test_retired_surfaces_have_executable_redirects`
- **Claim boundary**: Use exact machine checkpoints; arbitrary fault recovery and hardware regeneration are not claimed.
- **Redirect**: `turing_universal_quantum_computer.phi_quantum_machine.PhiQuantumMachine.checkpoint`
- **Retirement reason**: Only exact checkpoint restoration has current executable evidence; generic fault injection is not implemented.

### `turing_1000_qubit_machine` — elevated

- **Historical surface**: `PhiQuantumMachine1000, signed-Pauli verification, algorithm catalogue` (HYBA_1000_QUBIT_VQC_20260724.zip)
- **Capability**: Large-width exact Clifford execution and discriminating stabilizer verification.
- **Current owner**: `Turing` (turing_universal_quantum_computer/turing_universal_quantum_computer/phi_quantum_machine.py; phi_verification.py)
- **Symbol**: `turing_universal_quantum_computer.phi_quantum_machine:PhiQuantumMachine1000`
- **Evidence**: `unit: turing_universal_quantum_computer/tests/test_phi_quantum_machine_consolidation.py::test_qasm_clifford_surface_and_non_clifford_rejection`; `invariant: turing_universal_quantum_computer/tests/test_phi_quantum_machine_consolidation.py::test_exact_ghz_stabilizer_membership_is_discriminating`; `integration: turing_universal_quantum_computer/tests/test_phi_quantum_machine_consolidation.py::test_full_1000_qubit_production_gate`
- **Claim boundary**: Exact classical Clifford/stabilizer execution; not universal arbitrary-circuit computation or quantum advantage.

### `turing_algorithm_catalogue` — elevated

- **Historical surface**: `12-algorithm acceleration catalogue` (HYBA_1000_QUBIT_VQC_20260724.zip)
- **Capability**: Publish per-algorithm execution status and supported state class.
- **Current owner**: `Turing` (turing_universal_quantum_computer/turing_universal_quantum_computer/phi_quantum_machine.py)
- **Symbol**: `turing_universal_quantum_computer.phi_quantum_machine:ALGORITHM_CATALOG`
- **Evidence**: `unit: turing_universal_quantum_computer/tests/test_phi_quantum_machine_consolidation.py::test_algorithm_plans_distinguish_executable_from_metadata`; `invariant: turing_universal_quantum_computer/tests/test_phi_machine_profile.py::TestPhiMachineProfile::test_algorithm_surface_keeps_non_clifford_boundary`; `integration: turing_universal_quantum_computer/tests/test_console_session.py::test_backends_matrix_lists_every_backend`
- **Claim boundary**: Catalogue rows are capability metadata, not evidence that all listed algorithms execute or accelerate.

### `turing_candidate_set_boundary` — elevated

- **Historical surface**: `phi-VQC candidate ordering` (HYBA_1000_QUBIT_VQC_20260724.zip)
- **Capability**: VQC-based candidate prioritization without replacing consensus validation.
- **Current owner**: `Turing and mining` (turing_universal_quantum_computer/turing_universal_quantum_computer/phi_vqc.py; mining/hash_pipeline.py)
- **Symbol**: `turing_universal_quantum_computer.phi_vqc:PhiGroverVQC`
- **Evidence**: `unit: turing_universal_quantum_computer/tests/test_phi_quantum_machine_consolidation.py::test_vqc_ranks_only_existing_candidates`; `invariant: tests/test_three_layer_runtime.py::test_tensor_advice_fails_closed_on_window_mutation`; `integration: tests/test_hash_pipeline.py::test_removed_quantum_standin_ids_are_rejected`
- **Claim boundary**: Candidate ordering only; mining hash pipeline alone verifies proof-of-work and remains the accept authority.

### `trotter_and_cptp_fixes` — elevated

- **Historical surface**: `Full Hilbert dimension, Grover keyword compatibility, CPTP completeness` (PULVINI_V3_HERMES_COMPLETION_20260724.zip)
- **Capability**: Retain corrected Trotter dimension, Grover execution, and trace-preserving channel checks.
- **Current owner**: `Turing` (turing_universal_quantum_computer/turing_universal_quantum_computer/trotter_simulation.py; kellogg/compressed_tensor.py)
- **Symbol**: `kellogg.compressed_tensor:QuantumCompressedTensorEngine`
- **Evidence**: `unit: tests/test_july_capability_consolidation.py::test_completed_grover_and_cptp_fixes_remain_live`; `invariant: tests/test_kellogg_tensor_network_convergence.py::test_unitary_kraus_and_measurement_paths_preserve_density`; `integration: tests/test_july_capability_consolidation.py::test_completed_qsim_trotterization_retains_full_hilbert_dimension`
- **Claim boundary**: Numerical validation within explicit domains; no broad quantum capability or speedup claim.

### `topology_signature` — elevated

- **Historical surface**: `Topology signature and preservation checks` (src.chronos.compression and src.chronos.academic.tensor_compression)
- **Capability**: Compare graph topology before and after declared tensor transformations.
- **Current owner**: `Kellogg` (kellogg/tensor_network.py)
- **Symbol**: `kellogg.tensor_network:topology_signature`
- **Evidence**: `unit: tests/test_kellogg_tensor_network_convergence.py::test_topology_and_persistence_contracts`; `invariant: tests/test_kellogg_tensor_network_convergence.py::test_topology_and_persistence_contracts`; `integration: tests/test_aethel_geodesic_handoff.py::test_geodesic_step_uses_engine_invariant`
- **Claim boundary**: The signature is a graph descriptor comparison, not a proof of general topological equivalence.

### `variational_fisher_natural_gradient` — elevated

- **Historical surface**: `Fisher metric and natural-gradient step` (src.chronos.theory.metrology and euclid.pythagoras.quantum.pulvini_enterprise.next_gen_2025)
- **Capability**: Compute complex-state Fisher geometry and a normalized optimizer step.
- **Current owner**: `Kellogg` (kellogg/tensor_network.py; kellogg/quantum_tensor.py)
- **Symbol**: `kellogg.tensor_network:natural_gradient_step`
- **Evidence**: `unit: tests/test_kellogg_tensor_network_convergence.py::test_quantum_fisher_uses_complex_modulus_and_step_normalizes`; `invariant: tests/test_kellogg_tensor_network_convergence.py::test_quantum_fisher_uses_complex_modulus_and_step_normalizes`; `integration: turing_universal_quantum_computer/tests/test_variational.py::VQCCircuitTests::test_train_records_history_and_best_params`
- **Claim boundary**: Finite-dimensional numerical metric and optimizer update; no convergence, energy, or quantum-advantage guarantee.

### `chronus_physical_execution` — elevated

- **Historical surface**: `Physical tensor backend and execution provenance` (GEODESIC_TENSOR_ENGINE_EXTENDED_20260724.zip)
- **Capability**: Route declared tensor kernels to actual hardware with measured provenance.
- **Current owner**: `Chronus and Tensor` (chronus/tensor_compute.py; tensor/backends/chronus_backend.py)
- **Symbol**: `tensor.backends.chronus_backend:ChronusBackend`
- **Evidence**: `unit: tests/test_chronus_tensor_compute.py::test_chronus_backend_wires_runtime`; `invariant: tests/test_chronus_production_measurement.py::test_device_tensor_measurement_rejects_unverified_output`; `integration: tests/test_chronus_production_measurement.py::test_device_tensor_measurement_is_verified_and_device_labelled`
- **Claim boundary**: A real device claim requires runtime hardware and verified output provenance; absence is unavailable, not simulated success.

### `chronos_academic_integrations` — elevated

- **Historical surface**: `academic integrations (Caltech topological/surface-code/Ising-anyon, Cambridge PINN/GQN/RL, CERN cavity-QED/QFT/LHC, MIT fault-tolerant control, Jaynes-Cummings, NIST benchmark, TokyoTech metrology)` (src.chronos.academic)
- **Capability**: Deterministic physics-model integrations used for enhancement and verification experiments.
- **Current owner**: `chronus.v33.academic` (chronus/v33/academic)
- **Symbol**: `chronus.v33.academic:AcademicChronosEngine`
- **Evidence**: `unit: tests/test_july_chronos_mapping.py::test_v33_academic_surface`; `invariant: tests/test_chronus_v33/test_academic.py::test_uhlmann_fidelity_self`; `integration: tests/test_chronus_v33/test_academic_integration.py::test_academic_engine_end_to_end`
- **Claim boundary**: Software model facades executing deterministic computations; no lab hardware access or published-result replication is claimed.

### `chronos_memory_substrate` — elevated

- **Historical surface**: `QRAM, QSVT, block-encoding, MPS store, neural-combine memory, memory hierarchy, table memory` (src.chronos.memory)
- **Capability**: Memory primitives: quantum random access, singular-value transform, block encodings, MPS storage and learned index combination.
- **Current owner**: `chronus.v33.memory` (chronus/v33/memory)
- **Symbol**: `chronus.v33.memory:MemoryHierarchy`
- **Evidence**: `unit: tests/test_july_chronos_mapping.py::test_v33_memory_surface`; `invariant: tests/test_chronus_v33/test_memory.py::test_table_qram_roundtrip`; `integration: tests/test_chronus_v33/test_memory.py::test_hierarchy_pipeline`
- **Claim boundary**: Exact software models of the memory primitives; no hardware QRAM or physical qubit array is claimed.

### `chronos_tebd_compression` — elevated

- **Historical surface**: `TEBD time evolution, phi-fold compression, large-Hilbert-space handling` (src.chronos.compression)
- **Capability**: Time-evolving block decimation and phi-fold tensor compression for large spaces.
- **Current owner**: `chronus.v33.compression` (chronus/v33/compression)
- **Symbol**: `chronus.v33.compression:run_tebd`
- **Evidence**: `unit: tests/test_july_chronos_mapping.py::test_v33_compression_surface`; `invariant: tests/test_july_chronos_mapping.py::test_tebd_step_preserves_state_norm`; `integration: tests/test_chronus_v33/test_memory.py::test_mps_ghz_compression`
- **Claim boundary**: Finite-bond-dimension TEBD with measured truncation and energy reports; convergence claims come from the run report, not assertion.

### `chronos_control_feedback` — elevated

- **Historical surface**: `QuantumController pulses and ClosedLoopController feedback` (src.chronos.control)
- **Capability**: Pulse application, frequency tuning, drift evolution, readout and closed-loop feedback control.
- **Current owner**: `chronus.v33.control` (chronus/v33/control)
- **Symbol**: `chronus.v33.control:ClosedLoopController`
- **Evidence**: `unit: tests/test_july_chronos_mapping.py::test_v33_control_surface`; `invariant: tests/test_july_chronos_mapping.py::test_control_evolution_preserves_norm`; `integration: tests/test_july_chronos_mapping.py::test_closed_loop_step_produces_feedback`
- **Claim boundary**: Exact state evolution under declared Hamiltonians and pulses; no physical control electronics is implied.

### `chronos_environment_models` — elevated

- **Historical surface**: `decoherence, thermal environment, cryogenic environment` (src.chronos.environment)
- **Capability**: Lindblad dissipation, amplitude damping and thermal/cryogenic environment models.
- **Current owner**: `chronus.v33.environment` (chronus/v33/environment)
- **Symbol**: `chronus.v33.environment:CryogenicEnvironment`
- **Evidence**: `unit: tests/test_july_chronos_mapping.py::test_v33_environment_surface`; `invariant: tests/test_july_chronos_mapping.py::test_amplitude_damping_preserves_trace`; `integration: tests/test_july_chronos_mapping.py::test_cryogenic_environment_reports`
- **Claim boundary**: Exact Kraus/Lindblad channels on declared density matrices; no device noise characterization is claimed.

### `chronos_field_drives` — elevated

- **Historical surface**: `laser and microwave field drives` (src.chronos.fields)
- **Capability**: Coherent/displacement laser states and microwave Rabi drive evolution.
- **Current owner**: `chronus.v33.fields` (chronus/v33/fields)
- **Symbol**: `chronus.v33.fields:CoherentLaser`
- **Evidence**: `unit: tests/test_july_chronos_mapping.py::test_v33_fields_surface`; `invariant: tests/test_july_chronos_mapping.py::test_rabi_evolve_preserves_norm`; `integration: tests/test_july_chronos_mapping.py::test_microwave_drive_rotates_population`
- **Claim boundary**: Deterministic field-driven state evolution in software; no lab instruments are driven.

### `chronos_engine_evolution` — elevated

- **Historical surface**: `ChronosEngine, EvolutionEngine, ErrorMitigationProcessor, HamiltonianLibrary, M32Manifold` (src.chronos.engine, src.chronos.evolution_engine, src.chronos.emp, src.chronos.hamiltonian, src.chronos.manifold)
- **Capability**: The orchestrating engine, evolution engine, error-mitigation processor, Hamiltonian library and M32 manifold.
- **Current owner**: `chronus.v33` (chronus/v33)
- **Symbol**: `chronus.v33:ChronosEngine`
- **Evidence**: `unit: tests/test_july_chronos_mapping.py::test_v33_engine_surface`; `invariant: tests/test_chronus_v33/test_gap_close.py::test_engine_default_path_unchanged_energy`; `integration: tests/test_chronus_v33/test_gap_close.py::test_engine_emp_path_smoke`
- **Claim boundary**: Engine outputs are computed states and reports; performance numbers come only from measured paths.

### `chronos_qsdl_pipeline` — elevated

- **Historical surface**: `QSDLParser and QSDLCompiler scene pipeline` (src.chronos.qsdl_parser)
- **Capability**: Quantum scene description language parsing and compilation into validated scenes.
- **Current owner**: `chronus.v33` (chronus/v33)
- **Symbol**: `chronus.v33:QSDLCompiler`
- **Evidence**: `unit: tests/test_july_chronos_mapping.py::test_v33_qsdl_surface`; `invariant: tests/test_july_chronos_mapping.py::test_qsdl_default_scene_is_stable`; `integration: tests/test_july_chronos_mapping.py::test_qsdl_compile_produces_scene_objects`
- **Claim boundary**: The compiler validates declared scenes; scene contents are configuration, not measured hardware evidence.

### `chronos_weak_measurement` — elevated

- **Historical surface**: `WeakMeasurementSession, uhlmann_fidelity, bayesian_inversion` (src.chronos.weak_measurement)
- **Capability**: Weak-measurement sessions, Uhlmann fidelity and Bayesian inversion of measurement records.
- **Current owner**: `chronus.v33` (chronus/v33/weak_measurement.py)
- **Symbol**: `chronus.v33:WeakMeasurementSession`
- **Evidence**: `unit: tests/test_chronus_v33/test_gap_close.py::test_weak_measurement_self_test`; `invariant: tests/test_chronus_v33/test_gap_close.py::test_weak_measurement_kraus_preserves_trace`; `integration: tests/test_chronus_v33/test_gap_close.py::test_bayesian_inversion_high_fidelity_small_epsilon`
- **Claim boundary**: Statistical estimation over simulated measurement records; no physical meter is read.

### `chronos_theory_reports` — elevated

- **Historical surface**: `theory report surfaces (run_unbuilt_maths and domain reports)` (src.chronos.theory)
- **Capability**: Consolidated reporting over the archived theory modules.
- **Current owner**: `chronus.v33.theory` (chronus/v33/theory)
- **Symbol**: `chronus.v33.theory:run_unbuilt_maths`
- **Evidence**: `unit: tests/test_july_chronos_mapping.py::test_v33_theory_surface`; `invariant: tests/test_chronus_v33/test_research_reconciliation.py::test_every_documented_claim_is_dispositioned_and_sourced`; `integration: tests/test_chronus_v33/test_research_registry.py::test_research_registry_is_source_linked_and_executable`
- **Claim boundary**: Theory reports enumerate declared material with measured statuses; they assert no unmeasured result.

### `qaoa_optimize` — adapter-added

- **Historical surface**: `qaoa_optimize` (euclid.pythagoras.quantum.pulvini_enterprise.quantum_formalism)
- **Capability**: QAOA optimisation facade over a small problem instance.
- **Current owner**: `turing_universal_quantum_computer.july_compat` (turing_universal_quantum_computer/turing_universal_quantum_computer/july_compat.py)
- **Symbol**: `turing_universal_quantum_computer.july_compat:QuantumAccelerationEngine`
- **Evidence**: `unit: tests/test_july_capability_gap_analysis.py::test_qaoa_maxcut_recovers_triangle_optimum`; `invariant: tests/test_july_capability_gap_analysis.py::test_qaoa_state_is_normalized_and_angles_bounded`; `integration: tests/test_july_capability_gap_analysis.py::test_qaoa_end_to_end_result_contract_and_fail_closed`
- **Claim boundary**: Bounded exact MaxCut QAOA on <= max_qubits nodes with deterministic grid+refine angle selection; the result record cannot claim speedup, hardware, or consensus authority.

### `optimizer_composition_strategy` — adapter-added

- **Historical surface**: `CompositionStrategy` (euclid.pythagoras.quantum.pulvini_enterprise.quantum_optimizer)
- **Capability**: Composition of optimiser passes over one parameter vector.
- **Current owner**: `turing_universal_quantum_computer.july_compat` (turing_universal_quantum_computer/turing_universal_quantum_computer/july_compat.py)
- **Symbol**: `turing_universal_quantum_computer.july_compat:CompositionStrategy`
- **Evidence**: `unit: tests/test_july_capability_gap_analysis.py::test_composition_strategy_orders_and_reports_stages`; `invariant: tests/test_july_capability_gap_analysis.py::test_composition_is_deterministic_and_validates_inputs`; `integration: tests/test_july_capability_gap_analysis.py::test_composition_integrates_with_canonical_vqe_objective`
- **Claim boundary**: Sequential deterministic composition of software optimiser stages; per-stage objective values are reported, no acceleration is asserted.

### `phi_recursive_operator` — elevated

- **Historical surface**: `PhiRecursiveOperator, PHI` (euclid.pythagoras.quantum.pulvini_enterprise.formal)
- **Capability**: The recursive golden-ratio operator primitive used by the July formal layer.
- **Current owner**: `quantum_compute_substrate.pulvini` (quantum_compute_substrate/pulvini/pulvini_scaling.py)
- **Symbol**: `quantum_compute_substrate.pulvini.pulvini_scaling:PulviniOperator`
- **Evidence**: `unit: quantum_compute_substrate/tests/test_pulvini.py::TestEdgeCasesAndStability::test_fibonacci_split_sums_to_dim`; `invariant: quantum_compute_substrate/tests/test_pulvini.py::TestGoldenRatioInvariants::test_phi_squared_identity`; `integration: quantum_compute_substrate/tests/test_pulvini.py::TestReconstructionErrorBounds::test_multi_level_fold_roundtrip`
- **Claim boundary**: The operator performs phi-recursive partition with measured reconstruction error; no operator-algebra law beyond the tested fold/unfold contracts is claimed.

### `pulvini_scaling_audit` — elevated

- **Historical surface**: `PulviniAuditEnvelope` (euclid.pythagoras.quantum.pulvini_enterprise.pulvini_scaling)
- **Capability**: Deterministic audit envelope for phi-scaled reductions.
- **Current owner**: `quantum_compute_substrate.pulvini` (quantum_compute_substrate/pulvini/pulvini_scaling.py)
- **Symbol**: `quantum_compute_substrate.pulvini.pulvini_scaling:PulviniAuditEnvelope`
- **Evidence**: `unit: quantum_compute_substrate/tests/test_pulvini.py::TestSpectralGapPreservation::test_audit_envelope_fields_populated`; `invariant: quantum_compute_substrate/tests/test_pulvini.py::TestQuantumDynamics::test_norm_drift_field_populated`; `integration: quantum_compute_substrate/tests/test_pulvini.py::TestPythagorasOrchestrator::test_routing_audit_fields_present`
- **Claim boundary**: The envelope reports measured dimensions, error bounds and gap deltas; it never asserts preservation without measurement.

### `regenerative_fault_taxonomy` — superseded

- **Historical surface**: `FaultSeverity` (euclid.pythagoras.quantum.pulvini_enterprise.regenerative)
- **Capability**: Fault taxonomy used by the fault-injection contract.
- **Current owner**: `salamander` (salamander/models.py)
- **Evidence**: `redirect: tests/test_july_capability_gap_analysis.py::test_retired_surfaces_have_executable_redirects`
- **Claim boundary**: Severity is an incident-health classification; it does not inject faults.
- **Redirect**: `salamander.models.Severity`
- **Retirement reason**: Arbitrary fault injection/regeneration was superseded by checkpoint-tamper detection plus the Salamander severity ladder.

### `regenerative_invariant_checks` — superseded

- **Historical surface**: `verify_invariants` (euclid.pythagoras.quantum.pulvini_enterprise.regenerative)
- **Capability**: Post-fault invariant verification entry point.
- **Current owner**: `euclid.adapter` (euclid/adapter.py)
- **Evidence**: `redirect: tests/test_july_capability_gap_analysis.py::test_retired_surfaces_have_executable_redirects`
- **Claim boundary**: Verification is read-only; it does not claim regeneration.
- **Redirect**: `euclid.adapter.EuclidEngineAdapter.verify_property_invariants`
- **Retirement reason**: The regenerative fault contract was superseded by checkpoint verification plus the property-invariant suite.

### `runner_ultimate_integration` — superseded

- **Historical surface**: `run_ultimate_integration` (repository root)
- **Capability**: Standalone July integration runner for the full stack.
- **Current owner**: `turing_universal_quantum_computer` (turing_universal_quantum_computer/turing_universal_quantum_computer/july_compat.py)
- **Evidence**: `redirect: tests/test_july_capability_gap_analysis.py::test_retired_surfaces_have_executable_redirects`
- **Claim boundary**: The canonical gate is tests/test_july_capability_gap_analysis.py; the redirect executes the invariant suite.
- **Redirect**: `turing_universal_quantum_computer.run_all_verifications`
- **Retirement reason**: Standalone runners were replaced by the in-repo verification battery and the aggregate conformance gate.

### `runner_1000_qubit_vqc` — superseded

- **Historical surface**: `run_1000_qubit_vqc_integration` (repository root)
- **Capability**: Standalone 1,000-qubit + VQC integration runner.
- **Current owner**: `turing_universal_quantum_computer` (turing_universal_quantum_computer/turing_universal_quantum_computer/phi_machine.py)
- **Evidence**: `redirect: tests/test_july_capability_gap_analysis.py::test_retired_surfaces_have_executable_redirects`
- **Claim boundary**: Verification replays the discriminating signed-Pauli checks; it does not mine.
- **Redirect**: `turing_universal_quantum_computer.run_1000_qubit_verification`
- **Retirement reason**: The runner was consolidated into the canonical 1,000-qubit verification entry point.

### `runner_close_gaps` — superseded

- **Historical surface**: `close_gaps_test` (repository root)
- **Capability**: Standalone gap-closure test driver.
- **Current owner**: `chronus.v33` (chronus/v33/test_harness.py)
- **Evidence**: `redirect: tests/test_july_capability_gap_analysis.py::test_retired_surfaces_have_executable_redirects`
- **Claim boundary**: The harness reports self-test outcomes; coverage claims come from the test suite, not the runner name.
- **Redirect**: `chronus.v33.test_harness.ChronosTestHarness`
- **Retirement reason**: The v33 consolidation moved gap closure into the executable test harness and the pytest suites.

### `runner_benchmarks` — superseded

- **Historical surface**: `run_benchmarks` (benchmarks)
- **Capability**: Standalone benchmark driver script.
- **Current owner**: `benchmarks` (benchmarks/common.py)
- **Evidence**: `redirect: tests/test_july_capability_gap_analysis.py::test_retired_surfaces_have_executable_redirects`
- **Claim boundary**: Benchmarks are measured software timings; no hardware superiority is implied.
- **Redirect**: `benchmarks.common`
- **Retirement reason**: Benchmarking moved to the benchmarks package with deterministic RNG and CI statistics; claims run through the benchmark tests.

### `example_memory_integration` — superseded

- **Historical surface**: `memory_integration` (examples)
- **Capability**: Example wiring of the July memory stack.
- **Current owner**: `chronus.v33.memory` (chronus/v33/memory)
- **Evidence**: `redirect: tests/test_july_capability_gap_analysis.py::test_retired_surfaces_have_executable_redirects`
- **Claim boundary**: Self-tests verify the software models only.
- **Redirect**: `chronus.v33.memory.run_memory_self_tests`
- **Retirement reason**: The example was consolidated into the canonical memory self-test battery.

### `tests_geodesic_historical` — superseded

- **Historical surface**: `test_geodesic_tensor_engine, test_geodesic_tensor_engine_extensions` (/data/raw/hyba_mining_review_20261001_v1/geodesic)
- **Capability**: July Geodesic engine test files.
- **Current owner**: `python_backend.core_modules` (python_backend/core_modules/geodesic_tensor_engine.py)
- **Evidence**: `redirect: tests/test_july_capability_gap_analysis.py::test_retired_surfaces_have_executable_redirects`
- **Claim boundary**: Current gates supersede the archived copies; historical totals are provenance, not CI evidence.
- **Redirect**: `python_backend.core_modules.geodesic_tensor_engine`
- **Retirement reason**: The canonical geodesic engine is gated by the in-checkout geodesic and consolidation test suites.

### `tests_pulvini_historical` — superseded

- **Historical surface**: `test_pulvini_completion, test_pulvini_use_cases` (/data/raw/hyba_mining_review_20261001_v1/pulvini)
- **Capability**: July PULVINI completion/use-case test files.
- **Current owner**: `quantum_compute_substrate.pulvini` (quantum_compute_substrate/pulvini)
- **Evidence**: `redirect: tests/test_july_capability_gap_analysis.py::test_retired_surfaces_have_executable_redirects`
- **Claim boundary**: Current gates supersede the archived copies; historical totals are provenance, not CI evidence.
- **Redirect**: `quantum_compute_substrate.pulvini`
- **Retirement reason**: PULVINI semantics are gated by quantum_compute_substrate/tests/test_pulvini.py.

### `test_phi_quantum_machine_historical` — superseded

- **Historical surface**: `test_phi_quantum_machine` (/data/raw/hyba_mining_review_20261001_v1/vqc)
- **Capability**: July 1,000-qubit machine test file.
- **Current owner**: `turing_universal_quantum_computer` (turing_universal_quantum_computer/turing_universal_quantum_computer/phi_quantum_machine.py)
- **Evidence**: `redirect: tests/test_july_capability_gap_analysis.py::test_retired_surfaces_have_executable_redirects`
- **Claim boundary**: Current gates supersede the archived copy; historical totals are provenance, not CI evidence.
- **Redirect**: `turing_universal_quantum_computer.phi_quantum_machine`
- **Retirement reason**: The machine is gated by turing_universal_quantum_computer/tests/test_phi_quantum_machine_consolidation.py.

### `test_vqc_phi_grover_historical` — superseded

- **Historical surface**: `test_vqc_phi_grover` (/data/raw/hyba_mining_review_20261001_v1/vqc)
- **Capability**: July phi-VQC test file.
- **Current owner**: `turing_universal_quantum_computer` (turing_universal_quantum_computer/turing_universal_quantum_computer/phi_vqc.py)
- **Evidence**: `redirect: tests/test_july_capability_gap_analysis.py::test_retired_surfaces_have_executable_redirects`
- **Claim boundary**: The VQC orders supplied candidates only; it never creates proofs.
- **Redirect**: `turing_universal_quantum_computer.phi_vqc`
- **Retirement reason**: The VQC ranker is gated by the consolidation and variational test suites.

### `module_euclid_script` — superseded

- **Historical surface**: `euclid` (repository root)
- **Capability**: Top-level July euclid.py driver module.
- **Current owner**: `euclid.adapter` (euclid/adapter.py)
- **Evidence**: `redirect: tests/test_july_capability_gap_analysis.py::test_retired_surfaces_have_executable_redirects`
- **Claim boundary**: The adapter reports cognition-layer metrics; mining authority stays with the hash pipeline.
- **Redirect**: `euclid.adapter.EuclidEngineAdapter`
- **Retirement reason**: The loose script was consolidated into the EuclidEngineAdapter intelligence surface.

### `module_property_invariants` — superseded

- **Historical surface**: `property_invariants` (repository root)
- **Capability**: Top-level July property_invariants.py module.
- **Current owner**: `turing_universal_quantum_computer` (turing_universal_quantum_computer/turing_universal_quantum_computer/property_invariants.py)
- **Evidence**: `redirect: tests/test_july_capability_gap_analysis.py::test_retired_surfaces_have_executable_redirects`
- **Claim boundary**: The suite reports pass/fail counts it actually executed; no coverage beyond its checks is implied.
- **Redirect**: `turing_universal_quantum_computer.property_invariants.InvariantTestSuite`
- **Retirement reason**: The loose module was consolidated into the canonical InvariantTestSuite.

## Defects found and fixed during this analysis

1. `chronus/v33/academic/caltech.py::_build_stabilizers` emitted boundary
   checks that anti-commuted with the bulk plaquettes (weight-1 checks
   inside opposite-type plaquettes). Replaced with the diagonal-corner
   weight-2 boundary set X{(1,2),(6,7)} / Z{(0,3),(5,8)}: all 8
   stabilizers commute, the code space has dimension 2 (one logical
   qubit), and `verify_stabilizer_algebra` passes end-to-end.
   `test_surface_code_decodes_single_error` was updated to assert the
   real decoder contract (correction cancels the syndrome), because
   boundary-degenerate single errors legitimately share syndromes and a
   distance-3 code cannot return the identical error for every qubit.
2. `turing_universal_quantum_computer/backends::_selection_order`
   leaked non-Clifford programs to approximate backends at wide width
   instead of refusing. Selection now fails closed when no declared
   backend supports the program.
3. `july_compat` was missing the `qaoa_optimize`, `CompositionStrategy`,
   and several redirect surfaces the July inventory references; they are
   now implemented as bounded adapters with measured result records
   (no speedup, hardware, or consensus-authority claims).
4. `salamander/control_plane.py::execute` degraded structural contract
   violations (`FailClosed` for unregistered handlers, missing
   idempotency keys) into a FAILED ActionResult instead of propagating.
   FailClosed now propagates after an `action-rejected` ledger record.
5. `euclid/runtime.py::restore` re-opened the state-dir sqlite a second
   time and discarded the first handle; `Intelligence/pythia_store.py`
   wrote its snapshot into a directory it never created. Both leaked
   handles / broke close() and tempdir cleanup on Windows.
6. `euclid` cognition never consumed `problem["strategy"]` or
   `problem["representation_evidence"]`, `AblationConfig` had no
   `mathematical_structure` switch for the v16 search skills, and the
   reachability matrix had no rule that promoted `toe.world_model` to
   FEEDBACK_CLOSED or `euclid.memory_database` to TRANSFER_VERIFIED.
   `hyba_substrate` task contracts hard-failed on any new measured
   action; `ExperienceSuperlearner.extend_task_actions` now grows the
   declared action set through an audited checkpointed path.
7. `StabilizerState.measure` forced outcome 0 on deterministic
   qubits and then raised; the canonical 0 convention now applies only
   to degenerate measurements, deterministic ones return the actual
   outcome.
8. `tests/test_backend_decision_evidence.py` left a bare ModuleType in
   `sys.modules["chronus.mla1517.mining.coordinator"]`, breaking every
   later import from that module; tearDown now restores the real
   module.
9. `scripts/import_audit.py` resolved distribution directories after
   the repo root, so `turing_universal_quantum_computer/` (which has a
   pyproject and stray .py files) shadowed its inner package. `_dist_base`
   now prefers dist dirs that actually resolve to a package.
