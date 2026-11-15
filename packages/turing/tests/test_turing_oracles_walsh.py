import sys
from fractions import Fraction
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[1] / "src")
if sys.path[:1] != [_SRC]:
    sys.path.insert(0, _SRC)

from turing.algorithms import deutsch_jozsa, gf2, oracles, walsh  # noqa: E402
from turing.algorithms.oracles import (  # noqa: E402
    AffineOracle,
    BooleanOracle,
    FunctionOracle,
    LinearOracle,
    Oracle,
)


class _PlainParity:
    """Duck-typed oracle: no subclassing, just domain_size and __call__."""

    def __init__(self, n):
        self.domain_size = 1 << n

    def __call__(self, x):
        return x.bit_count() & 1


def _raises(error, function, *args):
    try:
        function(*args)
    except error:
        return True
    raise AssertionError(f"{function.__name__}{args!r} did not raise {error.__name__}")


def test_protocol_accepts_duck_typed_objects():
    oracle = _PlainParity(3)
    assert isinstance(oracle, Oracle)
    assert oracles.boolean_table(oracle) == tuple(x.bit_count() & 1 for x in range(8))
    assert deutsch_jozsa.run(3, oracle).verdict == "balanced"


def test_constructors_from_predicate_dict_and_list():
    by_predicate = BooleanOracle.from_predicate(8, lambda x: x % 3 == 0)
    assert by_predicate.table == (1, 0, 0, 1, 0, 0, 1, 0)
    assert BooleanOracle.from_marked(8, [0, 3, 6]).table == by_predicate.table
    assert BooleanOracle.from_list([1, 0, 0, 1, 0, 0, 1, 0]).table == by_predicate.table
    assert BooleanOracle.from_dict({0: 1, 1: 0, 2: 0, 3: 1}).table == (1, 0, 0, 1)
    function = FunctionOracle.from_function(6, lambda x: x * x % 7)
    assert function.domain_size == 6 and function(4) == 2
    assert FunctionOracle.from_dict({1: 5, 0: 9}).table == (9, 5)
    assert FunctionOracle.from_list([True, False]).table == (1, 0)


def test_validation_errors_are_clear():
    _raises(ValueError, BooleanOracle.from_list, [0, 2])
    _raises(ValueError, FunctionOracle.from_dict, {1: 0})
    _raises(ValueError, FunctionOracle.from_list, [])
    _raises(ValueError, BooleanOracle.from_marked, 4, [4])
    _raises(ValueError, BooleanOracle.from_predicate, 4, lambda x: 7)
    _raises(ValueError, FunctionOracle.from_list([1, 2]), 2)
    _raises(TypeError, oracles.function_table, object())
    _raises(ValueError, oracles.qubits_for_domain, 12)
    assert oracles.qubits_for_domain(16) == 4

    class _BadValue:
        domain_size = 2

        def __call__(self, x):
            return "one"

    _raises(ValueError, oracles.function_table, _BadValue())
    _raises(ValueError, oracles.require_qubit_domain, BooleanOracle.from_list([0, 1, 1, 0]), 3)


def test_promise_helpers():
    assert oracles.require_constant_or_balanced([1, 1, 1, 1]) == "constant"
    assert oracles.require_constant_or_balanced([0, 1, 1, 0]) == "balanced"
    _raises(ValueError, oracles.require_constant_or_balanced, [0, 0, 0, 1])
    assert oracles.require_affine([1, 0, 1, 0], 2) == (1, 1)
    _raises(ValueError, oracles.require_affine, [0, 0, 0, 1], 2)
    assert oracles.require_simon_promise([4, 9, 9, 4], 2) == 3
    assert oracles.require_simon_promise([5, 6, 7, 8], 2) == 0
    _raises(ValueError, oracles.require_simon_promise, [1, 1, 1, 2], 2)
    _raises(ValueError, oracles.require_simon_promise, [1, 1, 2, 3], 2)


def test_dense_domain_limit_points_to_structured_paths():
    huge = AffineOracle(40, 5, 0)
    assert huge.domain_size == 1 << 40
    _raises(ValueError, deutsch_jozsa.run, 40, huge)


def test_affine_and_linear_oracles():
    affine = AffineOracle(4, 0b1011, 1)
    assert [affine(x) for x in range(16)] == [((x & 0b1011).bit_count() + 1) & 1 for x in range(16)]
    assert not affine.is_constant() and AffineOracle(4, 0, 1).is_constant()
    linear = LinearOracle(3, (0b011, 0b110))
    assert linear.num_outputs == 2
    for x in range(8):
        assert linear(x) == ((x & 0b011).bit_count() & 1) | (((x & 0b110).bit_count() & 1) << 1)
    _raises(ValueError, AffineOracle, 3, 8, 0)
    _raises(ValueError, LinearOracle, 2, (4,))


def test_walsh_hadamard_is_exact_and_invertible():
    for n in range(7):
        size = 1 << n
        vector = [(7 * x * x + 3 * x + 1) % 11 - 5 for x in range(size)]
        transformed = walsh.walsh_hadamard(vector)
        assert walsh.walsh_hadamard(transformed) == [size * v for v in vector]
        assert walsh.inverse_walsh_hadamard(transformed) == [Fraction(v) for v in vector]
        assert sum(v * v for v in transformed) == size * sum(v * v for v in vector)
        for y in range(size):
            assert transformed[y] == sum((-1) ** walsh.dot_parity(x, y) * vector[x] for x in range(size))
    _raises(ValueError, walsh.walsh_hadamard, [1, 2, 3])


def test_phase_oracle_amplitudes_are_normalised():
    for n in range(1, 6):
        table = [((x * 5 + 1) >> 2) & 1 for x in range(1 << n)]
        amplitudes = walsh.phase_oracle_amplitudes(table)
        assert sum(a * a for a in amplitudes) == 1


def test_gf2_elimination_matches_brute_force():
    vectors = [0b1011, 0b0110, 0b1101, 0b0000, 0b0110]
    width = 4
    assert gf2.rank(vectors) == 2
    kernel = gf2.nullspace(vectors, width)
    brute = [x for x in range(1 << width) if all(gf2.parity(v & x) == 0 for v in vectors)]
    space = gf2.AffineSubspace(width, 0, kernel)
    assert sorted(space.elements()) == brute
    constraints = [(0b1011, 1), (0b0110, 0)]
    solutions = gf2.solve_affine(constraints, width)
    brute = [x for x in range(1 << width)
             if all(gf2.parity(c & x) == s for c, s in constraints)]
    assert sorted(solutions.elements()) == brute
    assert solutions.uniform_probability == Fraction(1, len(brute))
    assert gf2.solve_affine([(0b11, 0), (0b11, 1)], 2) is None
    for x in range(1 << width):
        assert solutions.contains(x) == (x in brute)
    complement = gf2.AffineSubspace(width, 0, kernel).orthogonal_complement()
    assert gf2.rank(complement) == gf2.rank(vectors)
