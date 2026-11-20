import pytest

from chronus.accounting.bookings import Rider

pytestmark = pytest.mark.real

def test_exact_index_ratio():
    r = Rider("2026-01-01", "USD", 100, 3, 2, "test-index", "base")
    assert r.cost(gb_num=3, gb_den=2, index_num=5, index_den=2) == 250

@pytest.mark.parametrize(
    "numerator,denominator,expected",
    [(7, 5, 1), (3, 2, 2), (5, 2, 2), (13, 5, 3), (2**54 + 2, 2, 2**53 + 1)],
)
def test_cost_rounds_half_even_at_the_minor_unit(numerator, denominator, expected):
    rider = Rider("2026-01-01", "USD", 1, 1, 1, "test-index", "base")
    assert rider.cost(gb_num=numerator, gb_den=denominator, index_num=1, index_den=1) == expected


@pytest.mark.parametrize("field,value", [("gb_den",0),("index_den",0),("index_num",0),("gb_num",True),("gb_num",-1)])
def test_invalid_index_quantities(field,value):
    r = Rider("2026-01-01", "USD", 100, 1, 1, "test-index", "base")
    inputs = dict(gb_num=1, gb_den=1, index_num=1, index_den=1)
    inputs[field] = value
    with pytest.raises(ValueError):
        r.cost(**inputs)
