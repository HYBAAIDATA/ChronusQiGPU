"""Falsification tests for the VQC product boundary.

These tests exist to *falsify* claims, not to confirm happy paths.  Each one
pins a boundary the package must not cross:

* exactness — amplitudes and norms are exact, with no tolerance anywhere;
* refusal — out-of-domain programs are refused, never approximated;
* honesty — no result can claim hardware it did not use;
* parity — independent backends agree on the same program;
* determinism — a seed replays identically.

Run: ``python -m pytest tests/test_backend_boundary.py -q``
"""

from __future__ import annotations

import unittest
from fractions import Fraction

from turing_universal_quantum_computer.backends import (
    ExecutionClass,
    Exact,
    ExactFieldBackend,
    ExactStatevector,
    Program,
    Q2,
    QPUBackend,
    QPUClaimError,
    QPUJob,
    QPUUnavailableError,
    StatevectorTooLargeError,
    TruthClass,
    execute,
    gate_names,
    select_backend,
)
from turing_universal_quantum_computer.backends.reference import (
    GATES,
    _check_gate_table,
    _gate_is_unitary,
)
from turing_universal_quantum_computer.capabilities import (
    audit_claims,
    capability_report,
)
from turing_universal_quantum_computer.certificates import (
    WitnessError,
    issue_witness,
    verify_witness,
)


class GatePropertyTests(unittest.TestCase):
    """Gate properties must hold exactly, by algebra rather than tolerance."""

    def test_every_gate_is_exactly_unitary(self):
        _check_gate_table()
        for name, gate in GATES.items():
            with self.subTest(gate=name):
                self.assertTrue(_gate_is_unitary(gate))

    def test_gate_inverse_returns_identity(self):
        pairs = [("h", "h"), ("x", "x"), ("y", "y"), ("z", "z"), ("s", "sdg"), ("t", "tdg")]
        for forward, backward in pairs:
            with self.subTest(gate=forward):
                state = ExactStatevector(1).apply("h", 0).apply(forward, 0).apply(backward, 0).apply("h", 0)
                self.assertTrue(state.is_normalised())
                # H U U^-1 H |0> == |0>
                self.assertEqual(state.amplitudes[0], Exact(Q2(1)))
                self.assertTrue(state.amplitudes[1].is_zero())

    def test_t_is_eighth_root_of_identity(self):
        state = ExactStatevector(1)
        for _ in range(8):
            state.apply("t", 0)
        self.assertTrue(state.is_normalised())
        self.assertEqual(state.amplitudes[0], Exact(Q2(1)))
        self.assertTrue(state.amplitudes[1].is_zero())

    def test_normalisation_is_exact_after_every_gate(self):
        program = (
            Program(3)
            .then("h", 0).then("t", 1).then("cx", 0, 1).then("s", 2)
            .then("tdg", 0).then("cz", 1, 2).then("swap", 0, 2).then("y", 1)
        )
        state = ExactStatevector(3)
        for operation in program.operations:
            if operation.gate in ("cx", "cnot"):
                state.apply_controlled("x", *operation.qubits)
            elif operation.gate == "cz":
                state.apply_controlled("z", *operation.qubits)
            elif operation.gate == "swap":
                state.swap(*operation.qubits)
            else:
                state.apply(operation.gate, *operation.qubits)
            self.assertEqual(state.norm_sq(), Q2(1), operation.gate)


