import sys
from fractions import Fraction
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[1] / "src")
if sys.path[:1] != [_SRC]:
    sys.path.insert(0, _SRC)

from turing.algorithms import bernstein_vazirani, deutsch_jozsa, gf2, qpe, simon, structured  # noqa: E402
from turing.algorithms.oracles import AffineOracle, BooleanOracle, FunctionOracle, LinearOracle  # noqa: E402

# Deterministic wide inputs: register sizes below are computed from these values.
DATA_BITS = 2499
WIDE_STRING = (3 ** 1575 % (1 << DATA_BITS)) | (1 << (DATA_BITS - 1))
SIMON_BITS = 1250
SIMON_PERIOD = (3 ** 790 % (1 << SIMON_BITS)) | (1 << (SIMON_BITS - 1)) | 1
PHASE_NUMERATOR = 3 ** 1600 % (1 << 2500)


def test_deutsch_jozsa_on_2500_qubits():
    for b in (0, 1):
        constant = structured.deutsch_jozsa_clifford(AffineOracle(DATA_BITS, 0, b))
        assert constant.num_qubits == 2500 and constant.data_qubits == DATA_BITS
        assert constant.verdict == "constant" and constant.probability_all_zero == 1
        balanced = structured.deutsch_jozsa_clifford(AffineOracle(DATA_BITS, WIDE_STRING, b))
        assert balanced.num_qubits == 2500
        assert balanced.verdict == "balanced" and balanced.probability_all_zero == 0
        assert balanced.data_support.dimension == 0 and balanced.data_support.offset == WIDE_STRING


def test_bernstein_vazirani_on_2500_qubits():
    oracle = AffineOracle(WIDE_STRING.bit_length(), WIDE_STRING, 1)
    result = structured.bernstein_vazirani_clifford(oracle)
    assert result.num_qubits == 2500 and result.data_qubits == 2499
    assert result.hidden_string == WIDE_STRING
    assert result.probability == 1
    assert result.deterministic_bits == 2499


def test_simon_on_2500_qubits():
    rows = structured.simon_kernel_matrix(SIMON_PERIOD, SIMON_BITS)
    assert gf2.nullspace(rows, SIMON_BITS) == (SIMON_PERIOD,)
    result = structured.simon_clifford(LinearOracle(SIMON_BITS, rows))
    assert result.num_qubits == 2500 and result.register_qubits == SIMON_BITS
    support = result.support
    assert support.offset == 0
    assert support.dimension == SIMON_BITS - 1
    assert all(gf2.parity(vector & SIMON_PERIOD) == 0 for vector in support.basis)
    assert result.outcome_probability == Fraction(1, 1 << (SIMON_BITS - 1))
    assert result.hidden_period == SIMON_PERIOD


def test_dyadic_phase_estimation_with_2500_qubits():
    assert PHASE_NUMERATOR.bit_length() == 2500 and PHASE_NUMERATOR % 2 == 1
    result = structured.dyadic_phase_estimation(Fraction(PHASE_NUMERATOR, 1 << 2500))
    assert result.precision_qubits == 2500
    assert result.numerator == PHASE_NUMERATOR
    assert result.probability == 1
    assert len(result.bit_probabilities) == 2500 and all(p == 1 for p in result.bit_probabilities)


def test_structured_paths_agree_with_dense_evaluation():
    for n in range(1, 6):
        for a in range(1 << n):
            for b in (0, 1):
                oracle = AffineOracle(n, a, b)
                dense_table = BooleanOracle.from_predicate(1 << n, oracle)
                assert deutsch_jozsa.run(n, dense_table).probability_all_zero == \
                    structured.deutsch_jozsa_clifford(oracle).probability_all_zero
                assert structured.bernstein_vazirani_clifford(oracle).hidden_string == \
                    bernstein_vazirani.run(n, dense_table).hidden_string == a
    for n in range(2, 5):
        for s in range(1, 1 << n):
            rows = structured.simon_kernel_matrix(s, n)
            oracle = LinearOracle(n, rows)
            dense = simon.run(n, FunctionOracle.from_function(1 << n, oracle))
            fast = structured.simon_clifford(oracle)
            assert fast.hidden_period == dense.hidden_period == s
            assert sorted(fast.support.elements()) == list(dense.support)
            assert all(dense.distribution[y] == fast.outcome_probability for y in dense.support)


def test_dyadic_semiclassical_readout_matches_the_dense_distribution():
    for t in range(1, 9):
        for numerator in (1, (1 << t) - 1, (5 * t + 3) % (1 << t)):
            phase = Fraction(numerator, 1 << t)
            fast = structured.dyadic_phase_estimation(phase, t)
            dense = qpe.recover_phase(phase, t)
            assert fast.numerator == dense.outcome and fast.probability == dense.probability == 1


def test_structured_paths_validate_their_inputs():
    try:
        structured.simon_clifford(LinearOracle(3, (0b001, 0b001, 0b000)))
    except ValueError as error:
        assert "Simon promise" in str(error)
    else:
        raise AssertionError("ker A of dimension 2 violates Simon's promise")
    try:
        structured.deutsch_jozsa_clifford(BooleanOracle.from_list([0, 1]))
    except TypeError:
        pass
    else:
        raise AssertionError("the structured path needs an AffineOracle")
    try:
        structured.dyadic_phase_estimation(Fraction(1, 3))
    except ValueError:
        pass
    else:
        raise AssertionError("1/3 is not dyadic")
