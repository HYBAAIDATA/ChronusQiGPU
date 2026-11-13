"""Exact tests for the AL HARAS [[5,1,3]] code, dual-rail arithmetic and policy-criteria check.

References are computed independently in this file (direct bit-flip/sign
operator action, re-implemented mixing function, brute-force subset counts);
mutation tests show that the assertions reject wrong implementations.
"""

import inspect
from fractions import Fraction
from itertools import combinations

import pytest

from chronus.security.al_haras import autonomous_roe as roe
from chronus.security.al_haras import holographic_qec as qec
from chronus.security.al_haras import tempest_scrambler as ts
from chronus.security.al_haras.autonomous_roe import AutonomousROEValidator, EngagementSimplex, ROECriterion
from chronus.security.al_haras.holographic_qec import HappyTensorNetwork, HolographicQECEngine
from chronus.security.al_haras.receipts import ReceiptSigner
from chronus.security.al_haras.tempest_scrambler import Matrix2x2, TempestEmissionScrambler


# ==============================================================================
# [[5,1,3]] code
# ==============================================================================


def apply_xz_string(pauli, amplitudes):
    """Independent action of an X/Z Pauli string on {bitstring: amplitude}."""
    out = {}
    for bits, amp in amplitudes.items():
        sign = 1
        flipped = list(bits)
        for j, letter in enumerate(pauli):
            if letter == "Z" and bits[j] == "1":
                sign = -sign
            elif letter == "X":
                flipped[j] = "1" if bits[j] == "0" else "0"
        key = "".join(flipped)
        out[key] = out.get(key, 0) + sign * amp
    return {k: v for k, v in out.items() if v != 0}


@pytest.fixture
def engine():
    return HolographicQECEngine(depth=1)


class TestFiveQubitCode:
    def test_code_properties_recomputed(self, engine):
        props = engine.verify_code_properties()
        assert props["status"] == "CODE_PROPERTIES_VERIFIED"
        assert props["code_distance"] == 3
        assert props["generator_rank_gf2"] == 4
        assert props["logical_classes_count"] == 4 ** 5 // 2 ** 4 - 2 ** 4
        assert props["max_correctable_erasures"] == 2
        assert props["two_qubit_marginals_maximally_mixed"] is True

    def test_codewords_against_independent_operator_action(self, engine):
        zero = engine.encode_bulk_logical_state(0)["boundary_amplitudes"]
        one = engine.encode_bulk_logical_state(1)["boundary_amplitudes"]
        for word in (zero, one):
            assert len(word) == 16 and all(abs(a) == Fraction(1, 4) for a in word.values())
            for generator in qec.GENERATOR_STRINGS:
                assert apply_xz_string(generator, word) == word
        assert apply_xz_string("ZZZZZ", zero) == zero
        assert apply_xz_string("ZZZZZ", one) == {k: -v for k, v in one.items()}
        assert apply_xz_string("XXXXX", zero) == one
        even = {format(i, "05b") for i in range(32) if bin(i).count("1") % 2 == 0}
        assert set(zero) == even and set(one) == {format(i, "05b") for i in range(32)} - even

    def test_generators_commute_independently(self):
        basis = {format(i, "05b"): Fraction(i + 1) for i in range(32)}
        for g, h in combinations(qec.GENERATOR_STRINGS, 2):
            assert apply_xz_string(g, apply_xz_string(h, basis)) == apply_xz_string(h, apply_xz_string(g, basis))

    def test_every_single_qubit_error_corrected_and_syndromes_distinct(self, engine):
        syndromes = set()
        for j in range(5):
            for letter in "XYZ":
                error = "I" * j + letter + "I" * (4 - j)
                result = engine.correct_error(error)
                assert result["corrected"] is True and result["outcome"] == "CORRECTED"
                syndromes.add(tuple(result["syndrome"]))
        assert len(syndromes) == 15 and (0, 0, 0, 0) not in syndromes

    def test_some_weight_two_error_is_a_logical_error(self, engine):
        outcomes = {engine.correct_error(a + b + "III")["outcome"] for a in "XYZ" for b in "XYZ"}
        assert "LOGICAL_ERROR" in outcomes

    def test_erasure_recovery_for_every_subset(self, engine):
        for bit in (0, 1):
            encoded = engine.encode_bulk_logical_state(bit)
            for size in range(6):
                for erased in combinations(range(5), size):
                    result = engine.reconstruct_bulk_state(encoded, list(erased))
                    if size <= 2:
                        assert result["reconstructed"] is True
                        assert result["reconstructed_logical_bit"] == bit
                        letters = result["logical_operator_on_survivors"].lstrip("+-i")
                        assert len(letters) == 5 and all(letters[j] == "I" for j in erased)
                    else:
                        assert result["reconstructed"] is False
                        assert result["reconstructed_logical_bit"] is None
                        assert result["survivor_state_independent_of_logical_bit"] is True

    def test_reconstruction_ignores_the_logical_bit_label(self, engine):
        encoded = engine.encode_bulk_logical_state(1)
        encoded["logical_bit"] = 0
        assert engine.reconstruct_bulk_state(encoded, [0, 4])["reconstructed_logical_bit"] == 1

    def test_non_codeword_and_invalid_inputs(self, engine):
        basis_state = {"boundary_amplitudes": {"00000": Fraction(1)}}
        result = engine.reconstruct_bulk_state(basis_state, [])
        assert result["reconstructed"] is False
        assert result["reconstruction_status"] == "LOGICAL_OUTCOME_NOT_DEFINITE"
        with pytest.raises(ValueError):
            engine.reconstruct_bulk_state({"boundary_amplitudes": {"00000": Fraction(1, 2)}}, [])
        encoded = engine.encode_bulk_logical_state(0)
        for bad in ([5], [-1], [True]):
            with pytest.raises(ValueError):
                engine.reconstruct_bulk_state(encoded, bad)
        with pytest.raises(ValueError):
            engine.encode_bulk_logical_state(2)
        with pytest.raises(ValueError):
            HappyTensorNetwork(depth=2)

    def test_network_shape(self):
        network = HappyTensorNetwork(depth=1)
        assert len(network.nodes) == 6 and network.boundary_indices == [0, 1, 2, 3, 4]
        assert network.nodes["BULK_CENTER"].is_bulk is True

    def test_mutation_phase_free_pauli_product_is_caught(self, engine, monkeypatch):
        def phase_free(self, other):
            return qec.Pauli(self.x ^ other.x, self.z ^ other.z, (self.phase + other.phase) % 4)

        monkeypatch.setattr(qec.Pauli, "__mul__", phase_free)
        try:
            broken = HolographicQECEngine()
            status = broken.verify_code_properties()["status"]
        except RuntimeError:
            status = "CONSTRUCTION_FAILED"
        assert status != "CODE_PROPERTIES_VERIFIED"


