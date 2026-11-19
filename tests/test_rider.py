from fractions import Fraction
import pytest
from chronus.accounting.bookings import Rider, settlement

def test_exact_index_ratio():
    r = Rider("2026-01-01", "USD", 100, 3, 2, "test-index", "base")
    assert r.cost(gb_num=3, gb_den=2, index_num=5, index_den=2) == 250

@pytest.mark.parametrize("field,value", [("gb_den",0),("index_den",0),("index_num",0),("gb_num",True),("gb_num",-1)])
def test_invalid_index_quantities(field,value):
    r = Rider("2026-01-01", "USD", 100, 1, 1, "test-index", "base")
    inputs = dict(gb_num=1, gb_den=1, index_num=1, index_den=1)
    inputs[field] = value
    with pytest.raises(ValueError):
        r.cost(**inputs)
