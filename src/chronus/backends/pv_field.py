"""Exact PV scaling in F_257[phi], shared by fleet and device adapters."""
from chronus.core.scaling import PVScale

MODULUS = 257


def validate_pairs(values):
    """Copy and validate canonical residue pairs before any device conversion."""
    pairs = []
    for pair in values:
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError("each field element must contain two residues")
        if any(type(v) is not int or not 0 <= v < MODULUS for v in pair):
            raise ValueError("field residues must be integers in [0, 256]")
        pairs.append(tuple(pair))
    return pairs


def scale_pairs(values, index: int):
    """Multiply by phi**index using its exact period-516 field image."""
    factor = PVScale(index).field_factor()
    c, d = factor
    return [((a * c + b * d) % MODULUS,
             (a * d + b * c + b * d) % MODULUS)
            for a, b in validate_pairs(values)]