class KnownStateTests(unittest.TestCase):
    """States whose amplitudes are known in closed form."""

    def test_bell_state_amplitudes_are_exact(self):
        state = ExactStatevector(2).apply("h", 0).cnot(0, 1)
        half_sqrt2 = Exact(Q2(0, Fraction(1, 2)))
        self.assertEqual(state.amplitudes[0], half_sqrt2)
        self.assertEqual(state.amplitudes[3], half_sqrt2)
        self.assertTrue(state.amplitudes[1].is_zero())
        self.assertTrue(state.amplitudes[2].is_zero())
        self.assertEqual(state.probabilities()[0], Q2(Fraction(1, 2)))

    def test_ghz_state_has_two_nonzero_amplitudes(self):
        state = ExactStatevector(4).apply("h", 0)
        for qubit in range(3):
            state.cnot(qubit, qubit + 1)
        self.assertEqual(state.support(), [0, 15])
        self.assertEqual(state.entropy_bits([0]), 1.0)
        self.assertFalse(state.is_product_state([0, 1]))

    def test_uniform_superposition_stays_in_the_field(self):
        state = ExactStatevector.uniform_superposition(3)
        self.assertEqual(len(state.support()), 8)
        self.assertTrue(state.is_normalised())
        for probability in state.probabilities():
            self.assertEqual(probability, Q2(Fraction(1, 8)))

    def test_product_state_is_separable(self):
        state = ExactStatevector(2).apply("h", 0)
        # |+>|0>: separable across the cut, yet qubit 0 alone is maximally
        # mixed, so S({0}) = 1 while S({1}) = 0. Entanglement is a property of
        # the cut, not of a qubit.
        self.assertTrue(state.is_product_state([0, 1]))
        self.assertEqual(state.entropy_bits([0]), 1.0)
        self.assertEqual(state.entropy_bits([1]), 0.0)


class AdversarialDimensionTests(unittest.TestCase):
    """Malformed and hostile inputs must be refused, not absorbed."""

    def test_zero_and_negative_registers_refused(self):
        for n in (0, -1, -1000):
            with self.subTest(n=n):
                with self.assertRaises(Exception):
                    ExactStatevector(n)

    def test_non_integer_register_refused(self):
        with self.assertRaises(Exception):
            ExactStatevector(2.5)  # type: ignore[arg-type]

    def test_qubit_index_outside_register_refused(self):
        state = ExactStatevector(2)
        for qubit in (-1, 2, 99):
            with self.subTest(qubit=qubit):
                with self.assertRaises(Exception):
                    state.apply("h", qubit)

    def test_control_equal_to_target_refused(self):
        with self.assertRaises(Exception):
            ExactStatevector(2).apply_controlled("x", 1, 1)

    def test_unknown_gate_refused(self):
        with self.assertRaises(Exception):
            ExactStatevector(2).apply("sqrt_of_not_a_gate", 0)

    def test_program_rejects_out_of_range_qubit(self):
        with self.assertRaises(ValueError):
            Program(2).then("h", 5)

    def test_two_qubit_gate_with_one_qubit_refused(self):
        backend = ExactFieldBackend()
        admission = backend.admit(Program(3).then("cx", 0))
        self.assertFalse(admission.admitted)
        self.assertIn("2 qubits", admission.reason)


class MemoryLimitTests(unittest.TestCase):
    """The materialisation budget is a refusal, never a truncation."""

    def test_oversized_register_is_refused_not_truncated(self):
        backend = ExactFieldBackend(max_amplitudes=1 << 10)
        program = Program(11).then("h", 0)
        admission = backend.admit(program)
        self.assertFalse(admission.admitted)
        self.assertIn("max_amplitudes", admission.reason)
        with self.assertRaises(StatevectorTooLargeError):
            backend.execute(program)

    def test_refusal_is_a_memory_error_subclass(self):
        self.assertTrue(issubclass(StatevectorTooLargeError, MemoryError))

    def test_statevector_budget_is_enforced_at_construction(self):
        with self.assertRaises(StatevectorTooLargeError):
            ExactStatevector(20, max_amplitudes=1 << 5)

    def test_boundary_width_is_admitted(self):
        backend = ExactFieldBackend(max_amplitudes=1 << 6)
        self.assertTrue(backend.admit(Program(6).then("h", 0)).admitted)
        self.assertFalse(backend.admit(Program(7).then("h", 0)).admitted)


class DeterminismTests(unittest.TestCase):
    """A seed must replay identically; the draw must actually be random."""

    def test_same_seed_replays_identically(self):
        state = ExactStatevector(3).apply("h", 0).cnot(0, 1).apply("t", 2).apply("h", 2)
        first = state.sample(500, seed=12345)
        second = state.sample(500, seed=12345)
        self.assertEqual(first, second)

    def test_different_seeds_differ(self):
        state = ExactStatevector(4).apply("h", 0)
        for qubit in range(3):
            state.cnot(qubit, qubit + 1)
        self.assertNotEqual(state.sample(500, seed=1), state.sample(500, seed=2))

    def test_shots_are_conserved(self):
        state = ExactStatevector(2).apply("h", 0)
        counts = state.sample(997, seed=4)
        self.assertEqual(sum(counts.values()), 997)

    def test_marginal_sampling_is_deterministic(self):
        state = ExactStatevector(3).apply("h", 0).cnot(0, 1)
        self.assertEqual(
            state.sample_marginal(300, [0, 1], seed=9),
            state.sample_marginal(300, [0, 1], seed=9),
        )


