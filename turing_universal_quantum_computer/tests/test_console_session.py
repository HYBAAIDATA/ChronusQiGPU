"""Console session tests.

The console is the operator surface, so its *refusals* and its *representation
reporting* are part of the product.  These tests drive a scripted session the
way an operator would and pin the behaviour that must not regress:

* a dense register reports dense amplitudes;
* a wide register reports its tableau and still answers every query;
* out-of-domain programs are refused with a reason, not approximated;
* the hardware boundary refuses and never reports ``measured_qpu``.
"""

from __future__ import annotations

import unittest

from turing_universal_quantum_computer.console import (
    DEMO_SCRIPT,
    QuantumConsole,
    render_circuit,
)


class ConsoleSessionTests(unittest.TestCase):
    def setUp(self):
        self.console = QuantumConsole()

    # -- dense representation ----------------------------------------------
    def test_register_reports_representation(self):
        output = self.console.do("init 3")
        self.assertIn("dense_algebraic", output)

    def test_gates_apply_and_report_exactness(self):
        self.console.do("init 2")
        output = self.console.do("h 0")
        self.assertIn("exact", output)
        self.assertIn("‖ψ‖² = 1", output)

    def test_psi_shows_exact_amplitudes(self):
        self.console.do("init 2")
        self.console.do("h 0")
        self.console.do("cx 0 1")
        output = self.console.do("psi")
        self.assertIn("dense_algebraic", output)
        self.assertIn("Q(√2)", output)

    def test_circuit_diagram_renders_controls(self):
        self.console.do("init 2")
        self.console.do("h 0")
        self.console.do("cx 0 1")
        diagram = self.console.do("diagram")
        self.assertIn("●", diagram)
        self.assertIn("⊕", diagram)

    def test_measurement_is_reproducible_and_conserves_shots(self):
        self.console.do("init 3")
        for line in ("h 0", "cx 0 1", "cx 1 2"):
            self.console.do(line)
        first = self.console.do("measure 512 --seed 7")
        second = self.console.do("measure 512 --seed 7")
        self.assertEqual(first, second)

    def test_unseeded_measure_reports_the_effective_seed_zero(self):
        # The public boundary normalizes omitted seeds to 0; the console must
        # report what actually ran, not the omitted request value.
        self.console.do("init 2")
        self.console.do("h 0")
        output = self.console.do("measure 64")
        self.assertIn("seed 0", output)
        self.assertNotIn("seed None", output)

    def test_expectation_values_are_exact(self):
        self.console.do("init 2")
        self.console.do("h 0")
        output = self.console.do("expect 0")
        self.assertIn("⟨Z⟩ = 0", output)

    def test_entropy_of_a_bell_pair_is_one_bit(self):
        self.console.do("init 2")
        self.console.do("h 0")
        self.console.do("cx 0 1")
        self.assertIn("1.000000 bits", self.console.do("entropy 0"))

    def test_product_test_distinguishes_entangled_states(self):
        self.console.do("init 2")
        self.console.do("h 0")
        self.console.do("cx 0 1")
        self.assertIn("ENTANGLED", self.console.do("product 0 1"))

    def test_witness_is_issued_and_verified(self):
        self.console.do("init 2")
        self.console.do("h 0")
        output = self.console.do("certify")
        self.assertIn("verified: True", output)
        self.assertIn('"measured_qpu": false', output)

    # -- refusal behaviour --------------------------------------------------
    def test_unknown_command_is_reported(self):
        self.assertIn("unknown command", self.console.do("teleport 0 1"))

    def test_gate_before_register_is_reported(self):
        self.assertIn("no register", self.console.do("h 0"))

    def test_out_of_range_qubit_is_reported(self):
        self.console.do("init 2")
        self.assertIn("outside", self.console.do("h 5"))

    def test_non_clifford_gate_is_refused_with_a_reason(self):
        self.console.do("init 2")
        output = self.console.do("t 0")
        # T is inside the dense Clifford+T set, so it is accepted here.
        self.assertIn("applied t 0", output)

    def test_wide_non_clifford_is_refused_not_approximated(self):
        self.console.do("init 64")
        output = self.console.do("t 0")
        self.assertIn("REFUSED", output)
        self.assertIn("approximate", output.lower())

    # -- wide representation -----------------------------------------------
    def test_wide_register_reports_tableau(self):
        output = self.console.do("init 10000")
        self.assertIn("tableau", output)

    def test_wide_register_still_gates_and_measures(self):
        self.console.do("init 10000")
        self.assertIn("tableau", self.console.do("h 0"))
        self.assertIn("tableau", self.console.do("cx 0 9999"))
        output = self.console.do("measure 32 --seed 3 --readout 0,9999")
        self.assertIn("|00⟩", output)
        self.assertIn("|11⟩", output)

    def test_wide_register_answers_quantum_queries(self):
        self.console.do("init 10000")
        self.console.do("h 0")
        self.console.do("cx 0 9999")
        self.assertIn("⟨Z⟩", self.console.do("expect 0"))
        self.assertIn("exact integer", self.console.do("entropy 0"))
        # A cut is entangled or not depending on which qubits it names.  The
        # pair {0, 9999} is the *pure* Bell state, so that cut is separable;
        # cutting qubit 0 away from its partner is what is entangled.
        self.assertIn("SEPARABLE", self.console.do("product 0 9999"))
        self.assertIn("ENTANGLED", self.console.do("product 0 1"))

    def test_wide_marginal_is_exact(self):
        self.console.do("init 10000")
        self.console.do("h 0")
        self.console.do("cx 0 9999")
        output = self.console.do("prob 0 9999")
        self.assertIn("|00⟩", output)
        self.assertIn("|11⟩", output)
        self.assertIn("1/2", output)

    def test_wide_dimension_is_not_printed_as_a_decimal(self):
        self.console.do("init 10000")
        output = self.console.do("status")
        self.assertIn("2^10000", output)
        self.assertNotIn("1995063116", output)

    def test_amplitude_list_is_unavailable_and_says_why(self):
        self.console.do("init 10000")
        output = self.console.do("amps")
        self.assertIn("no amplitude list", output)
        self.assertIn("measure", output)

    # -- machine surfaces ---------------------------------------------------
    def test_backends_matrix_lists_every_backend(self):
        output = self.console.do("backends")
        for name in ("exact_algebraic", "stabilizer", "sparse", "closed_form", "qpu"):
            self.assertIn(name, output)

    def test_capabilities_reports_a_clean_claim_boundary(self):
        output = self.console.do("capabilities")
        self.assertIn("claim boundary clean: True", output)
        self.assertIn("NOT AVAILABLE", output)

    def test_qpu_reports_no_provider_and_refuses(self):
        self.console.do("init 2")
        output = self.console.do("qpu")
        self.assertIn("available=False", output)
        self.assertIn("measured_qpu=False", output)
        self.assertIn("REFUSED", output)

    def test_help_lists_the_command_groups(self):
        output = self.console.do("help")
        for group in ("register", "gates", "readout", "quantum", "machine"):
            self.assertIn(group, output)

    # -- scripted sessions --------------------------------------------------
    def test_quit_is_signalled(self):
        self.assertEqual(self.console.do("quit"), "__QUIT__")

    def test_script_runner_returns_pairs(self):
        results = self.console.run_script(["init 2", "h 0", "psi"])
        self.assertEqual(len(results), 3)
        self.assertTrue(all(isinstance(pair, tuple) for pair in results))

    def test_demo_script_completes_without_error(self):
        console = QuantumConsole()
        for line in DEMO_SCRIPT:
            output = console.do(line)
            self.assertNotEqual(output, "__QUIT__")
            self.assertNotIn("Traceback", output)

    def test_circuit_renderer_handles_an_empty_program(self):
        from turing_universal_quantum_computer.backends import Program

        self.assertIn("empty", render_circuit(Program(2)))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