# ==============================================================================
# Dual-rail arithmetic and the toy mixing function
# ==============================================================================


def reference_mix(word, cycles):
    """Independent re-implementation from the module docstring's description."""
    for _ in range(cycles):
        chunks = []
        for i in range(8):
            x = (word >> (8 * i)) & 0xFF
            chunks.append(0 if (x + 3) % 257 == 0 else (5 * x + 7) * pow(x + 3, 255, 257) % 257)
        for i in range(1, 8):
            chunks[i] ^= chunks[i - 1]
        chunks[0] ^= chunks[7]
        packed = sum((c & 0xFF) << (8 * i) for i, c in enumerate(chunks))
        word = ((packed << 29) | (packed >> 35)) & (2 ** 64 - 1)
    return word


def popcount(value):
    return sum((value >> i) & 1 for i in range(value.bit_length()))


class TestDualRail:
    def test_identity_for_every_byte(self):
        scrambler = TempestEmissionScrambler(bus_width=8)
        for word in range(256):
            res = scrambler.scramble_bus_word(word)
            assert res["hw_active"] == popcount(word)
            assert res["hw_complement"] == 8 - popcount(word)
            assert res["dual_rail_identity_holds"] is True and res["hamming_weight_sum"] == 8
        assert scrambler.scramble_bus_word(0x1FF)["input_truncated"] is True

    def test_transition_model_is_data_dependent_without_spacer(self):
        scrambler = TempestEmissionScrambler(bus_width=64)
        trace = [i * 0x0101010101010101 for i in range(16)]
        res = scrambler.verify_constant_power_trace(trace)
        assert res["verified"] is True and res["hamming_weight_span"] == 0
        assert res["constant_hamming_weight"] == 64
        expected = [2 * popcount(a ^ b) for a, b in zip(trace, trace[1:])]
        assert res["transitions_without_spacer"] == {"min": min(expected), "max": max(expected), "span": max(expected) - min(expected)}
        assert res["data_dependent_without_spacer"] is True
        assert res["transitions_with_return_to_zero_spacer"] == {"min": 128, "max": 128, "span": 0}
        assert res["status"] == "DUAL_RAIL_IDENTITY_HOLDS"

    def test_no_protection_or_emission_labels(self):
        scrambler = TempestEmissionScrambler()
        outputs = [scrambler.scramble_bus_word(5), scrambler.verify_constant_power_trace([1, 2]), scrambler.measure_avalanche_diffusion(0, 1)]
        text = repr(outputs) + inspect.getsource(ts)
        for phrase in ("CERTIFIED", "GAUSSIAN_THERMAL", "STATISTICALLY_UNOBSERVABLE", "SPECTRAL_EXPANSION_OPTIMAL", "rf_emission_profile"):
            assert phrase not in text
        assert scrambler.verify_constant_power_trace([]) == {"verified": False, "reason": "EMPTY_TRACE", "status": "EMPTY_TRACE"}

    def test_mutation_unmasked_complement_breaks_the_identity(self, monkeypatch):
        scrambler = TempestEmissionScrambler(bus_width=64)
        monkeypatch.setattr(TempestEmissionScrambler, "_complement", lambda self, word: word)
        assert scrambler.verify_constant_power_trace([0, 3])["verified"] is False

    def test_avalanche_is_measured_on_the_inputs(self):
        scrambler = TempestEmissionScrambler(bus_width=64)
        for a, b, cycles in ((0, 1, 3), (0xDEADBEEF, 0xDEADBEEE, 1), (2 ** 64 - 1, 0, 2), (12345, 12345, 3)):
            res = scrambler.measure_avalanche_diffusion(a, b, cycles=cycles)
            flipped = popcount(reference_mix(a, cycles) ^ reference_mix(b, cycles))
            assert res["flipped_bits"] == flipped
            assert res["avalanche_basis_points"] == flipped * 10000 // 64
            assert res["meets_avalanche_threshold"] is (2 * flipped >= 64)
        assert scrambler.measure_avalanche_diffusion(5, 6, cycles=0)["flipped_bits"] == popcount(5 ^ 6)

    def test_avalanche_profile_matches_reference(self):
        scrambler = TempestEmissionScrambler()
        profile = scrambler.avalanche_profile(0x0123456789ABCDEF, cycles=3)
        base = reference_mix(0x0123456789ABCDEF, 3)
        flips = [popcount(base ^ reference_mix(0x0123456789ABCDEF ^ (1 << j), 3)) for j in range(64)]
        assert profile["flipped_bits_per_input_bit"] == flips
        assert profile["mean_flipped_bits"] == str(Fraction(sum(flips), 64))
        assert profile["inputs_meeting_half_width"] == sum(1 for f in flips if 2 * f >= 64)

    def test_input_validation(self):
        with pytest.raises(ValueError):
            TempestEmissionScrambler(bus_width=0)
        with pytest.raises(ValueError):
            TempestEmissionScrambler().scramble_bus_word(-1)
        with pytest.raises(ValueError):
            TempestEmissionScrambler(bus_width=32).measure_avalanche_diffusion(0, 1)
        with pytest.raises(ValueError):
            TempestEmissionScrambler().measure_avalanche_diffusion(0, 1, cycles=-1)

    def test_matrix_relations_over_f257(self):
        s, t = TempestEmissionScrambler.GEN_S, TempestEmissionScrambler.GEN_T
        minus_identity = Matrix2x2(256, 0, 0, 256)
        assert s.determinant() == 1 and t.determinant() == 1
        assert s.multiply(s) == minus_identity
        st = s.multiply(t)
        assert st.multiply(st).multiply(st) == minus_identity


