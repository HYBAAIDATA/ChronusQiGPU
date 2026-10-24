"""Tests for the 6-phase exact quantum software stack."""

from __future__ import annotations

from fractions import Fraction
import pytest

import turing_universal_quantum_computer as tqc
from turing_universal_quantum_computer.backends.base import Program
from turing_universal_quantum_computer.pipeline import VQCRequest, run_pipeline
from turing_universal_quantum_computer.quantum_library import (
    ExactLaneError,
    QuantumLibrary,
    TRUTH_EXACT,
    audit_exactness,
)
from turing_universal_quantum_computer.software_stack import (
    CouplingMap,
    HybridJobSpec,
    HybridWorkloadOrchestrator,
    build_ansatz_program,
    compile_pulse_schedule,
    decompose_to_basis,
    optimize_program,
    program_from_qasm,
    program_to_qasm,
    qasm_roundtrip_report,
    route_program,
    run_hybrid_workload,
    run_quantum_software_stack,
    run_surface_code_qec_cycle,
    transpile_program,
)
from turing_universal_quantum_computer.verify import program_unitary_columns


# ======================================================================
# Phase 1: High-Level Development (Developer Intent)
# ======================================================================


def test_phase1_build_ansatz_program_axes_and_entanglement():
    for axis in ("x", "y", "z"):
        for pattern in ("linear", "ring", "full"):
            prog = build_ansatz_program(
                3,
                [Fraction(1, 8), Fraction(1, 4), Fraction(3, 8)],
                layers=2,
                axis=axis,
                entangler="cx",
                entanglement=pattern,
            )
            assert prog.n_qubits == 3
            assert len(prog.operations) > 0

    with pytest.raises(ExactLaneError):
        # 1/3 turn does not have a denominator dividing 8 for Clifford+T gate synthesis
        build_ansatz_program(2, [Fraction(1, 3), Fraction(1, 8)])


# ======================================================================
# Phase 2: Intermediate Representation & OpenQASM 2.0 Assembly
# ======================================================================


def test_phase2_openqasm_roundtrip_clifford_t_and_toffoli():
    prog = (
        Program(3)
        .then("h", 0)
        .then("t", 0)
        .then("s", 1)
        .then("sdg", 2)
        .then("cx", 0, 1)
        .then("cz", 1, 2)
        .then("swap", 0, 2)
        .then("ccx", 0, 1, 2)
        .then("tdg", 2)
    )
    report = qasm_roundtrip_report(prog)
    assert report["roundtrip_exact"] is True
    assert report["original_digest"] == report["restored_digest"]
    assert "ccx q[0],q[1],q[2];" in report["qasm"]

    # Executable QASM decomposition expands CCX into 15 Clifford+T gates
    unfolded = Program.from_qasm(prog.to_qasm(), decompose_toffoli=True)
    assert "ccx" not in unfolded.gates()
    assert len(unfolded.operations) == len(prog.operations) - 1 + 15

    # VQCPipeline accepts non-Clifford QASM (including T and CCX) via Program.from_qasm
    vqc_report = run_pipeline(VQCRequest(qasm=prog.to_qasm()))
    assert vqc_report.verdict == "PASS"


# ======================================================================
# Phase 3: Compilation and Transpilation (The Optimizer)
# ======================================================================


def test_phase3_basis_decomposition_exact_unitary_identities():
    prog = (
        Program(3)
        .then("i", 0)
        .then("x", 0)
        .then("y", 1)
        .then("z", 2)
        .then("cz", 0, 1)
        .then("swap", 1, 2)
        .then("ccx", 0, 1, 2)
    )
    # Compare against minimal Clifford+T basis ("h", "t", "tdg", "cx")
    minimal_basis = ("h", "t", "tdg", "cx")
    decomposed = decompose_to_basis(prog, basis_gates=minimal_basis)
    assert decomposed.gates() <= set(minimal_basis)

    # Reference unfolded (replace ccx with 15-gate Clifford+T and verify against decomposed)
    ref = Program.from_qasm(prog.to_qasm(), decompose_toffoli=True)
    assert program_unitary_columns(decomposed) == program_unitary_columns(ref)

    # Also test decomposition into CZ-native basis ("h", "s", "sdg", "t", "tdg", "cz")
    cz_basis = ("h", "s", "sdg", "t", "tdg", "cz")
    cz_decomposed = decompose_to_basis(prog, basis_gates=cz_basis)
    assert cz_decomposed.gates() <= set(cz_basis)
    assert program_unitary_columns(cz_decomposed) == program_unitary_columns(ref)


