import unittest
from dataclasses import replace
from fractions import Fraction

from turing_universal_quantum_computer.deterministic_hashrate import (
    CertificateError,
    DeterminismEnvelope,
    DeterministicMiningSystem,
    FleetDesign,
    PipelineSpec,
    TEN_EH_HPS,
    design_lattice,
    issue_hashrate_certificate,
    minimum_chips,
    minimum_chips_for_window,
    verify_hashrate_certificate,
)


class DeterministicHashrateTests(unittest.TestCase):
    def test_exact_steady_state_floor(self):
        design = FleetDesign(1_000_000, 10_000, Fraction(1_000_000_000))
        self.assertEqual(design.steady_state_hps, TEN_EH_HPS)
        self.assertEqual(design.pipeline.latency_cycles, 192)
        self.assertEqual(minimum_chips(10_000, 1_000_000_000), 1_000_000)

    def test_finite_window_accounts_for_pipeline_fill(self):
        design = FleetDesign(1_000_000, 10_000, Fraction(1_000_000_000))
        cycles = 1_000_000_000
        self.assertLess(design.window_rate_hps(cycles), TEN_EH_HPS)
        self.assertEqual(
            minimum_chips_for_window(10_000, 1_000_000_000, cycles),
            1_000_001,
        )
        guaranteed = FleetDesign(1_000_001, 10_000, Fraction(1_000_000_000))
        self.assertGreaterEqual(guaranteed.window_rate_hps(cycles), TEN_EH_HPS)

    def test_certificate_is_exact_content_addressed_and_replayable(self):
        design = FleetDesign(1_000_001, 10_000, Fraction(1_000_000_000))
        certificate = issue_hashrate_certificate(
            design,
            cold_start_cycles=1_000_000_000,
        )
        self.assertTrue(certificate.steady_state_floor_met)
        self.assertTrue(certificate.cold_start_floor_met)
        self.assertTrue(verify_hashrate_certificate(certificate))
        self.assertEqual(len(certificate.attestation_root), 64)
        self.assertEqual(len(certificate.certificate_digest), 64)
        self.assertEqual(
            certificate,
            issue_hashrate_certificate(design, cold_start_cycles=1_000_000_000),
        )

    def test_tampered_certificate_fails_closed(self):
        design = FleetDesign(1_000_001, 10_000, Fraction(1_000_000_000))
        certificate = issue_hashrate_certificate(design)
        tampered = replace(certificate, floor_hps=TEN_EH_HPS + 1)
        with self.assertRaises(CertificateError):
            verify_hashrate_certificate(tampered)

    def test_design_lattice_uses_exact_arithmetic(self):
        rows = design_lattice(
            (500_000_000, 1_000_000_000, 1_500_000_000),
            (1_000, 10_000),
        )
        self.assertEqual(len(rows), 6)
        self.assertTrue(all(row["floor_met"] for row in rows))
        self.assertEqual(rows[3]["minimum_chips"], 1_000_000)

    def test_envelope_and_machine_proof_obligations(self):
        design = FleetDesign(1_000_001, 10_000, Fraction(1_000_000_000))
        envelope = DeterminismEnvelope(
            design.chips,
            design.cores_per_chip,
            design.clock_hz,
        )
        self.assertTrue(envelope.floor_met)
        system = DeterministicMiningSystem.build(
            design,
            cold_start_cycles=1_000_000_000,
        )
        proofs = system.proof_obligations()
        nonphysical = (
            value
            for key, value in proofs.items()
            if key != "T6_physical_realization"
        )
        self.assertTrue(all(nonphysical))
        self.assertFalse(proofs["T6_physical_realization"])

    def test_invalid_pipeline_and_pre_fill_window_fail_closed(self):
        with self.assertRaises(ValueError):
            PipelineSpec(initiation_interval_cycles=0)
        pipeline = PipelineSpec()
        with self.assertRaises(ValueError):
            minimum_chips_for_window(10_000, 1_000_000_000, 191, pipeline=pipeline)


if __name__ == "__main__":
    unittest.main()
