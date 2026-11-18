"""Exact tests for AL HARAS threshold secret sharing and transfer-batch boundary checks.

Known answers are computed independently in this file (Lucas-Lehmer, rational
Vandermonde solves, signed incidence matrices, naive point counts); mutation
tests show that the assertions reject plausible wrong implementations.
"""

import hashlib
import inspect
import random
from fractions import Fraction
from itertools import combinations, product

import pytest

from chronus.security.al_haras import fingerprint
from chronus.security.al_haras import sovereign_settlement as ss
from chronus.security.al_haras import threshold_mpc as tm
from chronus.security.al_haras.sovereign_settlement import (
    EXTERNAL_ISSUER,
    HomologicalSettlementEngine,
    Ledger1Chain,
    SovereignCBDCSettlementEngine,
    SovereignCentralBank,
    SovereignSettlementRejection,
    SovereignTransferSimplex,
    boundary_operator_1,
    commit_settlement_ledger,
    create_ledger_transition_chain,
    evaluate_boundary_operator_1,
    verify_hecke_eigenform_invariant,
)
from chronus.security.al_haras.threshold_mpc import (
    FIELD_PRIME,
    BunkerLocation,
    InsufficientSharesError,
    TopologicalThresholdMPC,
    interpolate_at_zero,
    points_consistent,
    split_secret,
)

pytestmark = pytest.mark.real

A, B, C = (SovereignCentralBank.CENTRAL_BANK_A, SovereignCentralBank.CENTRAL_BANK_B, SovereignCentralBank.CENTRAL_BANK_C)


# ==============================================================================
# Independent references
# ==============================================================================


def lucas_lehmer(p):
    """Deterministic primality proof for the Mersenne number 2^p - 1 (p an odd prime)."""
    m = (1 << p) - 1
    s = 4
    for _ in range(p - 2):
        s = (s * s - 2) % m
    return s == 0


def solve_rational(matrix, rhs):
    """Gauss-Jordan elimination over Q (independent of the module's modular Lagrange)."""
    n = len(matrix)
    aug = [[Fraction(v) for v in row] + [Fraction(r)] for row, r in zip(matrix, rhs)]
    for col in range(n):
        pivot = next(r for r in range(col, n) if aug[r][col] != 0)
        aug[col], aug[pivot] = aug[pivot], aug[col]
        lead = aug[col][col]
        aug[col] = [v / lead for v in aug[col]]
        for r in range(n):
            if r != col and aug[r][col] != 0:
                factor = aug[r][col]
                aug[r] = [a - factor * b for a, b in zip(aug[r], aug[col])]
    return [row[-1] for row in aug]


def incidence_boundary(legs):
    """d1 via an explicit signed incidence matrix times the amount vector."""
    vertices = sorted({v for s, d, _ in legs for v in (s, d)})
    matrix = [[(1 if d == v else 0) - (1 if s == v else 0) for s, d, _ in legs] for v in vertices]
    amounts = [a for _, _, a in legs]
    return {v: sum(m * a for m, a in zip(row, amounts)) for v, row in zip(vertices, matrix)}


def naive_frobenius_trace(a, b, p):
    """a_p = p + 1 - #E(F_p) by brute force over all (x, y) pairs."""
    affine = sum(1 for x in range(p) for y in range(p) if (y * y - (x ** 3 + a * x + b)) % p == 0)
    return p + 1 - (affine + 1)


# ==============================================================================
# Threshold secret sharing
# ==============================================================================