class SerializationTests(unittest.TestCase):
    """State round-trips must be lossless, including the algebraic field."""

    def test_state_round_trip_is_lossless(self):
        state = ExactStatevector(3).apply("h", 0).cnot(0, 1).apply("t", 2).apply("sdg", 1)
        restored = ExactStatevector.from_json(state.to_json())
        self.assertEqual(restored.dirac(), state.dirac())
        self.assertEqual(restored.norm_sq(), state.norm_sq())
        self.assertEqual(restored.probabilities(), state.probabilities())

    def test_unknown_schema_is_refused(self):
        with self.assertRaises(Exception):
            ExactStatevector.from_dict({"schema": "not.ours", "n_qubits": 1, "amplitudes": []})


class RefusalBoundaryTests(unittest.TestCase):
    """Out-of-domain programs must be refused with a reason, never downgraded."""

    def test_non_clifford_at_wide_width_is_refused(self):
        program = Program(64).then("h", 0).then("t", 0)
        backend, admission = select_backend(program)
        self.assertIsNone(backend)
        self.assertFalse(admission.admitted)

    def test_non_clifford_is_refused_by_the_stabilizer_backend(self):
        from turing_universal_quantum_computer.backends import StabilizerBackend

        backend = StabilizerBackend()
        admission = backend.admit(Program(4).then("h", 0).then("t", 1))
        self.assertFalse(admission.admitted)
        self.assertIn("non-Clifford", admission.reason)

    def test_clifford_at_wide_width_selects_the_tableau(self):
        from turing_universal_quantum_computer.backends import StabilizerBackend

        if not StabilizerBackend().available()[0]:
            self.skipTest("stabilizer engine unavailable")
        backend, admission = select_backend(Program(64).then("h", 0).then("cx", 0, 63))
        self.assertIsNotNone(backend)
        self.assertEqual(backend.name, "stabilizer")
        self.assertTrue(admission.admitted)

    def test_dense_backend_refuses_beyond_its_budget(self):
        backend = ExactFieldBackend(max_amplitudes=1 << 4)
        with self.assertRaises(StatevectorTooLargeError):
            backend.execute(Program(8).then("h", 0))

    def test_no_execution_ever_returns_an_undeclared_approximation(self):
        # At 8 qubits with a 16-amplitude dense budget the program must still be
        # answered exactly -- by a narrower exact backend -- never approximately.
        result = execute(Program(8).then("h", 0), max_amplitudes=1 << 4)
        self.assertEqual(result.truth_class, TruthClass.EXACT)
        self.assertIn(
            result.execution_class,
            (
                ExecutionClass.EXACT_ALGEBRAIC,
                ExecutionClass.EXACT_SYMBOLIC,
                ExecutionClass.BOUNDED_EXACT,
            ),
        )

    def test_a_non_clifford_wide_program_has_no_dense_path(self):
        program = Program(64).then("h", 0).then("t", 0)
        admission = ExactFieldBackend().admit(program)
        self.assertFalse(admission.admitted)


