"""Bounded generated algebraic checks; these do not prove universal claims."""
from fractions import Fraction
from hypothesis import given, settings, strategies as st
from hyba.unification.field import QPhi

rational = st.builds(Fraction, st.integers(-1000000, 1000000), st.integers(1, 1000))
phi_number = st.builds(QPhi, rational, rational)

@settings(max_examples=300, derandomize=True, deadline=None)
@given(phi_number, phi_number, phi_number)
def test_field_properties_and_roundtrip(x,y,z):
    zero, one = QPhi(0,0), QPhi(1,0)
    assert (x+y)+z == x+(y+z)
    assert (x*y)*z == x*(y*z)
    assert x*(y+z) == x*y+x*z
    assert QPhi.from_cyclotomic_coordinates(x.cyclotomic_coordinates()) == x
    if x != zero:
        assert x*x.inverse() == one