class TestShamirArithmetic:
    def test_field_prime_is_the_mersenne_prime_m521(self):
        assert FIELD_PRIME == 2 ** 521 - 1
        assert lucas_lehmer(521) is True
        assert lucas_lehmer(523) is False  # 2^523 - 1 is composite: the check is not vacuous

    def test_known_answer_against_independent_rational_solver(self):
        coefficients = [1234, 166, 94]
        points = [(x, sum(c * x ** k for k, c in enumerate(coefficients))) for x in range(1, 7)]
        for subset in combinations(points, 3):
            assert interpolate_at_zero(list(subset)) == 1234
            vandermonde = [[x ** k for k in range(3)] for x, _ in subset]
            assert solve_rational(vandermonde, [y for _, y in subset]) == coefficients

    def test_known_answer_in_a_small_field(self):
        p = 1613
        coefficients = [1234, 166, 94]
        points = [(x, sum(c * x ** k for k, c in enumerate(coefficients)) % p) for x in range(1, 7)]
        assert all(interpolate_at_zero(list(s), prime=p) == 1234 for s in combinations(points, 3))
        assert points_consistent(points, 3, prime=p) is True
        bad = points[:5] + [(6, (points[5][1] + 1) % p)]
        assert points_consistent(bad, 3, prime=p) is False

    def test_every_t_subset_recovers_and_t_minus_1_does_not(self):
        secret = 0x1F2E3D4C5B6A79880102030405060708
        shares = split_secret(secret, 3, 5)
        assert len({x for x, _ in shares}) == 5
        for k in (3, 4, 5):
            for subset in combinations(shares, k):
                assert interpolate_at_zero(list(subset)) == secret
        # Two shares fix a line, not the degree-2 polynomial: the intercept is not the secret
        # except with probability 1/P per pair.
        assert all(interpolate_at_zero(list(s)) != secret for s in combinations(shares, 2))

    def test_fewer_than_t_shares_reveal_nothing_exhaustive_small_field(self):
        """For every secret, (a1, a2) -> (f(1), f(2)) is a bijection of F_13^2:
        two shares are uniformly distributed whatever the secret is."""
        p = 13
        for secret in range(p):
            images = {
                (tm.evaluate_polynomial([secret, a1, a2], 1, p), tm.evaluate_polynomial([secret, a1, a2], 2, p))
                for a1, a2 in product(range(p), repeat=2)
            }
            assert len(images) == p * p

    def test_invalid_inputs_rejected(self):
        with pytest.raises(tm.ThresholdCustodyError):
            split_secret(FIELD_PRIME, 2, 3)
        with pytest.raises(tm.ThresholdCustodyError):
            split_secret(5, 4, 3)
        with pytest.raises(TypeError):
            split_secret(True, 2, 3)
        with pytest.raises(tm.ThresholdCustodyError):
            interpolate_at_zero([(1, 5), (1, 6)])
        with pytest.raises(InsufficientSharesError):
            points_consistent([(1, 5)], 2)

    def test_mutation_wrong_lagrange_basis_is_caught(self):
        def mutant(points, prime=FIELD_PRIME):
            total = 0
            for j, (xj, yj) in enumerate(points):
                num = den = 1
                for m, (xm, _) in enumerate(points):
                    if m != j:
                        num = num * (0 - xj) % prime  # bug: should be (0 - xm)
                        den = den * (xj - xm) % prime
                total = (total + yj * num * pow(den, -1, prime)) % prime
            return total

        points = [(x, (1234 + 166 * x + 94 * x * x) % FIELD_PRIME) for x in (1, 2, 3)]
        assert interpolate_at_zero(points) == 1234
        assert mutant(points) != 1234


