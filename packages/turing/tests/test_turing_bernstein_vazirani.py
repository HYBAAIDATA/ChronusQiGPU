import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[1] / "src")
if sys.path[:1] != [_SRC]:
    sys.path.insert(0, _SRC)

from turing.algorithms import bernstein_vazirani  # noqa: E402
from turing.algorithms.oracles import BooleanOracle  # noqa: E402


def test_every_hidden_string_is_recovered_with_probability_one():
    for n in range(1, 7):
        for s in range(1 << n):
            for b in (0, 1):
                oracle = BooleanOracle.from_predicate(1 << n, lambda x: ((s & x).bit_count() + b) & 1)
                result = bernstein_vazirani.run(n, oracle)
                assert result.hidden_string == s
                assert result.offset == b
                assert result.probability == 1
                assert sum(result.distribution) == 1
                assert all(p == 0 for y, p in enumerate(result.distribution) if y != s)


def test_non_affine_oracle_is_rejected():
    for n in range(2, 7):
        oracle = BooleanOracle.from_predicate(1 << n, lambda x: 1 if x == 3 else 0)
        try:
            bernstein_vazirani.run(n, oracle)
        except ValueError as error:
            assert "s.x xor b" in str(error)
        else:
            raise AssertionError("x -> [x == 3] is not affine")
