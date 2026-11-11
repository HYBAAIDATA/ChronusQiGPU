"""Explicit bounded matrix-product contraction over Z[zeta_5].

The result is an unnormalized coordinate vector; all arithmetic uses ring
addition and multiplication. Dense output and large coefficients have costs.
"""
from chronus.quantum.geometric_polychoron import Cyclotomic5

MAX_SITES = 10
MAX_BOND = 4


def contract_mps(sites):
    """Contract tensors indexed [left][physical=2][right] exactly.

    Outer bonds must be 1, adjacent bond dimensions must match, and all
    coefficients must be Cyclotomic5. Reject invalid or oversized inputs.
    """
    if not isinstance(sites, (list, tuple)):
        raise TypeError('sites must be a list or tuple')
    if not 1 <= len(sites) <= MAX_SITES:
        raise ValueError('invalid site count')
    previous_right = 1
    for site in sites:
        if not isinstance(site, (list, tuple)) or len(site) != previous_right:
            raise ValueError('left bond mismatch')
        right = None
        for left in site:
            if not isinstance(left, (list, tuple)) or len(left) != 2:
                raise ValueError('physical dimension must be two')
            for physical in left:
                if not isinstance(physical, (list, tuple)) or not 1 <= len(physical) <= MAX_BOND:
                    raise ValueError('invalid right bond')
                if right is None:
                    right = len(physical)
                if len(physical) != right:
                    raise ValueError('ragged right bond')
                if not all(isinstance(x, Cyclotomic5) for x in physical):
                    raise TypeError('entries must be Cyclotomic5')
        previous_right = right
    if previous_right != 1:
        raise ValueError('final bond must be one')
    current = [[Cyclotomic5.one()]]
    for site in sites:
        right = len(site[0][0])
        next_rows = []
        for row in current:
            for physical in range(2):
                out = []
                for r in range(right):
                    value = Cyclotomic5.zero()
                    for l, coefficient in enumerate(row):
                        value = value + coefficient*site[l][physical][r]
                    out.append(value)
                next_rows.append(out)
        current = next_rows
    return tuple(row[0] for row in current)