class TestThresholdCustodyEngine:
    def setup_method(self, method):
        self.mpc = TopologicalThresholdMPC(threshold_t=3, total_bunkers_n=5)
        self.shares = self.mpc.generate_distributed_braid_shares("unit-test-seed")

    def test_shares_commitments_and_labels(self):
        assert sorted(self.shares) == [f"BUNKER_{i:02d}" for i in range(1, 6)]
        commitments = self.mpc.share_commitments
        for bunker_id, share in self.shares.items():
            assert self.mpc.verify_share(share) is True
            assert commitments[bunker_id] == share.share_hash
        assert len(set(commitments.values())) == 5
        assert "share_value" not in repr(next(iter(self.shares.values())))

    def test_custodian_labels_are_neutral(self):
        banned = ("STRATCOM", "OFFUTT", "MOD", "WHITEHALL", "NATO", "SHAPE", "DND", "CARLING", "ASD", "CANBERRA", "EMBASSY")
        for member in BunkerLocation:
            assert not any(word in member.value or word in member.name for word in banned)
        source = inspect.getsource(tm)
        for phrase in ("FIPS 204", "Five Eyes", "STRATCOM", "PKCS#11 HSM custody"):
            assert phrase not in source

    def test_reconstruction_from_every_quorum(self):
        expected = tm.secret_from_seed("unit-test-seed")
        for k in (3, 4, 5):
            for subset in combinations(self.shares.values(), k):
                assert self.mpc.reconstruct_secret(subset) == expected

    def test_reconstruction_refuses_fewer_than_t(self):
        for subset in combinations(self.shares.values(), 2):
            with pytest.raises(InsufficientSharesError):
                self.mpc.reconstruct_secret(subset)

    @pytest.mark.parametrize("field_name", ["share_value", "blinding_nonce", "share_index"])
    def test_any_tampered_field_fails_its_commitment(self, field_name):
        share = self.mpc.custodian_share("BUNKER_02")
        if field_name == "share_value":
            share.share_value = (share.share_value + 1) % FIELD_PRIME
        elif field_name == "blinding_nonce":
            share.blinding_nonce = bytes([share.blinding_nonce[0] ^ 1]) + share.blinding_nonce[1:]
        else:
            share.share_index = 3
        assert self.mpc.verify_share(share) is False

    def test_swapped_share_under_another_id_is_rejected(self):
        stolen = self.mpc.custodian_share("BUNKER_01")
        stolen.bunker_id = "BUNKER_02"
        assert self.mpc.verify_share(stolen) is False

    def test_mutation_skipping_commitments_gives_a_wrong_key(self):
        held = [self.mpc.custodian_share(b) for b in ("BUNKER_01", "BUNKER_02", "BUNKER_03")]
        held[1].share_value = (held[1].share_value + 1) % FIELD_PRIME
        naive = interpolate_at_zero([(s.share_index, s.share_value) for s in held])
        assert naive != tm.secret_from_seed("unit-test-seed")
        assert points_consistent(
            [(s.share_index, s.share_value) for s in held] + [(4, self.shares["BUNKER_04"].share_value)], 3
        ) is False

    def test_quorum_signature_verifies_only_for_its_payload_and_key(self):
        res = self.mpc.authorize_sovereign_action(b"rotate-key-17", ["BUNKER_01", "BUNKER_03", "BUNKER_05"])
        assert res["authorized"] is True and res["status"] == "QUORUM_MET" and res["reason"] is None
        assert res["action_digest"] == hashlib.sha256(b"rotate-key-17").hexdigest()
        token, key = res["joint_authorization_token"], res["verification_public_key_hex"]
        assert tm.verify_joint_authorization(b"rotate-key-17", token, key) is True
        assert tm.verify_joint_authorization(b"rotate-key-18", token, key) is False
        other = TopologicalThresholdMPC(3, 5)
        other.generate_distributed_braid_shares()
        assert tm.verify_joint_authorization(b"rotate-key-17", token, other.verification_public_key_hex) is False

    def test_injected_tamper_is_detected_by_computation(self):
        res = self.mpc.authorize_sovereign_action(
            b"payload", ["BUNKER_01", "BUNKER_02", "BUNKER_03", "BUNKER_04"], injected_compromised_bunker="BUNKER_02"
        )
        assert res["authorized"] is True
        assert res["isolated_compromised_bunkers"] == ["BUNKER_02"]
        assert res["valid_shares_verified"] == 3
        res = self.mpc.authorize_sovereign_action(
            b"payload", ["BUNKER_01", "BUNKER_02", "BUNKER_03"], injected_compromised_bunker="BUNKER_02"
        )
        assert res["authorized"] is False and res["joint_authorization_token"] is None
        assert "QUORUM_DEFICIT" in res["reason"] and res["status"] == "QUORUM_NOT_MET"

    def test_duplicates_and_unknown_participants_do_not_count(self):
        res = self.mpc.authorize_sovereign_action(b"x", ["BUNKER_01", "BUNKER_01", "BUNKER_02", "BUNKER_99"])
        assert res["authorized"] is False
        assert res["valid_shares_verified"] == 2
        assert res["unknown_bunkers"] == ["BUNKER_99"]
        assert res["duplicate_bunkers_ignored"] == ["BUNKER_01"]

    def test_seed_fixes_the_secret_but_not_the_shares(self):
        again = TopologicalThresholdMPC(3, 5)
        again_shares = again.generate_distributed_braid_shares("unit-test-seed")
        assert again.verification_public_key_hex == self.mpc.verification_public_key_hex
        assert all(again_shares[b].share_value != self.shares[b].share_value for b in self.shares)
        assert again.verify_share(self.shares["BUNKER_01"]) is False

    def test_parameter_and_state_validation(self):
        with pytest.raises(ValueError):
            TopologicalThresholdMPC(threshold_t=1, total_bunkers_n=5)
        with pytest.raises(ValueError):
            TopologicalThresholdMPC(threshold_t=6, total_bunkers_n=5)
        with pytest.raises(TypeError):
            TopologicalThresholdMPC(threshold_t=True, total_bunkers_n=5)
        fresh = TopologicalThresholdMPC(2, 3)
        with pytest.raises(tm.ThresholdCustodyError):
            fresh.authorize_sovereign_action(b"x", ["BUNKER_01", "BUNKER_02"])
        with pytest.raises(TypeError):
            self.mpc.authorize_with_shares("text", list(self.shares.values()))

    def test_larger_n_than_named_labels(self):
        mpc = TopologicalThresholdMPC(threshold_t=4, total_bunkers_n=7)
        shares = mpc.generate_distributed_braid_shares()
        assert shares["BUNKER_07"].bunker_location is None
        res = mpc.authorize_with_shares(b"y", [shares[b] for b in ("BUNKER_02", "BUNKER_04", "BUNKER_06", "BUNKER_07")])
        assert res["authorized"] is True


