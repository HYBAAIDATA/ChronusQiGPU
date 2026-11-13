import sys
from fractions import Fraction
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[1] / "src")
if sys.path[:1] != [_SRC]:
    sys.path.insert(0, _SRC)

from turing.algorithms import deutsch_jozsa  # noqa: E402
from turing.algorithms.oracles import BooleanOracle  # noqa: E402


def _balanced_tables(n):
    size = 1 << n
    tables = [[(x >> i) & 1 for x in range(size)] for i in range(n)]
    tables.append([1 if x < size // 2 else 0 for x in range(size)])
    if n >= 2:
        tables.append([(x.bit_count() + (x >> (n - 1))) & 1 for x in range(size)])
        order = sorted(range(size), key=lambda x: (x * 7 + 3) % size)
        chosen = set(order[: size // 2])
        tables.append([1 if x in chosen else 0 for x in range(size)])
    return tables


def test_constant_oracles_give_probability_exactly_one():
    for n in range(1, 7):
        for value in (0, 1):
            result = deutsch_jozsa.run(n, BooleanOracle.from_list([value] * (1 << n)))
            assert result.probability_all_zero == 1
            assert isinstance(result.probability_all_zero, Fraction)
            assert result.verdict == "constant"
            assert sum(result.distribution) == 1


def test_balanced_oracles_give_probability_exactly_zero():
    for n in range(1, 7):
        for table in _balanced_tables(n):
            assert sum(table) * 2 == 1 << n
            result = deutsch_jozsa.run(n, BooleanOracle.from_list(table))
            assert result.probability_all_zero == 0
            assert result.verdict == "balanced"
            assert sum(result.distribution) == 1


def test_promise_violation_is_rejected():
    for n in range(2, 7):
        table = [0] * (1 << n)
        table[3] = 1
        try:
            deutsch_jozsa.run(n, BooleanOracle.from_list(table))
        except ValueError as error:
            assert "promise" in str(error)
        else:
            raise AssertionError("an oracle with a single one is neither constant nor balanced")


def test_domain_must_match_register():
    try:
        deutsch_jozsa.run(3, BooleanOracle.from_list([0, 1, 1, 0]))
    except ValueError:
        pass
    else:
        raise AssertionError("domain_size 4 does not match n = 3")