def test_phase3_toffoli_truth_table_is_exact():
    """Verify the 15-gate Clifford+T CCX decomposition on all 8 computational basis states."""
    from turing_universal_quantum_computer.backends.exact_algebra import ONE, ZERO

    ccx_prog = decompose_to_basis(Program(3).then("ccx", 0, 1, 2))
    cols = program_unitary_columns(ccx_prog)
    assert cols is not None
    # Qubit 0 is bit 0, qubit 1 is bit 1, qubit 2 (target) is bit 2.
    # Only |110> (index 3, bits 0 and 1 set) and |111> (index 7, bits 0,1,2 set) swap!
    for basis_idx in range(8):
        expected_idx = basis_idx ^ 4 if (basis_idx & 0b011) == 0b011 else basis_idx
        col = cols[basis_idx]
        for row_idx, amp in enumerate(col):
            if row_idx == expected_idx:
                assert amp == ONE
            else:
                assert amp == ZERO


def test_phase3_topology_routing_and_unitary_equivalence():
    cmap = CouplingMap.line(4)  # 0 - 1 - 2 - 3
    prog = (
        Program(4)
        .then("h", 0)
        .then("t", 0)
        .then("cx", 0, 3)  # distance 3 apart on line
        .then("cz", 3, 0)  # consecutive gate on same pair reuses layout
        .then("cx", 1, 3)  # distance 2 apart
    )
    routing = route_program(prog, cmap, restore_layout=True)
    assert routing.all_two_qubit_gates_adjacent is True
    assert routing.layout_restored is True
    assert routing.inserted_swaps > 0
    assert program_unitary_columns(routing.routed_program) == program_unitary_columns(prog)


def test_phase3_peephole_and_z_phase_folding_optimizer():
    # t^8 == I, s*sdg == I, h*z*h == x, cx*cx == I
    prog = (
        Program(2)
        .then("t", 0)
        .then("t", 0)
        .then("s", 0)
        .then("z", 0)  # t^2 * s * z = s * s * z = z * z = I
        .then("h", 1)
        .then("z", 1)
        .then("h", 1)  # -> x(1)
        .then("cx", 0, 1)
        .then("cx", 0, 1)  # -> I
    )
    opt = optimize_program(prog)
    assert len(opt.operations) == 1
    assert opt.operations[0].gate == "x"
    assert opt.operations[0].qubits == (1,)
    assert program_unitary_columns(opt) == program_unitary_columns(prog)


def test_phase3_full_transpiler_pipeline():
    cmap = CouplingMap.grid(2, 2)  # 0-1, 0-2, 1-3, 2-3 (0 and 3 are diagonal, distance 2)
    prog = (
        Program(4)
        .then("h", 0)
        .then("y", 1)
        .then("cx", 0, 3)
        .then("t", 3)
        .then("tdg", 3)
    )
    report = transpile_program(prog, coupling_map=cmap)
    assert report.topology_satisfied is True
    assert report.basis_satisfied is True
    assert report.unitary_verified is True
    assert report.unitary_equivalent is True
    assert audit_exactness(report.as_dict()).exact


# ======================================================================
# Phase 4: Quantum Error Correction (QEC) & Fault Tolerance Layer
# ======================================================================


def test_phase4_surface_code_qec_cycle_ancilla_and_decoders():
    # Distance-3 planar surface code corrects any weight-1 X and weight-1 Z error
    report = run_surface_code_qec_cycle(
        distance=3,
        x_error_qubits=(4,),
        z_error_qubits=(7,),
    )
    assert report.data_qubits == 13
    assert report.ancilla_qubits == 12
    assert report.total_tableau_qubits == 25
    assert report.ancilla_matches_gf2_parity is True
    assert report.ancilla_measurements_deterministic is True
    assert report.exact_decoder_succeeded is True
    assert report.union_find_decoder_succeeded is True
    assert report.post_recovery_syndrome_zero is True
    assert report.logical_z_preserved is True
    assert report.code_verified is True
    assert audit_exactness(report.as_dict()).exact


def test_phase4_distance_5_two_qubit_error_correction():
    # Distance-5 planar surface code (41 data qubits + 40 ancillas = 81 tableau qubits)
    # corrects weight-2 X and weight-2 Z errors
    report = run_surface_code_qec_cycle(
        distance=5,
        x_error_qubits=(0, 20),
        z_error_qubits=(3, 15),
    )
    assert report.data_qubits == 41
    assert report.total_tableau_qubits == 81
    assert report.ancilla_matches_gf2_parity is True
    assert report.ancilla_measurements_deterministic is True
    assert report.exact_decoder_succeeded is True
    assert report.post_recovery_syndrome_zero is True
    assert report.logical_z_preserved is True


# ======================================================================
# Phase 5: Quantum Orchestration and Hybrid Workload Scheduling
# ======================================================================


def test_phase5_hybrid_workload_orchestrator_priority_and_receipt_chain():
    orchestrator = HybridWorkloadOrchestrator()
    terms = tuple(QuantumLibrary.ising_terms(2, J=1, g=1))
    orchestrator.submit(
        HybridJobSpec(
            job_id="low-priority-job",
            n_qubits=2,
            pauli_terms=terms,
            candidate_turns=(Fraction(0, 1), Fraction(1, 4)),
            priority=1,
        )
    )
    orchestrator.submit(
        HybridJobSpec(
            job_id="high-priority-job",
            n_qubits=2,
            pauli_terms=terms,
            candidate_turns=(Fraction(0, 1), Fraction(1, 8), Fraction(7, 8)),
            priority=10,
        )
    )
    assert orchestrator.pending_count() == 2
    reports = orchestrator.drain()
    assert [r.job_id for r in reports] == ["high-priority-job", "low-priority-job"]
    for rep in reports:
        assert rep.receipt_chain_verified is True
        assert len(rep.final_receipt_digest) == 64
        assert audit_exactness(rep.as_dict()).exact