# ==============================================================================
# Transfer-batch boundary checks
# ==============================================================================


def _batch(*legs):
    return [SovereignTransferSimplex(f"tx{i}", s, d, a) for i, (s, d, a) in enumerate(legs)]


class TestBoundaryOperator:
    def test_known_answer_matches_incidence_matrix(self):
        legs = [("A", "B", 5), ("B", "C", 3), ("C", "A", 2), ("A", "C", 7)]
        assert boundary_operator_1(legs) == incidence_boundary(legs) == {"A": -10, "B": 2, "C": 8}

    def test_conservation_identity_and_linearity_random(self):
        rng = random.Random(20261111)
        accounts = [f"N{i}" for i in range(6)]
        for _ in range(200):
            legs = []
            for _ in range(rng.randint(1, 12)):
                s, d = rng.sample(accounts, 2)
                legs.append((s, d, rng.randint(0, 10 ** 12)))
            d1 = boundary_operator_1(legs)
            assert sum(d1.values()) == 0
            assert d1 == incidence_boundary(legs)
            half = len(legs) // 2
            left, right = boundary_operator_1(legs[:half]), boundary_operator_1(legs[half:])
            assert all(d1.get(v, 0) == left.get(v, 0) + right.get(v, 0) for v in set(d1) | set(left) | set(right))

    def test_invalid_legs_rejected(self):
        with pytest.raises(ValueError):
            boundary_operator_1([("A", "A", 1)])
        with pytest.raises(ValueError):
            boundary_operator_1([("A", "B", -1)])
        with pytest.raises(TypeError):
            boundary_operator_1([("A", "B", 1.5)])
        with pytest.raises(TypeError):
            boundary_operator_1([("A", "B", True)])

    def test_mutation_outflow_only_boundary_is_caught(self):
        def check(fn):
            legs = [("A", "B", 5), ("B", "C", 3), ("C", "A", 2)]
            result = fn(legs)
            return result == incidence_boundary(legs) and sum(result.values()) == 0

        def mutant(legs):
            out = {}
            for s, d, a in legs:
                out[s] = out.get(s, 0) - a
                out.setdefault(d, 0)
            return out

        assert check(boundary_operator_1) is True
        assert check(mutant) is False


