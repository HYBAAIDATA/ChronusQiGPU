"""Exact tests for the T-ISA model, the F_257 trace receipts and the executable checks.

Pure computation (no web framework). Each test compares a computed result with
an independent derivation, feeds adversarial input, or applies a mutation that
a wrong implementation would not survive.
"""

import copy
import hashlib
import itertools
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytest

from chronus.security.al_haras import braids, reed_solomon, zk_neural
from chronus.security.al_haras.cyclotomic import CyclotomicZ5
from chronus.security.al_haras.formal_invariants import (
    LEAN_SOURCE_PATH,
    LEAN_THEOREMS,
    FormalTopologicalProofVerifier,
)
from chronus.security.al_haras.hardware_t_isa import (
    FUNCT7_MAP,
    RTL_SEMANTICS,
    STATUS_FAULT,
    STATUS_HARMONIC_CONSENSUS,
    STATUS_UNCHECKED,
    WORD_MAX,
    WORD_MIN,
    CoprocessorRegisters,
    MemoryBus,
    RegisterECCFault,
    RicciCurvatureNeckFault,
    RISCVTopologicalCoprocessor,
    RoCCInstruction,
    TISAInstruction,
    TISAOpcode,
    TopologicalSheafFault,
    cyclo5_poly_mul_mod_phi5,
    decode_t_isa_instruction,
    dsw_instanton_repair_alu,
    encode_t_isa_instruction,
    execute_t_isa_instruction,
    protect_register,
    to_word,
)
from chronus.security.al_haras.sheaf import GraphSheaf
from chronus.security.al_haras.zk_neural import (
    PROOF_TYPE,
    LineRateVerifiableNeuralCompute,
    VerifiableNeuralComputeEngine,
    build_trace_receipt,
    check_inference_receipt,
    compute_vanishing_polynomial_on_trace_domain,
    forward_pass_with_trace,
    generate_fri_stark_proof,
    interpolate_trace_polynomial,
    poly_eval,
    poly_mul,
    polynomial_divide_exact,
    transition_vanishing_polynomial,
    verify_stark_quotient,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
RTL_PATH = REPO_ROOT / "hardware" / "rtl" / "t_isa_coprocessor.sv"
LEAN_PATH = REPO_ROOT / LEAN_SOURCE_PATH
P = 257
H = [pow(4, i, P) for i in range(8)]

# The T_CYCLO_MUL expressions of the RTL before this revision (kept to show the test catches them).
PREVIOUS_RTL_MUL = {
    "p0": "(a0*b0) - (a3*b1) - (a2*b2) - (a1*b3)",
    "p1": "(a1*b0) + (a0*b1) - (a3*b2) - (a2*b3) - (a3*b1)",
    "p2": "(a2*b0) + (a1*b1) + (a0*b2) - (a3*b3) - (a3*b2) - (a2*b3)",
    "p3": "(a3*b0) + (a2*b1) + (a1*b2) + (a0*b3) - (a3*b3)",
}


def _rtl_mul_mismatches(expressions):
    mismatches = 0
    for a in itertools.product((-1, 0, 1), repeat=4):
        for b in itertools.product((-1, 0, 1), repeat=4):
            env = {f"a{i}": a[i] for i in range(4)}
            env.update({f"b{i}": b[i] for i in range(4)})
            rtl = tuple(eval(expressions[f"p{k}"], {"__builtins__": {}}, env) for k in range(4))
            mismatches += rtl != (CyclotomicZ5(*a) * CyclotomicZ5(*b)).coeffs()
    return mismatches


def _fresh():
    return CoprocessorRegisters(32), MemoryBus()


def _run(funct7, regs, bus, rs1=1, rs2=2, rd=3):
    return execute_t_isa_instruction(RoCCInstruction(funct7=funct7, rs1=rs1, rs2=rs2, rd=rd), regs, bus)


# --------------------------------------------------------------------------- T-ISA arithmetic
class TestCyclotomicALU:
    def test_multiplier_matches_the_ring_product_and_zeta_has_order_five(self):
        for a in itertools.product((-2, 0, 3), repeat=4):
            for b in itertools.product((-1, 0, 2), repeat=4):
                assert cyclo5_poly_mul_mod_phi5(a, b) == (CyclotomicZ5(*a) * CyclotomicZ5(*b)).coeffs()
        zeta, power = (0, 1, 0, 0), (1, 0, 0, 0)
        for k in range(1, 6):
            power = cyclo5_poly_mul_mod_phi5(power, zeta)
            assert (power == (1, 0, 0, 0)) == (k == 5)

    def test_rtl_multiplier_expressions_match_the_model(self):
        source = RTL_PATH.read_text(encoding="utf-8")
        expressions = dict(re.findall(r"wire signed \[63:0\] (p[0-3]) = (.*?);", source))
        assert sorted(expressions) == ["p0", "p1", "p2", "p3"]
        assert _rtl_mul_mismatches(expressions) == 0
        # mutation: the expressions this revision replaced disagree with the ring product
        assert _rtl_mul_mismatches(PREVIOUS_RTL_MUL) > 0

    def test_rtl_sheaf_trap_tests_equality_because_the_norm_wraps(self):
        source = RTL_PATH.read_text(encoding="utf-8")
        assert "wire sheaf_obstruction_detected = (rs1_data != rs2_data);" in source
        # the replaced decision used a 64-bit sum of squares, which is 0 when every difference is -2^31
        assert sum((-(1 << 31)) ** 2 for _ in range(4)) % (1 << 64) == 0
        regs, bus = _fresh()
        regs.write_128bit(2, (WORD_MIN,) * 4)
        with pytest.raises(TopologicalSheafFault):
            _run(0x03, regs, bus, rs1=0, rs2=2)

    def test_add_and_mul_wrap_like_the_32_bit_datapath(self):
        regs, bus = _fresh()
        regs.write_128bit(1, (WORD_MAX, 5, -7, 0))
        regs.write_128bit(2, (1, 2, 3, 4))
        res = _run(0x01, regs, bus)
        assert res["dst"] == (WORD_MIN, 7, -4, 4) and res["overflow"] is True
        assert regs.read_128bit(3) == res["dst"]
        regs.write_128bit(1, (1, 2, 0, 0))
        regs.write_128bit(2, (3, 1, 0, 0))
        assert _run(0x01, regs, bus)["overflow"] is False
        mul = _run(0x02, regs, bus)
        assert mul["dst"] == (CyclotomicZ5(1, 2) * CyclotomicZ5(3, 1)).coeffs() == (3, 7, 2, 0)
        assert mul["overflow"] is False
        regs.write_128bit(1, (1 << 20, 0, 0, 0))
        regs.write_128bit(2, (1 << 20, 3, 0, 0))
        big = _run(0x02, regs, bus)
        assert big["dst"] == (to_word(1 << 40), to_word(3 << 20), 0, 0) == (0, 3 << 20, 0, 0)
        assert big["overflow"] is True

    def test_host_writes_are_validated(self):
        regs, _ = _fresh()
        with pytest.raises(ValueError):
            regs.write_128bit(1, (1 << 31, 0, 0, 0))
        with pytest.raises(ValueError):
            regs.write_128bit(1, (1, 2, 3))
        with pytest.raises(TypeError):
            regs.write_128bit(1, (True, 0, 0, 0))
        with pytest.raises(TypeError):
            regs.write_128bit(1, ("7", 0, 0, 0))
        with pytest.raises(IndexError):
            regs.write_128bit(32, (1, 1, 1, 1))
        regs.write_128bit(0, (9, 9, 9, 9))
        assert regs.read_128bit(0) == (0, 0, 0, 0)
        assert regs.get_status(4) == STATUS_UNCHECKED


# --------------------------------------------------------------------------- sheaf inspection
class TestSheafInspect:
    def test_equal_registers_pass_with_a_zero_coboundary(self):
        regs, bus = _fresh()
        regs.write_128bit(1, (3, -1, 4, 1))
        regs.write_128bit(2, (3, -1, 4, 1))
        res = _run(0x03, regs, bus, rd=5)
        assert res["consistent"] is True and res["coboundary"] == [0, 0, 0, 0] and res["residual_norm_sq"] == 0
        assert regs.get_status(5) == STATUS_HARMONIC_CONSENSUS
        assert bus.is_egress_blocked() is False

    def test_unequal_registers_trap_with_the_graph_sheaf_coboundary(self):
        regs, bus = _fresh()
        regs.write_128bit(1, (10, 0, 0, 0))
        regs.write_128bit(2, (0, 10, 0, 0))
        with pytest.raises(TopologicalSheafFault, match="SHEAF_NONZERO_COBOUNDARY") as exc_info:
            _run(0x03, regs, bus, rd=5)
        sheaf = GraphSheaf(["x", "y"], [("x", "y")], 4)
        expected = sheaf.coboundary(sheaf.section({"x": [10, 0, 0, 0], "y": [0, 10, 0, 0]}))[0]
        assert exc_info.value.details["coboundary"] == [int(v) for v in expected] == [-10, 10, 0, 0]
        assert exc_info.value.details["residual_norm_sq"] == 200
        assert regs.get_status(5) == STATUS_FAULT
        assert bus.is_egress_blocked() is True
        with pytest.raises(TopologicalSheafFault, match="EGRESS_BLOCKED"):
            bus.write(0x1000, b"payload")
        assert bus.writes == []

    def test_every_single_coefficient_difference_is_caught(self):
        base = (5, -6, 7, -8)
        for position in range(4):
            for delta in (1, -1, 1 << 20):
                regs, bus = _fresh()
                changed = list(base)
                changed[position] += delta
                regs.write_128bit(1, base)
                regs.write_128bit(2, tuple(changed))
                with pytest.raises(TopologicalSheafFault):
                    _run(0x03, regs, bus)


# --------------------------------------------------------------------------- Reed-Solomon heal
class TestReedSolomonHeal:
    VALUE = (123456, -42, 7, WORD_MIN)

    def test_scrub_corrects_up_to_four_corrupted_bytes_in_place(self):
        for positions in ([0], [1, 15], [2, 5, 9], [0, 4, 8, 12]):
            regs, bus = _fresh()
            regs.write_128bit(7, self.VALUE)
            assert regs.inject_upset(7, positions) != self.VALUE
            res = _run(0x04, regs, bus, rd=7)
            assert res["ecc_result"] == "CORRECTED"
            assert res["corrected_byte_positions"] == positions
            assert regs.read_128bit(7) == res["repaired"] == self.VALUE
            assert bus.is_egress_blocked() is False

    def test_scrub_never_overwrites_a_legitimately_written_value(self):
        regs, bus = _fresh()
        regs.write_128bit(1, (1, 0, 0, 0))
        regs.write_128bit(2, (10, 0, 0, 0))
        res = _run(0x04, regs, bus, rs1=0, rs2=2, rd=1)
        assert res["ecc_result"] == "CLEAN" and res["corrected_byte_positions"] == []
        assert regs.read_128bit(1) == (1, 0, 0, 0)

    def test_five_corrupted_bytes_trap_and_close_the_gate(self):
        regs, bus = _fresh()
        regs.write_128bit(7, self.VALUE)
        regs.inject_upset(7, [0, 3, 6, 9, 12])
        with pytest.raises(RegisterECCFault, match="ECC_UNCORRECTABLE"):
            _run(0x04, regs, bus, rd=7)
        assert bus.is_egress_blocked() is True
        assert regs.get_status(7) == STATUS_FAULT

    def test_repair_depends_on_the_stored_parity(self):
        regs, _ = _fresh()
        regs.write_128bit(3, self.VALUE)
        envelope = regs.ecc[3]
        corrupted = regs.inject_upset(3, [2, 13])
        assert dsw_instanton_repair_alu(corrupted, envelope) == self.VALUE
        # mutation: parity of a different value does not give back this value
        wrong = protect_register((1, 2, 3, 4))
        try:
            assert dsw_instanton_repair_alu(corrupted, wrong) != self.VALUE
        except RegisterECCFault:
            pass


# --------------------------------------------------------------------------- remaining operations
class TestOtherOperations:
    def test_sign_test_writes_its_flag_and_traps_on_negative_c0(self):
        for c0, ok in ((10, True), (0, True), (-5, False)):
            regs, bus = _fresh()
            regs.write_128bit(1, (c0, 0, 0, 0))
            if ok:
                res = _run(0x06, regs, bus, rd=2)
                assert res["c0_nonnegative"] is True and regs.read_128bit(2) == (1, 0, 0, 0)
                assert regs.get_status(2) == STATUS_HARMONIC_CONSENSUS
            else:
                with pytest.raises(RicciCurvatureNeckFault, match="C0_NEGATIVE"):
                    _run(0x06, regs, bus, rd=2)
                assert regs.read_128bit(2) == (0, 0, 0, 0) and regs.get_status(2) == STATUS_FAULT
                assert bus.is_egress_blocked() is True

    def test_coordinate_projection_is_idempotent(self):
        regs, bus = _fresh()
        regs.write_128bit(1, (5, 7, 99, -120))
        first = _run(0x07, regs, bus, rs1=1, rd=2)
        second = _run(0x07, regs, bus, rs1=2, rd=3)
        assert first["dst"] == second["dst"] == (5, 7, 0, 0)
        assert first["removed_norm_sq"] == 99 * 99 + 120 * 120 and second["removed_norm_sq"] == 0

    def test_cat_map_is_a_permutation_so_it_does_not_erase(self):
        images = {((2 * x + y) % P, (x + y) % P) for x in range(P) for y in range(P)}
        assert len(images) == P * P
        regs, bus = _fresh()
        regs.write_128bit(1, (300, -2, 256, 13))
        res = _run(0x08, regs, bus, rs1=1, rd=2)
        x0, y0, x1, y1 = 300 % P, -2 % P, 256, 13
        assert res["dst"] == ((2 * x0 + y0) % P, (x0 + y0) % P, (2 * x1 + y1) % P, (x1 + y1) % P)
        assert res["inverse_recovers_input"] is True and res["input_mod_257"] == (x0, y0, x1, y1)

    def test_stark_eval_checks_the_quotient_identity_at_one_point(self):
        q_poly = [3, 1]
        p_poly = poly_mul(q_poly, compute_vanishing_polynomial_on_trace_domain())
        z = 5
        regs, bus = _fresh()
        regs.write_128bit(1, (poly_eval(p_poly, z), poly_eval(q_poly, z), z, 8))
        res = _run(0x05, regs, bus, rd=4)
        assert res["identity_holds"] is True and regs.read_128bit(4) == (1, 0, 0, 0)
        regs.write_128bit(1, ((poly_eval(p_poly, z) + 1) % P, poly_eval(q_poly, z), z, 8))
        res = _run(0x05, regs, bus, rd=4)
        assert res["identity_holds"] is False and regs.read_128bit(4) == (0, 0, 0, 0)
        assert regs.get_status(4) == STATUS_FAULT
        regs.write_128bit(1, (1, 1, 2, -1))
        with pytest.raises(ValueError):
            _run(0x05, regs, bus, rd=4)


# --------------------------------------------------------------------------- encoding and programs
class TestEncodingAndPrograms:
    def test_encode_decode_roundtrip_and_illegal_words(self):
        for opcode in FUNCT7_MAP:
            word = encode_t_isa_instruction(TISAInstruction(opcode, rd=5, rs1=12, rs2=31))
            assert word & 0x7F == 0x0B
            decoded = decode_t_isa_instruction(word)
            assert (decoded.opcode, decoded.rd, decoded.rs1, decoded.rs2) == (opcode, 5, 12, 31)
        with pytest.raises(ValueError):
            encode_t_isa_instruction(TISAInstruction(TISAOpcode.T_CYCLO_ADD, rd=32))
        with pytest.raises(ValueError):
            decode_t_isa_instruction((0x7F << 25) | 0x0B)

    def test_illegal_instructions_are_reported(self):
        regs, bus = _fresh()
        res = execute_t_isa_instruction(RoCCInstruction(funct7=0x7F), regs, bus)
        assert res["status"] == "ILLEGAL_INSTRUCTION" and res["rtl_semantics_match"] is True
        res = execute_t_isa_instruction(RoCCInstruction(funct7=0x01, opcode=0x2B), regs, bus)
        assert res["status"] == "ILLEGAL_INSTRUCTION" and res["model_cycles"] is None

    def test_model_cycles_follow_the_rtl_semantics_table(self):
        for funct7, rtl in RTL_SEMANTICS.items():
            regs, bus = _fresh()
            regs.write_128bit(1, (1, 2, 3, 4))
            regs.write_128bit(2, (1, 2, 3, 4))
            res = _run(funct7, regs, bus)
            assert "cycles" not in res
            assert res["rtl_semantics_match"] is rtl["matches_model"]
            assert res["model_cycles"] == (1 if rtl["matches_model"] else None)

    def test_program_recovers_a_storage_upset_but_not_a_real_disagreement(self):
        coproc = RISCVTopologicalCoprocessor()
        coproc.execute_instruction(TISAInstruction(TISAOpcode.T_LOAD_CYCLO, rd=1, imm=(7, 1, 0, 0)))
        coproc.execute_instruction(TISAInstruction(TISAOpcode.T_LOAD_CYCLO, rd=2, imm=(7, 1, 0, 0)))
        coproc.regfile.inject_upset(2, [3])
        res = coproc.execute_program([TISAInstruction(TISAOpcode.T_SHEAF_INSPECT, rs1=1, rs2=2, rd=4)])
        assert (res["faults_trapped"], res["ecc_recoveries"], res["unresolved_faults"]) == (1, 1, 0)
        assert res["status"] == "COMPLETED" and res["egress_blocked"] is True
        scrubbed = {s["register"]: s for s in res["faults"][0]["ecc_scrub"]}
        assert scrubbed[2]["ecc_result"] == "CORRECTED" and scrubbed[2]["corrected_byte_positions"] == [3]
        assert coproc.regfile.read(2) == CyclotomicZ5(7, 1, 0, 0)

        coproc = RISCVTopologicalCoprocessor()
        res = coproc.execute_program(
            [
                TISAInstruction(TISAOpcode.T_LOAD_CYCLO, rd=1, imm=(1, 0, 0, 0)),
                TISAInstruction(TISAOpcode.T_LOAD_CYCLO, rd=3, imm=(99, 0, 0, 0)),
                TISAInstruction(TISAOpcode.T_SHEAF_INSPECT, rs1=1, rs2=3),
            ]
        )
        assert (res["faults_trapped"], res["ecc_recoveries"], res["unresolved_faults"]) == (1, 0, 1)
        assert res["status"] == "COMPLETED_WITH_UNRESOLVED_FAULTS"
        assert [s["ecc_result"] for s in res["faults"][0]["ecc_scrub"]] == ["CLEAN", "CLEAN"]
        assert coproc.regfile.read(1) == CyclotomicZ5(1, 0, 0, 0)

    def test_diagnostic_program_outcome_is_computed(self):
        program = [
            TISAInstruction(TISAOpcode.T_LOAD_CYCLO, rd=1, imm=(1, 2, 0, 0)),
            TISAInstruction(TISAOpcode.T_LOAD_CYCLO, rd=2, imm=(3, 1, 0, 0)),
            TISAInstruction(TISAOpcode.T_CYCLO_ADD, rd=3, rs1=1, rs2=2),
            TISAInstruction(TISAOpcode.T_CYCLO_MUL, rd=4, rs1=1, rs2=2),
            TISAInstruction(TISAOpcode.T_SHEAF_INSPECT, rs1=1, rs2=1),
            TISAInstruction(TISAOpcode.T_STARK_EVAL, rs1=1),
        ]
        coproc = RISCVTopologicalCoprocessor()
        res = coproc.execute_program(program)
        assert res["status"] == "COMPLETED" and res["faults_trapped"] == 0
        assert res["instructions_completed"] == len(program)
        matched = sum(1 for inst in program if RTL_SEMANTICS.get(FUNCT7_MAP[inst.opcode], {}).get("matches_model"))
        assert res["model_cycles_total"] == matched == 3
        assert res["instructions_without_rtl_cycle_model"] == len(program) - matched
        assert coproc.regfile.read(4) == CyclotomicZ5(1, 2) * CyclotomicZ5(3, 1)
        json.dumps(res)


# --------------------------------------------------------------------------- trace receipts (zk-ML notes)
def _honest_package(simulate_tampering=False):
    engine = VerifiableNeuralComputeEngine("model_under_test")
    package = engine.generate_inference_proof("layer_dense_0", [10, 20, 30, 40], "a" * 64, simulate_tampering)
    return engine, package


def _pointwise_failures(com_w, trace):
    h = hashlib.sha256(com_w.encode("utf-8")).digest()
    a = h[0] % 17 + 1
    return [i for i in range(7) if (a * trace[i] + h[i + 1] % 13) % P != trace[i + 1]]


class TestTraceReceipts:
    def test_forward_pass_matches_an_independent_recurrence(self):
        com_w = "independent-check"
        h = hashlib.sha256(com_w.encode("utf-8")).digest()
        expected = [sum([5, 600, -3]) % P]
        for i in range(1, 8):
            expected.append((expected[-1] * (h[0] % 17 + 1) + h[i] % 13) % P)
        y, trace = forward_pass_with_trace([5, 600, -3], com_w)
        assert trace == expected and y == expected[-1]
        coeffs = interpolate_trace_polynomial(trace)
        assert [poly_eval(coeffs, w) for w in H] == trace

    def test_transition_vanishing_polynomial(self):
        z_t = transition_vanishing_polynomial()
        assert poly_mul(z_t, [(-H[7]) % P, 1]) == compute_vanishing_polynomial_on_trace_domain()
        assert [poly_eval(z_t, w) == 0 for w in H] == [True] * 7 + [False]

    def test_honest_receipt_verifies_and_states_its_limits(self):
        y, receipt = LineRateVerifiableNeuralCompute("w-commitment").execute_and_prove_inference([12, 24, 36, 48])
        assert receipt["verified"] is True and receipt["proof_type"] == PROOF_TYPE
        assert all(receipt["verification"]["checks"].values())
        assert receipt["challenge_z"] not in H
        props = receipt["properties"]
        assert (props["zero_knowledge"], props["succinct"], props["fri_low_degree_test"]) == (False, False, False)
        report = check_inference_receipt(receipt, "w-commitment", [12, 24, 36, 48], y)
        assert report["verified"] is True and report["failing_transitions"] == []
        assert verify_stark_quotient(receipt, "w-commitment", [12, 24, 36, 48], y) is True
        json.dumps(receipt)

    def test_simulated_tampering_is_found_by_the_quotient_remainder(self):
        engine, package = _honest_package(simulate_tampering=True)
        package["simulation"]["tampering_simulated"] = False  # flags are never trusted
        res = engine.verify_inference_proof(package)
        assert res["verified"] is False and res["status"] == "REJECTED"
        assert res["reason"] == "TRANSITION_CONSTRAINT_VIOLATED"
        assert res["failing_transitions"] == _pointwise_failures("a" * 64, package["proof"]["trace"]) == [2, 3]
        checks = res["checks"]
        assert checks["weights_root_registered"] and checks["commitment_matches"] and checks["evaluations_match"]
        assert checks["transitions_hold"] is False
        honest_engine, honest = _honest_package()
        assert honest_engine.verify_inference_proof(honest)["verified"] is True

    @pytest.mark.parametrize(
        "edit, reason",
        [
            (lambda p: p["proof"]["trace"].__setitem__(5, (p["proof"]["trace"][5] + 1) % P), "TRANSITION_CONSTRAINT_VIOLATED"),
            (lambda p: p.__setitem__("claimed_output", (p["claimed_output"] + 1) % P), "OUTPUT_MISMATCH"),
            (lambda p: p["proof"].__setitem__("eval_Q_at_z", (p["proof"]["eval_Q_at_z"] + 1) % P), "EVALUATION_MISMATCH"),
            (lambda p: p["proof"].__setitem__("challenge_z", (p["proof"]["challenge_z"] + 1) % P), "CHALLENGE_MISMATCH"),
            (lambda p: p["proof"].__setitem__("commitment", "0" * 64), "COMMITMENT_MISMATCH"),
            (lambda p: p.__setitem__("input_data", [10, 20, 30, 41]), "INPUT_MISMATCH"),
            (lambda p: p.__setitem__("weights_root", "f" * 64), "WEIGHTS_ROOT_NOT_REGISTERED"),
            (lambda p: p.__setitem__("layer_name", "layer_unknown"), "LAYER_NOT_REGISTERED"),
            (lambda p: p.__setitem__("proof", None), "MISSING_RECEIPT"),
            (lambda p: p["proof"].__setitem__("trace", [1, 2, 3]), "MALFORMED_TRACE"),
        ],
    )
    def test_post_hoc_edits_are_rejected(self, edit, reason):
        engine, package = _honest_package()
        edited = copy.deepcopy(package)
        edit(edited)
        res = engine.verify_inference_proof(edited)
        assert res["verified"] is False and res["reason"] == reason

    def test_self_consistent_receipt_under_other_weights_is_rejected(self):
        x = [10, 20, 30, 40]
        _, forged_trace = forward_pass_with_trace(x, "f" * 64)
        assert _pointwise_failures("a" * 64, forged_trace)
        engine = VerifiableNeuralComputeEngine()
        package = {
            "layer_name": "layer_dense_0",
            "weights_root": "a" * 64,
            "input_data": x,
            "claimed_output": forged_trace[-1],
            "proof": build_trace_receipt("a" * 64, x, forged_trace),
        }
        res = engine.verify_inference_proof(package)
        assert res["verified"] is False and res["reason"] == "TRANSITION_CONSTRAINT_VIOLATED"
        assert res["checks"]["commitment_matches"] and res["checks"]["evaluations_match"]

    def test_legacy_evaluation_only_receipt_is_rejected(self):
        # the previous verifier accepted any receipt with eval_P == eval_Q * eval_ZH (mod 257)
        legacy = {"com_W": "w", "eval_P_at_z": 6, "eval_Q_at_z": 2, "eval_ZH_at_z": 3}
        assert verify_stark_quotient(legacy, "w", [1, 2], 0) is False
        y, receipt = LineRateVerifiableNeuralCompute("authentic").execute_and_prove_inference([10, 20, 30, 40])
        assert verify_stark_quotient(receipt, "forged", [10, 20, 30, 40], y) is False

    def test_mutation_without_the_remainder_check_flips_the_transition_verdict(self, monkeypatch):
        _, package = _honest_package(simulate_tampering=True)
        receipt = package["proof"]
        args = (receipt, "a" * 64, package["input_data"], package["claimed_output"])
        assert check_inference_receipt(*args)["checks"]["transitions_hold"] is False
        real = zk_neural.poly_divmod
        monkeypatch.setattr(zk_neural, "poly_divmod", lambda num, den, modulus=P: (real(num, den, modulus)[0], [0]))
        assert check_inference_receipt(*args)["checks"]["transitions_hold"] is True

    def test_polynomial_helpers(self):
        assert polynomial_divide_exact([256, 0, 1], [256, 1]) == [1, 1]
        assert polynomial_divide_exact([257 * 3 - 1, 257, 1], [-1, 1]) == [1, 1]
        with pytest.raises(ValueError):
            polynomial_divide_exact([1, 0, 1], [256, 1])
        with pytest.raises(ZeroDivisionError):
            polynomial_divide_exact([1, 1], [0, 257])
        record = generate_fri_stark_proof([1, 0, 256], [1, 0, 0], [1])
        other = generate_fri_stark_proof([1, 0, 0], [1, 0, 0], [1])
        assert record["fri_performed"] is False and record["sha256_P"] != other["sha256_P"]
        p_poly = poly_mul([3, 1], compute_vanishing_polynomial_on_trace_domain())
        assert generate_fri_stark_proof(p_poly, [3, 1], compute_vanishing_polynomial_on_trace_domain())["identity_holds_at_z"]
        bumped = [(p_poly[0] + 1) % P] + p_poly[1:]
        assert not generate_fri_stark_proof(bumped, [3, 1], compute_vanishing_polynomial_on_trace_domain())["identity_holds_at_z"]


# --------------------------------------------------------------------------- executable checks
class TestExecutableChecks:
    def test_all_checks_hold_and_are_labelled_as_executable(self):
        audit = FormalTopologicalProofVerifier.verify_all_theorems()
        assert audit["verification_method"] == "EXECUTABLE_EXACT_CHECKS"
        assert audit["all_checks_hold"] is True and audit["checks_run"] == audit["checks_holding"] == 4
        assert all(c["holds"] and c["status"] == "HOLDS" and c["cases_checked"] > 0 for c in audit["checks"])
        assert audit["lean_specification"]["path"] == LEAN_SOURCE_PATH
        assert audit["lean_specification"]["machine_checked_in_ci"] is False
        text = json.dumps(audit)
        for banned in ("EAL", "FORMALLY_VERIFIED", "LEAN4_COMPLIANT", "CERTIF", "MATHEMATICALLY_PROVED"):
            assert banned not in text.upper()

    def test_lean_source_keeps_every_specified_theorem_with_real_proofs(self):
        source = LEAN_PATH.read_text(encoding="utf-8")
        for name in LEAN_THEOREMS:
            assert re.search(rf"\btheorem {re.escape(name.rsplit('.', 1)[1])}\b", source)
        # The original specification's declarations stay in the file.
        for name in ("cyclotomic_nilpotence_in_quotient", "sheaf_harmonic_consensus_iff_zero_coboundary",
                     "dsw_1_cycle_repair_bound"):
            assert re.search(rf"\btheorem {name}\b", source)
        for name in ("CellularSheaf", "DSWMonopoleRepair"):
            assert re.search(rf"\bstructure {name}\b", source)
        # Exact arithmetic only, and no unfinished proofs.
        for banned in ("sorry", "Float", "admit"):
            assert banned not in source

    def test_checks_fail_under_mutation(self, monkeypatch):
        monkeypatch.setattr(braids, "verify_relations", lambda: {"artin_relation": False})
        assert FormalTopologicalProofVerifier.run_check("braid_relations").holds is False

        def heal_nothing(received, envelope, received_parity=None):
            return {"repaired": bytes(received), "corrected_data_positions": [], "integrity_verified": True}

        monkeypatch.setattr(reed_solomon, "heal", heal_nothing)
        assert FormalTopologicalProofVerifier.run_check("reed_solomon_repair").holds is False

        monkeypatch.setattr(GraphSheaf, "is_coboundary", lambda self, c: {"is_coboundary": True})
        assert FormalTopologicalProofVerifier.run_check("cycle_sum_obstruction").holds is False

        monkeypatch.setattr(GraphSheaf, "coboundary", lambda self, s: [[0] * self.dim for _ in self.edges])
        assert FormalTopologicalProofVerifier.run_check("sheaf_coboundary_zero_iff_consistent").holds is False
