import hashlib
import unittest

from turing_universal_quantum_computer.fault_tolerant_asic import (
    APPLICATIONS,
    CryoCMOS,
    Decoder,
    DilutionRefrigerator,
    EvidenceRecord,
    EvidenceState,
    LogicalQubit,
    MathematicalEvidence,
    ProductionEvidence,
    PureQuantumMathASIC,
    QuantumAsicStack,
    QuantumChipLayout,
    RSFQ,
    ReadoutResonator,
    RoomTemperatureControl,
    ScalingModel,
    SignalChain,
    SurfaceCode,
    SyndromeExtraction,
    TransmonCoherence,
    TransmonQubit,
    TunableCoupler,
    WiringBudget,
)


def _record(category, state=EvidenceState.MEASURED):
    return EvidenceRecord(
        category=category,
        state=state,
        artifact_digest=hashlib.sha256(category.encode()).hexdigest(),
        source="test-fixture",
        observed_at="2026-10-05T20:00:00Z",
    )


class QuantumAsicModelTests(unittest.TestCase):
    def test_refrigerator_thermodynamics_and_wire_capacity(self):
        fridge = DilutionRefrigerator()
        self.assertEqual(fridge.coldest.temperature_k, 0.01)
        self.assertAlmostEqual(fridge.cooling_power(0.02), 4e-6)
        self.assertAlmostEqual(fridge.minimum_work(1e-6, 300, 0.01), 0.029999)
        self.assertAlmostEqual(fridge.wiring_heat(10, 10e-9), 100e-9)
        self.assertEqual(fridge.line_capacity(10e-9, reserve_fraction=0.2), 80)

    def test_transmon_coherence_and_device_contracts(self):
        coherence = TransmonCoherence()
        qubit = TransmonQubit()
        self.assertGreater(coherence.quality_factor, 0)
        self.assertGreater(coherence.t1_seconds, 0)
        self.assertGreater(coherence.t2_seconds, 0)
        self.assertAlmostEqual(qubit.ej_ec_ratio, 50)
        self.assertTrue(qubit.report(coherence)["transmon_regime"])
        coupler = TunableCoupler()
        self.assertAlmostEqual(coupler.residual_zz_hz(300e6), 3333.333333, places=5)
        self.assertGreater(ReadoutResonator().snr_proxy, 0)

    def test_surface_code_overhead_logical_rate_and_minimum_distance(self):
        code = SurfaceCode(distance=21, physical_error_rate=1e-3)
        self.assertEqual(code.physical_qubits, 881)
        self.assertEqual(code.correctable_errors, 10)
        self.assertAlmostEqual(code.logical_error_rate, 3e-13)
        self.assertEqual(SurfaceCode.minimum_distance(1e-3, 1e-12), 21)
        with self.assertRaises(ValueError):
            SurfaceCode.minimum_distance(1e-2, 1e-12)

    def test_wiring_chip_and_signal_chain(self):
        wiring = WiringBudget(6, 10e-9, 100)
        self.assertEqual(wiring.effective_lines(1000), 60)
        self.assertEqual(wiring.maximum_qubits(1e-6), 1333)
        chip = QuantumChipLayout()
        self.assertEqual(chip.qubit_capacity, 400)
        self.assertEqual(chip.readout_lines, 40)
        chain = SignalChain()
        self.assertEqual(chain.total_attenuation_db, 50)
        self.assertEqual(chain.net_gain_db, -30)

    def test_syndrome_decoder_and_logical_qubit_contracts(self):
        self.assertAlmostEqual(SyndromeExtraction().cycle_time_s, 1.7e-6)
        decoder = Decoder(throughput_bits_s=1e12)
        self.assertEqual(decoder.syndrome_bits_per_cycle, 800)
        self.assertAlmostEqual(decoder.required_input_rate, 8e8)
        self.assertEqual(decoder.graph_vertices, 800)
        self.assertEqual(decoder.mwpm_complexity_upper_bound, 800**3)
        self.assertTrue(decoder.ready)
        logical = LogicalQubit()
        self.assertAlmostEqual(logical.gate_time_s, 10e-6)
        self.assertGreater(logical.logical_lifetime_s, 1e6)

    def test_control_surfaces_are_validated_and_measurable(self):
        room = RoomTemperatureControl(awg_channels=100, fpga_count=10)
        self.assertEqual(room.network_bits_s, 100e9)
        cryo = CryoCMOS()
        self.assertEqual(cryo.tiles(10_000), 100)
        self.assertAlmostEqual(cryo.power_w(10_000), 1.0)
        self.assertFalse(cryo.supports(10_000))
        projected = CryoCMOS.ten_year_target()
        self.assertAlmostEqual(projected.power_w(10_000), 0.1)
        self.assertTrue(projected.supports(10_000))
        self.assertAlmostEqual(RSFQ().power_w(1000), 10e-6)

    def test_application_catalog_is_modelled_not_executed(self):
        expected = {
            "shor_rsa_2048",
            "grover_aes_256",
            "chemistry_femoco",
            "qaoa",
            "boson_sampling",
        }
        self.assertEqual(set(APPLICATIONS), expected)
        for resource in APPLICATIONS.values():
            self.assertIs(resource.evidence_state, EvidenceState.MODELLED)
            self.assertIn("not", resource.notes)

    def test_scaling_model_uses_ceiling_and_rejects_unknown_technology(self):
        result = ScalingModel().calculate(100, 21, "cryo_cmos", logical_depth=1000)
        self.assertEqual(result.physical_qubits, 88_100)
        self.assertEqual(result.refrigerators, 9)
        self.assertEqual(result.total_wall_power_w, 90_000)
        self.assertEqual(result.total_cost_usd, 9_000_000)
        self.assertAlmostEqual(result.runtime_s, 0.01)
        with self.assertRaises(ValueError):
            ScalingModel().calculate(1, 21, "magic")

    def test_four_thresholds_fail_closed_until_decoder_rate_is_met(self):
        default = QuantumAsicStack()
        thresholds = default.thresholds(100_000)
        self.assertTrue(thresholds.physical_error_below_threshold)
        self.assertTrue(thresholds.physical_qubit_minimum)
        self.assertFalse(thresholds.decoder_budget)
        provisioned = QuantumAsicStack(decoder=Decoder(throughput_bits_s=1e12))
        self.assertTrue(provisioned.thresholds(100_000).all_crossed)

    def test_readiness_requires_hash_addressed_independent_evidence(self):
        empty = ProductionEvidence()
        self.assertFalse(empty.software_model_ready)
        self.assertFalse(empty.physical_stack_ready)
        self.assertIn("software_tests", empty.missing)
        records = (
            _record("software_tests"),
            _record("independent_model_review", EvidenceState.INDEPENDENTLY_REPRODUCED),
            _record("cryogenic_measurements"),
            _record("qubit_chip_measurements"),
            _record("decoder_hardware_measurements"),
            _record("control_stack_measurements"),
            _record("logical_qubit_demonstration"),
            _record("application_execution", EvidenceState.INDEPENDENTLY_REPRODUCED),
        )
        evidence = ProductionEvidence(records)
        self.assertTrue(evidence.software_model_ready)
        self.assertTrue(evidence.physical_stack_ready)
        self.assertEqual(evidence.missing, ())
        stack = QuantumAsicStack(decoder=Decoder(throughput_bits_s=1e12))
        report = stack.report(physical_qubits=100_000, evidence=evidence)
        self.assertTrue(report["physical_qpu_present"])
        self.assertTrue(report["production"]["physical_stack_ready"])
        self.assertEqual(len(report["report_digest"]), 64)
        self.assertEqual(stack.application("qaoa").name, "qaoa")
        with self.assertRaises(ValueError):
            stack.application("unknown")

    def test_first_principles_verifier_issues_exact_replayable_evidence(self):
        machine = PureQuantumMathASIC()
        bundle = machine.verify_first_principles()
        self.assertTrue(bundle.verified)
        self.assertTrue(all(bundle.checks.values()))
        self.assertEqual(bundle.evidence.missing, ("independent_model_review",))
        unitarity = bundle.artifacts["unitarity_verification"]
        self.assertEqual(unitarity["rational_rotation_error_sq"], "0")
        self.assertEqual(unitarity["clifford_state"], "PASS")
        self.assertGreater(unitarity["clifford_checked_pairs"], 0)
        self.assertTrue(
            bundle.artifacts["deterministic_replay"]["certificate_valid"]
        )
        error_proof = bundle.artifacts["error_correction_invariants"]
        self.assertEqual(error_proof["css_noncommuting_pairs"], ())
        self.assertTrue(error_proof["logical_anticommutation"])
        self.assertGreater(error_proof["css_pairs_checked"], 0)

    def test_pure_quantum_math_abstraction_requires_math_evidence_only(self):
        empty = PureQuantumMathASIC().report(logical_scale=10_000)
        self.assertEqual(
            empty["truth_class"],
            "pure_quantum_mathematical_abstraction",
        )
        self.assertFalse(empty["physical_qpu_present"])
        self.assertFalse(empty["production"]["mathematical_abstraction_ready"])
        categories = (
            "software_tests",
            "independent_model_review",
            "unitarity_verification",
            "normalization_verification",
            "error_correction_invariants",
            "deterministic_replay",
            "deterministic_hashrate_verification",
        )
        records = tuple(
            _record(
                category,
                EvidenceState.INDEPENDENTLY_REPRODUCED
                if category == "independent_model_review"
                else EvidenceState.EXACT_VERIFIED,
            )
            for category in categories
        )
        report = PureQuantumMathASIC().report(
            logical_scale=10_000,
            evidence=MathematicalEvidence(records),
        )
        self.assertTrue(report["production"]["mathematical_abstraction_ready"])
        self.assertFalse(report["production"]["hardware_evidence_required"])
        self.assertEqual(report["formal_hilbert_dimension"], "2^10000")

    def test_invalid_parameters_and_evidence_fail_closed(self):
        with self.assertRaises(ValueError):
            SurfaceCode(distance=4)
        with self.assertRaises(ValueError):
            TransmonQubit(anharmonicity_hz=1)
        with self.assertRaises(ValueError):
            EvidenceRecord("x", EvidenceState.MEASURED, "bad", "source", "now")
        duplicate = _record("software_tests")
        with self.assertRaises(ValueError):
            ProductionEvidence((duplicate, duplicate))
        with self.assertRaises(ValueError):
            QuantumAsicStack(
                surface_code=SurfaceCode(distance=11),
                logical=LogicalQubit(code=SurfaceCode(distance=21)),
            )


if __name__ == "__main__":
    unittest.main()