class TestHomologicalSettlementEngine:
    def test_clearing_cycle_settles(self):
        res = HomologicalSettlementEngine().settle_transfer_batch(_batch((A, B, 10), (B, C, 10), (C, A, 10)))
        assert res["settlement_status"] == "SETTLED_CLOSED_1_CYCLE"
        assert res["is_homologically_closed"] is True and res["is_cycle"] is True
        assert res["boundary_norm"] == 0 and res["net_position_sum"] == 0
        assert res["rtgs_receipt_id"].startswith("rtgs_rcpt_")
        assert res["balance_check_performed"] is False

    def test_open_chain_rejected_with_computed_residuals(self):
        res = HomologicalSettlementEngine().settle_transfer_batch(_batch((A, B, 10), (B, C, 4)))
        assert res["settlement_status"] == "REJECTED_BOUNDARY_MISMATCH"
        assert res["boundary_residuals"] == {"CENTRAL_BANK_A": -10, "CENTRAL_BANK_B": 6, "CENTRAL_BANK_C": 4}
        assert res["boundary_norm"] == 20 and res["rtgs_receipt_id"] is None
        assert res["total_liquidity_settled"] == 0

    def test_declared_external_issuance(self):
        engine = HomologicalSettlementEngine()
        batch = _batch((EXTERNAL_ISSUER, A, 100), (A, B, 40))
        declared = {EXTERNAL_ISSUER: -100, A: 60, B: 40}
        ok = engine.settle_transfer_batch(batch, declared_net_positions=declared)
        assert ok["settlement_status"] == "SETTLED_DECLARED_NET_POSITIONS"
        assert engine.settle_transfer_batch(batch)["settlement_status"] == "REJECTED_BOUNDARY_MISMATCH"
        wrong = engine.settle_transfer_batch(batch, declared_net_positions={EXTERNAL_ISSUER: -99, A: 59, B: 40})
        assert wrong["boundary_norm"] == 2
        closes, residual, norm = engine.verify_cycle_boundary(
            _batch((A, B, 7), (B, A, 7)), simulate_unbacked_inflation=True
        )
        assert (closes, residual, norm) == (False, {"CENTRAL_BANK_A": 7, EXTERNAL_ISSUER: -7}, 14)

    def test_double_spend_is_a_balance_violation(self):
        engine = HomologicalSettlementEngine(opening_balances={A: 10})
        declared = {A: -20, B: 10, C: 10}
        res = engine.settle_transfer_batch(_batch((A, B, 10), (A, C, 10)), declared_net_positions=declared)
        assert res["is_homologically_closed"] is True
        assert res["settlement_status"] == "REJECTED_INSUFFICIENT_BALANCE"
        assert res["overdrafts"] == [{"leg": 1, "account": "CENTRAL_BANK_A", "available": 0, "debit": 10, "shortfall": 10}]
        assert engine.balances == {"CENTRAL_BANK_A": 10}
        ok = engine.settle_transfer_batch(_batch((A, B, 10)), declared_net_positions={A: -10, B: 10})
        assert ok["settlement_status"] == "SETTLED_DECLARED_NET_POSITIONS"
        assert engine.balances == {"CENTRAL_BANK_A": 0, "CENTRAL_BANK_B": 10}
        again = engine.settle_transfer_batch(_batch((A, C, 1)), declared_net_positions={A: -1, C: 1})
        assert again["settlement_status"] == "REJECTED_INSUFFICIENT_BALANCE"

    def test_gross_replay_order_matters(self):
        engine = HomologicalSettlementEngine(opening_balances={B: 10})
        declared = {B: -10, C: 10}
        late = engine.settle_transfer_batch(_batch((A, C, 10), (B, A, 10)), declared_net_positions=declared)
        assert late["settlement_status"] == "REJECTED_INSUFFICIENT_BALANCE"
        early = engine.settle_transfer_batch(_batch((B, A, 10), (A, C, 10)), declared_net_positions=declared)
        assert early["settlement_status"] == "SETTLED_DECLARED_NET_POSITIONS"

    def test_replay_hook_changes_the_input_and_detection_is_computed(self):
        res = HomologicalSettlementEngine().settle_transfer_batch(
            _batch((A, B, 10), (B, C, 10), (C, A, 10)), simulate_double_spend=True
        )
        assert res["transfers_in_batch"] == 4
        assert res["injected_test_perturbation"] == "replayed_first_transfer"
        assert res["duplicate_transfer_ids"] == ["tx0"]
        assert res["boundary_norm"] == 20
        assert res["settlement_status"] == "REJECTED_BOUNDARY_MISMATCH"

    def test_duplicate_ids_rejected_even_when_closed(self):
        batch = [SovereignTransferSimplex("same", A, B, 5), SovereignTransferSimplex("same", B, A, 5)]
        res = HomologicalSettlementEngine().settle_transfer_batch(batch)
        assert res["is_homologically_closed"] is True
        assert res["settlement_status"] == "REJECTED_DUPLICATE_TRANSFER_ID"

    def test_empty_and_malformed_batches(self):
        engine = HomologicalSettlementEngine()
        with pytest.raises(ValueError):
            engine.settle_transfer_batch([])
        with pytest.raises(ValueError):
            engine.settle_transfer_batch(_batch((A, A, 1)))
        with pytest.raises(ValueError):
            engine.settle_transfer_batch([SovereignTransferSimplex("", A, B, 1)])

    def test_neutral_identifiers_only(self):
        source = inspect.getsource(ss)
        for name in ("BANK_OF_ENGLAND", "FEDERAL_RESERVE", "EUROPEAN_CENTRAL_BANK", "BANK_OF_JAPAN", "SWISS", "BIS_", "FedNow", "CHAPS", "TARGET2", "admissible"):
            assert name not in source
        assert all(member.value.startswith("CENTRAL_BANK_") for member in SovereignCentralBank)