# ==============================================================================
# Policy-criteria completeness check
# ==============================================================================

ALL = list(ROECriterion)
COMMITMENT = "ab" * 32


def make_request(criteria=ALL, approvers=None, score=10, ceiling=25, commitment=COMMITMENT, request_id="REQ-1"):
    approvers = approvers or [f"reviewer-{i}" for i in range(len(criteria))]
    return EngagementSimplex(
        request_id=request_id,
        subject_commitment=commitment,
        approvals=dict(zip(criteria, approvers)),
        risk_score=score,
        risk_ceiling=ceiling,
    )


class TestPolicyCompleteness:
    def test_complete_record_still_requires_a_human_decision(self):
        res = AutonomousROEValidator().check_policy_completeness(make_request())
        assert res["complete"] is True
        assert res["status"] == "COMPLETE_AWAITING_HUMAN_DECISION"
        assert res["boundary_defect_norm"] == 0 and res["violations"] == []
        assert "human" in res["decision_authority"]
        assert "authorized" not in res and "AUTHORI" not in res["status"]
        assert AutonomousROEValidator.verify_review_record(res["review_record"]) is True

    def test_defect_counts_missing_vertices_for_every_subset(self):
        validator = AutonomousROEValidator(min_distinct_approvers=1)
        for size in range(len(ALL) + 1):
            for subset in combinations(ALL, size):
                res = validator.check_policy_completeness(make_request(list(subset)))
                assert res["boundary_defect_norm"] == len(ALL) - size
                assert res["missing_criteria"] == sorted(c.value for c in set(ALL) - set(subset))
                assert res["complete"] is (size == len(ALL))

    def test_distinct_approvers_and_risk_ceiling(self):
        validator = AutonomousROEValidator()
        same = validator.check_policy_completeness(make_request(approvers=["one-person"] * 4))
        assert same["violations"] == ["INSUFFICIENT_DISTINCT_APPROVERS_1_OF_2"]
        over = validator.check_policy_completeness(make_request(score=45, ceiling=25))
        assert over["violations"] == ["RISK_SCORE_EXCEEDS_CEILING_BY_20"] and over["status"] == "INCOMPLETE"
        assert validator.check_policy_completeness(make_request(score=25, ceiling=25))["complete"] is True

    def test_invalid_records(self):
        validator = AutonomousROEValidator()
        bad = validator.check_policy_completeness(make_request(commitment="not-a-digest", request_id=""))
        assert set(bad["violations"]) == {"INVALID_REQUEST_ID", "INVALID_SUBJECT_COMMITMENT"}
        blank = make_request()
        blank.approvals[ROECriterion.LEGAL_REVIEW_RECORDED] = "   "
        assert validator.evaluate_boundary_closure(blank) == (False, 1, ["MISSING_REQUIRED_CRITERION_LEGAL_REVIEW_RECORDED"])
        with pytest.raises(TypeError):
            validator.check_policy_completeness(make_request(score=True))
        with pytest.raises(ValueError):
            validator.check_policy_completeness(make_request(score=-1))
        with pytest.raises(ValueError):
            AutonomousROEValidator(required_criteria=[])
        with pytest.raises(ValueError):
            AutonomousROEValidator(required_criteria=[ROECriterion.SUBJECT_IDENTIFIED], min_distinct_approvers=2)

    def test_signed_record_detects_tampering_and_untrusted_keys(self):
        res = AutonomousROEValidator().check_policy_completeness(make_request(criteria=ALL[:3]))
        record = res["review_record"]
        assert AutonomousROEValidator.verify_review_record(record) is True
        tampered = {"body": dict(record["body"], complete=True, violations=[]), "signature": record["signature"]}
        assert AutonomousROEValidator.verify_review_record(tampered) is False
        forger = ReceiptSigner(seed=bytes(32))
        forged = {"body": tampered["body"], "signature": forger.sign(tampered["body"])}
        assert AutonomousROEValidator.verify_review_record(forged) is False
        assert AutonomousROEValidator.verify_review_record(None) is False

    def test_vocabulary_is_neutral(self):
        source = inspect.getsource(roe)
        for phrase in ("ENGAGEMENT_AUTHORIZED", "GENEVA", "zk_stark", "weapon", "PROPORTIONALITY", "SANCTUARY", "FVEY"):
            assert phrase not in source
        assert not [name for name in dir(AutonomousROEValidator) if name.startswith("authorize")]

    def test_mutation_validator_ignoring_missing_criteria_is_caught(self):
        class Mutant(AutonomousROEValidator):
            def _assess(self, request):
                assessed = super()._assess(request)
                assessed["violations"] = [v for v in assessed["violations"] if not v.startswith("MISSING_")]
                assessed["missing"] = []
                return assessed

        def subset_check(validator):
            return all(
                validator.check_policy_completeness(make_request(list(s)))["complete"] is (len(s) == len(ALL))
                for size in range(len(ALL) + 1)
                for s in combinations(ALL, size)
            )

        assert subset_check(AutonomousROEValidator(min_distinct_approvers=1)) is True
        assert subset_check(Mutant(min_distinct_approvers=1)) is False
