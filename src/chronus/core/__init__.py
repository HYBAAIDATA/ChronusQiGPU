"""Chronus exact-arithmetic kernel: the unified mathematical core.

Single import surface for every exact ring and fold structure in the
substrate. Zero floating point: every value is an integer, a Fraction, a
finite-field element, or an exact algebraic pair.

    Z[phi] / Q(sqrt(5))  ->  PhiElement, phi_power, verify_fold
    metallic means       ->  MetallicElement, metallic_power, metallic_sequence
    Zeckendorf folding   ->  zeckendorf_encode/decode/increment, fold_pair
    limb encoding        ->  encode_int256, decode_int256
"""

from chronus.backends.lattice import (
    HardwareUnavailableError,
    LatticeOverflowError,
    ParityVerificationError,
    PhiElement,
    phi_power,
    verify_fold,
)
from chronus.backends.limbs import decode_int256, encode_int256
from chronus.backends.metallic import (
    MetallicElement,
    metallic_power,
    metallic_sequence,
)
from chronus.core.facade import ChronusVerificationOrchestrator
from chronus.core.scaling import PVScale
from chronus.execution.structural import (
    fold_pair,
    unfold_pair,
    zeckendorf_decode,
    zeckendorf_encode,
    zeckendorf_increment,
)

__all__ = [
    "ChronusVerificationOrchestrator",
    "HardwareUnavailableError",
    "LatticeOverflowError",
    "MetallicElement",
    "PVScale",
    "ParityVerificationError",
    "PhiElement",
    "decode_int256",
    "encode_int256",
    "fold_pair",
    "metallic_power",
    "metallic_sequence",
    "phi_power",
    "unfold_pair",
    "verify_fold",
    "zeckendorf_decode",
    "zeckendorf_encode",
    "zeckendorf_increment",
]