class TestSingleInstructionEngine:
    NODES = ["CENTRAL_BANK_A", "CENTRAL_BANK_B", "CENTRAL_BANK_C"]

    def test_accepted_instruction_receipt_is_computed(self):
        engine = SovereignCBDCSettlementEngine(self.NODES)
        receipt = engine.process_cross_border_settlement("CENTRAL_BANK_A", "CENTRAL_BANK_B", 25_000_000)
        assert receipt.status == "SETTLED_HOMOLOGICALLY_CONSERVED"
        assert receipt.boundary_defect == 0
        assert receipt.net_positions == {"CENTRAL_BANK_A": -25_000_000, "CENTRAL_BANK_B": 25_000_000}
        assert receipt.net_position_sum == 0
        assert receipt.settlement_id == f"cbdc_{receipt.receipt_digest[:24]}"
        curve = fingerprint.curve_from_payload(bytes.fromhex(receipt.receipt_digest))
        assert receipt.hecke_eigenvalue_ap == naive_frobenius_trace(curve["a"], curve["b"], 257)
        assert receipt.weil_bound == 32 and 32 * 32 <= 4 * 257 < 33 * 33
        assert receipt.hecke_eigenvalue_ap ** 2 <= 4 * 257
        second = engine.process_cross_border_settlement("CENTRAL_BANK_A", "CENTRAL_BANK_B", 25_000_000)
        assert second.settlement_id != receipt.settlement_id

    def test_replayed_leg_rejected_with_computed_evidence(self):
        engine = SovereignCBDCSettlementEngine(self.NODES)
        with pytest.raises(SovereignSettlementRejection) as info:
            engine.process_cross_border_settlement("CENTRAL_BANK_A", "CENTRAL_BANK_B", 25_000_000, simulate_double_spend=True)
        exc = info.value
        assert "HOMOLOGICAL_BOUNDARY_DEFECT_DETECTED" in str(exc)
        assert exc.reasons == ["HOMOLOGICAL_BOUNDARY_DEFECT_DETECTED", "INSUFFICIENT_AVAILABLE_BALANCE"]
        assert exc.boundary_defect == 50_000_000
        assert exc.boundary_residuals == {"CENTRAL_BANK_A": -25_000_000, "CENTRAL_BANK_B": 25_000_000}
        assert exc.overdraft == 25_000_000
        assert exc.to_dict()["boundary_defect"] == 50_000_000
        rejection = SovereignCBDCSettlementEngine(self.NODES)
        with pytest.raises(SovereignSettlementRejection) as other:
            rejection.process_cross_border_settlement("CENTRAL_BANK_A", "CENTRAL_BANK_B", 7, simulate_double_spend=True)
        assert other.value.boundary_defect == 14

    def test_zero_amount_replay_spends_nothing(self):
        receipt = SovereignCBDCSettlementEngine(self.NODES).process_cross_border_settlement(
            "CENTRAL_BANK_A", "CENTRAL_BANK_B", 0, simulate_double_spend=True
        )
        assert receipt.boundary_defect == 0
        assert receipt.injected_test_perturbations == ["replayed_leg"]

    def test_ledger_mode_detects_overspending_across_calls(self):
        engine = SovereignCBDCSettlementEngine(self.NODES, opening_balances={"CENTRAL_BANK_A": 100})
        engine.process_cross_border_settlement("CENTRAL_BANK_A", "CENTRAL_BANK_B", 80)
        assert engine.balances == {"CENTRAL_BANK_A": 20, "CENTRAL_BANK_B": 80, "CENTRAL_BANK_C": 0}
        with pytest.raises(SovereignSettlementRejection) as info:
            engine.process_cross_border_settlement("CENTRAL_BANK_A", "CENTRAL_BANK_C", 80)
        assert info.value.reasons == ["INSUFFICIENT_AVAILABLE_BALANCE"]
        assert info.value.boundary_defect == 0 and info.value.overdraft == 60
        assert engine.balances["CENTRAL_BANK_A"] == 20

    @pytest.mark.parametrize(
        "sender,receiver,amount,code",
        [
            ("CENTRAL_BANK_A", "CENTRAL_BANK_Z", 5, "UNKNOWN_PARTICIPANT:CENTRAL_BANK_Z"),
            ("CENTRAL_BANK_A", "CENTRAL_BANK_A", 5, "SENDER_EQUALS_RECEIVER"),
            ("CENTRAL_BANK_A", "CENTRAL_BANK_B", -5, "INVALID_AMOUNT"),
            ("CENTRAL_BANK_A", "CENTRAL_BANK_B", True, "INVALID_AMOUNT"),
            ("", "CENTRAL_BANK_B", 5, "INVALID_SENDER_IDENTIFIER"),
        ],
    )
    def test_invalid_instructions_rejected_before_boundary(self, sender, receiver, amount, code):
        with pytest.raises(SovereignSettlementRejection) as info:
            SovereignCBDCSettlementEngine(self.NODES).process_cross_border_settlement(sender, receiver, amount)
        assert code in info.value.reasons
        assert info.value.boundary_defect is None

    def test_constructor_validation(self):
        with pytest.raises(ValueError):
            SovereignCBDCSettlementEngine([])
        with pytest.raises(ValueError):
            SovereignCBDCSettlementEngine(["X", "X"])
        with pytest.raises(ValueError):
            SovereignCBDCSettlementEngine(["X"], opening_balances={"Y": 1})
        with pytest.raises(ValueError):
            SovereignCBDCSettlementEngine(["X"], opening_balances={"X": -1})