# ======================================================================
# Phase 6: Pulse-Level Compilation and Control Software
# ======================================================================


def test_phase6_pulse_compiler_virtual_z_and_channel_alignment():
    prog = (
        Program(2)
        .then("z", 0)
        .then("s", 0)
        .then("t", 0)  # total Virtual-Z on q0 = 1/2 + 1/4 + 1/8 = 7/8 turn in 0 ns
        .then("x", 0)  # 32 ns DRAG pulse on d0
        .then("h", 1)  # 0 ns pre-VZ + 16 ns DRAG + 0 ns post-VZ on d1
        .then("cx", 0, 1)  # aligned at max(32, 16) = 32 ns, duration 64 ns -> ends at 96 ns
    )
    schedule = compile_pulse_schedule(prog, include_readout=True)
    assert schedule.virtual_z_count == 5  # z, s, t on q0 + pre/post VZ for h on q1
    assert schedule.final_frame_phases["q0"] == "7/8"
    assert schedule.final_frame_phases["q1"] == "1/2"
    # Unitary ends at 32 + 64 = 96 ns; readout adds 256 ns -> 352 ns
    assert schedule.total_duration_ns == 352
    assert audit_exactness(schedule.as_dict()).exact


# ======================================================================
# Full 6-Phase Facade & QuantumLibrary Integration
# ======================================================================


def test_full_six_phase_software_stack_and_quantum_library_surface():
    res_qasm = QuantumLibrary.qasm_roundtrip(2, [("h", 0), ("t", 0), ("cx", 0, 1)])
    assert res_qasm.truth_class == TRUTH_EXACT
    assert res_qasm.payload["roundtrip_exact"] is True

    res_trans = QuantumLibrary.transpile(3, [("h", 0), ("cx", 0, 2), ("ccx", 0, 1, 2)])
    assert res_trans.truth_class == TRUTH_EXACT
    assert res_trans.payload["topology_satisfied"] is True
    assert res_trans.payload["unitary_equivalent"] is True

    res_qec = QuantumLibrary.qec_surface_cycle(3, x_error_qubits=(1,), z_error_qubits=(5,))
    assert res_qec.truth_class == TRUTH_EXACT
    assert res_qec.payload["logical_z_preserved"] is True

    res_hyb = QuantumLibrary.hybrid_orchestrate(2, J=1, g=1)
    assert res_hyb.truth_class == TRUTH_EXACT
    assert res_hyb.payload["receipt_chain_verified"] is True

    res_pulse = QuantumLibrary.compile_pulses(2, [("h", 0), ("s", 0), ("cx", 0, 1)])
    assert res_pulse.truth_class == TRUTH_EXACT
    assert res_pulse.payload["total_duration_ns"] == 16 + 64 + 256

    res_stack = QuantumLibrary.software_stack(3, qec_distance=3)
    assert res_stack.truth_class == TRUTH_EXACT
    assert res_stack.payload["all_phases_verified"] is True
    assert res_stack.verify_exactness().exact

    # Lazy export from top-level package
    direct_report = tqc.run_quantum_software_stack(3)
    assert direct_report.all_phases_verified is True


def test_gpu_fleet_hybrid_quantum_workload_and_failover():
    res_fleet = QuantumLibrary.gpu_fleet_workload(
        n_qubits=2,
        J=1,
        g=1,
        worker_count=3,
        lanes_per_worker=4,
        scale_index=15,
        fail_worker_ids=("gpu-worker-1",),
    )
    assert res_fleet.truth_class == TRUTH_EXACT
    assert res_fleet.verify_exactness().exact is True
    payload = res_fleet.payload
    assert payload["total_candidates"] == 8
    fleet_rep = payload["fleet_report"]
    assert fleet_rep["certificate_verified"] is True
    assert fleet_rep["single_vs_distributed_agree"] is True
    assert fleet_rep["custody_committed_count"] == 3
    assert len(fleet_rep["failover_events"]) == 1
    assert fleet_rep["failover_events"][0]["worker_id"] == "gpu-worker-1"
    assert fleet_rep["failover_events"][0]["stale_rejected"] is True

    # Must match the optimal energy and optimal turns of single-node run_hybrid_workload
    single_hyb = QuantumLibrary.hybrid_orchestrate(2, J=1, g=1).payload
    assert payload["optimal_energy_exact"] == single_hyb["optimal_energy_exact"]
    assert payload["optimal_turns"] == single_hyb["optimal_turns"]

