import unittest

import turing_universal_quantum_computer as tqc


class PhiMachineProfileTests(unittest.TestCase):
    def test_ghz_state_uses_discriminating_stabilizer_group_check(self):
        machine = tqc.PhiQuantumMachine1000(64, fold_depth=12)
        result = machine.execute(tqc.PhiQuantumCircuit.ghz(64))
        self.assertEqual(result.gates_executed, 64)
        self.assertTrue(machine.verifies_ghz_stabilizer_group())
        self.assertEqual(result.truth_class, "exact_clifford_tableau")

    def test_checkpoint_roundtrip_and_tamper_detection(self):
        machine = tqc.PhiQuantumMachine1000(32, fold_depth=20)
        result = machine.execute(tqc.PhiQuantumCircuit.ghz(32))
        checkpoint = machine.checkpoint()
        machine.reset()
        machine.restore(checkpoint)
        self.assertEqual(tqc.state_digest(machine.register), result.state_digest)

        broken = tqc.PhiCheckpoint(
            folded_payload=bytes([checkpoint.folded_payload[0] ^ 1]) + checkpoint.folded_payload[1:],
            level_lengths=checkpoint.level_lengths,
            logical_qubits=checkpoint.logical_qubits,
            state_digest=checkpoint.state_digest,
            depth=checkpoint.depth,
        )
        with self.assertRaises(RuntimeError):
            machine.restore(broken)

    def test_seeded_random_clifford_digest_is_reproducible(self):
        first = tqc.seeded_clifford_digest(24, gates=96, seed=20260802)
        second = tqc.seeded_clifford_digest(24, gates=96, seed=20260802)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)

    def test_algorithm_surface_keeps_non_clifford_boundary(self):
        machine = tqc.PhiQuantumMachine1000(1000)
        self.assertEqual(
            machine.plan_algorithm("qec")["execution_status"], "executable_clifford"
        )
        self.assertTrue(machine.plan_algorithm("qec")["executable"])
        shor = machine.plan_algorithm("shor")
        self.assertEqual(shor["execution_status"], "restricted_non_clifford")
        self.assertFalse(shor["executable"])
        self.assertEqual(
            machine.plan_algorithm("qft")["execution_status"],
            "planned_non_clifford_general",
        )

    def test_1000_qubit_corrected_verification_gate(self):
        result = tqc.run_1000_qubit_verification()
        self.assertEqual(result["logical_qubits"], 1000)
        self.assertTrue(result["direct_stabilizer_group_equality"])
        self.assertTrue(result["checkpoint_exact"])
        self.assertFalse(result["ghz_shot_correlation_used_as_evidence"])
        self.assertFalse(result["speedup_claim"])

    def test_qasm_subset_routes_to_turing_stabilizer(self):
        circuit = tqc.PhiQuantumCircuit.from_qasm(
            """
            OPENQASM 2.0;
            include "qelib1.inc";
            qreg q[3];
            h q[0];
            cx q[0],q[1];
            cx q[0],q[2];
            """
        )
        machine = tqc.PhiQuantumMachine1000(3)
        machine.execute(circuit)
        self.assertTrue(machine.verifies_ghz_stabilizer_group())


class MidasVQCTests(unittest.TestCase):
    HEADER = {
        "version": 1,
        "prev_hash": "00" * 32,
        "merkle_root": "11" * 32,
        "ntime": 1234567890,
        "nbits": 0x207FFFFF,
    }

    def test_ranker_has_no_consensus_authority(self):
        ranker = tqc.MidasPhiVQCRanker(tqc.VQCConfig(candidate_count=64, seed=7))
        result = ranker.rank_candidates(self.HEADER, count=64)
        self.assertFalse(result["consensus_authority"])
        self.assertEqual(
            result["execution_class"],
            "classical_variational_ranker_with_clifford_skeleton",
        )

    def test_existing_window_is_only_reordered(self):
        ranker = tqc.MidasPhiVQCRanker(tqc.VQCConfig(seed=9))
        window = list(range(100, 164))
        ordered = ranker.order_existing_window(self.HEADER, window)
        self.assertEqual(sorted(ordered), window)
        self.assertEqual(len(ordered), len(window))
        with self.assertRaises(ValueError):
            ranker.order_existing_window(self.HEADER, [1, -1])

    def test_clifford_skeleton_executes_on_turing_profile(self):
        ranker = tqc.MidasPhiVQCRanker(tqc.VQCConfig(seed=3))
        report = ranker.execute_clifford_skeleton()
        self.assertEqual(report["logical_qubits"], 32)
        self.assertEqual(report["truth_class"], "exact_clifford_tableau")
        self.assertFalse(report["consensus_authority"])


if __name__ == "__main__":
    unittest.main()