class BackendParityTests(unittest.TestCase):
    """Independent exact backends must agree on the same program."""

    def test_bell_marginal_matches_dense_amplitudes(self):
        from turing_universal_quantum_computer.backends import StabilizerBackend

        if not StabilizerBackend().available()[0]:
            self.skipTest("stabilizer engine unavailable")
        program = Program(2).then("h", 0).then("cx", 0, 1)
        dense = execute(program, prefer="exact_algebraic")
        tableau = execute(program, prefer="stabilizer", marginal_of=[0, 1])
        dense_probs = {
            row["bitstring"]: row["probability_exact"]
            for row in dense.payload["amplitudes"]
            if row["probability_approx"] > 0
        }
        marginal = tableau.payload["marginal"]["distribution"]
        self.assertEqual(set(dense_probs), set(marginal))
        for key, value in marginal.items():
            self.assertEqual(str(value), dense_probs[key])

    def test_ghz_entropy_agrees_across_backends(self):
        from turing_universal_quantum_computer.backends import StabilizerBackend

        if not StabilizerBackend().available()[0]:
            self.skipTest("stabilizer engine unavailable")
        dense = execute(
            Program(4).then("h", 0).then("cx", 0, 1).then("cx", 1, 2).then("cx", 2, 3),
            entropy_of=[0],
        )
        tableau = execute(
            Program(4).then("h", 0).then("cx", 0, 1).then("cx", 1, 2).then("cx", 2, 3),
            prefer="stabilizer",
            entropy_of=[0],
        )
        self.assertEqual(dense.payload["entanglement_entropy_bits"], 1.0)
        self.assertEqual(tableau.payload["entanglement_entropy_bits"], 1)

    def test_full_width_clifford_runs_without_materialising(self):
        from turing_universal_quantum_computer.backends import StabilizerBackend

        if not StabilizerBackend().available()[0]:
            self.skipTest("stabilizer engine unavailable")
        program = Program(10_000).then("h", 0).then("cx", 0, 9_999)
        result = execute(program, prefer="stabilizer", entropy_of=[0])
        self.assertEqual(result.truth_class, TruthClass.EXACT)
        self.assertFalse(result.materialised)
        self.assertEqual(result.payload["tableau_bits"], 20_000)
        self.assertEqual(result.payload["entanglement_entropy_bits"], 1)


class QPUBoundaryTests(unittest.TestCase):
    """No path may reach a hardware claim without hardware."""

    def setUp(self):
        from turing_universal_quantum_computer.backends import reset_providers

        reset_providers()

    def tearDown(self):
        from turing_universal_quantum_computer.backends import reset_providers

        reset_providers()

    def test_qpu_is_unavailable_without_a_provider(self):
        available, reason = QPUBackend().available()
        self.assertFalse(available)
        self.assertIn("no QPU provider", reason)

    def test_qpu_execute_refuses(self):
        with self.assertRaises(QPUUnavailableError):
            QPUBackend().execute(Program(2).then("h", 0))

    def test_qpu_is_never_auto_selected(self):
        backend, _ = select_backend(Program(2).then("h", 0))
        self.assertNotEqual(backend.name if backend else None, "qpu")

    def test_hardware_claim_requires_a_job_record(self):
        from turing_universal_quantum_computer.backends import assert_measured_qpu

        exact = execute(Program(2).then("h", 0))
        with self.assertRaises(QPUClaimError):
            assert_measured_qpu(exact, None)
        with self.assertRaises(QPUClaimError):
            assert_measured_qpu(
                exact, QPUJob("ibm", "job-1", "2026-01-01T00:00:00Z", "deadbeef")
            )

    def test_job_record_requires_every_field(self):
        for kwargs in (
            {"provider": "", "job_id": "j", "completed_at": "t", "result_digest": "d"},
            {"provider": "p", "job_id": "", "completed_at": "t", "result_digest": "d"},
            {"provider": "p", "job_id": "j", "completed_at": "", "result_digest": "d"},
            {"provider": "p", "job_id": "j", "completed_at": "t", "result_digest": ""},
        ):
            with self.subTest(**kwargs):
                with self.assertRaises(QPUClaimError):
                    QPUJob(**kwargs)


