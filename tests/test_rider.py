import pytest

from chronus.accounting.bookings import Rider

pytestmark = pytest.mark.real

def test_exact_index_ratio():
    r = Rider("2026-01-01", "USD", 100, 3, 2, "test-index", "base")
    assert r.cost(gb_num=3, gb_den=2, index_num=5, index_den=2) == 250


@pytest.mark.parametrize(
    ("gb_num", "gb_den", "expected"),
    [
        (7, 5, 1),
        (8, 5, 2),
        (3, 2, 2),
        (5, 2, 2),
        (2**54 + 3, 2, 2**53 + 2),
    ],
)
def test_cost_rounds_minor_units_half_even(gb_num, gb_den, expected):
    rider = Rider("2026-01-01", "USD", 1, 1, 1, "test-index", "base")
    assert rider.cost(gb_num=gb_num, gb_den=gb_den, index_num=1, index_den=1) == expected


@pytest.mark.parametrize("field,value", [("gb_den",0),("index_den",0),("index_num",0),("gb_num",True),("gb_num",-1)])
def test_invalid_index_quantities(field,value):
    r = Rider("2026-01-01", "USD", 100, 1, 1, "test-index", "base")
    inputs = dict(gb_num=1, gb_den=1, index_num=1, index_den=1)
    inputs[field] = value
    with pytest.raises(ValueError):
        r.cost(**inputs)
