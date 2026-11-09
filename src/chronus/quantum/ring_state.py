"""Bounded exact coordinate vectors over Z[zeta_5].

This module represents algebraic coefficients, not probabilities or normalized
physical states. Coordinates are explicit; no complexity advantage is implied.
"""
from chronus.quantum.geometric_polychoron import Cyclotomic5

MAX_COORDINATES = 256


def scale_element(scalar, element):
    """Apply ring multiplication to one coefficient."""
    if not isinstance(scalar, Cyclotomic5) or not isinstance(element, Cyclotomic5):
        raise TypeError('expected Cyclotomic5 elements')
    return scalar * element


def scale_vector(scalar, vector):
    """Apply the same multiplication independently to each coordinate."""
    if not isinstance(scalar, Cyclotomic5):
        raise TypeError('expected Cyclotomic5 scalar')
    if not isinstance(vector, (tuple, list)):
        raise TypeError('expected explicit list or tuple')
    if not 1 <= len(vector) <= MAX_COORDINATES:
        raise ValueError('coordinate count outside bounds')
    if not all(isinstance(x, Cyclotomic5) for x in vector):
        raise TypeError('expected Cyclotomic5 coordinates')
    return tuple(scale_element(scalar, x) for x in vector)
