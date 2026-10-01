from __future__ import annotations

import pytest

from turing_universal_quantum_computer import (
    PhiGroverVQC,
    PhiQuantumCircuit,
    PhiQuantumMachine,
    PhiQuantumMachine1000,
    run_1000_qubit_verification,
    verify_ghz_stabilizer_group,
)


def test_qasm_clifford_surface_and_non_clifford_rejection():
    circuit = PhiQuantumCircuit.from_qasm(
        """
        OPENQASM 2.0;
        include "qelib1.inc";
        qreg q[3];
        h q[0];
        cx q[0],q[1];
        s q[2];
        """
    )
    assert circuit.num_qubits == 3
    assert [gate.name for gate in circuit.gates] == ["h", "cx", "s"]
    with pytest.raises(ValueError):
        PhiQuantumCircuit.from_qasm("OPENQASM 2.0;\nqreg q[1];\nt q[0];")


def test_exact_ghz_stabilizer_membership_is_discriminating():
    machine = PhiQuantumMachine(12)
    machine.execute(PhiQuantumCircuit.ghz(12), shots=4, seed=7)
    evidence = verify_ghz_stabilizer_group(machine.register)
    assert evidence["expected_generators"] == 12
    assert evidence["verified_generators"] == 12
    assert evidence["all_generators_verified"] is True

    machine.register.x(0)
    corrupted = verify_ghz_stabilizer_group(machine.register)
    assert corrupted["all_generators_verified"] is False


def test_depth_20_pulvini_checkpoint_restores_exact_digest():
    machine = PhiQuantumMachine(16, fold_depth=20)
    machine.execute(PhiQuantumCircuit.ghz(16), shots=2, seed=1)
    original = machine.state_digest()
    checkpoint = machine.checkpoint()
    assert checkpoint.depth == 20
    assert checkpoint.exact is True
    assert "no physical compression" in checkpoint.claim_boundary

    machine.register.z(3)
    assert machine.state_digest() != original
    machine.restore(checkpoint)
    assert machine.state_digest() == original == checkpoint.digest


def test_algorithm_plans_distinguish_executable_from_metadata():
    machine = PhiQuantumMachine1000()
    qec = machine.plan_algorithm("qec")
    shor = machine.plan_algorithm("shor", problem_qubits=1000)
    qft = machine.plan_algorithm("qft", problem_qubits=1000)
    grover = machine.plan_algorithm("grover", problem_qubits=1000)

    assert qec["status"] == "executable-clifford"
    assert qec["syndrome_channels"] == 1000
    assert shor["status"] == "restricted-on-stabilizer"
    assert shor["max_planned_modulus_bits"] == 500
    assert "non-Clifford" in shor["reason"]
    assert qft["status"] == "planned-on-this-backend"
    assert grover["status"] == "bounded-executable-on-other-turing-backends"


def test_vqc_ranks_only_existing_candidates():
    ranker = PhiGroverVQC()
    candidates = [0, 1, 7, 19, 2**32 - 1]
    result = ranker.rank_candidates(
        {"prevhash": "00" * 32, "ntime": "00000000", "nbits": "1d00ffff"},
        candidates,
    )
    assert result["candidate_set_preserved"] is True
    assert result["proof_authority"] is False
    assert set(result["candidates"]) == set(candidates)
    assert len(result["candidates"]) == len(candidates)

    with pytest.raises(ValueError):
        ranker.rank_candidates({}, [0, 0])
    with pytest.raises(ValueError):
        ranker.rank_candidates({}, [-1])
    with pytest.raises(ValueError):
        ranker.rank_candidates({}, [2**32])


def test_vqc_clifford_skeleton_checkpoint_is_exact():
    report = PhiGroverVQC().verify_quantum_skeleton()
    assert report["logical_qubits"] == 32
    assert report["checkpoint_restore_verified"] is True
    assert report["truth_class"] == "exact-clifford"
    assert report["execution_type"] == "classical_trainable_ranker_with_exact_clifford_skeleton"


def test_full_1000_qubit_production_gate():
    report = run_1000_qubit_verification(shots=2)
    assert report["logical_qubits"] == 1000
    assert report["stabilizer_evidence"]["verified_generators"] == 1000
    assert report["stabilizer_evidence"]["all_generators_verified"] is True
    assert report["pulvini_checkpoint_depth"] == 20
    assert report["pulvini_restore_digest_verified"] is True
    assert report["measurement_correlation_is_evidence"] is False
    assert report["verification_pass"] is True
