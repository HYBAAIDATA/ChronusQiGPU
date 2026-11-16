"""Bounded unnormalised matrix-product-state contraction in Z[zeta_5].

Experimental reference path; no physical measurement or approximate inputs.
The output grows exponentially and is explicitly bounded (<= 65,536
coefficients, <= 16 sites). The conventional normalisation step is
deliberately not applied: it may leave the ring. Notion trace: recovered
PULVINI tensor-train contract — the archived ``astype(float)`` defect was
a real defect in the archive only; this module implements an independent
exact Q-valued factorisation and must not be read as the archived engine.
"""
from chronus.quantum.geometric_polychoron import Cyclotomic5

MAX_SITES = 16


def contract(sites):
    """Expand a rank-three MPS as tuples in lexicographic physical-index order.

    Each site is indexed [left bond][physical index][right bond]. Bond and
    physical dimensions must be nonzero, and open boundaries must be one.
    Entries must be Cyclotomic5, never floats. No truncation is performed.
    """
    if not isinstance(sites, (list, tuple)) or not 1 <= len(sites) <= MAX_SITES:
        raise ValueError('site count outside bounded range')
    previous = 1
    physical_sizes = []
    for site in sites:
        if not isinstance(site, (list, tuple)) or len(site) != previous:
            raise ValueError('left bond mismatch')
        if not isinstance(site[0], (list, tuple)) or not site[0]:
            raise ValueError('empty physical dimension')
        physical = len(site[0])
        if not isinstance(site[0][0], (list, tuple)) or not site[0][0]:
            raise ValueError('empty right bond')
        right = len(site[0][0])
        for left in site:
            if not isinstance(left, (list, tuple)) or len(left) != physical:
                raise ValueError('ragged physical dimension')
            for row in left:
                if not isinstance(row, (list, tuple)) or len(row) != right:
                    raise ValueError('ragged right bond')
                if any(not isinstance(value, Cyclotomic5) for value in row):
                    raise TypeError('all coefficients must be Cyclotomic5')
        physical_sizes.append(physical)
        previous = right
    if previous != 1:
        raise ValueError('right boundary must be one')
    if __import__('math').prod(physical_sizes) > 65536:
        raise ValueError('output dimension exceeds 65536')
    states = [(Cyclotomic5.one(),)]
    for site in sites:
        right, physical = len(site[0][0]), len(site[0])
        next_states = []
        for vector in states:
            for p in range(physical):
                next_states.append(tuple(
                    sum((vector[l] * site[l][p][r] for l in range(len(vector))), Cyclotomic5.zero())
                    for r in range(right)))
        states = next_states
    return tuple(v[0] for v in states)
