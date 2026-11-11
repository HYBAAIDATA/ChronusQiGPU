import sys
from fractions import Fraction
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[1] / "src")
if sys.path[:1] != [_SRC]:
    sys.path.insert(0, _SRC)

from turing.algorithms import simon  # noqa: E402
from turing.algorithms.oracles import FunctionOracle  # noqa: E402

PERIODS = {
    2: (1, 2, 3),
    3: (1, 3, 5, 6, 7),
    4: (1, 6, 9, 10, 15),
    5: (3, 12, 17, 21, 30, 31),
}


def _periodic_oracle(n, s):
    """f(x) = label of the pair {x, x xor s}; labels are distinct per pair."""
    return FunctionOracle.from_function(1 << n, lambda x: 5 * min(x, x ^ s) + 11)


def test_distribution_is_uniform_on_the_orthogonal_complement():
    for n, periods in PERIODS.items():
        for s in periods:
            result = simon.run(n, _periodic_oracle(n, s))
            for y, probability in enumerate(result.distribution):
                orthogonal = ((y & s).bit_count() & 1) == 0
                assert probability == (Fraction(1, 1 << (n - 1)) if orthogonal else 0)
            assert sum(result.distribution) == 1
            assert result.hidden_period == s
            assert result.support_rank == n - 1
            assert len(result.support) == 1 << (n - 1)


def test_injective_oracle_gives_the_uniform_distribution():
    for n in range(2, 6):
        oracle = FunctionOracle.from_function(1 << n, lambda x: (x * 7 + 3) % (1 << n))
        result = simon.run(n, oracle)
        assert all(p == Fraction(1, 1 << n) for p in result.distribution)
        assert result.hidden_period == 0
        assert result.support_rank == n


def test_folded_distribution_matches_the_unfolded_amplitudes():
    for n, periods in PERIODS.items():
        for s in periods[:2]:
            oracle = _periodic_oracle(n, s)
            table = [oracle(x) for x in range(1 << n)]
            values = sorted(set(table))
            expected = []
            for y in range(1 << n):
                total = Fraction(0)
                for v in values:
                    amplitude = Fraction(sum((-1) ** ((x & y).bit_count() & 1)
                                             for x in range(1 << n) if table[x] == v), 1 << n)
                    total += amplitude * amplitude
                expected.append(total)
            assert simon.outcome_distribution(n, oracle) == tuple(expected)


def test_promise_violations_are_rejected():
    for table in ([7, 7, 7, 7], [1, 1, 1, 2, 3, 4, 5, 6], [1, 1, 2, 3, 2, 3, 4, 4]):
        n = len(table).bit_length() - 1
        try:
            simon.run(n, FunctionOracle.from_list(table))
        except ValueError as error:
            assert "Simon promise" in str(error)
        else:
            raise AssertionError(f"{table} violates Simon's promise")