class TestLedgerChainFunctions:
    def test_chain_defects(self):
        assert evaluate_boundary_operator_1(create_ledger_transition_chain("N1", "N2", 5_000_000)) == 0
        assert evaluate_boundary_operator_1(create_ledger_transition_chain("N1", "N2", 9, simulate_double_spend=True)) == 18
        inflated = create_ledger_transition_chain("N1", "N2", 9, simulate_inflation=True)
        assert evaluate_boundary_operator_1(inflated) == 18
        assert inflated.metadata["injected_test_perturbations"] == ["undeclared_issuance_leg"]
        assert evaluate_boundary_operator_1(Ledger1Chain(simplices=[("N1", "N2", 3), ("N2", "N1", 3)])) == 0
        assert evaluate_boundary_operator_1(Ledger1Chain(simplices=[("N1", "N2", 3)])) == 6

    def test_commit_refuses_open_chains_and_ids_are_unique(self):
        with pytest.raises(SovereignSettlementRejection) as info:
            commit_settlement_ledger(Ledger1Chain(simplices=[("N1", "N2", 3)]))
        assert info.value.boundary_defect == 6
        chain = create_ledger_transition_chain("N1", "N2", 3)
        assert commit_settlement_ledger(chain) != commit_settlement_ledger(chain)

    def test_fingerprint_self_test_and_prime_validation(self):
        chain = create_ledger_transition_chain("N1", "N2", 3)
        assert verify_hecke_eigenform_invariant(chain, p=257) is True
        assert verify_hecke_eigenform_invariant(chain, p=101) is True
        for bad in (255, 3, 1 << 21, True):
            with pytest.raises(ValueError):
                verify_hecke_eigenform_invariant(chain, p=bad)
