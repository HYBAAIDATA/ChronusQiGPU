"""Regenerate the July 2026 capability gap manifest deterministically.

The manifest is byte-stable: ``json.dumps(indent=2, ensure_ascii=False) + "\n"``.
This script owns the entry inventory so additions stay schema-valid.

The regeneration is idempotent: managed entries are upserted by ``id`` in
place, so repeated runs produce the same file. ``--check`` verifies the
on-disk manifest matches the regenerated output without writing — exit 1
on drift.
"""

import json
import sys

PATH = "manifests/july_2026_capability_gap_analysis.json"


def main() -> None:
    check = "--check" in sys.argv[1:]
    with open(PATH, encoding="utf-8") as handle:
        document = json.load(handle)
    entries = document["entries"]
    by_id = {entry["id"]: entry for entry in entries}

    def active(entry_id, src, surface, hist, owner, path, symbol, tests, boundary, status):
        return {
            "id": entry_id,
            "source_module": src,
            "public_surface": surface,
            "historical_capability": hist,
            "current_owner": owner,
            "current_path": path,
            "status": status,
            "symbol": symbol,
            "evidence_tests": [{"kind": kind, "nodeid": nodeid} for kind, nodeid in tests],
            "claim_boundary": boundary,
            "redirect": "",
            "retirement_reason": "",
        }

    def retired(entry_id, src, surface, hist, owner, path, redirect, reason, boundary):
        return {
            "id": entry_id,
            "source_module": src,
            "public_surface": surface,
            "historical_capability": hist,
            "current_owner": owner,
            "current_path": path,
            "status": "superseded",
            "symbol": "",
            "evidence_tests": [
                {
                    "kind": "redirect",
                    "nodeid": "tests/test_july_capability_gap_analysis.py::"
                    "test_retired_surfaces_have_executable_redirects",
                }
            ],
            "claim_boundary": boundary,
            "redirect": redirect,
            "retirement_reason": reason,
        }

    # hamiltonian_reduction: real tested implementation exists in
    # quantum_compute_substrate.pulvini — reclassify retired -> elevated.
    entry = by_id["hamiltonian_reduction"]
    entry.update(
        {
            "status": "elevated",
            "current_owner": "quantum_compute_substrate.pulvini",
            "current_path": "quantum_compute_substrate/pulvini/pulvini_scaling.py",
            "symbol": "quantum_compute_substrate.pulvini.pulvini_scaling:PulviniOperator",
            "evidence_tests": [
                {
                    "kind": "unit",
                    "nodeid": "quantum_compute_substrate/tests/test_pulvini.py::"
                    "TestSpectralGapPreservation::test_rejects_non_square",
                },
                {
                    "kind": "invariant",
                    "nodeid": "quantum_compute_substrate/tests/test_pulvini.py::"
                    "TestSpectralGapPreservation::test_gap_preserved_dim_16",
                },
                {
                    "kind": "integration",
                    "nodeid": "quantum_compute_substrate/tests/test_pulvini.py::"
                    "TestSubstrateIntegration::test_orchestrator_hamiltonian_from_cathedral_pauli",
                },
            ],
            "claim_boundary": (
                "SVD projection into the phi^2-complement subspace with a measured "
                "spectral-gap delta and Frobenius reconstruction bound; the audit "
                "declares is_reversible=False for the Hamiltonian path."
            ),
            "redirect": "",
            "retirement_reason": "",
        }
    )

    entry = by_id["hamiltonian_result_record"]
    entry.update(
        {
            "status": "elevated",
            "current_owner": "quantum_compute_substrate.pulvini",
            "current_path": "quantum_compute_substrate/pulvini/pulvini_scaling.py",
            "symbol": "quantum_compute_substrate.pulvini.pulvini_scaling:PulviniAuditEnvelope",
            "evidence_tests": [
                {
                    "kind": "unit",
                    "nodeid": "quantum_compute_substrate/tests/test_pulvini.py::"
                    "TestSpectralGapPreservation::test_audit_envelope_fields_populated",
                },
                {
                    "kind": "invariant",
                    "nodeid": "quantum_compute_substrate/tests/test_pulvini.py::"
                    "TestQuantumDynamics::test_norm_drift_field_populated",
                },
                {
                    "kind": "integration",
                    "nodeid": "quantum_compute_substrate/tests/test_pulvini.py::"
                    "TestPythagorasOrchestrator::test_routing_audit_fields_present",
                },
            ],
            "claim_boundary": (
                "The audit envelope reports measured dimensions, reconstruction "
                "error, spectral-gap delta and norm drift; it does not claim "
                "spectral preservation."
            ),
            "redirect": "",
            "retirement_reason": "",
        }
    )

    new_entries = [
        active(
            "chronos_academic_integrations",
            "src.chronos.academic",
            "academic integrations (Caltech topological/surface-code/Ising-anyon, "
            "Cambridge PINN/GQN/RL, CERN cavity-QED/QFT/LHC, MIT fault-tolerant "
            "control, Jaynes-Cummings, NIST benchmark, TokyoTech metrology)",
            "Deterministic physics-model integrations used for enhancement and "
            "verification experiments.",
            "chronus.v33.academic",
            "chronus/v33/academic",
            "chronus.v33.academic:AcademicChronosEngine",
            [
                ("unit", "chronus/tests/test_july_chronos_mapping.py::test_v33_academic_surface"),
                (
                    "invariant",
                    "chronus/tests/test_chronus_v33/test_academic.py::test_uhlmann_fidelity_self",
                ),
                (
                    "integration",
                    "chronus/tests/test_chronus_v33/test_academic_integration.py::"
                    "test_academic_engine_end_to_end",
                ),
            ],
            "Software model facades executing deterministic computations; no lab "
            "hardware access or published-result replication is claimed.",
            "elevated",
        ),
        active(
            "chronos_memory_substrate",
            "src.chronos.memory",
            "QRAM, QSVT, block-encoding, MPS store, neural-combine memory, "
            "memory hierarchy, table memory",
            "Memory primitives: quantum random access, singular-value transform, "
            "block encodings, MPS storage and learned index combination.",
            "chronus.v33.memory",
            "chronus/v33/memory",
            "chronus.v33.memory:MemoryHierarchy",
            [
                ("unit", "chronus/tests/test_july_chronos_mapping.py::test_v33_memory_surface"),
                (
                    "invariant",
                    "chronus/tests/test_chronus_v33/test_memory.py::test_table_qram_roundtrip",
                ),
                (
                    "integration",
                    "chronus/tests/test_chronus_v33/test_memory.py::test_hierarchy_pipeline",
                ),
            ],
            "Exact software models of the memory primitives; no hardware QRAM or "
            "physical qubit array is claimed.",
            "elevated",
        ),
        active(
            "chronos_tebd_compression",
            "src.chronos.compression",
            "TEBD time evolution, phi-fold compression, large-Hilbert-space handling",
            "Time-evolving block decimation and phi-fold tensor compression for " "large spaces.",
            "chronus.v33.compression",
            "chronus/v33/compression",
            "chronus.v33.compression:run_tebd",
            [
                ("unit", "chronus/tests/test_july_chronos_mapping.py::test_v33_compression_surface"),
                (
                    "invariant",
                    "chronus/tests/test_july_chronos_mapping.py::test_tebd_step_preserves_state_norm",
                ),
                (
                    "integration",
                    "chronus/tests/test_chronus_v33/test_memory.py::test_mps_ghz_compression",
                ),
            ],
            "Finite-bond-dimension TEBD with measured truncation and energy "
            "reports; convergence claims come from the run report, not assertion.",
            "elevated",
        ),
        active(
            "chronos_control_feedback",
            "src.chronos.control",
            "QuantumController pulses and ClosedLoopController feedback",
            "Pulse application, frequency tuning, drift evolution, readout and "
            "closed-loop feedback control.",
            "chronus.v33.control",
            "chronus/v33/control",
            "chronus.v33.control:ClosedLoopController",
            [
                ("unit", "chronus/tests/test_july_chronos_mapping.py::test_v33_control_surface"),
                (
                    "invariant",
                    "chronus/tests/test_july_chronos_mapping.py::test_control_evolution_preserves_norm",
                ),
                (
                    "integration",
                    "chronus/tests/test_july_chronos_mapping.py::test_closed_loop_step_produces_feedback",
                ),
            ],
            "Exact state evolution under declared Hamiltonians and pulses; no "
            "physical control electronics is implied.",
            "elevated",
        ),
        active(
            "chronos_environment_models",
            "src.chronos.environment",
            "decoherence, thermal environment, cryogenic environment",
            "Lindblad dissipation, amplitude damping and thermal/cryogenic " "environment models.",
            "chronus.v33.environment",
            "chronus/v33/environment",
            "chronus.v33.environment:CryogenicEnvironment",
            [
                ("unit", "chronus/tests/test_july_chronos_mapping.py::test_v33_environment_surface"),
                (
                    "invariant",
                    "chronus/tests/test_july_chronos_mapping.py::" "test_amplitude_damping_preserves_trace",
                ),
                (
                    "integration",
                    "chronus/tests/test_july_chronos_mapping.py::test_cryogenic_environment_reports",
                ),
            ],
            "Exact Kraus/Lindblad channels on declared density matrices; no device "
            "noise characterization is claimed.",
            "elevated",
        ),
        active(
            "chronos_field_drives",
            "src.chronos.fields",
            "laser and microwave field drives",
            "Coherent/displacement laser states and microwave Rabi drive evolution.",
            "chronus.v33.fields",
            "chronus/v33/fields",
            "chronus.v33.fields:CoherentLaser",
            [
                ("unit", "chronus/tests/test_july_chronos_mapping.py::test_v33_fields_surface"),
                (
                    "invariant",
                    "chronus/tests/test_july_chronos_mapping.py::test_rabi_evolve_preserves_norm",
                ),
                (
                    "integration",
                    "chronus/tests/test_july_chronos_mapping.py::"
                    "test_microwave_drive_rotates_population",
                ),
            ],
            "Deterministic field-driven state evolution in software; no lab "
            "instruments are driven.",
            "elevated",
        ),
        active(
            "chronos_engine_evolution",
            "src.chronos.engine, src.chronos.evolution_engine, src.chronos.emp, "
            "src.chronos.hamiltonian, src.chronos.manifold",
            "ChronosEngine, EvolutionEngine, ErrorMitigationProcessor, "
            "HamiltonianLibrary, M32Manifold",
            "The orchestrating engine, evolution engine, error-mitigation "
            "processor, Hamiltonian library and M32 manifold.",
            "chronus.v33",
            "chronus/v33",
            "chronus.v33:ChronosEngine",
            [
                ("unit", "chronus/tests/test_july_chronos_mapping.py::test_v33_engine_surface"),
                (
                    "invariant",
                    "chronus/tests/test_chronus_v33/test_gap_close.py::"
                    "test_engine_default_path_unchanged_energy",
                ),
                (
                    "integration",
                    "chronus/tests/test_chronus_v33/test_gap_close.py::test_engine_emp_path_smoke",
                ),
            ],
            "Engine outputs are computed states and reports; performance numbers "
            "come only from measured paths.",
            "elevated",
        ),
        active(
            "chronos_qsdl_pipeline",
            "src.chronos.qsdl_parser",
            "QSDLParser and QSDLCompiler scene pipeline",
            "Quantum scene description language parsing and compilation into " "validated scenes.",
            "chronus.v33",
            "chronus/v33",
            "chronus.v33:QSDLCompiler",
            [
                ("unit", "chronus/tests/test_july_chronos_mapping.py::test_v33_qsdl_surface"),
                (
                    "invariant",
                    "chronus/tests/test_july_chronos_mapping.py::test_qsdl_default_scene_is_stable",
                ),
                (
                    "integration",
                    "chronus/tests/test_july_chronos_mapping.py::"
                    "test_qsdl_compile_produces_scene_objects",
                ),
            ],
            "The compiler validates declared scenes; scene contents are "
            "configuration, not measured hardware evidence.",
            "elevated",
        ),
        active(
            "chronos_weak_measurement",
            "src.chronos.weak_measurement",
            "WeakMeasurementSession, uhlmann_fidelity, bayesian_inversion",
            "Weak-measurement sessions, Uhlmann fidelity and Bayesian inversion of "
            "measurement records.",
            "chronus.v33",
            "chronus/v33/weak_measurement.py",
            "chronus.v33:WeakMeasurementSession",
            [
                (
                    "unit",
                    "chronus/tests/test_chronus_v33/test_gap_close.py::" "test_weak_measurement_self_test",
                ),
                (
                    "invariant",
                    "chronus/tests/test_chronus_v33/test_gap_close.py::"
                    "test_weak_measurement_kraus_preserves_trace",
                ),
                (
                    "integration",
                    "chronus/tests/test_chronus_v33/test_gap_close.py::"
                    "test_bayesian_inversion_high_fidelity_small_epsilon",
                ),
            ],
            "Statistical estimation over simulated measurement records; no "
            "physical meter is read.",
            "elevated",
        ),
        active(
            "chronos_theory_reports",
            "src.chronos.theory",
            "theory report surfaces (run_unbuilt_maths and domain reports)",
            "Consolidated reporting over the archived theory modules.",
            "chronus.v33.theory",
            "chronus/v33/theory",
            "chronus.v33.theory:run_unbuilt_maths",
            [
                ("unit", "chronus/tests/test_july_chronos_mapping.py::test_v33_theory_surface"),
                (
                    "invariant",
                    "chronus/tests/test_chronus_v33/test_research_reconciliation.py::"
                    "test_every_documented_claim_is_dispositioned_and_sourced",
                ),
                (
                    "integration",
                    "chronus/tests/test_chronus_v33/test_research_registry.py::"
                    "test_research_registry_is_source_linked_and_executable",
                ),
            ],
            "Theory reports enumerate declared material with measured statuses; "
            "they assert no unmeasured result.",
            "elevated",
        ),
        active(
            "qaoa_optimize",
            "euclid.pythagoras.quantum.pulvini_enterprise.quantum_formalism",
            "qaoa_optimize",
            "QAOA optimisation facade over a small problem instance.",
            "turing_universal_quantum_computer.july_compat",
            "turing_universal_quantum_computer/turing_universal_quantum_computer/july_compat.py",
            "turing_universal_quantum_computer.july_compat:QuantumAccelerationEngine",
            [
                (
                    "unit",
                    "tests/test_july_capability_gap_analysis.py::"
                    "test_qaoa_maxcut_recovers_triangle_optimum",
                ),
                (
                    "invariant",
                    "tests/test_july_capability_gap_analysis.py::"
                    "test_qaoa_state_is_normalized_and_angles_bounded",
                ),
                (
                    "integration",
                    "tests/test_july_capability_gap_analysis.py::"
                    "test_qaoa_end_to_end_result_contract_and_fail_closed",
                ),
            ],
            "Bounded exact MaxCut QAOA on <= max_qubits nodes with deterministic "
            "grid+refine angle selection; the result record cannot claim speedup, "
            "hardware, or consensus authority.",
            "adapter-added",
        ),
        active(
            "optimizer_composition_strategy",
            "euclid.pythagoras.quantum.pulvini_enterprise.quantum_optimizer",
            "CompositionStrategy",
            "Composition of optimiser passes over one parameter vector.",
            "turing_universal_quantum_computer.july_compat",
            "turing_universal_quantum_computer/turing_universal_quantum_computer/july_compat.py",
            "turing_universal_quantum_computer.july_compat:CompositionStrategy",
            [
                (
                    "unit",
                    "tests/test_july_capability_gap_analysis.py::"
                    "test_composition_strategy_orders_and_reports_stages",
                ),
                (
                    "invariant",
                    "tests/test_july_capability_gap_analysis.py::"
                    "test_composition_is_deterministic_and_validates_inputs",
                ),
                (
                    "integration",
                    "tests/test_july_capability_gap_analysis.py::"
                    "test_composition_integrates_with_canonical_vqe_objective",
                ),
            ],
            "Sequential deterministic composition of software optimiser stages; "
            "per-stage objective values are reported, no acceleration is asserted.",
            "adapter-added",
        ),
        active(
            "phi_recursive_operator",
            "euclid.pythagoras.quantum.pulvini_enterprise.formal",
            "PhiRecursiveOperator, PHI",
            "The recursive golden-ratio operator primitive used by the July " "formal layer.",
            "quantum_compute_substrate.pulvini",
            "quantum_compute_substrate/pulvini/pulvini_scaling.py",
            "quantum_compute_substrate.pulvini.pulvini_scaling:PulviniOperator",
            [
                (
                    "unit",
                    "quantum_compute_substrate/tests/test_pulvini.py::"
                    "TestEdgeCasesAndStability::test_fibonacci_split_sums_to_dim",
                ),
                (
                    "invariant",
                    "quantum_compute_substrate/tests/test_pulvini.py::"
                    "TestGoldenRatioInvariants::test_phi_squared_identity",
                ),
                (
                    "integration",
                    "quantum_compute_substrate/tests/test_pulvini.py::"
                    "TestReconstructionErrorBounds::test_multi_level_fold_roundtrip",
                ),
            ],
            "The operator performs phi-recursive partition with measured "
            "reconstruction error; no operator-algebra law beyond the tested "
            "fold/unfold contracts is claimed.",
            "elevated",
        ),
        active(
            "pulvini_scaling_audit",
            "euclid.pythagoras.quantum.pulvini_enterprise.pulvini_scaling",
            "PulviniAuditEnvelope",
            "Deterministic audit envelope for phi-scaled reductions.",
            "quantum_compute_substrate.pulvini",
            "quantum_compute_substrate/pulvini/pulvini_scaling.py",
            "quantum_compute_substrate.pulvini.pulvini_scaling:PulviniAuditEnvelope",
            [
                (
                    "unit",
                    "quantum_compute_substrate/tests/test_pulvini.py::"
                    "TestSpectralGapPreservation::test_audit_envelope_fields_populated",
                ),
                (
                    "invariant",
                    "quantum_compute_substrate/tests/test_pulvini.py::"
                    "TestQuantumDynamics::test_norm_drift_field_populated",
                ),
                (
                    "integration",
                    "quantum_compute_substrate/tests/test_pulvini.py::"
                    "TestPythagorasOrchestrator::test_routing_audit_fields_present",
                ),
            ],
            "The envelope reports measured dimensions, error bounds and gap "
            "deltas; it never asserts preservation without measurement.",
            "elevated",
        ),
        retired(
            "regenerative_fault_taxonomy",
            "euclid.pythagoras.quantum.pulvini_enterprise.regenerative",
            "FaultSeverity",
            "Fault taxonomy used by the fault-injection contract.",
            "salamander",
            "salamander/models.py",
            "salamander.models.Severity",
            "Arbitrary fault injection/regeneration was superseded by "
            "checkpoint-tamper detection plus the Salamander severity ladder.",
            "Severity is an incident-health classification; it does not inject " "faults.",
        ),
        retired(
            "regenerative_invariant_checks",
            "euclid.pythagoras.quantum.pulvini_enterprise.regenerative",
            "verify_invariants",
            "Post-fault invariant verification entry point.",
            "euclid.adapter",
            "euclid/adapter.py",
            "euclid.adapter.EuclidEngineAdapter.verify_property_invariants",
            "The regenerative fault contract was superseded by checkpoint "
            "verification plus the property-invariant suite.",
            "Verification is read-only; it does not claim regeneration.",
        ),
        retired(
            "runner_ultimate_integration",
            "repository root",
            "run_ultimate_integration",
            "Standalone July integration runner for the full stack.",
            "turing_universal_quantum_computer",
            "turing_universal_quantum_computer/turing_universal_quantum_computer/july_compat.py",
            "turing_universal_quantum_computer.run_all_verifications",
            "Standalone runners were replaced by the in-repo verification battery "
            "and the aggregate conformance gate.",
            "The canonical gate is tests/test_july_capability_gap_analysis.py; "
            "the redirect executes the invariant suite.",
        ),
        retired(
            "runner_1000_qubit_vqc",
            "repository root",
            "run_1000_qubit_vqc_integration",
            "Standalone 1,000-qubit + VQC integration runner.",
            "turing_universal_quantum_computer",
            "turing_universal_quantum_computer/turing_universal_quantum_computer/phi_machine.py",
            "turing_universal_quantum_computer.run_1000_qubit_verification",
            "The runner was consolidated into the canonical 1,000-qubit "
            "verification entry point.",
            "Verification replays the discriminating signed-Pauli checks; it does " "not mine.",
        ),
        retired(
            "runner_close_gaps",
            "repository root",
            "close_gaps_test",
            "Standalone gap-closure test driver.",
            "chronus.v33",
            "chronus/v33/test_harness.py",
            "chronus.v33.test_harness.ChronosTestHarness",
            "The v33 consolidation moved gap closure into the executable test "
            "harness and the pytest suites.",
            "The harness reports self-test outcomes; coverage claims come from "
            "the test suite, not the runner name.",
        ),
        retired(
            "runner_benchmarks",
            "benchmarks",
            "run_benchmarks",
            "Standalone benchmark driver script.",
            "benchmarks",
            "benchmarks/common.py",
            "benchmarks.common",
            "Benchmarking moved to the benchmarks package with deterministic RNG "
            "and CI statistics; claims run through the benchmark tests.",
            "Benchmarks are measured software timings; no hardware superiority is " "implied.",
        ),
        retired(
            "example_memory_integration",
            "examples",
            "memory_integration",
            "Example wiring of the July memory stack.",
            "chronus.v33.memory",
            "chronus/v33/memory",
            "chronus.v33.memory.run_memory_self_tests",
            "The example was consolidated into the canonical memory self-test " "battery.",
            "Self-tests verify the software models only.",
        ),
        retired(
            "tests_geodesic_historical",
            "/data/raw/hyba_mining_review_20261001_v1/geodesic",
            "test_geodesic_tensor_engine, test_geodesic_tensor_engine_extensions",
            "July Geodesic engine test files.",
            "python_backend.core_modules",
            "python_backend/core_modules/geodesic_tensor_engine.py",
            "python_backend.core_modules.geodesic_tensor_engine",
            "The canonical geodesic engine is gated by the in-checkout geodesic "
            "and consolidation test suites.",
            "Current gates supersede the archived copies; historical totals are "
            "provenance, not CI evidence.",
        ),
        retired(
            "tests_pulvini_historical",
            "/data/raw/hyba_mining_review_20261001_v1/pulvini",
            "test_pulvini_completion, test_pulvini_use_cases",
            "July PULVINI completion/use-case test files.",
            "quantum_compute_substrate.pulvini",
            "quantum_compute_substrate/pulvini",
            "quantum_compute_substrate.pulvini",
            "PULVINI semantics are gated by " "quantum_compute_substrate/tests/test_pulvini.py.",
            "Current gates supersede the archived copies; historical totals are "
            "provenance, not CI evidence.",
        ),
        retired(
            "test_phi_quantum_machine_historical",
            "/data/raw/hyba_mining_review_20261001_v1/vqc",
            "test_phi_quantum_machine",
            "July 1,000-qubit machine test file.",
            "turing_universal_quantum_computer",
            "turing_universal_quantum_computer/turing_universal_quantum_computer/phi_quantum_machine.py",
            "turing_universal_quantum_computer.phi_quantum_machine",
            "The machine is gated by "
            "turing_universal_quantum_computer/tests/"
            "test_phi_quantum_machine_consolidation.py.",
            "Current gates supersede the archived copy; historical totals are "
            "provenance, not CI evidence.",
        ),
        retired(
            "test_vqc_phi_grover_historical",
            "/data/raw/hyba_mining_review_20261001_v1/vqc",
            "test_vqc_phi_grover",
            "July phi-VQC test file.",
            "turing_universal_quantum_computer",
            "turing_universal_quantum_computer/turing_universal_quantum_computer/phi_vqc.py",
            "turing_universal_quantum_computer.phi_vqc",
            "The VQC ranker is gated by the consolidation and variational test " "suites.",
            "The VQC orders supplied candidates only; it never creates proofs.",
        ),
        retired(
            "module_euclid_script",
            "repository root",
            "euclid",
            "Top-level July euclid.py driver module.",
            "euclid.adapter",
            "euclid/adapter.py",
            "euclid.adapter.EuclidEngineAdapter",
            "The loose script was consolidated into the EuclidEngineAdapter "
            "intelligence surface.",
            "The adapter reports cognition-layer metrics; mining authority stays "
            "with the hash pipeline.",
        ),
        retired(
            "module_property_invariants",
            "repository root",
            "property_invariants",
            "Top-level July property_invariants.py module.",
            "turing_universal_quantum_computer",
            "turing_universal_quantum_computer/turing_universal_quantum_computer/property_invariants.py",
            "turing_universal_quantum_computer.property_invariants.InvariantTestSuite",
            "The loose module was consolidated into the canonical " "InvariantTestSuite.",
            "The suite reports pass/fail counts it actually executed; no coverage "
            "beyond its checks is implied.",
        ),
    ]

    # Upsert managed entries by id, in place: a rerun must reproduce the
    # same manifest, not append a second copy of every managed entry.
    position = {entry["id"]: index for index, entry in enumerate(entries)}
    for entry in new_entries:
        if entry["id"] in position:
            entries[position[entry["id"]]] = entry
        else:
            entries.append(entry)
    rendered = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    if check:
        with open(PATH, encoding="utf-8", newline="\n") as handle:
            current = handle.read()
        if current == rendered:
            print("check: manifest up to date, entries:", len(entries))
            return
        print(
            "check: manifest drifted from the regenerated output; "
            "run scripts/regen_july_manifest.py to rewrite it",
            file=sys.stderr,
        )
        sys.exit(1)
    with open(PATH, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(rendered)
    print("entries:", len(entries))


if __name__ == "__main__":
    main()