class WitnessTests(unittest.TestCase):
    """A witness must not be able to assert more than the backend proved."""

    def _witness(self, program=None, **options):
        program = program or Program(2).then("h", 0).then("cx", 0, 1)
        return program, issue_witness(program, execute(program, **options))

    def test_witness_verifies(self):
        _, witness = self._witness()
        self.assertTrue(verify_witness(witness))

    def test_witness_never_claims_theorems_or_authority(self):
        _, witness = self._witness()
        self.assertFalse(witness.theorem_proven)
        self.assertFalse(witness.consensus_authority)
        self.assertFalse(witness.measured_qpu)

    def test_witness_round_trips(self):
        from turing_universal_quantum_computer.certificates import RunWitness

        _, witness = self._witness()
        self.assertEqual(RunWitness.from_dict(witness.to_dict()).digest(), witness.digest())

    def test_measured_qpu_on_a_simulated_run_is_rejected(self):
        from turing_universal_quantum_computer.certificates import RunWitness

        _, witness = self._witness()
        forged = RunWitness(**{**witness.to_dict(), "measured_qpu": True, "provider_job_id": "x"})
        with self.assertRaises(WitnessError):
            verify_witness(forged)

    def test_theorem_claim_is_rejected(self):
        from turing_universal_quantum_computer.certificates import RunWitness

        _, witness = self._witness()
        forged = RunWitness(**{**witness.to_dict(), "theorem_proven": True})
        with self.assertRaises(WitnessError):
            verify_witness(forged)

    def test_consensus_claim_is_rejected(self):
        from turing_universal_quantum_computer.certificates import RunWitness

        _, witness = self._witness()
        forged = RunWitness(**{**witness.to_dict(), "consensus_authority": True})
        with self.assertRaises(WitnessError):
            verify_witness(forged)

    def test_exact_backend_cannot_report_approximate(self):
        from turing_universal_quantum_computer.certificates import RunWitness

        _, witness = self._witness()
        forged = RunWitness(**{**witness.to_dict(), "truth_class": "approximate"})
        with self.assertRaises(WitnessError):
            verify_witness(forged)

    def test_hardware_witness_without_a_job_is_rejected(self):
        from turing_universal_quantum_computer.certificates import RunWitness

        _, witness = self._witness()
        forged = RunWitness(
            **{
                **witness.to_dict(),
                "execution_class": ExecutionClass.HARDWARE.value,
                "measured_qpu": True,
                "provider_job_id": None,
            }
        )
        with self.assertRaises(WitnessError):
            verify_witness(forged)

    def test_unknown_witness_field_is_rejected(self):
        from turing_universal_quantum_computer.certificates import RunWitness

        _, witness = self._witness()
        with self.assertRaises(WitnessError):
            RunWitness.from_dict({**witness.to_dict(), "sneaky_field": 1})


class ClaimBoundaryTests(unittest.TestCase):
    """The published claim text must pass its own audit."""

    def test_published_report_is_clean(self):
        report = capability_report()
        self.assertTrue(report["claim_boundary_clean"], report["claim_violations"])

    def test_universal_width_claim_is_flagged(self):
        self.assertTrue(
            audit_claims("TURING is a universal 10,000-qubit computer.")
        )

    def test_hardware_claim_is_flagged(self):
        self.assertTrue(audit_claims("We built a physical quantum computer."))
        self.assertTrue(audit_claims("measured on a real quantum device"))

    def test_cryptanalytic_claim_is_flagged(self):
        self.assertTrue(audit_claims("This breaks RSA-2048."))

    def test_correct_claim_wording_passes(self):
        honest = (
            "A 10,000-qubit logical register, exact for stabilizer and "
            "closed-form state classes; arbitrary circuits are refused beyond "
            "the materialisation budget. No physical QPU is bound."
        )
        self.assertEqual(audit_claims(honest), [])

    def test_matrix_reports_availability_honestly(self):
        for row in capability_report()["matrix"]:
            with self.subTest(backend=row["backend"]):
                self.assertIn("available", row)
                self.assertIn("availability", row)


class CapabilityContractTests(unittest.TestCase):
    """Every backend must declare a coherent envelope."""

    def test_gate_set_names_are_stable(self):
        self.assertIn("h", gate_names())
        self.assertIn("t", gate_names())

    def test_symbolic_backends_never_materialise(self):
        for row in capability_report()["matrix"]:
            if row["execution_class"] == ExecutionClass.EXACT_SYMBOLIC.value:
                with self.subTest(backend=row["backend"]):
                    self.assertFalse(row["materialises_state"])

    def test_no_backend_claims_a_physical_device_except_qpu(self):
        for row in capability_report()["matrix"]:
            if row["backend"] != "qpu":
                with self.subTest(backend=row["backend"]):
                    self.assertNotEqual(row["execution_class"], ExecutionClass.HARDWARE.value)

    def test_only_the_qpu_backend_is_hardware(self):
        hardware = [
            row["backend"]
            for row in capability_report()["matrix"]
            if row["execution_class"] == ExecutionClass.HARDWARE.value
        ]
        self.assertEqual(hardware, ["qpu"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
